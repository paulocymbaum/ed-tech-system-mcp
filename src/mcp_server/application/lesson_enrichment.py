"""Lesson enrichment query expansion (application use-case)."""

from __future__ import annotations

import json
import re

from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field

from mcp_server.application.llm import get_chat_model
from mcp_server.application.llm_model_name import resolve_invoked_model_name
from mcp_server.application.workflow_llm_trace import record_llm_invocation
from mcp_server.domain.exceptions import ResourceNotFoundError
from mcp_server.domain.llm_routing import LLMComplexity

_ENRICHMENT_STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "by",
    "for",
    "from",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
}

_WORD_RE = re.compile(r"[a-zA-Z]+")


class LessonEnrichmentQuery(BaseModel):
    """Terms generated from course/module/lesson titles for enrichment search."""

    terms: list[str] = Field(
        default_factory=list,
        min_length=1,
        max_length=5,
        description="4-5 concise search terms for finding videos and library documents",
    )
    query: str = Field(
        default="",
        description="Terms joined into a single query string for legacy BFFs",
    )


def clean_search_words(text: str) -> list[str]:
    """Extract significant, lowercase search words from a title or term."""
    words = [w.lower() for w in _WORD_RE.findall(text)]
    return [w for w in words if len(w) > 1 and w not in _ENRICHMENT_STOP_WORDS]


def build_enrichment_terms(
    course_title: str,
    module_title: str,
    lesson_title: str,
    raw_terms: list[str],
) -> list[str]:
    """Build a clean, deduplicated list of 4-5 search terms."""
    seen: set[str] = set()
    terms: list[str] = []

    def add_word(word: str) -> None:
        if not word or len(word) < 2 or word in seen or word in _ENRICHMENT_STOP_WORDS:
            return
        seen.add(word)
        terms.append(word)

    for phrase in raw_terms:
        for word in clean_search_words(phrase):
            add_word(word)

    for word in clean_search_words(course_title):
        add_word(word)

    for word in clean_search_words(module_title):
        add_word(word)

    for word in clean_search_words(lesson_title):
        add_word(word)

    return terms[:5]


async def build_lesson_enrichment_query(
    course_title: str,
    module_title: str,
    lesson_title: str,
) -> LessonEnrichmentQuery:
    """Use a lightweight LLM to turn lesson metadata into 4-5 search terms."""
    model = get_chat_model()
    if model is None:
        raise ResourceNotFoundError("Chat model has not been initialized")

    prompt = (
        "You are helping build a search query for lesson enrichment materials "
        "(YouTube videos and educational documents).\n\n"
        f"Course title: {course_title}\n"
        f"Module title: {module_title}\n"
        f"Lesson title: {lesson_title}\n\n"
        "Return a JSON array of 4 to 5 concise, relevant search terms a student would type. "
        "Prefer single lowercase words. Do not include numerals, IDs, slugs, or hyphens. "
        "Include a term for the course name. Avoid repeating terms. "
        "Return ONLY the JSON array, with no markdown or explanation."
    )
    result = await model.ainvoke(
        [HumanMessage(content=prompt)],
        llm_complexity=int(LLMComplexity.LOW),
    )
    raw = result.content if isinstance(result.content, str) else str(result.content)
    record_llm_invocation(
        system_prompt="",
        user_prompt=prompt,
        raw_output=raw,
        model_name=resolve_invoked_model_name(model),
        llm_complexity=int(LLMComplexity.LOW),
    )

    raw_terms: list[str] = []
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            raw_terms = [str(t).strip() for t in parsed if str(t).strip()]
    except (json.JSONDecodeError, TypeError, ValueError):
        pass

    terms = build_enrichment_terms(
        course_title,
        module_title,
        lesson_title,
        raw_terms,
    )
    return LessonEnrichmentQuery(terms=terms, query=" ".join(terms))
