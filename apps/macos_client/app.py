from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

import client_support
import provisioning_support


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
        self.root.geometry("860x760")
        self.root.configure(bg="#f4f1eb")

        self.portal_var = tk.StringVar(value="https://nabaztag.org")
        self.account_email_var = tk.StringVar()
        self.account_password_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Connecte-toi pour accéder à tes lapins.")
        self.selected_rabbit_status_var = tk.StringVar(value="Aucun lapin sélectionné.")
        self.selected_rabbit_id: int | None = None
        self.rabbits_by_label: dict[str, dict] = {}
        self.bootstrap_host_var = tk.StringVar(value="192.168.0.1")
        self.bootstrap_setup_ssid_var = tk.StringVar(value="NabaztagXX")
        self.bootstrap_home_ssid_var = tk.StringVar()
        self.bootstrap_home_password_var = tk.StringVar()
        self.bootstrap_wifi_status_var = tk.StringVar(value="Wi-Fi du Mac non détecté.")
        self.bootstrap_status_var = tk.StringVar(value="Prêt pour la mise en service locale du lapin.")
        self.bootstrap_violet_platform_var = tk.StringVar(
            value=provisioning_support.build_violet_platform_value(self.portal_var.get())
        )
        self.portal_var.trace_add("write", lambda *_args: self._update_violet_platform())

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
        self.app_shell: ttk.Frame | None = None
        self.app_canvas: tk.Canvas | None = None
        self.app_scrollbar: ttk.Scrollbar | None = None
        self.app_container: ttk.Frame | None = None
        self.portal_entry: ttk.Entry | None = None
        self.email_entry: ttk.Entry | None = None
        self.password_entry: ttk.Entry | None = None
        self.rabbit_listbox: tk.Listbox | None = None
        self.rabbit_pairing_combo: ttk.Combobox | None = None
        self.message_text: scrolledtext.ScrolledText | None = None
        self.log_widget: scrolledtext.ScrolledText | None = None
        self.setup_mode_photo: tk.PhotoImage | None = None
        self.auth_logo_photo: tk.PhotoImage | None = None
        self.provisioning_frame: ttk.LabelFrame | None = None
        self.rabbit_selection_frame: ttk.Frame | None = None
        self.talk_frame: ttk.LabelFrame | None = None
        self.control_frame: ttk.LabelFrame | None = None
        self.log_frame: ttk.LabelFrame | None = None

        self._build_ui()
        self._load_existing_config()
        self._schedule_log_poll()

    def _build_ui(self) -> None:
        self.auth_container = tk.Frame(self.root, bg="#f4f1eb", padx=24, pady=24)
        self.auth_container.pack(fill=tk.BOTH, expand=True)

        auth_card = tk.Frame(
            self.auth_container,
            bg="#fffdfa",
            highlightbackground="#d8d1c4",
            highlightthickness=1,
            padx=28,
            pady=26,
        )
        auth_card.pack(expand=True)

        hero = tk.Frame(auth_card, bg="#fffdfa")
        hero.pack(fill=tk.X, pady=(0, 18))
        logo_path = provisioning_support.app_logo_image_path()
        if logo_path.exists():
            try:
                self.auth_logo_photo = tk.PhotoImage(file=str(logo_path)).subsample(2, 2)
                tk.Label(hero, image=self.auth_logo_photo, bg="#fffdfa").pack(anchor=tk.CENTER, pady=(0, 10))
            except tk.TclError:
                self.auth_logo_photo = None
        tk.Label(
            hero,
            text="Nabaztag",
            font=("Helvetica", 24, "bold"),
            fg="#243b37",
            bg="#fffdfa",
        ).pack(anchor=tk.CENTER)
        tk.Label(
            hero,
            text="Identifie-toi pour retrouver immédiatement tes lapins.",
            wraplength=420,
            justify=tk.CENTER,
            fg="#7d776d",
            bg="#fffdfa",
            font=("Helvetica", 12),
        ).pack(anchor=tk.CENTER, pady=(8, 0))

        form = ttk.Frame(auth_card)
        form.pack(fill=tk.X)
        form.columnconfigure(1, weight=1)
        self.portal_entry = self._labeled_entry(form, 0, "Portail", self.portal_var)
        self.email_entry = self._labeled_entry(form, 1, "Identifiant", self.account_email_var)
        self.password_entry = self._labeled_entry(form, 2, "Mot de passe", self.account_password_var, field_type="password")
        self.password_entry.bind("<Return>", lambda _event: self.login())

        actions = tk.Frame(auth_card, bg="#fffdfa")
        actions.pack(fill=tk.X, pady=(18, 10))
        tk.Button(
            actions,
            text="Connexion",
            command=self.login,
            bg="#243b37",
            fg="white",
            activebackground="#1d312d",
            activeforeground="white",
            relief=tk.FLAT,
            padx=18,
            pady=10,
            cursor="hand2",
        ).pack(anchor=tk.CENTER)
        tk.Button(
            actions,
            text="Créer un compte",
            command=self.open_account_registration,
            bg="#fffdfa",
            fg="#b8633e",
            activebackground="#f7eee8",
            activeforeground="#b8633e",
            relief=tk.FLAT,
            padx=12,
            pady=8,
            cursor="hand2",
        ).pack(anchor=tk.CENTER, pady=(8, 0))

        tk.Label(
            auth_card,
            textvariable=self.status_var,
            wraplength=420,
            justify=tk.CENTER,
            fg="#7d776d",
            bg="#fffdfa",
            font=("Helvetica", 11),
        ).pack(anchor=tk.CENTER, pady=(6, 0))

        self.app_shell = ttk.Frame(self.root)
        self.app_canvas = tk.Canvas(self.app_shell, highlightthickness=0)
        self.app_scrollbar = ttk.Scrollbar(self.app_shell, orient=tk.VERTICAL, command=self.app_canvas.yview)
        self.app_canvas.configure(yscrollcommand=self.app_scrollbar.set)
        self.app_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.app_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.app_container = ttk.Frame(self.app_canvas, padding=16)
        self.app_canvas_window = self.app_canvas.create_window((0, 0), window=self.app_container, anchor="nw")
        self.app_container.bind("<Configure>", self._on_app_container_configure)
        self.app_canvas.bind("<Configure>", self._on_app_canvas_configure)
        self.app_canvas.bind("<Enter>", self._bind_app_mousewheel)
        self.app_canvas.bind("<Leave>", self._unbind_app_mousewheel)

        topbar = ttk.Frame(self.app_container)
        topbar.pack(fill=tk.X, pady=(0, 12))
        ttk.Label(topbar, text="Mes lapins", font=("Helvetica", 20, "bold")).pack(side=tk.LEFT)
        ttk.Button(topbar, text="Rafraîchir", command=self.refresh_rabbits).pack(side=tk.RIGHT)
        ttk.Button(topbar, text="Ajouter un lapin", command=self.show_add_rabbit_flow).pack(side=tk.RIGHT, padx=(0, 8))
        ttk.Button(topbar, text="Se déconnecter", command=self.logout).pack(side=tk.RIGHT, padx=(0, 8))

        account_status = ttk.LabelFrame(self.app_container, text="Compte")
        account_status.pack(fill=tk.X, pady=(0, 12))
        ttk.Label(account_status, textvariable=self.status_var, wraplength=680).pack(anchor=tk.W, padx=12, pady=12)

        self.provisioning_frame = ttk.LabelFrame(self.app_container, text="Connectez votre lapin")
        self.provisioning_frame.pack(fill=tk.X, pady=(0, 12))

        ttk.Label(
            self.provisioning_frame,
            text=(
                "Détecte le Wi-Fi du Mac, vérifie le configurateur local sur 192.168.0.1 "
                "et prépare la configuration du lapin avec nabaztag.org/vl."
            ),
            wraplength=700,
        ).pack(anchor=tk.W, padx=12, pady=(12, 8))

        illustration_path = provisioning_support.setup_mode_image_path()
        if illustration_path.exists():
            try:
                self.setup_mode_photo = tk.PhotoImage(file=str(illustration_path)).subsample(4, 4)
                ttk.Label(
                    self.provisioning_frame,
                    image=self.setup_mode_photo,
                    text="Maintenir le bouton pendant le branchement",
                    compound="top",
                ).pack(anchor=tk.CENTER, padx=12, pady=(0, 10))
            except tk.TclError:
                ttk.Label(
                    self.provisioning_frame,
                    text="Maintenir le bouton du Nabaztag appuyé pendant que tu le branches.",
                    wraplength=700,
                ).pack(anchor=tk.W, padx=12, pady=(0, 10))

        provisioning_form = ttk.Frame(self.provisioning_frame)
        provisioning_form.pack(fill=tk.X, padx=12, pady=(0, 8))
        provisioning_form.columnconfigure(1, weight=1)

        ttk.Label(provisioning_form, text="Hôte du lapin").grid(row=0, column=0, sticky="w", padx=(0, 10), pady=4)
        ttk.Entry(provisioning_form, textvariable=self.bootstrap_host_var).grid(row=0, column=1, sticky="ew", pady=4)
        ttk.Label(provisioning_form, text="SSID setup").grid(row=1, column=0, sticky="w", padx=(0, 10), pady=4)
        ttk.Entry(provisioning_form, textvariable=self.bootstrap_setup_ssid_var).grid(row=1, column=1, sticky="ew", pady=4)
        ttk.Label(provisioning_form, text="Wi-Fi maison").grid(row=2, column=0, sticky="w", padx=(0, 10), pady=4)
        ttk.Entry(provisioning_form, textvariable=self.bootstrap_home_ssid_var).grid(row=2, column=1, sticky="ew", pady=4)
        ttk.Label(provisioning_form, text="Mot de passe Wi-Fi").grid(row=3, column=0, sticky="w", padx=(0, 10), pady=4)
        ttk.Entry(provisioning_form, textvariable=self.bootstrap_home_password_var, show="*").grid(row=3, column=1, sticky="ew", pady=4)
        ttk.Label(provisioning_form, text="Violet Platform").grid(row=4, column=0, sticky="w", padx=(0, 10), pady=4)
        ttk.Entry(provisioning_form, textvariable=self.bootstrap_violet_platform_var, state="readonly").grid(row=4, column=1, sticky="ew", pady=4)

        provisioning_actions = ttk.Frame(self.provisioning_frame)
        provisioning_actions.pack(fill=tk.X, padx=12, pady=(0, 8))
        ttk.Button(provisioning_actions, text="Détecter le Wi-Fi du Mac", command=self.detect_mac_wifi).pack(side=tk.LEFT)
        ttk.Button(provisioning_actions, text="Tester 192.168.0.1", command=self.probe_local_bootstrap).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(provisioning_actions, text="Ouvrir le configurateur", command=self.open_local_bootstrap).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(provisioning_actions, text="Configurer le lapin", command=self.configure_local_bootstrap).pack(side=tk.RIGHT)

        ttk.Label(self.provisioning_frame, textvariable=self.bootstrap_wifi_status_var, wraplength=700).pack(anchor=tk.W, padx=12)
        ttk.Label(self.provisioning_frame, textvariable=self.bootstrap_status_var, wraplength=700).pack(anchor=tk.W, padx=12, pady=(4, 12))

        self.rabbit_selection_frame = ttk.Frame(self.app_container)
        self.rabbit_selection_frame.pack(fill=tk.X, pady=(0, 12))
        ttk.Label(self.rabbit_selection_frame, text="Lapin").pack(anchor=tk.W)
        rabbit_list_frame = ttk.Frame(self.rabbit_selection_frame)
        rabbit_list_frame.pack(fill=tk.X, pady=(6, 0))
        self.rabbit_listbox = tk.Listbox(rabbit_list_frame, height=4, exportselection=False)
        self.rabbit_listbox.pack(side=tk.LEFT, fill=tk.X, expand=True)
        rabbit_scrollbar = ttk.Scrollbar(rabbit_list_frame, orient=tk.VERTICAL, command=self.rabbit_listbox.yview)
        rabbit_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.rabbit_listbox.configure(yscrollcommand=rabbit_scrollbar.set)
        self.rabbit_listbox.bind("<<ListboxSelect>>", self.on_rabbit_selected)
        ttk.Label(self.rabbit_selection_frame, textvariable=self.selected_rabbit_status_var).pack(anchor=tk.W, pady=(6, 0))

        self.talk_frame = ttk.LabelFrame(self.app_container, text="Lui parler")
        self.talk_frame.pack(fill=tk.BOTH, expand=True)
        self.message_text = scrolledtext.ScrolledText(self.talk_frame, wrap=tk.WORD, height=7)
        self.message_text.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        ttk.Button(self.talk_frame, text="Envoyer au lapin", command=self.send_message_to_rabbit).pack(anchor=tk.E, padx=8, pady=(0, 8))

        self.control_frame = ttk.LabelFrame(self.app_container, text="Pilotage direct")
        self.control_frame.pack(fill=tk.X, pady=(12, 0))

        ears_frame = ttk.Frame(self.control_frame)
        ears_frame.pack(fill=tk.X, padx=8, pady=(8, 6))
        ttk.Label(ears_frame, text="Oreille gauche").grid(row=0, column=0, sticky="w")
        ttk.Spinbox(ears_frame, from_=0, to=16, textvariable=self.ear_left_var, width=6).grid(row=0, column=1, padx=(8, 16))
        ttk.Label(ears_frame, text="Oreille droite").grid(row=0, column=2, sticky="w")
        ttk.Spinbox(ears_frame, from_=0, to=16, textvariable=self.ear_right_var, width=6).grid(row=0, column=3, padx=(8, 16))
        ttk.Button(ears_frame, text="Bouger les oreilles", command=self.move_rabbit_ears).grid(row=0, column=4, sticky="e")

        led_frame = ttk.Frame(self.control_frame)
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

        radio_frame = ttk.Frame(self.control_frame)
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

        power_frame = ttk.Frame(self.control_frame)
        power_frame.pack(fill=tk.X, padx=8, pady=(6, 8))
        ttk.Button(power_frame, text="Dormir", command=self.put_rabbit_to_sleep).pack(side=tk.LEFT)
        ttk.Button(power_frame, text="Réveiller", command=self.wake_rabbit).pack(side=tk.LEFT, padx=(8, 0))

        self.log_frame = ttk.LabelFrame(self.app_container, text="Journal")
        self.log_frame.pack(fill=tk.BOTH, expand=True, pady=(12, 0))
        self.log_widget = scrolledtext.ScrolledText(self.log_frame, wrap=tk.WORD, height=12, state=tk.DISABLED)
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
        if self.app_shell is not None:
            self.app_shell.pack_forget()
        if self.auth_container is not None:
            self.auth_container.pack(fill=tk.BOTH, expand=True)
        self.root.geometry("540x720")
        self.root.deiconify()
        self.root.lift()
        self.root.after(50, self._focus_auth_form)

    def _show_app_view(self) -> None:
        if self.auth_container is not None:
            self.auth_container.pack_forget()
        if self.app_shell is not None:
            self.app_shell.pack(fill=tk.BOTH, expand=True)
        if self.app_canvas is not None:
            self.app_canvas.yview_moveto(0)
        self.root.geometry("860x760")
        self.root.deiconify()
        self.root.lift()

    def _set_app_mode(self, *, has_rabbits: bool) -> None:
        if self.provisioning_frame is not None:
            if has_rabbits:
                self.provisioning_frame.pack_forget()
            else:
                self.provisioning_frame.pack(fill=tk.X, pady=(0, 12))
        if self.rabbit_selection_frame is not None:
            if has_rabbits:
                self.rabbit_selection_frame.pack(fill=tk.X, pady=(0, 12))
            else:
                self.rabbit_selection_frame.pack_forget()
        if self.talk_frame is not None:
            if has_rabbits:
                self.talk_frame.pack(fill=tk.BOTH, expand=True)
            else:
                self.talk_frame.pack_forget()
        if self.control_frame is not None:
            if has_rabbits:
                self.control_frame.pack(fill=tk.X, pady=(12, 0))
            else:
                self.control_frame.pack_forget()
        if self.log_frame is not None:
            if has_rabbits:
                self.log_frame.pack(fill=tk.BOTH, expand=True, pady=(12, 0))
            else:
                self.log_frame.pack_forget()
        if self.app_canvas is not None:
            self.root.after(0, lambda: self.app_canvas.configure(scrollregion=self.app_canvas.bbox("all")))

    def show_add_rabbit_flow(self) -> None:
        self._set_app_mode(has_rabbits=False)
        self.bootstrap_status_var.set("Connecte un nouveau lapin en suivant cette procédure.")
        if self.app_canvas is not None:
            self.app_canvas.yview_moveto(0)

    def _on_app_container_configure(self, _event=None) -> None:
        if self.app_canvas is None:
            return
        self.app_canvas.configure(scrollregion=self.app_canvas.bbox("all"))

    def _on_app_canvas_configure(self, event) -> None:
        if self.app_canvas is None:
            return
        self.app_canvas.itemconfigure(self.app_canvas_window, width=event.width)

    def _on_mousewheel(self, event) -> None:
        if self.app_canvas is None:
            return
        if event.delta:
            self.app_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        elif getattr(event, "num", None) == 4:
            self.app_canvas.yview_scroll(-1, "units")
        elif getattr(event, "num", None) == 5:
            self.app_canvas.yview_scroll(1, "units")

    def _bind_app_mousewheel(self, _event=None) -> None:
        self.root.bind_all("<MouseWheel>", self._on_mousewheel)
        self.root.bind_all("<Button-4>", self._on_mousewheel)
        self.root.bind_all("<Button-5>", self._on_mousewheel)

    def _unbind_app_mousewheel(self, _event=None) -> None:
        self.root.unbind_all("<MouseWheel>")
        self.root.unbind_all("<Button-4>")
        self.root.unbind_all("<Button-5>")

    def _focus_auth_form(self) -> None:
        target = self.password_entry if self.account_email_var.get().strip() else self.email_entry
        if target is None:
            return
        try:
            target.focus_force()
            target.icursor(tk.END)
        except tk.TclError:
            return

    def _load_existing_config(self) -> None:
        config = client_support.load_config()
        if not config:
            self._show_auth_view()
            return
        portal = str(config.get("portal") or "").strip()
        if portal:
            self.portal_var.set(portal)
        companion = config.get("companion") if isinstance(config.get("companion"), dict) else {}
        email = str(companion.get("email") or "").strip()
        if email:
            self.account_email_var.set(email)
        self.status_var.set("Connecte-toi pour accéder à tes lapins.")
        self._update_violet_platform()
        self._show_auth_view()

    def _run_in_thread(self, fn, *, on_error: str) -> None:
        def target() -> None:
            self.root.after(0, lambda: self.root.configure(cursor="watch"))
            try:
                fn()
            except Exception as exc:
                self.log_queue.put(f"Erreur: {exc}")
                self.root.after(0, lambda: self.status_var.set(f"{on_error} {exc}"))
            finally:
                self.root.after(0, lambda: self.root.configure(cursor=""))

        threading.Thread(target=target, daemon=True).start()

    def _update_violet_platform(self) -> None:
        self.bootstrap_violet_platform_var.set(
            provisioning_support.build_violet_platform_value(self.portal_var.get())
        )

    def open_account_registration(self) -> None:
        portal = client_support.normalize_portal_base(self.portal_var.get())
        provisioning_support.open_external_url(f"{portal}/register")

    def _companion_token(self) -> tuple[str, str]:
        config = client_support.load_config()
        portal = client_support.normalize_portal_base(str(config.get("portal") or self.portal_var.get() or ""))
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
            response = client_support.http_json(
                url=f"{client_support.normalize_portal_base(portal)}/mobile-api/v1/session/login",
                method="POST",
                payload={"email": email, "password": password, "device_name": "Nabaztag macOS"},
            )
            if not response.get("ok"):
                raise RuntimeError(response.get("message") or "Connexion impossible.")
            config = client_support.load_config()
            config["portal"] = client_support.normalize_portal_base(portal)
            config["companion"] = {"api_token": response["api_token"], "email": email}
            client_support.save_config(config)
            rabbit_count = len(response.get("rabbits") or []) if isinstance(response.get("rabbits"), list) else 0
            self.log_queue.put("Application macOS connectée au compte.")
            self.root.after(0, lambda: self.account_password_var.set(""))
            self.root.after(0, self._update_violet_platform)
            self.root.after(0, self._show_app_view)
            self.root.after(0, lambda: self._set_app_mode(has_rabbits=rabbit_count > 0))
            self.root.after(0, lambda: self.status_var.set(f"Connecté au compte. {rabbit_count} lapin(s) disponible(s)."))
            self.root.after(0, self.refresh_rabbits)

        self._run_in_thread(do_login, on_error="Impossible de connecter l'application macOS.")

    def logout(self) -> None:
        config = client_support.load_config()
        companion = config.get("companion") if isinstance(config.get("companion"), dict) else {}
        config["companion"] = {"email": str(companion.get("email") or self.account_email_var.get() or "").strip().lower()}
        client_support.save_config(config)
        self.rabbits_by_label = {}
        self.selected_rabbit_id = None
        self.selected_rabbit_status_var.set("Aucun lapin sélectionné.")
        if self.rabbit_listbox is not None:
            self.rabbit_listbox.delete(0, tk.END)
        self.status_var.set("Déconnecté. Connecte-toi pour accéder à tes lapins.")
        self._update_violet_platform()
        self._show_auth_view()
        self.log_queue.put("Application macOS déconnectée du compte.")

    def detect_mac_wifi(self) -> None:
        self.bootstrap_wifi_status_var.set("Détection du Wi-Fi du Mac…")

        def do_detect() -> None:
            interface, ssid = provisioning_support.current_wifi_ssid()
            if not interface:
                raise RuntimeError("Impossible d'identifier l'interface Wi-Fi du Mac.")
            password = provisioning_support.read_wifi_password(ssid or "") if ssid else None

            def update_ui() -> None:
                if ssid:
                    self.bootstrap_home_ssid_var.set(ssid)
                if password and not self.bootstrap_home_password_var.get().strip():
                    self.bootstrap_home_password_var.set(password)
                if ssid and password:
                    self.bootstrap_wifi_status_var.set(
                        f"Wi-Fi détecté sur {interface} : {ssid}. Mot de passe récupéré depuis le trousseau."
                    )
                elif ssid:
                    self.bootstrap_wifi_status_var.set(
                        f"Wi-Fi détecté sur {interface} : {ssid}. Saisis le mot de passe pour le lapin."
                    )
                else:
                    self.bootstrap_wifi_status_var.set(
                        f"Interface Wi-Fi détectée : {interface}, mais aucun SSID actif n'a été trouvé."
                    )

            self.root.after(0, update_ui)
            self.log_queue.put("Détection Wi-Fi du Mac terminée.")

        self._run_in_thread(do_detect, on_error="Impossible de détecter le Wi-Fi du Mac.")

    def probe_local_bootstrap(self) -> None:
        host = " ".join(self.bootstrap_host_var.get().split()).strip() or "192.168.0.1"
        self.bootstrap_status_var.set(f"Test du configurateur local sur {host}…")

        def do_probe() -> None:
            result = provisioning_support.probe_bootstrap_host(host)

            def update_ui() -> None:
                message = f"Lapin joignable sur {result.get('url') or f'http://{host}/'}."
                if result.get("has_start_link"):
                    message += " Lien de démarrage détecté."
                if result.get("advanced_url"):
                    message += " Vue Advanced configuration détectée."
                self.bootstrap_status_var.set(message)

            self.root.after(0, update_ui)
            self.log_queue.put(f"Configurateur local détecté sur {host}.")

        self._run_in_thread(do_probe, on_error="Impossible de joindre le configurateur local du lapin.")

    def open_local_bootstrap(self) -> None:
        host = " ".join(self.bootstrap_host_var.get().split()).strip() or "192.168.0.1"
        if provisioning_support.open_bootstrap_page(host):
            self.bootstrap_status_var.set(f"Configurateur local ouvert sur http://{host}/")
        else:
            self.bootstrap_status_var.set(f"Impossible d'ouvrir automatiquement http://{host}/")

    def configure_local_bootstrap(self) -> None:
        host = " ".join(self.bootstrap_host_var.get().split()).strip() or "192.168.0.1"
        home_wifi_ssid = " ".join(self.bootstrap_home_ssid_var.get().split()).strip()
        home_wifi_password = self.bootstrap_home_password_var.get()
        if not home_wifi_ssid or not home_wifi_password:
            messagebox.showerror("Nabaztag", "Saisis le Wi-Fi maison et son mot de passe.")
            return

        self.bootstrap_status_var.set("Envoi de la configuration au lapin…")

        def do_configure() -> None:
            result = provisioning_support.configure_bootstrap_host(
                host=host,
                home_wifi_ssid=home_wifi_ssid,
                home_wifi_password=home_wifi_password,
                portal_base=self.portal_var.get(),
            )

            def update_ui() -> None:
                self.bootstrap_violet_platform_var.set(str(result.get("violet_platform") or ""))
                self.bootstrap_status_var.set(str(result.get("message") or "Configuration envoyée au lapin."))

            self.root.after(0, update_ui)
            self.log_queue.put(f"Configuration locale envoyée au lapin via {host}.")

        self._run_in_thread(do_configure, on_error="Impossible de configurer automatiquement le lapin.")

    def refresh_rabbits(self) -> None:
        portal, token = self._companion_token()
        if not portal or not token:
            self.status_var.set("Application non connectée au compte.")
            self._show_auth_view()
            return

        def do_refresh() -> None:
            response = client_support.http_json(
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
                self.rabbits_by_label = rabbit_map
                has_rabbits = bool(labels)
                self._set_app_mode(has_rabbits=has_rabbits)
                if self.rabbit_listbox is not None:
                    current_index = None
                    if labels:
                        current_selection = self.rabbit_listbox.curselection()
                        if current_selection:
                            current_index = current_selection[0]
                        self.rabbit_listbox.delete(0, tk.END)
                        for label in labels:
                            self.rabbit_listbox.insert(tk.END, label)
                        if current_index is not None and 0 <= current_index < len(labels):
                            self.rabbit_listbox.selection_set(current_index)
                        else:
                            self.rabbit_listbox.selection_set(0)
                        self.rabbit_listbox.activate(self.rabbit_listbox.curselection()[0])
                    else:
                        self.rabbit_listbox.delete(0, tk.END)
                        self.selected_rabbit_id = None
                        self.selected_rabbit_status_var.set("Aucun lapin sélectionné.")
                    self.on_rabbit_selected()
                    self.status_var.set(
                        f"Connecté au compte. {len(labels)} lapin(s) disponible(s)."
                        if labels
                        else "Aucun lapin rattaché pour l'instant. Connectez votre lapin."
                    )
                self._show_app_view()

            self.root.after(0, update_ui)
            self.log_queue.put("Liste des lapins rafraîchie.")

        self._run_in_thread(do_refresh, on_error="Impossible de récupérer les lapins.")

    def on_rabbit_selected(self, _event=None) -> None:
        if self.rabbit_listbox is None:
            return
        selection = self.rabbit_listbox.curselection()
        if not selection:
            self.selected_rabbit_id = None
            self.selected_rabbit_status_var.set("Aucun lapin sélectionné.")
            return
        label = " ".join(str(self.rabbit_listbox.get(selection[0]) or "").split()).strip()
        rabbit = self.rabbits_by_label.get(label) or {}
        rabbit_id = rabbit.get("id")
        self.selected_rabbit_id = int(rabbit_id) if isinstance(rabbit_id, int) else None
        status = " ".join(str(rabbit.get("status") or "").split()).strip().lower()
        if status == "online":
            self.selected_rabbit_status_var.set("Statut du lapin : connecté")
        elif status:
            self.selected_rabbit_status_var.set("Statut du lapin : non connecté")
        else:
            self.selected_rabbit_status_var.set("Statut du lapin : inconnu")

    def _select_rabbit_by_id(self, rabbit_id: int) -> None:
        if self.rabbit_listbox is None:
            return
        for index, (label, rabbit) in enumerate(self.rabbits_by_label.items()):
            if rabbit.get("id") == rabbit_id:
                self.rabbit_listbox.selection_clear(0, tk.END)
                self.rabbit_listbox.selection_set(index)
                self.rabbit_listbox.activate(index)
                self.on_rabbit_selected()
                return

    def load_rabbit_pairing_code(self) -> None:
        portal = client_support.normalize_portal_base(self.portal_var.get().strip())
        pairing_token = "".join(self.rabbit_app_pairing_code_var.get().upper().split())
        if not portal or not pairing_token:
            messagebox.showerror("Nabaztag", "Saisis le portail et le code temporaire.")
            return

        def do_load() -> None:
            response = client_support.http_json(
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
        portal = client_support.normalize_portal_base(self.portal_var.get().strip())
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
            response = client_support.http_json(
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
        rabbit_id = self.selected_rabbit_id
        self.status_var.set("Envoi du message au lapin…")

        def do_send() -> None:
            response = client_support.http_json(
                url=f"{portal}/mobile-api/v1/rabbits/{rabbit_id}/conversation",
                method="POST",
                token=token,
                payload={"text": message},
                timeout=180,
            )
            if not response.get("ok"):
                raise RuntimeError(response.get("message") or "Envoi impossible.")
            reply = " ".join(str(response.get("reply") or "").split()).strip()
            self.log_queue.put(f"Message envoyé au lapin {rabbit_id}.")
            if reply:
                self.log_queue.put(f"Réponse du lapin : {reply}")
            self.root.after(0, lambda: self.message_text.delete("1.0", tk.END))
            self.root.after(0, lambda: self.status_var.set("Message envoyé au lapin."))

        self._run_in_thread(do_send, on_error="Impossible d'envoyer le message au lapin.")

    def _invoke_rabbit_api(self, path: str, payload: dict, *, success_message: str, error_message: str) -> None:
        portal, token = self._require_session()
        if not portal or not token:
            return

        def do_invoke() -> None:
            response = client_support.http_json(
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
