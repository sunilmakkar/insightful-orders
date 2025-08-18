"""
WebSocket listener tool for Insightful-Orders alerts.

Responsibilities:
    - Connect to the alerts WebSocket endpoint with a valid JWT.
    - Listen for incoming alert messages and pretty-print them to stdout.

Usage:
    python app/tools/ws_listen.py <JWT>

Environment variables:
    WS_BASE_URL (optional): Override the base WebSocket URL.
                            Defaults to "ws://localhost:5050".

Example:
    export WS_BASE_URL="ws://prod-server:5050"
    python app/tools/ws_listen.py eyJhbGciOi...

Notes:
    - Messages are parsed as JSON and printed with indentation if possible.
    - Falls back to raw string printing if JSON decoding fails.
"""

import os
import sys
import asyncio
import json
import websockets


if len(sys.argv) < 2:
    print("Usage: python app/tools/ws_listen.py <JWT>")
    sys.exit(1)

TOKEN = sys.argv[1]
BASE = os.environ.get("WS_BASE_URL", "ws://localhost:5050")  # host default
URL = f"{BASE}/ws/alerts?token={TOKEN}"

async def main():
    """Connect to WebSocket server and print incoming alert messages."""
    async with websockets.connect(URL, compression=None) as ws:
        print(f"Connected to {URL}. Waiting for alert messages…")
        async for msg in ws:
            try:
                print(json.dumps(json.loads(msg), indent=2))
            except Exception:
                print(msg)

if __name__ == "__main__":
    asyncio.run(main())

