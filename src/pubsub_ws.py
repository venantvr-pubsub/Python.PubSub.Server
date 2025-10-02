import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple

import flask
from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, request, send_from_directory
from flask_socketio import SocketIO, join_room
from python_sqlite_async import AsyncSQLite

# Import de votre nouvelle librairie

# 1. Configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(threadName)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()
DB_FILE_NAME = os.getenv("DATABASE_FILE", "pubsub.db")

# 2. Initialisation de la base de données via la librairie
db = AsyncSQLite(DB_FILE_NAME)


# 3. Le Broker simplifié
# noinspection PyShadowingNames
class Broker:
    """
    Sert d'interface entre la logique de l'application et la librairie
    de base de données asynchrone.
    """

    def __init__(self, db_manager: AsyncSQLite) -> None:
        self.db = db_manager

    def register_subscription(self, sid: str, consumer: str, topic: str) -> None:
        if not all([sid, consumer, topic]):
            logger.warning("register_subscription: Paramètres requis manquants")
            return

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
        sql = "INSERT INTO messages (topic, message_id, message, producer, timestamp) VALUES (?, ?, ?, ?, ?)"
        message_json = json.dumps(message) if not isinstance(message, str) else message
        params = (topic, message_id, message_json, producer, time.time())
        self.db.execute_write(sql, params)
        socketio.emit("new_message", {"topic": topic, "message_id": message_id, "message": message, "producer": producer, "timestamp": time.time()})

    def save_consumption(self, consumer: str, topic: str, message_id: str, message: Any) -> None:
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


# 4. Initialisation de Flask, SocketIO et du Broker
app = Flask(__name__)
app.config["SECRET_KEY"] = "secret!"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")
broker = Broker(db)


# 5. Routes Flask et Handlers SocketIO
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


@app.route("/network-graph.html")
def serve_network_graph() -> flask.Response:
    return send_from_directory(".", "network-graph.html")


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
def main() -> None:
    """Démarre le worker BDD, gère l'init du schéma, puis lance le serveur Flask."""

    # La préparation du chemin du script ne change pas
    migration_script = os.path.join(os.path.dirname(__file__), '..', 'migrations', '001_add_message_id_and_producer.sql')
    migration_script = os.path.normpath(migration_script)

    # NOUVEAU : Démarrage simple du worker
    # La méthode start() ne fait plus que lancer le thread.
    db.start()

    logger.info("Main thread waiting for database to be ready...")
    if not db.wait_for_ready(timeout=10):
        logger.error("Database worker failed to initialize in time. Exiting.")
        db.stop()
        return

    # NOUVEAU : Logique de migration explicite
    try:
        logger.info("Checking for 'messages' table to decide on migration...")
        # On vérifie manuellement si la table existe
        res = db.execute_read("SELECT name FROM sqlite_master WHERE type='table' AND name=?", ("messages",))

        if not res:
            logger.info("Table 'messages' not found, running migration script...")
            # Si elle n'existe pas, on exécute le script
            db.execute_script(migration_script)

            # NOUVEAU et ESSENTIEL : On attend la fin de la migration
            # db.sync() bloque jusqu'à ce que toutes les commandes en file (y compris notre script) soient terminées.
            if not db.sync(timeout=15):
                raise RuntimeError("Migration script failed to complete in time.")
            logger.info("Migration finished successfully.")
        else:
            logger.info("Table 'messages' already exists, skipping migration.")

    except Exception as e:
        logger.error(f"An error occurred during migration check: {e}", exc_info=True)
        db.stop()
        return

    logger.info("Database is ready. Starting Flask-SocketIO server on port 5000.")
    try:
        socketio.run(app, host="0.0.0.0", port=5000, log_output=False, use_reloader=False)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received.")
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
    finally:
        logger.info("Shutting down...")
        db.stop()
        logger.info("Shutdown complete.")

if __name__ == "__main__":
    main()
