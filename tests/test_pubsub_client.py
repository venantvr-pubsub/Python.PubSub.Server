import logging
import sys
from pathlib import Path

# Add src to path - needs to be before local imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from unittest.mock import MagicMock, patch  # noqa: E402

import pytest  # noqa: E402
from client import BASE_URL, PubSubClient  # noqa: E402
from socketio import exceptions  # noqa: E402


# Mock of socketio.Client
# We will mock the socketio.Client class itself, not its instance directly
# Then, we access mock_sio_client.return_value to mock the instance methods
@pytest.fixture
def mock_sio_client():
    """Mocks the socketio.Client instance used by PubSubClient."""
    with patch(
            "client.socketio.Client"
    ) as MockClient:  # <-- Patch la class directement dans le module client
        instance = MockClient.return_value  # This is the mock of the instance that will be created
        instance.connected = False  # Simulate initial disconnected state
        yield MockClient  # We yield the Mock of the Client CLASS itself, not its instance


# Mock de requests.post
@pytest.fixture
def mock_requests_post():
    """Mocke requests.post pour les appels de publication HTTP."""
    # Patch requests.post in the client module where it is used
    with patch(
            "client.requests.post"
    ) as mock_post:  # <-- Patch requests.post dans le module client
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "ok", "message_id": "test_id_returned"}
        mock_response.raise_for_status.return_value = None  # No HTTP errors by default
        mock_post.return_value = mock_response
        yield mock_post


# --- Tests pour la class PubSubClient (du fichier client.py) ---


def test_pubsub_client_init(mock_sio_client):
    """Verifies client initialization and handler registration."""
    consumer = "test_alice"
    topics = ["sport", "finance"]
    client = PubSubClient(consumer, topics)

    assert client.consumer_name == consumer
    assert client.topics == topics

    # Verify that socketio.Client was called once with the correct argument
    mock_sio_client.assert_called_once_with(reconnection=True)

    # Verify that event handlers are registered on the mocked instance
    mock_sio_client.return_value.on.assert_any_call("message", client.on_message)
    mock_sio_client.return_value.on.assert_any_call("new_client", client.on_new_client)
    mock_sio_client.return_value.on.assert_any_call(
        "client_disconnected", client.on_client_disconnected
    )
    mock_sio_client.return_value.on.assert_any_call("new_consumption", client.on_new_consumption)
    mock_sio_client.return_value.on.assert_any_call("new_message", client.on_new_message)


def test_pubsub_client_connect_success(mock_sio_client):
    """Tests the connect method in case of success."""
    consumer = "test_bob"
    topics = ["tech"]
    client = PubSubClient(consumer, topics)

    # Get the mock of the client instance that was created
    mock_instance = mock_sio_client.return_value
    mock_instance.connected = True  # Simulate successful connection

    client.connect()

    # Verify that connect was called on the mocked instance with the correct URL
    mock_instance.connect.assert_called_once_with(BASE_URL)

    # Verify that the "subscribe" event was emitted on the mocked instance
    mock_instance.emit.assert_called_once_with(
        "subscribe", {"consumer": consumer, "topics": topics}
    )


def test_pubsub_client_connect_failure(mock_sio_client, caplog):
    """Tests the connect method in case of connection failure."""
    consumer = "test_charlie"
    topics = ["music"]
    client = PubSubClient(consumer, topics)

    # Obtenez le mock de l'instance client
    mock_instance = mock_sio_client.return_value
    # Simule une ConnectionError lors de la connection
    mock_instance.connect.side_effect = exceptions.ConnectionError("Connection refused")

    with caplog.at_level(logging.ERROR):  # Capture les logs d'erreur
        client.connect()

    # The error message should be in the logs
    assert "Failed to connect to server: Connection refused" in caplog.text
    # Verify that connect was called even if it raised an exception
    mock_instance.connect.assert_called_once()


def test_pubsub_client_on_message(caplog):
    """Teste le gestionnaire on_message."""
    consumer = "test_diana"
    topics = ["food"]
    client = PubSubClient(consumer, topics)

    test_data = {"topic": "pizza", "message": {"type": "text", "content": "Hello pizza!"}}
    with caplog.at_level(logging.INFO):
        client.on_message(test_data)
    assert "[MESSAGE] [pizza] {'type': 'text', 'content': 'Hello pizza!'}" in caplog.text


def test_pubsub_client_publish(mock_requests_post):
    """Tests the publish method."""
    consumer = "test_eve"
    topics = ["travel"]
    client = PubSubClient(consumer, topics)

    topic_to_publish = "destinations"
    message_content = {"city": "Paris", "country": "France"}
    message_id = "uuid-1234"

    response = client.publish(topic_to_publish, message_content, message_id)

    # Verify that requests.post was called with the correct data
    expected_url = f"{BASE_URL}/publish"
    expected_json = {
        "topic": topic_to_publish,
        "message": message_content,
        "producer": consumer,
        "message_id": message_id,
    }
    mock_requests_post.assert_called_once_with(expected_url, json=expected_json, timeout=10)

    # Verify the response returned by the publish method
    assert response == {"status": "ok", "message_id": "test_id_returned"}


def test_pubsub_client_disconnect_connected(mock_sio_client, caplog):
    """Tests disconnection when the client is connected."""
    consumer = "test_frank"
    topics = ["sports"]
    client = PubSubClient(consumer, topics)

    # Obtenez le mock de l'instance client
    mock_instance = mock_sio_client.return_value
    mock_instance.connected = True  # Simulate connected state

    with caplog.at_level(logging.INFO):
        client.disconnect()

    # Verify that disconnect was called on the mocked instance
    mock_instance.disconnect.assert_called_once()
    assert f"Disconnected {consumer} from server." in caplog.text


def test_pubsub_client_disconnect_not_connected(mock_sio_client, caplog):
    """Tests disconnection when the client is not connected."""
    consumer = "test_grace"
    topics = ["art"]
    client = PubSubClient(consumer, topics)

    # Obtenez le mock de l'instance client
    mock_instance = mock_sio_client.return_value
    mock_instance.connected = False  # Simulate disconnected state

    with caplog.at_level(logging.INFO):
        client.disconnect()

    # Verify that disconnect was NOT called on the mocked instance
    mock_instance.disconnect.assert_not_called()
    assert f"Disconnected {consumer} from server." not in caplog.text
