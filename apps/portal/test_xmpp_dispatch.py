from __future__ import annotations

import importlib.util
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parent / "portal_app" / "xmpp_dispatch.py"
SPEC = importlib.util.spec_from_file_location("portal_app.xmpp_dispatch", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Unable to load {MODULE_PATH}")
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)
build_round_robin_batch = MODULE.build_round_robin_batch


class BuildRoundRobinBatchTests(unittest.TestCase):
    def test_interleaves_serials_instead_of_starving_recent_one(self) -> None:
        now = datetime(2026, 5, 15, 15, 0, 0)
        batch = build_round_robin_batch(
            {
                "0019db9c4fd0": [1, 2, 3, 4, 5],
                "0019db01de8e": [100, 101],
            },
            oldest_by_serial={
                "0019db9c4fd0": now - timedelta(days=8),
                "0019db01de8e": now,
            },
            limit=6,
        )

        self.assertEqual(batch, [1, 100, 2, 101, 3, 4])

    def test_respects_limit_and_ignores_empty_queues(self) -> None:
        now = datetime(2026, 5, 15, 15, 0, 0)
        batch = build_round_robin_batch(
            {
                "lapin-a": [],
                "lapin-b": [10, 11, 12],
                "lapin-c": [20],
            },
            oldest_by_serial={
                "lapin-a": now - timedelta(days=1),
                "lapin-b": now,
                "lapin-c": now + timedelta(minutes=1),
            },
            limit=3,
        )

        self.assertEqual(batch, [10, 20, 11])


if __name__ == "__main__":
    unittest.main()
