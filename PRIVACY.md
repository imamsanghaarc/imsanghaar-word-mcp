# Privacy Policy

**Effective date:** 2026-10-10

## Overview

Office-Word-MCP-Server is a self-hosted Model Context Protocol (MCP) server
published as [`msow-imsanghaar-mcp`](https://pypi.org/project/msow-imsanghaar-mcp/).
This policy explains what data the server touches and why.

**The short version: the server runs entirely on your own machine, processes
only the files you point it at, and sends nothing to us.**

## What the server does not collect

Office-Word-MCP-Server does **not**:

- collect, store, or transmit any personal data
- require an account, login, or subscription
- include telemetry, analytics, crash reporting, or usage tracking
- read, scan, or index the contents of files you do not pass to it as an
  argument. The one exception is `list_available_documents`, which returns
  the names and sizes of the `.docx` files in the single directory you give
  it — it never opens them
- phone home to any project-controlled server

There is no project-operated backend. The maintainers never see your
documents, their contents, or your usage of the server.

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

The only network-related URLs that appear in the code are the standard
Open XML namespace URIs required by the Office Open XML file format:

- `http://schemas.openxmlformats.org/...`
- `http://www.w3.org/...`

These are XML namespace identifiers, not network endpoints. They are used
purely as identifiers inside the `.docx` file format and are never fetched,
resolved, or connected to.

The dependencies declared in `pyproject.toml` (`python-docx`, `fastmcp`,
`msoffcrypto-tool`, `docx2pdf`, `python-dotenv`, `pytest`) are installed from
public package indexes by your own package manager as part of installation.

## Configuration and secrets

Configuration is read from local environment variables and an optional
`.env` file in your working directory. No API keys, tokens, or credentials
are bundled with the server, and none are transmitted anywhere.

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

The server does not integrate with any third-party service. It does not use
a hosted model, a document-processing API, or an external storage provider.

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
