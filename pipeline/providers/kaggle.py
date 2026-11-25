import httpx

API_BASE = "https://www.kaggle.com/api/v1"


class KaggleAccount:
    provider = "kaggle"
    model = "api"

    def __init__(self, *, api_token: str | None = None, username: str | None = None, key: str | None = None) -> None:
        # New Kaggle tokens (KGAT_...) use a bearer header; older ones use username + key.
        if api_token:
            self._headers = {"Authorization": f"Bearer {api_token}"}
            self._auth = None
        elif username and key:
            self._headers = {}
            self._auth = (username, key)
        else:
            raise ValueError("Set KAGGLE_API_TOKEN, or KAGGLE_USERNAME and KAGGLE_KEY")

    def check(self) -> str:
        response = httpx.get(
            f"{API_BASE}/kernels/list",
            params={"pageSize": 1},
            headers=self._headers,
            auth=self._auth,
            timeout=30.0,
        )
        response.raise_for_status()
        return "authenticated"
