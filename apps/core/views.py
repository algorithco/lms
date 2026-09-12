"""Core app views — health checks for container orchestration."""
from django.db import connection
from django.http import JsonResponse


def healthz_view(request):
    """Liveness/readiness probe for Docker/Kubernetes healthchecks.

    Returns 200 with DB status when the app and database are reachable,
    503 when the database is down (so orchestration can restart us).
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        db_ok = True
    except Exception:
        db_ok = False

    status = 200 if db_ok else 503
    return JsonResponse({"status": "ok" if db_ok else "unavailable", "db": db_ok}, status=status)