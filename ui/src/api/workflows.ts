export type GraphNode = {
  id: string;
  label: string;
  kind: "start" | "end" | "node";
  x: number;
  y: number;
};

export type NodeGroup = {
  id: string;
  label: string;
  node_ids: string[];
  default_collapsed: boolean;
};

export type GraphEdge = {
  source: string;
  target: string;
  kind: "forward" | "retry" | "failure" | "async";
};

export type WorkflowGraph = {
  id: string;
  name: string;
  description: string;
  framework: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
  node_groups: NodeGroup[];
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
    input_tokens?: number;
    output_tokens?: number;
    total_tokens?: number;
    token_breakdown?: {
      system_prompt_tokens?: number;
      user_prompt_tokens?: number;
      raw_output_tokens?: number;
    };
  } | null;
};

export type ResearchArticleRunResult = {
  query: string;
  generation_complete: boolean;
  research_brief: string;
  web_result_count: number;
  video_count: number;
  web_results: string[];
  videos: Array<{
    title: string;
    channel: string;
    url: string;
    duration_seconds?: number | null;
    relevance_score?: number;
  }>;
  tool_calls: Array<Record<string, unknown>>;
  merged_context: string;
  article: string;
  trace: WorkflowTraceStep[];
};

export type TavilySearchRunResult = {
  query: string;
  result_count: number;
  results: string[];
  trace: WorkflowTraceStep[];
};

export type YouTubeSearchRunResult = {
  query: string;
  video_count: number;
  videos: Array<{
    title: string;
    channel: string;
    url: string;
    duration_seconds?: number | null;
    relevance_score?: number;
  }>;
  trace: WorkflowTraceStep[];
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

export type RagEvaluationContext = {
  retrieval_mode: "vector" | "hybrid";
  retrieve_limit: number;
  rerank_enabled: boolean;
  rerank_top_n: number;
  effective_k: number;
  score_kind: "cosine" | "rrf" | "reranker";
  chunk_size?: number | null;
  chunk_overlap?: number | null;
  indexed_chunk_count?: number | null;
};

export type RagRetrievalRunResult = {
  query: string;
  retrieval_mode: "vector" | "hybrid";
  retrieval_complete: boolean;
  chunk_count: number;
  merged_context: string;
  rag_evaluation_context: RagEvaluationContext | null;
  trace: WorkflowTraceStep[];
};

export type RagValidationRunResult = {
  query: string;
  retrieval_mode: "vector" | "hybrid";
  retrieval_complete: boolean;
  index_complete: boolean;
  indexed_chunk_count: number;
  document_title: string;
  document_source: string;
  validation_passed: boolean;
  validation_errors: string[];
  expected_phrases: string[];
  matched_phrases: string[];
  missing_phrases: string[];
  rag_benchmarks: Record<string, number>;
  rag_evaluation_context: RagEvaluationContext | null;
  chunk_count: number;
  merged_context: string;
  trace: WorkflowTraceStep[];
};

export type RagValidationDocumentDefaults = {
  document_title: string;
  document_text: string;
  query: string;
  expected_phrases: string[];
};

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

export async function fetchRagValidationDocumentDefaults(): Promise<RagValidationDocumentDefaults> {
  const response = await fetch(`${API_BASE}/api/workflows/rag-validation/document-defaults`);
  if (!response.ok) {
    throw new Error(`Failed to load RAG validation document defaults (${response.status})`);
  }
  return response.json() as Promise<RagValidationDocumentDefaults>;
}

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
  body: Record<string, string | number | boolean | string[]>,
): Promise<
  | TavilySearchRunResult
  | YouTubeSearchRunResult
  | ResearchArticleRunResult
  | ContentGenerationRunResult
  | RagRetrievalRunResult
  | RagValidationRunResult
> {
  const response = await fetch(`${API_BASE}/api/workflows/${workflowId}/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Workflow run failed (${response.status})`);
  }
  return response.json() as Promise<
    | TavilySearchRunResult
    | YouTubeSearchRunResult
    | ResearchArticleRunResult
    | ContentGenerationRunResult
    | RagRetrievalRunResult
    | RagValidationRunResult
  >;
}
