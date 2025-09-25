/**
 * circular-graph.js
 * Configure et initialise un graphe avec une disposition circulaire.
 */
// import { createGraph } from './common-graph.js';

document.addEventListener("DOMContentLoaded", () => {
    // Helper pour calculer le chemin courbé des flèches
    function calculateCurvedPath(source, target) {
        const radius = 20; // Le rayon des cercles
        const dx = target.x - source.x;
        const dy = target.y - source.y;
        const distance = Math.sqrt(dx * dx + dy * dy);

        if (distance === 0) return "";

        // Calcul du point d'arrivée sur le bord du cercle cible
        const targetX = target.x - (dx / distance) * radius;
        const targetY = target.y - (dy / distance) * radius;

        const newDx = targetX - source.x;
        const newDy = targetY - source.y;
        const newDr = Math.sqrt(newDx * newDx + newDy * newDy);

        return `M${source.x},${source.y}A${newDr},${newDr} 0 0,1 ${targetX},${targetY}`;
    }

    // Configuration spécifique au graphe circulaire
    const circularGraphConfig = {
        svgSelector: "#activity-svg",
        arrow: { refX: 2, orient: "auto-start-reverse" },

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
                // On fixe la position pour un cercle parfait
                node.fx = width / 2 + circleRadius * Math.cos(angle);
                node.fy = height / 2 + circleRadius * Math.sin(angle);
            });
        },

        drawLink: (linkGroup, sourceNode, targetNode, type) => {
            return linkGroup.append("path")
                .datum({ source: sourceNode, target: targetNode })
                .attr("class", `link ${type}`)
                .attr("marker-end", `url(#arrow-${type})`)
                .attr("d", calculateCurvedPath(sourceNode, targetNode));
        },

        tickHandler: (nodeGroup, linkGroup) => {
            nodeGroup.selectAll('.node').attr("transform", d => `translate(${d.x},${d.y})`);
            // Met à jour le chemin courbé à chaque tick
            linkGroup.selectAll('path').attr("d", d => calculateCurvedPath(d.source, d.target));
        }
    };

    // Création du graphe avec sa configuration
    createGraph(circularGraphConfig);
});