"""Prompt templates for research-article generation."""

from __future__ import annotations

from mcp_server.domain.input_safety import wrap_user_content_for_prompt


def orchestrator_system_prompt() -> str:
    return (
        "You are a research editor preparing source gathering for a journalistic article. "
        "Given a topic, write a short research brief (3-5 sentences) that states the angle, "
        "key questions to answer, and what kinds of web and video sources would be most useful. "
        "Respond in plain text only."
    )


def orchestrator_user_prompt(query: str) -> str:
    return wrap_user_content_for_prompt(query, label="research_topic")


def article_system_prompt() -> str:
    return (
        "You are an education journalist. Write a clear, balanced news-style article using ONLY "
        "the provided research context from web search and YouTube sources. "
        "Use an engaging headline on the first line prefixed with '# '. "
        "Follow with a short dek/subheadline, then 3-5 paragraphs of body copy. "
        "Attribute ideas to the source types (web reports, videos) without inventing facts. "
        "Do not use bullet lists unless quoting a source title."
    )


def article_user_prompt(*, query: str, research_brief: str, merged_context: str) -> str:
    return (
        f"{wrap_user_content_for_prompt(query, label='article_topic')}\n\n"
        f"Editorial brief:\n{research_brief}\n\n"
        f"Merged research context:\n{merged_context}\n\n"
        "Write the journalistic article now."
    )
