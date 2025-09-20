document.addEventListener("DOMContentLoaded", () => {
    const MAX_LIST_SIZE = 100; // Limite globale pour toutes les listes

    // Generate a UUID v4 for message IDs
    function uuidv4() {
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
            let r = Math.random() * 16 | 0,
                v = c === 'x' ? r : (r & 0x3 | 0x8);
            return v.toString(16);
        });
    }

    // Base message class for structuring messages
    class BaseMessage {
        constructor(producer, payload, message_id = null) {
            this.message_id = message_id || uuidv4();
            this.producer = producer;
            this.payload = payload;
        }

        toPayload(topic) {
            return {
                topic: topic,
                message_id: this.message_id,
                message: this.payload,
                producer: this.producer
            };
        }
    }

    // Specific business class for text messages
    class TextMessage extends BaseMessage {
        constructor(text, producer, message_id) {
            super(producer, {text: text}, message_id);
        }
    }

    let socket;

    // Handle connect and subscribe button click
    document.getElementById("connectBtn").addEventListener("click", () => {
        const consumer = document.getElementById("consumer").value;
        const topics = document.getElementById("topics").value
            .split(",").map(s => s.trim()).filter(s => s);

        if (!consumer || topics.length === 0) {
            alert("Please enter a consumer name and at least one topic.");
            return;
        }

        console.log(`Connecting as ${consumer} to topics: ${topics}`);

        // If a socket already exists and is connected, disconnect first
        if (socket && socket.connected) {
            console.log("Disconnecting existing socket before new connection.");
            socket.disconnect();
        }

        socket = io({
            reconnection: true,
            reconnectionAttempts: Infinity,
            reconnectionDelay: 2000
        });

        socket.on("connect", () => {
            console.log("Connected to server.");
            socket.emit("subscribe", {consumer, topics});
            console.log(`Subscribed to topics: ${topics}`);
            // Refresh admin tables on successful connection
            refreshMessages();
            refreshClients();
            refreshConsumptions();
        });

        socket.on("message", (data) => {
            console.log(`Message received: ${JSON.stringify(data)}`);

            // Display message in the "Received Messages" UI
            const item = document.createElement("li");
            item.className = "list-group-item";
            item.innerHTML = `<strong>[${data.topic}]</strong> <em>(${data.producer} / ${data.message_id})</em>: ${JSON.stringify(data.message)}`;
            list.prepend(item);

            // --- AJOUT : Limiter la taille de la liste des messages reçus ---
            while (list.children.length > MAX_LIST_SIZE) {
                list.removeChild(list.lastChild);
            }
            // --- FIN DE L'AJOUT ---

            socket.emit("consumed", {
                topic: data.topic,
                message_id: data.message_id,
                message: data.message,
                consumer: consumer
            });
        });

        socket.on("disconnect", () => console.log("Disconnected from server."));
        socket.on("new_message", () => refreshMessages());
        socket.on("new_client", () => refreshClients());
        socket.on("client_disconnected", () => refreshClients());
        socket.on("new_consumption", () => refreshConsumptions());
    });

    document.getElementById("pubBtn").addEventListener("click", () => {
        const topic = document.getElementById("pubTopic").value;
        const messageText = document.getElementById("pubMessage").value;
        const producer = document.getElementById("pubProducer").value || "frontend_publisher";

        if (!topic || !messageText) {
            alert("Please enter a topic and a message to publish.");
            return;
        }

        const msg = new TextMessage(messageText, producer, uuidv4());
        const payload = msg.toPayload(topic);

        fetch("/publish", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(payload)
        })
            .then(r => r.ok ? r.json() : r.json().then(e => Promise.reject(new Error(e.message))))
            .then(data => {
                console.log(`Publish response: ${JSON.stringify(data)}`);
                document.getElementById("pubMessage").value = "";
            })
            .catch(err => {
                console.error(`Publish error: ${err}`);
                alert(`Failed to publish message: ${err.message}`);
            });
    });

    // Helper function to format timestamp
    function formatTimestamp(unixTimestamp) {
        if (!unixTimestamp) return '';
        return new Date(unixTimestamp * 1000).toLocaleString();
    }

    // Refresh the clients table
    function refreshClients() {
        console.log("Refreshing clients list");
        fetch("/clients")
            .then(r => r.json())
            .then(clients => {
                const tbody = document.querySelector("#clientsTable tbody");
                tbody.innerHTML = "";
                // --- AJOUT : Limiter le nombre de clients affichés ---
                clients.slice(0, MAX_LIST_SIZE).forEach(c => {
                    const tr = document.createElement("tr");
                    tr.innerHTML = `<td>${c.consumer}</td><td>${c.topic}</td><td>${formatTimestamp(c.connected_at)}</td>`;
                    tbody.appendChild(tr);
                });
            })
            .catch(err => console.error(`Error fetching clients: ${err}`));
    }

    // Refresh the messages table
    function refreshMessages() {
        console.log("Refreshing published messages list");
        fetch("/messages")
            .then(r => r.json())
            .then(messages => {
                const tbody = document.querySelector("#messagesTable tbody");
                tbody.innerHTML = "";
                // --- AJOUT : Limiter le nombre de messages affichés ---
                messages.slice(0, MAX_LIST_SIZE).forEach(m => {
                    const tr = document.createElement("tr");
                    tr.innerHTML = `<td>${m.producer}</td><td>${m.topic}</td><td>${JSON.stringify(m.message)}</td><td>${formatTimestamp(m.timestamp)}</td>`;
                    tbody.appendChild(tr);
                });
                console.log(`Published messages list updated with ${messages.length} messages`);
            })
            .catch(err => console.error(`Error fetching messages: ${err}`));
    }

    // Refresh the consumptions table
    function refreshConsumptions() {
        console.log("Refreshing consumptions list");
        fetch("/consumptions")
            .then(r => r.json())
            .then(consumptions => {
                const tbody = document.querySelector("#consTable tbody");
                tbody.innerHTML = "";
                // --- AJOUT : Limiter le nombre de consommations affichées ---
                consumptions.slice(0, MAX_LIST_SIZE).forEach(c => {
                    const tr = document.createElement("tr");
                    tr.innerHTML = `<td>${c.consumer}</td><td>${c.topic}</td><td>${JSON.stringify(c.message)}</td><td>${formatTimestamp(c.timestamp)}</td>`;
                    tbody.appendChild(tr);
                });
                console.log(`Consumptions list updated with ${consumptions.length} consumptions`);
            })
            .catch(err => console.error(`Error fetching consumptions: ${err}`));
    }

    // Refresh tab content when switching tabs
    document.getElementById('pubSubTabs').addEventListener('shown.bs.tab', function (event) {
        const targetTab = event.target.getAttribute('data-bs-target');
        if (targetTab === '#clients') refreshClients();
        else if (targetTab === '#messages') refreshMessages();
        else if (targetTab === '#consumptions') refreshConsumptions();
    });
});