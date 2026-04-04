from __future__ import annotations

import json
import queue
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, scrolledtext, ttk


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.local_bridge import bridge_agent


class BridgeApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Nabaztag Bridge")
        self.root.geometry("760x560")

        self.portal_var = tk.StringVar(value="https://nabaztag.org")
        self.pairing_token_var = tk.StringVar()
        self.bridge_name_var = tk.StringVar(value="maison")
        self.status_var = tk.StringVar(value="Bridge non appairé.")

        self.log_queue: queue.Queue[str] = queue.Queue()
        self.run_thread: threading.Thread | None = None
        self.run_stop = threading.Event()

        self._build_ui()
        self._load_existing_config()
        self._schedule_log_poll()

    def _build_ui(self) -> None:
        container = ttk.Frame(self.root, padding=16)
        container.pack(fill=tk.BOTH, expand=True)

        title = ttk.Label(container, text="Nabaztag Bridge", font=("Helvetica", 20, "bold"))
        title.pack(anchor=tk.W)

        subtitle = ttk.Label(
            container,
            text="Client macOS minimal pour appairer et lancer le bridge local Nabaztag.",
        )
        subtitle.pack(anchor=tk.W, pady=(4, 16))

        form = ttk.Frame(container)
        form.pack(fill=tk.X)
        form.columnconfigure(1, weight=1)

        self._labeled_entry(form, 0, "Portail", self.portal_var)
        self._labeled_entry(form, 1, "Code d'appairage", self.pairing_token_var)
        self._labeled_entry(form, 2, "Nom du bridge", self.bridge_name_var)

        actions = ttk.Frame(container)
        actions.pack(fill=tk.X, pady=(16, 12))

        ttk.Button(actions, text="Appairer le bridge", command=self.pair_bridge).pack(side=tk.LEFT)
        ttk.Button(actions, text="Démarrer le bridge", command=self.start_bridge).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(actions, text="Arrêter", command=self.stop_bridge).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(actions, text="Rafraîchir l'état", command=self.refresh_status).pack(side=tk.LEFT, padx=(8, 0))

        status_frame = ttk.LabelFrame(container, text="État")
        status_frame.pack(fill=tk.X, pady=(0, 12))
        ttk.Label(status_frame, textvariable=self.status_var, wraplength=680).pack(anchor=tk.W, padx=12, pady=12)

        log_frame = ttk.LabelFrame(container, text="Journal")
        log_frame.pack(fill=tk.BOTH, expand=True)
        self.log_widget = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, height=18, state=tk.DISABLED)
        self.log_widget.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

    def _labeled_entry(self, parent: ttk.Frame, row: int, label: str, variable: tk.StringVar) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=6)
        ttk.Entry(parent, textvariable=variable).grid(row=row, column=1, sticky="ew", pady=6)

    def _append_log(self, message: str) -> None:
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

    def _load_existing_config(self) -> None:
        config = bridge_agent.load_config()
        if not config:
            return
        portal = str(config.get("portal") or "").strip()
        bridge_name = str((config.get("bridge") or {}).get("name") or "").strip()
        if portal:
            self.portal_var.set(portal)
        if bridge_name:
            self.bridge_name_var.set(bridge_name)
        self.status_var.set(f"Bridge configuré : {bridge_name or 'bridge'}")

    def _run_in_thread(self, fn, *, on_error: str) -> None:
        def target() -> None:
            try:
                fn()
            except Exception as exc:
                self.log_queue.put(f"Erreur: {exc}")
                self.root.after(0, lambda: messagebox.showerror("Nabaztag Bridge", f"{on_error}\n\n{exc}"))

        threading.Thread(target=target, daemon=True).start()

    def pair_bridge(self) -> None:
        portal = self.portal_var.get().strip()
        pairing_token = self.pairing_token_var.get().strip()
        bridge_name = self.bridge_name_var.get().strip() or "maison"
        if not portal or not pairing_token:
            messagebox.showerror("Nabaztag Bridge", "Saisis le portail et le code d'appairage.")
            return

        def do_pair() -> None:
            args = type(
                "Args",
                (),
                {"portal": portal, "pairing_token": pairing_token, "name": bridge_name},
            )()
            exit_code = bridge_agent.pair(args)
            if exit_code != 0:
                raise RuntimeError("Appairage impossible.")
            self.log_queue.put("Bridge appairé avec succès.")
            self.root.after(0, self._load_existing_config)
            self.root.after(0, self.refresh_status)

        self._run_in_thread(do_pair, on_error="Impossible d'appairer le bridge.")

    def refresh_status(self) -> None:
        config = bridge_agent.load_config()
        portal = str(config.get("portal") or "").strip()
        token = str(config.get("bridge_token") or "").strip()
        if not portal or not token:
            self.status_var.set("Bridge non appairé.")
            return

        def do_refresh() -> None:
            response = bridge_agent.http_json(
                url=f"{bridge_agent.normalize_portal_base(portal)}/bridge-api/v1/me",
                method="GET",
                token=token,
            )
            bridge = response.get("bridge") or {}
            status = f"Bridge actif : {bridge.get('name', 'bridge')}"
            capabilities = bridge.get("capabilities") or []
            capability_names = [item.get("name") for item in capabilities if isinstance(item, dict) and item.get("name")]
            if capability_names:
                status += f" | capacités : {', '.join(capability_names)}"
            self.root.after(0, lambda: self.status_var.set(status))
            self.log_queue.put("État du bridge rafraîchi.")

        self._run_in_thread(do_refresh, on_error="Impossible de récupérer l'état du bridge.")

    def start_bridge(self) -> None:
        if self.run_thread and self.run_thread.is_alive():
            self.log_queue.put("Le bridge tourne déjà.")
            return

        config = bridge_agent.load_config()
        if not config:
            messagebox.showerror("Nabaztag Bridge", "Appaire d'abord le bridge.")
            return

        self.run_stop.clear()

        def loop() -> None:
            self.log_queue.put("Boucle bridge démarrée.")
            portal = bridge_agent.normalize_portal_base(str(config.get("portal") or ""))
            token = str(config.get("bridge_token") or "").strip()
            while not self.run_stop.is_set():
                try:
                    response = bridge_agent.http_json(
                        url=f"{portal}/bridge-api/v1/commands/next",
                        method="GET",
                        token=token,
                    )
                    command = response.get("command")
                    if not command:
                        time.sleep(2.0)
                        continue
                    command_id = int(command["id"])
                    try:
                        result = bridge_agent.execute_command(command.get("payload") or {})
                        bridge_agent.http_json(
                            url=f"{portal}/bridge-api/v1/commands/{command_id}/complete",
                            method="POST",
                            token=token,
                            payload={"status": "done", "result": result},
                        )
                        self.log_queue.put(f"Commande {command_id} exécutée.")
                    except Exception as exc:
                        bridge_agent.http_json(
                            url=f"{portal}/bridge-api/v1/commands/{command_id}/complete",
                            method="POST",
                            token=token,
                            payload={"status": "failed", "error": str(exc)},
                        )
                        self.log_queue.put(f"Commande {command_id} en échec : {exc}")
                except Exception as exc:
                    self.log_queue.put(f"Erreur de boucle bridge : {exc}")
                    time.sleep(2.0)
            self.log_queue.put("Boucle bridge arrêtée.")

        self.run_thread = threading.Thread(target=loop, daemon=True)
        self.run_thread.start()
        self.status_var.set("Bridge en cours d'exécution.")

    def stop_bridge(self) -> None:
        self.run_stop.set()
        self.status_var.set("Bridge arrêté.")


def main() -> int:
    root = tk.Tk()
    style = ttk.Style(root)
    if "aqua" in style.theme_names():
        style.theme_use("aqua")
    app = BridgeApp(root)
    app.refresh_status()
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
