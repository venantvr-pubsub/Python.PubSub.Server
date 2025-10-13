/**
 * network-graph.js
 * Configures and initializes a graph with a "network" layout by roles.
 * Uses straight arrows with connector dots on nodes.
 */
// import { createGraph } from './common-graph.js';

document.addEventListener("DOMContentLoaded", () => {
    const NODE_RADIUS = 18;

    // Calculate connector position for a node
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

    // Network graph specific configuration
    const networkGraphConfig = {
        svgSelector: "#activity-svg",
        arrow: { refX: 20, orient: "auto" },

        createSimulation: (width, height) => {
            return d3.forceSimulation()
                .force("charge", d3.forceManyBody().strength(-400))
                .force("x", d3.forceX(width / 2).strength(0.05))
                .force("y", d3.forceY(height / 2).strength(0.05));
        },

        positionNodes: (nodes, width, height) => {
            const producers = nodes.filter(n => n.roles.includes('producer'));
            const consumers = nodes.filter(n => n.roles.includes('consumer'));
            const topics = nodes.filter(n => n.roles.includes('topic'));

            const horizontalRadius = width / 3.5;

            // Position producers on the left
            producers.forEach((node) => {
                if (node.fx == null) node.x = width / 2 - horizontalRadius;
            });

            // Position consumers on the right
            consumers.forEach((node) => {
                if (node.fx == null) node.x = width / 2 + horizontalRadius;
            });

            // Position topics in center (fixed position)
            const topicYStep = (height / 2) / (topics.length + 1);
            topics.forEach((node, i) => {
                node.fx = width / 2;
                node.fy = (height / 4) + (i + 1) * topicYStep;
            });
        },

        drawLink: (linkGroup, sourceNode, targetNode, type) => {
            // Calculate connector positions
            const sourceConnector = getConnectorPosition(sourceNode, targetNode);
            const targetConnector = getConnectorPosition(targetNode, sourceNode);

            // Draw the link line from connector to connector
            const link = linkGroup.append("line")
                .datum({ source: sourceNode, target: targetNode })
                .attr("class", `link ${type}`)
                .attr("marker-end", `url(#arrow-${type})`)
                .attr("x1", sourceConnector.x)
                .attr("y1", sourceConnector.y)
                .attr("x2", targetConnector.x)
                .attr("y2", targetConnector.y)
                .style("opacity", 1);

            // Draw connector dots
            const connectorGroup = linkGroup.append("g").attr("class", "connector-group");

            connectorGroup.append("circle")
                .attr("class", "connector")
                .attr("cx", sourceConnector.x)
                .attr("cy", sourceConnector.y);

            connectorGroup.append("circle")
                .attr("class", "connector")
                .attr("cx", targetConnector.x)
                .attr("cy", targetConnector.y);

            link.connectorGroup = connectorGroup;

            return link;
        },

        tickHandler: (nodeGroup, linkGroup) => {
            nodeGroup.selectAll('.node').attr("transform", d => `translate(${d.x},${d.y})`);

            // Update straight lines with connectors at each tick
            linkGroup.selectAll('line').each(function(d) {
                const sourceConnector = getConnectorPosition(d.source, d.target);
                const targetConnector = getConnectorPosition(d.target, d.source);

                d3.select(this)
                    .attr("x1", sourceConnector.x)
                    .attr("y1", sourceConnector.y)
                    .attr("x2", targetConnector.x)
                    .attr("y2", targetConnector.y);
            });

            // Update connector positions
            linkGroup.selectAll('.connector-group').each(function(d, i, nodes) {
                const lineData = d3.select(nodes[i].previousSibling).datum();
                if (lineData) {
                    const { source, target } = lineData;

                    const sourceConnector = getConnectorPosition(source, target);
                    const targetConnector = getConnectorPosition(target, source);

                    d3.select(this).selectAll('.connector')
                        .data([sourceConnector, targetConnector])
                        .attr("cx", d => d.x)
                        .attr("cy", d => d.y);
                }
            });
        }
    };

    // Create graph with its configuration
    createGraph(networkGraphConfig);
});