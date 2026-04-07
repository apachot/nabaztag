from __future__ import annotations

import sys
from PySide6.QtCore import QThread, QTimer, Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsBlurEffect,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

import client_support
import provisioning_support


class LoginWorker(QThread):
    finished_ok = Signal(dict)
    failed = Signal(str)

    def __init__(self, *, portal: str, email: str, password: str) -> None:
        super().__init__()
        self.portal = portal
        self.email = email
        self.password = password

    def run(self) -> None:
        try:
            response = client_support.http_json(
                url=f"{client_support.normalize_portal_base(self.portal)}/mobile-api/v1/session/login",
                method="POST",
                payload={"email": self.email, "password": self.password, "device_name": "Nabaztag macOS Qt"},
            )
            if not response.get("ok"):
                raise RuntimeError(response.get("message") or "Connexion impossible.")
            self.finished_ok.emit(response)
        except Exception as exc:
            self.failed.emit(str(exc))


class RefreshWorker(QThread):
    finished_ok = Signal(dict)
    failed = Signal(str)

    def __init__(self, *, portal: str, token: str) -> None:
        super().__init__()
        self.portal = portal
        self.token = token

    def run(self) -> None:
        try:
            response = client_support.http_json(
                url=f"{self.portal}/mobile-api/v1/rabbits",
                method="GET",
                token=self.token,
            )
            self.finished_ok.emit(response)
        except Exception as exc:
            self.failed.emit(str(exc))


class ConversationWorker(QThread):
    finished_ok = Signal(dict)
    failed = Signal(str)

    def __init__(self, *, portal: str, token: str, rabbit_id: int, text: str) -> None:
        super().__init__()
        self.portal = portal
        self.token = token
        self.rabbit_id = rabbit_id
        self.text = text

    def run(self) -> None:
        try:
            response = client_support.http_json(
                url=f"{self.portal}/mobile-api/v1/rabbits/{self.rabbit_id}/conversation",
                method="POST",
                token=self.token,
                payload={"text": self.text},
                timeout=180,
            )
            if not response.get("ok"):
                raise RuntimeError(response.get("message") or "Envoi impossible.")
            self.finished_ok.emit(response)
        except Exception as exc:
            self.failed.emit(str(exc))


class DeleteRabbitWorker(QThread):
    finished_ok = Signal(dict)
    failed = Signal(str)

    def __init__(self, *, portal: str, token: str, rabbit_id: int) -> None:
        super().__init__()
        self.portal = portal
        self.token = token
        self.rabbit_id = rabbit_id

    def run(self) -> None:
        try:
            response = client_support.http_json(
                url=f"{self.portal}/mobile-api/v1/rabbits/{self.rabbit_id}",
                method="DELETE",
                token=self.token,
            )
            if not response.get("ok"):
                raise RuntimeError(response.get("message") or "Suppression impossible.")
            self.finished_ok.emit(response)
        except Exception as exc:
            self.failed.emit(str(exc))


class ProvisioningWorker(QThread):
    finished_ok = Signal(dict)
    failed = Signal(str)

    def __init__(self, *, action: str, payload: dict | None = None) -> None:
        super().__init__()
        self.action = action
        self.payload = payload or {}

    def run(self) -> None:
        try:
            if self.action == "detect_wifi":
                details = provisioning_support.current_wifi_configuration()
                self.finished_ok.emit(details)
                return
            if self.action == "scan_setup_networks":
                interface, networks, message = provisioning_support.scan_nearby_setup_networks()
                self.finished_ok.emit({"interface": interface or "", "networks": networks, "message": message or ""})
                return
            if self.action == "connect_setup_network":
                interface, ssid = provisioning_support.connect_wifi_network(
                    str(self.payload.get("ssid") or ""),
                    str(self.payload.get("password") or "") or None,
                )
                self.finished_ok.emit({"interface": interface, "ssid": ssid})
                return
            if self.action == "probe":
                result = provisioning_support.probe_bootstrap_host(str(self.payload.get("host") or "192.168.0.1"))
                self.finished_ok.emit(result)
                return
            if self.action == "configure":
                result = provisioning_support.configure_bootstrap_host(
                    host=str(self.payload.get("host") or "192.168.0.1"),
                    home_wifi_ssid=str(self.payload.get("home_wifi_ssid") or ""),
                    home_wifi_password=str(self.payload.get("home_wifi_password") or ""),
                    portal_base=str(self.payload.get("portal_base") or ""),
                    home_wifi_security=str(self.payload.get("home_wifi_security") or ""),
                )
                self.finished_ok.emit(result)
                return
            raise RuntimeError(f"Action de provisioning inconnue: {self.action}")
        except Exception as exc:
            self.failed.emit(str(exc))


class LoginView(QWidget):
    login_requested = Signal(str, str, str)

    def __init__(self) -> None:
        super().__init__()
        self.portal_input = QLineEdit("https://nabaztag.org")
        self.email_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.status_label = QLabel("Connecte-toi pour accéder à tes lapins.")
        self.status_label.setWordWrap(True)
        self.login_button = QPushButton("Connexion")

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 28, 28, 28)

        card = QFrame()
        card.setObjectName("loginCard")
        card.setMaximumWidth(460)
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(14)

        logo = QLabel()
        logo.setAlignment(Qt.AlignCenter)
        logo_path = provisioning_support.app_logo_image_path()
        if logo_path.exists():
            pixmap = QPixmap(str(logo_path))
            if not pixmap.isNull():
                logo.setPixmap(pixmap.scaledToWidth(220, Qt.SmoothTransformation))
        card_layout.addWidget(logo)

        subtitle = QLabel("Identifie-toi pour retrouver immédiatement tes lapins.")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setWordWrap(True)
        subtitle.setObjectName("subtitle")
        card_layout.addWidget(subtitle)

        for label_text, widget in (
            ("Portail", self.portal_input),
            ("Identifiant", self.email_input),
            ("Mot de passe", self.password_input),
        ):
            label = QLabel(label_text)
            card_layout.addWidget(label)
            card_layout.addWidget(widget)

        self.login_button.clicked.connect(self._emit_login)
        self.password_input.returnPressed.connect(self._emit_login)
        card_layout.addWidget(self.login_button)
        card_layout.addWidget(self.status_label)

        outer = QHBoxLayout()
        outer.addStretch(1)
        outer.addWidget(card)
        outer.addStretch(1)
        root.addStretch(1)
        root.addLayout(outer)
        root.addStretch(1)

    def _emit_login(self) -> None:
        self.login_requested.emit(
            self.portal_input.text().strip(),
            self.email_input.text().strip().lower(),
            self.password_input.text(),
        )

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)


class RabbitPanel(QWidget):
    send_requested = Signal(str)
    refresh_requested = Signal()
    add_rabbit_requested = Signal()
    logout_requested = Signal()
    delete_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.rabbits_list = QListWidget()
        self.status_label = QLabel("Aucun lapin sélectionné.")
        self.message_input = QTextEdit()
        self.message_input.setPlaceholderText("Écris un message pour le lapin…")
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)

        root = QVBoxLayout(self)
        toolbar = QHBoxLayout()
        title = QLabel("Mes lapins")
        title.setObjectName("panelTitle")
        logout_button = QPushButton("Se déconnecter")
        logout_button.clicked.connect(self.logout_requested.emit)
        refresh_button = QPushButton("Rafraîchir")
        refresh_button.clicked.connect(self.refresh_requested.emit)
        toolbar.addWidget(title)
        toolbar.addStretch(1)
        toolbar.addWidget(logout_button)
        add_button = QPushButton("Ajouter un lapin")
        add_button.clicked.connect(self.add_rabbit_requested.emit)
        toolbar.addWidget(add_button)
        delete_button = QPushButton("Supprimer ce lapin")
        delete_button.clicked.connect(self.delete_requested.emit)
        toolbar.addWidget(delete_button)
        toolbar.addWidget(refresh_button)
        root.addLayout(toolbar)

        splitter = QSplitter()
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(QLabel("Lapins"))
        left_layout.addWidget(self.rabbits_list)
        left_layout.addWidget(self.status_label)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.addWidget(QLabel("Lui parler"))
        right_layout.addWidget(self.message_input)
        send_button = QPushButton("Envoyer au lapin")
        send_button.clicked.connect(self._emit_send)
        right_layout.addWidget(send_button)
        right_layout.addWidget(QLabel("Journal"))
        right_layout.addWidget(self.log_output)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter)

    def _emit_send(self) -> None:
        text = " ".join(self.message_input.toPlainText().split()).strip()
        if text:
            self.send_requested.emit(text)

    def append_log(self, text: str) -> None:
        self.log_output.append(text)

    def clear_selection_state(self) -> None:
        self.rabbits_list.clearSelection()
        self.status_label.setText("Aucun lapin sélectionné.")
        self.message_input.clear()


class ProvisioningView(QWidget):
    scan_setup_networks_requested = Signal()
    attach_requested = Signal(str)
    back_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.status_label = QLabel("Mets ton lapin en mode configuration, puis attends qu'il soit détecté à proximité.")
        self.detected_setup_list = QListWidget()
        self.detected_setup_list.setMaximumHeight(180)
        self.status_label.setWordWrap(True)

        root = QVBoxLayout(self)
        toolbar = QHBoxLayout()
        title = QLabel("Connectez votre lapin")
        title.setObjectName("panelTitle")
        back_button = QPushButton("Retour à mes lapins")
        back_button.clicked.connect(self.back_requested.emit)
        toolbar.addWidget(title)
        toolbar.addStretch(1)
        toolbar.addWidget(back_button)
        root.addLayout(toolbar)

        card = QFrame()
        card.setObjectName("loginCard")
        card_layout = QVBoxLayout(card)

        illustration = QLabel()
        illustration.setAlignment(Qt.AlignCenter)
        setup_image = provisioning_support.setup_mode_image_path()
        if setup_image.exists():
            pixmap = QPixmap(str(setup_image))
            if not pixmap.isNull():
                illustration.setPixmap(pixmap.scaledToWidth(260, Qt.SmoothTransformation))
        card_layout.addWidget(illustration)

        explainer = QLabel(
            "Maintiens le bouton du Nabaztag pendant le branchement pour le passer en mode configuration. "
            "L'application recherche ensuite automatiquement les lapins visibles à proximité."
        )
        explainer.setWordWrap(True)
        card_layout.addWidget(explainer)

        nearby_label = QLabel("Lapins detectes a proximite")
        card_layout.addWidget(nearby_label)
        card_layout.addWidget(self.detected_setup_list)

        buttons = QHBoxLayout()
        scan_button = QPushButton("Rechercher les Nabaztag a proximite")
        scan_button.clicked.connect(self.scan_setup_networks_requested.emit)
        attach_button = QPushButton("Rattacher ce lapin")
        attach_button.clicked.connect(self._emit_attach)
        buttons.addWidget(scan_button)
        buttons.addStretch(1)
        buttons.addWidget(attach_button)
        card_layout.addLayout(buttons)

        card_layout.addWidget(self.status_label)

        root.addWidget(card)
        root.addStretch(1)

    def set_detected_setup_networks(self, networks: list[str]) -> None:
        self.detected_setup_list.clear()
        for network in networks:
            self.detected_setup_list.addItem(network)

    def _emit_attach(self) -> None:
        item = self.detected_setup_list.currentItem()
        if item is not None:
            self.attach_requested.emit(item.text().strip())


class BlockingOverlay(QWidget):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("blockingOverlay")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.hide()

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setAlignment(Qt.AlignCenter)

        card = QFrame()
        card.setObjectName("blockingOverlayCard")
        card.setMinimumWidth(420)
        card.setMaximumWidth(520)
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(14)

        self.title_label = QLabel("Connexion au lapin")
        self.title_label.setObjectName("blockingOverlayTitle")
        self.message_label = QLabel("")
        self.message_label.setWordWrap(True)
        self.message_label.setObjectName("blockingOverlayMessage")

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)

        card_layout.addWidget(self.title_label)
        card_layout.addWidget(self.message_label)
        card_layout.addWidget(self.progress)
        root.addWidget(card)

    def update_message(self, title: str, message: str) -> None:
        self.title_label.setText(title)
        self.message_label.setText(message)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Nabaztag")
        self.resize(960, 760)

        self.portal = "https://nabaztag.org"
        self.api_token = ""
        self.rabbits: list[dict] = []
        self.selected_rabbit_id: int | None = None
        self.login_worker: LoginWorker | None = None
        self.refresh_worker: RefreshWorker | None = None
        self.conversation_worker: ConversationWorker | None = None
        self.provisioning_worker: ProvisioningWorker | None = None
        self.active_provisioning_workers: list[ProvisioningWorker] = []
        self.delete_rabbit_worker: DeleteRabbitWorker | None = None
        self.wait_blur_effect = QGraphicsBlurEffect(self)
        self.wait_blur_effect.setBlurRadius(10)
        self.location_poll_timer = QTimer(self)
        self.location_poll_timer.setInterval(1000)
        self.location_poll_timer.timeout.connect(self._poll_location_authorization)
        self.location_request_pending = False
        self.auto_scan_after_location = False
        self.last_prompted_setup_ssid: str | None = None
        self.pending_setup_ssid: str | None = None
        self.pending_home_wifi: dict[str, str] | None = None

        self.stack = QStackedWidget()
        self.login_view = LoginView()
        self.rabbit_panel = RabbitPanel()
        self.provisioning_view = ProvisioningView()
        self.stack.addWidget(self.login_view)
        self.stack.addWidget(self.provisioning_view)
        self.stack.addWidget(self.rabbit_panel)
        self.setCentralWidget(self.stack)
        self.blocking_overlay = BlockingOverlay(self.stack)
        self.blocking_overlay.setGeometry(self.stack.rect())

        self.login_view.login_requested.connect(self.login)
        self.rabbit_panel.refresh_requested.connect(self.refresh_rabbits)
        self.rabbit_panel.send_requested.connect(self.send_message)
        self.rabbit_panel.add_rabbit_requested.connect(self.show_provisioning_view)
        self.rabbit_panel.logout_requested.connect(self.logout)
        self.rabbit_panel.delete_requested.connect(self.delete_selected_rabbit)
        self.rabbit_panel.rabbits_list.currentItemChanged.connect(self._on_rabbit_selected)
        self.provisioning_view.scan_setup_networks_requested.connect(self.scan_setup_networks)
        self.provisioning_view.attach_requested.connect(self.attach_detected_rabbit)
        self.provisioning_view.back_requested.connect(self.show_rabbit_or_login_view)

        self._apply_styles()
        self._restore_session()

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow, QWidget { background: #f4f1eb; color: #181715; font-size: 14px; }
            QFrame#loginCard {
                background: #fffdfa;
                border: 1px solid #d8d1c4;
                padding: 12px;
            }
            QLabel#subtitle { color: #7d776d; }
            QLabel#panelTitle { font-size: 24px; font-weight: 700; color: #243b37; }
            QLineEdit, QTextEdit, QListWidget {
                background: #fffdfa;
                border: 1px solid #d8d1c4;
                padding: 8px;
            }
            QPushButton {
                background: #f1e4d7;
                color: #243b37;
                border: 1px solid #d8d1c4;
                padding: 8px 14px;
            }
            QPushButton:hover { background: #ead7c7; }
            QWidget#blockingOverlay {
                background: rgba(28, 24, 20, 140);
            }
            QFrame#blockingOverlayCard {
                background: rgba(255, 253, 250, 238);
                border: 1px solid #d8d1c4;
                border-radius: 18px;
                padding: 18px;
            }
            QLabel#blockingOverlayTitle {
                font-size: 22px;
                font-weight: 700;
                color: #243b37;
            }
            QLabel#blockingOverlayMessage {
                font-size: 15px;
                color: #433b34;
            }
            QProgressBar {
                border: 1px solid #d8d1c4;
                border-radius: 8px;
                background: #efe6dc;
                min-height: 14px;
            }
            QProgressBar::chunk {
                background: #c66f3d;
                border-radius: 8px;
            }
            """
        )

    def _restore_session(self) -> None:
        config = client_support.load_config()
        portal = str(config.get("portal") or "").strip()
        companion = config.get("companion") if isinstance(config.get("companion"), dict) else {}
        email = str(companion.get("email") or "").strip()
        token = str(companion.get("api_token") or "").strip()
        if portal:
            self.portal = client_support.normalize_portal_base(portal)
            self.login_view.portal_input.setText(self.portal)
        if email:
            self.login_view.email_input.setText(email)
        if token:
            self.api_token = token
            self.login_view.set_status("Reconnexion automatique au compte…")
            self.refresh_rabbits()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.blocking_overlay.setGeometry(self.stack.rect())

    def _show_wait_overlay(self, message: str, title: str = "Connexion au lapin") -> None:
        self.blocking_overlay.setGeometry(self.stack.rect())
        self.blocking_overlay.update_message(title, message)
        self.stack.setGraphicsEffect(self.wait_blur_effect)
        self.blocking_overlay.raise_()
        self.blocking_overlay.show()

    def _hide_wait_overlay(self) -> None:
        self.blocking_overlay.hide()
        self.stack.setGraphicsEffect(None)

    def login(self, portal: str, email: str, password: str) -> None:
        if not portal or not email or not password:
            self.login_view.set_status("Saisis le portail, l'identifiant et le mot de passe.")
            return
        self.login_view.set_status("Connexion en cours…")
        self.login_worker = LoginWorker(portal=portal, email=email, password=password)
        self.login_worker.finished_ok.connect(self._on_login_success)
        self.login_worker.failed.connect(self._on_login_failed)
        self.login_worker.start()

    def _on_login_success(self, response: dict) -> None:
        email = str(response.get("user", {}).get("email") or self.login_view.email_input.text()).strip()
        self.portal = client_support.normalize_portal_base(self.login_view.portal_input.text())
        self.api_token = str(response.get("api_token") or "").strip()
        config = client_support.load_config()
        config["portal"] = self.portal
        config["companion"] = {"api_token": self.api_token, "email": email}
        client_support.save_config(config)
        self.refresh_rabbits()

    def _on_login_failed(self, message: str) -> None:
        self.login_view.set_status(message)

    def refresh_rabbits(self) -> None:
        if not self.api_token:
            self.stack.setCurrentWidget(self.login_view)
            return
        self.refresh_worker = RefreshWorker(portal=self.portal, token=self.api_token)
        self.refresh_worker.finished_ok.connect(self._on_refresh_success)
        self.refresh_worker.failed.connect(self._on_refresh_failed)
        self.refresh_worker.start()

    def _on_refresh_success(self, response: dict) -> None:
        self.rabbits = response.get("rabbits") if isinstance(response.get("rabbits"), list) else []
        self.rabbit_panel.rabbits_list.clear()
        self.selected_rabbit_id = None
        for rabbit in self.rabbits:
            name = str(rabbit.get("name") or "").strip() or "Lapin"
            status = str(rabbit.get("status") or "unknown").strip()
            item = QListWidgetItem(f"{name} ({status})")
            item.setData(Qt.UserRole, rabbit)
            self.rabbit_panel.rabbits_list.addItem(item)
        self.show_rabbit_or_login_view()
        if self.rabbits:
            self.rabbit_panel.rabbits_list.setCurrentRow(0)
            self.rabbit_panel.append_log("Liste des lapins rafraîchie.")
        else:
            self.rabbit_panel.clear_selection_state()
            self.provisioning_view.status_label.setText("Aucun lapin rattaché pour l'instant. Connectez votre premier lapin.")

    def _on_refresh_failed(self, message: str) -> None:
        self.login_view.set_status(message)
        self.stack.setCurrentWidget(self.login_view)

    def logout(self) -> None:
        config = client_support.load_config()
        companion = config.get("companion") if isinstance(config.get("companion"), dict) else {}
        config["companion"] = {
            "email": str(companion.get("email") or self.login_view.email_input.text() or "").strip().lower()
        }
        client_support.save_config(config)
        self.api_token = ""
        self.rabbits = []
        self.selected_rabbit_id = None
        self.rabbit_panel.rabbits_list.clear()
        self.rabbit_panel.clear_selection_state()
        self.login_view.password_input.clear()
        self.login_view.set_status("Déconnecté. Connecte-toi pour accéder à tes lapins.")
        self.stack.setCurrentWidget(self.login_view)

    def show_provisioning_view(self) -> None:
        self.provisioning_view.set_detected_setup_networks([])
        self.last_prompted_setup_ssid = None
        self.provisioning_view.status_label.setText(
            "Mets ton lapin en mode configuration, puis attends qu'il soit détecté à proximité."
        )
        self.stack.setCurrentWidget(self.provisioning_view)
        if self._ensure_location_authorization():
            self.scan_setup_networks()

    def _ensure_location_authorization(self) -> bool:
        status = provisioning_support.location_authorization_status()
        if status in {"authorized_when_in_use", "authorized_always"}:
            self.location_request_pending = False
            self.auto_scan_after_location = False
            self.location_poll_timer.stop()
            return True
        if status == "not_determined":
            self.auto_scan_after_location = True
            self.request_location_authorization()
            return False
        elif status in {"restricted", "denied"}:
            self.provisioning_view.status_label.setText(
                "La localisation est requise pour detecter les reseaux Wi-Fi Nabaztag. "
                "Autorise Nabaztag dans Reglages Systeme > Confidentialite et securite > Service de localisation."
            )
            self.auto_scan_after_location = True
            return False
        return False

    def _poll_location_authorization(self) -> None:
        if self.stack.currentWidget() is not self.provisioning_view:
            self.location_poll_timer.stop()
            self.location_request_pending = False
            return
        status = provisioning_support.location_authorization_status()
        if status in {"authorized_when_in_use", "authorized_always"}:
            self.location_poll_timer.stop()
            self.location_request_pending = False
            self.provisioning_view.status_label.setText("La localisation est autorisee. Recherche des reseaux Wi-Fi…")
            if self.auto_scan_after_location:
                self.auto_scan_after_location = False
                self.scan_setup_networks()
        elif status in {"restricted", "denied"}:
            self.location_poll_timer.stop()
            self.location_request_pending = False
            self.provisioning_view.status_label.setText(
                "macOS refuse actuellement l'acces a la localisation. "
                "Autorise Nabaztag dans Reglages Systeme > Confidentialite et securite > Service de localisation."
            )

    def show_rabbit_or_login_view(self) -> None:
        if self.rabbits:
            self.stack.setCurrentWidget(self.rabbit_panel)
        elif self.api_token:
            self.show_provisioning_view()
        else:
            self.stack.setCurrentWidget(self.login_view)

    def scan_setup_networks(self) -> None:
        self.provisioning_view.status_label.setText("Recherche des reseaux Nabaztag a proximite…")
        self._start_provisioning_worker(
            ProvisioningWorker(action="scan_setup_networks"),
            self._on_scan_setup_networks_success,
            self._on_provisioning_failed,
        )

    def _start_provisioning_worker(
        self,
        worker: ProvisioningWorker,
        success_handler,
        failure_handler,
    ) -> None:
        self.provisioning_worker = worker
        self.active_provisioning_workers.append(worker)
        worker.finished_ok.connect(success_handler)
        worker.failed.connect(failure_handler)
        worker.finished.connect(lambda worker=worker: self._on_provisioning_worker_finished(worker))
        worker.start()

    def _on_provisioning_worker_finished(self, worker: ProvisioningWorker) -> None:
        if self.provisioning_worker is worker:
            self.provisioning_worker = None
        if worker in self.active_provisioning_workers:
            self.active_provisioning_workers.remove(worker)
        worker.deleteLater()

    def _on_scan_setup_networks_success(self, result: dict) -> None:
        interface = str(result.get("interface") or "").strip()
        networks = [str(item).strip() for item in result.get("networks") or [] if str(item).strip()]
        diagnostic = " ".join(str(result.get("message") or "").split()).strip()
        self.provisioning_view.set_detected_setup_networks(networks)
        if networks:
            self.provisioning_view.detected_setup_list.setCurrentRow(0)
            prefix = f"sur {interface} " if interface else ""
            self.provisioning_view.status_label.setText(
                f"{len(networks)} reseau(x) Nabaztag detecte(s) {prefix}a proximite."
            )
            first_network = networks[0]
            if self.last_prompted_setup_ssid != first_network:
                self.last_prompted_setup_ssid = first_network
                confirmation = QMessageBox.question(
                    self,
                    "Nabaztag detecte",
                    f"Le lapin {first_network} a ete detecte.\n\nVeux-tu le rattacher maintenant ?",
                )
                if confirmation == QMessageBox.Yes:
                    self.attach_detected_rabbit(first_network)
        else:
            self.last_prompted_setup_ssid = None
            self.provisioning_view.status_label.setText(
                diagnostic
                or "Aucun reseau Nabaztag detecte a proximite. Relance la recherche."
            )

    def _on_provisioning_failed(self, message: str) -> None:
        self._hide_wait_overlay()
        self.provisioning_view.status_label.setText(message)

    def attach_detected_rabbit(self, setup_ssid: str) -> None:
        if not setup_ssid:
            QMessageBox.warning(self, "Nabaztag", "Choisis d'abord un lapin détecté à proximité.")
            return
        self.pending_setup_ssid = setup_ssid
        self.provisioning_view.status_label.setText(
            "Preparation du Wi-Fi maison…"
        )
        self._show_wait_overlay(
            "Preparation du Wi-Fi maison avant la connexion au lapin. Merci de patienter."
        )
        self._start_provisioning_worker(
            ProvisioningWorker(action="detect_wifi"),
            self._on_detect_home_wifi_success,
            self._on_detect_home_wifi_failed,
        )

    def _on_detect_home_wifi_success(self, result: dict) -> None:
        interface = str(result.get("interface") or "").strip()
        ssid = str(result.get("ssid") or "").strip()
        security = str(result.get("security") or "").strip()
        self._hide_wait_overlay()
        if not ssid:
            self._on_detect_home_wifi_failed("Impossible de determiner le Wi-Fi maison actuel du Mac.")
            return

        label = "Mot de passe du Wi-Fi maison"
        if security:
            label += f" ({ssid}, {security})"
        else:
            label += f" ({ssid})"
        password, accepted = QInputDialog.getText(
            self,
            "Wi-Fi maison",
            label,
            QLineEdit.Password,
        )
        if not accepted:
            self.pending_home_wifi = None
            self.pending_setup_ssid = None
            self.provisioning_view.status_label.setText("Rattachement du lapin annule.")
            return
        if not password:
            self._on_detect_home_wifi_failed("Le mot de passe du Wi-Fi maison est requis.")
            return

        self.pending_home_wifi = {
            "interface": interface,
            "ssid": ssid,
            "password": password,
            "security": security,
        }
        setup_ssid = self.pending_setup_ssid or ""
        self.provisioning_view.status_label.setText(f"Connexion au reseau {setup_ssid}…")
        self._show_wait_overlay(
            f"Connexion en cours au reseau {setup_ssid}. Laisse le Mac basculer automatiquement sur le Wi-Fi du lapin."
        )
        self._start_provisioning_worker(
            ProvisioningWorker(
                action="connect_setup_network",
                payload={"ssid": setup_ssid},
            ),
            self._on_connect_setup_network_success,
            self._on_connect_setup_network_failed,
        )

    def _on_detect_home_wifi_failed(self, message: str) -> None:
        self._hide_wait_overlay()
        self.pending_home_wifi = None
        self.pending_setup_ssid = None
        self.provisioning_view.status_label.setText(message)
        QMessageBox.warning(
            self,
            "Nabaztag",
            (
                "Impossible de recuperer automatiquement le Wi-Fi maison "
                "(nom, mot de passe ou type de securite).\n\n"
                f"{message}"
            ),
        )

    def _on_connect_setup_network_success(self, result: dict) -> None:
        setup_ssid = str(result.get("ssid") or self.pending_setup_ssid or "").strip()
        interface = str(result.get("interface") or "").strip()
        self.provisioning_view.status_label.setText(
            f"Connecte au reseau {setup_ssid} {f'sur {interface} ' if interface else ''}. Verification du configurateur local…"
        )
        self._show_wait_overlay(
            f"Connexion au reseau {setup_ssid} reussie. Verification du configurateur local du lapin…"
        )
        self._start_provisioning_worker(
            ProvisioningWorker(
                action="probe",
                payload={"host": "192.168.0.1"},
            ),
            self._on_probe_setup_network_success,
            self._on_probe_setup_network_failed,
        )

    def _on_connect_setup_network_failed(self, message: str) -> None:
        self._hide_wait_overlay()
        self.pending_home_wifi = None
        self.pending_setup_ssid = None
        self.provisioning_view.status_label.setText(message)
        QMessageBox.warning(
            self,
            "Nabaztag",
            f"Impossible de se connecter automatiquement au reseau du lapin.\n\n{message}",
        )

    def _on_probe_setup_network_success(self, result: dict) -> None:
        setup_ssid = self.pending_setup_ssid or "Nabaztag"
        home_wifi = self.pending_home_wifi or {}
        home_ssid = str(home_wifi.get("ssid") or "").strip()
        home_password = str(home_wifi.get("password") or "")
        home_security = str(home_wifi.get("security") or "").strip()
        if not home_ssid or not home_password:
            self._on_probe_setup_network_failed(
                "Le Wi-Fi maison n'a pas pu etre prepare automatiquement."
            )
            return
        self.provisioning_view.status_label.setText(
            f"Connecte au reseau {setup_ssid}. Envoi de la configuration Wi-Fi au lapin…"
        )
        self._show_wait_overlay(
            "Le lapin est joignable. Envoi de la configuration Wi-Fi maison et redemarrage en cours…"
        )
        self._start_provisioning_worker(
            ProvisioningWorker(
                action="configure",
                payload={
                    "host": "192.168.0.1",
                    "home_wifi_ssid": home_ssid,
                    "home_wifi_password": home_password,
                    "home_wifi_security": home_security,
                    "portal_base": self.portal,
                },
            ),
            self._on_configure_setup_network_success,
            self._on_configure_setup_network_failed,
        )

    def _on_probe_setup_network_failed(self, message: str) -> None:
        self._hide_wait_overlay()
        setup_ssid = self.pending_setup_ssid or "Nabaztag"
        self.provisioning_view.status_label.setText(
            f"Connecte au reseau {setup_ssid}, mais le configurateur local ne repond pas encore."
        )
        QMessageBox.warning(
            self,
            "Nabaztag",
            (
                f"Le Mac a bien bascule sur le reseau {setup_ssid}, "
                f"mais http://192.168.0.1/ ne repond pas encore.\n\n{message}"
            ),
        )
        self.pending_home_wifi = None
        self.pending_setup_ssid = None

    def _on_configure_setup_network_success(self, result: dict) -> None:
        setup_ssid = self.pending_setup_ssid or "Nabaztag"
        message = " ".join(str(result.get("message") or "").split()).strip() or "Configuration envoyee au lapin."
        home_wifi = self.pending_home_wifi or {}
        home_ssid = str(home_wifi.get("ssid") or "").strip()
        home_password = str(home_wifi.get("password") or "")
        if not home_ssid:
            self._hide_wait_overlay()
            self.provisioning_view.status_label.setText(message)
            QMessageBox.information(
                self,
                "Nabaztag",
                (
                    f"Le lapin {setup_ssid} a recu les parametres du Wi-Fi maison.\n\n"
                    f"{message}"
                ),
            )
            self.pending_home_wifi = None
            self.pending_setup_ssid = None
            return

        self.provisioning_view.status_label.setText(
            f"{message} Reconnexion automatique au Wi-Fi maison {home_ssid}…"
        )
        self._show_wait_overlay(
            f"Le lapin a recu la configuration. Reconnexion automatique du Mac au reseau {home_ssid}…"
        )
        self._start_provisioning_worker(
            ProvisioningWorker(
                action="connect_setup_network",
                payload={"ssid": home_ssid, "password": home_password},
            ),
            lambda reconnect_result, bootstrap_message=message, bootstrap_ssid=setup_ssid: self._on_reconnect_home_wifi_success(
                reconnect_result,
                bootstrap_message,
                bootstrap_ssid,
            ),
            lambda reconnect_error, bootstrap_message=message, bootstrap_ssid=setup_ssid, home_network=home_ssid: self._on_reconnect_home_wifi_failed(
                reconnect_error,
                bootstrap_message,
                bootstrap_ssid,
                home_network,
            ),
        )

    def _on_configure_setup_network_failed(self, message: str) -> None:
        self._hide_wait_overlay()
        setup_ssid = self.pending_setup_ssid or "Nabaztag"
        self.provisioning_view.status_label.setText(
            f"Connecte au reseau {setup_ssid}, mais l'envoi de la configuration a echoue."
        )
        QMessageBox.warning(
            self,
            "Nabaztag",
            (
                f"Le Mac est bien connecte au reseau {setup_ssid}, "
                f"mais l'envoi a http://192.168.0.1/b.htm a echoue.\n\n{message}"
            ),
        )
        self.pending_home_wifi = None
        self.pending_setup_ssid = None

    def _on_reconnect_home_wifi_success(
        self,
        result: dict,
        bootstrap_message: str,
        bootstrap_ssid: str,
    ) -> None:
        self._hide_wait_overlay()
        home_ssid = str(result.get("ssid") or "").strip() or str(
            (self.pending_home_wifi or {}).get("ssid") or "Wi-Fi maison"
        ).strip()
        interface = str(result.get("interface") or "").strip()
        self.provisioning_view.status_label.setText(
            f"Reconnecte au Wi-Fi maison {home_ssid}."
        )
        QMessageBox.information(
            self,
            "Nabaztag",
            (
                f"Le lapin {bootstrap_ssid} a recu les parametres du Wi-Fi maison.\n\n"
                f"{bootstrap_message}\n\n"
                f"Le Mac a ete reconnecte automatiquement au reseau {home_ssid}"
                f"{f' sur {interface}' if interface else ''}."
            ),
        )
        self.pending_home_wifi = None
        self.pending_setup_ssid = None

    def _on_reconnect_home_wifi_failed(
        self,
        message: str,
        bootstrap_message: str,
        bootstrap_ssid: str,
        home_ssid: str,
    ) -> None:
        self._hide_wait_overlay()
        self.provisioning_view.status_label.setText(
            f"Le lapin est configure, mais la reconnexion au Wi-Fi maison {home_ssid} a echoue."
        )
        QMessageBox.warning(
            self,
            "Nabaztag",
            (
                f"Le lapin {bootstrap_ssid} a recu les parametres du Wi-Fi maison.\n\n"
                f"{bootstrap_message}\n\n"
                f"Le Mac n'a pas pu se reconnecter automatiquement au reseau {home_ssid}.\n\n"
                f"{message}"
            ),
        )
        self.pending_home_wifi = None
        self.pending_setup_ssid = None

    def request_location_authorization(self) -> None:
        status = provisioning_support.request_location_authorization()
        if status == "unavailable":
            self.provisioning_view.status_label.setText(
                "Impossible de demander automatiquement l'autorisation de localisation sur ce Mac."
            )
            return
        if status in {"authorized_when_in_use", "authorized_always"}:
            self.provisioning_view.status_label.setText(
                "La localisation est autorisee. Recherche des reseaux Wi-Fi…"
            )
            self.location_request_pending = False
            self.location_poll_timer.stop()
            if self.auto_scan_after_location:
                self.auto_scan_after_location = False
            self.scan_setup_networks()
            return
        if status in {"restricted", "denied"}:
            self.provisioning_view.status_label.setText(
                "macOS refuse actuellement l'acces a la localisation. "
                "Autorise Nabaztag dans Reglages Systeme > Confidentialite et securite > Service de localisation."
            )
            return
        self.location_request_pending = True
        self.location_poll_timer.start()
        self.provisioning_view.status_label.setText(
            "Demande d'autorisation envoyee a macOS. La recherche Wi-Fi se lancera automatiquement des que la localisation sera autorisee."
        )

    def open_location_settings(self) -> None:
        if provisioning_support.open_location_settings():
            self.provisioning_view.status_label.setText(
                "Réglages Système ouverts. Autorise l'application à accéder à la localisation puis relance la recherche."
            )
        else:
            self.provisioning_view.status_label.setText(
                "Impossible d'ouvrir automatiquement les Réglages Système."
            )

    def _on_rabbit_selected(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        rabbit = current.data(Qt.UserRole) if current is not None else {}
        rabbit_id = rabbit.get("id") if isinstance(rabbit, dict) else None
        self.selected_rabbit_id = int(rabbit_id) if isinstance(rabbit_id, int) else None
        status = str(rabbit.get("status") or "").strip().lower() if isinstance(rabbit, dict) else ""
        if status == "online":
            self.rabbit_panel.status_label.setText("Statut du lapin : connecté")
        elif status:
            self.rabbit_panel.status_label.setText("Statut du lapin : non connecté")
        else:
            self.rabbit_panel.status_label.setText("Statut du lapin : inconnu")

    def send_message(self, text: str) -> None:
        if self.selected_rabbit_id is None:
            QMessageBox.warning(self, "Nabaztag", "Choisis un lapin.")
            return
        self.conversation_worker = ConversationWorker(
            portal=self.portal,
            token=self.api_token,
            rabbit_id=self.selected_rabbit_id,
            text=text,
        )
        self.conversation_worker.finished_ok.connect(self._on_send_success)
        self.conversation_worker.failed.connect(self._on_send_failed)
        self.conversation_worker.start()
        self.rabbit_panel.append_log("Envoi du message au lapin…")

    def _on_send_success(self, response: dict) -> None:
        reply = " ".join(str(response.get("reply") or "").split()).strip()
        self.rabbit_panel.message_input.clear()
        self.rabbit_panel.append_log("Message envoyé au lapin.")
        if reply:
            self.rabbit_panel.append_log(f"Réponse du lapin : {reply}")

    def _on_send_failed(self, message: str) -> None:
        self.rabbit_panel.append_log(f"Erreur : {message}")

    def delete_selected_rabbit(self) -> None:
        if self.selected_rabbit_id is None:
            QMessageBox.warning(self, "Nabaztag", "Choisis un lapin.")
            return
        current_item = self.rabbit_panel.rabbits_list.currentItem()
        rabbit_label = current_item.text() if current_item is not None else "ce lapin"
        confirmation = QMessageBox.question(
            self,
            "Supprimer le lapin",
            f"Supprimer définitivement {rabbit_label} ?",
        )
        if confirmation != QMessageBox.Yes:
            return

        self.delete_rabbit_worker = DeleteRabbitWorker(
            portal=self.portal,
            token=self.api_token,
            rabbit_id=self.selected_rabbit_id,
        )
        self.delete_rabbit_worker.finished_ok.connect(self._on_delete_rabbit_success)
        self.delete_rabbit_worker.failed.connect(self._on_delete_rabbit_failed)
        self.delete_rabbit_worker.start()
        self.rabbit_panel.append_log("Suppression du lapin en cours…")

    def _on_delete_rabbit_success(self, response: dict) -> None:
        message = " ".join(str(response.get("message") or "").split()).strip() or "Lapin supprimé."
        self.selected_rabbit_id = None
        self.rabbit_panel.clear_selection_state()
        self.rabbit_panel.append_log(message)
        self.refresh_rabbits()

    def _on_delete_rabbit_failed(self, message: str) -> None:
        self.rabbit_panel.append_log(f"Erreur : {message}")


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
