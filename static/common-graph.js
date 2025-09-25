/**
 * common-graph.js
 * Ce fichier contient la logique générique pour créer un graphe D3 interactif
 * mis à jour via WebSockets. Il est configurable pour différents types de layouts et de rendus.
 */

// Exporte la fonction principale pour la rendre importable dans d'autres fichiers.
/* export */ function createGraph(config) {
    // --- Initialisation Socket.io et D3 ---
    const socket = io();
    const svg = d3.select(config.svgSelector);
    const width = svg.node().getBoundingClientRect().width;
    const height = svg.node().getBoundingClientRect().height;
    const radius = 20;

    const g = svg.append("g");
    const linkGroup = g.append("g").attr("class", "links");
    const nodeGroup = g.append("g").attr("class", "nodes");

    // --- Définition des flèches (Markers) ---
    // La configuration permet d'ajuster la position de la pointe de flèche.
    svg.append("defs").selectAll("marker")
        .data(["publish", "consume", "consumed"])
        .enter().append("marker")
        .attr("id", d => `arrow-${d}`)
        .attr("viewBox", "0 -5 10 10")
        .attr("refX", config.arrow.refX)
        .attr("refY", 0)
        .attr("markerWidth", 6)
        .attr("markerHeight", 6)
        .attr("orient", config.arrow.orient)
        .append("path")
        .attr("d", "M0,-5L10,0L0,5")
        .style("fill", d => d === 'publish' ? '#28a745' : d === 'consume' ? '#ffab40' : '#dc3545');

    // --- Données et Simulation ---
    let nodes = [];
    const nodeMap = new Map();
    // La simulation est créée en utilisant la fonction fournie dans la configuration.
    const simulation = config.createSimulation(width, height);

    // --- Fonctions communes ---

    function addOrUpdateNode(id, role) {
        let node = nodeMap.get(id);
        let isNewNode = false;
        if (!node) {
            node = { id, name: id, roles: [role] };
            nodes.push(node);
            nodeMap.set(id, node);
            isNewNode = true;
        } else if (!node.roles.includes(role)) {
            node.roles.push(role);
        }
        return isNewNode;
    }

    function drawTemporaryArrow(sourceId, targetId, type) {
        const sourceNode = nodeMap.get(sourceId);
        const targetNode = nodeMap.get(targetId);
        if (!sourceNode || !targetNode) return;

        // Appelle la fonction de dessin de lien fournie par la configuration.
        const tempLink = config.drawLink(linkGroup, sourceNode, targetNode, type);

        tempLink.transition()
            .duration(2000)
            .style("opacity", 0)
            .remove();
    }

    function updateGraph() {
        nodeGroup.selectAll(".node")
            .data(nodes, d => d.id)
            .join(
                enter => {
                    const nodeEnter = enter.append("g")
                        .attr("class", d => `node ${d.roles.join(' ')}`)
                        .call(drag(simulation));
                    nodeEnter.append("circle").attr("r", radius);
                    nodeEnter.append("text").attr("dy", ".35em").attr("y", radius + 15).text(d => d.name);
                    return nodeEnter;
                },
                update => update.attr("class", d => `node ${d.roles.join(' ')}`)
            );

        simulation.nodes(nodes);
        simulation.alpha(0.3).restart();
    }

    // Le "tick" appelle la fonction de tick spécifique fournie par la configuration.
    simulation.on("tick", () => config.tickHandler(nodeGroup, linkGroup));

    // --- Interactivité (Zoom et Drag) ---

    const zoom = d3.zoom().on("zoom", (event) => g.attr("transform", event.transform));
    svg.call(zoom);

    const drag = simulation => {
        function dragstarted(event, d) {
            if (!event.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
        }
        function dragged(event, d) {
            d.fx = event.x;
            d.fy = event.y;
        }
        function dragended(event, d) {
            if (!event.active) simulation.alphaTarget(0);
            d.fx = null;
            d.fy = null;
        }
        return d3.drag().on("start", dragstarted).on("drag", dragged).on("end", dragended);
    }

    // --- Initialisation et WebSockets ---

    async function initializeGraph() {
        const response = await fetch('/graph/state');
        const state = await response.json();

        state.producers.forEach(p => addOrUpdateNode(p, 'producer'));
        state.topics.forEach(t => addOrUpdateNode(t, 'topic'));
        state.consumers.forEach(c => addOrUpdateNode(c, 'consumer'));

        // Appelle la fonction de positionnement des nœuds de la configuration.
        config.positionNodes(nodes, width, height);
        updateGraph();
    }

    function handleWebSocketEvent(data) {
        const { producer, topic, consumer } = data;
        let needsReposition = false;

        if (producer) needsReposition = addOrUpdateNode(producer, 'producer') || needsReposition;
        if (topic) needsReposition = addOrUpdateNode(topic, 'topic') || needsReposition;
        if (consumer) needsReposition = addOrUpdateNode(consumer, 'consumer') || needsReposition;

        if (data.type === 'publish') drawTemporaryArrow(producer, topic, 'publish');
        if (data.type === 'consume') drawTemporaryArrow(topic, consumer, 'consume');
        if (data.type === 'consumed') drawTemporaryArrow(topic, consumer, 'consumed');

        if (needsReposition) {
            config.positionNodes(nodes, width, height);
        }
        updateGraph();
    }

    socket.on('connect', () => console.log('Connected to activity stream.'));
    socket.on('new_message', (data) => handleWebSocketEvent({ ...data, type: 'publish' }));
    socket.on('new_consumption', (data) => handleWebSocketEvent({ ...data, type: 'consume' }));
    socket.on('new_client', (data) => handleWebSocketEvent({ ...data, type: 'consume' })); // Assimilé à new_consumption
    socket.on('consumed', (data) => handleWebSocketEvent({ ...data, type: 'consumed' }));

    // Lancement
    initializeGraph();
}