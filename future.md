# Future Work

## Tool Description Accuracy

**Status:** Resolved in the declarative-registration refactor.

Tools are now registered as explicit `(name, handler, title)` entries in `_READ_ONLY_TOOLS` / `_WRITE_TOOLS` in `word_document_server/main.py`, and `_register_tool()` attaches the handler function itself to the MCP server. Each tool's `fn` resolves to a module-level function (e.g. `word_document_server.tools.content_tools.add_paragraph`) instead of a `register_tools.<locals>` closure, so static scanners can resolve every tool → handler.

Tool descriptions are read straight from the handler docstrings in `word_document_server/tools/*.py`, which carry full `Args:` sections. FastMCP parses those sections and injects per-parameter descriptions into the JSON schema. Public names, titles, parameter names, and the four hints are unchanged from the prior wrappers (verified against a captured baseline: 54/54, zero deprecation warnings).

**Follow-up:** Re-run the M8ven scan and confirm the description-accuracy check now resolves handlers.

## Authentication

**Status:** Not implemented — anonymous access only.

**Note:** Currently the MCP server has no authentication. This is acceptable for local stdio transport but would be needed for network-exposed deployments (streamable-http, sse).

## Rate Limiting

**Status:** Not implemented.

**Note:** No rate limiting is in place. This is acceptable for local single-user usage but should be considered for multi-user or network-exposed deployments.
