import { useEffect, useMemo } from "react";
import {
  Background,
  Controls,
  MarkerType,
  MiniMap,
  ReactFlow,
  type Edge,
  type Node,
  type NodeTypes,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import type { WorkflowGraph, WorkflowTraceStep } from "../api/workflows";
import { WorkflowNode, type WorkflowNodeData } from "./WorkflowNode";

type WorkflowGraphViewProps = {
  workflow: WorkflowGraph;
  activeStep: WorkflowTraceStep | null;
  activeNodeAttempts: Record<string, number>;
};

const NODE_WIDTH = 180;
const NODE_HEIGHT = 56;

const nodeTypes = { workflow: WorkflowNode } satisfies NodeTypes;

type GraphNode = WorkflowGraph["nodes"][number];
type GraphEdge = WorkflowGraph["edges"][number];

function nodeStatus(
  nodeId: string,
  activeStep: WorkflowTraceStep | null,
  activeNodeAttempts: Record<string, number>,
): WorkflowNodeData["status"] {
  if (!activeStep || activeStep.node_id !== nodeId) {
    return "idle";
  }
  if (activeStep.status === "failed") {
    return "failed";
  }
  if (activeStep.status === "retry" || activeNodeAttempts[nodeId] > 1) {
    return "retry";
  }
  return "active";
}

function edgeStyle(kind: GraphEdge["kind"], isActive: boolean) {
  if (kind === "retry") {
    return {
      stroke: isActive ? "#fbbf24" : "#d97706",
      strokeDasharray: "6 4",
      strokeWidth: isActive ? 2.5 : 1.5,
    };
  }
  if (kind === "failure") {
    return {
      stroke: isActive ? "#f87171" : "#dc2626",
      strokeDasharray: "4 4",
      strokeWidth: isActive ? 2.5 : 1.5,
    };
  }
  return {
    stroke: isActive ? "#60a5fa" : "#94a3b8",
    strokeWidth: isActive ? 3 : 2,
  };
}

function edgeHandles(kind: GraphEdge["kind"]): { sourceHandle?: string; targetHandle?: string } {
  if (kind === "retry") {
    return { sourceHandle: "top-source", targetHandle: "top" };
  }
  return { sourceHandle: "right", targetHandle: "left" };
}

function buildNodes(
  graphNodes: GraphNode[],
  activeStep: WorkflowTraceStep | null,
  activeNodeAttempts: Record<string, number>,
): Node<WorkflowNodeData, "workflow">[] {
  return graphNodes.map((node) => {
    const status = nodeStatus(node.id, activeStep, activeNodeAttempts);
    const attempt = activeNodeAttempts[node.id] ?? 0;
    const label =
      attempt > 1 && (activeStep?.node_id === node.id || status === "retry")
        ? `${node.label} (#${attempt})`
        : node.label;

    return {
      id: node.id,
      type: "workflow",
      data: {
        label,
        kind: node.kind,
        status,
      },
      position: { x: node.x, y: node.y },
      style: {
        width: NODE_WIDTH,
        height: NODE_HEIGHT,
      },
    };
  });
}

export function WorkflowGraphView({
  workflow,
  activeStep,
  activeNodeAttempts,
}: WorkflowGraphViewProps) {
  const nodes = useMemo(
    () => buildNodes(workflow.nodes, activeStep, activeNodeAttempts),
    [workflow.nodes, activeStep, activeNodeAttempts],
  );

  const edges = useMemo<Edge[]>(
    () =>
      workflow.edges.map((edge, index) => {
        const isActive =
          activeStep !== null &&
          activeStep.node_id === edge.target &&
          (edge.kind === "forward" || edge.kind === "retry" || edge.kind === "failure");
        const styles = edgeStyle(edge.kind, isActive);
        const handles = edgeHandles(edge.kind);
        const label =
          edge.kind === "retry" ? "retry" : edge.kind === "failure" ? "give up" : undefined;
        return {
          id: `${edge.source}-${edge.target}-${index}`,
          source: edge.source,
          target: edge.target,
          sourceHandle: handles.sourceHandle,
          targetHandle: handles.targetHandle,
          animated: isActive,
          label,
          labelStyle: { fill: "#f8fafc", fontSize: 11, fontWeight: 600 },
          labelBgStyle: { fill: "#1e293b", fillOpacity: 0.95 },
          labelBgPadding: [6, 4] as [number, number],
          labelBgBorderRadius: 4,
          markerEnd: { type: MarkerType.ArrowClosed, color: styles.stroke, width: 20, height: 20 },
          style: styles,
          zIndex: 1,
        };
      }),
    [workflow.edges, activeStep],
  );

  useEffect(() => {
    document.title = `${workflow.name} · Workflow UI`;
  }, [workflow.name]);

  return (
    <div className="graph-panel">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        nodesDraggable={false}
        nodesConnectable={false}
        colorMode="dark"
      >
        <Background gap={18} color="#334155" />
        <MiniMap pannable zoomable nodeColor="#1e293b" maskColor="rgba(2, 6, 23, 0.75)" />
        <Controls />
      </ReactFlow>
    </div>
  );
}
