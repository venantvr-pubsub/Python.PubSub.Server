import json
import logging
import os
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

import flask
from collections import deque
from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, request, send_from_directory
from flask_socketio import SocketIO, join_room
from python_sqlite_async import AsyncSQLite

# Import de votre nouvelle librairie

# 1. Configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(threadName)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()
DB_FILE_NAME = os.getenv("DATABASE_FILE", ":memory:")
MAX_ROWS_PER_TABLE = int(os.getenv("MAX_ROWS_PER_TABLE", "5000"))

# Configuration du nettoyage en arrière-plan
CLEANUP_INTERVAL = int(os.getenv("CLEANUP_INTERVAL", "30"))  # Secondes entre chaque vérification
CLEANUP_MAX_LOAD_THRESHOLD = float(os.getenv("CLEANUP_MAX_LOAD_THRESHOLD", "10.0"))  # Requêtes/seconde max pour autoriser le nettoyage
CLEANUP_LOAD_WINDOW = int(os.getenv("CLEANUP_LOAD_WINDOW", "60"))  # Fenêtre d'observation de la charge en secondes

# 2. Initialisation de la base de données via la librairie
db = AsyncSQLite(DB_FILE_NAME)


# 3. Surveillance de la charge
class LoadMonitor:
    """
    Surveille la charge du serveur en comptant les requêtes sur une fenêtre de temps glissante.
    """

    def __init__(self, window_seconds: int = 60) -> None:
        self.window_seconds = window_seconds
        self.request_timestamps: deque = deque()
        self.lock = threading.Lock()

    def record_request(self) -> None:
        """Enregistre une nouvelle requête."""
        with self.lock:
            now = time.time()
            self.request_timestamps.append(now)
            # Nettoie les anciennes entrées en dehors de la fenêtre
            cutoff = now - self.window_seconds
            while self.request_timestamps and self.request_timestamps[0] < cutoff:
                self.request_timestamps.popleft()

    def get_requests_per_second(self) -> float:
        """Retourne le nombre moyen de requêtes par seconde sur la fenêtre."""
        with self.lock:
            now = time.time()
            cutoff = now - self.window_seconds
            # Nettoie les anciennes entrées
            while self.request_timestamps and self.request_timestamps[0] < cutoff:
                self.request_timestamps.popleft()

            count = len(self.request_timestamps)
            if count == 0:
                return 0.0

            # Calcule la durée réelle couverte par les requêtes
            if count == 1:
                return 1.0 / self.window_seconds

            oldest = self.request_timestamps[0]
            duration = now - oldest
            return count / max(duration, 1.0)

    def is_low_load(self, threshold: float) -> bool:
        """Vérifie si la charge est en dessous du seuil."""
        return self.get_requests_per_second() < threshold


# 4. Le Broker simplifié
# noinspection PyShadowingNames
class Broker:
    """
    Sert d'interface entre la logique de l'application et la librairie
    de base de données asynchrone.
    """

    def __init__(self, db_manager: AsyncSQLite, max_rows: int = 5000, load_monitor: Optional[LoadMonitor] = None,
                 cleanup_interval: int = 30, cleanup_threshold: float = 10.0) -> None:
        self.db = db_manager
        self.max_rows = max_rows
        self.load_monitor = load_monitor
        self.cleanup_interval = cleanup_interval
        self.cleanup_threshold = cleanup_threshold
        self.cleanup_thread: Optional[threading.Thread] = None
        self.cleanup_running = False

    def cleanup_old_rows(self, table_name: str, order_column: str) -> None:
        """
        Supprime les anciennes lignes d'une table si elle dépasse max_rows.
        Garde les lignes les plus récentes selon order_column.
        """
        if self.max_rows <= 0:
            return

        sql = f"""
        DELETE FROM {table_name}
        WHERE rowid IN (
            SELECT rowid FROM {table_name}
            ORDER BY {order_column} DESC
            LIMIT -1 OFFSET ?
        )
        """
        self.db.execute_write(sql, (self.max_rows,))

    def _background_cleanup_loop(self) -> None:
        """
        Boucle de nettoyage en arrière-plan qui s'exécute périodiquement
        uniquement pendant les périodes de faible charge.
        """
        logger.info(f"Background cleanup thread started (interval={self.cleanup_interval}s, threshold={self.cleanup_threshold} req/s)")

        while self.cleanup_running:
            try:
                time.sleep(self.cleanup_interval)

                if not self.cleanup_running:
                    break

                # Vérifie si la charge est faible
                if self.load_monitor and not self.load_monitor.is_low_load(self.cleanup_threshold):
                    current_load = self.load_monitor.get_requests_per_second()
                    logger.debug(f"Skipping cleanup: load too high ({current_load:.2f} req/s > {self.cleanup_threshold} req/s)")
                    continue

                # Exécute le nettoyage sur toutes les tables
                logger.info("Starting background cleanup of tables...")
                start_time = time.time()

                self.cleanup_old_rows("subscriptions", "connected_at")
                self.cleanup_old_rows("messages", "timestamp")
                self.cleanup_old_rows("consumptions", "timestamp")

                elapsed = time.time() - start_time
                logger.info(f"Background cleanup completed in {elapsed:.2f}s")

            except Exception as e:
                logger.error(f"Error in background cleanup loop: {e}", exc_info=True)

        logger.info("Background cleanup thread stopped")

    def start_cleanup_thread(self) -> None:
        """Démarre le thread de nettoyage en arrière-plan."""
        if self.cleanup_thread is not None and self.cleanup_thread.is_alive():
            logger.warning("Cleanup thread is already running")
            return

        self.cleanup_running = True
        self.cleanup_thread = threading.Thread(target=self._background_cleanup_loop, daemon=True, name="CleanupThread")
        self.cleanup_thread.start()
        logger.info("Background cleanup thread started")

    def stop_cleanup_thread(self) -> None:
        """Arrête le thread de nettoyage en arrière-plan."""
        if self.cleanup_thread is None or not self.cleanup_thread.is_alive():
            logger.warning("Cleanup thread is not running")
            return

        logger.info("Stopping background cleanup thread...")
        self.cleanup_running = False
        if self.cleanup_thread:
            self.cleanup_thread.join(timeout=5)
        logger.info("Background cleanup thread stopped")

    def register_subscription(self, sid: str, consumer: str, topic: str) -> None:
        if not all([sid, consumer, topic]):
            logger.warning("register_subscription: Paramètres requis manquants")
            return

        if self.load_monitor:
            self.load_monitor.record_request()

        sql = "INSERT OR REPLACE INTO subscriptions (sid, consumer, topic, connected_at) VALUES (?, ?, ?, ?)"
        params = (sid, consumer, topic, time.time())
        self.db.execute_write(sql, params)
        socketio.emit("new_client", {"consumer": consumer, "topic": topic, "connected_at": time.time()})

    def unregister_client(self, sid: str) -> None:
        client_info = self.get_client_by_sid(sid)
        consumer, topic = (None, None)
        if client_info:
            consumer, topic = client_info

        sql = "DELETE FROM subscriptions WHERE sid = ?"
        self.db.execute_write(sql, (sid,))

        if consumer and topic:
            socketio.emit("client_disconnected", {"consumer": consumer, "topic": topic})

    def save_message(self, topic: str, message_id: str, message: Any, producer: str) -> None:
        if self.load_monitor:
            self.load_monitor.record_request()

        sql = "INSERT INTO messages (topic, message_id, message, producer, timestamp) VALUES (?, ?, ?, ?, ?)"
        message_json = json.dumps(message) if not isinstance(message, str) else message
        params = (topic, message_id, message_json, producer, time.time())
        self.db.execute_write(sql, params)
        socketio.emit("new_message", {"topic": topic, "message_id": message_id, "message": message, "producer": producer, "timestamp": time.time()})

    def save_consumption(self, consumer: str, topic: str, message_id: str, message: Any) -> None:
        if self.load_monitor:
            self.load_monitor.record_request()

        sql = "INSERT INTO consumptions (consumer, topic, message_id, message, timestamp) VALUES (?, ?, ?, ?, ?)"
        message_json = json.dumps(message) if not isinstance(message, str) else message
        params = (consumer, topic, message_id, message_json, time.time())
        self.db.execute_write(sql, params)
        socketio.emit("new_consumption", {"consumer": consumer, "topic": topic, "message_id": message_id, "message": message, "timestamp": time.time()})

    def get_client_by_sid(self, sid: str) -> Optional[Tuple[str, str]]:
        sql = "SELECT consumer, topic FROM subscriptions WHERE sid = ?"
        return self.db.execute_read(sql, (sid,), fetch="one")

    def get_clients(self) -> List[Dict[str, Any]]:
        rows = self.db.execute_read("SELECT consumer, topic, connected_at FROM subscriptions ORDER BY connected_at DESC LIMIT 100")
        return [{"consumer": r[0], "topic": r[1], "connected_at": r[2]} for r in rows]

    def get_messages(self) -> List[Dict[str, Any]]:
        rows = self.db.execute_read("SELECT topic, message_id, message, producer, timestamp FROM messages ORDER BY timestamp DESC LIMIT 100")
        # Gère le cas où le JSON est invalide ou vide
        messages = []
        for r in rows:
            try:
                message_content = json.loads(r[2]) if r[2] else {}
            except json.JSONDecodeError:
                message_content = {"error": "Invalid JSON", "raw": r[2]}
            messages.append({"topic": r[0], "message_id": r[1], "message": message_content, "producer": r[3], "timestamp": r[4]})
        return messages

    def get_consumptions(self) -> List[Dict[str, Any]]:
        rows = self.db.execute_read("SELECT consumer, topic, message_id, message, timestamp FROM consumptions ORDER BY timestamp DESC LIMIT 100")
        consumptions = []
        for r in rows:
            try:
                message_content = json.loads(r[3]) if r[3] else {}
            except json.JSONDecodeError:
                message_content = {"error": "Invalid JSON", "raw": r[3]}
            consumptions.append({"consumer": r[0], "topic": r[1], "message_id": r[2], "message": message_content, "timestamp": r[4]})
        return consumptions

    def get_graph_state(self) -> Dict[str, Any]:
        producers = [row[0] for row in self.db.execute_read("SELECT DISTINCT producer FROM messages")]
        consumers = [row[0] for row in self.db.execute_read("SELECT DISTINCT consumer FROM subscriptions UNION SELECT DISTINCT consumer FROM consumptions")]
        topics = [row[0] for row in self.db.execute_read("SELECT DISTINCT topic FROM messages UNION SELECT DISTINCT topic FROM subscriptions")]
        subscriptions = [{"source": row[0], "target": row[1], "type": "consume"} for row in self.db.execute_read("SELECT topic, consumer FROM subscriptions")]
        publications = [{"source": row[0], "target": row[1], "type": "publish"} for row in self.db.execute_read("SELECT DISTINCT producer, topic FROM messages")]
        return {"producers": producers, "consumers": consumers, "topics": topics, "links": subscriptions + publications}


# 5. Initialisation de Flask, SocketIO, LoadMonitor et du Broker
app = Flask(__name__)
app.config["SECRET_KEY"] = "secret!"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")
load_monitor = LoadMonitor(window_seconds=CLEANUP_LOAD_WINDOW)
broker = Broker(db, max_rows=MAX_ROWS_PER_TABLE, load_monitor=load_monitor,
                cleanup_interval=CLEANUP_INTERVAL, cleanup_threshold=CLEANUP_MAX_LOAD_THRESHOLD)


# 6. Routes Flask et Handlers SocketIO
@app.route("/publish", methods=["POST"])
def publish() -> Tuple[flask.Response, int]:
    data = request.json
    if not data:
        return jsonify({"status": "error", "message": "Invalid JSON"}), 400
    topic, msg_id, msg, prod = data.get("topic"), data.get("message_id"), data.get("message"), data.get("producer")
    if not all([topic, msg_id, msg, prod]):
        return jsonify({"status": "error", "message": "Missing topic, message_id, message, or producer"}), 400

    logger.info(f"Publishing message {msg_id} to topic {topic} by {prod}")
    broker.save_message(topic=topic, message_id=msg_id, message=msg, producer=prod)
    socketio.emit("message", data, to=topic)
    return jsonify({"status": "ok"}), 200


@app.route("/clients")
def clients() -> flask.Response:
    return jsonify(broker.get_clients())


@app.route("/messages")
def messages() -> flask.Response:
    return jsonify(broker.get_messages())


@app.route("/consumptions")
def consumptions() -> flask.Response:
    return jsonify(broker.get_consumptions())


@app.route("/graph/state")
def graph_state() -> flask.Response:
    return jsonify(broker.get_graph_state())


@app.route("/health")
def health_check() -> Tuple[flask.Response, int]:
    try:
        # Fait un simple test de lecture pour vérifier que la connexion fonctionne
        broker.get_clients()
        return jsonify({"status": "healthy", "timestamp": time.time()}), 200
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({"status": "unhealthy", "error": str(e)}), 503


@app.route("/")
def index() -> flask.Response:
    return redirect("/control-panel.html")


@app.route("/control-panel.html")
def serve_control_panel() -> flask.Response:
    return send_from_directory(".", "control-panel.html")


@app.route("/static/<path:filename>")
def serve_static(filename: str) -> flask.Response:
    return send_from_directory("static", filename)


@app.route("/activity-map.html")
def serve_activity_map() -> flask.Response:
    return send_from_directory(".", "activity-map.html")


@app.route("/circular-graph.html")
def serve_circular_graph() -> flask.Response:
    return send_from_directory(".", "circular-graph.html")


# noinspection PyUnresolvedReferences
@socketio.on("subscribe")
def handle_subscribe(data: Dict[str, Any]) -> None:
    sid = request.sid
    consumer, topics = data.get("consumer"), data.get("topics", [])
    if not all([sid, consumer, topics]):
        logger.warning(f"Invalid subscribe data from {sid}: {data}")
        return

    logger.info(f"Subscribing {consumer} (SID: {sid}) to topics: {topics}")
    for topic in topics:
        join_room(topic)
        broker.register_subscription(sid, consumer, topic)


@socketio.on("consumed")
def handle_consumed(data: Dict[str, Any]) -> None:
    consumer, topic, msg_id, msg = data.get("consumer"), data.get("topic"), data.get("message_id"), data.get("message")
    if not all([consumer, topic, msg_id]):
        logger.warning(f"Incomplete consumption data received: {data}")
        return
    broker.save_consumption(consumer, topic, msg_id, msg)


# noinspection PyUnresolvedReferences
@socketio.on("disconnect")
def handle_disconnect() -> None:
    sid = request.sid
    logger.info(f"Client disconnecting (SID: {sid})")
    broker.unregister_client(sid)


# 6. Point d'entrée principal
def configure_sqlite_performance() -> None:
    """Configure SQLite pour des performances optimales."""
    logger.info("Configuring SQLite performance settings...")

    # WAL mode pour permettre les lectures concurrentes
    # Essentiel pour le multi-threading
    db.execute_write("PRAGMA journal_mode = WAL")

    # Cache de 64 Mo (64000 pages de 1024 bytes)
    # Augmente significativement les performances en lecture/écriture
    db.execute_write("PRAGMA cache_size = -64000")

    # Synchronous NORMAL pour un bon compromis performance/sécurité
    # FULL serait trop lent, OFF trop risqué
    db.execute_write("PRAGMA synchronous = NORMAL")

    # Augmente la taille de page à 4096 pour de meilleures performances
    # Doit être fait AVANT la création des tables
    db.execute_write("PRAGMA page_size = 4096")

    # Active le memory-mapped I/O pour améliorer les performances
    # 256 MB de mmap
    db.execute_write("PRAGMA mmap_size = 268435456")

    # Optimise les jointures et les requêtes complexes
    db.execute_write("PRAGMA optimize")

    # Vérifie et log les paramètres
    journal_mode = db.execute_read("PRAGMA journal_mode", fetch="one")
    cache_size = db.execute_read("PRAGMA cache_size", fetch="one")
    synchronous = db.execute_read("PRAGMA synchronous", fetch="one")

    logger.info(f"SQLite configuration: journal_mode={journal_mode}, cache_size={cache_size}, synchronous={synchronous}")


def main() -> None:
    """Démarre le worker BDD, gère l'init du schéma, puis lance le serveur Flask."""

    # Le chemin des scripts de migration
    migration_001 = os.path.join(os.path.dirname(__file__), 'migrations', '001_add_message_id_and_producer.sql')
    migration_002 = os.path.join(os.path.dirname(__file__), 'migrations', '002_optimize_performance.sql')
    migration_001 = os.path.normpath(migration_001)
    migration_002 = os.path.normpath(migration_002)

    # NOUVEAU : Démarrage simple du worker
    # La méthode start() ne fait plus que lancer le thread.
    db.start()

    logger.info("Main thread waiting for database to be ready...")
    if not db.wait_for_ready(timeout=10):
        logger.error("Database worker failed to initialize in time. Exiting.")
        db.stop()
        return

    # Configuration SQLite pour la performance
    try:
        configure_sqlite_performance()
    except Exception as e:
        logger.error(f"Failed to configure SQLite performance settings: {e}", exc_info=True)

    # NOUVEAU : Logique de migration explicite
    try:
        logger.info("Checking for 'messages' table to decide on migration...")
        # On vérifie manuellement si la table existe
        res = db.execute_read("SELECT name FROM sqlite_master WHERE type='table' AND name=?", ("messages",))

        if not res:
            logger.info("Table 'messages' not found, running migration 001...")
            # Si elle n'existe pas, on exécute le script
            db.execute_script(migration_001)

            # NOUVEAU et ESSENTIEL : On attend la fin de la migration
            # db.sync() bloque jusqu'à ce que toutes les commandes en file (y compris notre script) soient terminées.
            if not db.sync(timeout=15):
                raise RuntimeError("Migration 001 failed to complete in time.")
            logger.info("Migration 001 finished successfully.")
        else:
            logger.info("Table 'messages' already exists, skipping migration 001.")

        # Vérifie si la migration 002 doit être appliquée (check si un trigger existe encore)
        logger.info("Checking if migration 002 needs to be applied...")
        triggers = db.execute_read("SELECT name FROM sqlite_master WHERE type='trigger' AND name='trim_messages'")

        if triggers:
            logger.info("Old triggers found, running migration 002 to optimize performance...")
            db.execute_script(migration_002)

            if not db.sync(timeout=15):
                raise RuntimeError("Migration 002 failed to complete in time.")
            logger.info("Migration 002 finished successfully - triggers removed and composite indexes added.")
        else:
            logger.info("Migration 002 already applied or not needed.")

    except Exception as e:
        logger.error(f"An error occurred during migration check: {e}", exc_info=True)
        db.stop()
        return

    logger.info("Database is ready. Starting background cleanup thread...")
    broker.start_cleanup_thread()

    logger.info("Starting Flask-SocketIO server on port 5000.")
    try:
        socketio.run(app, host="0.0.0.0", port=5000, log_output=False, use_reloader=False)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received.")
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
    finally:
        logger.info("Shutting down...")
        broker.stop_cleanup_thread()
        db.stop()
        logger.info("Shutdown complete.")


if __name__ == "__main__":
    main()
