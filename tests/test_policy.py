import unittest

from modules.policy import (
    provider_allowed,
    is_external_provider,
    is_local_provider,
)


class ProviderPolicyTests(unittest.TestCase):

    def test_supported_providers(self):
        self.assertTrue(provider_allowed("role-local"))
        self.assertTrue(provider_allowed("openai"))
        self.assertTrue(provider_allowed("gemini"))
        self.assertTrue(provider_allowed("ollama"))

    def test_unknown_provider_blocked(self):
        self.assertFalse(provider_allowed("unknown"))
        self.assertFalse(provider_allowed("random-provider"))

    def test_external_detection(self):
        self.assertTrue(is_external_provider("openai"))
        self.assertTrue(is_external_provider("gemini"))
        self.assertTrue(is_external_provider("ollama"))
        self.assertFalse(is_external_provider("role-local"))

    def test_local_detection(self):
        self.assertTrue(is_local_provider("role-local"))
        self.assertFalse(is_local_provider("openai"))


if __name__ == "__main__":
    unittest.main()
