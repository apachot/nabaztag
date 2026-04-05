from setuptools import setup


APP = ["app.py"]
DATA_FILES = []
OPTIONS = {
    "argv_emulation": False,
    "includes": ["client_support", "provisioning_support"],
    "plist": {
        "CFBundleName": "Nabaztag",
        "CFBundleDisplayName": "Nabaztag",
        "CFBundleIdentifier": "org.nabaztag.macos",
        "CFBundleShortVersionString": "0.2.0",
        "CFBundleVersion": "0.2.0",
    },
    "packages": [],
}


setup(
    app=APP,
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
