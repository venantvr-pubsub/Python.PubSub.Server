document.addEventListener("DOMContentLoaded", () => {
    const socket = io();

    // --- Configuration D3 ---
    const svg = d3.select("#activity-svg");
    const width = svg.node().getBoundingClientRect().width;
    const height = svg.node().getBoundingClientRect().height;
    const radius = 20; // Rayon des disques

    // Conteneur principal pour le zoom et le pan
    const g = svg.append("g");

    // Groupes pour les liens (temporaires) et les nœuds (permanents)
    const linkGroup = g.append("g").attr("class", "links");
    const nodeGroup = g.append("g").attr("class", "nodes");

    // Définition des pointes de flèches
    svg.append("defs").selectAll("marker")
        .data(["publish", "consume"])
        .enter().append("marker")
        .attr("id", d => `arrow-${d}`)
        .attr("viewBox", "0 -5 10 10")
        .attr("refX", 30) // Distance par rapport au cercle
        .attr("refY", 0)
        .attr("markerWidth", 6)
        .attr("markerHeight", 6)
        .attr("orient", "auto")
        .append("path")
        .attr("d", "M0,-5L10,0L0,5")
        .attr("class", d => `arrow-${d}`)
        .style("fill", d => d === 'publish' ? '#28a745' : '#ffab40');

    // Simulation de forces D3 (sans force de lien permanente)
    const simulation = d3.forceSimulation()
        .force("charge", d3.forceManyBody().strength(-400))
        .force("x", d3.forceX(width / 2).strength(0.05))
        .force("y", d3.forceY(height / 2).strength(0.05))
        .on("tick", ticked); // L'événement 'tick' met à jour les positions

    // --- Gestion des données du graphe ---
    let nodes = [];
    const nodeMap = new Map(); // Pour garantir des nœuds singletons

    // Fonction pour ajouter un nœud s'il n'existe pas
    function addNode(id, type) {
        if (!nodeMap.has(id)) {
            const newNode = { id, type, name: id.split('-').slice(1).join('-') };
            nodes.push(newNode);
            nodeMap.set(id, newNode);
            return true; // Indique qu'un noeud a été ajouté
        }
        return false;
    }

    // ✨ --- NOUVELLE FONCTION POUR LES FLÈCHES TEMPORAIRES --- ✨
    function drawTemporaryArrow(sourceId, targetId, type) {
        const sourceNode = nodeMap.get(sourceId);
        const targetNode = nodeMap.get(targetId);

        if (!sourceNode || !targetNode) {
            console.warn("Cannot draw arrow, node not found.", { sourceId, targetId });
            return;
        }

        // Crée l'élément <line> pour la flèche
        const tempLink = linkGroup.append("line")
            .attr("class", `link ${type}`)
            .attr("marker-end", `url(#arrow-${type})`)
            .attr("x1", sourceNode.x)
            .attr("y1", sourceNode.y)
            .attr("x2", targetNode.x)
            .attr("y2", targetNode.y)
            .style("opacity", 1);

        // Fait disparaître la flèche après 2 secondes
        tempLink.transition()
            .duration(2000)
            .style("opacity", 0)
            .remove(); // Supprime l'élément du DOM à la fin de la transition
    }

    // --- Fonction de mise à jour du rendu ---
    function updateGraph() {
        // Met à jour uniquement les Nœuds
        nodeGroup.selectAll(".node")
            .data(nodes, d => d.id)
            .join(
                enter => {
                    const nodeEnter = enter.append("g")
                        .attr("class", d => `node ${d.type}`)
                        .call(drag(simulation));

                    nodeEnter.append("circle").attr("r", radius);
                    nodeEnter.append("circle").attr("r", 5).attr("cx", -radius).attr("cy", 0).style("fill", "#ffab40");
                    nodeEnter.append("circle").attr("r", 5).attr("cx", radius).attr("cy", 0).style("fill", "#28a745");
                    nodeEnter.append("text")
                        .attr("dy", ".35em")
                        .attr("x", 0)
                        .attr("y", radius + 15)
                        .text(d => d.name);

                    return nodeEnter;
                }
            );

        // Relance la simulation avec les nouveaux nœuds
        simulation.nodes(nodes);
        simulation.alpha(0.3).restart();
    }

    // Fonction appelée à chaque "tick" de la simulation pour mettre à jour les positions
    function ticked() {
        nodeGroup.selectAll('.node')
            .attr("transform", d => `translate(${d.x},${d.y})`);
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

    // --- Positionnement initial des nœuds ---
    function positionNodes() {
        const producers = nodes.filter(n => n.type === 'producer');
        const consumers = nodes.filter(n => n.type === 'consumer');
        const topics = nodes.filter(n => n.type === 'topic');

        const horizontalRadius = width / 3.5;
        const verticalRadius = height / 3.5;

        // Positionner les producteurs sur un arc à gauche
        const producerAngleStep = Math.PI / (producers.length + 1);
        producers.forEach((node, i) => {
            const angle = Math.PI / 2 + (i + 1) * producerAngleStep;
            if (node.fx == null) node.x = width / 2 - horizontalRadius * Math.sin(angle);
            if (node.fy == null) node.y = height / 2 - verticalRadius * Math.cos(angle);
        });

        // Positionner les consommateurs sur un arc à droite
        const consumerAngleStep = Math.PI / (consumers.length + 1);
        consumers.forEach((node, i) => {
            const angle = Math.PI / 2 + (i + 1) * consumerAngleStep;
            if (node.fx == null) node.x = width / 2 + horizontalRadius * Math.sin(angle);
            if (node.fy == null) node.y = height / 2 - verticalRadius * Math.cos(angle);
        });

        // Positionner les topics au centre et les fixer
        const topicYStep = (height / 2) / (topics.length + 1);
        topics.forEach((node, i) => {
            node.fx = width / 2;
            node.fy = (height / 4) + (i + 1) * topicYStep;
        });
    }

    // --- Initialisation du graphe (sans les liens) ---
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

    socket.on('new_message', (data) => { // PUBLISH
        const producerId = `producer-${data.producer}`;
        const topicId = `topic-${data.topic}`;
        const isNewProducer = addNode(producerId, 'producer');
        const isNewTopic = addNode(topicId, 'topic');

        drawTemporaryArrow(producerId, topicId, 'publish');

        if (isNewProducer || isNewTopic) {
            positionNodes();
            updateGraph();
        }
    });

    socket.on('new_consumption', (data) => { // CONSUME
        const topicId = `topic-${data.topic}`;
        const consumerId = `consumer-${data.consumer}`;
        const isNewTopic = addNode(topicId, 'topic');
        const isNewConsumer = addNode(consumerId, 'consumer');

        drawTemporaryArrow(topicId, consumerId, 'consume');

        if (isNewTopic || isNewConsumer) {
            positionNodes();
            updateGraph();
        }
    });

    socket.on('new_client', (data) => { // SUBSCRIBE
        const consumerId = `consumer-${data.consumer}`;
        const topicId = `topic-${data.topic}`;
        const isNewConsumer = addNode(consumerId, 'consumer');
        const isNewTopic = addNode(topicId, 'topic');

        drawTemporaryArrow(topicId, consumerId, 'consume');

        if (isNewConsumer || isNewTopic) {
            positionNodes();
            updateGraph();
        }
    });

    initializeGraph();
});