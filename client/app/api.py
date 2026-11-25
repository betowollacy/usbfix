import json
import urllib.error
import urllib.parse
import urllib.request

from .ssl_context import create_ssl_context


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
            with urllib.request.urlopen(
                req, timeout=20, context=create_ssl_context()
            ) as resp:
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

    def downloads(self):
        return self._request("GET", "/api/downloads")

    def register(self, username, password, email=""):
        return self._request("POST", "/api/register", {"username": username, "email": email, "password": password})

    def login(self, email, password, instance=None, device_name=None):
        body = {"email": email, "password": password}
        if instance:
            body["instance"] = instance
        if device_name:
            body["deviceName"] = device_name
        return self._request("POST", "/api/login", body)

    def me(self, instance=None):
        path = "/api/me"
        if instance:
            path += "?" + urllib.parse.urlencode({"instance": instance})
        return self._request("GET", path)

    def set_subdomain(self, subdomain):
        return self._request("POST", "/api/subdomain", {"subdomain": subdomain})

    def set_my_username(self, new_username, instance=None):
        body = {"newUsername": new_username}
        if instance:
            body["instance"] = instance
        return self._request("POST", "/api/me/username", body)

    def sessions(self):
        return self._request("GET", "/api/sessions")

    def peers(self):
        return self._request("GET", "/api/peers")

    def tunnel_event(self, status, instance=None, device_name=None):
        body = {"status": status}
        if instance:
            body["instance"] = instance
        if device_name:
            body["deviceName"] = device_name
        return self._request("POST", "/api/tunnel-event", body)
