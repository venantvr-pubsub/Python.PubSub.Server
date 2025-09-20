document.addEventListener("DOMContentLoaded", () => {
    const socket = io();
    const producersCol = document.getElementById('producers-col');
    const topicsCol = document.getElementById('topics-col');
    const consumersCol = document.getElementById('consumers-col');
    const svg = document.getElementById('map-svg');

    const nodes = new Set();

    const drawNode = (name, type, column) => {
        const nodeId = `node-${type}-${name}`;
        if (!nodes.has(nodeId)) {
            nodes.add(nodeId);
            const nodeEl = document.createElement('div');
            nodeEl.id = nodeId;
            nodeEl.className = 'node';
            nodeEl.textContent = name;
            column.appendChild(nodeEl);
        }
        return nodeId;
    };

    const drawArrow = (startId, endId) => {
        const startEl = document.getElementById(startId);
        const endEl = document.getElementById(endId);
        if (!startEl || !endEl) return;

        const mapRect = svg.getBoundingClientRect();
        const startRect = startEl.getBoundingClientRect();
        const endRect = endEl.getBoundingClientRect();

        const startX = startRect.right - mapRect.left;
        const startY = startRect.top + startRect.height / 2 - mapRect.top;
        const endX = endRect.left - mapRect.left;
        const endY = endRect.top + endRect.height / 2 - mapRect.top;

        const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
        line.setAttribute('x1', startX);
        line.setAttribute('y1', startY);
        line.setAttribute('x2', endX);
        line.setAttribute('y2', endY);
        line.setAttribute('class', 'message-arrow');

        // Add arrowhead marker
        line.setAttribute('marker-end', 'url(#arrowhead)');

        svg.appendChild(line);

        setTimeout(() => {
            svg.removeChild(line);
        }, 1000); // Remove after 1 second animation
    };

    // Define arrowhead marker in SVG
    const defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
    const marker = document.createElementNS('http://www.w3.org/2000/svg', 'marker');
    marker.setAttribute('id', 'arrowhead');
    marker.setAttribute('viewBox', '0 0 10 10');
    marker.setAttribute('refX', '8');
    marker.setAttribute('refY', '5');
    marker.setAttribute('markerWidth', '6');
    marker.setAttribute('markerHeight', '6');
    marker.setAttribute('orient', 'auto-start-reverse');
    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    path.setAttribute('d', 'M 0 0 L 10 5 L 0 10 z');
    path.setAttribute('fill', '#ffab40');
    marker.appendChild(path);
    defs.appendChild(marker);
    svg.appendChild(defs);


    socket.on('connect', () => {
        console.log('Connected to activity stream.');
    });

    socket.on('new_message', (data) => {
        console.log('New Message:', data);
        const producerId = drawNode(data.producer, 'producer', producersCol);
        const topicId = drawNode(data.topic, 'topic', topicsCol);
        drawArrow(producerId, topicId);
    });

    socket.on('new_consumption', (data) => {
        console.log('New Consumption:', data);
        const topicId = drawNode(data.topic, 'topic', topicsCol);
        const consumerId = drawNode(data.consumer, 'consumer', consumersCol);
        drawArrow(topicId, consumerId);
    });

    socket.on('new_client', (data) => {
        // Pre-draw consumer nodes when they connect
        drawNode(data.consumer, 'consumer', consumersCol);
    });
});