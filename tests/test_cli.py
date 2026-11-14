import json
import re
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    def test_cli_builds_report_without_mutating_database(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / 'state.db'
            out = Path(tmp) / 'audit.html'
            conn = sqlite3.connect(db)
            conn.executescript('''CREATE TABLE sessions (id TEXT, title TEXT, source TEXT, parent_session_id TEXT);
                CREATE TABLE messages (id INTEGER, session_id TEXT, role TEXT, content TEXT,
                tool_call_id TEXT, tool_calls TEXT, tool_name TEXT, timestamp REAL);''')
            conn.execute('INSERT INTO sessions VALUES (?,?,?,?)', ('s','first','telegram',None))
            call = {'id':'c','function':{'name':'terminal','arguments':json.dumps({'command':'echo API_KEY=abcdef123456'})}}
            conn.execute('INSERT INTO messages VALUES (?,?,?,?,?,?,?,?)',
                         (1,'s','assistant','',None,json.dumps([call]),None,1700000000))
            conn.execute('INSERT INTO messages VALUES (?,?,?,?,?,?,?,?)',
                         (2,'s','tool','{"success":true}','c',None,'terminal',1700000001))
            conn.commit(); conn.close()
            before = db.stat().st_mtime_ns
            done = subprocess.run([sys.executable, '-m', 'hermes_audit', '--db', str(db),
                                   '--out', str(out)], cwd=ROOT, text=True, capture_output=True)
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertIn('1 records', done.stdout)
            self.assertTrue(out.is_file())
            self.assertNotIn('abcdef123456', out.read_text())
            self.assertEqual(db.stat().st_mtime_ns, before)

    def test_minimum_severity_exports_only_high_and_critical_actions(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / 'state.db'
            out = Path(tmp) / 'high-risk.html'
            subprocess.run([sys.executable, 'tests/fixture.py', str(db)], cwd=ROOT, check=True)
            done = subprocess.run([sys.executable, '-m', 'hermes_audit', '--db', str(db),
                                   '--min-severity', 'high', '--out', str(out)],
                                  cwd=ROOT, text=True, capture_output=True)
            self.assertEqual(done.returncode, 0, done.stderr)
            text = out.read_text(encoding='utf-8')
            payload = re.search(r'<script id="report-data" type="application/json">(.*?)</script>', text).group(1)
            events = json.loads(payload)['events']
            self.assertEqual({e['tool'] for e in events}, {'terminal','browser_exec'})
            self.assertEqual({e['severity'] for e in events}, {'high','critical'})


if __name__ == '__main__':
    unittest.main()
