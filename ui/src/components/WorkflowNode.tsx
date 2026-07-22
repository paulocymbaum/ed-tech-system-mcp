import { Handle, type Node, type NodeProps, Position } from "@xyflow/react";

export type WorkflowNodeData = {
  label: string;
  kind: "start" | "end" | "node";
  status: "idle" | "active" | "failed" | "retry";
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
        className={`workflow-node workflow-node--${data.kind} workflow-node--${data.status}`}
        title={data.label}
      >
        <span className="workflow-node__label">{data.label}</span>
      </div>
    </>
  );
}
