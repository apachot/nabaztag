from setuptools import setup


APP = ["app.py"]
DATA_FILES = []
OPTIONS = {
    "argv_emulation": False,
    "plist": {
        "CFBundleName": "Nabaztag Bridge",
        "CFBundleDisplayName": "Nabaztag Bridge",
        "CFBundleIdentifier": "org.nabaztag.bridge",
        "CFBundleShortVersionString": "0.1.0",
        "CFBundleVersion": "0.1.0",
    },
    "packages": [],
}


setup(
    app=APP,
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
