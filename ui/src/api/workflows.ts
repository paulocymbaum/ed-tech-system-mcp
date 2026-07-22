export type GraphNode = {
  id: string;
  label: string;
  kind: "start" | "end" | "node";
};

export type GraphEdge = {
  source: string;
  target: string;
};

export type WorkflowGraph = {
  id: string;
  name: string;
  description: string;
  framework: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
};

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

export async function fetchWorkflows(): Promise<WorkflowGraph[]> {
  const response = await fetch(`${API_BASE}/api/workflows`);
  if (!response.ok) {
    throw new Error(`Failed to load workflows (${response.status})`);
  }
  return response.json() as Promise<WorkflowGraph[]>;
}

export async function fetchWorkflow(workflowId: string): Promise<WorkflowGraph> {
  const response = await fetch(`${API_BASE}/api/workflows/${workflowId}`);
  if (!response.ok) {
    throw new Error(`Failed to load workflow '${workflowId}' (${response.status})`);
  }
  return response.json() as Promise<WorkflowGraph>;
}
