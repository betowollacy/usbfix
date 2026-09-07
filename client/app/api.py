import json
import urllib.error
import urllib.parse
import urllib.request


class ApiError(Exception):
    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


class Api:
    def __init__(self, base_url):
        self.base = base_url.rstrip("/")
        self.token = None

    def set_token(self, token):
        self.token = token

    def _request(self, method, path, body=None):
        url = self.base + path
        data = None
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if body is not None:
            data = json.dumps(body).encode()
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                raw = resp.read()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as exc:
            detail = "erro do servidor"
            try:
                payload = json.loads(exc.read())
                detail = payload.get("detail", detail)
            except Exception:
                pass
            raise ApiError(str(detail), exc.code)

    def health(self):
        return self._request("GET", "/api/health")

    def register(self, email, password):
        return self._request("POST", "/api/register", {"email": email, "password": password})

    def login(self, email, password):
        return self._request("POST", "/api/login", {"email": email, "password": password})

    def me(self):
        return self._request("GET", "/api/me")

    def set_subdomain(self, subdomain):
        return self._request("POST", "/api/subdomain", {"subdomain": subdomain})

    def sessions(self):
        return self._request("GET", "/api/sessions")

    def tunnel_event(self, status):
        return self._request("POST", "/api/tunnel-event", {"status": status})