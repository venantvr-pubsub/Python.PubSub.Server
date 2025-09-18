"""Unit tests for message handling in the PubSub system."""

import sqlite3

import pytest


class TestMessageHandling:
    """Test message storage, retrieval, and consumption tracking."""

    @pytest.fixture
    def in_memory_db(self):
        """Create an in-memory database with proper schema."""
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()

        # Create tables
        cursor.execute(
            """
            CREATE TABLE messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT NOT NULL,
                message TEXT NOT NULL,
                producer TEXT NOT NULL,
                timestamp REAL DEFAULT (julianday('now'))
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                consumer TEXT NOT NULL,
                topic TEXT NOT NULL,
                timestamp REAL DEFAULT (julianday('now')),
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
                consumed_at REAL DEFAULT (julianday('now')),
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
            "INSERT INTO messages (topic, message, producer) VALUES (?, ?, ?)",
            ("test_topic", "test_message", "test_producer"),
        )
        in_memory_db.commit()

        # Retrieve the message
        cursor.execute(
            "SELECT topic, message, producer FROM messages WHERE topic = ?", ("test_topic",)
        )
        result = cursor.fetchone()

        assert result is not None
        assert result[0] == "test_topic"
        assert result[1] == "test_message"
        assert result[2] == "test_producer"

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
        cursor.execute(
            "INSERT INTO messages (topic, message, producer) VALUES (?, ?, ?)",
            ("test", "message1", "producer1"),
        )
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

    def test_message_ordering(self, in_memory_db):
        """Test that messages are retrieved in correct order."""
        cursor = in_memory_db.cursor()

        # Store messages with specific order
        messages = [
            ("order_test", "First", "producer1"),
            ("order_test", "Second", "producer2"),
            ("order_test", "Third", "producer3"),
        ]

        message_ids = []
        for topic, message, producer in messages:
            cursor.execute(
                "INSERT INTO messages (topic, message, producer) VALUES (?, ?, ?)",
                (topic, message, producer),
            )
            message_ids.append(cursor.lastrowid)

        in_memory_db.commit()

        # Retrieve messages
        cursor.execute(
            "SELECT id, message FROM messages WHERE topic = ? ORDER BY id", ("order_test",)
        )
        results = cursor.fetchall()

        assert len(results) == 3
        assert results[0][0] == message_ids[0]
        assert results[0][1] == "First"
        assert results[1][0] == message_ids[1]
        assert results[1][1] == "Second"
        assert results[2][0] == message_ids[2]
        assert results[2][1] == "Third"

    def test_multiple_consumers_same_message(self, in_memory_db):
        """Test multiple consumers consuming the same message."""
        cursor = in_memory_db.cursor()

        # Store a message
        cursor.execute(
            "INSERT INTO messages (topic, message, producer) VALUES (?, ?, ?)",
            ("shared_topic", "shared_message", "shared_producer"),
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

        # Check all consumptions were recorded
        cursor.execute(
            "SELECT COUNT(DISTINCT consumer) FROM consumptions WHERE message_id = ?", (message_id,)
        )
        count = cursor.fetchone()[0]
        assert count == 3

    def test_topic_filtering(self, in_memory_db):
        """Test filtering messages by topic."""
        cursor = in_memory_db.cursor()

        # Store messages in different topics
        topics_messages = [
            ("sports", "Goal scored!", "sports_bot"),
            ("news", "Breaking news", "news_bot"),
            ("sports", "Match ended", "sports_bot"),
            ("tech", "New release", "tech_bot"),
            ("sports", "Player transferred", "sports_bot"),
        ]

        for topic, message, producer in topics_messages:
            cursor.execute(
                "INSERT INTO messages (topic, message, producer) VALUES (?, ?, ?)",
                (topic, message, producer),
            )
        in_memory_db.commit()

        # Get only sports messages
        cursor.execute("SELECT message FROM messages WHERE topic = ?", ("sports",))
        sports_messages = [row[0] for row in cursor.fetchall()]

        assert len(sports_messages) == 3
        assert "Goal scored!" in sports_messages
        assert "Match ended" in sports_messages
        assert "Player transferred" in sports_messages

    def test_consumer_subscription_patterns(self, in_memory_db):
        """Test different consumer subscription patterns."""
        cursor = in_memory_db.cursor()

        # Create subscription patterns
        subscriptions = [
            ("alice", "sports"),
            ("alice", "news"),
            ("bob", "tech"),
            ("charlie", "sports"),
            ("charlie", "tech"),
            ("charlie", "news"),
        ]

        for consumer, topic in subscriptions:
            cursor.execute(
                "INSERT OR IGNORE INTO subscriptions (consumer, topic) VALUES (?, ?)",
                (consumer, topic),
            )
        in_memory_db.commit()

        # Test subscription queries
        cursor.execute("SELECT topic FROM subscriptions WHERE consumer = ?", ("alice",))
        alice_topics = [row[0] for row in cursor.fetchall()]

        cursor.execute("SELECT topic FROM subscriptions WHERE consumer = ?", ("charlie",))
        charlie_topics = [row[0] for row in cursor.fetchall()]

        assert len(alice_topics) == 2
        assert "sports" in alice_topics
        assert "news" in alice_topics

        assert len(charlie_topics) == 3
        assert "sports" in charlie_topics
        assert "tech" in charlie_topics
        assert "news" in charlie_topics

    @pytest.mark.parametrize(
        "topic,message",
        [
            ("sports", "Game started"),
            ("news", "Breaking news"),
            ("tech", "New release"),
            ("finance", "Market update"),
        ],
    )
    def test_message_creation_patterns(self, in_memory_db, topic, message):
        """Test message creation for different patterns."""
        cursor = in_memory_db.cursor()

        cursor.execute(
            "INSERT INTO messages (topic, message, producer) VALUES (?, ?, ?)",
            (topic, message, f"{topic}_producer"),
        )
        in_memory_db.commit()

        # Retrieve and verify
        cursor.execute("SELECT topic, message, producer FROM messages WHERE topic = ?", (topic,))
        result = cursor.fetchone()

        assert result[0] == topic
        assert result[1] == message
        assert result[2] == f"{topic}_producer"

    def test_message_statistics(self, in_memory_db):
        """Test message statistics and counts."""
        cursor = in_memory_db.cursor()

        # Create messages across multiple topics
        test_data = [("sports", 5), ("news", 3), ("tech", 7), ("finance", 2)]

        for topic, count in test_data:
            for i in range(count):
                cursor.execute(
                    "INSERT INTO messages (topic, message, producer) VALUES (?, ?, ?)",
                    (topic, f"Message {i}", f"{topic}_bot"),
                )
        in_memory_db.commit()

        # Test statistics
        cursor.execute("SELECT COUNT(*) FROM messages")
        total_messages = cursor.fetchone()[0]
        assert total_messages == sum(count for _, count in test_data)

        # Test per-topic statistics
        cursor.execute("SELECT topic, COUNT(*) FROM messages GROUP BY topic ORDER BY topic")
        topic_counts = cursor.fetchall()

        expected = dict(test_data)
        for topic, count in topic_counts:
            assert expected[topic] == count
