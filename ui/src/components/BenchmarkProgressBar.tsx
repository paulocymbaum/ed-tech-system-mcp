import type { BenchmarkStage, OptimizationStage } from "../api/benchmarks";

type BenchmarkProgressBarProps = {
  progress: number;
  stage: BenchmarkStage | OptimizationStage;
  message: string;
  running: boolean;
  error?: string | null;
};

const STAGE_LABELS: Record<BenchmarkStage | OptimizationStage, string> = {
  indexing: "Indexing",
  embedding: "Embedding",
  retrieving: "Retrieving",
  validating: "Validating",
  baseline: "Baseline",
  searching: "Searching",
  saving: "Saving",
  after: "After",
  complete: "Complete",
  error: "Error",
};

export function BenchmarkProgressBar({
  progress,
  stage,
  message,
  running,
  error,
}: BenchmarkProgressBarProps) {
  const clampedProgress = Math.min(100, Math.max(0, progress));
  const statusClass = error ? "error" : running ? "running" : stage === "complete" ? "complete" : "idle";

  return (
    <div className={`benchmark-progress benchmark-progress--${statusClass}`}>
      <div className="benchmark-progress__header">
        <span className="benchmark-progress__stage">{STAGE_LABELS[stage]}</span>
        <span className="benchmark-progress__percent">{clampedProgress}%</span>
      </div>
      <div className="benchmark-progress__track" aria-hidden="true">
        <span
          className="benchmark-progress__fill"
          style={{ width: `${clampedProgress}%` }}
        />
      </div>
      <p className="benchmark-progress__message">{error ?? message}</p>
    </div>
  );
}
