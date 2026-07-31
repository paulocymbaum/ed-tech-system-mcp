import type { GraphEdge, GraphNode, NodeGroup } from "../api/workflows";

export const RAG_PIPELINE_NODE_IDS = [
  "embed_query",
  "retrieve_chunks",
  "rerank_chunks",
  "merge_context",
] as const;

export function compositeNodeId(groupId: string): string {
  return `group:${groupId}`;
}

export function isCompositeNodeId(nodeId: string): boolean {
  return nodeId.startsWith("group:");
}

export function groupForNode(nodeId: string, groups: NodeGroup[]): NodeGroup | null {
  return groups.find((group) => group.node_ids.includes(nodeId)) ?? null;
}

export function initialCollapsedGroups(groups: NodeGroup[]): Set<string> {
  return new Set(groups.filter((group) => group.default_collapsed).map((group) => group.id));
}

export function toggleCollapsedGroup(collapsed: Set<string>, groupId: string): Set<string> {
  const next = new Set(collapsed);
  if (next.has(groupId)) {
    next.delete(groupId);
  } else {
    next.add(groupId);
  }
  return next;
}

export function collapseGraphView(
  nodes: GraphNode[],
  edges: GraphEdge[],
  groups: NodeGroup[],
  collapsedGroupIds: Set<string>,
): { nodes: GraphNode[]; edges: GraphEdge[] } {
  if (groups.length === 0 || collapsedGroupIds.size === 0) {
    return { nodes, edges };
  }

  const collapsedGroups = groups.filter((group) => collapsedGroupIds.has(group.id));
  if (collapsedGroups.length === 0) {
    return { nodes, edges };
  }

  const hiddenNodes = new Set<string>();
  const compositeNodes: GraphNode[] = [];

  for (const group of collapsedGroups) {
    const members = nodes.filter((node) => group.node_ids.includes(node.id));
    for (const member of members) {
      hiddenNodes.add(member.id);
    }
    if (members.length === 0) {
      continue;
    }
    const avgX = Math.round(members.reduce((sum, node) => sum + node.x, 0) / members.length);
    const avgY = Math.round(members.reduce((sum, node) => sum + node.y, 0) / members.length);
    compositeNodes.push({
      id: compositeNodeId(group.id),
      label: group.label,
      kind: "node",
      x: avgX,
      y: avgY,
    });
  }

  const visibleNodes = nodes.filter((node) => !hiddenNodes.has(node.id)).concat(compositeNodes);

  const nodeToComposite = new Map<string, string>();
  for (const group of collapsedGroups) {
    const compositeId = compositeNodeId(group.id);
    for (const nodeId of group.node_ids) {
      nodeToComposite.set(nodeId, compositeId);
    }
  }

  const remap = (nodeId: string): string => nodeToComposite.get(nodeId) ?? nodeId;

  const remappedEdges: GraphEdge[] = [];
  const seen = new Set<string>();

  for (const edge of edges) {
    const source = remap(edge.source);
    const target = remap(edge.target);
    if (source === target) {
      continue;
    }
    const key = `${source}->${target}:${edge.kind}`;
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    remappedEdges.push({ ...edge, source, target });
  }

  return { nodes: visibleNodes, edges: remappedEdges };
}

export type TraceSection =
  | { type: "step"; step: import("../api/workflows").WorkflowTraceStep; index: number }
  | {
      type: "group";
      group: NodeGroup;
      steps: Array<{ step: import("../api/workflows").WorkflowTraceStep; index: number }>;
    };

export function buildTraceSections(
  trace: import("../api/workflows").WorkflowTraceStep[],
  groups: NodeGroup[],
): TraceSection[] {
  if (groups.length === 0 || trace.length === 0) {
    return trace.map((step, index) => ({ type: "step", step, index }));
  }

  const nodeToGroup = new Map<string, NodeGroup>();
  for (const group of groups) {
    for (const nodeId of group.node_ids) {
      nodeToGroup.set(nodeId, group);
    }
  }

  const sections: TraceSection[] = [];
  let currentGroup: NodeGroup | null = null;
  let bufferedSteps: Array<{ step: import("../api/workflows").WorkflowTraceStep; index: number }> = [];

  const flushBuffer = () => {
    if (bufferedSteps.length === 0) {
      return;
    }
    if (currentGroup) {
      sections.push({ type: "group", group: currentGroup, steps: bufferedSteps });
    } else {
      for (const entry of bufferedSteps) {
        sections.push({ type: "step", step: entry.step, index: entry.index });
      }
    }
    bufferedSteps = [];
  };

  trace.forEach((step, index) => {
    const group = nodeToGroup.get(step.node_id) ?? null;
    if (group?.id === currentGroup?.id) {
      bufferedSteps.push({ step, index });
      return;
    }
    flushBuffer();
    currentGroup = group;
    bufferedSteps = [{ step, index }];
  });
  flushBuffer();

  return sections;
}
