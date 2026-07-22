import { useEffect, useMemo } from "react";
import {
  Background,
  Controls,
  MarkerType,
  MiniMap,
  ReactFlow,
  type Edge,
  type Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import type { WorkflowGraph } from "../api/workflows";

type WorkflowGraphViewProps = {
  workflow: WorkflowGraph;
};

const NODE_WIDTH = 180;
const NODE_HEIGHT = 56;
const COLUMN_GAP = 120;

function nodeStyle(kind: GraphNode["kind"]) {
  if (kind === "start") {
    return { background: "#14532d", border: "1px solid #22c55e", color: "#ecfdf5" };
  }
  if (kind === "end") {
    return { background: "#7f1d1d", border: "1px solid #ef4444", color: "#fef2f2" };
  }
  return { background: "#1e293b", border: "1px solid #38bdf8", color: "#e2e8f0" };
}

type GraphNode = WorkflowGraph["nodes"][number];

function layoutNodes(graphNodes: GraphNode[], edges: WorkflowGraph["edges"]): Node[] {
  const order = topologicalOrder(graphNodes, edges);
  const positions = new Map<string, { x: number; y: number }>();

  order.forEach((nodeId, index) => {
    positions.set(nodeId, { x: index * (NODE_WIDTH + COLUMN_GAP), y: 80 });
  });

  return graphNodes.map((node) => ({
    id: node.id,
    data: { label: node.label },
    position: positions.get(node.id) ?? { x: 0, y: 0 },
    style: {
      width: NODE_WIDTH,
      height: NODE_HEIGHT,
      borderRadius: node.kind === "node" ? 12 : 999,
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      fontSize: 13,
      fontWeight: 600,
      ...nodeStyle(node.kind),
    },
  }));
}

function topologicalOrder(
  graphNodes: GraphNode[],
  edges: WorkflowGraph["edges"],
): string[] {
  const ids = graphNodes.map((node) => node.id);
  const incoming = new Map(ids.map((id) => [id, 0]));
  const adjacency = new Map(ids.map((id) => [id, [] as string[]]));

  for (const edge of edges) {
    adjacency.get(edge.source)?.push(edge.target);
    incoming.set(edge.target, (incoming.get(edge.target) ?? 0) + 1);
  }

  const queue = ids.filter((id) => (incoming.get(id) ?? 0) === 0);
  const ordered: string[] = [];

  while (queue.length > 0) {
    const current = queue.shift();
    if (!current) {
      continue;
    }
    ordered.push(current);
    for (const next of adjacency.get(current) ?? []) {
      const nextCount = (incoming.get(next) ?? 0) - 1;
      incoming.set(next, nextCount);
      if (nextCount === 0) {
        queue.push(next);
      }
    }
  }

  return ordered.length > 0 ? ordered : ids;
}

export function WorkflowGraphView({ workflow }: WorkflowGraphViewProps) {
  const nodes = useMemo(
    () => layoutNodes(workflow.nodes, workflow.edges),
    [workflow.nodes, workflow.edges],
  );

  const edges = useMemo<Edge[]>(
    () =>
      workflow.edges.map((edge, index) => ({
        id: `${edge.source}-${edge.target}-${index}`,
        source: edge.source,
        target: edge.target,
        animated: true,
        markerEnd: { type: MarkerType.ArrowClosed, color: "#94a3b8" },
        style: { stroke: "#94a3b8" },
      })),
    [workflow.edges],
  );

  useEffect(() => {
    document.title = `${workflow.name} · Workflow UI`;
  }, [workflow.name]);

  return (
    <div className="graph-panel">
      <ReactFlow nodes={nodes} edges={edges} fitView nodesDraggable={false} nodesConnectable={false}>
        <Background gap={18} color="#334155" />
        <MiniMap pannable zoomable />
        <Controls />
      </ReactFlow>
    </div>
  );
}
