"""Shared pytest fixtures and configuration."""

import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    yield db_path

    # Cleanup
    try:
        Path(db_path).unlink()
    except FileNotFoundError:
        pass  # File already removed
    except OSError as e:
        # Handle permission or other OS-related errors
        import warnings

        warnings.warn(f"Could not remove temporary file {db_path}: {e}", stacklevel=2)


@pytest.fixture
def in_memory_db():
    """Create an in-memory SQLite database."""
    conn = sqlite3.connect(":memory:")
    yield conn
    conn.close()


@pytest.fixture
def mock_socketio_server(mocker):
    """Mock SocketIO server for testing."""
    mock_server = mocker.MagicMock()
    mock_server.emit = mocker.MagicMock()
    mock_server.send = mocker.MagicMock()
    return mock_server


@pytest.fixture
def mock_flask_app(mocker):
    """Mock Flask application for testing."""
    mock_app = mocker.MagicMock()
    mock_app.config = {}
    return mock_app


@pytest.fixture
def sample_messages():
    """Sample messages for testing."""
    return [
        {"topic": "sports", "message": "Game started"},
        {"topic": "news", "message": "Breaking news"},
        {"topic": "weather", "message": "Sunny day"},
        {"topic": "sports", "message": "Goal scored!"},
    ]


@pytest.fixture
def sample_consumers():
    """Sample consumer configurations."""
    return [
        {"name": "alice", "topics": ["sports", "news"]},
        {"name": "bob", "topics": ["weather"]},
        {"name": "charlie", "topics": ["sports", "weather", "news"]},
    ]
