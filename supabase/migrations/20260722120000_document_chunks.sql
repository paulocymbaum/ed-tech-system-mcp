-- Phase A Vector RAG: documents, document_chunks (384-dim), match + hybrid RPCs

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS documents (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    title text NOT NULL,
    content text NOT NULL,
    course_id text,
    tags text[] DEFAULT '{}',
    language text,
    content_hash text NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS documents_course_id_idx ON documents (course_id);
CREATE INDEX IF NOT EXISTS documents_content_hash_idx ON documents (content_hash);

CREATE TABLE IF NOT EXISTS document_chunks (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id uuid NOT NULL REFERENCES documents (id) ON DELETE CASCADE,
    content text NOT NULL,
    content_hash text NOT NULL,
    language text,
    chunk_index integer NOT NULL,
    metadata jsonb NOT NULL DEFAULT '{}',
    embedding vector(384),
    fts tsvector GENERATED ALWAYS AS (
        to_tsvector(coalesce(language, 'simple')::regconfig, content)
    ) STORED,
    deleted_at timestamptz,
    CONSTRAINT document_chunks_unique_chunk UNIQUE (document_id, chunk_index, content_hash)
);

CREATE INDEX IF NOT EXISTS document_chunks_document_id_idx ON document_chunks (document_id);
CREATE INDEX IF NOT EXISTS document_chunks_embedding_idx
    ON document_chunks
    USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS document_chunks_fts_idx ON document_chunks USING gin (fts);
CREATE INDEX IF NOT EXISTS document_chunks_active_idx
    ON document_chunks (document_id)
    WHERE deleted_at IS NULL;

CREATE OR REPLACE FUNCTION match_chunks(
    query_embedding vector(384),
    match_count integer DEFAULT 20,
    filter jsonb DEFAULT '{}'::jsonb
)
RETURNS TABLE (
    id uuid,
    document_id uuid,
    title text,
    content text,
    score double precision,
    metadata jsonb
)
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    course_filter text := filter ->> 'course_id';
    language_filter text := filter ->> 'language';
    tags_filter text[];
BEGIN
    IF filter ? 'tags' THEN
        SELECT array_agg(value::text)
        INTO tags_filter
        FROM jsonb_array_elements_text(filter -> 'tags') AS value;
    END IF;

    RETURN QUERY
    SELECT
        dc.id,
        dc.document_id,
        d.title,
        dc.content,
        (1 - (dc.embedding <=> query_embedding))::double precision AS score,
        dc.metadata
    FROM document_chunks dc
    INNER JOIN documents d ON d.id = dc.document_id
    WHERE dc.deleted_at IS NULL
      AND dc.embedding IS NOT NULL
      AND (course_filter IS NULL OR d.course_id = course_filter)
      AND (language_filter IS NULL OR dc.language = language_filter)
      AND (
          tags_filter IS NULL
          OR d.tags && tags_filter
      )
    ORDER BY dc.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

CREATE OR REPLACE FUNCTION hybrid_search_chunks(
    query_text text,
    query_embedding vector(384),
    match_count integer DEFAULT 20,
    filter jsonb DEFAULT '{}'::jsonb,
    full_text_weight double precision DEFAULT 1.0,
    semantic_weight double precision DEFAULT 1.0,
    rrf_k integer DEFAULT 60
)
RETURNS TABLE (
    id uuid,
    document_id uuid,
    title text,
    content text,
    score double precision,
    metadata jsonb
)
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    course_filter text := filter ->> 'course_id';
    language_filter text := filter ->> 'language';
    tags_filter text[];
BEGIN
    IF filter ? 'tags' THEN
        SELECT array_agg(value::text)
        INTO tags_filter
        FROM jsonb_array_elements_text(filter -> 'tags') AS value;
    END IF;

    RETURN QUERY
    WITH filtered AS (
        SELECT
            dc.id,
            dc.document_id,
            d.title,
            dc.content,
            dc.metadata,
            dc.embedding,
            dc.fts
        FROM document_chunks dc
        INNER JOIN documents d ON d.id = dc.document_id
        WHERE dc.deleted_at IS NULL
          AND dc.embedding IS NOT NULL
          AND (course_filter IS NULL OR d.course_id = course_filter)
          AND (language_filter IS NULL OR dc.language = language_filter)
          AND (
              tags_filter IS NULL
              OR d.tags && tags_filter
          )
    ),
    semantic AS (
        SELECT
            f.id,
            ROW_NUMBER() OVER (ORDER BY f.embedding <=> query_embedding) AS rank_ix
        FROM filtered f
        ORDER BY f.embedding <=> query_embedding
        LIMIT match_count * 2
    ),
    keyword AS (
        SELECT
            f.id,
            ROW_NUMBER() OVER (
                ORDER BY ts_rank_cd(f.fts, websearch_to_tsquery(coalesce(language_filter, 'simple'), query_text)) DESC
            ) AS rank_ix
        FROM filtered f
        WHERE f.fts @@ websearch_to_tsquery(coalesce(language_filter, 'simple'), query_text)
        ORDER BY ts_rank_cd(f.fts, websearch_to_tsquery(coalesce(language_filter, 'simple'), query_text)) DESC
        LIMIT match_count * 2
    ),
    rrf AS (
        SELECT
            combined.id,
            SUM(combined.rrf_score) AS score
        FROM (
            SELECT s.id, semantic_weight * (1.0 / (rrf_k + s.rank_ix)) AS rrf_score
            FROM semantic s
            UNION ALL
            SELECT k.id, full_text_weight * (1.0 / (rrf_k + k.rank_ix)) AS rrf_score
            FROM keyword k
        ) AS combined
        GROUP BY combined.id
    )
    SELECT
        f.id,
        f.document_id,
        f.title,
        f.content,
        r.score::double precision,
        f.metadata
    FROM rrf r
    INNER JOIN filtered f ON f.id = r.id
    ORDER BY r.score DESC
    LIMIT match_count;
END;
$$;
