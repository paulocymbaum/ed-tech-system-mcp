import { useCallback, useEffect, useMemo, useState } from "react";
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
import {
  collapseGraphView,
  compositeNodeId,
  initialCollapsedGroups,
  isCompositeNodeId,
  toggleCollapsedGroup,
} from "../lib/ragNodeGroups";
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
  memberNodeIds?: string[],
): WorkflowNodeData["status"] {
  const resolvedIds =
    isCompositeNodeId(nodeId) && memberNodeIds && memberNodeIds.length > 0
      ? memberNodeIds
      : [nodeId];

  for (const resolvedId of resolvedIds) {
    if (activeStep?.node_id === resolvedId) {
      if (activeStep.status === "failed") {
        return "failed";
      }
      if (activeStep.status === "retry" || activeNodeAttempts[resolvedId] > 1) {
        return "retry";
      }
      return "active";
    }
  }

  let worst: WorkflowNodeData["status"] = "idle";
  for (const resolvedId of resolvedIds) {
    const history = nodeHistory[resolvedId];
    if (!history) {
      continue;
    }
    if (history.worstStatus === "failed") {
      return "history-failed";
    }
    if (history.worstStatus === "retry" || history.maxAttempt > 1 || history.visitCount > 1) {
      worst = "history-retry";
      continue;
    }
    if (history.visitCount > 0) {
      worst = "visited";
    }
  }
  return worst;
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
  if (kind === "async") {
    return {
      stroke: active ? "#a78bfa" : traversed ? "#8b5cf6" : "#5b21b6",
      strokeDasharray: "8 4",
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

function edgeHandles(edge: GraphEdge): { sourceHandle?: string; targetHandle?: string } {
  if (edge.kind === "retry") {
    return { sourceHandle: "top-source", targetHandle: "top" };
  }
  if (edge.kind === "async" && edge.target.includes("youtube")) {
    return { sourceHandle: "right", targetHandle: "left" };
  }
  if (edge.kind === "async") {
    return { sourceHandle: "top-source", targetHandle: "top" };
  }
  return { sourceHandle: "right", targetHandle: "left" };
}

function buildNodes(
  graphNodes: GraphNode[],
  activeStep: WorkflowTraceStep | null,
  activeNodeAttempts: Record<string, number>,
  nodeHistory: Record<string, NodeHistory>,
  nodeGroups: WorkflowGraph["node_groups"],
  collapsedGroupIds: Set<string>,
  onToggleGroup: (groupId: string) => void,
): Node<WorkflowNodeData, "workflow">[] {
  const groupByCompositeId = new Map(
    nodeGroups.map((group) => [compositeNodeId(group.id), group]),
  );

  return graphNodes.map((node) => {
    const compositeGroup = groupByCompositeId.get(node.id);
    const memberNodeIds = compositeGroup?.node_ids;
    const status = nodeStatus(node.id, activeStep, activeNodeAttempts, nodeHistory, memberNodeIds);
    const history = compositeGroup
      ? compositeGroup.node_ids
          .map((nodeId) => nodeHistory[nodeId])
          .find((entry) => entry !== undefined)
      : nodeHistory[node.id];
    const attempt = compositeGroup
      ? Math.max(
          ...compositeGroup.node_ids.map((nodeId) =>
            activeStep?.node_id === nodeId ? activeNodeAttempts[nodeId] : (nodeHistory[nodeId]?.maxAttempt ?? 1),
          ),
        )
      : activeStep?.node_id === node.id
        ? activeNodeAttempts[node.id]
        : history?.maxAttempt;
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
        composite: Boolean(compositeGroup),
        groupId: compositeGroup?.id,
        expanded: compositeGroup ? !collapsedGroupIds.has(compositeGroup.id) : undefined,
        onToggleGroup: compositeGroup ? onToggleGroup : undefined,
      },
      position: { x: node.x, y: node.y },
      style: {
        width: compositeGroup ? NODE_WIDTH + 24 : NODE_WIDTH,
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
  const [collapsedGroupIds, setCollapsedGroupIds] = useState<Set<string>>(() =>
    initialCollapsedGroups(workflow.node_groups ?? []),
  );

  useEffect(() => {
    setCollapsedGroupIds(initialCollapsedGroups(workflow.node_groups ?? []));
  }, [workflow.id, workflow.node_groups]);

  const onToggleGroup = useCallback((groupId: string) => {
    setCollapsedGroupIds((current) => toggleCollapsedGroup(current, groupId));
  }, []);

  const { nodes: displayNodes, edges: displayEdges } = useMemo(
    () =>
      collapseGraphView(
        workflow.nodes,
        workflow.edges,
        workflow.node_groups ?? [],
        collapsedGroupIds,
      ),
    [workflow.nodes, workflow.edges, workflow.node_groups, collapsedGroupIds],
  );

  const nodeHistory = useMemo(() => buildNodeHistory(trace), [trace]);
  const traversedEdges = useMemo(() => traversedEdgeKeys(trace), [trace]);
  const activeEdgeKey = useMemo(() => activeTransitionKey(trace, activeStep), [trace, activeStep]);

  const nodes = useMemo(
    () =>
      buildNodes(
        displayNodes,
        activeStep,
        activeNodeAttempts,
        nodeHistory,
        workflow.node_groups ?? [],
        collapsedGroupIds,
        onToggleGroup,
      ),
    [
      displayNodes,
      activeStep,
      activeNodeAttempts,
      nodeHistory,
      workflow.node_groups,
      collapsedGroupIds,
      onToggleGroup,
    ],
  );

  const edges = useMemo<Edge[]>(
    () =>
      displayEdges.map((edge, index) => {
        const edgeKey = `${edge.source}->${edge.target}`;
        const isTraversed = traversedEdges.has(edgeKey);
        const isActive = activeEdgeKey === edgeKey;
        const emphasis = isActive ? "active" : isTraversed ? "traversed" : "idle";
        const styles = edgeStyle(edge.kind, emphasis);
        const handles = edgeHandles(edge);
        const label =
          edge.kind === "retry"
            ? "retry"
            : edge.kind === "failure"
              ? "give up"
              : edge.kind === "async"
                ? "async"
                : undefined;
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
    [displayEdges, traversedEdges, activeEdgeKey],
  );

  useEffect(() => {
    document.title = `${workflow.name} · Workflow UI`;
  }, [workflow.name]);

  const hasRagGroups = (workflow.node_groups ?? []).length > 0;

  return (
    <div className="graph-panel">
      {trace.length > 0 && (
        <div className="graph-legend">
          <span className="graph-legend__item graph-legend__item--visited">visited path</span>
          <span className="graph-legend__item graph-legend__item--async">parallel async tools</span>
          <span className="graph-legend__item graph-legend__item--retry">retry / re-run</span>
          <span className="graph-legend__item graph-legend__item--failed">validation failure</span>
        </div>
      )}
      {hasRagGroups && (
        <p className="graph-hint muted">
          Click grouped nodes to expand or collapse substeps. <strong>Document Pipeline</strong> loads and indexes
          your text; <strong>RAG Pipeline</strong> covers embed → retrieve → rerank → merge.
        </p>
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
