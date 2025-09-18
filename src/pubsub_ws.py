# pubsub_ws.py

import json
import logging
import sqlite3
import time
from os import path
from typing import Any, Dict, List, Optional, Tuple

import flask
from flask import Flask, jsonify, request, send_from_directory
from flask_socketio import SocketIO, emit, join_room

# Configure logging for debugging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# --- START MODIFICATION FOR DB MANAGEMENT AND TESTS ---
def init_db(db_name: str, connection: Optional[sqlite3.Connection] = None) -> None:
    """Initialize the SQLite database and run migrations if necessary."""
    if connection:
        conn = connection
        close_conn = False  # Don't close connection if provided
    else:
        conn = sqlite3.connect(db_name)
        close_conn = True  # Close connection if created here

    try:
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='messages'")
        if not c.fetchone():
            logger.info(
                f"[INIT DB] Messages table missing in {db_name}, running migration script...")
            migration_script = "migrations/001_add_message_id_and_producer.sql"
            if path.exists(migration_script):
                with open(migration_script) as f:
                    conn.executescript(f.read())
                    logger.info(f"[INIT DB] Migration script executed successfully for {db_name}.")
            else:
                logger.error(f"[INIT DB] Migration script not found: {migration_script}")
    finally:
        if close_conn and conn:  # Close connection only if it was opened here
            conn.close()


# Default DB file name
DB_FILE_NAME = "pubsub.db"
# --- END MODIFICATION FOR DB MANAGEMENT AND TESTS ---


app = Flask(__name__)
app.config["SECRET_KEY"] = "secret!"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

# Initialize the real database when starting the application
if __name__ == "__main__":
    init_db(DB_FILE_NAME)


class Broker:
    # The broker can receive an existing connection for tests
    def __init__(self, db_name: str, test_conn: Optional[sqlite3.Connection] = None):
        """
        Initialize the Broker with a database name.

        :param db_name: Name of the SQLite database file (or ':memory:')
        :param test_conn: An optional existing SQLite connection for testing purposes.
        """
        self.db_name = db_name
        self._test_conn = test_conn  # Store test connection

    def _get_db_connection(self) -> sqlite3.Connection:
        """Helper to get a database connection. Uses test_conn if available."""
        if self._test_conn:
            return self._test_conn  # Return test connection
        return sqlite3.connect(self.db_name)

    def _close_db_connection(self, conn: sqlite3.Connection) -> None:
        """Helper to close a database connection, if it's not a test connection."""
        if conn != self._test_conn:  # Don't close test connection
            conn.close()

    def register_subscription(self, sid: str, consumer: str, topic: str) -> None:
        conn = None
        try:
            conn = self._get_db_connection()
            c = conn.cursor()
            c.execute(
                """
                INSERT OR REPLACE INTO subscriptions (sid, consumer, topic, connected_at)
                VALUES (?, ?, ?, ?)
            """,
                (sid, consumer, topic, time.time()),
            )
            conn.commit()
            logger.info(f"Registered subscription: {consumer} to {topic} (SID: {sid})")

            socketio.emit(
                "new_client",
                {"consumer": consumer, "topic": topic, "connected_at": time.time()},
                # Add timestamp for the UI
            )
        except sqlite3.Error as e:
            logger.error(f"Database error during subscription registration: {e}")
            if conn:
                conn.rollback()  # Rollback on error
        finally:
            if conn:
                self._close_db_connection(conn)  # Use the new close method

    def unregister_client(self, sid: str) -> None:
        conn = None
        try:
            conn = self._get_db_connection()
            c = conn.cursor()
            c.execute("SELECT consumer, topic FROM subscriptions WHERE sid = ?", (sid,))
            client_data = c.fetchall()
            c.execute("DELETE FROM subscriptions WHERE sid = ?", (sid,))
            conn.commit()
            for consumer, topic in client_data:
                logger.info(f"Unregistered client: {consumer} from {topic} (SID: {sid})")
                socketio.emit("client_disconnected", {"consumer": consumer, "topic": topic})
        except sqlite3.Error as e:
            logger.error(f"Database error during client unregistration: {e}")
            if conn:
                conn.rollback()
        finally:
            if conn:
                self._close_db_connection(conn)

    def save_message(self, topic: str, message_id: str, message: Any, producer: str) -> None:
        conn = None
        timestamp = time.time()
        try:
            conn = self._get_db_connection()
            c = conn.cursor()
            c.execute(
                """
                INSERT INTO messages (topic, message_id, message, producer, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """,
                (topic, message_id, json.dumps(message), producer, timestamp),
            )
            conn.commit()
            logger.info(f"Saved message: {message_id} to topic {topic} by {producer}")

            socketio.emit(
                "new_message",
                {
                    "topic": topic,
                    "message_id": message_id,
                    "message": message,
                    "producer": producer,
                    "timestamp": timestamp,
                },
            )
        except sqlite3.Error as e:
            logger.error(f"Database error during message save: {e}")
            if conn:
                conn.rollback()
        finally:
            if conn:
                self._close_db_connection(conn)

    def save_consumption(self, consumer: str, topic: str, message_id: str, message: Any) -> None:
        conn = None
        timestamp = time.time()
        try:
            conn = self._get_db_connection()
            c = conn.cursor()
            c.execute(
                """
                INSERT INTO consumptions (consumer, topic, message_id, message, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """,
                (consumer, topic, message_id, json.dumps(message), timestamp),
            )
            conn.commit()
            logger.info(f"Saved consumption: {consumer} consumed {message_id} from {topic}")

            socketio.emit(
                "new_consumption",
                {
                    "consumer": consumer,
                    "topic": topic,
                    "message_id": message_id,
                    "message": message,
                    "timestamp": timestamp,
                },
            )
        except sqlite3.Error as e:
            logger.error(f"Database error during consumption save: {e}")
            if conn:
                conn.rollback()
        finally:
            if conn:
                self._close_db_connection(conn)

    # noinspection PyShadowingNames
    def get_clients(self) -> List[Dict[str, Any]]:
        conn = None
        try:
            conn = self._get_db_connection()
            c = conn.cursor()
            c.execute(
                """
                SELECT consumer, topic, connected_at FROM subscriptions
            """
            )
            rows = c.fetchall()
            clients = [{"consumer": r[0], "topic": r[1], "connected_at": r[2]} for r in rows]
            logger.info(f"Retrieved {len(clients)} connected clients")
            return clients
        except sqlite3.Error as e:
            logger.error(f"Database error retrieving clients: {e}")
            return []
        finally:
            if conn:
                self._close_db_connection(conn)

    # noinspection PyShadowingNames
    def get_messages(self) -> List[Dict[str, Any]]:
        conn = None
        try:
            conn = self._get_db_connection()
            c = conn.cursor()
            c.execute(
                """
                SELECT topic, message_id, message, producer, timestamp FROM messages
                WHERE message_id IS NOT NULL
                ORDER BY timestamp DESC
            """
            )
            rows = c.fetchall()
            messages = [
                {"topic": r[0], "message_id": r[1], "message": json.loads(r[2]), "producer": r[3],
                 "timestamp": r[4]}
                for r in rows
            ]
            logger.info(f"Retrieved {len(messages)} messages")
            return messages
        except sqlite3.Error as e:
            logger.error(f"Database error retrieving messages: {e}")
            return []
        finally:
            if conn:
                self._close_db_connection(conn)

    # noinspection PyShadowingNames
    def get_consumptions(self) -> List[Dict[str, Any]]:
        conn = None
        try:
            conn = self._get_db_connection()
            c = conn.cursor()
            c.execute(
                """
                SELECT consumer, topic, message_id, message, timestamp FROM consumptions
                WHERE message_id IS NOT NULL
                ORDER BY timestamp DESC
            """
            )
            rows = c.fetchall()
            consumptions = [
                {"consumer": r[0], "topic": r[1], "message_id": r[2], "message": json.loads(r[3]),
                 "timestamp": r[4]}
                for r in rows
            ]
            logger.info(f"Retrieved {len(consumptions)} consumption events")
            return consumptions
        except sqlite3.Error as e:
            logger.error(f"Database error retrieving consumptions: {e}")
            return []
        finally:
            if conn:
                self._close_db_connection(conn)


# Create the Broker instance with the real database filename
# This line is executed only if __name__ == "__main__"
# For tests, the Broker is instantiated via the fixture
broker = Broker(DB_FILE_NAME)


@app.route("/publish", methods=["POST"])
def publish() -> Tuple[Dict[str, str], int]:
    data = request.json
    topic = data.get("topic")
    message_id = data.get("message_id")
    message = data.get("message")
    producer = data.get("producer")

    if not all([topic, message_id, message, producer]):
        logger.error("Publish failed: Missing topic, message_id, message, or producer")
        return jsonify(
            {"status": "error", "message": "Missing topic, message_id, message, or producer"}), 400

    logger.info(f"Publishing message {message_id} to topic {topic} by {producer}")
    # The real broker will be used here, not the mock
    broker.save_message(topic=topic, message_id=message_id, message=message, producer=producer)

    payload = {"topic": topic, "message_id": message_id, "message": message, "producer": producer}

    socketio.emit("message", payload, to=topic)

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


@app.route("/client.html")
def serve_client() -> flask.Response:
    logger.info("Serving client.html")
    return send_from_directory(".", "client.html")


@app.route("/static/<path:filename>")
def serve_static(filename: str) -> flask.Response:
    logger.info(f"Serving static file: {filename}")
    return send_from_directory("static", filename)


@socketio.on("subscribe")
def handle_subscribe(data: Dict[str, Any]) -> None:
    consumer = data.get("consumer")
    topics = data.get("topics", [])

    # noinspection PyUnresolvedReferences
    sid = request.sid  # request.sid is dynamically added by Flask-SocketIO

    if sid is None:
        logger.error("No session ID available for subscription")
        return

    logger.info(f"Subscribing {consumer} to topics {topics} (SID: {sid})")
    for topic in topics:
        join_room(topic)
        broker.register_subscription(str(sid), str(consumer), topic)
        emit(
            "message",
            {
                "topic": topic,
                "message_id": f"sub_conf_{int(time.time())}",
                "message": f"Subscribed to {topic}",
                "producer": "server",
            },
            to=sid,
        )


@socketio.on("consumed")
def handle_consumed(data: Dict[str, Any]) -> None:
    consumer = data.get("consumer")
    topic = data.get("topic")
    message_id = data.get("message_id")
    message = data.get("message")

    if not all([consumer, topic, message_id, message]):
        logger.warning(f"Incomplete consumption data received: {data}")
        return

    logger.info(f"Handling consumption by {consumer} for message {message_id} in topic {topic}")
    broker.save_consumption(str(consumer), str(topic), str(message_id), str(message))


@socketio.on("disconnect")
def handle_disconnect() -> None:  # <-- Signature without explicit argument for the SID
    """Handle client disconnection."""
    # noinspection PyUnresolvedReferences
    sid = request.sid  # Always get SID via request.sid
    logger.info(f"Client disconnected (SID: {sid})")
    broker.unregister_client(sid)


def main() -> None:
    """Entry point for the pubsub server."""
    logger.info("Starting Flask-SocketIO server on port 5000")
    socketio.run(app, host="0.0.0.0", port=5000)  # nosec B104


if __name__ == "__main__":
    main()
