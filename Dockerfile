# Production image for remote Streamable HTTP MCP deployments.
FROM python:3.12-slim AS builder

WORKDIR /build
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir --prefix=/install .

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MCP_TRANSPORT=streamable-http \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=8000 \
    AE_READ_ONLY=true

RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin mcpuser \
    && mkdir -p /app/.ae_tokens \
    && chown -R mcpuser:mcpuser /app

COPY --from=builder /install /usr/local
COPY --chown=mcpuser:mcpuser scripts/health_check.py /app/scripts/health_check.py

WORKDIR /app
USER mcpuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python /app/scripts/health_check.py --offline || exit 1

STOPSIGNAL SIGTERM

CMD ["salesforce-account-engagement-mcp", "--transport", "streamable-http", "--host", "0.0.0.0", "--port", "8000"]
