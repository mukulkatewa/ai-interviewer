"""Error tracking (D44): Sentry, only when SENTRY_DSN is set. Without it nothing is imported or sent.

What leaves the server is deliberately small: the exception, its stack trace and the route. Never request
bodies (resume text, audio), never the user's email or IP, and no performance tracing.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

_DROPPED_REQUEST_KEYS = ("data", "cookies", "headers", "query_string")


def scrub(event: dict[str, Any], _hint: dict[str, Any]) -> dict[str, Any]:
    """Last line of defense: strip anything personal Sentry's integrations may have attached."""
    request = event.get("request")
    if isinstance(request, dict):
        for key in _DROPPED_REQUEST_KEYS:
            request.pop(key, None)
    event.pop("user", None)
    return event


def init_error_tracking(dsn: str, environment: str) -> bool:
    if not dsn:
        return False
    import sentry_sdk  # imported lazily: not needed (or loaded) when tracking is off

    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        send_default_pii=False,
        max_request_body_size="never",
        traces_sample_rate=0,
        before_send=scrub,
    )
    logger.info("error tracking on (%s)", environment)
    return True
