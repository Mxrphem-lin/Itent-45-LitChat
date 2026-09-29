import ipaddress

from django.http import HttpResponseForbidden


class LoopbackOnlyMiddleware:
    """Reject requests that did not originate on the local machine."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            is_loopback = ipaddress.ip_address(request.META.get("REMOTE_ADDR", "")).is_loopback
        except (TypeError, ValueError):
            is_loopback = False
        if not is_loopback:
            return HttpResponseForbidden("LitChat is available only from this device.")
        return self.get_response(request)
