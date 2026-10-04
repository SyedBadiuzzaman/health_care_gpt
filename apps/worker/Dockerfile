FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.12.5 /uv /uvx /bin/
WORKDIR /workspace
COPY . .
RUN uv sync --frozen --no-dev --package doc-agent-worker
ENV PATH="/workspace/.venv/bin:$PATH"
CMD ["doc-agent-index"]
