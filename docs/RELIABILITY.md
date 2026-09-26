# Reliability and fault testing

The toolkit provides a Toxiproxy container fixture. Product tests define the actual network topology
and expected recovery behavior.

Good black-box scenarios:
- dependency latency
- connection reset
- timeout
- temporary dependency outage
- SUT restart
- dependency restart
- retry/idempotency behavior
- recovery after network restoration

Avoid arbitrary sleeps. Poll public state with a deadline.

Container kill/restart scenarios should use public container/process boundaries in the test
environment and verify recovery only through public product interfaces.
