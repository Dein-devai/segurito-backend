-- Schema RAG sobre pgvector (Supabase). Aplicar con scripts/bootstrap_supabase.py
-- o pegando este archivo en el SQL Editor del dashboard.

create extension if not exists vector;

create table if not exists rag_documents (
  collection  text        not null,
  id          text        not null,
  document    text        not null,
  metadata    jsonb       not null default '{}'::jsonb,
  embedding   vector(512) not null,
  created_at  timestamptz not null default now(),
  primary key (collection, id)
);

create index if not exists rag_documents_collection_idx
  on rag_documents (collection);

create index if not exists rag_documents_embedding_idx
  on rag_documents using hnsw (embedding vector_cosine_ops);

create index if not exists rag_documents_intencion_idx
  on rag_documents ((metadata->>'intencion'));
