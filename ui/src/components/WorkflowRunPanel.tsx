import { useEffect, useState } from "react";

import {
  fetchRagValidationDocumentDefaults,
  runWorkflow,
  type ContentGenerationRunResult,
  type RagRetrievalRunResult,
  type RagValidationRunResult,
  type WorkflowGraph,
  type WorkflowTraceStep,
} from "../api/workflows";
import type { ContentRunMeta } from "../lib/traceAnalytics";
import type { RagWorkflowRunMeta } from "../lib/ragBenchmarks";

export type RagValidationRunMeta = RagWorkflowRunMeta & {
  validationPassed: boolean;
  validationErrors: string[];
  indexedChunkCount: number;
  chunkCount: number;
  documentTitle: string;
  documentSource: string;
  ragBenchmarks: Record<string, number>;
};

export type WorkflowRunOutcome = {
  trace: WorkflowTraceStep[];
  runMeta: ContentRunMeta | null;
  ragValidation: RagValidationRunMeta | null;
  ragRun: RagWorkflowRunMeta | null;
};

type WorkflowRunPanelProps = {
  workflow: WorkflowGraph;
  onRunComplete: (outcome: WorkflowRunOutcome) => void;
  onError: (message: string | null) => void;
};

function contentRunMeta(result: ContentGenerationRunResult): ContentRunMeta {
  return {
    generationComplete: result.generation_complete,
    lessonRetryCount: result.lesson_retry_count,
    quizRetryCount: result.quiz_retry_count,
    pblRetryCount: result.pbl_retry_count,
  };
}

function ragValidationRunMeta(result: RagValidationRunResult): RagValidationRunMeta {
  return {
    workflowId: "rag-validation",
    validationPassed: result.validation_passed,
    validationErrors: result.validation_errors,
    indexedChunkCount: result.indexed_chunk_count,
    chunkCount: result.chunk_count,
    documentTitle: result.document_title,
    documentSource: result.document_source,
    expectedPhrases: result.expected_phrases,
    matchedPhrases: result.matched_phrases,
    missingPhrases: result.missing_phrases,
    ragBenchmarks: result.rag_benchmarks ?? {},
    ragEvaluationContext: result.rag_evaluation_context ?? null,
  };
}

function ragRetrievalRunMeta(result: RagRetrievalRunResult): RagWorkflowRunMeta {
  return {
    workflowId: "rag-retrieval",
    ragEvaluationContext: result.rag_evaluation_context ?? null,
  };
}

export function WorkflowRunPanel({ workflow, onRunComplete, onError }: WorkflowRunPanelProps) {
  const [query, setQuery] = useState(
    workflow.id === "rag-validation"
      ? "How does photosynthesis convert light energy?"
      : "fractions",
  );
  const [maxResults, setMaxResults] = useState(5);
  const [maxWebResults, setMaxWebResults] = useState(5);
  const [maxVideoResults, setMaxVideoResults] = useState(3);
  const [topic, setTopic] = useState("fractions");
  const [gradeLevel, setGradeLevel] = useState("6th grade");
  const [retrieveLimit, setRetrieveLimit] = useState(4);
  const [rerankTopN, setRerankTopN] = useState(4);
  const [rerankEnabled, setRerankEnabled] = useState(false);
  const [retrievalMode, setRetrievalMode] = useState<"vector" | "hybrid">("vector");
  const [documentTitle, setDocumentTitle] = useState("RAG Validation Fixture — Photosynthesis");
  const [documentText, setDocumentText] = useState("");
  const [expectedPhrases, setExpectedPhrases] = useState("chlorophyll, light-dependent reactions, glucose");
  const [loadingDefaults, setLoadingDefaults] = useState(workflow.id === "rag-validation");
  const [running, setRunning] = useState(false);

  useEffect(() => {
    if (workflow.id !== "rag-validation") {
      setLoadingDefaults(false);
      return;
    }

    let cancelled = false;
    setLoadingDefaults(true);
    onError(null);

    void fetchRagValidationDocumentDefaults()
      .then((defaults) => {
        if (cancelled) {
          return;
        }
        setDocumentTitle(defaults.document_title);
        setDocumentText(defaults.document_text);
        setQuery(defaults.query);
        setExpectedPhrases(defaults.expected_phrases.join(", "));
      })
      .catch((loadError) => {
        if (!cancelled) {
          onError(loadError instanceof Error ? loadError.message : "Failed to load document defaults");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoadingDefaults(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [workflow.id, onError]);

  async function handleRun() {
    setRunning(true);
    onError(null);
    try {
      const parsedExpectedPhrases = expectedPhrases
        .split(",")
        .map((phrase) => phrase.trim())
        .filter(Boolean);

      const body: Record<string, string | number | boolean | string[]> =
        workflow.id === "content-generation"
          ? { topic, grade_level: gradeLevel }
          : workflow.id === "research-article"
            ? {
                query,
                max_web_results: maxWebResults,
                max_video_results: maxVideoResults,
              }
            : workflow.id === "youtube-search"
              ? { query, max_results: maxResults, language: "en", safe_search: true }
              : workflow.id === "rag-validation"
                ? {
                    query,
                    document_title: documentTitle,
                    document_text: documentText,
                    expected_phrases: parsedExpectedPhrases,
                    retrieval_mode: retrievalMode,
                    retrieve_limit: retrieveLimit,
                    rerank_top_n: rerankTopN,
                    rerank_enabled: rerankEnabled,
                  }
              : workflow.id === "rag-retrieval"
                ? {
                    query,
                    retrieval_mode: retrievalMode,
                    retrieve_limit: retrieveLimit,
                    rerank_top_n: rerankTopN,
                    rerank_enabled: rerankEnabled,
                  }
                : { query, max_results: maxResults };
      const result = await runWorkflow(workflow.id, body);
      onRunComplete({
        trace: result.trace ?? [],
        runMeta:
          workflow.id === "content-generation"
            ? contentRunMeta(result as ContentGenerationRunResult)
            : null,
        ragValidation:
          workflow.id === "rag-validation"
            ? ragValidationRunMeta(result as RagValidationRunResult)
            : null,
        ragRun:
          workflow.id === "rag-validation"
            ? ragValidationRunMeta(result as RagValidationRunResult)
            : workflow.id === "rag-retrieval"
              ? ragRetrievalRunMeta(result as RagRetrievalRunResult)
              : null,
      });
    } catch (runError) {
      onRunComplete({ trace: [], runMeta: null, ragValidation: null, ragRun: null });
      onError(runError instanceof Error ? runError.message : "Workflow run failed");
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="run-panel">
      <h3>Run workflow</h3>
      {workflow.id === "content-generation" ? (
        <div className="run-form">
          <label>
            Topic
            <input value={topic} onChange={(event) => setTopic(event.target.value)} />
          </label>
          <label>
            Grade level
            <input value={gradeLevel} onChange={(event) => setGradeLevel(event.target.value)} />
          </label>
        </div>
      ) : workflow.id === "research-article" ? (
        <div className="run-form">
          <label>
            Query
            <input value={query} onChange={(event) => setQuery(event.target.value)} />
          </label>
          <label>
            Max web results
            <input
              type="number"
              min={1}
              max={25}
              value={maxWebResults}
              onChange={(event) => setMaxWebResults(Number(event.target.value))}
            />
          </label>
          <label>
            Max video results
            <input
              type="number"
              min={1}
              max={25}
              value={maxVideoResults}
              onChange={(event) => setMaxVideoResults(Number(event.target.value))}
            />
          </label>
        </div>
      ) : workflow.id === "rag-retrieval" ? (
        <div className="run-form">
          <label>
            Query
            <input value={query} onChange={(event) => setQuery(event.target.value)} />
          </label>
          <label>
            Retrieval mode
            <select
              value={retrievalMode}
              onChange={(event) => setRetrievalMode(event.target.value as "vector" | "hybrid")}
            >
              <option value="vector">vector</option>
              <option value="hybrid">hybrid</option>
            </select>
          </label>
          <label>
            Retrieve limit
            <input
              type="number"
              min={1}
              max={100}
              value={retrieveLimit}
              onChange={(event) => setRetrieveLimit(Number(event.target.value))}
            />
          </label>
          <label>
            Rerank top n
            <input
              type="number"
              min={1}
              max={50}
              value={rerankTopN}
              disabled={!rerankEnabled}
              onChange={(event) => setRerankTopN(Number(event.target.value))}
            />
          </label>
          <label className="run-form-checkbox">
            <input
              type="checkbox"
              checked={rerankEnabled}
              onChange={(event) => setRerankEnabled(event.target.checked)}
            />
            Enable rerank
          </label>
          {rerankEnabled && (
            <p className="muted run-form-note">
              First rerank run downloads the cross-encoder model (~100MB) and can take 1–3 minutes.
              Later runs use the cached model. Watch API logs for progress.
            </p>
          )}
        </div>
      ) : workflow.id === "rag-validation" ? (
        <div className="run-form run-form--document">
          <p className="muted run-form-note">
            Edit the document below. The workflow runs <strong>load document</strong> then{" "}
            <strong>index document</strong> before retrieval.
          </p>
          <label>
            Document title
            <input value={documentTitle} onChange={(event) => setDocumentTitle(event.target.value)} />
          </label>
          <label className="run-form-textarea">
            Document text
            <textarea
              rows={12}
              value={documentText}
              onChange={(event) => setDocumentText(event.target.value)}
              disabled={loadingDefaults}
              placeholder={loadingDefaults ? "Loading default document…" : "Paste or edit markdown corpus"}
            />
          </label>
          <label>
            Expected phrases (comma-separated)
            <input value={expectedPhrases} onChange={(event) => setExpectedPhrases(event.target.value)} />
          </label>
          <label>
            Query
            <input value={query} onChange={(event) => setQuery(event.target.value)} />
          </label>
          <label>
            Retrieval mode
            <select
              value={retrievalMode}
              onChange={(event) => setRetrievalMode(event.target.value as "vector" | "hybrid")}
            >
              <option value="vector">vector</option>
              <option value="hybrid">hybrid</option>
            </select>
          </label>
          <label>
            Retrieve limit
            <input
              type="number"
              min={1}
              max={100}
              value={retrieveLimit}
              onChange={(event) => setRetrieveLimit(Number(event.target.value))}
            />
          </label>
          <label>
            Rerank top n
            <input
              type="number"
              min={1}
              max={50}
              value={rerankTopN}
              disabled={!rerankEnabled}
              onChange={(event) => setRerankTopN(Number(event.target.value))}
            />
          </label>
          <label className="run-form-checkbox">
            <input
              type="checkbox"
              checked={rerankEnabled}
              onChange={(event) => setRerankEnabled(event.target.checked)}
            />
            Enable rerank
          </label>
          {rerankEnabled && (
            <p className="muted run-form-note">
              First rerank run downloads the cross-encoder model (~100MB) and can take 1–3 minutes.
              Later runs use the cached model. Watch API logs for progress.
            </p>
          )}
        </div>
      ) : (
        <div className="run-form">
          <label>
            Query
            <input value={query} onChange={(event) => setQuery(event.target.value)} />
          </label>
          <label>
            Max results
            <input
              type="number"
              min={1}
              max={25}
              value={maxResults}
              onChange={(event) => setMaxResults(Number(event.target.value))}
            />
          </label>
        </div>
      )}
      <button
        type="button"
        className="run-button"
        disabled={running || (workflow.id === "rag-validation" && loadingDefaults)}
        onClick={() => void handleRun()}
      >
        {running ? "Running…" : "Run and capture trace"}
      </button>
    </div>
  );
}
