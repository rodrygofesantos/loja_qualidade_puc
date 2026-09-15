from django.db import OperationalError, ProgrammingError


def lab_context(request):
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {}
    try:
        state = request.user.lab_state
    except (AttributeError, OperationalError, ProgrammingError):
        return {}
    return {"lab_state": state}

