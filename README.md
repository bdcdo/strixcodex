# strixcodex

Local OpenAI-compatible proxy that bridges **Strix AI** (autonomous pentest agent)
to the **ChatGPT Codex backend**, so you can run Strix using your **ChatGPT Pro**
subscription instead of paying for OpenAI API tokens.

Inspired by and reusing OAuth code from
[`simonw/llm-openai-via-codex`](https://github.com/simonw/llm-openai-via-codex)
(Apache-2.0).

```
Strix (LiteLLM, Chat Completions)
        ↓ http://localhost:8787/v1/chat/completions
strixcodex proxy   ← translates Chat Completions ↔ Responses
        ↓ https://chatgpt.com/backend-api/codex/responses
ChatGPT Codex backend (auth via OAuth from ~/.codex/auth.json)
```

## Why this exists

- Strix uses LiteLLM and speaks `/chat/completions`.
- The ChatGPT Codex backend only speaks the Responses API (`/responses`).
- This proxy translates between the two formats, including streaming SSE and tool calls,
  while reusing the OAuth tokens that the official `codex` CLI stores locally.

## Prerequisites

- ChatGPT Pro (or Plus, with Codex access).
- [`codex`](https://github.com/openai/codex) CLI installed and logged in (`codex login`).
- Python 3.10+, [`uv`](https://docs.astral.sh/uv/) (or `pip`).
- Strix AI installed (see [docs.strix.ai](https://docs.strix.ai/)).

## Install

```bash
uv sync
# or:
pip install -e .
```

## Run the proxy

Strix runs inside a Docker container, so the proxy must listen on `0.0.0.0`
and Strix must dial it via `host.docker.internal` (which Strix already maps
to `host-gateway` automatically — see `strix/runtime/docker_runtime.py`).

```bash
uv run python -m strixcodex --host 0.0.0.0
# listens on http://0.0.0.0:8787
```

Smoke test (from the host):

```bash
curl -fsS http://127.0.0.1:8787/healthz
curl -fsS http://127.0.0.1:8787/v1/models | jq
curl http://127.0.0.1:8787/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "gpt-5.4",
    "messages": [{"role":"user","content":"reply with the word ok"}]
  }'
```

## Run Strix through the proxy

Strix runs a connectivity probe against `LLM_API_BASE` from the host **before**
launching its Docker sandbox (`strix/interface/main.py:230`). On Linux,
`host.docker.internal` does not resolve on the host, only inside containers,
so the URL must use an IP that works from both sides — the `docker0` bridge
gateway (typically `172.17.0.1`) does.

```bash
# from the directory you want Strix to analyze
export STRIX_LLM="openai/gpt-5.4"
export LLM_API_KEY="anything-non-empty"
export LLM_API_BASE="http://172.17.0.1:8787/v1"
strix -t .
```

Or use the helper that boots the proxy and exports the right env:

```bash
cd /path/to/target
/path/to/strixcodex/scripts/run-strix.sh -t .
```

On startup the helper checks PyPI for a newer `strix-agent` release and, in an
interactive terminal, asks whether to run `uv tool upgrade strix-agent` before
launching. The check is non-blocking — if you are offline or PyPI is
unreachable it is skipped silently — and non-interactive runs only print the
upgrade command. It runs at most once a day, caching the result under `$XDG_CACHE_HOME/strixcodex` (default `~/.cache/strixcodex`). Disable it entirely with `STRIX_VERSION_CHECK=0`.

## Tests

```bash
uv run pytest
```

Translator tests cover round-trips of: simple prompts, system messages, tool definitions,
assistant-with-tool-call → tool-result chains, image attachments, streaming text deltas,
and streaming tool-call argument assembly.

## Limitations and caveats

- The Codex endpoint is **semi-official**: tolerated by OpenAI ("use Codex wherever you
  like" — Romain Huet, OpenAI) but not a public API. It can change without notice.
- Run the proxy **bound to 127.0.0.1 only**. Do not expose it.
- Strix executes code autonomously. With this setup it runs against **your personal
  ChatGPT account** — only target systems you are authorized to test.
- The Codex backend may have stricter rate / context limits than the paid API.
- Embeddings, image generation, and audio endpoints are **not** implemented; only
  `/v1/chat/completions` and `/v1/models`.

## License

MIT for the original code in this repo. The vendored `borrow_codex_key` helper
in `strixcodex/auth.py` is Apache-2.0 from `simonw/llm-openai-via-codex`.
