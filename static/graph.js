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

    // Simulation de forces D3
    const simulation = d3.forceSimulation()
        .force("link", d3.forceLink().id(d => d.id).distance(150))
        .force("charge", d3.forceManyBody().strength(-400))
        .force("center", d3.forceCenter(width / 2, height / 2));

    // --- Gestion des données du graphe ---
    let nodes = [];
    let links = [];
    const nodeMap = new Map(); // Pour garantir des nœuds singletons

    function getNodeType(id) {
        if (id.startsWith('producer-')) return 'producer';
        if (id.startsWith('topic-')) return 'topic';
        if (id.startsWith('consumer-')) return 'consumer';
    }

    // Fonction pour ajouter un nœud s'il n'existe pas
    function addNode(id, type) {
        if (!nodeMap.has(id)) {
            const newNode = { id, type, name: id.split('-').slice(1).join('-') };
            nodes.push(newNode);
            nodeMap.set(id, newNode);
        }
    }

    // Fonction pour ajouter un lien
    function addLink(sourceId, targetId, type) {
        // Évite les doublons
        const linkExists = links.some(l => l.source.id === sourceId && l.target.id === targetId);
        if (!linkExists) {
            links.push({ source: sourceId, target: targetId, type });
        }
        // Trouve et anime le lien correspondant
        const linkElement = linkGroup.selectAll(".link")
            .filter(d => d.source.id === sourceId && d.target.id === targetId);

        if (linkElement) {
            linkElement.classed("active", true);
            setTimeout(() => linkElement.classed("active", false), 1000);
        }
    }

    // --- Fonction de mise à jour du rendu ---
    function updateGraph() {
        // 1. Mise à jour des Nœuds (disques + texte)
        const node = nodeGroup.selectAll(".node")
            .data(nodes, d => d.id)
            .join(
                enter => {
                    const nodeEnter = enter.append("g")
                        .attr("class", d => `node ${d.type}`)
                        .call(drag(simulation)); // Ajoute le drag & drop

                    nodeEnter.append("circle")
                        .attr("r", radius);

                    // Connecteurs IN/OUT (ici visuels, non fonctionnels pour les liens)
                    nodeEnter.append("circle").attr("r", 5).attr("cx", -radius).attr("cy", 0).style("fill", "#ffab40"); // IN (orange)
                    nodeEnter.append("circle").attr("r", 5).attr("cx", radius).attr("cy", 0).style("fill", "#28a745"); // OUT (vert)

                    nodeEnter.append("text")
                        .attr("dy", ".35em")
                        .attr("x", 0)
                        .attr("y", radius + 15)
                        .text(d => d.name);

                    return nodeEnter;
                }
            );

        // 2. Mise à jour des Liens (lignes)
        const link = linkGroup.selectAll(".link")
            .data(links, d => `${d.source.id}-${d.target.id}`)
            .join("line")
            .attr("class", d => `link ${d.type}`)
            .attr("marker-end", d => `url(#arrow-${d.type})`);

        // 3. Relancer la simulation avec les nouvelles données
        simulation.nodes(nodes).on("tick", ticked);
        simulation.force("link").links(links);
        simulation.alpha(1).restart(); // "Réchauffe" la simulation

        function ticked() {
            link
                .attr("x1", d => d.source.x)
                .attr("y1", d => d.source.y)
                .attr("x2", d => d.target.x)
                .attr("y2", d => d.target.y);

            node
                .attr("transform", d => `translate(${d.x},${d.y})`);
        }
    }

    // --- Interactivité (Zoom et Drag) ---
    const zoom = d3.zoom().on("zoom", (event) => {
        g.attr("transform", event.transform);
    });
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
      return d3.drag()
          .on("start", dragstarted)
          .on("drag", dragged)
          .on("end", dragended);
    }

    // --- Initialisation du graphe ---
    async function initializeGraph() {
        const response = await fetch('/graph/state');
        const state = await response.json();

        state.producers.forEach(p => addNode(`producer-${p}`, 'producer'));
        state.topics.forEach(t => addNode(`topic-${t}`, 'topic'));
        state.consumers.forEach(c => addNode(`consumer-${c}`, 'consumer'));
        state.links.forEach(l => {
            const sourceId = `${getNodeType(l.source)}-${l.source}`;
            const targetId = `${getNodeType(l.target)}-${l.target}`;
            addLink(sourceId, targetId, l.type);
        });

        // Positionnement initial en cercle pour un démarrage propre
        const numNodes = nodes.length;
        const angleStep = (2 * Math.PI) / numNodes;
        nodes.forEach((node, i) => {
            node.x = width / 2 + (width / 3) * Math.cos(i * angleStep);
            node.y = height / 2 + (height / 3) * Math.sin(i * angleStep);
        });

        updateGraph();
    }

    // --- Connexion WebSocket ---
    socket.on('connect', () => {
        console.log('Connected to activity stream.');
    });

    socket.on('new_message', (data) => { // PUBLISH
        const producerId = `producer-${data.producer}`;
        const topicId = `topic-${data.topic}`;
        addNode(producerId, 'producer');
        addNode(topicId, 'topic');
        addLink(producerId, topicId, 'publish');
        updateGraph();
    });

    socket.on('new_consumption', (data) => { // CONSUME
        const topicId = `topic-${data.topic}`;
        const consumerId = `consumer-${data.consumer}`;
        addNode(topicId, 'topic');
        addNode(consumerId, 'consumer');
        addLink(topicId, consumerId, 'consume');
        updateGraph();
    });

    socket.on('new_client', (data) => { // SUBSCRIBE (crée le nœud en avance)
        const consumerId = `consumer-${data.consumer}`;
        const topicId = `topic-${data.topic}`;
        addNode(consumerId, 'consumer');
        addNode(topicId, 'topic');
        addLink(topicId, consumerId, 'consume');
        updateGraph();
    });

    initializeGraph();
});