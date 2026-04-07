from setuptools import setup


APP = ["qt_client.py"]
DATA_FILES = [("assets", ["assets/setup-mode-button-hold.png", "assets/logo-nabaztag-org.png"])]
OPTIONS = {
    "argv_emulation": False,
    "includes": [
        "client_support",
        "provisioning_support",
        "qt_client",
        "CoreLocation",
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        "shiboken6",
    ],
    "plist": {
        "CFBundleName": "Nabaztag",
        "CFBundleDisplayName": "Nabaztag",
        "CFBundleIdentifier": "org.nabaztag.macos",
        "CFBundleShortVersionString": "0.2.0",
        "CFBundleVersion": "0.2.0",
        "NSLocationWhenInUseUsageDescription": (
            "Nabaztag a besoin de la localisation pour détecter les réseaux Wi-Fi Nabaztag à proximité."
        ),
    },
    "packages": [],
}


setup(
    app=APP,
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
)
