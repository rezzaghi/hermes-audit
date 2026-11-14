import json
import stat
import tempfile
import unittest
from pathlib import Path

from hermes_audit.report import render_report


class ReportTests(unittest.TestCase):
    def test_generates_standalone_html_with_redacted_safe_embedded_data(self):
        event = {
            "id": "s:1:0", "kind": "tool", "role": "assistant", "tool": "terminal",
            "session_id": "s", "session_title": "audit", "source": "telegram",
            "timestamp": 1700000000, "severity": "critical", "failed": False,
            "tags": ["credential-access"], "reasons": ["credential path"],
            "arguments": {"command": "cat /tmp/.env; API_KEY=abcdef123456"},
            "result": "</script><script>alert('unsafe')</script>",
        }
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "report.html"
            render_report([event], output)
            page = output.read_text(encoding="utf-8")
            mode = stat.S_IMODE(output.stat().st_mode)
        self.assertIn('<script id="report-data" type="application/json">', page)
        self.assertIn("Search", page)
        self.assertIn("s:1:0", page)
        self.assertIn("[REDACTED]", page)
        self.assertNotIn("abcdef123456", page)
        self.assertNotIn("</script><script>alert", page)
        self.assertNotIn('src="https://', page)
        self.assertIn("\\u003c/script\\u003e", page)
        self.assertEqual(mode, 0o600)

    def test_export_redacts_nested_credentials_before_embedding(self):
        event = {"id":"s:1:0","kind":"tool","tool":"web_search","session_id":"s",
                 "session_title":"demo","source":"telegram","timestamp":1,"severity":"low",
                 "failed":False,"tags":[],"reasons":[],"arguments":{},
                 "result":'{"client_secret":"client-demo-987654","X-API-Key":"header-demo-123456"}'}
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "report.html"
            render_report([event], output)
            page = output.read_text(encoding="utf-8")
        self.assertNotIn("client-demo-987654", page)
        self.assertNotIn("header-demo-123456", page)


if __name__ == "__main__":
    unittest.main()
