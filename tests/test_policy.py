import unittest

from modules.policy import provider_allowed


class ProviderPolicyTests(unittest.TestCase):
    def test_only_local_provider_is_allowed(self):
        self.assertTrue(provider_allowed("role-local"))
        self.assertFalse(provider_allowed("openai"))
        self.assertFalse(provider_allowed("gemini"))
        self.assertFalse(provider_allowed("ollama"))


if __name__ == "__main__":
    unittest.main()
