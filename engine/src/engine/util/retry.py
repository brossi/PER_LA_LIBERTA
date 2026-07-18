"""API-call retry with exponential backoff — ported from ``utils.retry_api_call``.

The default backends behind the M4b chat seams (triage, cleanup's LLM path) wrap their network
call in this, so a transient provider error (rate-limit, 5xx, timeout, dropped connection) is
retried instead of failing the whole step. The retryable set defaults to the Anthropic transient
errors, imported **lazily** so importing this module needs no provider SDK; a caller may pass its
own ``retryable_exceptions``. Pure backoff mechanics — book/language-neutral.
"""

from __future__ import annotations

import time
from typing import Callable

#: Seconds to wait before each retry. Module constant so a test can patch it to ``()`` / zeros and
#: not actually sleep. Verbatim from the live ``retry_api_call`` (``delays = [2, 4, 8]``).
_RETRY_DELAYS = (2, 4, 8)


def retry_api_call(
    fn: Callable,
    *args,
    max_attempts: int = 3,
    retryable_exceptions: tuple | None = None,
    **kwargs,
):
    """Call ``fn(*args, **kwargs)``, retrying on transient errors with exponential backoff.

    Retries up to ``max_attempts`` times; on the final attempt the exception propagates. When
    ``retryable_exceptions`` is ``None`` it defaults to the Anthropic transient set
    (``RateLimitError``/``InternalServerError``/``APITimeoutError``/``APIConnectionError``),
    imported lazily. A non-retryable exception is never caught.
    """
    if retryable_exceptions is None:
        import anthropic

        retryable_exceptions = (
            anthropic.RateLimitError,
            anthropic.InternalServerError,
            anthropic.APITimeoutError,
            anthropic.APIConnectionError,
        )

    for attempt in range(max_attempts):
        try:
            return fn(*args, **kwargs)
        except retryable_exceptions as exc:
            if attempt == max_attempts - 1:
                raise
            delay = _RETRY_DELAYS[min(attempt, len(_RETRY_DELAYS) - 1)]
            print(f"    Retrying in {delay}s ({type(exc).__name__}: {exc})")
            if delay:
                time.sleep(delay)
