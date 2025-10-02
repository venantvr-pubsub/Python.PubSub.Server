/**
 * network-graph.js
 * Configures and initializes a graph with a "network" layout by roles.
 */
// import { createGraph } from './common-graph.js';

document.addEventListener("DOMContentLoaded", () => {
    // Network graph specific configuration
    const networkGraphConfig = {
        svgSelector: "#activity-svg",
        arrow: { refX: 30, orient: "auto" },

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
            return linkGroup.append("line")
                .datum({ source: sourceNode, target: targetNode })
                .attr("class", `link ${type}`)
                .attr("marker-end", `url(#arrow-${type})`)
                .attr("x1", sourceNode.x)
                .attr("y1", sourceNode.y)
                .attr("x2", targetNode.x)
                .attr("y2", targetNode.y)
                .style("opacity", 1);
        },

        tickHandler: (nodeGroup, linkGroup) => {
            nodeGroup.selectAll('.node').attr("transform", d => `translate(${d.x},${d.y})`);
            // Update straight lines at each tick
            linkGroup.selectAll('line')
                .attr("x1", d => d.source.x)
                .attr("y1", d => d.source.y)
                .attr("x2", d => d.target.x)
                .attr("y2", d => d.target.y);
        }
    };

    // Create graph with its configuration
    createGraph(networkGraphConfig);
});