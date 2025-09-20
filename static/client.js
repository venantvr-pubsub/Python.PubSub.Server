document.addEventListener("DOMContentLoaded", () => {
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
            super(producer, { text: text }, message_id);
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

            socket.emit("subscribe", {
                consumer,
                topics
            });

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
            document.getElementById("receivedMessagesList").prepend(item); // Add to top

            // Notify server of consumption
            socket.emit("consumed", {
                topic: data.topic,
                message_id: data.message_id,
                message: data.message,
                consumer: consumer
            });
        });

        // Handle disconnection
        socket.on("disconnect", () => {
            console.log("Disconnected from server.");
        });

        // Handle new message events for UI updates (ADMIN panel specific)
        socket.on("new_message", (data) => {
            console.log(`New message event received (for admin UI): ${JSON.stringify(data)}`);
            refreshMessages();
        });

        // ADMIN EVENTS
        socket.on("new_client", (data) => {
            console.log(`New client connected: ${JSON.stringify(data)}`);
            refreshClients();
        });

        socket.on("client_disconnected", (data) => {
            console.log(`Client disconnected: ${JSON.stringify(data)}`);
            refreshClients();
        });

        socket.on("new_consumption", (data) => {
            console.log(`New consumption: ${JSON.stringify(data)}`);
            refreshConsumptions();
        });
    });

    // Handle publish button click
    document.getElementById("pubBtn").addEventListener("click", () => {
        const topic = document.getElementById("pubTopic").value;
        const messageText = document.getElementById("pubMessage").value;
        const producer = document.getElementById("pubProducer").value || "frontend_publisher"; // Default producer

        if (!topic || !messageText) {
            alert("Please enter a topic and a message to publish.");
            return;
        }

        const message_id = uuidv4(); // Generate mandatory message ID

        console.log(`Publishing to topic ${topic}: "${messageText}" by ${producer} with ID ${message_id}`);

        const msg = new TextMessage(messageText, producer, message_id);
        const payload = msg.toPayload(topic);

        fetch("/publish", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        })
            .then(r => {
                if (!r.ok) { // Check for HTTP errors (4xx, 5xx)
                    return r.json().then(errData => Promise.reject(new Error(errData.message || `HTTP error! Status: ${r.status}`)));
                }
                return r.json();
            })
            .then(data => {
                console.log(`Publish response: ${JSON.stringify(data)}`);
                // The new_message event from the server will trigger refreshMessages()
                // No need to call refreshMessages() directly here
                document.getElementById("pubMessage").value = ""; // Clear message field
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
            .then(r => {
                if (!r.ok) throw new Error(`HTTP error! Status: ${r.status}`);
                return r.json();
            })
            .then(clients => {
                const tbody = document.querySelector("#clientsTable tbody");
                tbody.innerHTML = "";
                clients.forEach(c => {
                    const tr = document.createElement("tr");
                    tr.innerHTML = `<td>${c.consumer}</td>
                                <td>${c.topic}</td>
                                <td>${formatTimestamp(c.connected_at)}</td>`;
                    tbody.appendChild(tr);
                });
                console.log(`Clients list updated with ${clients.length} clients`);
            })
            .catch(err => {
                console.error(`Error fetching clients: ${err}`);
            });
    }

    // Refresh the messages table
    function refreshMessages() {
        console.log("Refreshing published messages list");
        fetch("/messages")
            .then(r => {
                if (!r.ok) throw new Error(`HTTP error! Status: ${r.status}`);
                return r.json();
            })
            .then(messages => {
                const tbody = document.querySelector("#messagesTable tbody");
                tbody.innerHTML = "";
                messages.forEach(m => {
                    const tr = document.createElement("tr");
                    tr.innerHTML = `<td>${m.producer}</td>
                                <td>${m.topic}</td>
                                <td>${JSON.stringify(m.message)}</td>
                                <td>${formatTimestamp(m.timestamp)}</td>`;
                    tbody.appendChild(tr);
                });
                console.log(`Published messages list updated with ${messages.length} messages`);
            })
            .catch(err => {
                console.error(`Error fetching messages: ${err}`);
            });
    }

    // Refresh the consumptions table
    function refreshConsumptions() {
        console.log("Refreshing consumptions list");
        fetch("/consumptions")
            .then(r => {
                if (!r.ok) throw new Error(`HTTP error! Status: ${r.status}`);
                return r.json();
            })
            .then(consumptions => {
                const tbody = document.querySelector("#consTable tbody");
                tbody.innerHTML = "";
                consumptions.forEach(c => {
                    const tr = document.createElement("tr");
                    tr.innerHTML = `<td>${c.consumer}</td>
                                <td>${c.topic}</td>
                                <td>${JSON.stringify(c.message)}</td>
                                <td>${formatTimestamp(c.timestamp)}</td>`;
                    tbody.appendChild(tr);
                });
                console.log(`Consumptions list updated with ${consumptions.length} consumptions`);
            })
            .catch(err => {
                console.error(`Error fetching consumptions: ${err}`);
            });
    }

    // Refresh tab content when switching tabs
    document.getElementById('pubSubTabs').addEventListener('shown.bs.tab', function (event) {
        const targetTab = event.target.getAttribute('data-bs-target');
        if (targetTab === '#received-messages') {
            console.log('Switched to Received Messages tab');
            // This tab updates in real-time, no specific refresh needed on switch
        } else if (targetTab === '#clients') {
            console.log('Switched to Clients tab');
            refreshClients();
        } else if (targetTab === '#messages') {
            console.log('Switched to Published Messages tab');
            refreshMessages();
        } else if (targetTab === '#consumptions') {
            console.log('Switched to Consumptions tab');
            refreshConsumptions();
        }
    });

    // Initial refresh of admin tables on page load
    document.addEventListener("DOMContentLoaded", () => {
        // Only refresh the currently active tab initially to avoid unnecessary calls
        // Bootstrap tabs usually activate the first one by default if not specified
        const activeTabButton = document.querySelector('#pubSubTabs button.active');
        if (activeTabButton) {
            const targetTab = activeTabButton.getAttribute('data-bs-target');
            if (targetTab === '#clients') {
                refreshClients();
            } else if (targetTab === '#messages') {
                refreshMessages();
            } else if (targetTab === '#consumptions') {
                refreshConsumptions();
            }
        }
        // Alternatively, you can just call all three for simplicity if performance isn't a concern
        // refreshClients();
        // refreshMessages();
        // refreshConsumptions();
    });
});
