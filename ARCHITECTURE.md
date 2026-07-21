# Architecture Documentation: Domain-Driven MCP Server

This document defines the architectural standards for our MCP (Model Context Protocol) server implementation. We prioritize maintainability, testability, and scalability by enforcing Domain-Driven Design (DDD) principles, SOLID design, and the Clean Architecture philosophy.

## Core Design Principles

- **SOLID**: Each component must have a single responsibility. We prefer composition over inheritance and strictly follow the Dependency Inversion Principle.
- **DRY (Don't Repeat Yourself)**: Domain logic must exist in exactly one place. If logic is duplicated between tools or resources, it belongs in a Domain Service.
- **Clean Code**: Code must be readable, self-documenting, and free of unnecessary complexity. Names should reflect domain concepts, not implementation details.

---

## Architectural Layers (Clean Architecture)

We divide the application into concentric layers, where the inner layers (Domain) are oblivious to outer layers (Frameworks/Transport).

### 1. Domain Layer (`/domain`)
The "source of truth." This layer contains only pure business logic, entities, and domain exceptions.
*   **Restrictions:** No dependencies on the MCP SDK, LangChain, database drivers, or external API libraries.
*   **Responsibility:** Define core business objects, validation rules, domain-specific service interfaces (Ports), and video search contracts (`IVideoSearchClient`, `VideoResult`).

### 2. Application/Use-Case Layer (`/application`)
Coordinates the flow of data between the Domain and the Interface layers, orchestrating Agentic workflows.
*   **Restrictions:** Can depend on Domain interfaces and LangChain primitives for orchestration, but not on concrete data/infrastructure implementations.
*   **Responsibility:** Orchestrate domain services and LangChain tools to fulfill specific execution requests, including document retrieval enriched with YouTube video discovery.

### 3. Interface Layer (`/interface`)
The adapter layer bridging the external MCP protocol and internal Application/Domain logic.
*   **Restrictions:** Can depend on the Domain, Application, and the MCP SDK.
*   **Responsibility:** Expose tools to the MCP server, handle JSON-RPC translation, enforce Pydantic validation on incoming requests, and handle error mapping.

### 4. Infrastructure Layer (`/infrastructure`)
Contains the implementations (Adapters) of the interfaces defined in the Domain layer.
*   **Responsibility:** Supabase integration, open-source search APIs, YouTube video search, file system access, logging, and external tool clients.

---

## File Structure

```text
src/
└── mcp_server/
    ├── __init__.py
    ├── domain/                     # Pure Business Logic
    │   ├── __init__.py
    │   ├── exceptions.py           # Domain exceptions (e.g., ResourceNotFound)
    │   ├── interfaces.py           # Abstract base classes (Ports) for DB/Search/Video
    │   └── schemas.py              # Core entity definitions
    ├── application/                # LangChain & Orchestration
    │   ├── __init__.py
    │   ├── agent.py                # LangChain agent/graph definitions
    │   └── workflows.py            # Use-case orchestrators tying tools together (incl. document + video discovery)
    ├── interface/                  # MCP Adapter & Strict Validation
    │   ├── __init__.py
    │   ├── mcp_server.py           # MCP Server instantiation & tool routing
    │   ├── validation.py           # Pydantic validation layer for incoming/outgoing data
    │   └── custom_tools.py         # MCP tool wrappers around application workflows
    ├── infrastructure/             # External Integrations (Adapters)
    │   ├── __init__.py
    │   ├── supabase_client.py      # Supabase repository implementation
    │   ├── search_client.py        # Open-source web search implementation (e.g., DuckDuckGo)
    │   ├── youtube_client.py       # YouTube Data API adapter for educational video search
    │   └── external_apis.py        # Other customized 3rd-party integrations
    └── main.py                     # Entrypoint (Transport initialization: Stdio/SSE)
```

---

## Dependency Stack & Usage

| Dependency | Primary Use Case | Which Layer? |
| :--- | :--- | :--- |
| **`mcp` / `fastmcp`** | The core MCP server transport and protocol handler. Exposes tools to external clients. | Interface / Entrypoint |
| **`langchain` / `langgraph`** | Orchestrating multi-step workflows, agent reasoning, and wrapping customized tools for LLM consumption. | Application |
| **`pydantic` (v2)** | The strict validation layer. Enforcing schema rules on inputs/outputs before they reach the reasoning engine. | Domain / Interface |
| **`supabase`** | Postgres database client for querying, vector search (pgvector), and handling structured application data. | Infrastructure |
| **`duckduckgo-search`** (or `tavily-python`) | Open-source web search integration for real-time information retrieval. | Infrastructure |
| **`google-api-python-client`** | YouTube Data API v3 client for searching educational videos by topic, channel, or document-derived keywords. | Infrastructure |
| **`python-dotenv`** | Managing environment variables (Supabase URL/Keys, API keys). | Entrypoint |

---

## Core Patterns

### 1. Pydantic Validation Layer Pattern
All incoming MCP tool calls must be intercepted by a strict Pydantic validation layer before reaching LangChain or Domain logic.
*   **Rule:** Define request and response schemas in `interface/validation.py`. Validate inputs directly within the MCP tool decorators using these models. This prevents malformed JSON or AI hallucinations from polluting the reasoning engine and guarantees type safety.

### 2. External Integration Pattern (Ports & Adapters)
External tools (like the search tool or customized 3rd-party APIs) must not be tightly coupled directly to LangChain logic.
*   **Rule:** Define an interface like `ISearchClient` (Port) in `domain/interfaces.py`. Implement `DuckDuckGoSearchClient` (Adapter) in `infrastructure/`. The LangChain tool in `application/` receives this interface via Dependency Injection, making the system highly testable and agnostic to the specific search provider.

### 3. Database Integration Pattern (Supabase Repository)
Direct database queries should never occur within tools or application logic.
*   **Rule:** Use the Repository Pattern. Define `IDataRepository` in the domain. Create `SupabaseRepository` in the infrastructure layer. This encapsulates the `supabase-py` client logic, ensuring that connection pooling, querying, and data mapping are centralized.

### 4. YouTube Video Search Pattern (Document-Aware Discovery)
Educational video discovery must be decoupled from MCP tools and LangChain agents, and must enrich — not replace — document retrieval.
*   **Rule:** Define `IVideoSearchClient` (Port) in `domain/interfaces.py` with domain entities such as `VideoResult` (title, channel, URL, duration, relevance score) in `domain/schemas.py`. Implement `YouTubeDataApiClient` (Adapter) in `infrastructure/youtube_client.py`.
*   **Document linkage:** Application workflows in `workflows.py` extract search terms from validated document metadata or user queries (e.g., lesson title, topic tags from Supabase), then call `IVideoSearchClient` to find complementary videos. The workflow merges document hits and video results into a single, ranked response — never exposing raw YouTube API payloads to the MCP layer.
*   **Validation:** MCP tool inputs for video search (query, max results, language, safe-search flag) and outputs (normalized `VideoResult` list) must pass through Pydantic schemas in `interface/validation.py` before reaching Application logic.
*   **Credentials:** YouTube API keys are loaded at the Entrypoint and injected into the Infrastructure adapter only. Never embed keys in tool definitions or LangChain prompts.

### 5. Schema Evolution Pattern
*   **Rule:** Maintain a clear boundary between *External Schemas* (MCP protocol contracts), *Validation Schemas* (Pydantic), and *Domain Entities*. Ensure database-specific fields (like internal IDs or Supabase metadata) do not leak into the MCP External Schemas unless explicitly required by the LLM client.

---

## Anti-Patterns (What to Avoid)

| Anti-Pattern | Description | Why it's harmful |
| :--- | :--- | :--- |
| **"Smart" Tools** | Writing LangChain routing logic or Supabase queries directly inside the MCP tool decorator. | Impossible to test independently; violates Single Responsibility. |
| **Leaky Contexts** | Passing MCP `Context` objects directly into Supabase queries or LangChain agents. | Binds the core data and reasoning layers to the transport protocol. |
| **Unvalidated I/O** | Trusting the LLM's JSON output without passing it through Pydantic first. | Leads to runtime crashes when the AI hallucinates parameters or omits required fields. |
| **Direct YouTube API Calls in Tools** | Calling the YouTube Data API inside an MCP tool decorator or LangChain agent node. | Bypasses the Port/Adapter boundary; makes video search untestable and couples transport to a third-party API. |
| **Raw API Leakage** | Returning YouTube API response blobs directly to the LLM client. | Exposes provider-specific fields, wastes context tokens, and breaks the External Schema boundary. |