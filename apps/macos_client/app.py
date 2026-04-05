from __future__ import annotations

import queue
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, scrolledtext, ttk


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.local_bridge import bridge_agent


RADIO_PRESETS = {
    "RFI Monde": "http://live02.rfi.fr/rfimonde-64.mp3",
    "Radio Swiss Jazz": "https://stream.srg-ssr.ch/srgssr/rsj/mp3/128",
    "SomaFM Groove Salad": "https://ice2.somafm.com/groovesalad-128-mp3",
    "SomaFM Drone Zone": "https://ice2.somafm.com/dronezone-128-mp3",
}


class NabaztagMacApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Nabaztag")
        self.root.geometry("760x620")

        self.portal_var = tk.StringVar(value="https://nabaztag.org")
        self.account_email_var = tk.StringVar()
        self.account_password_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Connecte-toi pour accéder à tes lapins.")
        self.selected_rabbit_id: int | None = None
        self.rabbits_by_name: dict[str, dict] = {}

        self.rabbit_app_pairing_code_var = tk.StringVar()
        self.rabbit_app_pairing_status_var = tk.StringVar(value="Aucun code d'appairage lapin chargé.")
        self.rabbit_pairing_device_var = tk.StringVar()
        self.rabbit_pairing_devices_by_label: dict[str, dict] = {}

        self.ear_left_var = tk.IntVar(value=4)
        self.ear_right_var = tk.IntVar(value=12)
        self.led_target_var = tk.StringVar(value="nose")
        self.led_color_var = tk.StringVar(value="blue")
        self.radio_url_var = tk.StringVar(value=RADIO_PRESETS["RFI Monde"])
        self.radio_preset_var = tk.StringVar(value="RFI Monde")

        self.log_queue: queue.Queue[str] = queue.Queue()

        self.auth_container: ttk.Frame | None = None
        self.app_container: ttk.Frame | None = None
        self.rabbit_combo: ttk.Combobox | None = None
        self.rabbit_pairing_combo: ttk.Combobox | None = None
        self.message_text: scrolledtext.ScrolledText | None = None
        self.log_widget: scrolledtext.ScrolledText | None = None

        self._build_ui()
        self._load_existing_config()
        self._schedule_log_poll()

    def _build_ui(self) -> None:
        self.auth_container = ttk.Frame(self.root, padding=24)
        self.auth_container.pack(fill=tk.BOTH, expand=True)

        hero = ttk.Frame(self.auth_container)
        hero.pack(fill=tk.X, pady=(0, 18))
        ttk.Label(hero, text="Nabaztag", font=("Helvetica", 24, "bold")).pack(anchor=tk.W)
        ttk.Label(
            hero,
            text="Connecte-toi avec ton compte nabaztag.org pour retrouver immédiatement tes lapins.",
            wraplength=680,
        ).pack(anchor=tk.W, pady=(6, 0))

        form = ttk.Frame(self.auth_container)
        form.pack(fill=tk.X)
        form.columnconfigure(1, weight=1)
        self._labeled_entry(form, 0, "Portail", self.portal_var)
        self._labeled_entry(form, 1, "Email", self.account_email_var)
        password_entry = self._labeled_entry(form, 2, "Mot de passe", self.account_password_var, field_type="password")
        password_entry.bind("<Return>", lambda _event: self.login())

        actions = ttk.Frame(self.auth_container)
        actions.pack(fill=tk.X, pady=(18, 14))
        ttk.Button(actions, text="Se connecter", command=self.login).pack(side=tk.LEFT)

        status_frame = ttk.LabelFrame(self.auth_container, text="État")
        status_frame.pack(fill=tk.X)
        ttk.Label(status_frame, textvariable=self.status_var, wraplength=680).pack(anchor=tk.W, padx=12, pady=12)

        self.app_container = ttk.Frame(self.root, padding=16)

        topbar = ttk.Frame(self.app_container)
        topbar.pack(fill=tk.X, pady=(0, 12))
        ttk.Label(topbar, text="Mes lapins", font=("Helvetica", 20, "bold")).pack(side=tk.LEFT)
        ttk.Button(topbar, text="Rafraîchir", command=self.refresh_rabbits).pack(side=tk.RIGHT)
        ttk.Button(topbar, text="Se déconnecter", command=self.logout).pack(side=tk.RIGHT, padx=(0, 8))

        account_status = ttk.LabelFrame(self.app_container, text="Compte")
        account_status.pack(fill=tk.X, pady=(0, 12))
        ttk.Label(account_status, textvariable=self.status_var, wraplength=680).pack(anchor=tk.W, padx=12, pady=12)

        rabbit_selection = ttk.Frame(self.app_container)
        rabbit_selection.pack(fill=tk.X, pady=(0, 12))
        ttk.Label(rabbit_selection, text="Lapin").pack(anchor=tk.W)
        self.rabbit_combo = ttk.Combobox(rabbit_selection, state="readonly")
        self.rabbit_combo.pack(fill=tk.X, pady=(6, 0))
        self.rabbit_combo.bind("<<ComboboxSelected>>", self.on_rabbit_selected)

        talk_frame = ttk.LabelFrame(self.app_container, text="Lui parler")
        talk_frame.pack(fill=tk.BOTH, expand=True)
        self.message_text = scrolledtext.ScrolledText(talk_frame, wrap=tk.WORD, height=7)
        self.message_text.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        ttk.Button(talk_frame, text="Envoyer au lapin", command=self.send_message_to_rabbit).pack(anchor=tk.E, padx=8, pady=(0, 8))

        pairing_frame = ttk.LabelFrame(self.app_container, text="Rattacher un Nabaztag à un lapin")
        pairing_frame.pack(fill=tk.X, pady=(12, 0))
        pairing_form = ttk.Frame(pairing_frame)
        pairing_form.pack(fill=tk.X, padx=8, pady=(8, 6))
        pairing_form.columnconfigure(1, weight=1)
        ttk.Label(pairing_form, text="Code temporaire").grid(row=0, column=0, sticky="w", padx=(0, 12))
        ttk.Entry(pairing_form, textvariable=self.rabbit_app_pairing_code_var).grid(row=0, column=1, sticky="ew")
        ttk.Button(pairing_form, text="Charger le code", command=self.load_rabbit_pairing_code).grid(row=0, column=2, padx=(8, 0))
        ttk.Label(pairing_frame, textvariable=self.rabbit_app_pairing_status_var, wraplength=680).pack(anchor=tk.W, padx=8, pady=(0, 8))
        pairing_actions = ttk.Frame(pairing_frame)
        pairing_actions.pack(fill=tk.X, padx=8, pady=(0, 8))
        self.rabbit_pairing_combo = ttk.Combobox(pairing_actions, state="readonly", textvariable=self.rabbit_pairing_device_var)
        self.rabbit_pairing_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(pairing_actions, text="Rattacher ce Nabaztag", command=self.attach_rabbit_from_code).pack(side=tk.LEFT, padx=(8, 0))

        control_frame = ttk.LabelFrame(self.app_container, text="Pilotage direct")
        control_frame.pack(fill=tk.X, pady=(12, 0))

        ears_frame = ttk.Frame(control_frame)
        ears_frame.pack(fill=tk.X, padx=8, pady=(8, 6))
        ttk.Label(ears_frame, text="Oreille gauche").grid(row=0, column=0, sticky="w")
        ttk.Spinbox(ears_frame, from_=0, to=16, textvariable=self.ear_left_var, width=6).grid(row=0, column=1, padx=(8, 16))
        ttk.Label(ears_frame, text="Oreille droite").grid(row=0, column=2, sticky="w")
        ttk.Spinbox(ears_frame, from_=0, to=16, textvariable=self.ear_right_var, width=6).grid(row=0, column=3, padx=(8, 16))
        ttk.Button(ears_frame, text="Bouger les oreilles", command=self.move_rabbit_ears).grid(row=0, column=4, sticky="e")

        led_frame = ttk.Frame(control_frame)
        led_frame.pack(fill=tk.X, padx=8, pady=6)
        ttk.Label(led_frame, text="LED").grid(row=0, column=0, sticky="w")
        ttk.Combobox(
            led_frame,
            state="readonly",
            textvariable=self.led_target_var,
            values=("nose", "left", "center", "right", "bottom"),
            width=10,
        ).grid(row=0, column=1, padx=(8, 16))
        ttk.Label(led_frame, text="Couleur").grid(row=0, column=2, sticky="w")
        ttk.Combobox(
            led_frame,
            state="readonly",
            textvariable=self.led_color_var,
            values=("red", "green", "blue", "cyan", "violet", "yellow", "white"),
            width=10,
        ).grid(row=0, column=3, padx=(8, 16))
        ttk.Button(led_frame, text="Allumer la LED", command=self.set_rabbit_led).grid(row=0, column=4, sticky="e")

        radio_frame = ttk.Frame(control_frame)
        radio_frame.pack(fill=tk.X, padx=8, pady=6)
        ttk.Label(radio_frame, text="Radio").grid(row=0, column=0, sticky="w")
        preset_combo = ttk.Combobox(
            radio_frame,
            state="readonly",
            textvariable=self.radio_preset_var,
            values=tuple(RADIO_PRESETS.keys()),
            width=22,
        )
        preset_combo.grid(row=0, column=1, padx=(8, 12))
        preset_combo.bind(
            "<<ComboboxSelected>>",
            lambda _event=None: self.radio_url_var.set(RADIO_PRESETS.get(self.radio_preset_var.get(), "")),
        )
        ttk.Entry(radio_frame, textvariable=self.radio_url_var).grid(row=0, column=2, sticky="ew")
        ttk.Button(radio_frame, text="Lancer", command=self.start_rabbit_radio).grid(row=0, column=3, padx=(12, 0))
        ttk.Button(radio_frame, text="Stop", command=self.stop_rabbit_radio).grid(row=0, column=4, padx=(8, 0))
        radio_frame.columnconfigure(2, weight=1)

        power_frame = ttk.Frame(control_frame)
        power_frame.pack(fill=tk.X, padx=8, pady=(6, 8))
        ttk.Button(power_frame, text="Dormir", command=self.put_rabbit_to_sleep).pack(side=tk.LEFT)
        ttk.Button(power_frame, text="Réveiller", command=self.wake_rabbit).pack(side=tk.LEFT, padx=(8, 0))

        log_frame = ttk.LabelFrame(self.app_container, text="Journal")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(12, 0))
        self.log_widget = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, height=12, state=tk.DISABLED)
        self.log_widget.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

    def _labeled_entry(self, parent: ttk.Frame, row: int, label: str, variable: tk.StringVar, *, field_type: str = "text") -> ttk.Entry:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=6)
        entry = ttk.Entry(parent, textvariable=variable, show="*" if field_type == "password" else "")
        entry.grid(row=row, column=1, sticky="ew", pady=6)
        return entry

    def _append_log(self, message: str) -> None:
        if self.log_widget is None:
            return
        self.log_widget.configure(state=tk.NORMAL)
        self.log_widget.insert(tk.END, f"{message}\n")
        self.log_widget.see(tk.END)
        self.log_widget.configure(state=tk.DISABLED)

    def _schedule_log_poll(self) -> None:
        while True:
            try:
                message = self.log_queue.get_nowait()
            except queue.Empty:
                break
            self._append_log(message)
        self.root.after(200, self._schedule_log_poll)

    def _show_auth_view(self) -> None:
        if self.app_container is not None:
            self.app_container.pack_forget()
        if self.auth_container is not None:
            self.auth_container.pack(fill=tk.BOTH, expand=True)

    def _show_app_view(self) -> None:
        if self.auth_container is not None:
            self.auth_container.pack_forget()
        if self.app_container is not None:
            self.app_container.pack(fill=tk.BOTH, expand=True)

    def _load_existing_config(self) -> None:
        config = bridge_agent.load_config()
        if not config:
            self._show_auth_view()
            return
        portal = str(config.get("portal") or "").strip()
        if portal:
            self.portal_var.set(portal)
        companion = config.get("companion") if isinstance(config.get("companion"), dict) else {}
        email = str(companion.get("email") or "").strip()
        token = str(companion.get("api_token") or "").strip()
        if email:
            self.account_email_var.set(email)
        if token:
            self.status_var.set("Connexion restaurée, récupération des lapins…")
            self._show_app_view()
            self.refresh_rabbits()
        else:
            self._show_auth_view()

    def _run_in_thread(self, fn, *, on_error: str) -> None:
        def target() -> None:
            try:
                fn()
            except Exception as exc:
                self.log_queue.put(f"Erreur: {exc}")
                self.root.after(0, lambda: messagebox.showerror("Nabaztag", f"{on_error}\n\n{exc}"))

        threading.Thread(target=target, daemon=True).start()

    def _companion_token(self) -> tuple[str, str]:
        config = bridge_agent.load_config()
        portal = bridge_agent.normalize_portal_base(str(config.get("portal") or self.portal_var.get() or ""))
        companion = config.get("companion") if isinstance(config.get("companion"), dict) else {}
        token = str(companion.get("api_token") or "").strip()
        return portal, token

    def login(self) -> None:
        portal = self.portal_var.get().strip()
        email = " ".join(self.account_email_var.get().split()).strip().lower()
        password = self.account_password_var.get()
        if not portal or not email or not password:
            messagebox.showerror("Nabaztag", "Saisis le portail, l'email et le mot de passe.")
            return

        self.status_var.set("Connexion en cours…")

        def do_login() -> None:
            response = bridge_agent.http_json(
                url=f"{bridge_agent.normalize_portal_base(portal)}/mobile-api/v1/session/login",
                method="POST",
                payload={"email": email, "password": password, "device_name": "Nabaztag macOS"},
            )
            if not response.get("ok"):
                raise RuntimeError(response.get("message") or "Connexion impossible.")
            config = bridge_agent.load_config()
            config["portal"] = bridge_agent.normalize_portal_base(portal)
            config["companion"] = {"api_token": response["api_token"], "email": email}
            bridge_agent.save_config(config)
            rabbit_count = len(response.get("rabbits") or []) if isinstance(response.get("rabbits"), list) else 0
            self.log_queue.put("Application macOS connectée au compte.")
            self.root.after(0, lambda: self.account_password_var.set(""))
            self.root.after(0, self._show_app_view)
            self.root.after(0, lambda: self.status_var.set(f"Connecté au compte. {rabbit_count} lapin(s) disponible(s)."))
            self.root.after(0, self.refresh_rabbits)

        self._run_in_thread(do_login, on_error="Impossible de connecter l'application macOS.")

    def logout(self) -> None:
        config = bridge_agent.load_config()
        companion = config.get("companion") if isinstance(config.get("companion"), dict) else {}
        config["companion"] = {"email": str(companion.get("email") or self.account_email_var.get() or "").strip().lower()}
        bridge_agent.save_config(config)
        self.rabbits_by_name = {}
        self.selected_rabbit_id = None
        if self.rabbit_combo is not None:
            self.rabbit_combo["values"] = ()
            self.rabbit_combo.set("")
        self.status_var.set("Déconnecté. Connecte-toi pour accéder à tes lapins.")
        self._show_auth_view()
        self.log_queue.put("Application macOS déconnectée du compte.")

    def refresh_rabbits(self) -> None:
        portal, token = self._companion_token()
        if not portal or not token:
            self.status_var.set("Application non connectée au compte.")
            self._show_auth_view()
            return

        def do_refresh() -> None:
            response = bridge_agent.http_json(
                url=f"{portal}/mobile-api/v1/rabbits",
                method="GET",
                token=token,
            )
            rabbits = response.get("rabbits") if isinstance(response.get("rabbits"), list) else []
            rabbit_map: dict[str, dict] = {}
            labels: list[str] = []
            for rabbit in rabbits:
                if not isinstance(rabbit, dict):
                    continue
                name = str(rabbit.get("name") or "").strip()
                if not name:
                    continue
                label = f"{name} ({rabbit.get('status', 'n/a')})"
                rabbit_map[label] = rabbit
                labels.append(label)

            def update_ui() -> None:
                self.rabbits_by_name = rabbit_map
                if self.rabbit_combo is not None:
                    self.rabbit_combo["values"] = labels
                    if labels:
                        current = self.rabbit_combo.get().strip()
                        if current in labels:
                            self.rabbit_combo.set(current)
                        else:
                            self.rabbit_combo.current(0)
                        self.on_rabbit_selected()
                        self.status_var.set(f"Connecté au compte. {len(labels)} lapin(s) disponible(s).")
                    else:
                        self.rabbit_combo.set("")
                        self.selected_rabbit_id = None
                        self.status_var.set("Connecté au compte, mais aucun lapin n'est disponible.")
                self._show_app_view()

            self.root.after(0, update_ui)
            self.log_queue.put("Liste des lapins rafraîchie.")

        self._run_in_thread(do_refresh, on_error="Impossible de récupérer les lapins.")

    def on_rabbit_selected(self, _event=None) -> None:
        if self.rabbit_combo is None:
            return
        label = self.rabbit_combo.get().strip()
        rabbit = self.rabbits_by_name.get(label) or {}
        rabbit_id = rabbit.get("id")
        self.selected_rabbit_id = int(rabbit_id) if isinstance(rabbit_id, int) else None

    def _select_rabbit_by_id(self, rabbit_id: int) -> None:
        if self.rabbit_combo is None:
            return
        for label, rabbit in self.rabbits_by_name.items():
            if rabbit.get("id") == rabbit_id:
                self.rabbit_combo.set(label)
                self.on_rabbit_selected()
                return

    def load_rabbit_pairing_code(self) -> None:
        portal = bridge_agent.normalize_portal_base(self.portal_var.get().strip())
        pairing_token = "".join(self.rabbit_app_pairing_code_var.get().upper().split())
        if not portal or not pairing_token:
            messagebox.showerror("Nabaztag", "Saisis le portail et le code temporaire.")
            return

        def do_load() -> None:
            response = bridge_agent.http_json(
                url=f"{portal}/mobile-api/v1/rabbit-pairing/claim",
                method="POST",
                payload={"pairing_token": pairing_token},
            )
            if not response.get("ok"):
                raise RuntimeError(response.get("message") or "Chargement du code impossible.")
            pairing = response.get("pairing") if isinstance(response.get("pairing"), dict) else {}
            rabbit = pairing.get("rabbit") if isinstance(pairing.get("rabbit"), dict) else {}
            linked_device = pairing.get("linked_device") if isinstance(pairing.get("linked_device"), dict) else None
            button_candidate = pairing.get("button_candidate") if isinstance(pairing.get("button_candidate"), dict) else None
            recent_devices = pairing.get("recent_unclaimed_devices") if isinstance(pairing.get("recent_unclaimed_devices"), list) else []

            ordered_devices: list[dict] = []
            if button_candidate:
                ordered_devices.append(button_candidate)
            for device in recent_devices:
                if not isinstance(device, dict):
                    continue
                if button_candidate and device.get("id") == button_candidate.get("id"):
                    continue
                ordered_devices.append(device)

            labels: list[str] = []
            device_map: dict[str, dict] = {}
            for device in ordered_devices:
                label = f"{device.get('serial', 'n/a')} · {device.get('last_path') or 'n/a'}"
                labels.append(label)
                device_map[label] = device

            rabbit_id = rabbit.get("id")
            rabbit_name = " ".join(str(rabbit.get("name") or "").split()).strip() or "Lapin"

            def update_ui() -> None:
                self.rabbit_pairing_devices_by_label = device_map
                if self.rabbit_pairing_combo is not None:
                    self.rabbit_pairing_combo["values"] = labels
                    self.rabbit_pairing_combo.set(labels[0] if labels else "")
                if isinstance(rabbit_id, int):
                    self.refresh_rabbits()
                    self.root.after(500, lambda: self._select_rabbit_by_id(rabbit_id))
                if linked_device:
                    self.rabbit_app_pairing_status_var.set(
                        f"{rabbit_name} est déjà rattaché au Nabaztag {linked_device.get('serial', 'n/a')}."
                    )
                elif labels:
                    self.rabbit_app_pairing_status_var.set(
                        f"{rabbit_name} prêt à être rattaché. Choisis le Nabaztag détecté puis valide."
                    )
                else:
                    self.rabbit_app_pairing_status_var.set(
                        f"{rabbit_name} chargé, mais aucun Nabaztag non rattaché n'a encore été détecté."
                    )

            self.root.after(0, update_ui)
            self.log_queue.put(f"Code d'appairage chargé pour {rabbit_name}.")

        self._run_in_thread(do_load, on_error="Impossible de charger le code d'appairage lapin.")

    def attach_rabbit_from_code(self) -> None:
        portal = bridge_agent.normalize_portal_base(self.portal_var.get().strip())
        pairing_token = "".join(self.rabbit_app_pairing_code_var.get().upper().split())
        label = self.rabbit_pairing_combo.get().strip() if self.rabbit_pairing_combo is not None else ""
        device = self.rabbit_pairing_devices_by_label.get(label) or {}
        observation_id = device.get("id")
        if not portal or not pairing_token:
            messagebox.showerror("Nabaztag", "Charge d'abord un code d'appairage.")
            return
        if not isinstance(observation_id, int):
            messagebox.showerror("Nabaztag", "Choisis un Nabaztag à rattacher.")
            return

        def do_attach() -> None:
            response = bridge_agent.http_json(
                url=f"{portal}/mobile-api/v1/rabbit-pairing/attach",
                method="POST",
                payload={"pairing_token": pairing_token, "observation_id": observation_id},
            )
            if not response.get("ok"):
                raise RuntimeError(response.get("message") or "Appairage du lapin impossible.")
            pairing = response.get("pairing") if isinstance(response.get("pairing"), dict) else {}
            rabbit = pairing.get("rabbit") if isinstance(pairing.get("rabbit"), dict) else {}
            rabbit_id = rabbit.get("id")
            rabbit_name = " ".join(str(rabbit.get("name") or "").split()).strip() or "Lapin"
            message = " ".join(str(response.get("message") or "").split()).strip()

            def update_ui() -> None:
                if self.rabbit_pairing_combo is not None:
                    self.rabbit_pairing_combo["values"] = ()
                    self.rabbit_pairing_combo.set("")
                self.rabbit_pairing_devices_by_label = {}
                self.rabbit_app_pairing_status_var.set(message or f"{rabbit_name} rattaché.")
                self.rabbit_app_pairing_code_var.set("")
                self.refresh_rabbits()
                if isinstance(rabbit_id, int):
                    self.root.after(500, lambda: self._select_rabbit_by_id(rabbit_id))

            self.root.after(0, update_ui)
            self.log_queue.put(message or f"{rabbit_name} rattaché.")

        self._run_in_thread(do_attach, on_error="Impossible de rattacher le Nabaztag.")

    def _require_session(self) -> tuple[str, str]:
        portal, token = self._companion_token()
        if not portal or not token:
            messagebox.showerror("Nabaztag", "Connecte d'abord l'application au compte.")
            return "", ""
        if self.selected_rabbit_id is None:
            messagebox.showerror("Nabaztag", "Choisis un lapin.")
            return "", ""
        return portal, token

    def send_message_to_rabbit(self) -> None:
        portal, token = self._require_session()
        if not portal or not token or self.message_text is None:
            return
        message = " ".join(self.message_text.get("1.0", tk.END).split()).strip()
        if not message:
            messagebox.showerror("Nabaztag", "Saisis un message.")
            return

        def do_send() -> None:
            response = bridge_agent.http_json(
                url=f"{portal}/mobile-api/v1/rabbits/{self.selected_rabbit_id}/conversation",
                method="POST",
                token=token,
                payload={"text": message},
            )
            if not response.get("ok"):
                raise RuntimeError(response.get("message") or "Envoi impossible.")
            reply = " ".join(str(response.get("reply") or "").split()).strip()
            self.log_queue.put(f"Message envoyé au lapin {self.selected_rabbit_id}.")
            if reply:
                self.log_queue.put(f"Réponse du lapin : {reply}")
            self.root.after(0, lambda: self.message_text.delete("1.0", tk.END))

        self._run_in_thread(do_send, on_error="Impossible d'envoyer le message au lapin.")

    def _invoke_rabbit_api(self, path: str, payload: dict, *, success_message: str, error_message: str) -> None:
        portal, token = self._require_session()
        if not portal or not token:
            return

        def do_invoke() -> None:
            response = bridge_agent.http_json(
                url=f"{portal}{path}",
                method="POST",
                token=token,
                payload=payload,
            )
            if not response.get("ok"):
                raise RuntimeError(response.get("message") or error_message)
            detail = " ".join(str(response.get("message") or "").split()).strip()
            self.log_queue.put(success_message)
            if detail:
                self.log_queue.put(detail)

        self._run_in_thread(do_invoke, on_error=error_message)

    def move_rabbit_ears(self) -> None:
        self._invoke_rabbit_api(
            f"/mobile-api/v1/rabbits/{self.selected_rabbit_id}/ears",
            {"left": int(self.ear_left_var.get()), "right": int(self.ear_right_var.get())},
            success_message="Commande oreilles envoyée.",
            error_message="Impossible de bouger les oreilles.",
        )

    def set_rabbit_led(self) -> None:
        self._invoke_rabbit_api(
            f"/mobile-api/v1/rabbits/{self.selected_rabbit_id}/led",
            {"target": self.led_target_var.get().strip(), "color_preset": self.led_color_var.get().strip()},
            success_message="Commande LED envoyée.",
            error_message="Impossible d'allumer la LED.",
        )

    def start_rabbit_radio(self) -> None:
        stream_url = " ".join(self.radio_url_var.get().split()).strip()
        if not stream_url:
            messagebox.showerror("Nabaztag", "Saisis une URL de radio.")
            return
        self._invoke_rabbit_api(
            f"/mobile-api/v1/rabbits/{self.selected_rabbit_id}/radio",
            {"stream_url": stream_url},
            success_message="Stream radio envoyé.",
            error_message="Impossible de lancer la radio.",
        )

    def stop_rabbit_radio(self) -> None:
        self._invoke_rabbit_api(
            f"/mobile-api/v1/rabbits/{self.selected_rabbit_id}/radio/stop",
            {},
            success_message="Interruption radio envoyée.",
            error_message="Impossible d'interrompre le stream.",
        )

    def put_rabbit_to_sleep(self) -> None:
        self._invoke_rabbit_api(
            f"/mobile-api/v1/rabbits/{self.selected_rabbit_id}/sleep",
            {},
            success_message="Mise en sommeil envoyée.",
            error_message="Impossible d'endormir le lapin.",
        )

    def wake_rabbit(self) -> None:
        self._invoke_rabbit_api(
            f"/mobile-api/v1/rabbits/{self.selected_rabbit_id}/wakeup",
            {},
            success_message="Réveil envoyé.",
            error_message="Impossible de réveiller le lapin.",
        )


def main() -> int:
    root = tk.Tk()
    style = ttk.Style(root)
    if "aqua" in style.theme_names():
        style.theme_use("aqua")
    NabaztagMacApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
