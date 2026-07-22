"""API schemas for the local workflow UI."""

from mcp_server.application.workflow_graph import WorkflowGraphView

WorkflowListResponse = list[WorkflowGraphView]
