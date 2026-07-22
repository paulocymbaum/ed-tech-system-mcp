export type GraphNode = {
  id: string;
  label: string;
  kind: "start" | "end" | "node";
  x: number;
  y: number;
};

export type GraphEdge = {
  source: string;
  target: string;
  kind: "forward" | "retry" | "failure";
};

export type WorkflowGraph = {
  id: string;
  name: string;
  description: string;
  framework: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
};

export type WorkflowTraceStep = {
  step: number;
  node_id: string;
  status: "ok" | "failed" | "retry";
  attempt: number;
  validation_errors: string[];
  retry_counts: Record<string, number>;
  input_snapshot: Record<string, unknown>;
  output_update: Record<string, unknown>;
  llm_io: {
    model_name?: string;
    llm_complexity?: number;
    system_prompt?: string;
    user_prompt?: string;
    raw_output?: string;
  } | null;
};

export type DocumentVideoRunResult = {
  query: string;
  search_terms: string;
  document_count: number;
  video_count: number;
  trace: WorkflowTraceStep[];
};

export type ContentGenerationRunResult = {
  topic: string;
  grade_level: string;
  generation_complete: boolean;
  lesson_retry_count: number;
  quiz_retry_count: number;
  pbl_retry_count: number;
  trace: WorkflowTraceStep[];
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

export async function runWorkflow(
  workflowId: string,
  body: Record<string, string | number>,
): Promise<DocumentVideoRunResult | ContentGenerationRunResult> {
  const response = await fetch(`${API_BASE}/api/workflows/${workflowId}/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Workflow run failed (${response.status})`);
  }
  return response.json() as Promise<DocumentVideoRunResult | ContentGenerationRunResult>;
}
