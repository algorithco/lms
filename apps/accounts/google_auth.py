"""Google OpenID Connect login and explicit account linking."""
from __future__ import annotations

import json
import logging
import secrets
import urllib.parse
import urllib.request

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.db import IntegrityError, transaction
from django.http import HttpRequest, HttpResponseRedirect
from django.shortcuts import redirect
from django.views.decorators.http import require_GET

logger = logging.getLogger(__name__)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"


def _get_google_config() -> dict[str, str]:
    client_id = getattr(settings, "GOOGLE_CLIENT_ID", "")
    client_secret = getattr(settings, "GOOGLE_CLIENT_SECRET", "")
    redirect_uri = getattr(settings, "GOOGLE_REDIRECT_URI", "")
    if not client_id or not client_secret or not redirect_uri:
        return {}
    return {"client_id": client_id, "client_secret": client_secret, "redirect_uri": redirect_uri}


@require_GET
def google_auth_start(request: HttpRequest) -> HttpResponseRedirect:
    config = _get_google_config()
    if not config:
        messages.error(request, "Google kirish hali sozlanmagan. Admin bilan bog'laning.")
        return redirect("web:login")

    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    request.session["google_oauth_state"] = state
    request.session["google_oauth_nonce"] = nonce
    request.session["google_oauth_link_user_id"] = request.user.pk if request.user.is_authenticated else None
    request.session.set_expiry(600)
    params = {
        "client_id": config["client_id"],
        "redirect_uri": config["redirect_uri"],
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "nonce": nonce,
    }
    return HttpResponseRedirect(f"{GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}")


def _verified_claims(raw_id_token: str, client_id: str, nonce: str) -> dict | None:
    """Verify Google's signature, issuer, audience and expiry, then session nonce."""
    try:
        from google.auth.transport.requests import Request
        from google.oauth2 import id_token

        claims = id_token.verify_oauth2_token(raw_id_token, Request(), client_id)
    except Exception as exc:
        logger.warning("Google ID token verification failed: %s", exc)
        return None
    if not secrets.compare_digest(str(claims.get("nonce", "")), nonce):
        logger.warning("Google OAuth nonce mismatch")
        return None
    if claims.get("email_verified") is not True:
        logger.warning("Google OAuth email is not verified")
        return None
    return claims


@require_GET
def google_auth_callback(request: HttpRequest) -> HttpResponseRedirect:
    if request.GET.get("error"):
        return redirect("web:login")

    code = request.GET.get("code")
    state = request.GET.get("state")
    expected_state = request.session.pop("google_oauth_state", None)
    nonce = request.session.pop("google_oauth_nonce", None)
    link_user_id = request.session.pop("google_oauth_link_user_id", None)
    if (not code or not state or not expected_state or not nonce
            or not secrets.compare_digest(state, expected_state)):
        logger.warning("Google OAuth missing code or invalid state")
        return redirect("web:login")

    config = _get_google_config()
    if not config:
        return redirect("web:login")
    token_data = urllib.parse.urlencode({
        "code": code,
        "client_id": config["client_id"],
        "client_secret": config["client_secret"],
        "redirect_uri": config["redirect_uri"],
        "grant_type": "authorization_code",
    }).encode("utf-8")
    try:
        token_request = urllib.request.Request(GOOGLE_TOKEN_URL, data=token_data, method="POST")
        with urllib.request.urlopen(token_request, timeout=10) as response:
            token_response = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        logger.warning("Google token exchange failed: %s", exc)
        return redirect("web:login")
    raw_id_token = token_response.get("id_token")
    if not isinstance(raw_id_token, str) or not raw_id_token:
        return redirect("web:login")
    claims = _verified_claims(raw_id_token, config["client_id"], nonce)
    if claims is None:
        return redirect("web:login")

    google_id = claims.get("sub")
    email = claims.get("email", "")
    if (not isinstance(google_id, str) or not google_id or len(google_id) > 64
            or not isinstance(email, str) or not email.strip()):
        return redirect("web:login")
    email = email.strip().lower()
    User = get_user_model()

    if link_user_id is not None:
        # A logged-in user deliberately started this flow. Never let a changed
        # browser session or a Google identity already owned by someone else link.
        if not request.user.is_authenticated or request.user.pk != link_user_id:
            return redirect("web:login")
        if User.objects.filter(google_id=google_id).exclude(pk=link_user_id).exists():
            messages.error(request, "Bu Google hisobi boshqa hisobga bog'langan.")
            return redirect("web:dashboard")
        try:
            with transaction.atomic():
                user = User.objects.select_for_update().get(pk=link_user_id)
                if user.google_id and user.google_id != google_id:
                    messages.error(request, "Boshqa Google hisobi allaqachon bog'langan.")
                    return redirect("web:dashboard")
                if not user.google_id:
                    user.google_id = google_id
                    user.save(update_fields=["google_id"])
        except (User.DoesNotExist, IntegrityError):
            return redirect("web:login")
    else:
        user = User.objects.filter(google_id=google_id).first()
        if user is None:
            # Email ownership alone is insufficient to attach a Google login.
            # The existing user can sign in with their password and link explicitly.
            if User.objects.filter(email=email).exists():
                messages.error(request, "Bu email allaqachon mavjud. Avval parol bilan kiring, keyin Google hisobingizni bog'lang.")
                return redirect("web:login")
            from apps.accounts.models import Profile

            try:
                with transaction.atomic():
                    user = User.objects.create_user(
                        email=email, password=None,
                        first_name=claims.get("given_name", ""),
                        last_name=claims.get("family_name", ""),
                        role=User.Role.STUDENT, google_id=google_id,
                    )
                    Profile.objects.get_or_create(user=user)
            except IntegrityError:
                logger.warning("Google account creation collision")
                return redirect("web:login")

    if not user.is_active:
        logger.warning("Inactive Google-linked user denied: user_id=%s", user.pk)
        return redirect("web:login")
    login(request, user)
    request.session.set_expiry(60 * 60 * 24 * 30)
    logger.info("Google OAuth login: user_id=%s", user.pk)
    return redirect("web:dashboard")
