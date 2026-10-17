"""Smoke test for chronos package initialization."""

import unittest
import chronos


class TestChronosInit(unittest.TestCase):
    def test_version_defined(self):
        self.assertEqual(chronos.__version__, "0.1.0")


if __name__ == "__main__":
    unittest.main()
