# Future Work

## Tool Description Accuracy

**Status:** Resolved in the declarative-registration refactor.

Tools are now registered as explicit `(name, handler, title)` entries in `_READ_ONLY_TOOLS` / `_WRITE_TOOLS` in `word_document_server/main.py`, and `_register_tool()` attaches the handler function itself to the MCP server. Each tool's `fn` resolves to a module-level function (e.g. `word_document_server.tools.content_tools.add_paragraph`) instead of a `register_tools.<locals>` closure, so static scanners can resolve every tool → handler.

Tool descriptions are read straight from the handler docstrings in `word_document_server/tools/*.py`, which carry full `Args:` sections. FastMCP parses those sections and injects per-parameter descriptions into the JSON schema. Public names, titles, parameter names, and the four hints are unchanged from the prior wrappers (verified against a captured baseline: 54/54, zero deprecation warnings).

Every tool's documented arguments were audited against its handler signature — all 54 match, and every tool now has an `Args:` section (the two that lacked one, `get_document_xml` and `replace_block_between_manual_anchors`, were completed).

**Follow-up:** Re-run the M8ven scan and confirm the description-accuracy check now resolves handlers.

## Authentication

**Status:** Partially implemented.

Local `stdio` use is gated by Sang Labs browser sign-in (`word_document_server/auth.py`): the first tool call opens the sign-in page, stores the resulting Supabase session under `~/.sanglabs/word-mcp/`, and refreshes it transparently. The hosted (HTTP) transports are intentionally refused by that middleware with a "use the local server" message, so server-side authentication for a network-exposed deployment is still **not available**.

## Rate Limiting

**Status:** Resolved.

`word_document_server/rate_limit.py` builds a FastMCP token-bucket middleware (`RateLimitingMiddleware`) and `run_server()` installs it as the outermost middleware. It is disabled for local `stdio` and enabled by default for the network transports (`streamable-http`, `sse`). Configuration (all optional):

- `MCP_RATE_LIMIT_ENABLED`: `auto` (default), `true`, or `false`
- `MCP_RATE_LIMIT_RPS`: sustained requests per second (default `10`)
- `MCP_RATE_LIMIT_BURST`: maximum burst capacity (default `2 x RPS`)
- `MCP_RATE_LIMIT_GLOBAL`: `true` for one shared bucket, `false` (default) for a bucket per client

