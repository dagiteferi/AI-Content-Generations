import httpx

API_BASE = "https://www.kaggle.com/api/v1"


class KaggleAccount:
    provider = "kaggle"
    model = "api"

    def __init__(self, username: str, key: str) -> None:
        self.username = username
        self._auth = (username, key)

    def check(self) -> str:
        response = httpx.get(
            f"{API_BASE}/kernels/list",
            params={"pageSize": 1, "user": self.username},
            auth=self._auth,
            timeout=30.0,
        )
        response.raise_for_status()
        return f"authenticated as {self.username}"
