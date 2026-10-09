# Future Work

## Privacy Policy

This MCP server operates entirely locally on the user's machine. It does not collect, store, or transmit any personal data. All document processing happens locally. No user data is sent to external servers. The only network-related activity is the use of standard XML namespace URIs (schemas.openxmlformats.org, www.w3.org) by the python-docx library, which are not actual network calls.

## Tool Test Coverage

**Status:** RESOLVED - all 54/54 tools now referenced in tests (100%).

**Test file:** `tests/test_all_tools.py` - 57 passing tests covering every registered tool by name.

**Previous state (weak point):**
Only 4/54 tools were actually called in tests (7%) - `create_document`, `add_paragraph`, `add_heading`, `convert_to_pdf`. The remaining imports in `test_tools.py` were print-only statements, not real test calls.

**Other tests:**
- `tests/test_all_tools.py` - covers all 54 registered tools (new)
- `test_formatting.py` - formatting parameters for `create_document`, `add_paragraph`, `add_heading`
- `tests/test_convert_to_pdf.py` - `convert_to_pdf` end-to-end
- `test_tools.py` - legacy smoke script (imports only, prints status)

**Run with:** `python -m pytest tests/test_all_tools.py -q`

## Where We Left Off

### Completed
- Added all four hints (`readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`) to all 54 tools in `word_document_server/main.py`
- Created `tests/test_all_tools.py` with 57 passing tests referencing all 54 tools

### In Progress
- Nothing pending

### Remaining
1. ~~Create `tests/test_all_tools.py` with tests for all 54 tools~~ (done)
2. ~~Run the tests to verify they pass~~ (done — 57 passed)
3. Commit and push all changes (awaiting user approval)

## Authentication

**Status:** Not implemented — anonymous access only.

**Note:** Currently the MCP server has no authentication. This is acceptable for local stdio transport but would be needed for network-exposed deployments (streamable-http, sse).

## Rate Limiting

**Status:** Not implemented.

**Note:** No rate limiting is in place. This is acceptable for local single-user usage but should be considered for multi-user or network-exposed deployments.

## Tool Description Accuracy

**Status:** Scanner limitation — "No tool handlers could be resolved, so descriptions could not be checked against behaviour."

**Note:** This is a scanner limitation, not a code issue. The tool handlers exist and have proper docstrings. No action needed.
