# WebSocket and SSE

`quality_bundle.realtime` provides small black-box helpers:
- `read_sse()` for bounded SSE event collection
- `websocket_json()` for JSON request/reply flows

Project tests own authentication, protocol messages, ordering rules and reconnect semantics.

Test reconnect/resume only when those behaviors are part of the public contract.
