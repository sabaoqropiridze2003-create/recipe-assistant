import re

from api_client import ENDPOINTS_USED

HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


def _normalize(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "{}", path)  


def _available_endpoints() -> set[tuple[str, str]]:
    from app.main import app

    paths = app.openapi()["paths"]
    return {
        (method.upper(), _normalize(path))
        for path, operations in paths.items()
        for method in operations
        if method in HTTP_METHODS
    }


def test_the_api_reports_its_routes():
    assert len(_available_endpoints()) > 20


def test_every_endpoint_the_ui_calls_exists_in_the_api():
    available = _available_endpoints()
    missing = sorted((m, p) for m, p in ENDPOINTS_USED if (m, _normalize(p)) not in available)
    assert missing == [], f"The UI calls endpoints that do not exist in the API: {missing}"