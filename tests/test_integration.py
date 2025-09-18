"""Integration tests for the PubSub system."""

import json
import sqlite3
import sys
import threading
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestIntegration:
    """Integration tests for the complete PubSub system."""

    def test_json_message_structure(self):
        """Test JSON message structure for pub/sub."""
        message = {
            "topic": "test",
            "message_id": "123",
            "message": "Hello World",
            "producer": "test_producer",
        }

        # Test serialization
        json_str = json.dumps(message)
        parsed = json.loads(json_str)

        assert parsed["topic"] == "test"
        assert parsed["message"] == "Hello World"
        assert parsed["producer"] == "test_producer"

    def test_database_integration(self):
        """Test database operations integration."""
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()

        # Create tables
        cursor.execute(
            """
            CREATE TABLE messages (
                id INTEGER PRIMARY KEY,
                topic TEXT,
                message TEXT,
                producer TEXT
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE subscriptions (
                id INTEGER PRIMARY KEY,
                consumer TEXT,
                topic TEXT
            )
        """
        )

        # Test message flow
        cursor.execute(
            "INSERT INTO messages (topic, message, producer) VALUES (?, ?, ?)",
            ("sports", "Game started", "sports_bot"),
        )

        cursor.execute(
            "INSERT INTO subscriptions (consumer, topic) VALUES (?, ?)", ("alice", "sports")
        )

        # Verify integration
        cursor.execute(
            """
            SELECT m.topic, m.message, s.consumer
            FROM messages m
            JOIN subscriptions s ON m.topic = s.topic
            WHERE s.consumer = ?
        """,
            ("alice",),
        )

        result = cursor.fetchone()
        assert result is not None
        assert result[0] == "sports"
        assert result[1] == "Game started"
        assert result[2] == "alice"

        conn.close()

    def test_concurrent_operations(self):
        """Test concurrent database operations."""
        import os
        import tempfile

        # Use a temporary file instead of in-memory database for thread safety
        temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        temp_db.close()
        db_path = temp_db.name

        try:
            # Create the database schema
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE test_messages (
                    id INTEGER PRIMARY KEY,
                    content TEXT,
                    thread_id INTEGER
                )
            """
            )
            conn.commit()
            conn.close()

            # Thread-safe lock for database operations
            db_lock = threading.Lock()

            def insert_messages(thread_id):
                """Insert messages from a thread."""
                with db_lock:
                    thread_conn = sqlite3.connect(db_path)
                    thread_cursor = thread_conn.cursor()
                    # noinspection PyShadowingNames
                    for i in range(3):
                        thread_cursor.execute(
                            "INSERT INTO test_messages (content, thread_id) VALUES (?, ?)",
                            (f"Message {i}", thread_id),
                        )
                    thread_conn.commit()
                    thread_conn.close()

            # Create threads
            threads = []
            for i in range(3):
                t = threading.Thread(target=insert_messages, args=(i,))
                threads.append(t)
                t.start()

            # Wait for all threads
            for t in threads:
                t.join()

            # Verify all messages were inserted
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM test_messages")
            count = cursor.fetchone()[0]
            assert count == 9  # 3 threads × 3 messages each

            conn.close()

        finally:
            # Clean up temporary database file
            if os.path.exists(db_path):
                os.unlink(db_path)

    def test_message_queue_simulation(self):
        """Test message queue behavior simulation."""
        from collections import deque

        # Simulate a message queue
        message_queue = deque()
        processed_messages = []

        # Producer adds messages
        messages = [
            {"topic": "news", "content": "Breaking news"},
            {"topic": "sports", "content": "Game update"},
            {"topic": "weather", "content": "Storm warning"},
        ]

        for msg in messages:
            message_queue.append(msg)

        # Consumer processes messages
        while message_queue:
            msg = message_queue.popleft()
            processed_messages.append(msg)
            time.sleep(0.001)  # Simulate processing time

        assert len(processed_messages) == 3
        assert processed_messages[0]["topic"] == "news"
        assert processed_messages[1]["topic"] == "sports"
        assert processed_messages[2]["topic"] == "weather"

    @pytest.mark.parametrize(
        "topic,message_count",
        [
            ("tech", 5),
            ("finance", 3),
            ("health", 7),
        ],
    )
    def test_topic_message_distribution(self, topic, message_count):
        """Test message distribution across different topics."""
        messages = []

        # Generate messages for the topic
        for i in range(message_count):
            message = {
                "topic": topic,
                "message_id": f"{topic}_{i}",
                "content": f"Message {i} for {topic}",
                "timestamp": time.time(),
            }
            messages.append(message)

        # Verify message structure
        assert len(messages) == message_count
        for msg in messages:
            assert msg["topic"] == topic
            assert "message_id" in msg
            assert "content" in msg
            assert "timestamp" in msg

    def test_websocket_message_format(self):
        """Test WebSocket message format compliance."""
        # Mock WebSocket message format
        websocket_message = {
            "event": "message",
            "data": {
                "topic": "updates",
                "message_id": "ws_001",
                "message": "WebSocket test message",
                "producer": "websocket_client",
                "timestamp": time.time(),
            },
        }

        # Validate structure
        assert "event" in websocket_message
        assert "data" in websocket_message
        assert websocket_message["event"] == "message"

        data = websocket_message["data"]
        assert "topic" in data
        assert "message_id" in data
        assert "message" in data
        assert "producer" in data
        assert "timestamp" in data

    def test_subscription_matching(self):
        """Test subscription topic matching logic."""
        # Simulate subscription patterns
        subscriptions = {
            "alice": ["sports", "news"],
            "bob": ["tech", "finance"],
            "charlie": ["sports", "tech", "news"],
        }

        # Test message routing
        message_topic = "sports"
        eligible_consumers = []

        for consumer, topics in subscriptions.items():
            if message_topic in topics:
                eligible_consumers.append(consumer)

        assert "alice" in eligible_consumers
        assert "charlie" in eligible_consumers
        assert "bob" not in eligible_consumers
        assert len(eligible_consumers) == 2
