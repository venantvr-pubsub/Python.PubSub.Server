"""Test the pubsub modules independently."""

import sqlite3
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestBroker:
    """Test the Broker class without Flask/SocketIO dependencies."""

    @pytest.fixture
    def in_memory_db(self):
        """Create an in-memory database."""
        conn = sqlite3.connect(":memory:")
        # Initialize the database schema
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT NOT NULL,
                message TEXT NOT NULL,
                timestamp REAL DEFAULT (CURRENT_TIMESTAMP)
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                consumer TEXT NOT NULL,
                topic TEXT NOT NULL,
                timestamp REAL DEFAULT (CURRENT_TIMESTAMP),
                UNIQUE(consumer, topic)
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE consumptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                consumer TEXT NOT NULL,
                message_id INTEGER NOT NULL,
                consumed_at REAL DEFAULT (CURRENT_TIMESTAMP),
                FOREIGN KEY (message_id) REFERENCES messages (id),
                UNIQUE(consumer, message_id)
            )
        """
        )

        conn.commit()
        yield conn
        conn.close()

    def test_message_storage(self, in_memory_db):
        """Test storing messages in the database."""
        cursor = in_memory_db.cursor()

        # Store a message
        cursor.execute(
            "INSERT INTO messages (topic, message) VALUES (?, ?)", ("test_topic", "test_message")
        )
        in_memory_db.commit()

        # Retrieve the message
        cursor.execute("SELECT topic, message FROM messages WHERE topic = ?", ("test_topic",))
        result = cursor.fetchone()

        assert result is not None
        assert result[0] == "test_topic"
        assert result[1] == "test_message"

    def test_subscription_management(self, in_memory_db):
        """Test subscription management."""
        cursor = in_memory_db.cursor()

        # Add subscription
        cursor.execute(
            "INSERT OR IGNORE INTO subscriptions (consumer, topic) VALUES (?, ?)",
            ("alice", "sports"),
        )
        cursor.execute(
            "INSERT OR IGNORE INTO subscriptions (consumer, topic) VALUES (?, ?)", ("alice", "news")
        )
        in_memory_db.commit()

        # Check subscriptions
        cursor.execute("SELECT topic FROM subscriptions WHERE consumer = ?", ("alice",))
        topics = [row[0] for row in cursor.fetchall()]

        assert "sports" in topics
        assert "news" in topics
        assert len(topics) == 2

    def test_consumption_tracking(self, in_memory_db):
        """Test consumption tracking."""
        cursor = in_memory_db.cursor()

        # Store a message
        cursor.execute("INSERT INTO messages (topic, message) VALUES (?, ?)", ("test", "message1"))
        message_id = cursor.lastrowid
        in_memory_db.commit()

        # Record consumption
        cursor.execute(
            "INSERT OR IGNORE INTO consumptions (consumer, message_id) VALUES (?, ?)",
            ("bob", message_id),
        )
        in_memory_db.commit()

        # Verify consumption
        cursor.execute(
            "SELECT * FROM consumptions WHERE consumer = ? AND message_id = ?", ("bob", message_id)
        )
        result = cursor.fetchone()

        assert result is not None
        assert result[1] == "bob"
        assert result[2] == message_id

    def test_multiple_consumers_same_message(self, in_memory_db):
        """Test multiple consumers consuming the same message."""
        cursor = in_memory_db.cursor()

        # Store a message
        cursor.execute(
            "INSERT INTO messages (topic, message) VALUES (?, ?)", ("shared", "shared_message")
        )
        message_id = cursor.lastrowid
        in_memory_db.commit()

        # Multiple consumers consume it
        consumers = ["alice", "bob", "charlie"]
        for consumer in consumers:
            cursor.execute(
                "INSERT OR IGNORE INTO consumptions (consumer, message_id) VALUES (?, ?)",
                (consumer, message_id),
            )
        in_memory_db.commit()

        # Verify all consumptions
        cursor.execute(
            "SELECT COUNT(DISTINCT consumer) FROM consumptions WHERE message_id = ?", (message_id,)
        )
        count = cursor.fetchone()[0]
        assert count == 3

    @pytest.mark.parametrize(
        "topic,message",
        [
            ("sports", "Game started"),
            ("news", "Breaking news"),
            ("tech", "New release"),
            ("weather", "Sunny day"),
        ],
    )
    def test_various_topics(self, in_memory_db, topic, message):
        """Test storing messages for various topics."""
        cursor = in_memory_db.cursor()

        cursor.execute("INSERT INTO messages (topic, message) VALUES (?, ?)", (topic, message))
        in_memory_db.commit()

        # Retrieve and verify
        cursor.execute("SELECT topic, message FROM messages WHERE topic = ?", (topic,))
        result = cursor.fetchone()

        assert result[0] == topic
        assert result[1] == message


class TestPubSubMessage:
    """Test PubSubMessage class functionality."""

    def test_message_creation(self):
        """Test creating a message object."""
        # Import here to avoid SocketIO initialization issues
        with patch.dict("sys.modules", {"pubsub_ws": MagicMock()}):
            from pubsub.pubsub_message import PubSubMessage

            msg = PubSubMessage(
                topic="test_topic",
                message_id="12345",
                message="test_content",
                producer="test_producer",
            )

            assert msg.topic == "test_topic"
            assert msg.message == "test_content"
            assert msg.producer == "test_producer"
            assert msg.message_id == "12345"

    def test_message_serialization(self):
        """Test message serialization to dict."""
        with patch.dict("sys.modules", {"pubsub_ws": MagicMock()}):
            from pubsub.pubsub_message import PubSubMessage

            msg = PubSubMessage(
                topic="sports",
                message_id="msg123",
                message="Goal scored!",
                producer="sports_reporter",
            )

            msg_dict = msg.to_dict()

            assert msg_dict["topic"] == "sports"
            assert msg_dict["message"] == "Goal scored!"
            assert msg_dict["producer"] == "sports_reporter"
            assert msg_dict["message_id"] == "msg123"


class TestPubSubClient:
    """Test PubSubClient functionality."""

    @pytest.fixture
    def mock_websocket(self):
        """Mock websocket connection."""
        return MagicMock()

    def test_client_creation(self, mock_websocket):
        """Test creating a PubSubClient."""
        with patch("socketio.Client"):
            from pubsub.pubsub_client import PubSubClient

            client = PubSubClient(
                url="http://localhost:5000", consumer="test_consumer", topics=["test_topic"]
            )

            assert client.url == "http://localhost:5000"
            assert client.consumer == "test_consumer"
            assert client.topics == ["test_topic"]

    def test_subscription_management(self, mock_websocket):
        """Test subscription management."""
        with patch("socketio.Client"):
            from pubsub.pubsub_client import PubSubClient

            topics = ["sports", "news", "tech"]
            client = PubSubClient(
                url="http://localhost:5000", consumer="test_consumer", topics=topics
            )

            # Check initial topics
            assert len(client.topics) == 3
            assert "sports" in client.topics
            assert "news" in client.topics
            assert "tech" in client.topics


class TestDatabaseOperations:
    """Test database operations in isolation."""

    def test_database_schema(self):
        """Test that the database schema is correct."""
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()

        # Create tables
        cursor.execute(
            """
            CREATE TABLE messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT NOT NULL,
                message TEXT NOT NULL,
                timestamp REAL DEFAULT (CURRENT_TIMESTAMP)
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                consumer TEXT NOT NULL,
                topic TEXT NOT NULL,
                timestamp REAL DEFAULT (CURRENT_TIMESTAMP),
                UNIQUE(consumer, topic)
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE consumptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                consumer TEXT NOT NULL,
                message_id INTEGER NOT NULL,
                consumed_at REAL DEFAULT (CURRENT_TIMESTAMP),
                FOREIGN KEY (message_id) REFERENCES messages (id),
                UNIQUE(consumer, message_id)
            )
        """
        )

        # Test schema by inserting data
        cursor.execute("INSERT INTO messages (topic, message) VALUES ('test', 'msg')")
        cursor.execute("INSERT INTO subscriptions (consumer, topic) VALUES ('alice', 'test')")
        message_id = 1
        cursor.execute(
            "INSERT INTO consumptions (consumer, message_id) VALUES ('alice', ?)", (message_id,)
        )

        conn.commit()

        # Verify data
        cursor.execute("SELECT COUNT(*) FROM messages")
        assert cursor.fetchone()[0] == 1

        cursor.execute("SELECT COUNT(*) FROM subscriptions")
        assert cursor.fetchone()[0] == 1

        cursor.execute("SELECT COUNT(*) FROM consumptions")
        assert cursor.fetchone()[0] == 1

        conn.close()

    def test_foreign_key_constraint(self):
        """Test foreign key constraints work."""
        conn = sqlite3.connect(":memory:")
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()

        # Create tables with foreign key
        cursor.execute(
            """
            CREATE TABLE messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT NOT NULL,
                message TEXT NOT NULL,
                timestamp REAL DEFAULT (CURRENT_TIMESTAMP)
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE consumptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                consumer TEXT NOT NULL,
                message_id INTEGER NOT NULL,
                consumed_at REAL DEFAULT (CURRENT_TIMESTAMP),
                FOREIGN KEY (message_id) REFERENCES messages (id)
            )
        """
        )

        # Insert valid message
        cursor.execute("INSERT INTO messages (topic, message) VALUES ('test', 'msg')")
        message_id = cursor.lastrowid
        conn.commit()

        # Valid foreign key reference should work
        cursor.execute(
            "INSERT INTO consumptions (consumer, message_id) VALUES ('alice', ?)", (message_id,)
        )
        conn.commit()

        # Invalid foreign key reference should fail
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("INSERT INTO consumptions (consumer, message_id) VALUES ('bob', 999)")
            conn.commit()

        conn.close()
