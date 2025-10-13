/**
 * circular-graph.js
 * Configures and initializes a graph with a circular layout.
 * Uses straight arrows with connector dots on nodes.
 */
// import { createGraph } from './common-graph.js';

document.addEventListener("DOMContentLoaded", () => {
    const NODE_RADIUS = 20;

    // Helper to calculate straight arrow paths with connectors
    function calculateStraightPath(source, target) {
        const dx = target.x - source.x;
        const dy = target.y - source.y;
        const distance = Math.sqrt(dx * dx + dy * dy);

        if (distance === 0) return "";

        // Calculate connector points on circle edges
        const sourceConnectorX = source.x + (dx / distance) * NODE_RADIUS;
        const sourceConnectorY = source.y + (dy / distance) * NODE_RADIUS;
        const targetConnectorX = target.x - (dx / distance) * NODE_RADIUS;
        const targetConnectorY = target.y - (dy / distance) * NODE_RADIUS;

        // Draw straight line from source connector to target connector
        return `M${sourceConnectorX},${sourceConnectorY}L${targetConnectorX},${targetConnectorY}`;
    }

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

    // Circular graph specific configuration
    const circularGraphConfig = {
        svgSelector: "#activity-svg",
        arrow: { refX: 20, orient: "auto" },

        createSimulation: (width, height) => {
            return d3.forceSimulation()
                .force("charge", d3.forceManyBody().strength(-200))
                .force("center", d3.forceCenter(width / 2, height / 2));
        },

        positionNodes: (nodes, width, height) => {
            const numNodes = nodes.length;
            if (numNodes === 0) return;
            const angleStep = (2 * Math.PI) / numNodes;
            const circleRadius = Math.min(width, height) / 3;

            nodes.forEach((node, i) => {
                const angle = i * angleStep;
                // Fix position for a perfect circle
                node.fx = width / 2 + circleRadius * Math.cos(angle);
                node.fy = height / 2 + circleRadius * Math.sin(angle);
            });
        },

        drawLink: (linkGroup, sourceNode, targetNode, type) => {
            // Draw the straight link line
            const link = linkGroup.append("path")
                .datum({ source: sourceNode, target: targetNode })
                .attr("class", `link ${type}`)
                .attr("marker-end", `url(#arrow-${type})`)
                .attr("d", calculateStraightPath(sourceNode, targetNode));

            // Draw connector dots
            const connectorGroup = linkGroup.append("g").attr("class", "connector-group");

            // Source connector
            const sourceConnector = getConnectorPosition(sourceNode, targetNode);
            connectorGroup.append("circle")
                .attr("class", "connector")
                .attr("cx", sourceConnector.x)
                .attr("cy", sourceConnector.y);

            // Target connector
            const targetConnector = getConnectorPosition(targetNode, sourceNode);
            connectorGroup.append("circle")
                .attr("class", "connector")
                .attr("cx", targetConnector.x)
                .attr("cy", targetConnector.y);

            // Store connector group reference for cleanup
            link.connectorGroup = connectorGroup;

            return link;
        },

        tickHandler: (nodeGroup, linkGroup) => {
            nodeGroup.selectAll('.node').attr("transform", d => `translate(${d.x},${d.y})`);

            // Update straight paths at each tick
            linkGroup.selectAll('path').attr("d", d => calculateStraightPath(d.source, d.target));

            // Update connector positions
            linkGroup.selectAll('.connector-group').each(function(d, i, nodes) {
                const pathData = d3.select(nodes[i].previousSibling).datum();
                if (pathData) {
                    const { source, target } = pathData;

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
    createGraph(circularGraphConfig);
});