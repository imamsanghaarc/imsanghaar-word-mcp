# Future Work

## Tool Description Accuracy

**M8ven finding:** "No tool handlers could be resolved, so descriptions could not be checked against behavior."

**Cause:** All 54 tools are decorated inside `register_tools()` in `word_document_server/main.py:91`, and each wrapper just delegates to a handler in another module (e.g. `content_tools.add_paragraph`) with no `return`-visible import of its own. Static scanners cannot resolve the wrapper → handler mapping, so they skip the check entirely.

**What to do:**
1. Verify each wrapper's docstring describes the same behavior as the underlying handler (the handlers in `word_document_server/tools/*.py` already have full `Args:` sections).
2. Make the delegation statically resolvable — either copy the handler docstrings onto the wrappers or register the handler functions directly:
   `@mcp.tool(annotations=...)` on a thin wrapper that does `return content_tools.add_paragraph(...)`
   instead of `def add_paragraph(...)` with a re-typed signature.
3. Re-run the M8ven scan and confirm the description-accuracy check resolves.

## Authentication

**Status:** Not implemented — anonymous access only.

**Note:** Currently the MCP server has no authentication. This is acceptable for local stdio transport but would be needed for network-exposed deployments (streamable-http, sse).

## Rate Limiting

**Status:** Not implemented.

**Note:** No rate limiting is in place. This is acceptable for local single-user usage but should be considered for multi-user or network-exposed deployments.
