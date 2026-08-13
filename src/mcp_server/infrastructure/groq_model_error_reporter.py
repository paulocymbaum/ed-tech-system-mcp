"""Report Groq model errors to the backend registry (E7 / 7.5)."""

from __future__ import annotations

import logging

import httpx
from pydantic import SecretStr

from mcp_server.domain.invariants import require_credential

logger = logging.getLogger(__name__)


class GroqModelErrorReporter:
    """POST /functions/v1/report-groq-model-errors with service role."""

    def __init__(self, supabase_url: str, service_role_key: SecretStr | str) -> None:
        self._supabase_url = supabase_url.rstrip("/")
        if isinstance(service_role_key, SecretStr):
            self._service_role_key = service_role_key.get_secret_value()
        else:
            self._service_role_key = service_role_key

    def report(self, *, model: str, error_type: str = "completion_error") -> None:
        require_credential(self._supabase_url, resource="Supabase")
        require_credential(self._service_role_key, resource="Supabase")
        url = f"{self._supabase_url}/functions/v1/report-groq-model-errors"
        headers = {
            "apikey": self._service_role_key,
            "Authorization": f"Bearer {self._service_role_key}",
            "Content-Type": "application/json",
        }
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.post(
                    url,
                    headers=headers,
                    json={"errors": [{"model": model, "error_type": error_type}]},
                )
                if response.status_code >= 400:
                    logger.warning(
                        "report-groq-model-errors failed status=%s body=%s",
                        response.status_code,
                        response.text[:200],
                    )
        except Exception:  # noqa: BLE001 — never fail the grader on telemetry
            logger.exception("report-groq-model-errors request failed")


_reporter: GroqModelErrorReporter | None = None


def register_groq_model_error_reporter(reporter: GroqModelErrorReporter) -> None:
    global _reporter
    _reporter = reporter


def report_groq_model_error(*, model: str, error_type: str = "completion_error") -> None:
    if _reporter is None:
        return
    _reporter.report(model=model, error_type=error_type)
