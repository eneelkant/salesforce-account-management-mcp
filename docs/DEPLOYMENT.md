# Deployment

## Local STDIO

```bash
./scripts/setup.sh
source .venv/bin/activate
salesforce-account-engagement-mcp
```

## Docker (Streamable HTTP)

```bash
cp .env.example .env   # fill secrets locally
docker compose up --build
```

- Container runs as non-root user `mcpuser` (uid 10001)
- Default `AE_READ_ONLY=true`
- Healthcheck runs `scripts/health_check.py --offline`
- `STOPSIGNAL SIGTERM` for graceful shutdown

## Remote HTTPS

1. Run Streamable HTTP behind a reverse proxy (nginx, Caddy, cloud LB).
2. Enforce HTTPS and network allowlists.
3. Store secrets in your platform secret manager.
4. Point ChatGPT / remote Gemini connectors at `https://host/mcp`.

## Configuration validation

CI and operators should run:

```bash
python scripts/health_check.py --offline
python -m json.tool examples/cursor-mcp.json
```
