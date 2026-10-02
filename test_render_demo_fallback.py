import os

from config import has_valid_redis_config, should_use_demo_mode


def test_demo_mode_defaults_to_enabled(monkeypatch):
    monkeypatch.delenv("DEMO_MODE", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.delenv("REDIS_HOST", raising=False)
    monkeypatch.delenv("REDIS_PASSWORD", raising=False)
    assert should_use_demo_mode() is True


def test_demo_mode_is_enabled_without_redis_url(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "false")
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.delenv("REDIS_HOST", raising=False)
    monkeypatch.delenv("REDIS_PASSWORD", raising=False)
    assert should_use_demo_mode() is True


def test_render_internal_redis_url_enables_streaming_without_auth(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "false")
    monkeypatch.setenv("REDIS_URL", "redis://red-example:6379")

    assert has_valid_redis_config() is True
    assert should_use_demo_mode() is False


def test_redis_password_without_remote_host_keeps_demo_enabled(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "false")
    monkeypatch.setenv("REDIS_PASSWORD", "configured-password")
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.delenv("REDIS_HOST", raising=False)

    assert has_valid_redis_config() is False
    assert should_use_demo_mode() is True


def test_api_uses_demo_fleet_when_redis_is_unavailable(monkeypatch):
    import api

    class UnavailableRedis:
        def ping(self):
            raise ConnectionError("Redis connection refused")

    monkeypatch.setattr(api, "DEMO_MODE", False)
    monkeypatch.setattr(api, "demo_fleet", None)
    monkeypatch.setattr(api, "r", UnavailableRedis())

    api.fallback_to_demo_if_redis_unavailable()

    assert api.health() == {"status": "ok", "mode": "demo", "redis": False}
    assert api.list_all_drivers()["count"] > 0
