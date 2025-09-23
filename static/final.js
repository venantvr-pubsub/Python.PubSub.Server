document.addEventListener("DOMContentLoaded", () => {
    const socket = io();

    // --- Configuration D3 ---
    const svg = d3.select("#activity-svg");
    const width = svg.node().getBoundingClientRect().width;
    const height = svg.node().getBoundingClientRect().height;
    const radius = 20;

    const g = svg.append("g");
    const linkGroup = g.append("g").attr("class", "links");
    const nodeGroup = g.append("g").attr("class", "nodes");

    // Définition des pointes de flèches
    svg.append("defs").selectAll("marker")
        .data(["publish", "consume"])
        .enter().append("marker")
        .attr("id", d => `arrow-${d}`)
        .attr("viewBox", "0 -5 10 10")
        .attr("refX", 15) // Ajusté pour les courbes
        .attr("refY", 0)
        .attr("markerWidth", 6)
        .attr("markerHeight", 6)
        .attr("orient", "auto-start-reverse") // Mieux pour les courbes
        .append("path")
        .attr("d", "M0,-5L10,0L0,5")
        .style("fill", d => d === 'publish' ? '#28a745' : '#ffab40');

    // Simulation de forces D3
    const simulation = d3.forceSimulation()
        .force("charge", d3.forceManyBody().strength(-200))
        .force("center", d3.forceCenter(width / 2, height / 2))
        .on("tick", ticked);

    // --- Gestion des données du graphe ---
    let nodes = [];
    const nodeMap = new Map(); // Assure le principe de singleton pour les entités

    // Fonction pour ajouter un nœud s'il n'existe pas
    function addNode(id, type) {
        if (!nodeMap.has(id)) {
            const newNode = {id, type, name: id.split('-').slice(1).join('-')};
            nodes.push(newNode);
            nodeMap.set(id, newNode);
            return true;
        }
        return false;
    }

    // ✨ NOUVEAU : Fonction pour calculer le chemin d'une flèche arrondie
    function calculateCurvedPath(source, target) {
        const dx = target.x - source.x;
        const dy = target.y - source.y;
        const dr = Math.sqrt(dx * dx + dy * dy);
        // "M" = MovoTo, "A" = Elliptical Arc
        return `M${source.x},${source.y}A${dr},${dr} 0 0,1 ${target.x},${target.y}`;
    }

    // Fonction pour dessiner les flèches temporaires
    function drawTemporaryArrow(sourceId, targetId, type) {
        const sourceNode = nodeMap.get(sourceId);
        const targetNode = nodeMap.get(targetId);
        if (!sourceNode || !targetNode) return;

        // On utilise <path> au lieu de <line>
        const tempLink = linkGroup.append("path")
            .datum({source: sourceNode, target: targetNode})
            .attr("class", `link ${type}`)
            .attr("marker-end", `url(#arrow-${type})`)
            .attr("d", calculateCurvedPath(sourceNode, targetNode)); // Applique le chemin arrondi

        tempLink.transition()
            .duration(2000)
            .style("opacity", 0)
            .remove();
    }

    // --- Fonction de mise à jour du rendu ---
    function updateGraph() {
        nodeGroup.selectAll(".node")
            .data(nodes, d => d.id)
            .join(
                enter => {
                    const nodeEnter = enter.append("g")
                        .attr("class", d => `node ${d.type}`)
                        .call(drag(simulation));
                    nodeEnter.append("circle").attr("r", radius);
                    nodeEnter.append("text").attr("dy", ".35em").attr("y", radius + 15).text(d => d.name);
                    return nodeEnter;
                }
            );
        simulation.nodes(nodes);
        simulation.alpha(0.3).restart();
    }

    // Fonction appelée à chaque "tick" de la simulation
    function ticked() {
        nodeGroup.selectAll('.node').attr("transform", d => `translate(${d.x},${d.y})`);

        // Met à jour le chemin arrondi de TOUTES les flèches existantes
        linkGroup.selectAll('path').attr("d", d => calculateCurvedPath(d.source, d.target));
    }

    // --- Interactivité (Zoom et Drag) ---
    const zoom = d3.zoom().on("zoom", (event) => g.attr("transform", event.transform));
    svg.call(zoom);

    const drag = simulation => {
        function dragstarted(event, d) {
            if (!event.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x; d.fy = d.y;
        }
        function dragged(event, d) {
            d.fx = event.x; d.fy = event.y;
        }
        function dragended(event, d) {
            if (!event.active) simulation.alphaTarget(0);
            d.fx = null; d.fy = null;
        }
        return d3.drag().on("start", dragstarted).on("drag", dragged).on("end", dragended);
    }

    // ✨ NOUVEAU : Positionnement initial des nœuds en cercle
    function positionNodes() {
        const numNodes = nodes.length;
        if (numNodes === 0) return;

        const angleStep = (2 * Math.PI) / numNodes;
        const circleRadius = Math.min(width, height) / 3;

        nodes.forEach((node, i) => {
            if (node.fx == null) {
                const angle = i * angleStep;
                node.x = width / 2 + circleRadius * Math.cos(angle);
                node.y = height / 2 + circleRadius * Math.sin(angle);
            }
        });
    }

    // --- Initialisation du graphe ---
    async function initializeGraph() {
        const response = await fetch('/graph/state');
        const state = await response.json();

        state.producers.forEach(p => addNode(`producer-${p}`, 'producer'));
        state.topics.forEach(t => addNode(`topic-${t}`, 'topic'));
        state.consumers.forEach(c => addNode(`consumer-${c}`, 'consumer'));

        positionNodes();
        updateGraph();
    }

    // --- Connexion WebSocket ---
    socket.on('connect', () => console.log('Connected to activity stream.'));

    socket.on('new_message', (data) => {
        const producerId = `producer-${data.producer}`;
        const topicId = `topic-${data.topic}`;
        const needsReposition = addNode(producerId, 'producer') || addNode(topicId, 'topic');
        drawTemporaryArrow(producerId, topicId, 'publish');
        if (needsReposition) {
            positionNodes();
            updateGraph();
        }
    });

    socket.on('new_consumption', (data) => {
        const topicId = `topic-${data.topic}`;
        const consumerId = `consumer-${data.consumer}`;
        const needsReposition = addNode(topicId, 'topic') || addNode(consumerId, 'consumer');
        drawTemporaryArrow(topicId, consumerId, 'consume');
        if (needsReposition) {
            positionNodes();
            updateGraph();
        }
    });

    socket.on('new_client', (data) => {
        const consumerId = `consumer-${data.consumer}`;
        const topicId = `topic-${data.topic}`;
        const needsReposition = addNode(consumerId, 'consumer') || addNode(topicId, 'topic');
        drawTemporaryArrow(topicId, consumerId, 'consume');
        if (needsReposition) {
            positionNodes();
            updateGraph();
        }
    });

    initializeGraph();
});