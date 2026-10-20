"""In-app Admin Panel views (staff / role='admin' only).

The React SPA owns all panel routes (/panel/*, /control-panel/*).
These views serve the baked SPA shell so that direct navigation and
browser refresh work. All data flows through /api/v1/panel/* JSON APIs.
"""

from django.http import HttpRequest, HttpResponse

from apps.core.spa import serve_spa_shell


# ---------------------------------------------------------------------------
# All panel routes serve the SPA shell — React Router handles the rest.
# The @admin_required decorator is enforced by the React route guard
# (AdminRoute) and the API endpoints (/api/v1/panel/*) enforce permissions.
# ---------------------------------------------------------------------------


def dashboard_view(request: HttpRequest) -> HttpResponse:
    return serve_spa_shell(request, fallback="/panel")


def test_list_view(request: HttpRequest) -> HttpResponse:
    return serve_spa_shell(request, fallback="/panel/tests")


def test_create_view(request: HttpRequest) -> HttpResponse:
    return serve_spa_shell(request, fallback="/panel/tests/new")


def test_edit_view(request: HttpRequest, test_id: int) -> HttpResponse:
    return serve_spa_shell(request, fallback=f"/panel/tests/{test_id}/edit")


def test_delete_view(request: HttpRequest, test_id: int) -> HttpResponse:
    return serve_spa_shell(request, fallback="/panel/tests")


def test_status_view(request: HttpRequest, test_id: int) -> HttpResponse:
    return serve_spa_shell(request, fallback="/panel/tests")


def question_manage_view(request: HttpRequest, test_id: int) -> HttpResponse:
    return serve_spa_shell(request, fallback=f"/panel/tests/{test_id}/questions")


def question_add_view(request: HttpRequest, test_id: int) -> HttpResponse:
    return serve_spa_shell(request, fallback=f"/panel/tests/{test_id}/questions")


def question_edit_view(
    request: HttpRequest, test_id: int, question_id: int
) -> HttpResponse:
    return serve_spa_shell(request, fallback=f"/panel/tests/{test_id}/questions")


def question_delete_view(
    request: HttpRequest, test_id: int, question_id: int
) -> HttpResponse:
    return serve_spa_shell(request, fallback=f"/panel/tests/{test_id}/questions")


def essay_topic_list_view(request: HttpRequest) -> HttpResponse:
    return serve_spa_shell(request, fallback="/panel/topics")


def essay_topic_create_view(request: HttpRequest) -> HttpResponse:
    return serve_spa_shell(request, fallback="/panel/topics")


def essay_topic_edit_view(request: HttpRequest, topic_id: int) -> HttpResponse:
    return serve_spa_shell(request, fallback="/panel/topics")


def essay_topic_delete_view(request: HttpRequest, topic_id: int) -> HttpResponse:
    return serve_spa_shell(request, fallback="/panel/topics")


def user_list_view(request: HttpRequest) -> HttpResponse:
    return serve_spa_shell(request, fallback="/panel/users")


def user_role_view(request: HttpRequest, user_id: int) -> HttpResponse:
    return serve_spa_shell(request, fallback="/panel/users")


def user_block_view(request: HttpRequest, user_id: int) -> HttpResponse:
    return serve_spa_shell(request, fallback="/panel/users")
