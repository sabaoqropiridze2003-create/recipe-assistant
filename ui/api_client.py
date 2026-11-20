"""EVERY call from the UI to the backend lives in this file (and nowhere else).

The UI never touches the database or the AI graph: it only speaks HTTP to the FastAPI service."""
import httpx
from helpers import friendly_error, parse_sse_line


class ApiError(Exception):
    """An error from the API, already turned into a message a person can read."""

    def __init__(self, status: int, message: str, detail=None):
        super().__init__(message)
        self.status = status
        self.message = message
        self.detail = detail  # the raw 'detail' of the response (the 409 carries the pending question)


def _raw_detail(response: httpx.Response):
    try:
        return response.json().get("detail")
    except Exception:
        return None


class ApiClient:
    def __init__(self, http: httpx.Client, token: str | None = None):
        self._http = http
        self._token = token

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._token}"} if self._token else {}

    def _fail(self, response: httpx.Response):
        detail = _raw_detail(response)
        raise ApiError(response.status_code, friendly_error(response.status_code, detail), detail)

    def _request(self, method: str, path: str, **kwargs):
        try:
            response = self._http.request(method, path, headers=self._headers(), **kwargs)
        except httpx.TimeoutException:
            raise ApiError(-1, friendly_error(-1, None))
        except httpx.RequestError:
            raise ApiError(0, friendly_error(0, None))
        if response.status_code >= 400:
            self._fail(response)
        return None if response.status_code == 204 else response.json()

    def _stream(self, path: str, body: dict):
        """Server-Sent Events: yields one event (a dict) at a time as the server sends it."""
        try:
            with self._http.stream("POST", path, json=body, headers=self._headers()) as response:
                if response.status_code >= 400:
                    response.read()
                    self._fail(response)
                for line in response.iter_lines():
                    event = parse_sse_line(line)
                    if event:
                        yield event
        except httpx.TimeoutException:
            raise ApiError(-1, friendly_error(-1, None))
        except httpx.RequestError:
            raise ApiError(0, friendly_error(0, None))

    # ---------------------------------------------------------------- auth
    def register(self, email: str, full_name: str, password: str) -> dict:
        return self._request("POST", "/auth/register", json={"email": email, "full_name": full_name, "password": password})

    def login(self, email: str, password: str) -> str:
        data = self._request("POST", "/auth/login", data={"username": email, "password": password})
        return data["access_token"]

    def me(self) -> dict:
        return self._request("GET", "/auth/me")

    # ---------------------------------------------------------------- profile and pantry
    def get_profile(self) -> dict:
        return self._request("GET", "/profile")

    def save_profile(self, body: dict) -> dict:
        return self._request("PUT", "/profile", json=body)

    def list_pantry(self) -> list:
        return self._request("GET", "/pantry")

    def add_pantry(self, name: str, quantity: float | None, unit: str | None) -> dict:
        return self._request("POST", "/pantry", json={"name": name, "quantity": quantity, "unit": unit})

    def delete_pantry(self, item_id: int) -> None:
        return self._request("DELETE", f"/pantry/{item_id}")

    # ---------------------------------------------------------------- recipes and cookbook
    def list_recipes(self, **params) -> dict:
        return self._request("GET", "/recipes", params={k: v for k, v in params.items() if v not in (None, "")})

    def get_recipe(self, recipe_id: int, servings: int | None = None) -> dict:
        params = {"servings": servings} if servings else None
        return self._request("GET", f"/recipes/{recipe_id}", params=params)

    def create_recipe(self, body: dict) -> dict:
        return self._request("POST", "/recipes", json=body)

    def delete_recipe(self, recipe_id: int) -> None:
        return self._request("DELETE", f"/recipes/{recipe_id}")

    def list_cookbook(self) -> list:
        return self._request("GET", "/cookbook")

    def save_to_cookbook(self, recipe_id: int) -> dict:
        return self._request("POST", f"/cookbook/{recipe_id}")

    def remove_from_cookbook(self, recipe_id: int) -> None:
        return self._request("DELETE", f"/cookbook/{recipe_id}")

    # ---------------------------------------------------------------- shopping lists
    def list_shopping_lists(self) -> list:
        return self._request("GET", "/shopping-lists")

    def get_shopping_list(self, list_id: int) -> dict:
        return self._request("GET", f"/shopping-lists/{list_id}")

    def mark_item(self, list_id: int, item_id: int, bought: bool) -> dict:
        return self._request("PATCH", f"/shopping-lists/{list_id}/items/{item_id}", json={"is_bought": bought})

    def delete_shopping_list(self, list_id: int) -> None:
        return self._request("DELETE", f"/shopping-lists/{list_id}")

    # ---------------------------------------------------------------- chat
    def create_session(self) -> dict:
        return self._request("POST", "/chat/sessions")

    def list_sessions(self) -> list:
        return self._request("GET", "/chat/sessions")

    def get_session(self, session_id: int) -> dict:
        return self._request("GET", f"/chat/sessions/{session_id}")

    def list_messages(self, session_id: int) -> list:
        return self._request("GET", f"/chat/sessions/{session_id}/messages")

    def delete_session(self, session_id: int) -> None:
        return self._request("DELETE", f"/chat/sessions/{session_id}")

    def stream_message(self, session_id: int, content: str):
        return self._stream(f"/chat/sessions/{session_id}/messages", {"content": content})

    def stream_confirm(self, session_id: int, approved: bool, items: list | None = None):
        body: dict = {"approved": approved}
        if items is not None:
            body["items"] = items
        return self._stream(f"/chat/sessions/{session_id}/confirm", body)

    # ---------------------------------------------------------------- analytics (admin)
    def popular_recipes(self, limit: int = 10) -> dict:
        return self._request("GET", "/analytics/popular-recipes", params={"limit": limit})

    def ai_generated(self) -> dict:
        return self._request("GET", "/analytics/ai-generated")

    def intents(self) -> list:
        return self._request("GET", "/analytics/intents")


# Every endpoint used above. A test checks that each one really exists in the API, so the UI
# cannot silently call a path that was renamed or never built.
ENDPOINTS_USED = [
    ("POST", "/auth/register"), ("POST", "/auth/login"), ("GET", "/auth/me"),
    ("GET", "/profile"), ("PUT", "/profile"),
    ("GET", "/pantry"), ("POST", "/pantry"), ("DELETE", "/pantry/{id}"),
    ("GET", "/recipes"), ("GET", "/recipes/{id}"), ("POST", "/recipes"), ("DELETE", "/recipes/{id}"),
    ("GET", "/cookbook"), ("POST", "/cookbook/{id}"), ("DELETE", "/cookbook/{id}"),
    ("GET", "/shopping-lists"), ("GET", "/shopping-lists/{id}"),
    ("PATCH", "/shopping-lists/{id}/items/{id}"), ("DELETE", "/shopping-lists/{id}"),
    ("POST", "/chat/sessions"), ("GET", "/chat/sessions"), ("GET", "/chat/sessions/{id}"),
    ("GET", "/chat/sessions/{id}/messages"), ("DELETE", "/chat/sessions/{id}"),
    ("POST", "/chat/sessions/{id}/messages"), ("POST", "/chat/sessions/{id}/confirm"),
    ("GET", "/analytics/popular-recipes"), ("GET", "/analytics/ai-generated"), ("GET", "/analytics/intents"),
]
