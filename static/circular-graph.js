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
        .data(["publish", "consume", "consumed"])
        .enter().append("marker")
        .attr("id", d => `arrow-${d}`)
        .attr("viewBox", "0 -5 10 10")
        .attr("refX", 2)
        .attr("refY", 0)
        .attr("markerWidth", 6)
        .attr("markerHeight", 6)
        .attr("orient", "auto-start-reverse")
        .append("path")
        .attr("d", "M0,-5L10,0L0,5")
        .style("fill", d => d === 'publish' ? '#28a745' : d === 'consume' ? '#ffab40' : '#dc3545');

    // Simulation de forces D3
    const simulation = d3.forceSimulation()
        .force("charge", d3.forceManyBody().strength(-200))
        .force("center", d3.forceCenter(width / 2, height / 2))
        .on("tick", ticked);

    // --- Gestion des données du graphe ---
    let nodes = [];
    const nodeMap = new Map();

    /**
     * ✅ FONCTION MODIFIÉE : Gère les nœuds avec un tableau de rôles, sans préfixes.
     */
    function addOrUpdateNode(id, role) {
        let node = nodeMap.get(id);
        let isNewNode = false;

        if (!node) {
            // Le nœud n'existe pas, on le crée
            node = { id: id, name: id, roles: [role] };
            nodes.push(node);
            nodeMap.set(id, node);
            isNewNode = true;
        } else if (!node.roles.includes(role)) {
            // Le nœud existe mais n'a pas ce rôle, on l'ajoute
            node.roles.push(role);
        }
        return isNewNode; // Retourne true si un nœud a été physiquement ajouté
    }

    // Fonction pour calculer le chemin (inchangée)
    function calculateCurvedPath(source, target) {
        const dx = target.x - source.x;
        const dy = target.y - source.y;
        const distance = Math.sqrt(dx * dx + dy * dy);

        if (distance === 0) return "";

        const targetX = target.x - (dx / distance) * radius;
        const targetY = target.y - (dy / distance) * radius;
        const newDx = targetX - source.x;
        const newDy = targetY - source.y;
        const newDr = Math.sqrt(newDx * newDx + newDy * newDy);

        return `M${source.x},${source.y}A${newDr},${newDr} 0 0,1 ${targetX},${targetY}`;
    }

    // Fonction pour dessiner les flèches (inchangée, elle utilise déjà les ID fournis)
    function drawTemporaryArrow(sourceId, targetId, type) {
        const sourceNode = nodeMap.get(sourceId);
        const targetNode = nodeMap.get(targetId);
        if (!sourceNode || !targetNode) return;

        const tempLink = linkGroup.append("path")
            .datum({source: sourceNode, target: targetNode})
            .attr("class", `link ${type}`)
            .attr("marker-end", `url(#arrow-${type})`)
            .attr("d", calculateCurvedPath(sourceNode, targetNode));

        tempLink.transition()
            .duration(2000)
            .style("opacity", 0)
            .remove();
    }

    // Fonction de mise à jour du rendu
    function updateGraph() {
        nodeGroup.selectAll(".node")
            .data(nodes, d => d.id)
            .join(
                enter => {
                    const nodeEnter = enter.append("g")
                        // ✨ MODIFICATION : Les classes sont basées sur le tableau de rôles
                        .attr("class", d => `node ${d.roles.join(' ')}`)
                        .call(drag(simulation));
                    nodeEnter.append("circle").attr("r", radius);
                    nodeEnter.append("text").attr("dy", ".35em").attr("y", radius + 15).text(d => d.name);
                    return nodeEnter;
                },
                // On met à jour les classes si un rôle est ajouté à un nœud existant
                update => update.attr("class", d => `node ${d.roles.join(' ')}`)
            );
        simulation.nodes(nodes);
        simulation.alpha(0.3).restart();
    }

    // Fonction "tick" (inchangée)
    function ticked() {
        nodeGroup.selectAll('.node').attr("transform", d => `translate(${d.x},${d.y})`);
        linkGroup.selectAll('path').attr("d", d => calculateCurvedPath(d.source, d.target));
    }

    // Interactivité (inchangée)
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

    // Positionnement des nœuds (inchangé, votre nouvelle logique est conservée)
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

    // Initialisation du graphe
    async function initializeGraph() {
        const response = await fetch('/graph/state');
        const state = await response.json();

        // ✨ MODIFICATION : On utilise la nouvelle fonction sans préfixes
        state.producers.forEach(p => addOrUpdateNode(p, 'producer'));
        state.topics.forEach(t => addOrUpdateNode(t, 'topic'));
        state.consumers.forEach(c => addOrUpdateNode(c, 'consumer'));

        positionNodes();
        updateGraph();
    }

    // --- Connexion WebSocket ---
    socket.on('connect', () => console.log('Connected to activity stream.'));

    // ✨ MODIFICATION : Tous les gestionnaires WebSocket utilisent les ID bruts
    socket.on('new_message', (data) => {
        const producerId = data.producer;
        const topicId = data.topic;

        const needsReposition = addOrUpdateNode(producerId, 'producer') || addOrUpdateNode(topicId, 'topic');
        drawTemporaryArrow(producerId, topicId, 'publish');

        if (needsReposition) {
            positionNodes();
        }
        updateGraph(); // On met à jour pour refléter les changements de rôles
    });

    socket.on('new_consumption', (data) => {
        const topicId = data.topic;
        const consumerId = data.consumer;

        const needsReposition = addOrUpdateNode(topicId, 'topic') || addOrUpdateNode(consumerId, 'consumer');
        drawTemporaryArrow(topicId, consumerId, 'consume');

        if (needsReposition) {
            positionNodes();
        }
        updateGraph();
    });

    socket.on('new_client', (data) => {
        const consumerId = data.consumer;
        const topicId = data.topic;

        const needsReposition = addOrUpdateNode(consumerId, 'consumer') || addOrUpdateNode(topicId, 'topic');
        drawTemporaryArrow(topicId, consumerId, 'consume');

        if (needsReposition) {
            positionNodes();
        }
        updateGraph();
    });

    socket.on('consumed', (data) => {
        const topicId = data.topic;
        const consumerId = data.consumer;

        const needsReposition = addOrUpdateNode(topicId, 'topic') || addOrUpdateNode(consumerId, 'consumer');
        drawTemporaryArrow(topicId, consumerId, 'consumed');

        if (needsReposition) {
            positionNodes();
        }
        updateGraph();
    });

    initializeGraph();
});