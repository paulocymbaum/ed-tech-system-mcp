import { Handle, type Node, type NodeProps, Position } from "@xyflow/react";

export type WorkflowNodeData = {
  label: string;
  kind: "start" | "end" | "node";
  status: "idle" | "active" | "failed" | "retry" | "visited" | "history-failed" | "history-retry";
  composite?: boolean;
  groupId?: string;
  expanded?: boolean;
  onToggleGroup?: (groupId: string) => void;
};

export type WorkflowNodeType = Node<WorkflowNodeData, "workflow">;

export function WorkflowNode({ data }: NodeProps<WorkflowNodeType>) {
  const showTarget = data.kind !== "start";
  const showSource = data.kind !== "end";

  return (
    <>
      {showTarget && (
        <>
          <Handle
            id="left"
            type="target"
            position={Position.Left}
            className="workflow-handle workflow-handle--target"
          />
          <Handle
            id="top"
            type="target"
            position={Position.Top}
            className="workflow-handle workflow-handle--target"
          />
        </>
      )}
      {showSource && (
        <>
          <Handle
            id="right"
            type="source"
            position={Position.Right}
            className="workflow-handle workflow-handle--source"
          />
          <Handle
            id="top-source"
            type="source"
            position={Position.Top}
            className="workflow-handle workflow-handle--source"
          />
        </>
      )}
      <div
        className={`workflow-node workflow-node--${data.kind} workflow-node--${data.status} ${
          data.composite ? "workflow-node--composite" : ""
        }`}
        title={data.label}
        onClick={
          data.composite && data.groupId && data.onToggleGroup
            ? (event) => {
                event.stopPropagation();
                data.onToggleGroup?.(data.groupId ?? "");
              }
            : undefined
        }
        onKeyDown={
          data.composite && data.groupId && data.onToggleGroup
            ? (event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  data.onToggleGroup?.(data.groupId ?? "");
                }
              }
            : undefined
        }
        role={data.composite ? "button" : undefined}
        tabIndex={data.composite ? 0 : undefined}
      >
        {data.composite && (
          <span className="workflow-node__chevron" aria-hidden="true">
            {data.expanded ? "▾" : "▸"}
          </span>
        )}
        <span className="workflow-node__label">{data.label}</span>
      </div>
    </>
  );
}
