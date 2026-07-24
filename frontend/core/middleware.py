from urllib.parse import urlencode

from django.conf import settings
from django.shortcuts import redirect
from django.utils.cache import patch_cache_control

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
            response = self.get_response(request)
            content_type = response.headers.get("Content-Type", "")
            if (
                not is_public
                and access_token
                and content_type.startswith("text/html")
            ):
                patch_cache_control(
                    response,
                    no_cache=True,
                    no_store=True,
                    must_revalidate=True,
                    private=True,
                )
            return response
        finally:
            reset_request_api_token(context_token)
