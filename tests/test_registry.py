from __future__ import annotations

import unittest

from astar_agents.registry import AGENT_PROFILES


class RegistryTests(unittest.TestCase):
    def test_all_subordinate_references_exist(self) -> None:
        missing = sorted(
            {
                subordinate
                for profile in AGENT_PROFILES.values()
                for subordinate in profile.subordinates
                if subordinate not in AGENT_PROFILES
            }
        )
        self.assertEqual(missing, [])

    def test_all_manager_references_exist(self) -> None:
        missing = sorted(
            {
                profile.reports_to
                for profile in AGENT_PROFILES.values()
                if profile.reports_to and profile.reports_to not in AGENT_PROFILES
            }
        )
        self.assertEqual(missing, [])
