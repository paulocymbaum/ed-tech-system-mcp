import type { WorkflowTraceStep } from "../api/workflows";

export type NodeHistory = {
  worstStatus: WorkflowTraceStep["status"];
  maxAttempt: number;
  visitCount: number;
};

export type TraceSummary = {
  totalSteps: number;
  failedSteps: number;
  retrySteps: number;
  lastNodeId: string | null;
  hasIssues: boolean;
};

export type ContentRunMeta = {
  generationComplete?: boolean;
  lessonRetryCount?: number;
  quizRetryCount?: number;
  pblRetryCount?: number;
  planRetryCount?: number;
  workflowError?: string | null;
};

const STATUS_RANK: Record<WorkflowTraceStep["status"], number> = {
  ok: 1,
  retry: 2,
  failed: 3,
};

export function buildActiveNodeAttempts(trace: WorkflowTraceStep[]): Record<string, number> {
  const counts: Record<string, number> = {};
  for (const step of trace) {
    counts[step.node_id] = step.attempt;
  }
  return counts;
}

export function buildNodeHistory(trace: WorkflowTraceStep[]): Record<string, NodeHistory> {
  const history: Record<string, NodeHistory> = {};

  for (const step of trace) {
    const current = history[step.node_id];
    if (!current) {
      history[step.node_id] = {
        worstStatus: step.status,
        maxAttempt: step.attempt,
        visitCount: 1,
      };
      continue;
    }

    history[step.node_id] = {
      worstStatus:
        STATUS_RANK[step.status] > STATUS_RANK[current.worstStatus] ? step.status : current.worstStatus,
      maxAttempt: Math.max(current.maxAttempt, step.attempt),
      visitCount: current.visitCount + 1,
    };
  }

  return history;
}

export function traversedEdgeKeys(trace: WorkflowTraceStep[]): Set<string> {
  const keys = new Set<string>();
  for (let index = 1; index < trace.length; index += 1) {
    const previous = trace[index - 1];
    const current = trace[index];
    if (previous && current) {
      keys.add(`${previous.node_id}->${current.node_id}`);
    }
  }
  return keys;
}

export function activeTransitionKey(
  trace: WorkflowTraceStep[],
  activeStep: WorkflowTraceStep | null,
): string | null {
  if (!activeStep) {
    return null;
  }
  const index = trace.findIndex((step) => step.step === activeStep.step);
  if (index <= 0) {
    return null;
  }
  const previous = trace[index - 1];
  return `${previous.node_id}->${activeStep.node_id}`;
}

export function summarizeTrace(trace: WorkflowTraceStep[]): TraceSummary {
  const failedSteps = trace.filter((step) => step.status === "failed").length;
  const retrySteps = trace.filter((step) => step.status === "retry").length;
  const lastNodeId = trace.length > 0 ? (trace[trace.length - 1]?.node_id ?? null) : null;

  return {
    totalSteps: trace.length,
    failedSteps,
    retrySteps,
    lastNodeId,
    hasIssues: failedSteps > 0 || retrySteps > 0,
  };
}

export function totalRetryCount(meta: ContentRunMeta): number {
  return (meta.lessonRetryCount ?? 0) + (meta.quizRetryCount ?? 0) + (meta.pblRetryCount ?? 0);
}
