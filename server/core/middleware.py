"""Request correlation middleware for structured logging."""

from __future__ import annotations

import logging
import time
import uuid

from django.utils.deprecation import MiddlewareMixin

from .observability import clear_request_id, set_request_id


logger = logging.getLogger("terrierconnect.request")
IGNORED_PATHS = {"/metrics", "/api/posts/health/"}


class RequestIDMiddleware(MiddlewareMixin):
    """
    If the incoming request carries an ``X-Request-ID`` header, use it;
    otherwise generate a new UUID.  Stores it on ``request.id`` and echoes
    it back on the response.
    """

    HEADER = "HTTP_X_REQUEST_ID"
    RESPONSE_HEADER = "X-Request-ID"

    def process_request(self, request):
        request.id = request.META.get(self.HEADER, str(uuid.uuid4()))
        request._start_time = time.perf_counter()
        set_request_id(request.id)

    def process_response(self, request, response):
        rid = getattr(request, "id", None)
        if rid:
            response[self.RESPONSE_HEADER] = rid

        start_time = getattr(request, "_start_time", None)
        if start_time is not None and getattr(request, "path", "") not in IGNORED_PATHS:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.info(
                "request completed",
                extra={
                    "request_id": rid,
                    "method": getattr(request, "method", ""),
                    "path": getattr(request, "path", ""),
                    "status_code": getattr(response, "status_code", 0),
                    "duration_ms": duration_ms,
                },
            )

        clear_request_id()
        return response
