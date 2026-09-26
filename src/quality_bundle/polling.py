import time
def poll_until(fn,predicate=bool,*,timeout=10,interval=.25,description="condition"):
    deadline=time.monotonic()+timeout; last=error=None
    while time.monotonic()<deadline:
        try:
            last=fn()
            if predicate(last):return last
        except Exception as exc:error=exc
        time.sleep(interval)
    raise TimeoutError(f"Timed out waiting for {description}; last={last!r}; error={error!r}")
