import unittest

from hermes_audit.privacy import redact_value


class PrivacyTests(unittest.TestCase):
    def test_redacts_bearer_keys_and_url_tokens_recursively(self):
        original = {
            "command": "curl -H 'Authorization: Bearer super-secret-123456' https://x.test/?token=abcdef123456",
            "nested": ["API_KEY=abcdef123456", "sk-" + "x" * 30],
        }
        output = redact_value(original)
        self.assertNotIn("super-secret-123456", str(output))
        self.assertNotIn("abcdef123456", str(output))
        self.assertNotIn("sk-" + "x" * 30, str(output))
        self.assertIn("[REDACTED]", str(output))
        self.assertIn("curl", output["command"])

    def test_redacts_sensitive_header_values_and_nested_dictionary_fields(self):
        source = {"headers": {"Authorization": "Basic dXNlcjpwYXNz", "Cookie": "session=abc123456"},
                  "password": "plainpass123", "safe": "hello"}
        result = redact_value(source)
        self.assertEqual(result["headers"]["Authorization"], "[REDACTED]")
        self.assertEqual(result["headers"]["Cookie"], "[REDACTED]")
        self.assertEqual(result["password"], "[REDACTED]")
        self.assertEqual(result["safe"], "hello")

    def test_redacts_basic_auth_in_shell_header(self):
        text = redact_value("curl -H 'Authorization: Basic dXNlcjpwYXNz' https://site.test")
        self.assertNotIn("dXNlcjpwYXNz", text)

    def test_redacts_fields_inside_json_encoded_tool_result(self):
        text = redact_value('{"Authorization":"Basic dXNlcjpwYXNz","password":"secretvalue123"}')
        self.assertNotIn("dXNlcjpwYXNz", text)
        self.assertNotIn("secretvalue123", text)
        self.assertIn("[REDACTED]", text)

    def test_redacts_client_secret_and_x_api_key_in_json_result(self):
        raw = '{"client_secret":"client-demo-987654","X-API-Key":"header-demo-123456"}'
        safe = redact_value(raw)
        self.assertNotIn("client-demo-987654", safe)
        self.assertNotIn("header-demo-123456", safe)

    def test_redacts_client_secret_and_x_api_key_in_plain_result(self):
        raw = "client_secret=client-demo-987654 X-API-Key: header-demo-123456"
        safe = redact_value(raw)
        self.assertNotIn("client-demo-987654", safe)
        self.assertNotIn("header-demo-123456", safe)


if __name__ == "__main__":
    unittest.main()
