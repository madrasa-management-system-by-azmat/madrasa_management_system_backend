from contextvars import ContextVar

_current_request = ContextVar("audit_request", default=None)

def set_audit_request(request):
    return _current_request.set(request)

def reset_audit_request(token):
    _current_request.reset(token)

def get_audit_request():
    return _current_request.get()
