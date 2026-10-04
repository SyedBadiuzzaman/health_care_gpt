# Graph Report - Doc_Agent  (2026-10-03)

## Corpus Check
- 74 files · ~19,566 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 587 nodes · 971 edges · 58 communities (42 shown, 16 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 92 edges (avg confidence: 0.94)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `5b34e8e5`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- patient_index.py
- config.py
- app.js
- RagRepository
- chunking.py
- GuardrailEngine
- run_retrieval_benchmark.py
- AppSettings
- authorized_principal
- verify
- Doc Agent RAG Platform
- doc_agent_api/schemas.py
- retrieval.py
- patients.py
- history_query
- API application
- generation.py
- query_service.py
- run
- StoredChunk
- list_patients
- .dispatch
- doc_agent_api/main.py
- Core RAG package
- HistoryQueryService
- Database package
- ssh_tunnel.py
- DoctorRateLimiter
- runtime_config.py
- state.js
- Database column review
- Module and Import Guide
- doc-agent-common
- RequestSecurityMiddleware
- Development authentication application
- Worker application
- Common package
- .list_patients
- benchmark_latency.py
- package.json
- Operator scripts
- health.py
- state.py
- PatientSummary
- doc_agent_dev_auth/run.py
- .encode
- dependencies/__init__.py
- doc_agent_api/__init__.py
- doc_agent_dev_auth/__init__.py
- doc_agent_worker/__init__.py
- pipelines/__init__.py
- evals/__init__.py
- metrics/__init__.py
- scripts/__init__.py
- infra/README.md
- doc_agent_common/__init__.py
- doc_agent_core/__init__.py
- doc_agent_db/__init__.py

## God Nodes (most connected - your core abstractions)
1. `RagRepository` - 32 edges
2. `AppSettings` - 31 edges
3. `StoredChunk` - 24 edges
4. `history_query()` - 23 edges
5. `list_patients()` - 17 edges
6. `record_patient_selection()` - 16 edges
7. `create_app()` - 14 edges
8. `API application` - 13 edges
9. `authorized_principal()` - 12 edges
10. `run()` - 12 edges

## Surprising Connections (you probably didn't know these)
- `JwtVerifier` --uses--> `AppSettings`  [INFERRED]
  apps/api/src/doc_agent_api/dependencies/authentication.py → packages/common/src/doc_agent_common/config.py
- `get_settings()` --uses--> `AppSettings`  [INFERRED]
  apps/api/src/doc_agent_api/dependencies/services.py → packages/common/src/doc_agent_common/config.py
- `get_repository()` --uses--> `RagRepository`  [INFERRED]
  apps/api/src/doc_agent_api/dependencies/services.py → packages/db/src/doc_agent_db/rag_repository.py
- `get_history_service()` --uses--> `HistoryQueryService`  [INFERRED]
  apps/api/src/doc_agent_api/dependencies/services.py → packages/core-rag/src/doc_agent_core/query_service.py
- `create_app()` --uses--> `SshTunnel`  [INFERRED]
  apps/api/src/doc_agent_api/main.py → packages/common/src/doc_agent_common/ssh_tunnel.py

## Import Cycles
- None detected.

## Communities (58 total, 16 thin omitted)

### Community 0 - "patient_index.py"
Cohesion: 0.06
Nodes (42): main(), Provide one CLI surface for ingestion and isolated contact synchronization., main(), prepare(), Path, Run the preparation steps in the order described in the README., Read approved data and build a patient index inside the project., Prepare the local patient index and print a non-identifying summary. (+34 more)

### Community 1 - "config.py"
Cohesion: 0.08
Nodes (24): _base64url(), DevelopmentSigningKey, Generate and expose the temporary RSA key used for local development JWTs., Keep one process-local private key and publish only its public numbers., create_app(), FastAPI, Issue short-lived doctor JWTs for loopback development only., DevelopmentTokenRequest (+16 more)

### Community 2 - "app.js"
Cohesion: 0.15
Nodes (27): addOption(), apiFetch(), appendCitations(), bootstrapDevelopmentAuth(), clearAllState(), elements, handleUnauthorized(), loadPatients() (+19 more)

### Community 3 - "RagRepository"
Cohesion: 0.12
Nodes (17): AsyncConnection, ClinicalDomain, FloatVector, RagRepository, Atomically upsert the new snapshot and remove its stale predecessors., Run filtered HNSW cosine retrieval for one authorized patient., Run filtered simple-dictionary full-text retrieval., Record one authorized selection and retain only the latest eight. (+9 more)

### Community 4 - "chunking.py"
Cohesion: 0.12
Nodes (22): build_chunk_drafts(), _chunk_id(), _clean_facts(), _content_hash(), count_domains(), ClinicalDomain, Protocol, Create short, domain-specific chunks from aggregated clinical facts. (+14 more)

### Community 5 - "GuardrailEngine"
Cohesion: 0.13
Nodes (15): main(), Path, Evaluate deterministic medical-direction filters without sending clinical data., Run the labeled adversarial cases and save aggregate, non-sensitive results., Print aggregate results and fail when a labeled directive escapes., run(), deterministic_input_allowed(), deterministic_output_allowed() (+7 more)

### Community 6 - "run_retrieval_benchmark.py"
Cohesion: 0.15
Nodes (18): average_metrics(), Score labeled retrieval results for dense, keyword, and hybrid strategies., Report the acceptance metrics for one retrieval strategy., Calculate binary relevance metrics at five documents., Average all labeled queries while requiring a result for every label., RetrievalMetrics, score_query(), EvaluationLabel (+10 more)

### Community 7 - "AppSettings"
Cohesion: 0.14
Nodes (12): create_app(), Construct the API and load model clients during application startup., AppSettings, Build a libpq connection string for the active network path., Require security and model settings before serving requests., Hold database, model, and authorization settings for one process., Load settings relative to the project root., DatabaseConnectionFactory (+4 more)

### Community 8 - "authorized_principal"
Cohesion: 0.16
Nodes (15): authenticated_principal(), authorized_principal(), DoctorPrincipal, Depends, max_length, min_length, Path, pattern (+7 more)

### Community 9 - "verify"
Cohesion: 0.15
Nodes (13): main(), Run the FastAPI service without access logs that expose patient URL paths., Start one worker; deploy multiple workers behind a shared gateway limiter., main(), Print aggregate benchmark metrics without clinical text or identifiers., configure_asyncio_for_psycopg(), Configure platform details shared by command-line entry points., Use Windows selector I/O because psycopg rejects the proactor loop. (+5 more)

### Community 10 - "Doc Agent RAG Platform"
Cohesion: 0.12
Nodes (13): Architecture, Clinical data path, Dependency direction, Runtime boundaries, AWS EC2 database access, Database preparation and indexing, Deployment boundaries, Doc Agent RAG Platform (+5 more)

### Community 11 - "doc_agent_api/schemas.py"
Cohesion: 0.18
Nodes (14): Citation, HistoryQueryRequest, HistoryQueryResponse, PatientListItem, PatientListResponse, BaseModel, Validate public API requests and responses., Accept one stateless question and an optional admission filter. (+6 more)

### Community 12 - "retrieval.py"
Cohesion: 0.21
Nodes (13): hybrid_select(), maximal_marginal_relevance(), ClinicalDomain, FloatVector, Fuse dense and lexical retrieval while preserving clinical diversity., Apply domain-aware MMR after weighted reciprocal-rank fusion., Infer domains for a structured query and default to all domains., Combine two rankings without comparing incompatible raw scores. (+5 more)

### Community 13 - "patients.py"
Cohesion: 0.27
Nodes (9): get_history_service(), get_rate_limiter(), get_repository(), get_settings(), Request, Resolve request-scoped access to initialized application services., Add request correlation, secure headers, and a bounded per-doctor rate limit., Serve authorized patient discovery and history queries. (+1 more)

### Community 14 - "history_query"
Cohesion: 0.21
Nodes (13): history_query(), Depends, min_length, Path, pattern, Request, Response, Answer one guarded question about one authorized patient's history. (+5 more)

### Community 15 - "API application"
Cohesion: 0.15
Nodes (13): API application, `apps/api/src/doc_agent_api/dependencies/authentication.py`, `apps/api/src/doc_agent_api/dependencies/__init__.py`, `apps/api/src/doc_agent_api/dependencies/services.py`, `apps/api/src/doc_agent_api/__init__.py`, `apps/api/src/doc_agent_api/main.py`, `apps/api/src/doc_agent_api/middleware.py`, `apps/api/src/doc_agent_api/routers/health.py` (+5 more)

### Community 16 - "generation.py"
Cohesion: 0.21
Nodes (11): assemble_context(), GeminiAnswer, GeneratedAnswer, BaseModel, Assemble de-identified context and generate citation-bound history summaries., Generate and validate a structured context-only answer., Define the only accepted structured model response., Return a validated answer with the referenced source chunks. (+3 more)

### Community 17 - "query_service.py"
Cohesion: 0.21
Nodes (10): Remove selected identifiers and email addresses before cloud generation., redact_question_identifiers(), GenerationFailure, QueryOutcome, Coordinate authorization-independent retrieval, generation, and output checks., Hide upstream model and malformed-output details from API clients., Carry one service decision into the HTTP response layer., Run both safety layers and keep every lookup scoped to one patient. (+2 more)

### Community 18 - "run"
Cohesion: 0.24
Nodes (8): Evaluate all strategies under the same patient and question set., run(), Open a local-only PostgreSQL forward for one process., Wait until the forwarded port accepts connections or SSH exits., Stop the forwarding process without affecting the SSH server., SshTunnel, RuntimeError, Self

### Community 19 - "StoredChunk"
Cohesion: 0.21
Nodes (9): HistoryRepository, ClinicalDomain, FloatVector, Protocol, Describe the patient-scoped reads required by the query pipeline., Represent a searchable chunk returned from PostgreSQL., Hold a bounded deterministic result for exhaustive questions., StoredChunk (+1 more)

### Community 20 - "list_patients"
Cohesion: 0.18
Nodes (10): list_patients(), get, max_length, Return only indexed patients authorized by the current JWT., ge, le, doctor_storage_key(), Provide shared one-way identifiers and safe URL checks. (+2 more)

### Community 21 - ".dispatch"
Cohesion: 0.20
Nodes (9): rate_limit_response(), Return a cache-safe limit response without sensitive request data., LoopbackOnlyMiddleware, BaseHTTPMiddleware, Request, Response, Reject network clients because this server grants arbitrary test access., JSONResponse (+1 more)

### Community 22 - "doc_agent_api/main.py"
Cohesion: 0.22
Nodes (5): JwtVerifier, Validate signatures and required claims against the configured JWKS., Resolve the signing key off-loop and validate all security claims., FastAPI, Assemble the stateless, JWT-protected medical-history API.

### Community 23 - "Core RAG package"
Cohesion: 0.22
Nodes (9): Core RAG package, `packages/core-rag/src/doc_agent_core/chunking.py`, `packages/core-rag/src/doc_agent_core/embeddings.py`, `packages/core-rag/src/doc_agent_core/generation.py`, `packages/core-rag/src/doc_agent_core/guardrails.py`, `packages/core-rag/src/doc_agent_core/__init__.py`, `packages/core-rag/src/doc_agent_core/query_service.py`, `packages/core-rag/src/doc_agent_core/retrieval.py` (+1 more)

### Community 24 - "HistoryQueryService"
Cohesion: 0.28
Nodes (6): MiniLmEmbedder, Generate normalized 384-dimensional embeddings on the local machine., GeminiHistoryGenerator, Call Gemini without sending patient, admission, email, or JWT identifiers., HistoryQueryService, Answer one question without retaining cross-request state.

### Community 25 - "Database package"
Cohesion: 0.25
Nodes (8): Database package, `packages/db/src/doc_agent_db/connection.py`, `packages/db/src/doc_agent_db/contact_schema.py`, `packages/db/src/doc_agent_db/contact_source.py`, `packages/db/src/doc_agent_db/contact_store.py`, `packages/db/src/doc_agent_db/__init__.py`, `packages/db/src/doc_agent_db/rag_repository.py`, `packages/db/src/doc_agent_db/source_queries.py`

### Community 26 - "ssh_tunnel.py"
Cohesion: 0.29
Nodes (6): Manage the existing SSH path to PostgreSQL., main(), Verify deployed pgvector storage without printing patient identifiers., Check extension, vectors, indexes, uniqueness, and injection isolation., Print only aggregate, non-identifying verification values., verify()

### Community 27 - "DoctorRateLimiter"
Cohesion: 0.33
Nodes (4): DoctorRateLimiter, Apply a small in-process limit keyed by a one-way doctor identifier., Make identifiers useful for local correlation without recording them., Discard expired timestamps and admit requests within the minute window.

### Community 28 - "runtime_config.py"
Cohesion: 0.33
Nodes (6): BaseModel, Depends, get, Expose non-sensitive browser bootstrap configuration., runtime_configuration(), RuntimeConfigResponse

### Community 30 - "Database column review"
Cohesion: 0.29
Nodes (6): Columns for selection, Confirmed selection and next step, Database column review, Email decision, Record identity, Verified local preparation

### Community 31 - "Module and Import Guide"
Cohesion: 0.29
Nodes (7): `evals/__init__.py`, `evals/metrics/__init__.py`, and `evals/scripts/__init__.py`, `evals/metrics/retrieval_metrics.py`, `evals/scripts/run_retrieval_benchmark.py`, `evals/scripts/run_safety_evaluation.py`, Evaluation modules, Folder purpose, Module and Import Guide

### Community 32 - "doc-agent-common"
Cohesion: 0.62
Nodes (7): doc-agent-api, doc-agent-common, doc-agent-core, doc-agent-db, doc-agent-dev-auth, doc-agent-worker, my-rag-platform

### Community 33 - "RequestSecurityMiddleware"
Cohesion: 0.33
Nodes (5): BaseHTTPMiddleware, Request, Response, Set safe response headers and request IDs without logging URL paths., RequestSecurityMiddleware

### Community 34 - "Development authentication application"
Cohesion: 0.33
Nodes (6): `apps/dev-auth/src/doc_agent_dev_auth/__init__.py`, `apps/dev-auth/src/doc_agent_dev_auth/keys.py`, `apps/dev-auth/src/doc_agent_dev_auth/main.py`, `apps/dev-auth/src/doc_agent_dev_auth/run.py`, `apps/dev-auth/src/doc_agent_dev_auth/schemas.py`, Development authentication application

### Community 35 - "Worker application"
Cohesion: 0.33
Nodes (6): `apps/worker/src/doc_agent_worker/__init__.py` and `pipelines/__init__.py`, `apps/worker/src/doc_agent_worker/main.py`, `apps/worker/src/doc_agent_worker/pipelines/contact_sync.py`, `apps/worker/src/doc_agent_worker/pipelines/patient_index.py`, `apps/worker/src/doc_agent_worker/run.py`, Worker application

### Community 36 - "Common package"
Cohesion: 0.33
Nodes (6): Common package, `packages/common/src/doc_agent_common/config.py`, `packages/common/src/doc_agent_common/__init__.py`, `packages/common/src/doc_agent_common/runtime.py`, `packages/common/src/doc_agent_common/security.py`, `packages/common/src/doc_agent_common/ssh_tunnel.py`

### Community 37 - ".list_patients"
Cohesion: 0.33
Nodes (5): PatientDirectoryEntry, PatientDirectoryPage, Expose selector metadata without loading clinical text., Return one authorized selector page and its recent ordering., List indexed patients inside the JWT claim and never outside it.

### Community 38 - "benchmark_latency.py"
Cohesion: 0.40
Nodes (5): benchmark(), main(), Measure API response latency without recording request or response content., Call one authorized history route repeatedly and return timing aggregates., Read the token from the environment so it never appears in shell history.

### Community 39 - "package.json"
Cohesion: 0.40
Nodes (4): description, name, private, type

### Community 40 - "Operator scripts"
Cohesion: 0.40
Nodes (5): Operator scripts, `scripts/apply_migrations.py`, `scripts/benchmark_latency.py`, `scripts/verify_retrieval.py`, `scripts/verify_storage.py`

### Community 41 - "health.py"
Cohesion: 0.50
Nodes (3): health(), get, Expose a minimal process health endpoint.

### Community 43 - "PatientSummary"
Cohesion: 0.50
Nodes (3): PatientSummary, Provide deterministic patient-level counts without clinical text., Read deterministic counts for one patient.

## Knowledge Gaps
- **78 isolated node(s):** `name`, `private`, `type`, `description`, `elements` (+73 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **16 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `AppSettings` connect `AppSettings` to `patient_index.py`, `config.py`, `RagRepository`, `GuardrailEngine`, `verify`, `patients.py`, `history_query`, `run`, `list_patients`, `doc_agent_api/main.py`, `HistoryQueryService`, `ssh_tunnel.py`, `runtime_config.py`?**
  _High betweenness centrality (0.083) - this node is a cross-community bridge._
- **Why does `RagRepository` connect `RagRepository` to `patient_index.py`, `chunking.py`, `.list_patients`, `AppSettings`, `verify`, `PatientSummary`, `patients.py`, `history_query`, `run`, `StoredChunk`, `list_patients`, `ssh_tunnel.py`?**
  _High betweenness centrality (0.080) - this node is a cross-community bridge._
- **Why does `StoredChunk` connect `StoredChunk` to `RagRepository`, `run_retrieval_benchmark.py`, `state.py`, `retrieval.py`, `generation.py`, `query_service.py`, `run`, `HistoryQueryService`?**
  _High betweenness centrality (0.043) - this node is a cross-community bridge._
- **Are the 16 inferred relationships involving `RagRepository` (e.g. with `get_repository()` and `create_app()`) actually correct?**
  _`RagRepository` has 16 INFERRED edges - model-reasoned connections that need verification._
- **Are the 19 inferred relationships involving `AppSettings` (e.g. with `JwtVerifier` and `get_settings()`) actually correct?**
  _`AppSettings` has 19 INFERRED edges - model-reasoned connections that need verification._
- **Are the 13 inferred relationships involving `StoredChunk` (e.g. with `_relevant()` and `run()`) actually correct?**
  _`StoredChunk` has 13 INFERRED edges - model-reasoned connections that need verification._
- **Are the 8 inferred relationships involving `history_query()` (e.g. with `DoctorPrincipal` and `DoctorRateLimiter`) actually correct?**
  _`history_query()` has 8 INFERRED edges - model-reasoned connections that need verification._