from __future__ import annotations
import json
import httpx

def read_sse(url: str, *, timeout: float = 10.0, headers: dict[str,str] | None = None, limit: int = 1):
    events = []
    with httpx.stream("GET", url, headers=headers, timeout=timeout) as response:
        response.raise_for_status()
        event = {}
        for line in response.iter_lines():
            if line == "":
                if event:
                    events.append(event); event = {}
                    if len(events) >= limit:
                        break
                continue
            if line.startswith(":"):
                continue
            key, _, value = line.partition(":")
            event[key] = value.lstrip()
    return events

async def websocket_json(url: str, messages: list[object], *, timeout: float = 10.0):
    import asyncio, websockets
    replies = []
    async with websockets.connect(url, open_timeout=timeout) as ws:
        for message in messages:
            await ws.send(json.dumps(message))
            replies.append(json.loads(await asyncio.wait_for(ws.recv(), timeout)))
    return replies
