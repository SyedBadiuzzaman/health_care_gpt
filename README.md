# Doc Agent RAG Platform

This repository is a uv monorepo for patient-scoped medical-history retrieval. It keeps the existing PostgreSQL and pgvector data on the configured AWS EC2 host, creates embeddings locally with `sentence-transformers/all-MiniLM-L6-v2`, and uses Gemini only for citation-bound historical summaries.

## Repository layout

```text
apps/api/          FastAPI routes, JWT authorization, middleware, static web serving
apps/worker/       Explicit indexing and contact-sync CLI jobs
apps/dev-auth/     Loopback-only JWT issuer for local testing
apps/web/          Dependency-free HTML, CSS, and JavaScript interface
packages/core-rag/ Chunking, MiniLM, hybrid retrieval, Gemini, and guardrails
packages/db/       PostgreSQL, pgvector, source SQL, migrations, contact SQLite
packages/common/   Settings, HMAC helpers, SSH tunnel, Windows runtime setup
evals/             Retained retrieval and adversarial safety evaluation assets
scripts/           Migration, storage, retrieval, and latency utilities
docs/              Architecture and module/import documentation
infra/             Boundary note for infrastructure that does not yet exist
```

Celery, Redis, Kafka, Qdrant, LangGraph, LlamaIndex, Terraform, and Kubernetes are intentionally absent because no running component uses them.

## Local setup on Windows

Install Python 3.12 and [uv](https://docs.astral.sh/uv/), then run from the repository root:

```powershell
Copy-Item .env.example .env
uv sync --all-packages
```

Keep your existing private `.env`, `Keys/health.pem`, `Keys/known_hosts`, and `models/` directory if they are already configured. Do not commit them.

For local login, use these values in `.env`:

```dotenv
DEV_AUTH_ENABLED=true
DEV_AUTH_PUBLIC_URL=http://127.0.0.1:8001
DEV_AUTH_ISSUER=http://127.0.0.1:8001
DEV_AUTH_AUDIENCE=doc-agent
DEV_AUTH_JWKS_URL=http://127.0.0.1:8001/.well-known/jwks.json
DEV_AUTH_ALLOWED_ORIGIN=http://127.0.0.1:8000
```

Open two PowerShell terminals in the repository root. Start the local identity service first:

```powershell
uv run doc-agent-dev-auth
```

Start the API in the second terminal:

```powershell
uv run doc-agent-api
```

Open [http://127.0.0.1:8000/app](http://127.0.0.1:8000/app). The **Local development access** panel asks for a doctor ID and comma-separated patient IDs. Enter real indexed patient IDs that the test doctor should be allowed to access. The development server signs a maximum one-hour RS256 token. The browser stores it only in memory, so reloading clears the session.

The token authorizes exactly the values in its `patient_ids` array. A request for another patient returns HTTP `403`. In production, set `DEV_AUTH_ENABLED=false` and configure `JWT_ISSUER`, `JWT_AUDIENCE`, and `JWT_JWKS_URL` for the real identity provider.

## AWS EC2 database access

When `DATABASE_USE_SSH_TUNNEL=true`, both the API and indexing worker run the local `ssh` command with the configured Ubuntu user and private key. They forward `DATABASE_TUNNEL_LOCAL_PORT` to PostgreSQL on the EC2 host. The application then connects to `127.0.0.1` at that forwarded port.

The API retrieves data from the EC2-backed `rag.patient_chunks`, `rag.patient_summaries`, and `rag.doctor_recent_patients` tables. It does not copy the main RAG database to the PC. The `models/` cache and the optional SQLite contact snapshot remain local.

Required SSH settings are:

```dotenv
DATABASE_HOST=your-ec2-host
DATABASE_USE_SSH_TUNNEL=true
SSH_USER=ubuntu
SSH_KEY_PATH=Keys/health.pem
SSH_KNOWN_HOSTS_PATH=Keys/known_hosts
```

## Database preparation and indexing

The migration command uses administrative SSH access and applies the idempotent SQL files in `packages/db/migrations`:

```powershell
uv run python scripts/apply_migrations.py
```

Build or refresh the pgvector index:

```powershell
uv run doc-agent-index
```

The refresh reuses unchanged embeddings, writes a complete successful run atomically, and removes stale chunks only after the new index succeeds.

Synchronize the isolated local contact snapshot separately:

```powershell
uv run doc-agent-contact-sync --project .
```

Email never enters RAG chunks, embeddings, retrieved context, Gemini prompts, or API responses. The contact pipeline redacts email-like text from its clinical document representation and stores addresses in a separate SQLite table.

## HTTP interfaces

- `GET /health` checks API process health.
- `GET /v1/runtime-config` reveals only whether local development auth is enabled and its loopback URL.
- `GET /v1/patients?search=&limit=50&offset=0` lists indexed patients intersected with the JWT claim.
- `POST /v1/patients/{patient_id}/selection` records a hashed-doctor recent selection.
- `POST /v1/patients/{patient_id}/history-query` performs authorized historical retrieval and generation.
- `GET /.well-known/jwks.json`, `POST /v1/token`, and `GET /health` belong to the separate development auth service on port 8001.

The API frontend can also be started by another trusted host page:

```javascript
window.DocAgentApp.start({
  getAccessToken: async () => token,
  doctorDisplayName: "Doctor",
  onUnauthorized: () => {},
});
```

## Operational verification

These commands emit aggregate information and avoid clinical text and identifiers:

```powershell
uv run python scripts/verify_storage.py
uv run python scripts/verify_retrieval.py
uv run python -m evals.scripts.run_safety_evaluation
uv run python -m evals.scripts.run_retrieval_benchmark
```

For latency measurements, place a short-lived token in the process environment and pass an authorized patient ID:

```powershell
$env:DOC_AGENT_BENCHMARK_TOKEN = "temporary-token"
uv run python scripts/benchmark_latency.py patient-id --runs 5
Remove-Item Env:DOC_AGENT_BENCHMARK_TOKEN
```

## Docker

Validate and start the production-like API container with:

```powershell
docker compose config
docker compose up --build api
```

Run indexing as an explicit profile:

```powershell
docker compose --profile worker run --rm worker
```

The development auth service is intentionally run directly on the host because its security boundary requires loopback. Its Dockerfile exists for reproducible image validation, but the root Compose deployment does not expose it.

## Deployment boundaries

Use a real identity provider in production. Terminate TLS and apply distributed rate limiting at the gateway when multiple API workers are deployed. The API process keeps no chat history; browser transcripts disappear on reload. PostgreSQL remains the source for indexed history and recent-selection metadata, while Gemini receives only de-identified context.

See [Architecture](docs/ARCHITECTURE.md) for the component diagram and [Module and Import Guide](docs/MODULE_AND_IMPORT_GUIDE.md) for every Python file and dependency.
