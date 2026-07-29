import type { WorkflowTraceStep } from "../api/workflows";

type WorkflowStepInspectorProps = {
  step: WorkflowTraceStep | null;
};

function JsonBlock({ title, value }: { title: string; value: unknown }) {
  const text =
    value === null || value === undefined
      ? "—"
      : JSON.stringify(value, null, 2);

  return (
    <div className="inspector-block">
      <h4>{title}</h4>
      <pre className="inspector-pre">{text}</pre>
    </div>
  );
}

export function WorkflowStepInspector({ step }: WorkflowStepInspectorProps) {
  if (!step) {
    return (
      <div className="inspector-panel">
        <h3>Node I/O</h3>
        <p className="muted">Select a replay step to inspect node input, output, and LLM prompts.</p>
      </div>
    );
  }

  return (
    <div className="inspector-panel">
      <h3>
        Node I/O · {step.node_id.replaceAll("_", " ")} (attempt {step.attempt})
      </h3>
      <JsonBlock title="Input state" value={step.input_snapshot} />
      <JsonBlock title="Output update" value={step.output_update} />
      {step.llm_io ? (
        <>
          <JsonBlock title="Model" value={step.llm_io.model_name ?? step.output_update.model_name} />
          <JsonBlock
            title="LLM complexity tier"
            value={step.llm_io.llm_complexity ?? step.output_update.llm_complexity}
          />
          <JsonBlock
            title="Token usage"
            value={{
              input_tokens: step.llm_io.input_tokens ?? step.output_update.input_tokens,
              output_tokens: step.llm_io.output_tokens ?? step.output_update.output_tokens,
              total_tokens: step.llm_io.total_tokens ?? step.output_update.total_tokens,
              breakdown: step.llm_io.token_breakdown,
            }}
          />
          <JsonBlock title="LLM system prompt" value={step.llm_io.system_prompt} />
          <JsonBlock title="LLM user prompt" value={step.llm_io.user_prompt} />
          <JsonBlock title="LLM raw output" value={step.llm_io.raw_output} />
        </>
      ) : (
        <p className="muted">This step did not invoke the LLM.</p>
      )}
    </div>
  );
}
