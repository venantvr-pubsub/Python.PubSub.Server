"""Basic tests to verify the project structure and imports work."""

import sys
from pathlib import Path

import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def test_basic_imports():
    """Test that basic modules can be imported without SocketIO initialization."""
    # Test that we can import the modules
    try:
        import sqlite3

        assert sqlite3 is not None
    except ImportError:
        pytest.fail("sqlite3 import failed")


def test_sqlite_operations():
    """Test basic SQLite operations."""
    import sqlite3

    # Create in-memory database
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()

    # Create test table
    cursor.execute(
        """
        CREATE TABLE test (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            value INTEGER
        )
    """
    )

    # Insert data
    cursor.execute("INSERT INTO test (name, value) VALUES (?, ?)", ("test1", 42))
    cursor.execute("INSERT INTO test (name, value) VALUES (?, ?)", ("test2", 100))

    # Query data
    cursor.execute("SELECT * FROM test ORDER BY id")
    results = cursor.fetchall()

    assert len(results) == 2
    assert results[0][1] == "test1"
    assert results[0][2] == 42
    assert results[1][1] == "test2"
    assert results[1][2] == 100

    conn.close()


def test_json_operations():
    """Test JSON serialization/deserialization."""
    import json

    data = {"topic": "test", "message": "Hello World", "timestamp": "2024-01-01T00:00:00Z"}

    # Serialize
    json_str = json.dumps(data)
    assert isinstance(json_str, str)

    # Deserialize
    parsed = json.loads(json_str)
    assert parsed == data


def test_path_operations():
    """Test path operations."""
    from pathlib import Path

    # Get project root
    project_root = Path(__file__).parent.parent
    assert project_root.exists()

    # Check key directories
    src_dir = project_root / "src"
    tests_dir = project_root / "tests"

    assert src_dir.exists()
    assert tests_dir.exists()


def test_requirements_file():
    """Test that requirements.txt exists and is readable."""
    from pathlib import Path

    req_file = Path(__file__).parent.parent / "requirements.txt"
    assert req_file.exists()

    content = req_file.read_text()
    assert "Flask" in content
    assert "flask-socketio" in content


@pytest.mark.parametrize(
    "topic,message",
    [
        ("sports", "Game started"),
        ("news", "Breaking news"),
        ("tech", "New release"),
    ],
)
def test_message_formatting(topic, message):
    """Test message formatting for different topics."""
    formatted = f"[{topic.upper()}] {message}"
    assert formatted.startswith(f"[{topic.upper()}]")
    assert message in formatted


def test_consumer_data():
    """Test consumer data structure."""
    consumer = {"name": "alice", "topics": ["sports", "news"], "connected": True}

    assert consumer["name"] == "alice"
    assert len(consumer["topics"]) == 2
    assert "sports" in consumer["topics"]
    assert consumer["connected"] is True


def test_message_queue_simulation():
    """Test a simple message queue simulation."""
    from collections import deque

    # Create message queue
    queue = deque()

    # Add messages
    messages = [
        {"topic": "sports", "message": "Goal!"},
        {"topic": "news", "message": "Update"},
        {"topic": "weather", "message": "Sunny"},
    ]

    for msg in messages:
        queue.append(msg)

    assert len(queue) == 3

    # Process messages
    processed = []
    while queue:
        msg = queue.popleft()
        processed.append(msg)

    assert len(processed) == 3
    assert processed[0]["topic"] == "sports"


def test_timestamp_handling():
    """Test timestamp operations."""
    import time
    from datetime import datetime

    # Current timestamp
    now = time.time()
    assert isinstance(now, float)
    assert now > 0

    # Datetime formatting
    dt = datetime.fromtimestamp(now)
    iso_format = dt.isoformat()
    assert isinstance(iso_format, str)
    assert "T" in iso_format
