"""End-to-end test of ModBridgeClient against a real ModBridge server."""
import asyncio
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Import custom_components.modbridge.api without executing the package
# __init__.py (which imports homeassistant).
pkg = types.ModuleType("custom_components")
pkg.__path__ = [str(ROOT / "custom_components")]
sys.modules["custom_components"] = pkg
mb = types.ModuleType("custom_components.modbridge")
mb.__path__ = [str(ROOT / "custom_components" / "modbridge")]
sys.modules["custom_components.modbridge"] = mb

import aiohttp
from custom_components.modbridge.api import (
    ModBridgeApiError,
    ModBridgeAuthError,
    ModBridgeClient,
    ModBridgeConnectionError,
    ModBridgePasswordChangeRequiredError,
)

HOST = "127.0.0.1"
PORT = 18080
INITIAL_PASSWORD = "*kU#3UoCo8=e#e=iPybbNkv-"
NEW_PASSWORD = "HaTest123!"


async def _tcp_target() -> asyncio.AbstractServer:
    """Tiny TCP server acting as the Modbus target device."""

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        try:
            while True:
                data = await reader.read(256)
                if not data:
                    break
                writer.write(data)  # echo
                await writer.drain()
        except ConnectionError:
            pass
        finally:
            writer.close()

    return await asyncio.start_server(handle, "127.0.0.1", 15021)


async def main() -> None:
    tcp_server = await _tcp_target()
    async with aiohttp.ClientSession() as session:
        # 1. bad credentials -> auth error
        bad = ModBridgeClient(session, HOST, PORT, "admin", "wrongpass")
        try:
            await bad.login()
            print("FAIL: bad login accepted")
            return
        except ModBridgeAuthError:
            print("PASS: invalid credentials -> ModBridgeAuthError")

        # 2. correct login; fresh installs force a password change
        #    (a previous test run may already have changed the password)
        client = None
        for candidate in (NEW_PASSWORD, INITIAL_PASSWORD):
            probe = ModBridgeClient(session, HOST, PORT, "admin", candidate)
            try:
                await probe.login()
                client = probe
                break
            except ModBridgeAuthError:
                continue
        assert client is not None, "neither password works"
        print("PASS: login")
        status = await client.async_get_status()
        assert "proxies" in status, status
        print("PASS: /api/status ->", {k: v for k, v in status.items() if k != "proxies"})

        try:
            await client.async_get_proxies()
            print("PASS: /api/proxies without password change (already changed)")
        except ModBridgePasswordChangeRequiredError:
            print("PASS: password change required detected")
            await client.async_change_password(INITIAL_PASSWORD, NEW_PASSWORD)
            print("PASS: password changed via /api/config/password")
            proxies = await client.async_get_proxies()
            assert isinstance(proxies, list)
            print(f"PASS: /api/proxies -> {len(proxies)} proxies")

        # 4. create a test proxy (enabled -> auto-starts) via raw request
        proxy_cfg = {
            "id": "test-ha-proxy-0001",
            "name": "HA Test",
            "listen_addr": "127.0.0.1:15020",
            "target_addr": "127.0.0.1:15021",
            "connection_timeout": 5,
            "read_timeout": 5,
            "max_retries": 1,
            "max_read_size": 1024,
            "connect_delay_ms": 0,
            "enabled": True,
            "paused": False,
        }
        await client._request("POST", "/api/proxies", json=proxy_cfg)
        print("PASS: created proxy via POST /api/proxies (CSRF flow works)")

        proxies = await client.async_get_proxies()
        assert any(p["id"] == proxy_cfg["id"] for p in proxies)
        p0 = next(p for p in proxies if p["id"] == proxy_cfg["id"])
        assert p0["status"] == "Running", p0
        print("PASS: enabled proxy auto-started -> Running")

        # 5. control: stop / start / start_all
        await client.async_control_proxy(proxy_cfg["id"], "stop")
        proxies = await client.async_get_proxies()
        p0 = next(p for p in proxies if p["id"] == proxy_cfg["id"])
        assert p0["status"] == "Stopped", p0["status"]
        print("PASS: control stop -> Stopped")

        await client.async_control_proxy(proxy_cfg["id"], "start")
        proxies = await client.async_get_proxies()
        p0 = next(p for p in proxies if p["id"] == proxy_cfg["id"])
        assert p0["status"] == "Running", p0["status"]
        print("PASS: control start -> Running")

        await client.async_control_proxy(proxy_cfg["id"], "stop")
        await client.async_control_all("start_all")
        proxies = await client.async_get_proxies()
        p0 = next(p for p in proxies if p["id"] == proxy_cfg["id"])
        # ModBridge semantics: stop() disables the proxy and start_all only
        # starts enabled proxies -> remains stopped.
        assert p0["status"] == "Stopped" and p0["enabled"] is False, p0
        print("PASS: start_all skips disabled proxies (upstream semantics)")

        await client.async_control_proxy(proxy_cfg["id"], "start")
        proxies = await client.async_get_proxies()
        p0 = next(p for p in proxies if p["id"] == proxy_cfg["id"])
        assert p0["status"] == "Running", p0["status"]
        print("PASS: control start -> Running")

        await client.async_control_all("stop_all")
        proxies = await client.async_get_proxies()
        p0 = next(p for p in proxies if p["id"] == proxy_cfg["id"])
        assert p0["status"] == "Stopped", p0["status"]
        print("PASS: control stop_all -> Stopped")

        # 6. pause / resume
        await client.async_control_proxy(proxy_cfg["id"], "pause")
        proxies = await client.async_get_proxies()
        p0 = next(p for p in proxies if p["id"] == proxy_cfg["id"])
        assert p0["paused"] is True and p0["status"] == "Stopped", p0
        print("PASS: control pause -> paused=True, Stopped")

        await client.async_control_proxy(proxy_cfg["id"], "resume")
        proxies = await client.async_get_proxies()
        p0 = next(p for p in proxies if p["id"] == proxy_cfg["id"])
        assert p0["paused"] is False and p0["status"] == "Running", p0
        print("PASS: control resume -> paused=False, Running")

        # 7. system info
        info = await client.async_get_system_info()
        assert "running_proxies" in info and "uptime_seconds" in info, info
        print("PASS: /api/system/info ->", {k: info[k] for k in ("running_proxies", "total_proxies", "uptime_seconds", "go_version")})

        # 8. version endpoint (may hit GitHub)
        version = await client.async_get_version()
        print("PASS: version ->", version)

        # 9. unknown proxy control -> API error
        try:
            await client.async_control_proxy("does-not-exist", "start")
            print("FAIL: control on unknown proxy did not raise")
            return
        except ModBridgeApiError as err:
            print(f"PASS: unknown proxy -> ModBridgeApiError ({err})")

        # 10. session expiry auto-relogin: forge an invalid session token
        client._session_token = "forged"
        proxies = await client.async_get_proxies()
        assert proxies, "no proxies after re-login"
        print("PASS: auto re-login after invalid session token")

        # 11. logout
        await client.close()
        print("PASS: logout / close")

    print("\nALL TESTS PASSED")
    tcp_server.close()
    await tcp_server.wait_closed()


asyncio.run(main())
