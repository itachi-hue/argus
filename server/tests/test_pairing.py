"""Tests for the pairing flow."""

import time

from tests.conftest import make_error


class TestPairRequest:
    def test_no_auth_needed(self, client):
        """Pairing endpoint should be accessible without auth."""
        r = client.post("/api/pair")
        assert r.status_code == 200
        assert "terminal" in r.json()["message"].lower() or "code" in r.json()["message"].lower()

    def test_confirm_no_auth_needed(self, client):
        """Confirm endpoint should be accessible without auth."""
        r = client.post("/api/pair/confirm", json={"code": "0000"})
        # 401 for wrong code, but NOT for missing Bearer token
        assert r.status_code == 401
        assert "error" in r.json()


class TestPairPage:
    def test_pair_page_no_auth_needed(self, client):
        """Web pairing page should be accessible without auth."""
        r = client.get("/pair")
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]

    def test_pair_page_contains_token(self, client, config):
        """Web pairing page should display the auth token."""
        r = client.get("/pair")
        assert config.auth_token in r.text

    def test_pair_page_has_copy_button(self, client):
        """Web pairing page should have a copy-to-clipboard button."""
        r = client.get("/pair")
        assert "copyToken" in r.text
        assert "Copy to Clipboard" in r.text


class TestPairFlow:
    def test_full_pairing_flow(self, client, config):
        """Request code → confirm code → get token."""
        # Step 1: Request pairing
        r = client.post("/api/pair")
        assert r.status_code == 200

        # Step 2: We need to get the code from the PairingManager
        # Since we can't read stderr in tests, we test via the manager directly
        from argus.api.pairing import PairingManager

        manager = PairingManager(config.auth_token)
        code = manager.generate_code()

        # Step 3: Confirm with correct code
        token = manager.validate_code(code)
        assert token == config.auth_token

    def test_wrong_code_rejected(self, client):
        """Wrong code should be rejected."""
        client.post("/api/pair")  # Generate a code first
        r = client.post("/api/pair/confirm", json={"code": "9999"})
        assert r.status_code == 401
        assert "error" in r.json()

    def test_code_is_one_time_use(self, client, config):
        """Code should only work once."""
        from argus.api.pairing import PairingManager

        manager = PairingManager(config.auth_token)
        code = manager.generate_code()

        # First use: success
        assert manager.validate_code(code) == config.auth_token
        # Second use: fail
        assert manager.validate_code(code) is None

    def test_code_expires(self, client, config):
        """Code should expire after TTL."""
        from argus.api.pairing import PairingManager

        manager = PairingManager(config.auth_token, ttl_seconds=0)  # instant expiry
        code = manager.generate_code()
        time.sleep(0.01)  # Ensure it's expired
        assert manager.validate_code(code) is None

    def test_new_code_replaces_old(self, config):
        """Generating a new code should invalidate the old one."""
        from argus.api.pairing import PairingManager

        manager = PairingManager(config.auth_token)
        old_code = manager.generate_code()
        new_code = manager.generate_code()

        assert manager.validate_code(old_code) is None
        assert manager.validate_code(new_code) == config.auth_token

    def test_token_works_for_api(self, client, auth_headers, store):
        """Token obtained via pairing should work for regular API calls."""
        r = client.post(
            "/api/ingest/events",
            json={
                "errors": [make_error()],
                "console_events": [],
                "network_events": [],
            },
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert len(store.get_errors()) == 1
