import sys
from pathlib import Path

# Add src to path - needs to be before local imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from unittest.mock import MagicMock, patch  # noqa: E402

import pytest  # noqa: E402
from flask import request  # noqa: E402

from pubsub_ws import (  # noqa: E402
    Broker,
    app,
    handle_disconnect,
    handle_subscribe,
    socketio,
)


# Fixtures
@pytest.fixture
def mock_db():
    """Creates a mock AsyncSQLite database for testing."""
    mock = MagicMock()
    # Configure default return values
    mock.execute_read.return_value = []
    return mock


@pytest.fixture
def test_broker(mock_db):
    """Creates a Broker instance using the mock database."""
    broker = Broker(mock_db)
    yield broker


@pytest.fixture
def socketio_test_client(test_broker):
    """Creates a Socket.IO test client for the Flask application."""
    with patch("pubsub_ws.broker", new=test_broker):
        client = socketio.test_client(app)
        yield client
        client.disconnect()


@pytest.fixture
def flask_test_client(test_broker):
    """Creates a Flask test client for the application."""
    with patch("pubsub_ws.broker", new=test_broker), app.test_client() as client:
        yield client


# --- Tests for the Broker class ---


# noinspection PyUnresolvedReferences
def test_broker_register_subscription(test_broker, mocker):
    sid = "test_sid_1"
    consumer = "test_consumer_1"
    topic = "test_topic_1"

    with patch.object(socketio, "emit") as mock_emit:
        test_broker.register_subscription(sid, consumer, topic)

        # Verify execute_write was called with correct SQL
        test_broker.db.execute_write.assert_called_once()
        call_args = test_broker.db.execute_write.call_args
        assert "INSERT OR REPLACE INTO subscriptions" in call_args[0][0]
        assert call_args[0][1][0] == sid
        assert call_args[0][1][1] == consumer
        assert call_args[0][1][2] == topic

        mock_emit.assert_called_with(
            "new_client", {"consumer": consumer, "topic": topic, "connected_at": mocker.ANY}
        )


# noinspection PyUnresolvedReferences
def test_broker_unregister_client(test_broker):
    sid = "test_sid_2"
    consumer = "test_consumer_2"
    topic = "test_topic_2"

    # Mock get_client_by_sid to return consumer and topic
    test_broker.db.execute_read.return_value = (consumer, topic)

    with patch.object(socketio, "emit") as mock_emit:
        test_broker.unregister_client(sid)

        # Verify DELETE was called
        assert test_broker.db.execute_write.call_count >= 1
        delete_call = [call for call in test_broker.db.execute_write.call_args_list
                       if "DELETE FROM subscriptions" in str(call)]
        assert len(delete_call) > 0

        mock_emit.assert_called_with("client_disconnected", {"consumer": consumer, "topic": topic})


# noinspection PyUnresolvedReferences
def test_broker_save_message(test_broker, mocker):
    topic = "sport"
    message_id = "msg_123"
    message = {"text": "Football score"}
    producer = "news_bot"

    with patch.object(socketio, "emit") as mock_emit:
        test_broker.save_message(topic, message_id, message, producer)

        # Verify execute_write was called
        test_broker.db.execute_write.assert_called_once()
        call_args = test_broker.db.execute_write.call_args
        assert "INSERT INTO messages" in call_args[0][0]

        mock_emit.assert_called_with(
            "new_message",
            {
                "topic": topic,
                "message_id": message_id,
                "message": message,
                "producer": producer,
                "timestamp": mocker.ANY,
            },
        )


# noinspection PyUnresolvedReferences
def test_broker_save_consumption(test_broker, mocker):
    consumer = "alice"
    topic = "finance"
    message_id = "msg_456"
    message = {"stock": "AAPL", "price": 170}

    with patch.object(socketio, "emit") as mock_emit:
        test_broker.save_consumption(consumer, topic, message_id, message)

        # Verify execute_write was called
        test_broker.db.execute_write.assert_called_once()
        call_args = test_broker.db.execute_write.call_args
        assert "INSERT INTO consumptions" in call_args[0][0]

        mock_emit.assert_called_with(
            "new_consumption",
            {
                "consumer": consumer,
                "topic": topic,
                "message_id": message_id,
                "message": message,
                "timestamp": mocker.ANY,
            },
        )


def test_broker_get_clients_and_messages_empty(test_broker):
    test_broker.db.execute_read.return_value = []

    assert test_broker.get_clients() == []
    assert test_broker.get_messages() == []
    assert test_broker.get_consumptions() == []


# --- Tests for HTTP endpoints (Flask) ---


def test_publish_endpoint(flask_test_client, test_broker):
    topic = "test_topic"
    message_id = "test_msg_id"
    message_content = {"data": "hello"}
    producer = "test_producer"
    payload = {
        "topic": topic,
        "message_id": message_id,
        "message": message_content,
        "producer": producer,
    }

    with patch.object(test_broker, "save_message") as mock_save, patch(
            "pubsub_ws.socketio.emit"
    ) as mock_emit:
        response = flask_test_client.post("/publish", json=payload)
        assert response.status_code == 200
        assert response.json == {"status": "ok"}
        mock_save.assert_called_once_with(
            topic=topic, message_id=message_id, message=message_content, producer=producer
        )
        mock_emit.assert_called_once_with("message", payload, to=topic)


def test_publish_endpoint_missing_data(flask_test_client):
    response = flask_test_client.post(
        "/publish", json={"topic": "sport", "message": "missing_id", "producer": "me"}
    )
    assert response.status_code == 400
    assert "Missing topic, message_id, message, or producer" in response.json["message"]


def test_clients_endpoint(flask_test_client, test_broker):
    test_broker.db.execute_read.return_value = [("bob", "tech", 123456.0)]

    response = flask_test_client.get("/clients")
    assert response.status_code == 200
    assert len(response.json) == 1
    assert response.json[0]["consumer"] == "bob"


def test_messages_endpoint(flask_test_client, test_broker):
    test_broker.db.execute_read.return_value = [
        ("news", "news_id_1", '{"text": "Breaking news"}', "reporter", 123456.0)
    ]

    response = flask_test_client.get("/messages")
    assert response.status_code == 200
    assert len(response.json) == 1
    assert response.json[0]["topic"] == "news"


def test_consumptions_endpoint(flask_test_client, test_broker):
    test_broker.db.execute_read.return_value = [
        ("charlie", "sport", "game_msg", '{"score": "2-1"}', 123456.0)
    ]

    response = flask_test_client.get("/consumptions")
    assert response.status_code == 200
    assert len(response.json) == 1
    assert response.json[0]["consumer"] == "charlie"


# --- Tests for Socket.IO events ---


def test_socketio_subscribe(socketio_test_client, test_broker, mocker):
    consumer_name = "test_consumer"
    topics = ["topic_a", "topic_b"]
    test_sid = "test_socket_sid_123_sub"

    with app.test_request_context("/"):
        request.sid = test_sid

        with patch("pubsub_ws.join_room") as mock_join_room, patch.object(
                test_broker, "register_subscription"
        ) as mock_register_subscription:
            handle_subscribe({"consumer": consumer_name, "topics": topics})

            mock_join_room.assert_any_call("topic_a")
            mock_join_room.assert_any_call("topic_b")
            assert mock_join_room.call_count == 2

            mock_register_subscription.assert_has_calls(
                [
                    mocker.call(test_sid, consumer_name, "topic_a"),
                    mocker.call(test_sid, consumer_name, "topic_b"),
                ],
                any_order=True,
            )
            assert mock_register_subscription.call_count == 2


def test_socketio_consumed(socketio_test_client, test_broker):
    data = {
        "consumer": "test_consumer_c",
        "topic": "test_topic_c",
        "message_id": "msg_id_c",
        "message": {"content": "consumed_message"},
    }

    with patch.object(test_broker, "save_consumption") as mock_save_consumption:
        socketio_test_client.emit("consumed", data)
        mock_save_consumption.assert_called_once_with(
            data["consumer"], data["topic"], data["message_id"], data["message"]
        )


# noinspection PyUnusedLocal
def test_socketio_disconnect(socketio_test_client, test_broker, mocker):
    test_sid = "test_socket_sid_disconnect_456"

    # Mock get_client_by_sid to return a tuple
    test_broker.db.execute_read.return_value = ("dis_consumer", "dis_topic")

    with app.test_request_context("/"):
        request.sid = test_sid

        with patch.object(test_broker, "unregister_client") as mock_unregister_client:
            handle_disconnect()
            mock_unregister_client.assert_called_once_with(test_sid)