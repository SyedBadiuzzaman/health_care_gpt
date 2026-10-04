# Module and Import Guide

This guide covers every Python file retained in the final repository. Standard-library imports ship with Python. Third-party imports name the installed package. Internal imports show the intended dependency direction.

## Folder purpose

- `apps/api` is the deployable HTTP application. It translates HTTP requests into calls to shared packages.
- `apps/worker` is the deployable command-line ingestion application. It has no always-running queue dependency.
- `apps/dev-auth` is the loopback-only development identity service.
- `apps/web` is the browser client and contains no Python files.
- `packages/core-rag` contains database-independent RAG behavior.
- `packages/db` contains persistence, SQL, and source-data access.
- `packages/common` contains the lowest-level runtime and security utilities.
- `evals` contains quality measurements that remain useful after ordinary implementation tests are removed.
- `scripts` contains operator-run maintenance and verification commands.
- `infra` documents where future infrastructure code belongs. Empty Terraform, Kubernetes, CI, parser, cache, and queue folders are omitted because the platform does not use them.

## API application

### `apps/api/src/doc_agent_api/__init__.py`

Marks `doc_agent_api` as a package. It has no imports or runtime behavior.

### `apps/api/src/doc_agent_api/main.py`

Builds the FastAPI application, owns its lifespan, opens the SSH tunnel, creates the embedding/model/repository services, installs middleware and routers, and serves `/app`. `create_app` is the application factory.

- Standard library: `asyncio` moves blocking model initialization to a thread; `collections.abc.AsyncIterator` types the lifespan; `contextlib.asynccontextmanager` implements startup and shutdown.
- Third party: `fastapi.FastAPI`, `CORSMiddleware`, `FileResponse`, `RedirectResponse`, and `StaticFiles` create the API, optional CORS handling, and frontend delivery.
- Internal: API authentication, middleware, and routers are same-app dependencies; `doc_agent_common` supplies settings and the tunnel; `doc_agent_core` supplies embeddings, generation, rails, and query orchestration; `doc_agent_db.RagRepository` supplies persistence. This is the composition root where all package directions meet.
- Runtime: loaded by `doc-agent-api`. Uses database, SSH, Gemini, JWT, HMAC, path, rate-limit, CORS, and development-auth environment settings.

### `apps/api/src/doc_agent_api/run.py`

Starts Uvicorn with access logs disabled so patient IDs in URL paths are not logged. `main` is the console entry point.

- Standard library: `os` reads `API_HOST` and `API_PORT`; `sys` selects the Windows path; `asyncio` creates a selector-loop runner on Windows so Psycopg can operate under Uvicorn.
- Third party: `uvicorn` runs ASGI.
- Internal: `doc_agent_common.runtime.configure_asyncio_for_psycopg` applies the Windows event-loop policy before startup.
- Runtime: `doc-agent-api`; `API_HOST`, `API_PORT`.

### `apps/api/src/doc_agent_api/middleware.py`

Adds request IDs, cache and browser security headers, a development-aware CSP, and bounded in-process doctor rate limiting. Main types are `RequestSecurityMiddleware`, `DoctorRateLimiter`, and `rate_limit_response`.

- Standard library: `hashlib` hashes local limiter keys; `logging` records non-sensitive events; `secrets` creates a process salt; `time` maintains the rolling window; `uuid` creates request IDs; `defaultdict` and `deque` store timestamp queues; `Awaitable` and `Callable` type middleware callbacks.
- Third party: FastAPI `Request`/`Response` and Starlette `BaseHTTPMiddleware`/`JSONResponse` implement ASGI middleware and responses.
- Internal: none; middleware stays independent of application services.

### `apps/api/src/doc_agent_api/schemas.py`

Defines Pydantic request and response contracts for questions, citations, retrieval metadata, and patient-directory pages.

- Standard library: `datetime` types recent-selection timestamps; `Literal` constrains status values.
- Third party: Pydantic `BaseModel`, `ConfigDict`, and `Field` validate and serialize API data.
- Internal: none, which keeps HTTP schemas separate from core dataclasses.

### `apps/api/src/doc_agent_api/dependencies/__init__.py`

Marks the dependency package. No imports or runtime behavior.

### `apps/api/src/doc_agent_api/dependencies/authentication.py`

Validates bearer JWT signatures, issuer, audience, expiry, doctor subject, and the patient claim. `authenticated_principal` handles general authentication; `authorized_principal` additionally checks the route patient.

- Standard library: `asyncio` runs synchronous JWKS/JWT work outside the event loop; `dataclass` defines `DoctorPrincipal`; `Annotated` and `Any` express dependency and decoded-claim types.
- Third party: `PyJWT` verifies tokens and retrieves JWKS; FastAPI dependency, exception, path, request, status, and HTTP bearer classes enforce the route contract.
- Internal: `AppSettings` supplies identity-provider configuration. Direction is API to common.
- Environment: `JWT_ISSUER`, `JWT_AUDIENCE`, `JWT_JWKS_URL`, `JWT_ALGORITHMS`, `JWT_PATIENT_IDS_CLAIM`, `JWT_DOCTOR_ID_CLAIM`.

### `apps/api/src/doc_agent_api/dependencies/services.py`

Reads already-initialized services from `app.state` for FastAPI dependency injection. Functions return settings, repository, query service, and rate limiter.

- Standard library: `typing.cast` narrows FastAPI's dynamic application-state attributes to their declared service types.
- Third party: FastAPI `Request` provides application state.
- Internal: middleware, common settings, core query service, and DB repository provide precise return types. Direction is API to packages.

### `apps/api/src/doc_agent_api/routers/__init__.py`

Marks the router package. No imports or runtime behavior.

### `apps/api/src/doc_agent_api/routers/health.py`

Defines the unauthenticated `GET /health` process check.

- Third party: FastAPI `APIRouter` registers the endpoint.
- Internal and standard-library imports: none.

### `apps/api/src/doc_agent_api/routers/runtime_config.py`

Defines `GET /v1/runtime-config`. It exposes only the development-auth enabled flag and local public URL.

- Standard library: `Annotated` types the injected settings.
- Third party: FastAPI router/dependency classes and Pydantic `BaseModel` define the endpoint and response.
- Internal: API `get_settings` retrieves `doc_agent_common.AppSettings`. Direction is API to common.
- Environment: `DEV_AUTH_ENABLED`, `DEV_AUTH_PUBLIC_URL`.

### `apps/api/src/doc_agent_api/routers/patients.py`

Implements patient search, recent selection, and history queries. It applies authorization and rate limits before repository or RAG calls, converts internal objects to API schemas, and logs only hashes/counts/latency/decisions.

- Standard library: `time` measures latency; `Annotated` types dependencies.
- Third party: FastAPI router, dependency, exception, parameter, request, and response classes implement the HTTP endpoints.
- Internal: authentication and service dependencies enforce the API boundary; API schemas serialize output; middleware supplies rate limiting and safe logging; common settings/security supply HMAC keys; core query service performs RAG; DB repository handles directory and recent data. Direction is API to common/core/DB.
- Environment: JWT settings, `RECENT_PATIENT_HMAC_KEY`, `API_RATE_LIMIT_PER_MINUTE`.

## Worker application

### `apps/worker/src/doc_agent_worker/__init__.py` and `pipelines/__init__.py`

Mark the worker packages. They have no imports or runtime behavior.

### `apps/worker/src/doc_agent_worker/main.py`

Provides an optional combined CLI that selects the `index` or `contacts` pipeline.

- Standard library: `argparse` parses the pipeline name.
- Internal: imports both pipeline `main` functions. Direction stays within the worker app.

### `apps/worker/src/doc_agent_worker/run.py`

Exports the two focused console entry functions `run_index` and `run_contact_sync`.

- Internal: imports the index and contact pipeline entry points. No standard-library or third-party imports.
- Runtime: `doc-agent-index` and `doc-agent-contact-sync`.

### `apps/worker/src/doc_agent_worker/pipelines/patient_index.py`

Runs an auditable full pgvector refresh. `build_index` aggregates, chunks, reuses unchanged vectors, embeds missing chunks, and atomically replaces the index. `main` is the safe CLI boundary.

- Standard library: `asyncio` coordinates I/O and model threads; `sys` writes safe failures; `uuid` creates ingestion run IDs.
- Internal: common settings/runtime/tunnel establish configuration and connectivity; core chunking/embedding/state provide the RAG transform; DB repository/source queries read and write PostgreSQL. Direction is worker to all shared packages.
- Runtime: `doc-agent-index`; database, SSH, model cache, and embedding metadata settings.

### `apps/worker/src/doc_agent_worker/pipelines/contact_sync.py`

Reads approved source fields over SSH and refreshes the separate SQLite contact snapshot. `prepare` performs the work and `main` parses the project path.

- Standard library: `argparse` handles CLI input; `asyncio` runs the source reader and thread-bound SQLite work; `json` prints a non-identifying summary; `Path` resolves repository files.
- Internal: DB `contact_source` reads the approved remote rows; DB `contact_store` writes clinical/contact tables. The RAG package is intentionally not imported.
- Runtime: `doc-agent-contact-sync`; database settings from `.env`, `Keys/health.pem`, and `data/patient_index.sqlite3`.

## Development authentication application

### `apps/dev-auth/src/doc_agent_dev_auth/__init__.py`

Marks the package. No imports or runtime behavior.

### `apps/dev-auth/src/doc_agent_dev_auth/keys.py`

Creates one in-memory RSA key and random `kid`, returns its public JWK, and signs RS256 tokens. `DevelopmentSigningKey.generate`, `jwks`, and `encode` are the main methods.

- Standard library: `base64` creates JWK modulus/exponent text; `secrets` generates the key ID; `dataclass` holds key state.
- Third party: `PyJWT` signs tokens; `cryptography.rsa` generates and represents the RSA key.
- Internal: none. Private key material never leaves the process.

### `apps/dev-auth/src/doc_agent_dev_auth/schemas.py`

Validates local doctor IDs and one to 500 unique patient IDs, and defines the token response.

- Third party: Pydantic model, config, field, and validator types perform request validation.
- Standard-library and internal imports: none.

### `apps/dev-auth/src/doc_agent_dev_auth/main.py`

Builds the local FastAPI identity service, rejects non-loopback clients, configures one allowed frontend origin, serves health/JWKS, and issues maximum one-hour tokens.

- Standard library: `UTC`, `datetime`, and `timedelta` create `iat` and `exp` claims.
- Third party: FastAPI, CORS middleware, and Starlette middleware/response types implement the service.
- Internal: common `DevAuthSettings` supplies safe local configuration; local keys and schemas implement signing and validation. Direction is app to common.
- Environment: `DEV_AUTH_ISSUER`, `DEV_AUTH_AUDIENCE`, `DEV_AUTH_ALLOWED_ORIGIN`, `DEV_AUTH_TOKEN_LIFETIME_SECONDS`.

### `apps/dev-auth/src/doc_agent_dev_auth/run.py`

Starts Uvicorn on fixed loopback address `127.0.0.1:8001` with access logs disabled.

- Third party: `uvicorn` runs the ASGI service.
- Runtime: `doc-agent-dev-auth`.

## Common package

### `packages/common/src/doc_agent_common/__init__.py`

Marks the shared package. No imports or runtime behavior.

### `packages/common/src/doc_agent_common/config.py`

Loads `.env` plus process overrides into immutable `AppSettings` and `DevAuthSettings`, validates ports, model/auth values, and loopback development URLs, and builds escaped PostgreSQL connection information.

- Standard library: `os` reads process settings; `dataclass`/`field` define immutable settings and hide secrets from representations; `Path` resolves files; `urlparse` validates local URLs.
- Third party: `python-dotenv.dotenv_values` reads literal `.env` values; `psycopg.make_conninfo` safely quotes PostgreSQL connection fields.
- Internal: none. This is a lowest-level package.
- Environment: every variable listed in `.env.example` except the latency-only token.

### `packages/common/src/doc_agent_common/runtime.py`

Selects the Windows selector event-loop policy required by async Psycopg/SSH subprocess behavior.

- Standard library: `asyncio` changes the policy; `sys` detects Windows.
- Third-party and internal imports: none.

### `packages/common/src/doc_agent_common/security.py`

Creates the HMAC-SHA256 doctor storage key used for recent selections.

- Standard library: `hashlib` selects SHA-256; `hmac` authenticates the doctor identity with a secret key.
- Third-party and internal imports: none.
- Environment: caller supplies `RECENT_PATIENT_HMAC_KEY`.

### `packages/common/src/doc_agent_common/ssh_tunnel.py`

Owns the OpenSSH port-forward subprocess and readiness checks. `SshTunnel` is an async context manager that always terminates its child process.

- Standard library: `asyncio` manages the subprocess and probes; `subprocess` supplies Windows flags; `sys` selects platform behavior; `dataclass` stores state; `Self` types context-manager return values.
- Internal: `AppSettings` supplies host, port, user, key, and known-hosts paths. Direction stays within common.

## Core RAG package

### `packages/core-rag/src/doc_agent_core/__init__.py`

Marks the package. No imports or runtime behavior.

### `packages/core-rag/src/doc_agent_core/state.py`

Defines typed dataclasses and aliases for facts, chunks, vectors, patient summaries, directory pages, retrieval rankings, and ingestion results.

- Standard library: `dataclass` defines immutable records; `datetime` types recent selections; `Literal` constrains clinical domains.
- Third party: NumPy and `numpy.typing.NDArray` define float-vector values.
- Internal: none; other packages may depend on these neutral types.

### `packages/core-rag/src/doc_agent_core/chunking.py`

Canonicalizes clinical facts, computes deterministic hashes and chunk IDs, merges repeated facts across admissions, and performs tokenizer-aware splitting without truncation. Main function: `build_chunk_drafts`.

- Standard library: `hashlib` creates SHA-256 identifiers; `json` creates sorted canonical facts; `re` splits text boundaries; `defaultdict` groups facts; `Mapping`/`Sequence` type inputs; `Protocol` describes the tokenizer without importing Transformers directly.
- Internal: common constants pin schema/model versions; core state supplies fact/chunk/domain records.

### `packages/core-rag/src/doc_agent_core/embeddings.py`

Loads the pinned Sentence Transformers model, batch-encodes normalized vectors, and asserts 384 dimensions. `MiniLmEmbedder` exposes its tokenizer and `encode` method.

- Standard library: `Sequence` and `Any` type model inputs without tying public interfaces to library internals.
- Third party: NumPy validates and normalizes arrays; `sentence-transformers` is imported lazily inside the class to load the Hugging Face model.
- Internal: common embedding constants enforce the model/revision/dimension; core `FloatVector` defines output type.

### `packages/core-rag/src/doc_agent_core/retrieval.py`

Recognizes structured/count questions, maps requested domains, fuses dense and keyword ranks with weighted RRF, and applies cosine MMR diversity.

- Standard library: `re` classifies questions; `Sequence` types candidate lists.
- Third party: NumPy calculates cosine similarity.
- Internal: core state supplies domain, vector, ranked, and stored chunk types.

### `packages/core-rag/src/doc_agent_core/generation.py`

Builds de-identified labeled context, calls Gemini for structured JSON, validates every inline citation, and returns only supplied chunks. It also removes patient/admission IDs and email patterns from questions.

- Standard library: `re` validates citations and redacts email; `dataclass` defines `GeneratedAnswer`; `Any` types SDK responses.
- Third party: Pydantic validates the model response; `google-genai` is imported lazily for the runtime client and request types.
- Internal: common settings select key/model; core `StoredChunk` defines context records.
- Environment: `GEMINI_API_KEY`, `GEMINI_MODEL`.

### `packages/core-rag/src/doc_agent_core/guardrails.py`

Provides deterministic input/output policy checks and wraps generation with NeMo input/output rails. Any rail error denies the response.

- Standard library: `re` implements deterministic checks; `Any`/`Literal` type NeMo results and stages.
- Third party: `langchain-google-genai` and `nemoguardrails` are imported lazily in `GuardrailEngine` because NeMo's supported provider integration requires them. A small provider subclass translates NeMo's generic `max_tokens` argument to Google's `max_output_tokens` field and accepts NeMo's structured response object.
- Internal: common settings supply Gemini and guardrail paths.
- Environment: `GEMINI_API_KEY`, `GEMINI_MODEL`, `GUARDRAILS_PATH`.

### `packages/core-rag/src/doc_agent_core/query_service.py`

Coordinates input rails, structured or hybrid retrieval, question redaction, Gemini generation, output rails, and citation-bound results. `HistoryRepository` is the persistence protocol; `HistoryQueryService.query` is the main operation.

- Standard library: `asyncio` runs independent retrieval branches concurrently; `Sequence` types results; `dataclass` defines response metadata; `Literal`/`Protocol` define statuses and the repository boundary.
- Internal: common settings/model name; core embedding, generation, guardrail, state, and retrieval modules. It deliberately has no DB import, allowing the API to inject any compliant repository.

## Database package

### `packages/db/src/doc_agent_db/__init__.py`

Marks the package. No imports or runtime behavior.

### `packages/db/src/doc_agent_db/connection.py`

Creates async Psycopg connections and registers pgvector codecs. `DatabaseConnectionFactory.connection` is an async context manager.

- Standard library: `AsyncIterator` and `asynccontextmanager` type and implement connection cleanup.
- Third party: `pgvector.psycopg.register_vector_async` enables vector values; Psycopg `AsyncConnection` handles PostgreSQL I/O.
- Internal: common `AppSettings` supplies escaped connection information. Direction is DB to common.

### `packages/db/src/doc_agent_db/source_queries.py`

Runs the four SQL aggregation domains against `public.clinical_records` and converts rows into core facts. `read_aggregated_facts` returns facts, source-row count, and patient counts.

- Standard library: `cast` narrows database values.
- Third party: Psycopg async connection and `dict_row` execute typed parameterized queries.
- Internal: core `AggregatedFact` and `ClinicalDomain` carry neutral results. Direction is DB to core state.

### `packages/db/src/doc_agent_db/rag_repository.py`

Implements ingestion audit rows, embedding reuse, atomic index replacement, dense/keyword/structured retrieval, summaries, authorized directory search, and recent selection retention.

- Standard library: `uuid` identifies ingestion runs; collection ABCs type mappings/sequences/iterators; `asynccontextmanager` exposes connections; `datetime` types timestamps; `cast` narrows rows.
- Third party: NumPy handles stored vectors; `pgvector.Vector` adapts query vectors; Psycopg connection, `dict_row`, and `Jsonb` execute parameterized PostgreSQL statements.
- Internal: common model/version/settings values; DB connection factory; core state records. Direction is DB to common and core types.

### `packages/db/src/doc_agent_db/contact_schema.py`

Declares approved source, clinical, and excluded column tuples. It has no imports. Email and demographic columns stay outside RAG content by construction.

### `packages/db/src/doc_agent_db/contact_source.py`

Loads the older contact-sync database settings and reads approved rows through a remote Python/psql process over SSH without putting the password on the command line.

- Standard library: `asyncio` manages SSH; `json` carries stdin/stdout payloads; `shlex` quotes remote code; `dataclass`/`field` define settings and hide the password; `Path` validates files.
- Third party: `python-dotenv` reads the private environment file literally.
- Internal: `contact_schema.SOURCE_COLUMNS` builds the explicit projection.

### `packages/db/src/doc_agent_db/contact_store.py`

Builds an atomic SQLite snapshot, keeps duplicate clinical rows, hashes deterministic record IDs, redacts email patterns, and stores contacts separately. Main functions: `build_patient_index` and `get_patient_records`.

- Standard library: `hashlib`, `json`, and `re` create IDs/serialized records/redaction; `sqlite3` stores the snapshot; `Counter` computes summary counts; `closing` ensures cleanup; `Path` handles files.
- Internal: contact source/schema provide row typing and approved column lists. It has no RAG or Gemini dependency.

## Evaluation modules

### `evals/__init__.py`, `evals/metrics/__init__.py`, and `evals/scripts/__init__.py`

Mark evaluation packages. They have no imports or runtime behavior.

### `evals/metrics/retrieval_metrics.py`

Calculates Precision@5, Recall@5, NDCG@5, and averages for labeled result sets.

- Standard library: `math` computes logarithmic discounts; `Mapping`/`Sequence` type labels and ranks; `dataclass` defines `RetrievalMetrics`.
- Third-party and internal imports: none.

### `evals/scripts/run_retrieval_benchmark.py`

Loads at least 30 labels, runs dense-only, keyword-only, and hybrid/MMR retrieval against one indexed patient, checks injection isolation, and applies acceptance thresholds.

- Standard library: `asyncio` coordinates retrieval; `json` loads/prints data; `asdict` serializes metrics; `Path` finds datasets; `TypedDict`/`cast` type labels.
- Third party: Psycopg `dict_row` selects one indexed patient.
- Internal: evaluation metrics score results; common settings/runtime/tunnel establish access; core embedding/state/retrieval perform fixed-model ranking; DB repository queries the live index.
- Runtime: `python -m evals.scripts.run_retrieval_benchmark`; database/SSH/model settings.

### `evals/scripts/run_safety_evaluation.py`

Runs the retained adversarial input/output phrases through deterministic rails and writes only aggregate counts to `evals/reports/safety_evaluation.json`.

- Standard library: `json` reads/writes the dataset/report; `Path` resolves the project.
- Internal: core deterministic input/output checks are the evaluated behavior.
- Runtime: `python -m evals.scripts.run_safety_evaluation`.

## Operator scripts

### `scripts/apply_migrations.py`

Concatenates ordered idempotent migrations and sends them through encrypted stdin to privileged `psql` on the Ubuntu EC2 host. It never prints SQL or credentials.

- Standard library: `asyncio` runs SSH; `json` builds the stdin payload; `shlex` quotes remote Python; `sys` reports safe status.
- Internal: common `AppSettings` supplies database and SSH configuration.
- Runtime: `python scripts/apply_migrations.py`; database and SSH environment settings.

### `scripts/verify_storage.py`

Checks installed pgvector/schema/index/version/count invariants and emits aggregate JSON.

- Standard library: `asyncio` coordinates checks; `json` prints aggregate output.
- Third party: Psycopg `dict_row` names result fields.
- Internal: common constants/settings/runtime/tunnel and DB repository connect to the live store.

### `scripts/verify_retrieval.py`

Runs safe live retrieval checks, including a malicious patient string, and prints counts rather than clinical content.

- Standard library: `asyncio` coordinates queries; `json` prints aggregates.
- Third party: Psycopg `dict_row` selects safe metadata.
- Internal: common settings/runtime/tunnel and DB repository access the live index.

### `scripts/benchmark_latency.py`

Measures repeated authorized history-query latency and prints run count, mean, median, and p95 without printing the token, patient ID, question, or answer.

- Standard library: `argparse` parses the authorized patient and options; `asyncio` runs HTTP calls; `json` prints metrics; `os` reads the token from process memory; `statistics` computes aggregates; `time` measures durations.
- Third party: `httpx` performs async HTTP requests.
- Runtime: `python scripts/benchmark_latency.py`; `DOC_AGENT_BENCHMARK_TOKEN` plus command-line API URL, patient, question, and run count.
