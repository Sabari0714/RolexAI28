import unittest

from modules.policy import policy_status
from modules.security import sha256_text
from modules.automation import LocalScheduler


class CoreImportTests(unittest.TestCase):
    def test_policy_status(self):
        self.assertIn("External AI providers: DISABLED", policy_status())

    def test_hash(self):
        self.assertEqual(len(sha256_text("Rolex")), 64)

    def test_scheduler(self):
        self.assertIsNotNone(LocalScheduler())


if __name__ == "__main__":
    unittest.main()
