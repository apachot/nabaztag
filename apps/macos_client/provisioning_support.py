from __future__ import annotations

import html
import re
import subprocess
import sys
import webbrowser
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from http.cookiejar import CookieJar
from urllib import parse as urllib_parse
from urllib import request as urllib_request


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
    if not match:
        return interface, None
    return interface, match.group(1).strip()


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
        body = urllib_parse.urlencode(payload).encode("utf-8")
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    request_object = urllib_request.Request(url, data=body, headers=headers, method=method.upper())
    with opener.open(request_object, timeout=timeout) as response:
        final_url = response.geturl()
        content = response.read().decode("utf-8", errors="replace")
    return final_url, content


def _parse(url: str, content: str) -> tuple[list[HtmlForm], list[HtmlLink]]:
    parser = _FormParser()
    parser.feed(content)
    links = []
    for link in parser.links:
        resolved = urllib_parse.urljoin(url, link.href)
        links.append(HtmlLink(href=resolved, text=link.text))
    return parser.forms, links


def probe_bootstrap_host(host: str = "192.168.0.1") -> dict[str, str | bool]:
    opener = urllib_request.build_opener(urllib_request.HTTPCookieProcessor(CookieJar()))
    root_url = f"http://{host.strip().rstrip('/')}/"
    final_url, content = _fetch(opener, url=root_url)
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
        "has_form": bool(forms),
        "has_start_link": bool(start_url),
        "start_url": start_url,
        "advanced_url": advanced_url,
    }


def _field_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", name.strip().lower())


def _choose_option(field: HtmlField, preferences: list[str]) -> str | None:
    lowered = [(option, f"{option.value} {option.label}".strip().lower()) for option in field.options]
    for preference in preferences:
        for option, haystack in lowered:
            if preference in haystack:
                return option.value or option.label
    return field.options[0].value if field.options else None


def _build_payload_for_form(
    form: HtmlForm,
    *,
    home_wifi_ssid: str,
    home_wifi_password: str,
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
            elif any(token in key for token in ("encrypt", "crypt", "secu", "security")):
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
        if any(token in key for token in ("encrypt", "crypt", "secu", "security")):
            preferred = ["wpa2", "wpa", "aes"] if home_wifi_password else ["none", "open", "no"]
            for preference in preferred:
                for field in fields:
                    haystack = f"{field.name} {field.value}".lower()
                    if preference in haystack:
                        chosen = field.value or "on"
                        break
                if chosen:
                    break
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


def configure_bootstrap_host(
    *,
    host: str,
    home_wifi_ssid: str,
    home_wifi_password: str,
    portal_base: str,
) -> dict[str, str | bool]:
    opener = urllib_request.build_opener(urllib_request.HTTPCookieProcessor(CookieJar()))
    root_url = f"http://{host.strip().rstrip('/')}/"
    current_url, content = _fetch(opener, url=root_url)
    forms, links = _parse(current_url, content)

    start_link = next((link.href for link in links if "start" in link.text.lower()), "")
    if start_link:
        current_url, content = _fetch(opener, url=start_link)
        forms, links = _parse(current_url, content)

    advanced_link = next((link.href for link in links if "advanced" in link.text.lower()), "")
    if advanced_link:
        advanced_url, advanced_content = _fetch(opener, url=advanced_link)
        advanced_forms, _advanced_links = _parse(advanced_url, advanced_content)
        if advanced_forms:
            current_url, content, forms = advanced_url, advanced_content, advanced_forms

    if not forms:
        raise RuntimeError("Le configurateur local du lapin n'expose aucun formulaire exploitable.")

    violet_platform = build_violet_platform_value(portal_base)
    best_form: HtmlForm | None = None
    best_payload: dict[str, str] = {}
    best_score = -1
    for form in forms:
        payload, score = _build_payload_for_form(
            form,
            home_wifi_ssid=home_wifi_ssid,
            home_wifi_password=home_wifi_password,
            violet_platform=violet_platform,
        )
        if score > best_score:
            best_form = form
            best_payload = payload
            best_score = score

    if best_form is None or best_score <= 0:
        raise RuntimeError("Je n'ai pas reconnu les champs SSID / mot de passe / Violet Platform sur cette page.")

    submit_url = urllib_parse.urljoin(current_url, best_form.action or current_url)
    final_url, response_content = _fetch(
        opener,
        url=submit_url,
        method=best_form.method or "POST",
        payload=best_payload,
    )
    lower_content = response_content.lower()
    success = any(token in lower_content for token in ("update", "start", "restart", "reboot", "saved", "applied"))
    return {
        "submitted": True,
        "success_hint": success,
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
