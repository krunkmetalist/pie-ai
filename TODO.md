# Pie.ai Enhancements Tracker

## 🟢 Easy (Implemented)
- [x] Fix CLI entrypoint in `pyproject.toml` and `proxy.py`.
- [x] Fix test suite paths in `README.md`.
- [x] Catch `json.JSONDecodeError` instead of bare `Exception` in payload parsing.
- [x] Move forbidden tools configuration to an environment variable (`FORBIDDEN_TOOLS`).

## 🟡 Medium (Up Next)
- [ ] **Streaming Support**: Handle `stream: true` requests. Currently, the proxy tries to parse Server-Sent Events (SSE) as JSON, which will crash. Fix by using FastAPI's `StreamingResponse` to pipe chunks back to the client.
- [ ] **Wildcard Routing**: Proxy all OpenAI-compatible paths (like `/v1/models`) instead of just `/v1/chat/completions`.

## 🔴 Hard (Future Roadmap)
- [ ] **Semantic Prompt Injection**: Integrate a lightweight classifier (like `ProtectAI/deberta-v3-base-injection`) instead of relying on exact string matching.
- [ ] **Accurate Token Counting**: Implement `tiktoken` for robust context bloat guarding rather than using raw character counts.
