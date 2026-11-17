# Security

## Reporting a vulnerability

Open a private security advisory on the repository. Do not open a public issue
for a vulnerability or include a working exploit in a public report.

## Secrets

- Never commit `GRPC_TOKEN`, a provider URL containing a token, wallet keys, or
  database credentials. Use environment variables; `.env` is ignored.
- The capture tool reads `GRPC_URL` and `GRPC_TOKEN` from the environment.
- If a token was committed or pasted into an issue, revoke it with the provider
  first, then remove it from history.

## Scope

The capture tool is a local gRPC client. It does not expose a network service.
The analysis pipeline reads local JSONL/Parquet files and DuckDB databases.
Treat captured provider data and third-party token metadata/URIs as untrusted
input.
