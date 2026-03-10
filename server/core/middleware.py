"""
Request-ID middleware for structured logging and distributed tracing.
"""

import uuid

from django.utils.deprecation import MiddlewareMixin


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

    def process_response(self, request, response):
        rid = getattr(request, "id", None)
        if rid:
            response[self.RESPONSE_HEADER] = rid
        return response
