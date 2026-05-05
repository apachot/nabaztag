from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.device_platform.adapters.nabaztag_tag import NabaztagTagAdapter
from app.device_platform.catalog import build_default_catalog
from app.device_platform.errors import UnsupportedPrimitiveError
from app.device_platform.mcp_server import ARCHITECTURE_DOC_PATH
from app.device_platform.models import DeviceTarget, SetLedPrimitiveRequest
from app.main import app
from app.models import ConnectionStatus
from app.protocol.types import ProtocolEventEnvelope
from app.settings import GatewaySettings


class DevicePlatformCatalogTest(unittest.TestCase):
    def test_default_catalog_exposes_all_targeted_families(self) -> None:
        catalog = build_default_catalog(GatewaySettings())

        models = catalog.list_models()
        keys = [model.key for model in models]

        self.assertCountEqual(keys, ["karotz", "nabaztag-tag", "nabaztag-v1"])

        descriptor = catalog.get_descriptor("nabaztag-tag")
        self.assertEqual(descriptor.implementation_status.value, "implemented")
        self.assertIn("docs/device-platform-architecture.md", descriptor.documentation_refs)

    def test_v1_recording_is_explicitly_unsupported(self) -> None:
        catalog = build_default_catalog(GatewaySettings())
        descriptor = catalog.get_descriptor("nabaztag-v1")

        primitive_statuses = {item.primitive.value: item.status.value for item in descriptor.primitives}

        self.assertEqual(primitive_statuses["audio.recording.start"], "unsupported")
        self.assertEqual(primitive_statuses["video.snapshot"], "unsupported")


class NabaztagTagAdapterTest(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter = NabaztagTagAdapter(GatewaySettings(driver="protocol"))
        self.target = DeviceTarget(host="192.168.0.21", label="kitchen-tag")

    def test_led_nose_is_rejected_by_capability_contract(self) -> None:
        with self.assertRaises(UnsupportedPrimitiveError):
            self.adapter.execute(
                self.target,
                SetLedPrimitiveRequest(target="nose", color="#112233"),
            )

    @patch("app.device_platform.adapters.nabaztag_tag.ProtocolClient.send_to")
    def test_led_all_uses_default_port_and_emits_warning(self, mock_send_to) -> None:
        mock_send_to.return_value = ProtocolEventEnvelope(
            kind="rabbit.info.accepted",
            connection_status=ConnectionStatus.ONLINE,
            payload={"status": "ok"},
        )

        result = self.adapter.execute(
            self.target,
            SetLedPrimitiveRequest(target="all", color="#abcdef"),
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.state.led_left, "#abcdef")
        self.assertEqual(result.state.led_center, "#abcdef")
        self.assertEqual(result.state.led_right, "#abcdef")
        self.assertEqual(
            result.warnings,
            ["`all` only updates left/center/right on Nabaztag:tag through nabd."],
        )
        self.assertEqual(mock_send_to.call_args.kwargs["port"], 10543)


class DevicePlatformApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)

    def test_models_endpoint_lists_device_platform_models(self) -> None:
        response = self.client.get("/api/device-platform/models")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        keys = [model["key"] for model in payload["models"]]

        self.assertIn("nabaztag-tag", keys)
        self.assertIn("karotz", keys)

    def test_unknown_model_returns_404(self) -> None:
        response = self.client.get("/api/device-platform/models/unknown-model")

        self.assertEqual(response.status_code, 404)
        self.assertIn("Unknown device model", response.json()["detail"])

    def test_planned_model_execute_returns_501(self) -> None:
        response = self.client.post(
            "/api/device-platform/execute",
            json={
                "model_key": "karotz",
                "target": {"host": "192.168.0.22"},
                "command": {"primitive": "lifecycle.sync"},
            },
        )

        self.assertEqual(response.status_code, 501)
        self.assertIn("does not have an executable adapter yet", response.json()["detail"])


class DevicePlatformMcpServerTest(unittest.TestCase):
    def test_architecture_doc_is_packaged_next_to_mcp_server(self) -> None:
        self.assertTrue(ARCHITECTURE_DOC_PATH.is_file())


if __name__ == "__main__":
    unittest.main()
