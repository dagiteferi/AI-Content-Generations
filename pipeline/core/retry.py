import random
import time
from collections.abc import Callable
from pathlib import Path

import httpx

from pipeline.core.runlog import Call, RunLog

TRANSIENT_STATUS = {408, 429, 500, 502, 503, 504}
MAX_BACKOFF_S = 30.0
MAX_ERROR_CHARS = 500


NETWORK_ERRORS = {"TimeoutException", "TransportError", "TimeoutError", "APIConnectionError"}


def is_transient(error: Exception) -> bool:
    if isinstance(error, (httpx.TimeoutException, httpx.TransportError)):
        return True
    # google-genai ships its own copy of httpx, so match its network errors by name.
    if NETWORK_ERRORS & {cls.__name__ for cls in type(error).__mro__}:
        return True
    status = getattr(error, "code", None) or getattr(error, "status_code", None)
    if status is None and isinstance(error, httpx.HTTPStatusError):
        status = error.response.status_code
    return status in TRANSIENT_STATUS


def backoff_s(attempt: int) -> float:
    return min(MAX_BACKOFF_S, 2.0**attempt) + random.uniform(0, 1)


def describe(error: Exception) -> str:
    return f"{type(error).__name__}: {error}"[:MAX_ERROR_CHARS]


def call_with_retry[T](
    operation: Callable[[], T],
    *,
    call: Call,
    log: RunLog,
    max_attempts: int = 3,
    output: Path | None = None,
) -> T:
    """Run a model call, logging every attempt and retrying transient failures."""
    for attempt in range(1, max_attempts + 1):
        started = time.perf_counter()
        try:
            result = operation()
        except Exception as error:
            log.record(
                call,
                status="error",
                attempt=attempt,
                latency_s=time.perf_counter() - started,
                error=describe(error),
            )
            if attempt == max_attempts or not is_transient(error):
                raise
            time.sleep(backoff_s(attempt))
        else:
            log.record(
                call,
                status="ok",
                attempt=attempt,
                latency_s=time.perf_counter() - started,
                output=output,
            )
            return result
    raise AssertionError("unreachable")
