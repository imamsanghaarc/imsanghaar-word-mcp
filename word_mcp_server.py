#!/usr/bin/env python3
"""
Run script for the Word Document Server.

This script provides a simple way to start the Word Document Server.
"""

import sys

if "--logout" in sys.argv:
    from word_document_server.auth import logout_local

    logout_local()
    print("Signed out — the local Sang Labs session has been revoked and removed.")
    sys.exit(0)

from word_document_server.main import run_server

if __name__ == "__main__":
    run_server()
