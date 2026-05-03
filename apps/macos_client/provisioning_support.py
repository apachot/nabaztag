from __future__ import annotations

import html
import re
import socket
import subprocess
import sys
import time
import webbrowser
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from http.cookiejar import CookieJar
from urllib import parse as urllib_parse
from urllib import request as urllib_request

try:
    import CoreLocation  # type: ignore
except Exception:  # pragma: no cover - optional on some environments
    CoreLocation = None

try:
    import CoreWLAN  # type: ignore
except Exception:  # pragma: no cover - optional on some environments
    CoreWLAN = None

_location_manager = None
_location_delegate = None


if CoreLocation is not None:
    class _LocationAuthorizationDelegate(CoreLocation.NSObject):  # type: ignore[misc,name-defined]
        def locationManagerDidChangeAuthorization_(self, _manager) -> None:
            # The callback only keeps the delegate alive long enough for macOS
            # to present and persist the authorization state for the app.
            return
else:
    _LocationAuthorizationDelegate = None


def normalize_portal_base(portal: str) -> str:
    normalized = portal.strip().rstrip("/")
    parsed = urllib_parse.urlparse(normalized)
    host = (parsed.hostname or "").strip().lower()
    if parsed.scheme == "http" and host not in {"localhost", "127.0.0.1"}:
        parsed = parsed._replace(scheme="https")
        normalized = urllib_parse.urlunparse(parsed).rstrip("/")
    return normalized


def build_violet_platform_value(portal: str) -> str:
    normalized = normalize_portal_base(portal)
    parsed = urllib_parse.urlparse(normalized if "://" in normalized else f"https://{normalized}")
    host = parsed.netloc or parsed.path
    return f"{host.rstrip('/')}/vl"


def detect_wifi_interface() -> str | None:
    result = subprocess.run(
        ["networksetup", "-listallhardwareports"],
        capture_output=True,
        text=True,
        check=False,
    )
    output = result.stdout or ""
    match = re.search(r"Hardware Port: Wi-Fi\s+Device: ([^\n]+)", output, re.MULTILINE)
    if match:
        return match.group(1).strip()
    match = re.search(r"Hardware Port: AirPort\s+Device: ([^\n]+)", output, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return None


def current_wifi_ssid() -> tuple[str | None, str | None]:
    interface = detect_wifi_interface()
    if not interface:
        return None, None
    result = subprocess.run(
        ["networksetup", "-getairportnetwork", interface],
        capture_output=True,
        text=True,
        check=False,
    )
    output = (result.stdout or result.stderr or "").strip()
    match = re.search(r"Current (?:Wi-Fi|AirPort) Network: (.+)$", output)
    if match:
        return interface, match.group(1).strip()

    if CoreWLAN is not None:
        try:
            client = CoreWLAN.CWWiFiClient.sharedWiFiClient()
            for candidate in list(client.interfaces() or []):
                candidate_name = str(candidate.interfaceName() or "").strip()
                if candidate_name != interface:
                    continue
                ssid = " ".join(str(candidate.ssid() or "").split()).strip()
                return interface, ssid or None
        except Exception:
            pass

    return interface, None


def read_wifi_password(ssid: str) -> str | None:
    network = " ".join(ssid.split()).strip()
    if not network:
        return None
    result = subprocess.run(
        ["security", "find-generic-password", "-D", "AirPort network password", "-wa", network],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    password = (result.stdout or "").strip()
    return password or None


def current_wifi_security() -> str | None:
    result = subprocess.run(
        ["system_profiler", "SPAirPortDataType"],
        capture_output=True,
        text=True,
        check=False,
    )
    output = result.stdout or ""
    match = re.search(r"Current Network Information:\s+.*?\n\s+Security:\s+([^\n]+)", output, re.S)
    if match:
        return " ".join(match.group(1).split()).strip()
    return None


def current_wifi_configuration() -> dict[str, str]:
    interface, ssid = current_wifi_ssid()
    if not interface or not ssid:
        raise RuntimeError("Impossible de determiner le Wi-Fi maison actuel du Mac.")
    security = current_wifi_security() or ""
    return {
        "interface": interface,
        "ssid": ssid,
        "password": "",
        "security": security,
    }


def _corewlan_interface(preferred_name: str | None = None):
    if CoreWLAN is None:
        return None, preferred_name

    client = CoreWLAN.CWWiFiClient.sharedWiFiClient()
    interfaces = list(client.interfaces() or [])
    if not interfaces:
        return None, preferred_name

    selected_interface = None
    if preferred_name:
        for candidate in interfaces:
            candidate_name = str(candidate.interfaceName() or "").strip()
            if candidate_name == preferred_name:
                selected_interface = candidate
                break
    if selected_interface is None:
        selected_interface = interfaces[0]
    interface_name = str(selected_interface.interfaceName() or "").strip() or preferred_name
    return selected_interface, interface_name


def _corewlan_network_for_ssid(interface, ssid: str):
    try:
        scan_result, scan_error = interface.scanForNetworksWithName_error_(ssid, None)
    except Exception:
        scan_result, scan_error = None, None
    if scan_error is None:
        for network in scan_result or []:
            candidate_ssid = " ".join(str(network.ssid() or "").split()).strip()
            if candidate_ssid == ssid:
                return network

    try:
        scan_result, scan_error = interface.scanForNetworksWithName_error_(None, None)
    except Exception as exc:
        raise RuntimeError(f"Echec du scan Wi-Fi CoreWLAN avant connexion: {exc}") from exc
    if scan_error is not None:
        raise RuntimeError(f"Echec du scan Wi-Fi CoreWLAN avant connexion: {scan_error}")
    for network in scan_result or []:
        candidate_ssid = " ".join(str(network.ssid() or "").split()).strip()
        if candidate_ssid == ssid:
            return network
    return None


def connect_wifi_network(ssid: str, password: str | None = None) -> tuple[str, str]:
    interface = detect_wifi_interface()
    if not interface:
        raise RuntimeError("Impossible d'identifier l'interface Wi-Fi du Mac.")

    corewlan_error = None
    selected_interface, interface = _corewlan_interface(interface)
    if selected_interface is not None:
        try:
            network = _corewlan_network_for_ssid(selected_interface, ssid)
            if network is None:
                raise RuntimeError(f"Le reseau {ssid} n'a pas ete retrouve par CoreWLAN.")
            assoc_result = selected_interface.associateToNetwork_password_error_(
                network,
                password or None,
                None,
            )
            if isinstance(assoc_result, tuple):
                success = bool(assoc_result[0]) if assoc_result else True
                assoc_error = assoc_result[1] if len(assoc_result) > 1 else None
                if not success or assoc_error is not None:
                    raise RuntimeError(str(assoc_error or f"Connexion au reseau {ssid} impossible."))
        except Exception as exc:
            corewlan_error = str(exc)

    if corewlan_error is not None:
        command = ["networksetup", "-setairportnetwork", interface, ssid]
        if password:
            command.append(password)
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )
        output = " ".join((result.stdout or result.stderr or "").split()).strip()
        if result.returncode != 0:
            detail = output or corewlan_error or f"Connexion au reseau {ssid} impossible."
            raise RuntimeError(detail)

    for _attempt in range(30):
        current_interface, current_ssid = current_wifi_ssid()
        if (current_interface or interface) == interface and (current_ssid or "").strip() == ssid:
            return interface, ssid
        time.sleep(1.0)

    current_interface, current_ssid = current_wifi_ssid()
    if (current_interface or interface) == interface and (current_ssid or "").strip() == ssid:
        return interface, ssid
    raise RuntimeError(f"Le Mac ne semble pas connecte au reseau {ssid} apres la tentative de bascule.")


def _security_mode_value(security: str, *, has_password: bool = False) -> str:
    lowered = security.lower()
    if "wpa2" in lowered or "wpa3" in lowered:
        return "64"
    if "wpa" in lowered:
        return "32"
    if "wep" in lowered:
        return "16"
    if has_password:
        return "32"
    return "0"


def location_authorization_status() -> str:
    if CoreLocation is None:
        return "unavailable"
    try:
        status = int(CoreLocation.CLLocationManager.authorizationStatus())
    except Exception:
        return "unavailable"
    mapping = {
        0: "not_determined",
        1: "restricted",
        2: "denied",
        3: "authorized_always",
        4: "authorized_when_in_use",
    }
    return mapping.get(status, f"unknown:{status}")


def request_location_authorization() -> str:
    if CoreLocation is None:
        return "unavailable"
    global _location_delegate
    global _location_manager
    try:
        if _location_manager is None:
            _location_manager = CoreLocation.CLLocationManager.alloc().init()
        if _location_delegate is None and _LocationAuthorizationDelegate is not None:
            _location_delegate = _LocationAuthorizationDelegate.alloc().init()
            _location_manager.setDelegate_(_location_delegate)
        _location_manager.requestWhenInUseAuthorization()
        _location_manager.startUpdatingLocation()
    except Exception:
        return "unavailable"
    return location_authorization_status()


def open_location_settings() -> bool:
    candidates = [
        "x-apple.systempreferences:com.apple.preference.security?Privacy_LocationServices",
        "x-apple.systempreferences:com.apple.settings.PrivacySecurity.extension?Privacy_LocationServices",
    ]
    for candidate in candidates:
        result = subprocess.run(["open", candidate], capture_output=True, text=True, check=False)
        if result.returncode == 0:
            return True
    fallback = subprocess.run(["open", "/System/Applications/System Settings.app"], check=False)
    return fallback.returncode == 0


def scan_nearby_setup_networks() -> tuple[str | None, list[str], str | None]:
    interface, current_ssid = current_wifi_ssid()

    if CoreWLAN is None:
        return interface, [], "Le framework Wi-Fi macOS CoreWLAN est indisponible sur ce Mac."

    client = CoreWLAN.CWWiFiClient.sharedWiFiClient()
    interfaces = list(client.interfaces() or [])
    if not interfaces:
        return interface, [], "Aucune interface Wi-Fi CoreWLAN n'a ete detectee sur ce Mac."

    networks: list[str] = []
    selected_interface = None
    if interface:
        for candidate in interfaces:
            if str(candidate.interfaceName() or "").strip() == interface:
                selected_interface = candidate
                break
    if selected_interface is None:
        selected_interface = interfaces[0]
        interface = str(selected_interface.interfaceName() or "").strip() or interface

    scan_result = None
    scan_error = None
    last_exception: Exception | None = None
    collected_networks: list[str] = []
    for scan_index in range(4):
        try:
            scan_result, scan_error = selected_interface.scanForNetworksWithName_error_(None, None)
            if scan_error is None:
                for network in scan_result or []:
                    ssid = " ".join(str(network.ssid() or "").split()).strip()
                    if not ssid:
                        continue
                    if not ssid.lower().startswith("nabaztag"):
                        continue
                    if ssid not in collected_networks:
                        collected_networks.append(ssid)
                if collected_networks:
                    break
                if scan_index < 3:
                    time.sleep(1.0)
                continue
            error_domain = str(getattr(scan_error, "domain", lambda: "")() or "")
            error_code = int(getattr(scan_error, "code", lambda: 0)() or 0)
            if error_domain == "NSPOSIXErrorDomain" and error_code == 16:
                time.sleep(1.0)
                continue
            return interface, [], f"Echec du scan Wi-Fi CoreWLAN: {scan_error}"
        except Exception as exc:
            last_exception = exc
            if "Code=16" in str(exc):
                time.sleep(1.0)
                continue
            return interface, [], f"Echec du scan Wi-Fi CoreWLAN: {exc}"

    if scan_error is not None:
        return (
            interface,
            [],
            "Le scan Wi-Fi macOS est temporairement occupe. "
            "Attends quelques secondes, puis relance la recherche.",
        )
    if last_exception is not None and scan_result is None:
            return (
                interface,
                [],
                "Le scan Wi-Fi macOS est temporairement occupe. "
                "Attends quelques secondes, puis relance la recherche.",
            )

    networks.extend(collected_networks)

    if current_ssid and current_ssid.lower().startswith("nabaztag") and current_ssid not in networks:
        networks.insert(0, current_ssid)

    if networks:
        return interface, networks, None

    auth_status = location_authorization_status()
    if auth_status in {"not_determined", "restricted", "denied"}:
        return (
            interface,
            [],
            "Le scan Wi-Fi macOS semble bloqué par l'autorisation de localisation. "
            "Autorise Nabaztag dans Reglages Systeme > Confidentialite et securite > Service de localisation.",
        )
    if not interface:
        return None, [], "Aucune interface Wi-Fi active n'a été détectée sur ce Mac."
    return interface, [], "Aucun réseau Nabaztag détecté à proximité."


@dataclass
class HtmlOption:
    value: str
    label: str


@dataclass
class HtmlField:
    name: str
    field_type: str
    value: str = ""
    checked: bool = False
    options: list[HtmlOption] = field(default_factory=list)


@dataclass
class HtmlForm:
    action: str
    method: str
    fields: list[HtmlField] = field(default_factory=list)


@dataclass
class HtmlLink:
    href: str
    text: str


class _FormParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.forms: list[HtmlForm] = []
        self.links: list[HtmlLink] = []
        self._current_form: HtmlForm | None = None
        self._current_select: HtmlField | None = None
        self._current_option_value = ""
        self._current_option_text: list[str] = []
        self._current_link_href: str | None = None
        self._current_link_text: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        attr_map = {key.lower(): value for key, value in attrs}
        if tag == "form":
            self._current_form = HtmlForm(
                action=str(attr_map.get("action") or "").strip(),
                method=str(attr_map.get("method") or "GET").strip().upper(),
            )
            self.forms.append(self._current_form)
            return
        if tag == "a":
            self._current_link_href = str(attr_map.get("href") or "").strip()
            self._current_link_text = []
            return
        if self._current_form is None:
            return
        if tag == "input":
            name = str(attr_map.get("name") or "").strip()
            if not name:
                return
            self._current_form.fields.append(
                HtmlField(
                    name=name,
                    field_type=str(attr_map.get("type") or "text").strip().lower(),
                    value=str(attr_map.get("value") or "").strip(),
                    checked="checked" in attr_map,
                )
            )
            return
        if tag == "textarea":
            name = str(attr_map.get("name") or "").strip()
            if not name:
                return
            self._current_form.fields.append(HtmlField(name=name, field_type="textarea"))
            return
        if tag == "select":
            name = str(attr_map.get("name") or "").strip()
            if not name:
                return
            select_field = HtmlField(name=name, field_type="select")
            self._current_form.fields.append(select_field)
            self._current_select = select_field
            return
        if tag == "option" and self._current_select is not None:
            self._current_option_value = str(attr_map.get("value") or "").strip()
            self._current_option_text = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._current_link_href is not None:
            text = " ".join("".join(self._current_link_text).split()).strip()
            self.links.append(HtmlLink(href=self._current_link_href, text=text))
            self._current_link_href = None
            self._current_link_text = []
            return
        if tag == "select":
            self._current_select = None
            return
        if tag == "option" and self._current_select is not None:
            label = " ".join("".join(self._current_option_text).split()).strip()
            self._current_select.options.append(HtmlOption(value=self._current_option_value, label=label))
            self._current_option_value = ""
            self._current_option_text = []

    def handle_data(self, data: str) -> None:
        if self._current_link_href is not None:
            self._current_link_text.append(data)
        if self._current_select is not None and self._current_option_value is not None:
            self._current_option_text.append(data)


def _fetch(
    opener,
    *,
    url: str,
    method: str = "GET",
    payload: dict[str, str] | None = None,
    timeout: float = 15,
) -> tuple[str, str]:
    body = None
    headers = {"User-Agent": "Nabaztag macOS Client/0.3"}
    if payload is not None:
        encoded_payload = urllib_parse.urlencode(payload)
        if method.upper() == "GET":
            separator = "&" if urllib_parse.urlparse(url).query else "?"
            url = f"{url}{separator}{encoded_payload}"
        else:
            body = encoded_payload.encode("utf-8")
            headers["Content-Type"] = "application/x-www-form-urlencoded"
    request_object = urllib_request.Request(url, data=body, headers=headers, method=method.upper())
    with opener.open(request_object, timeout=timeout) as response:
        final_url = response.geturl()
        content = response.read().decode("utf-8", errors="replace")
    return final_url, content


def _fetch_with_retries(
    opener,
    *,
    url: str,
    method: str = "GET",
    payload: dict[str, str] | None = None,
    timeout: float = 15,
    attempts: int = 3,
    retry_delay: float = 1.0,
) -> tuple[str, str]:
    last_error: Exception | None = None
    for attempt in range(max(1, attempts)):
        try:
            return _fetch(
                opener,
                url=url,
                method=method,
                payload=payload,
                timeout=timeout,
            )
        except Exception as exc:
            last_error = exc
            if attempt >= attempts - 1 or not _looks_like_timeout(exc):
                raise
            time.sleep(retry_delay)
    raise RuntimeError(str(last_error or f"Echec HTTP sur {url}."))


def _parse(url: str, content: str) -> tuple[list[HtmlForm], list[HtmlLink]]:
    parser = _FormParser()
    parser.feed(content)
    links = []
    for link in parser.links:
        resolved = urllib_parse.urljoin(url, link.href)
        links.append(HtmlLink(href=resolved, text=link.text))
    return parser.forms, links


def _extract_bootstrap_serial(content: str) -> str:
    match = re.search(
        r"Serial\s*number:\s*</td>\s*<td>\s*([^<\s]+)\s*</td>",
        content,
        flags=re.I | re.S,
    )
    if not match:
        return ""
    raw_serial = html.unescape(match.group(1)).strip()
    normalized = ":".join(part.lower() for part in re.findall(r"[0-9A-Fa-f]{2}", raw_serial))
    return normalized if len(normalized) == 17 else raw_serial


def probe_bootstrap_host(host: str = "192.168.0.1") -> dict[str, str | bool]:
    opener = urllib_request.build_opener(urllib_request.HTTPCookieProcessor(CookieJar()))
    root_url = f"http://{host.strip().rstrip('/')}/"
    last_error: Exception | None = None
    for _attempt in range(10):
        try:
            final_url, content = _fetch(opener, url=root_url)
            break
        except Exception as exc:
            last_error = exc
            time.sleep(1.0)
    else:
        raise RuntimeError(str(last_error or f"Le configurateur local sur {root_url} ne repond pas."))
    forms, links = _parse(final_url, content)
    start_url = ""
    advanced_url = ""
    for link in links:
        text = link.text.lower()
        if not start_url and "start" in text:
            start_url = link.href
        if not advanced_url and "advanced" in text:
            advanced_url = link.href
    return {
        "reachable": True,
        "url": final_url,
        "title_hint": html.unescape(" ".join(re.findall(r"<title[^>]*>(.*?)</title>", content, flags=re.I | re.S))).strip(),
        "serial": _extract_bootstrap_serial(content),
        "has_form": bool(forms),
        "has_start_link": bool(start_url),
        "start_url": start_url,
        "advanced_url": advanced_url,
    }


def _field_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", name.strip().lower())


def _looks_like_timeout(exc: Exception) -> bool:
    if isinstance(exc, TimeoutError | socket.timeout):
        return True
    return "timed out" in str(exc).lower()


def _choose_option(field: HtmlField, preferences: list[str]) -> str | None:
    lowered = [(option, f"{option.value} {option.label}".strip().lower()) for option in field.options]
    for preference in preferences:
        for option, haystack in lowered:
            if preference in haystack:
                return option.value or option.label
    return field.options[0].value if field.options else None


def _security_value_preferences(security: str, *, has_password: bool) -> list[str]:
    target_value = _security_mode_value(security, has_password=has_password)
    if target_value == "64":
        return ["64", "32", "16", "0"]
    if target_value == "32":
        return ["32", "64", "16", "0"]
    if target_value == "16":
        return ["16", "0", "32", "64"]
    return ["0", "16", "32", "64"]


def _looks_like_security_select(field: HtmlField) -> bool:
    option_values = {str(option.value).strip() for option in field.options if str(option.value).strip()}
    if field.name == "m" and option_values.intersection({"0", "16", "32", "64"}):
        return True
    encryption_labels = sum(
        1
        for option in field.options
        if any(
            token in f"{option.label} {option.value}".lower()
            for token in ("no encryption", "wep", "wpa", "wpa2")
        )
    )
    return encryption_labels >= 2


def _looks_like_security_radio_group(group_name: str, fields: list[HtmlField]) -> bool:
    values = {str(field.value).strip() for field in fields if str(field.value).strip()}
    if group_name == "m" and values.intersection({"0", "16", "32", "64"}):
        return True
    return values.issubset({"0", "16", "32", "64"}) and len(values) >= 3


def _choose_security_radio_value(
    fields: list[HtmlField],
    *,
    security: str,
    has_password: bool,
) -> str | None:
    preferences = _security_value_preferences(security, has_password=has_password)
    values = {str(field.value).strip(): field for field in fields if str(field.value).strip()}
    for preference in preferences:
        if preference in values:
            return values[preference].value or preference
    return None


def _build_payload_for_form(
    form: HtmlForm,
    *,
    home_wifi_ssid: str,
    home_wifi_password: str,
    home_wifi_security: str,
    violet_platform: str,
) -> tuple[dict[str, str], int]:
    payload: dict[str, str] = {}
    matched = 0
    radio_groups: dict[str, list[HtmlField]] = {}

    for field in form.fields:
        if field.field_type == "radio":
            radio_groups.setdefault(field.name, []).append(field)
            continue
        key = _field_key(field.name)
        value = field.value
        if "violet" in key or ("platform" in key and "violet" in f"{field.name} {field.value}".lower()):
            value = violet_platform
            matched += 1
        elif "ssid" in key:
            value = home_wifi_ssid
            matched += 1
        elif any(token in key for token in ("password", "passwd", "passphrase", "wepkey", "wpakey", "key")) and "serial" not in key:
            value = home_wifi_password
            matched += 1
        elif "dhcp" in key:
            value = value or "1"
        elif "proxy" in key:
            value = value or "0"
        elif field.field_type == "select" and field.options:
            choice = None
            if "auth" in key:
                choice = _choose_option(field, ["open", "opensystem", "open system"])
            elif any(token in key for token in ("encrypt", "crypt", "secu", "security")) or _looks_like_security_select(field):
                choice = _choose_option(
                    field,
                    _security_value_preferences(
                        home_wifi_security,
                        has_password=bool(home_wifi_password),
                    ),
                )
                if choice is None:
                    choice = _choose_option(field, ["wpa2", "wpa", "aes", "no encryption", "none"])
            elif "dhcp" in key:
                choice = _choose_option(field, ["yes", "true", "1", "enabled"])
            elif "proxy" in key:
                choice = _choose_option(field, ["no", "false", "0", "disabled"])
            value = choice or value
        payload[field.name] = value

    for group_name, fields in radio_groups.items():
        key = _field_key(group_name)
        chosen = None
        if any(token in key for token in ("encrypt", "crypt", "secu", "security")) or _looks_like_security_radio_group(group_name, fields):
            chosen = _choose_security_radio_value(
                fields,
                security=home_wifi_security,
                has_password=bool(home_wifi_password),
            )
        elif "dhcp" in key:
            for field in fields:
                if any(token in f"{field.name} {field.value}".lower() for token in ("1", "true", "yes", "on", "enable")):
                    chosen = field.value or "on"
                    break
        if chosen is None:
            checked = next((field for field in fields if field.checked), None)
            chosen = checked.value if checked else fields[0].value or "on"
        payload[group_name] = chosen

    return payload, matched


def _follow_link_with_timeout_fallback(
    opener,
    *,
    current_url: str,
    content: str,
    forms: list[HtmlForm],
    links: list[HtmlLink],
    text_fragment: str,
    attempts: int = 3,
) -> tuple[str, str, list[HtmlForm], list[HtmlLink]]:
    target_url = next((link.href for link in links if text_fragment in link.text.lower()), "")
    if not target_url:
        return current_url, content, forms, links
    try:
        next_url, next_content = _fetch_with_retries(
            opener,
            url=target_url,
            attempts=attempts,
        )
    except Exception as exc:
        if not _looks_like_timeout(exc):
            raise
        return current_url, content, forms, links
    next_forms, next_links = _parse(next_url, next_content)
    if next_forms or next_links:
        return next_url, next_content, next_forms, next_links
    return current_url, content, forms, links


def configure_bootstrap_host(
    *,
    host: str,
    home_wifi_ssid: str,
    home_wifi_password: str,
    portal_base: str,
    home_wifi_security: str = "",
) -> dict[str, str | bool]:
    opener = urllib_request.build_opener(urllib_request.HTTPCookieProcessor(CookieJar()))
    root_url = f"http://{host.strip().rstrip('/')}/"
    current_url, content = _fetch_with_retries(opener, url=root_url, attempts=5)
    bootstrap_serial = _extract_bootstrap_serial(content)
    forms, links = _parse(current_url, content)

    current_url, content, forms, links = _follow_link_with_timeout_fallback(
        opener,
        current_url=current_url,
        content=content,
        forms=forms,
        links=links,
        text_fragment="start",
    )
    current_url, content, forms, links = _follow_link_with_timeout_fallback(
        opener,
        current_url=current_url,
        content=content,
        forms=forms,
        links=links,
        text_fragment="advanced",
    )

    if not forms:
        raise RuntimeError("Le configurateur local du lapin n'expose aucun formulaire exploitable.")

    violet_platform = build_violet_platform_value(portal_base)
    legacy_form = next(
        (
            form
            for form in forms
            if any(field.name in {"w", "k", "m", "n", "l", "f", "g", "h", "i", "j", "c", "d", "e", "z2"} for field in form.fields)
        ),
        None,
    )
    if legacy_form is not None:
        legacy_payload = {
            "w": "-",
            "k": home_wifi_ssid,
            "m": _security_mode_value(
                home_wifi_security,
                has_password=bool(home_wifi_password),
            ),
            "n": home_wifi_password,
            "l": "0",
            "f": "1",
            "g": "0.0.0.0",
            "h": "255.255.255.0",
            "i": "0.0.0.0",
            "j": "0.0.0.0",
            "c": "0",
            "d": "0.0.0.0",
            "e": "0",
            "z2": "Update and Start",
            "a": violet_platform,
        }
        submit_url = urllib_parse.urljoin(current_url, legacy_form.action or current_url)
        try:
            final_url, response_content = _fetch(
                opener,
                url=submit_url,
                method=legacy_form.method or "GET",
                payload=legacy_payload,
            )
        except Exception as exc:
            if not _looks_like_timeout(exc):
                raise
            return {
                "submitted": True,
                "success_hint": True,
                "serial": bootstrap_serial,
                "violet_platform": violet_platform,
                "url": submit_url,
                "message": (
                    "Configuration envoyee au lapin. Il a probablement applique les parametres "
                    "et coupe son Wi-Fi de configuration avant de repondre completement."
                ),
            }
        lower_content = response_content.lower()
        success = any(token in lower_content for token in ("update", "start", "restart", "reboot", "saved", "applied"))
        return {
            "submitted": True,
            "success_hint": success,
            "serial": bootstrap_serial,
            "violet_platform": violet_platform,
            "url": final_url,
            "message": (
                "Configuration envoyee au lapin. Il doit maintenant redemarrer."
                if success
                else "Configuration envoyee au lapin. Verifie son redemarrage puis reconnecte le Mac a son Wi-Fi habituel."
            ),
        }

    best_form: HtmlForm | None = None
    best_payload: dict[str, str] = {}
    best_score = -1
    for form in forms:
        payload, score = _build_payload_for_form(
            form,
            home_wifi_ssid=home_wifi_ssid,
            home_wifi_password=home_wifi_password,
            home_wifi_security=home_wifi_security,
            violet_platform=violet_platform,
        )
        if score > best_score:
            best_form = form
            best_payload = payload
            best_score = score

    if best_form is None or best_score <= 0:
        raise RuntimeError("Je n'ai pas reconnu les champs SSID / mot de passe / Violet Platform sur cette page.")

    submit_url = urllib_parse.urljoin(current_url, best_form.action or current_url)
    try:
        final_url, response_content = _fetch(
            opener,
            url=submit_url,
            method=best_form.method or "POST",
            payload=best_payload,
        )
    except Exception as exc:
        if not _looks_like_timeout(exc):
            raise
        return {
            "submitted": True,
            "success_hint": True,
            "serial": bootstrap_serial,
            "violet_platform": violet_platform,
            "url": submit_url,
            "message": (
                "Configuration envoyee au lapin. Il a probablement applique les parametres "
                "et coupe son Wi-Fi de configuration avant de repondre completement."
            ),
        }
    lower_content = response_content.lower()
    success = any(token in lower_content for token in ("update", "start", "restart", "reboot", "saved", "applied"))
    return {
        "submitted": True,
        "success_hint": success,
        "serial": bootstrap_serial,
        "violet_platform": violet_platform,
        "url": final_url,
        "message": (
            "Configuration envoyée au lapin. Il doit maintenant redémarrer."
            if success
            else "Configuration envoyée au lapin. Vérifie son redémarrage et reconnecte ensuite ton Mac à ton Wi-Fi habituel."
        ),
    }


def open_bootstrap_page(host: str = "192.168.0.1") -> bool:
    url = f"http://{host.strip().rstrip('/')}/"
    return bool(webbrowser.open(url))


def open_external_url(url: str) -> bool:
    return bool(webbrowser.open(url))


def setup_mode_image_path() -> Path:
    if getattr(sys, "frozen", False):
        resources_dir = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent.parent / "Resources"))
        return resources_dir / "assets" / "setup-mode-button-hold.png"
    return Path(__file__).resolve().parent / "assets" / "setup-mode-button-hold.png"


def app_logo_image_path() -> Path:
    if getattr(sys, "frozen", False):
        resources_dir = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent.parent / "Resources"))
        return resources_dir / "assets" / "logo-nabaztag-org.png"
    return Path(__file__).resolve().parent / "assets" / "logo-nabaztag-org.png"
