document.addEventListener("DOMContentLoaded", () => {
    const socket = io();

    // --- Configuration D3 ---
    const svg = d3.select("#activity-svg");
    const width = svg.node().getBoundingClientRect().width;
    const height = svg.node().getBoundingClientRect().height;
    const radius = 20; // Rayon des disques

    // Conteneur principal pour le zoom et le pan
    const g = svg.append("g");

    // Groupes pour les liens et les nœuds
    const linkGroup = g.append("g").attr("class", "links");
    const nodeGroup = g.append("g").attr("class", "nodes");

    // Définition des pointes de flèches
    svg.append("defs").selectAll("marker")
        .data(["publish", "consume", "consumed"])
        .enter().append("marker")
        .attr("id", d => `arrow-${d}`)
        .attr("viewBox", "0 -5 10 10")
        .attr("refX", 30)
        .attr("refY", 0)
        .attr("markerWidth", 6)
        .attr("markerHeight", 6)
        .attr("orient", "auto")
        .append("path")
        .attr("d", "M0,-5L10,0L0,5")
        .attr("class", d => `arrow-${d}`)
        .style("fill", d => d === 'publish' ? '#28a745' : d === 'consume' ? '#ffab40' : '#dc3545');

    // Simulation de forces D3
    const simulation = d3.forceSimulation()
        .force("charge", d3.forceManyBody().strength(-400))
        .force("x", d3.forceX(width / 2).strength(0.05))
        .force("y", d3.forceY(height / 2).strength(0.05))
        .on("tick", ticked);

    // --- Gestion des données du graphe ---
    let nodes = [];
    const nodeMap = new Map();

    /**
     * ✅ NOUVELLE FONCTION : Crée un nœud s'il n'existe pas,
     * ou lui ajoute un nouveau rôle s'il existe déjà.
     */
    function addOrUpdateNode(id, role) {
        let node = nodeMap.get(id);
        let isNewNode = false;

        if (!node) {
            // Le nœud n'existe pas, on le crée avec un tableau de rôles
            node = {id: id, name: id, roles: [role]};
            nodes.push(node);
            nodeMap.set(id, node);
            isNewNode = true;
        } else if (!node.roles.includes(role)) {
            // Le nœud existe mais n'a pas ce rôle, on l'ajoute
            node.roles.push(role);
        }
        return isNewNode; // On retourne true seulement si le nœud est vraiment nouveau
    }

    // Fonction pour dessiner les flèches temporaires (inchangée)
    function drawTemporaryArrow(sourceId, targetId, type) {
        const sourceNode = nodeMap.get(sourceId);
        const targetNode = nodeMap.get(targetId);

        if (!sourceNode || !targetNode) {
            console.warn("Cannot draw arrow, node not found.", {sourceId, targetId});
            return;
        }

        const tempLink = linkGroup.append("line")
            .datum({source: sourceNode, target: targetNode})
            .attr("class", `link ${type}`)
            .attr("marker-end", `url(#arrow-${type})`)
            .attr("x1", sourceNode.x)
            .attr("y1", sourceNode.y)
            .attr("x2", targetNode.x)
            .attr("y2", targetNode.y)
            .style("opacity", 1);

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
                        // ✨ MODIFICATION : Les classes CSS sont basées sur le tableau de rôles
                        .attr("class", d => `node ${d.roles.join(' ')}`)
                        .call(drag(simulation));

                    nodeEnter.append("circle").attr("r", radius);
                    nodeEnter.append("text")
                        .attr("dy", ".35em")
                        .attr("x", 0)
                        .attr("y", radius + 15)
                        .text(d => d.name); // Le nom est maintenant juste l'ID

                    return nodeEnter;
                },
                update =>
                    // On s'assure que les classes sont mises à jour si un rôle est ajouté
                    update.attr("class", d => `node ${d.roles.join(' ')}`)
            );

        simulation.nodes(nodes);
        simulation.alpha(0.3).restart();
    }

    // Fonction "tick" (inchangée)
    function ticked() {
        nodeGroup.selectAll('.node')
            .attr("transform", d => `translate(${d.x},${d.y})`);

        linkGroup.selectAll('line')
            .attr("x1", d => d.source.x)
            .attr("y1", d => d.source.y)
            .attr("x2", d => d.target.x)
            .attr("y2", d => d.target.y);
    }

    // --- Interactivité (Zoom et Drag) --- (inchangé)
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

    // --- Positionnement initial des nœuds ---
    function positionNodes() {
        // ✨ MODIFICATION : On filtre les nœuds en regardant dans le tableau `roles`
        const producers = nodes.filter(n => n.roles.includes('producer'));
        const consumers = nodes.filter(n => n.roles.includes('consumer'));
        const topics = nodes.filter(n => n.roles.includes('topic'));

        const horizontalRadius = width / 3.5;
        const verticalRadius = height / 3.5;

        // Positionner les producteurs
        const producerAngleStep = Math.PI / (producers.length + 1);
        producers.forEach((node, i) => {
            const angle = Math.PI / 2 + (i + 1) * producerAngleStep;
            if (node.fx == null) node.x = width / 2 - horizontalRadius * Math.sin(angle);
            if (node.fy == null) node.y = height / 2 - verticalRadius * Math.cos(angle);
        });

        // Positionner les consommateurs
        const consumerAngleStep = Math.PI / (consumers.length + 1);
        consumers.forEach((node, i) => {
            const angle = Math.PI / 2 + (i + 1) * consumerAngleStep;
            if (node.fx == null) node.x = width / 2 + horizontalRadius * Math.sin(angle);
            if (node.fy == null) node.y = height / 2 - verticalRadius * Math.cos(angle);
        });

        // Positionner les topics
        const topicYStep = (height / 2) / (topics.length + 1);
        topics.forEach((node, i) => {
            node.fx = width / 2;
            node.fy = (height / 4) + (i + 1) * topicYStep;
        });
    }

    // --- Initialisation du graphe ---
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

    // ✨ TOUS LES GESTIONNAIRES SONT MODIFIÉS CI-DESSOUS
    socket.on('new_message', (data) => {
        const producerId = data.producer;
        const topicId = data.topic;

        const isNewProducer = addOrUpdateNode(producerId, 'producer');
        const isNewTopic = addOrUpdateNode(topicId, 'topic');

        drawTemporaryArrow(producerId, topicId, 'publish');

        if (isNewProducer || isNewTopic) {
            positionNodes();
        }
        updateGraph(); // On met à jour pour afficher les nouveaux rôles éventuels
    });

    socket.on('new_consumption', (data) => {
        const topicId = data.topic;
        const consumerId = data.consumer;

        const isNewTopic = addOrUpdateNode(topicId, 'topic');
        const isNewConsumer = addOrUpdateNode(consumerId, 'consumer');

        drawTemporaryArrow(topicId, consumerId, 'consume');

        if (isNewTopic || isNewConsumer) {
            positionNodes();
        }
        updateGraph();
    });

    socket.on('new_client', (data) => {
        const topicId = data.topic;
        const consumerId = data.consumer;

        const isNewTopic = addOrUpdateNode(topicId, 'topic');
        const isNewConsumer = addOrUpdateNode(consumerId, 'consumer');

        drawTemporaryArrow(topicId, consumerId, 'consume');

        if (isNewTopic || isNewConsumer) {
            positionNodes();
        }
        updateGraph();
    });

    socket.on('consumed', (data) => {
        const topicId = data.topic;
        const consumerId = data.consumer;

        const isNewTopic = addOrUpdateNode(topicId, 'topic');
        const isNewConsumer = addOrUpdateNode(consumerId, 'consumer');

        drawTemporaryArrow(topicId, consumerId, 'consumed');

        if (isNewTopic || isNewConsumer) {
            positionNodes();
        }
        updateGraph();
    });

    initializeGraph();
});