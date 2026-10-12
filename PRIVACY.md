# Privacy Policy

**Effective date:** 2026-10-12 (previously 2026-10-10)

## Overview

Office-Word-MCP-Server is a self-hosted Model Context Protocol (MCP) server
published as [`msow-imsanghaar-mcp`](https://pypi.org/project/msow-imsanghaar-mcp/).
This policy explains what data the server touches and why.

**The short version: the server processes only the files you point it at, runs
on your own machine, and the only thing it sends anywhere is a sign-in check
against your Sang Labs account.**

## Account and authentication (v1.2.0+)

Tool calls require a Sang Labs account:

- On the first tool call, the server opens your browser at
  `https://sanglabs.vercel.app/mcp/signup`, where you can sign up (name, email,
  occupation, password) or log in and click **Continue with this account**.
- The site hands your Supabase **session tokens** (access + refresh) to a
  loopback listener the server starts on `127.0.0.1` on your own machine
  (RFC 8252 native-app pattern). Only `http://127.0.0.1:<port>/callback` and
  `http://localhost:<port>/callback` redirect targets are ever accepted by the
  site, so tokens cannot be sent to a remote host.
- The session is stored in `~/.sanglabs/word-mcp/credentials.json` (file
  permissions set to owner-only where the filesystem supports it) and is
  refreshed automatically when the access token expires. Delete it or run
  `word_mcp_server --logout` to sign out; `--logout` also revokes the session
  server-side.
- Before accepting the browser handoff, the server verifies the access token
  with your Sang Labs project (`GET /auth/v1/user` on
  `jfnhntefueujmgpfonuy.supabase.co`). On each start it may refresh the session
  (`POST /auth/v1/token`) and record a `last_used_at` timestamp on your own
  connection row. No document content, filenames, or tool arguments are ever
  sent to Sang Labs.
- The browser handoff only works for the local `stdio` transport. Hosted
  (HTTP) deployments reject tool calls with an explanatory message.

The Sang Labs site (`sanglabs.vercel.app`) and its auth backend (Supabase)
have their own privacy policies covering the account itself.

## What the server does not collect

Office-Word-MCP-Server does **not**:

- collect, store, or transmit any personal data beyond the Sang Labs session
  described above
- include telemetry, analytics, crash reporting, or usage tracking
- read, scan, or index the contents of files you do not pass to it as an
  argument. The one exception is `list_available_documents`, which returns
  the names and sizes of the `.docx` files in the single directory you give
  it — it never opens them
- send anything to a project-controlled server other than the Sang Labs
  authentication checks described above

Beyond authentication, there is no project-operated backend. The maintainers
never see your documents, their contents, or your usage of the server.

## What happens to your documents

All document processing happens locally on the host where you run the server:

- Documents are opened, modified, and saved **on the local filesystem**, in
  place or to a destination path you specify.
- Document text stays in memory for the duration of a call and is discarded
  when the call returns.
- The PDF conversion tool shells out to LibreOffice (`libreoffice` / `soffice`)
  or `docx2pdf` (Microsoft Word) on your machine. No document content leaves
  the host for conversion.

Because the server never uploads your files, keeping them secure is a matter
of standard local filesystem permissions.

## Network activity

Version 1.2.0+ makes the following outbound requests, all to your Sang Labs
project (auth only — never document data):

- `GET https://jfnhntefueujmgpfonuy.supabase.co/auth/v1/user` — validate the
  session after the browser handoff
- `POST https://jfnhntefueujmgpfonuy.supabase.co/auth/v1/token` — refresh an
  expired session
- `POST https://jfnhntefueujmgpfonuy.supabase.co/auth/v1/logout` — only when
  you run `word_mcp_server --logout`
- `PATCH https://jfnhntefueujmgpfonuy.supabase.co/rest/v1/mcp_connections` —
  records a `last_used_at` timestamp on your own connection row

The URLs are overridable with `SANGLABS_SUPABASE_URL` /
`SANGLABS_SUPABASE_ANON_KEY` / `SANGLABS_SITE_URL`, and the local credentials
location with `SANGLABS_CREDENTIALS_PATH`.

In addition, the standard Open XML namespace URIs required by the Office Open
XML file format appear in the code:

- `http://schemas.openxmlformats.org/...`
- `http://www.w3.org/...`

These are XML namespace identifiers, not network endpoints. They are used
purely as identifiers inside the `.docx` file format and are never fetched,
resolved, or connected to.

The dependencies declared in `pyproject.toml` (`python-docx`, `fastmcp`,
`httpx`, `msoffcrypto-tool`, `docx2pdf`, `python-dotenv`, `pytest`) are
installed from public package indexes by your own package manager as part of
installation.

## Configuration and secrets

Configuration is read from local environment variables and an optional
`.env` file in your working directory. No API keys are bundled with the
server: the authentication credential is your own Sang Labs session, stored
under `~/.sanglabs/word-mcp/` on your machine.

If you choose to configure the optional network transports
(`streamable-http` or `sse`), the server has **no authentication or rate
limiting** built in. You are responsible for securing the host and network
path — for example by running it behind a reverse proxy with TLS, an
authenticating gateway, or on a trusted private network.

## Data retention

Because the server holds no data of its own, there is nothing to retain or
delete on our side. Documents remain yours, on your filesystem, under your
control.

## Third-party services

The server authenticates against your Sang Labs project, hosted on Supabase
(`supabase.com`) — see "Network activity" above for the exact endpoints. It
does not use a hosted model, a document-processing API, or an external
storage provider.

If you run this server as part of an MCP client (Claude Desktop, Cursor, VS
Code, OpenCode, and so on), that client has its own privacy policy and its
own data handling. This policy covers only this MCP server.

## Changes to this policy

Updates to this policy will be published in this repository. The effective
date above will be revised whenever the policy changes materially.

## Contact

Questions or concerns about this policy:

- Email: [imamsanghaar@gmail.com](mailto:imamsanghaar@gmail.com)
- Issues: <https://github.com/imamsanghaarc/imsanghaar-word-mcp/issues>
