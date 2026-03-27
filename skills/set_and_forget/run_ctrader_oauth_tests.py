import json
import tempfile
from pathlib import Path

import ctrader_oauth


BASE_DIR = Path(__file__).resolve().parent


class FakeResponse:
    def __init__(self, payload: dict):
        self.payload = payload

    def read(self):
        return json.dumps(self.payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def assert_authorization_url_contract():
    url = ctrader_oauth.build_authorization_url(
        {
            "client_id": "demo-client-id",
            "client_secret": "demo-client-secret",
            "redirect_uri": "http://127.0.0.1:8788/callback",
            "auth_base_url": "https://id.ctrader.com",
            "token_base_url": "https://openapi.ctrader.com",
        }
    )
    assert "client_id=demo-client-id" in url, "authorization url must contain the client_id"
    assert "scope=trading" in url, "authorization url must request trading scope"
    assert "redirect_uri=http%3A%2F%2F127.0.0.1%3A8788%2Fcallback" in url, (
        "authorization url must encode the redirect uri"
    )


def assert_token_exchange_contract():
    config = {
        "client_id": "demo-client-id",
        "client_secret": "demo-client-secret",
        "redirect_uri": "http://127.0.0.1:8788/callback",
        "auth_base_url": "https://id.ctrader.com",
        "token_base_url": "https://openapi.ctrader.com",
    }

    requested_urls = []

    def fake_urlopen(url):
        requested_urls.append(url)
        return FakeResponse(
            {
                "accessToken": "access-123",
                "refreshToken": "refresh-456",
                "tokenType": "bearer",
                "expiresIn": 2628000,
                "errorCode": None,
                "description": None,
            }
        )

    tokens = ctrader_oauth.exchange_authorization_code(config, "code-abc", opener=fake_urlopen)
    assert requested_urls, "token exchange must perform an HTTP request"
    assert "grant_type=authorization_code" in requested_urls[0], "token exchange must use the authorization_code grant"
    assert "code=code-abc" in requested_urls[0], "token exchange must send the authorization code"
    assert tokens["access_token"] == "access-123", "token exchange must normalize accessToken"
    assert tokens["refresh_token"] == "refresh-456", "token exchange must normalize refreshToken"
    assert tokens["access_token_expires_at"] is not None, "token exchange must compute an access token expiry timestamp"


def assert_env_upsert_contract():
    with tempfile.TemporaryDirectory() as tmpdir:
        env_file = Path(tmpdir) / "gateway.env"
        env_file.write_text(
            "\n".join(
                [
                    "CTRADER_ENVIRONMENT=demo",
                    "CTRADER_ACCOUNT_ID=4219358",
                    "CTRADER_CLIENT_ID=demo-client-id",
                    "CTRADER_CLIENT_SECRET=demo-client-secret",
                    "CTRADER_REDIRECT_URI=http://127.0.0.1:8788/callback",
                    "CTRADER_ACCESS_TOKEN=old-access",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        ctrader_oauth.upsert_env_file(
            env_file,
            {
                "CTRADER_ACCESS_TOKEN": "new-access",
                "CTRADER_REFRESH_TOKEN": "new-refresh",
                "CTRADER_TOKEN_TYPE": "bearer",
                "CTRADER_ACCESS_TOKEN_EXPIRES_AT": "2026-03-27T00:00:00+00:00",
            },
        )
        contents = env_file.read_text(encoding="utf-8")
        assert "CTRADER_ACCESS_TOKEN=new-access" in contents, "env upsert must replace an existing token"
        assert "CTRADER_REFRESH_TOKEN=new-refresh" in contents, "env upsert must append missing token lines"
        assert contents.count("CTRADER_ACCESS_TOKEN=") == 1, "env upsert must not duplicate existing keys"


def main():
    assert_authorization_url_contract()
    assert_token_exchange_contract()
    assert_env_upsert_contract()
    print("PASS 3/3 ctrader oauth scenarios")
    print("- authorization_url_contract: ok=True")
    print("- token_exchange_contract: ok=True")
    print("- env_upsert_contract: ok=True")


if __name__ == "__main__":
    main()
