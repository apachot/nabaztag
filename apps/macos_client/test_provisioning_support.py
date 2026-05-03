from __future__ import annotations

import socket
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import provisioning_support


LEGACY_FORM_HTML = """
<html>
  <body>
    <table>
      <tr><td>Serial number:</td><td>001122334455</td></tr>
    </table>
    <form action="b.htm" method="GET">
      <input type="hidden" name="w" value="-">
      <input type="text" name="k" value="">
      <input type="text" name="m" value="">
      <input type="password" name="n" value="">
      <input type="hidden" name="l" value="0">
      <input type="hidden" name="f" value="1">
      <input type="hidden" name="g" value="0.0.0.0">
      <input type="hidden" name="h" value="255.255.255.0">
      <input type="hidden" name="i" value="0.0.0.0">
      <input type="hidden" name="j" value="0.0.0.0">
      <input type="hidden" name="c" value="0">
      <input type="hidden" name="d" value="0.0.0.0">
      <input type="hidden" name="e" value="0">
      <input type="submit" name="z2" value="Update and Start">
    </form>
  </body>
</html>
"""

LEGACY_FORM_WITH_ADVANCED_LINK_HTML = """
<html>
  <body>
    <a href="advanced.htm">Advanced configuration</a>
    <form action="b.htm" method="GET">
      <input type="hidden" name="w" value="-">
      <input type="text" name="k" value="">
      <input type="text" name="m" value="">
      <input type="password" name="n" value="">
      <input type="hidden" name="l" value="0">
      <input type="hidden" name="f" value="1">
      <input type="hidden" name="g" value="0.0.0.0">
      <input type="hidden" name="h" value="255.255.255.0">
      <input type="hidden" name="i" value="0.0.0.0">
      <input type="hidden" name="j" value="0.0.0.0">
      <input type="hidden" name="c" value="0">
      <input type="hidden" name="d" value="0.0.0.0">
      <input type="hidden" name="e" value="0">
      <input type="submit" name="z2" value="Update and Start">
    </form>
  </body>
</html>
"""

LEGACY_RADIO_FORM_HTML = """
<html>
  <body>
    <table>
      <tr><td>Serial number:</td><td>001122334455</td></tr>
    </table>
    <form action="b.htm" method="GET">
      <input type="hidden" name="w" value="-">
      <input type="text" name="k" value="">
      <input type="radio" name="m" value="0">
      <input type="radio" name="m" value="16">
      <input type="radio" name="m" value="32">
      <input type="radio" name="m" value="64" checked>
      <input type="password" name="n" value="">
      <input type="hidden" name="l" value="0">
      <input type="hidden" name="f" value="1">
      <input type="hidden" name="g" value="0.0.0.0">
      <input type="hidden" name="h" value="255.255.255.0">
      <input type="hidden" name="i" value="0.0.0.0">
      <input type="hidden" name="j" value="0.0.0.0">
      <input type="hidden" name="c" value="0">
      <input type="hidden" name="d" value="0.0.0.0">
      <input type="hidden" name="e" value="0">
      <input type="submit" name="z2" value="Update and Start">
    </form>
  </body>
</html>
"""


class ConfigureBootstrapHostTests(unittest.TestCase):
    def test_retries_root_page_when_first_fetch_times_out(self) -> None:
        root_url = "http://192.168.0.1/"
        call_count = {"root": 0}

        def fake_fetch(_opener, *, url, method="GET", payload=None, timeout=15):
            if url == root_url:
                call_count["root"] += 1
                if call_count["root"] == 1:
                    raise socket.timeout("timed out")
                return root_url, LEGACY_FORM_HTML
            if url.startswith("http://192.168.0.1/b.htm"):
                self.assertEqual(method, "GET")
                self.assertIsNotNone(payload)
                return url, "saved"
            raise AssertionError(f"Unexpected URL: {url}")

        with patch.object(provisioning_support, "_fetch", side_effect=fake_fetch), patch.object(
            provisioning_support.time, "sleep", return_value=None
        ):
            result = provisioning_support.configure_bootstrap_host(
                host="192.168.0.1",
                home_wifi_ssid="Maison",
                home_wifi_password="secret",
                portal_base="https://nabaztag.org",
            )

        self.assertEqual(call_count["root"], 2)
        self.assertTrue(result["submitted"])
        self.assertTrue(result["success_hint"])

    def test_uses_current_form_when_advanced_page_times_out(self) -> None:
        root_url = "http://192.168.0.1/"
        advanced_url = "http://192.168.0.1/advanced.htm"
        advanced_attempts = 0

        def fake_fetch(_opener, *, url, method="GET", payload=None, timeout=15):
            nonlocal advanced_attempts
            if url == root_url:
                return root_url, LEGACY_FORM_WITH_ADVANCED_LINK_HTML
            if url == advanced_url:
                advanced_attempts += 1
                raise socket.timeout("timed out")
            if url.startswith("http://192.168.0.1/b.htm"):
                self.assertEqual(method, "GET")
                self.assertIsNotNone(payload)
                return url, "saved"
            raise AssertionError(f"Unexpected URL: {url}")

        with patch.object(provisioning_support, "_fetch", side_effect=fake_fetch), patch.object(
            provisioning_support.time, "sleep", return_value=None
        ):
            result = provisioning_support.configure_bootstrap_host(
                host="192.168.0.1",
                home_wifi_ssid="Maison",
                home_wifi_password="secret",
                portal_base="https://nabaztag.org",
            )

        self.assertEqual(advanced_attempts, 3)
        self.assertTrue(result["submitted"])
        self.assertTrue(result["success_hint"])

    def test_unknown_security_with_password_defaults_to_wpa(self) -> None:
        captured_payloads: list[dict] = []

        def fake_fetch(_opener, *, url, method="GET", payload=None, timeout=15):
            if url == "http://192.168.0.1/":
                return url, LEGACY_RADIO_FORM_HTML
            if url.startswith("http://192.168.0.1/b.htm"):
                captured_payloads.append(dict(payload or {}))
                return url, "saved"
            raise AssertionError(f"Unexpected URL: {url}")

        with patch.object(provisioning_support, "_fetch", side_effect=fake_fetch):
            result = provisioning_support.configure_bootstrap_host(
                host="192.168.0.1",
                home_wifi_ssid="Maison",
                home_wifi_password="secret",
                home_wifi_security="",
                portal_base="https://nabaztag.org",
            )

        self.assertTrue(result["submitted"])
        self.assertEqual(captured_payloads[-1]["m"], "32")

    def test_wpa2_security_selects_wpa2_when_supported(self) -> None:
        captured_payloads: list[dict] = []

        def fake_fetch(_opener, *, url, method="GET", payload=None, timeout=15):
            if url == "http://192.168.0.1/":
                return url, LEGACY_RADIO_FORM_HTML
            if url.startswith("http://192.168.0.1/b.htm"):
                captured_payloads.append(dict(payload or {}))
                return url, "saved"
            raise AssertionError(f"Unexpected URL: {url}")

        with patch.object(provisioning_support, "_fetch", side_effect=fake_fetch):
            result = provisioning_support.configure_bootstrap_host(
                host="192.168.0.1",
                home_wifi_ssid="Maison",
                home_wifi_password="secret",
                home_wifi_security="WPA2 Personal",
                portal_base="https://nabaztag.org",
            )

        self.assertTrue(result["submitted"])
        self.assertEqual(captured_payloads[-1]["m"], "64")


if __name__ == "__main__":
    unittest.main()
