/**
 * activity-map.js
 * Activity Map visualization using D3.js with a 3-column layout.
 * Shows producers, topics, and consumers in vertical columns with animated arrows.
 */

document.addEventListener("DOMContentLoaded", () => {
    const socket = io();
    const svg = d3.select("#map-svg");
    const width = svg.node().getBoundingClientRect().width;
    const height = svg.node().getBoundingClientRect().height;

    // Create groups for organized rendering
    const g = svg.append("g");
    const linkGroup = g.append("g").attr("class", "links");
    const nodeGroup = g.append("g").attr("class", "nodes");
    const labelGroup = g.append("g").attr("class", "labels");

    // Column configuration
    const COLUMN_WIDTH = width / 3;
    const NODE_SPACING = 80;
    const COLUMN_PADDING = 60;
    const NODE_RADIUS = 25;

    // Data structures
    const nodeMap = new Map();
    const producers = [];
    const topics = [];
    const consumers = [];

    // --- Arrow markers definition ---
    svg.append("defs").selectAll("marker")
        .data(["publish", "consume"])
        .enter().append("marker")
        .attr("id", d => `arrow-${d}`)
        .attr("viewBox", "0 -5 10 10")
        .attr("refX", 20)
        .attr("refY", 0)
        .attr("markerWidth", 6)
        .attr("markerHeight", 6)
        .attr("orient", "auto")
        .append("path")
        .attr("d", "M0,-5L10,0L0,5")
        .style("fill", d => d === 'publish' ? '#28a745' : '#ffab40');

    // --- Column headers ---
    const headers = [
        { x: COLUMN_WIDTH / 2, y: 40, text: "Producers" },
        { x: COLUMN_WIDTH * 1.5, y: 40, text: "Topics" },
        { x: COLUMN_WIDTH * 2.5, y: 40, text: "Consumers" }
    ];

    labelGroup.selectAll(".column-header")
        .data(headers)
        .enter()
        .append("text")
        .attr("class", "column-header")
        .attr("x", d => d.x)
        .attr("y", d => d.y)
        .attr("text-anchor", "middle")
        .style("font-size", "20px")
        .style("font-weight", "600")
        .style("fill", "#61dafb")
        .text(d => d.text);

    // --- Helper functions ---

    function getColumnX(type) {
        if (type === 'producer') return COLUMN_WIDTH / 2;
        if (type === 'topic') return COLUMN_WIDTH * 1.5;
        return COLUMN_WIDTH * 2.5;
    }

    function getColumnNodes(type) {
        if (type === 'producer') return producers;
        if (type === 'topic') return topics;
        return consumers;
    }

    function calculateNodeY(index, totalNodes) {
        const availableHeight = height - COLUMN_PADDING * 2;
        const spacing = Math.min(NODE_SPACING, availableHeight / (totalNodes + 1));
        return COLUMN_PADDING + (index + 1) * spacing;
    }

    function addOrUpdateNode(id, type) {
        let node = nodeMap.get(id);
        if (!node) {
            const columnNodes = getColumnNodes(type);
            node = {
                id,
                name: id,
                type,
                x: getColumnX(type),
                y: 0 // Will be updated by repositionNodes
            };
            columnNodes.push(node);
            nodeMap.set(id, node);
            repositionNodes(type);
            return true;
        }
        return false;
    }

    function repositionNodes(type) {
        const columnNodes = getColumnNodes(type);
        columnNodes.forEach((node, i) => {
            node.y = calculateNodeY(i, columnNodes.length);
        });
    }

    function getConnectorPosition(node, targetNode) {
        const dx = targetNode.x - node.x;
        const dy = targetNode.y - node.y;
        const distance = Math.sqrt(dx * dx + dy * dy);

        if (distance === 0) return { x: node.x, y: node.y };

        return {
            x: node.x + (dx / distance) * NODE_RADIUS,
            y: node.y + (dy / distance) * NODE_RADIUS
        };
    }

    function updateGraph() {
        // Update all nodes
        const allNodes = [...producers, ...topics, ...consumers];

        const nodeSelection = nodeGroup.selectAll(".node")
            .data(allNodes, d => d.id);

        // Enter new nodes
        const nodeEnter = nodeSelection.enter()
            .append("g")
            .attr("class", d => `node ${d.type}`)
            .attr("transform", d => `translate(${d.x},${d.y})`);

        nodeEnter.append("circle")
            .attr("r", 0)
            .transition()
            .duration(500)
            .attr("r", NODE_RADIUS);

        nodeEnter.append("text")
            .attr("dy", ".35em")
            .attr("text-anchor", "middle")
            .style("font-size", "12px")
            .style("font-weight", "500")
            .text(d => d.name);

        // Update existing nodes
        nodeSelection
            .transition()
            .duration(500)
            .attr("transform", d => `translate(${d.x},${d.y})`);

        // Exit old nodes
        nodeSelection.exit()
            .transition()
            .duration(300)
            .attr("opacity", 0)
            .remove();
    }

    function drawTemporaryArrow(sourceId, targetId, type) {
        const sourceNode = nodeMap.get(sourceId);
        const targetNode = nodeMap.get(targetId);
        if (!sourceNode || !targetNode) return;

        // Blink effect on target node
        const targetNodeElement = nodeGroup.selectAll('.node')
            .filter(d => d.id === targetId);

        if (!targetNodeElement.empty()) {
            targetNodeElement.classed('blink', true);
            setTimeout(() => targetNodeElement.classed('blink', false), 500);
        }

        // Calculate connector positions
        const sourceConnector = getConnectorPosition(sourceNode, targetNode);
        const targetConnector = getConnectorPosition(targetNode, sourceNode);

        // Draw temporary arrow
        const arrow = linkGroup.append("line")
            .attr("class", `message-arrow ${type}`)
            .attr("marker-end", `url(#arrow-${type})`)
            .attr("x1", sourceConnector.x)
            .attr("y1", sourceConnector.y)
            .attr("x2", targetConnector.x)
            .attr("y2", targetConnector.y);

        // Draw temporary connectors
        const connectorGroup = linkGroup.append("g").attr("class", "temp-connectors");

        connectorGroup.append("circle")
            .attr("class", "connector")
            .attr("cx", sourceConnector.x)
            .attr("cy", sourceConnector.y);

        connectorGroup.append("circle")
            .attr("class", "connector")
            .attr("cx", targetConnector.x)
            .attr("cy", targetConnector.y);

        // Remove after animation
        setTimeout(() => {
            arrow.remove();
            connectorGroup.remove();
        }, 1000);
    }

    // --- WebSocket event handlers ---

    socket.on('connect', () => {
        console.log('Connected to activity stream.');
    });

    socket.on('new_message', (data) => {
        console.log('New Message:', data);
        const producerAdded = addOrUpdateNode(data.producer, 'producer');
        const topicAdded = addOrUpdateNode(data.topic, 'topic');
        if (producerAdded || topicAdded) updateGraph();
        drawTemporaryArrow(data.producer, data.topic, 'publish');
    });

    socket.on('new_consumption', (data) => {
        console.log('New Consumption:', data);
        const topicAdded = addOrUpdateNode(data.topic, 'topic');
        const consumerAdded = addOrUpdateNode(data.consumer, 'consumer');
        if (topicAdded || consumerAdded) updateGraph();
        drawTemporaryArrow(data.topic, data.consumer, 'consume');
    });

    socket.on('new_client', (data) => {
        console.log('New Client:', data);
        if (addOrUpdateNode(data.consumer, 'consumer')) {
            updateGraph();
        }
    });

    socket.on('consumed', (data) => {
        console.log('Consumed:', data);
        const topicAdded = addOrUpdateNode(data.topic, 'topic');
        const consumerAdded = addOrUpdateNode(data.consumer, 'consumer');
        if (topicAdded || consumerAdded) updateGraph();
        drawTemporaryArrow(data.topic, data.consumer, 'consume');
    });
});
