import json
import logging
import os
import sqlite3
import threading
import time
from collections import deque
from os import path
from typing import Any, Dict, List, Optional, Tuple

import flask
from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, request, send_from_directory
from flask_socketio import SocketIO, emit, join_room

# 1. Configuration du logging (avec format amélioré pour le multithreading)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(threadName)s - %(message)s')
logger = logging.getLogger(__name__)

# 2. Chargement de la configuration et définition des variables globales
load_dotenv()
DB_FILE_NAME = os.getenv("DATABASE_FILE", ":memory:")

# Si on utilise :memory:, on doit utiliser un URI spécial pour partager la connexion entre threads
if DB_FILE_NAME == ":memory:":
    DB_FILE_NAME = "file::memory:?cache=shared"

db_write_queue = deque()
db_write_queue_lock = threading.Lock()  # Protection pour les ajouts concurrents
db_ready_event = threading.Event()


def init_db(db_name: str = ":memory:", connection: Optional[sqlite3.Connection] = None) -> sqlite3.Connection:
    """
    Initialise le schéma de la base de données. Utilisé pour les tests.

    Args:
        db_name: Nom de la base de données
        connection: Connexion existante (optionnelle)

    Returns:
        La connexion à la base de données
    """
    if connection is None:
        connection = sqlite3.connect(db_name, timeout=30.0)

    migration_script = "migrations/001_add_message_id_and_producer.sql"
    if path.exists(migration_script):
        with open(migration_script) as f:
            connection.executescript(f.read())
        logger.info("Migration script executed successfully.")
    else:
        # Schéma par défaut si le fichier de migration n'existe pas
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                sid TEXT PRIMARY KEY,
                consumer TEXT NOT NULL,
                topic TEXT NOT NULL,
                connected_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT NOT NULL,
                message_id TEXT NOT NULL,
                message TEXT NOT NULL,
                producer TEXT NOT NULL,
                timestamp REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS consumptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                consumer TEXT NOT NULL,
                topic TEXT NOT NULL,
                message_id TEXT NOT NULL,
                message TEXT NOT NULL,
                timestamp REAL NOT NULL
            );
        """)
        logger.info("Default schema created.")

    connection.commit()
    return connection


class DatabaseWorker(threading.Thread):
    """
    Thread dédié qui gère toutes les écritures dans la base de données.
    """

    def __init__(self, db_name: str, stop_event: threading.Event) -> None:
        super().__init__(name="DatabaseWorker")
        self.db_name = db_name
        self.daemon = True
        self._stop_event = stop_event

    def run(self) -> None:
        """Boucle principale du worker : initialise la BDD, signale qu'il est prêt, puis traite la file."""
        conn = None
        try:
            # Pour les bases en mémoire partagées, on doit utiliser uri=True
            if self.db_name.startswith("file:"):
                conn = sqlite3.connect(self.db_name, timeout=30.0, check_same_thread=False, uri=True)
            else:
                conn = sqlite3.connect(self.db_name, timeout=30.0, check_same_thread=False)

            if not self.db_name.startswith("file::memory:"):
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA busy_timeout=30000")

            logger.info("Initializing database...")
            self._init_schema(conn)
            logger.info("Database is ready.")
            db_ready_event.set()

            while not self._stop_event.is_set():
                try:
                    with db_write_queue_lock:
                        task = db_write_queue.popleft()

                    if task is None:
                        continue

                    sql, params = task
                    conn.execute(sql, params)
                    conn.commit()
                except IndexError:
                    time.sleep(0.01)
                except sqlite3.Error as e:
                    logger.error(f"Database write error: {e}")
                except Exception as e:
                    logger.error(f"Unexpected error in database worker: {e}")
        except Exception as e:
            logger.error(f"Fatal error in database worker: {e}")
        finally:
            if conn is not None:
                conn.close()
                logger.info("Database connection closed.")

    # noinspection PyMethodMayBeStatic
    def _init_schema(self, conn: sqlite3.Connection) -> None:
        """Exécute le script de migration si la table principale est manquante."""
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='messages'")
        if not cursor.fetchone():
            logger.info("Messages table not found, running migration script...")
            migration_script = "migrations/001_add_message_id_and_producer.sql"
            if path.exists(migration_script):
                with open(migration_script) as f:
                    conn.executescript(f.read())
                logger.info("Migration script executed successfully.")
            else:
                logger.error(f"Migration script not found: {migration_script}")


# noinspection PyShadowingNames
class Broker:
    """
    Le Broker sert d'interface : met en file d'attente les écritures et effectue les lectures.
    """

    def __init__(self, db_name: str, test_conn: Optional[sqlite3.Connection] = None) -> None:
        self.db_name = db_name
        self.test_conn = test_conn  # Pour les tests uniquement

    def register_subscription(self, sid: str, consumer: str, topic: str) -> None:
        if not all([sid, consumer, topic]):
            logger.warning("register_subscription: Missing required parameters")
            return

        sql = "INSERT OR REPLACE INTO subscriptions (sid, consumer, topic, connected_at) VALUES (?, ?, ?, ?)"
        params = (sid, consumer, topic, time.time())

        if self.test_conn:
            # Mode test : écriture synchrone
            try:
                self.test_conn.execute(sql, params)
                self.test_conn.commit()
            except sqlite3.Error as e:
                logger.error(f"Error in register_subscription: {e}")
        else:
            # Mode production : écriture asynchrone
            with db_write_queue_lock:
                db_write_queue.append((sql, params))

        socketio.emit("new_client", {"consumer": consumer, "topic": topic, "connected_at": time.time()})

    def unregister_client(self, sid: str, consumer: Optional[str] = None, topic: Optional[str] = None) -> None:
        """
        Désinscrit un client. Si consumer et topic ne sont pas fournis, ils sont récupérés via sid.

        Args:
            sid: ID de session du client
            consumer: Nom du consommateur (optionnel)
            topic: Nom du topic (optionnel)
        """
        if not sid:
            logger.warning("unregister_client: Missing sid")
            return

        # Si consumer et topic ne sont pas fournis, on les récupère
        if consumer is None or topic is None:
            client_info = self.get_client_by_sid(sid)
            if client_info:
                consumer, topic = client_info

        sql = "DELETE FROM subscriptions WHERE sid = ?"

        if self.test_conn:
            # Mode test : écriture synchrone
            try:
                self.test_conn.execute(sql, (sid,))
                self.test_conn.commit()
            except sqlite3.Error as e:
                logger.error(f"Error in unregister_client: {e}")
        else:
            # Mode production : écriture asynchrone
            with db_write_queue_lock:
                db_write_queue.append((sql, (sid,)))

        if consumer and topic:
            socketio.emit("client_disconnected", {"consumer": consumer, "topic": topic})

    def save_message(self, topic: str, message_id: str, message: Any, producer: str) -> None:
        if not all([topic, message_id, producer]):
            logger.warning("save_message: Missing required parameters")
            return

        timestamp = time.time()
        sql = "INSERT INTO messages (topic, message_id, message, producer, timestamp) VALUES (?, ?, ?, ?, ?)"
        message_json = json.dumps(message) if not isinstance(message, str) else message
        params = (topic, message_id, message_json, producer, timestamp)

        if self.test_conn:
            # Mode test : écriture synchrone
            try:
                self.test_conn.execute(sql, params)
                self.test_conn.commit()
            except sqlite3.Error as e:
                logger.error(f"Error in save_message: {e}")
        else:
            # Mode production : écriture asynchrone
            with db_write_queue_lock:
                db_write_queue.append((sql, params))

        socketio.emit("new_message", {"topic": topic, "message_id": message_id, "message": message, "producer": producer, "timestamp": timestamp})

    def save_consumption(self, consumer: str, topic: str, message_id: str, message: Any) -> None:
        if not all([consumer, topic, message_id]):
            logger.warning("save_consumption: Missing required parameters")
            return

        timestamp = time.time()
        sql = "INSERT INTO consumptions (consumer, topic, message_id, message, timestamp) VALUES (?, ?, ?, ?, ?)"
        message_json = json.dumps(message) if not isinstance(message, str) else message
        params = (consumer, topic, message_id, message_json, timestamp)

        if self.test_conn:
            # Mode test : écriture synchrone
            try:
                self.test_conn.execute(sql, params)
                self.test_conn.commit()
            except sqlite3.Error as e:
                logger.error(f"Error in save_consumption: {e}")
        else:
            # Mode production : écriture asynchrone
            with db_write_queue_lock:
                db_write_queue.append((sql, params))

        socketio.emit("new_consumption", {"consumer": consumer, "topic": topic, "message_id": message_id, "message": message, "timestamp": timestamp})

    def _get_read_connection(self) -> sqlite3.Connection:
        """Retourne une connexion en lecture seule, ou la connexion de test si disponible."""
        if self.test_conn:
            return self.test_conn

        # Si c'est déjà une URI file:, on la réutilise (pour mémoire partagée)
        if self.db_name.startswith("file:"):
            return sqlite3.connect(self.db_name, uri=True, timeout=5.0, check_same_thread=False)

        # Pour les fichiers sur disque, on ouvre en lecture seule
        db_uri = f"file:{self.db_name}?mode=ro"
        return sqlite3.connect(db_uri, uri=True, timeout=5.0)

    def get_client_by_sid(self, sid: str) -> Optional[Tuple[str, str]]:
        if not sid:
            return None

        try:
            if self.test_conn:
                cursor = self.test_conn.cursor()
                cursor.execute("SELECT consumer, topic FROM subscriptions WHERE sid = ?", (sid,))
                result = cursor.fetchone()
                return result if result else None
            else:
                with self._get_read_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT consumer, topic FROM subscriptions WHERE sid = ?", (sid,))
                    result = cursor.fetchone()
                    return result if result else None
        except sqlite3.Error as e:
            logger.error(f"Error fetching client by SID: {e}")
            return None

    def get_clients(self) -> List[Dict[str, Any]]:
        try:
            if self.test_conn:
                cursor = self.test_conn.cursor()
                cursor.execute("SELECT consumer, topic, connected_at FROM subscriptions ORDER BY connected_at DESC LIMIT 100")
                rows = cursor.fetchall()
                clients = [{"consumer": r[0], "topic": r[1], "connected_at": r[2]} for r in rows]
                logger.info(f"Retrieved {len(clients)} connected clients")
                return clients
            else:
                with self._get_read_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT consumer, topic, connected_at FROM subscriptions ORDER BY connected_at DESC LIMIT 100")
                    rows = cursor.fetchall()
                    clients = [{"consumer": r[0], "topic": r[1], "connected_at": r[2]} for r in rows]
                    logger.info(f"Retrieved {len(clients)} connected clients")
                    return clients
        except sqlite3.Error as e:
            logger.error(f"Error fetching clients: {e}")
            return []

    def get_messages(self) -> List[Dict[str, Any]]:
        try:
            if self.test_conn:
                cursor = self.test_conn.cursor()
                cursor.execute("SELECT topic, message_id, message, producer, timestamp FROM messages ORDER BY timestamp DESC LIMIT 100")
                rows = cursor.fetchall()
                messages = [{"topic": r[0], "message_id": r[1], "message": json.loads(r[2]) if r[2] else {}, "producer": r[3], "timestamp": r[4]} for r in rows]
                logger.info(f"Retrieved {len(messages)} messages")
                return messages
            else:
                with self._get_read_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT topic, message_id, message, producer, timestamp FROM messages ORDER BY timestamp DESC LIMIT 100")
                    rows = cursor.fetchall()
                    messages = [{"topic": r[0], "message_id": r[1], "message": json.loads(r[2]) if r[2] else {}, "producer": r[3], "timestamp": r[4]} for r in rows]
                    logger.info(f"Retrieved {len(messages)} messages")
                    return messages
        except sqlite3.Error as e:
            logger.error(f"Error fetching messages: {e}")
            return []
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding message JSON: {e}")
            return []

    def get_consumptions(self) -> List[Dict[str, Any]]:
        try:
            if self.test_conn:
                cursor = self.test_conn.cursor()
                cursor.execute("SELECT consumer, topic, message_id, message, timestamp FROM consumptions ORDER BY timestamp DESC LIMIT 100")
                rows = cursor.fetchall()
                consumptions = [{"consumer": r[0], "topic": r[1], "message_id": r[2], "message": json.loads(r[3]) if r[3] else {}, "timestamp": r[4]} for r in rows]
                logger.info(f"Retrieved {len(consumptions)} consumption events")
                return consumptions
            else:
                with self._get_read_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT consumer, topic, message_id, message, timestamp FROM consumptions ORDER BY timestamp DESC LIMIT 100")
                    rows = cursor.fetchall()
                    consumptions = [{"consumer": r[0], "topic": r[1], "message_id": r[2], "message": json.loads(r[3]) if r[3] else {}, "timestamp": r[4]} for r in rows]
                    logger.info(f"Retrieved {len(consumptions)} consumption events")
                    return consumptions
        except sqlite3.Error as e:
            logger.error(f"Error fetching consumptions: {e}")
            return []
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding consumption JSON: {e}")
            return []

    def get_graph_state(self) -> Dict[str, Any]:
        try:
            if self.test_conn:
                c = self.test_conn.cursor()
            else:
                conn = self._get_read_connection()
                c = conn.cursor()

            c.execute("SELECT DISTINCT producer FROM messages")
            producers = [row[0] for row in c.fetchall()]
            c.execute("SELECT DISTINCT consumer FROM subscriptions UNION SELECT DISTINCT consumer FROM consumptions")
            consumers = [row[0] for row in c.fetchall()]
            c.execute("SELECT DISTINCT topic FROM messages UNION SELECT DISTINCT topic FROM subscriptions")
            topics = [row[0] for row in c.fetchall()]
            c.execute("SELECT topic, consumer FROM subscriptions")
            subscriptions = [{"source": row[0], "target": row[1], "type": "consume"} for row in c.fetchall()]
            c.execute("SELECT DISTINCT producer, topic FROM messages")
            publications = [{"source": row[0], "target": row[1], "type": "publish"} for row in c.fetchall()]

            if not self.test_conn:
                # noinspection PyUnboundLocalVariable
                conn.close()

            return {"producers": producers, "consumers": consumers, "topics": topics, "links": subscriptions + publications}
        except sqlite3.Error as e:
            logger.error(f"Error fetching graph state: {e}")
            return {"producers": [], "consumers": [], "topics": [], "links": []}


# 3. Initialisation de Flask, SocketIO et du Broker
app = Flask(__name__)
app.config["SECRET_KEY"] = "secret!"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")
broker = Broker(DB_FILE_NAME)


# 4. Définition des routes Flask et des handlers SocketIO
@app.route("/publish", methods=["POST"])
def publish() -> Tuple[flask.Response, int]:
    data = request.json
    topic, msg_id, msg, prod = data.get("topic"), data.get("message_id"), data.get("message"), data.get("producer")
    if not all([topic, msg_id, msg, prod]):
        logger.error("Publish failed: Missing topic, message_id, message, or producer")
        return jsonify({"status": "error", "message": "Missing topic, message_id, message, or producer"}), 400

    logger.info(f"Publishing message {msg_id} to topic {topic} by {prod}")
    broker.save_message(topic=topic, message_id=msg_id, message=msg, producer=prod)
    socketio.emit("message", data, to=topic)
    return jsonify({"status": "ok"}), 200


@app.route("/clients")
def clients() -> flask.Response:
    logger.info("Fetching connected clients")
    return jsonify(broker.get_clients())


@app.route("/messages")
def messages() -> flask.Response:
    logger.info("Fetching published messages")
    return jsonify(broker.get_messages())


@app.route("/consumptions")
def consumptions() -> flask.Response:
    logger.info("Fetching consumption events")
    return jsonify(broker.get_consumptions())


@app.route("/graph/state")
def graph_state() -> flask.Response:
    logger.info("Fetching graph state")
    return jsonify(broker.get_graph_state())


@app.route("/health")
def health_check() -> Tuple[flask.Response, int]:
    """Health check endpoint to monitor system status."""
    if not db_ready_event.is_set():
        return jsonify({"status": "unhealthy", "reason": "Database not ready"}), 503
    try:
        broker.get_clients()  # Fait un simple test de lecture
        return jsonify({"status": "healthy", "timestamp": time.time()}), 200
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({"status": "unhealthy", "error": str(e)}), 503


@app.route("/")
def index() -> flask.Response:
    return redirect("/control-panel.html")


@app.route("/control-panel.html")
def serve_control_panel() -> flask.Response:
    logger.info("Serving control-panel.html")
    return send_from_directory(".", "control-panel.html")


@app.route("/static/<path:filename>")
def serve_static(filename: str) -> flask.Response:
    logger.info(f"Serving static file: {filename}")
    return send_from_directory("static", filename)


@app.route("/activity-map.html")
def serve_activity_map() -> flask.Response:
    logger.info("Serving activity-map.html")
    return send_from_directory(".", "activity-map.html")


@app.route("/network-graph.html")
def serve_network_graph() -> flask.Response:
    logger.info("Serving network-graph.html")
    return send_from_directory(".", "network-graph.html")


@app.route("/circular-graph.html")
def serve_circular_graph() -> flask.Response:
    logger.info("Serving circular-graph.html")
    return send_from_directory(".", "circular-graph.html")


@socketio.on("subscribe")
def handle_subscribe(data: Dict[str, Any]) -> None:
    try:
        # noinspection PyUnresolvedReferences
        sid = request.sid
        consumer, topics = data.get("consumer"), data.get("topics", [])
        if not all([sid, consumer, topics]):
            logger.warning(f"Invalid subscribe data: {data}")
            return

        logger.info(f"Subscribing {consumer} (SID: {sid}) to topics: {topics}")
        for topic in topics:
            if not isinstance(topic, str):
                logger.warning(f"Invalid topic type: {type(topic)}")
                continue

            join_room(topic)
            broker.register_subscription(sid, consumer, topic)
            emit("message", {"topic": topic, "message_id": f"subscribe_{topic}", "message": f"Subscribed to {topic}", "producer": "server"}, to=sid)
    except Exception as e:
        logger.error(f"Error in handle_subscribe: {e}")


@socketio.on("consumed")
def handle_consumed(data: Dict[str, Any]) -> None:
    try:
        consumer, topic, msg_id, msg = data.get("consumer"), data.get("topic"), data.get("message_id"), data.get("message")
        if not all([consumer, topic, msg_id]):
            logger.warning(f"Incomplete consumption data received: {data}")
            return

        # Convertir le message en str si c'est un dict ou autre type
        if isinstance(msg, dict):
            msg = str(msg)

        logger.info(f"Handling consumption by {consumer} for message {msg_id} in topic {topic}")
        broker.save_consumption(consumer, topic, msg_id, msg)
        socketio.emit("consumed", data)
    except Exception as e:
        logger.error(f"Error in handle_consumed: {e}")


@socketio.on("disconnect")
def handle_disconnect() -> None:
    try:
        # noinspection PyUnresolvedReferences
        sid = request.sid
        logger.info(f"Client disconnecting (SID: {sid})")
        broker.unregister_client(sid)
    except Exception as e:
        logger.error(f"Error in handle_disconnect: {e}")


# 5. Point d'entrée principal avec démarrage et arrêt propres
def main() -> None:
    """Démarre le worker BDD, attend sa confirmation, puis lance le serveur Flask."""
    stop_worker_event = threading.Event()

    logger.info(f"Starting DatabaseWorker for '{DB_FILE_NAME}'...")
    db_worker = DatabaseWorker(DB_FILE_NAME, stop_worker_event)
    db_worker.start()

    logger.info("Main thread waiting for database to be ready...")
    db_is_ready = db_ready_event.wait(timeout=10)
    if not db_is_ready:
        logger.error("Database worker failed to initialize in time. Exiting.")
        stop_worker_event.set()
        with db_write_queue_lock:
            db_write_queue.append(None)
        db_worker.join(timeout=5)
        return

    logger.info("Database is ready. Starting Flask-SocketIO server on port 5000.")
    try:
        socketio.run(app, host="0.0.0.0", port=5000, log_output=False, use_reloader=False)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received.")
    except Exception as e:
        logger.error(f"Server error: {e}")
    finally:
        logger.info("Shutting down...")
        stop_worker_event.set()
        with db_write_queue_lock:
            db_write_queue.append(None)
        db_worker.join(timeout=5)
        logger.info("Shutdown complete.")


if __name__ == "__main__":
    main()
