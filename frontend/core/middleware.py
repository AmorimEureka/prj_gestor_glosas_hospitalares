from urllib.parse import urlencode

from django.conf import settings
from django.shortcuts import redirect

from .services import reset_request_api_token, set_request_api_token


class ApiSessionMiddleware:
    public_paths = {
        "/login/",
        "/logout/",
        "/esqueci-senha/",
        "/redefinir-senha/",
        "/autenticacao/redefinir-senha",
        "/autenticacao/redefinir-senha/",
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        is_public = (
            request.path in self.public_paths
            or request.path.startswith(f"/{settings.STATIC_URL.lstrip('/')}")
            or request.path == "/favicon.ico"
        )
        access_token = request.session.get("api_access_token")
        if not is_public and not access_token:
            query = urlencode({"next": request.get_full_path()})
            return redirect(f"/login/?{query}")

        context_token = set_request_api_token(access_token)
        try:
            return self.get_response(request)
        finally:
            reset_request_api_token(context_token)
