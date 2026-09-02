import unittest

from modules.policy import policy_status
from modules.security import sha256_text
from modules.automation import LocalScheduler


class CoreImportTests(unittest.TestCase):

    def test_policy_status(self):
        status = policy_status()

        self.assertIn(
            "Rolex final-answer policy: ON",
            status
        )

        self.assertIn(
            "External intelligence sources: ENABLED",
            status
        )

        self.assertIn(
            "Rolex final response: REQUIRED",
            status
        )

    def test_hash(self):
        self.assertEqual(
            len(sha256_text("Rolex")),
            64
        )

    def test_scheduler(self):
        self.assertIsNotNone(
            LocalScheduler()
        )


if __name__ == "__main__":
    unittest.main()
