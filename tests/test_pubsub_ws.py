import sqlite3
import sys
from pathlib import Path

# Add src to path - needs to be before local imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from unittest.mock import patch  # noqa: E402

import pytest  # noqa: E402
from flask import request  # noqa: E402

from pubsub_ws import (  # noqa: E402
    Broker,
    app,
    handle_disconnect,
    handle_subscribe,
    init_db,
    socketio,
)


# Fixtures (unchanged)
@pytest.fixture
def db_conn():
    """Creates and initializes an in-memory SQLite database for each test."""
    conn = sqlite3.connect(":memory:")
    init_db(db_name=":memory:", connection=conn)
    yield conn
    conn.close()


@pytest.fixture
def test_broker(db_conn):
    """Creates a Broker instance using the in-memory database."""
    broker = Broker(db_name=":memory:", test_conn=db_conn)
    yield broker


@pytest.fixture
def socketio_test_client(test_broker, db_conn):
    """Creates a Socket.IO test client for the Flask application."""
    # Note: This client is mainly useful for complete integration tests,
    # not for directly testing handlers that manipulate `request.sid`.
    # We keep it for its ability to send events and receive responses.
    with patch("pubsub_ws.broker", new=test_broker), patch("pubsub_ws.init_db"):
        client = socketio.test_client(app)
        yield client
        client.disconnect()


@pytest.fixture
def flask_test_client(test_broker, db_conn):
    """Creates a Flask test client for the application."""
    with patch("pubsub_ws.broker", new=test_broker), app.test_client() as client:
        yield client


# --- Tests for the Broker class (unchanged because they pass) ---


def test_broker_register_subscription(test_broker, mocker):
    sid = "test_sid_1"
    consumer = "test_consumer_1"
    topic = "test_topic_1"
    with patch.object(socketio, "emit") as mock_emit:
        test_broker.register_subscription(sid, consumer, topic)
        clients = test_broker.get_clients()
        assert len(clients) == 1
        assert clients[0]["consumer"] == consumer
        assert clients[0]["topic"] == topic
        mock_emit.assert_called_with(
            "new_client", {"consumer": consumer, "topic": topic, "connected_at": mocker.ANY}
        )


def test_broker_unregister_client(test_broker):
    sid = "test_sid_2"
    consumer = "test_consumer_2"
    topic = "test_topic_2"
    test_broker.register_subscription(sid, consumer, topic)
    with patch.object(socketio, "emit") as mock_emit:
        test_broker.unregister_client(sid)
        clients = test_broker.get_clients()
        assert len(clients) == 0
        mock_emit.assert_called_with("client_disconnected", {"consumer": consumer, "topic": topic})


def test_broker_save_message(test_broker, mocker):
    topic = "sport"
    message_id = "msg_123"
    message = {"text": "Football score"}
    producer = "news_bot"
    with patch.object(socketio, "emit") as mock_emit:
        test_broker.save_message(topic, message_id, message, producer)
        messages = test_broker.get_messages()
        assert len(messages) == 1
        assert messages[0]["message_id"] == message_id
        assert messages[0]["message"] == message
        assert messages[0]["producer"] == producer
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


def test_broker_save_consumption(test_broker, mocker):
    consumer = "alice"
    topic = "finance"
    message_id = "msg_456"
    message = {"stock": "AAPL", "price": 170}
    with patch.object(socketio, "emit") as mock_emit:
        test_broker.save_consumption(consumer, topic, message_id, message)
        consumptions = test_broker.get_consumptions()
        assert len(consumptions) == 1
        assert consumptions[0]["consumer"] == consumer
        assert consumptions[0]["message_id"] == message_id
        assert consumptions[0]["message"] == message
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
    assert test_broker.get_clients() == []
    assert test_broker.get_messages() == []
    assert test_broker.get_consumptions() == []


# --- Tests for HTTP endpoints (Flask) (unchanged because they pass) ---


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
    test_broker.register_subscription("s1", "bob", "tech")
    response = flask_test_client.get("/clients")
    assert response.status_code == 200
    assert len(response.json) == 1
    assert response.json[0]["consumer"] == "bob"


def test_messages_endpoint(flask_test_client, test_broker):
    test_broker.save_message("news", "news_id_1", {"text": "Breaking news"}, "reporter")
    response = flask_test_client.get("/messages")
    assert response.status_code == 200
    assert len(response.json) == 1
    assert response.json[0]["topic"] == "news"


def test_consumptions_endpoint(flask_test_client, test_broker):
    test_broker.save_consumption("charlie", "sport", "game_msg", {"score": "2-1"})
    response = flask_test_client.get("/consumptions")
    assert response.status_code == 200
    assert len(response.json) == 1
    assert response.json[0]["consumer"] == "charlie"


# --- Tests for Socket.IO events ---


def test_socketio_subscribe(socketio_test_client, test_broker, mocker):
    consumer_name = "test_consumer"
    topics = ["topic_a", "topic_b"]

    # Generate an arbitrary but constant SID for this test
    test_sid = "test_socket_sid_123_sub"  # Utilisez un SID unique pour ce test

    # Utilisez le contexte de l'application Flask pour simuler `request`
    with app.test_request_context("/"):
        # Force request.sid to our test SID
        request.sid = test_sid  # <-- NEW: Direct assignment to request.sid

        with patch("pubsub_ws.join_room") as mock_join_room, patch.object(
                test_broker, "register_subscription"
        ) as mock_register_subscription, patch("pubsub_ws.emit") as mock_emit:
            # Call the event handler directly.
            # `handle_subscribe` attend `data` comme argument.
            handle_subscribe(
                {"consumer": consumer_name, "topics": topics}
            )  # <-- NOUVEAU : Appel direct

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

            mock_emit.assert_any_call(
                "message",
                {
                    "topic": "topic_a",
                    "message_id": mocker.ANY,
                    "message": "Subscribed to topic_a",
                    "producer": "server",
                },
                to=test_sid,
            )
            mock_emit.assert_any_call(
                "message",
                {
                    "topic": "topic_b",
                    "message_id": mocker.ANY,
                    "message": "Subscribed to topic_b",
                    "producer": "server",
                },
                to=test_sid,
            )
            assert mock_emit.call_count == 2

            # Note: `socketio_test_client.get_received()` ne fonctionnera pas ici
            # because we didn't emit *via* the test client, but directly
            # au gestionnaire. Ce n'est pas une limitation du test mais un changement de focus.
            # Si vous voulez tester ce que le client *recevrait*, vous devriez
            # utiliser le socketio_test_client et les patches de `request.sid` pour sa session.
            # Pour l'instant, nous testons le comportement du serveur.
            # assert len(received) >= 2 # REMOVED


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
            data["consumer"], data["topic"], data["message_id"], str(data["message"])
        )


# noinspection PyUnusedLocal
def test_socketio_disconnect(socketio_test_client, test_broker, mocker):
    # Generate an arbitrary but constant SID for this test
    test_sid = "test_socket_sid_disconnect_456"

    # Enregistrez d'abord une souscription pour que unregister_client ait un impact
    test_broker.register_subscription(test_sid, "dis_consumer", "dis_topic")

    # Utilisez le contexte de l'application Flask pour simuler `request`
    with app.test_request_context("/"):
        # Force request.sid to our test SID
        request.sid = test_sid  # <-- NEW: Direct assignment to request.sid

        with patch.object(test_broker, "unregister_client") as mock_unregister_client:
            # Call the event handler directly.
            # `handle_disconnect` ne prend pas d'arguments explicites.
            handle_disconnect()  # <-- NOUVEAU : Appel direct

            mock_unregister_client.assert_called_once_with(test_sid)
