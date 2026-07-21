"""Supabase repository implementation."""

from mcp_server.domain.interfaces import IDataRepository
from mcp_server.domain.schemas import DocumentHit


class SupabaseRepository(IDataRepository):
    """Adapter for Supabase-backed document storage."""

    def __init__(self, supabase_url: str, service_role_key: str) -> None:
        self._supabase_url = supabase_url
        self._service_role_key = service_role_key

    async def find_documents(self, query: str, limit: int = 10) -> list[DocumentHit]:
        raise NotImplementedError("SupabaseRepository.find_documents is not yet implemented")
