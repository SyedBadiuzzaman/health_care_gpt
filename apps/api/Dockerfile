FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.12.5 /uv /uvx /bin/
WORKDIR /workspace
COPY . .
RUN uv sync --frozen --no-dev --package doc-agent-api
ENV PATH="/workspace/.venv/bin:$PATH" API_HOST=0.0.0.0 API_PORT=8000
EXPOSE 8000
CMD ["doc-agent-api"]
