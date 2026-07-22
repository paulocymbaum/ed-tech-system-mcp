"""Supabase repository implementation."""

from mcp_server.domain.interfaces import IDataRepository
from mcp_server.domain.invariants import (
    require_credential,
    require_non_empty_text,
    require_positive_int,
)
from mcp_server.domain.schemas import DocumentHit


class SupabaseRepository(IDataRepository):
    """Adapter for Supabase-backed document storage."""

    def __init__(self, supabase_url: str, service_role_key: str) -> None:
        self._supabase_url = supabase_url
        self._service_role_key = service_role_key

    async def find_documents(self, query: str, limit: int = 10) -> list[DocumentHit]:
        query = require_non_empty_text(query, field="query")
        limit = require_positive_int(limit, field="limit")
        require_credential(self._supabase_url, resource="Supabase")
        require_credential(self._service_role_key, resource="Supabase")
        raise NotImplementedError("SupabaseRepository.find_documents is not yet implemented")
