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
import {
  activeTransitionKey,
  buildNodeHistory,
  traversedEdgeKeys,
  type NodeHistory,
} from "../lib/traceAnalytics";
import { WorkflowNode, type WorkflowNodeData } from "./WorkflowNode";

type WorkflowGraphViewProps = {
  workflow: WorkflowGraph;
  trace: WorkflowTraceStep[];
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
  nodeHistory: Record<string, NodeHistory>,
): WorkflowNodeData["status"] {
  if (activeStep?.node_id === nodeId) {
    if (activeStep.status === "failed") {
      return "failed";
    }
    if (activeStep.status === "retry" || activeNodeAttempts[nodeId] > 1) {
      return "retry";
    }
    return "active";
  }

  const history = nodeHistory[nodeId];
  if (!history) {
    return "idle";
  }
  if (history.worstStatus === "failed") {
    return "history-failed";
  }
  if (history.worstStatus === "retry" || history.maxAttempt > 1 || history.visitCount > 1) {
    return "history-retry";
  }
  if (history.visitCount > 0) {
    return "visited";
  }
  return "idle";
}

function edgeStyle(kind: GraphEdge["kind"], emphasis: "idle" | "traversed" | "active") {
  const active = emphasis === "active";
  const traversed = emphasis === "traversed";

  if (kind === "retry") {
    return {
      stroke: active ? "#fbbf24" : traversed ? "#f59e0b" : "#92400e",
      strokeDasharray: "6 4",
      strokeWidth: active ? 3 : traversed ? 2.5 : 1.5,
      opacity: traversed || active ? 1 : 0.45,
    };
  }
  if (kind === "failure") {
    return {
      stroke: active ? "#f87171" : traversed ? "#ef4444" : "#991b1b",
      strokeDasharray: "4 4",
      strokeWidth: active ? 3 : traversed ? 2.5 : 1.5,
      opacity: traversed || active ? 1 : 0.45,
    };
  }
  return {
    stroke: active ? "#60a5fa" : traversed ? "#38bdf8" : "#64748b",
    strokeWidth: active ? 3 : traversed ? 2.5 : 2,
    opacity: traversed || active ? 1 : 0.35,
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
  nodeHistory: Record<string, NodeHistory>,
): Node<WorkflowNodeData, "workflow">[] {
  return graphNodes.map((node) => {
    const status = nodeStatus(node.id, activeStep, activeNodeAttempts, nodeHistory);
    const history = nodeHistory[node.id];
    const attempt = activeStep?.node_id === node.id ? activeNodeAttempts[node.id] : history?.maxAttempt;
    const label =
      attempt && attempt > 1
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
  trace,
  activeStep,
  activeNodeAttempts,
}: WorkflowGraphViewProps) {
  const nodeHistory = useMemo(() => buildNodeHistory(trace), [trace]);
  const traversedEdges = useMemo(() => traversedEdgeKeys(trace), [trace]);
  const activeEdgeKey = useMemo(() => activeTransitionKey(trace, activeStep), [trace, activeStep]);

  const nodes = useMemo(
    () => buildNodes(workflow.nodes, activeStep, activeNodeAttempts, nodeHistory),
    [workflow.nodes, activeStep, activeNodeAttempts, nodeHistory],
  );

  const edges = useMemo<Edge[]>(
    () =>
      workflow.edges.map((edge, index) => {
        const edgeKey = `${edge.source}->${edge.target}`;
        const isTraversed = traversedEdges.has(edgeKey);
        const isActive = activeEdgeKey === edgeKey;
        const emphasis = isActive ? "active" : isTraversed ? "traversed" : "idle";
        const styles = edgeStyle(edge.kind, emphasis);
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
          zIndex: isActive ? 3 : isTraversed ? 2 : 1,
        };
      }),
    [workflow.edges, traversedEdges, activeEdgeKey],
  );

  useEffect(() => {
    document.title = `${workflow.name} · Workflow UI`;
  }, [workflow.name]);

  return (
    <div className="graph-panel">
      {trace.length > 0 && (
        <div className="graph-legend">
          <span className="graph-legend__item graph-legend__item--visited">visited path</span>
          <span className="graph-legend__item graph-legend__item--retry">retry / re-run</span>
          <span className="graph-legend__item graph-legend__item--failed">validation failure</span>
        </div>
      )}
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
