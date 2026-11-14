import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from hermes_audit.core import read_events


class HermesIngestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "state.db"
        conn = sqlite3.connect(self.db)
        conn.executescript("""
            CREATE TABLE sessions (id TEXT PRIMARY KEY, title TEXT, source TEXT,
                                   started_at REAL, parent_session_id TEXT);
            CREATE TABLE messages (id INTEGER PRIMARY KEY, session_id TEXT, role TEXT,
                                   content TEXT, tool_call_id TEXT, tool_calls TEXT,
                                   tool_name TEXT, timestamp REAL);
        """)
        conn.execute("INSERT INTO sessions VALUES (?, ?, ?, ?, ?)",
                     ("sess1", "Audit investigation", "telegram", 1700000000, None))
        call = {"id": "call_1", "type": "function", "function": {
            "name": "web_search", "arguments": json.dumps({"query": "safety evals"})}}
        conn.execute("INSERT INTO messages VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                     (1, "sess1", "assistant", "", None, json.dumps([call]), None, 1700000001))
        conn.execute("INSERT INTO messages VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                     (2, "sess1", "tool", '{"data":{"web":[]}}', "call_1", None, "web_search", 1700000002))
        conn.commit()
        conn.close()

    def test_pairs_a_real_tool_call_and_result_from_sqlite(self):
        events = read_events(self.db)
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event["id"], "sess1:1:0")
        self.assertEqual(event["tool"], "web_search")
        self.assertEqual(event["arguments"], {"query": "safety evals"})
        self.assertEqual(event["result"], '{"data":{"web":[]}}')
        self.assertEqual(event["session_title"], "Audit investigation")
        self.assertFalse(event["failed"])

    def test_failed_result_and_orphan_result_are_visible(self):
        conn = sqlite3.connect(self.db)
        conn.execute("UPDATE messages SET content = ? WHERE id = 2",
                     ('{"success":false,"exit_code":1}',))
        conn.execute("INSERT INTO messages VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                     (3, "sess1", "tool", "Traceback (most recent call last)",
                      "missing_call", None, "terminal", 1700000003))
        conn.commit()
        conn.close()
        events = read_events(self.db)
        self.assertEqual(len(events), 2)
        self.assertTrue(events[0]["failed"])
        self.assertEqual(events[1]["tool"], "terminal")
        self.assertIn("orphan-result", events[1]["tags"])
        self.assertIn("failure", events[1]["tags"])

    def test_session_filter_can_include_descendants(self):
        conn = sqlite3.connect(self.db)
        conn.execute("INSERT INTO sessions VALUES (?, ?, ?, ?, ?)",
                     ("child", "delegated", "tool", 1700000003, "sess1"))
        call = {"id": "child_call", "function": {"name": "calculator", "arguments": "{}"}}
        conn.execute("INSERT INTO messages VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                     (4, "child", "assistant", "", None, json.dumps([call]), None, 1700000004))
        conn.commit()
        conn.close()
        self.assertEqual(len(read_events(self.db, "sess1")), 1)
        combined = read_events(self.db, "sess1", include_lineage=True)
        self.assertEqual({e["session_id"] for e in combined}, {"sess1", "child"})

    def test_keeps_user_request_and_assistant_reply_as_context(self):
        conn = sqlite3.connect(self.db)
        conn.execute("INSERT INTO messages VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                     (0, "sess1", "user", "Find benchmark scores", None, None, None, 1699999999))
        conn.execute("INSERT INTO messages VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                     (3, "sess1", "assistant", "Here is the answer", None, None, None, 1700000003))
        conn.commit()
        conn.close()
        events = read_events(self.db)
        self.assertEqual([e["kind"] for e in events], ["message", "tool", "message"])
        self.assertEqual(events[0]["role"], "user")
        self.assertEqual(events[2]["result"], "Here is the answer")
        self.assertEqual(events[2]["severity"], "info")

    def test_reused_provider_id_pairs_by_occurrence_uid(self):
        conn = sqlite3.connect(self.db)
        for column in ("message_uid", "tool_call_uids", "tool_call_uid"):
            conn.execute(f"ALTER TABLE messages ADD COLUMN {column} TEXT")
        conn.execute("UPDATE messages SET message_uid=?,tool_call_uids=? WHERE id=1",
                     ("message-a", json.dumps({"call_1":"uid-a"})))
        conn.execute("UPDATE messages SET tool_call_uid=? WHERE id=2", ("uid-a",))
        conn.execute("UPDATE messages SET id=4 WHERE id=2")
        call = {"id":"call_1", "function":{"name":"terminal", "arguments":"{}"}}
        conn.execute("INSERT INTO messages (id,session_id,role,content,tool_calls,timestamp,message_uid,tool_call_uids) VALUES (?,?,?,?,?,?,?,?)",
                     (3,"sess1","assistant","",json.dumps([call]),1700000003,"message-b",json.dumps({"call_1":"uid-b"})))
        conn.execute("INSERT INTO messages (id,session_id,role,content,tool_call_id,tool_name,timestamp,tool_call_uid) VALUES (?,?,?,?,?,?,?,?)",
                     (5,"sess1","tool","second result","call_1","terminal",1700000005,"uid-b"))
        conn.commit(); conn.close()
        events = read_events(self.db)
        self.assertEqual({e["id"]:e["result"] for e in events},
                         {"sess1:uid-a":'{"data":{"web":[]}}',"sess1:uid-b":"second result"})

    def test_annotation_identity_survives_message_row_id_changes(self):
        conn = sqlite3.connect(self.db)
        for column in ("message_uid", "tool_call_uids", "tool_call_uid"):
            conn.execute(f"ALTER TABLE messages ADD COLUMN {column} TEXT")
        conn.execute("UPDATE messages SET message_uid=?,tool_call_uids=? WHERE id=1",
                     ("stable-message",json.dumps({"call_1":"stable-call"})))
        conn.execute("UPDATE messages SET tool_call_uid=? WHERE id=2", ("stable-call",))
        conn.commit()
        first = read_events(self.db)[0]["id"]
        conn.execute("UPDATE messages SET id=10 WHERE id=1")
        conn.execute("UPDATE messages SET id=20 WHERE id=2")
        conn.commit();conn.close()
        self.assertEqual(read_events(self.db)[0]["id"], first)
        self.assertEqual(first,"sess1:stable-call")

    def test_duplicate_provider_ids_sharing_uid_keep_distinct_events_and_results(self):
        conn = sqlite3.connect(self.db)
        for column in ("message_uid", "tool_call_uids", "tool_call_uid"):
            conn.execute(f"ALTER TABLE messages ADD COLUMN {column} TEXT")
        calls = [{"id":"same", "function":{"name":"web_search","arguments":"{}"}},
                 {"id":"same", "function":{"name":"terminal","arguments":"{}"}}]
        conn.execute("UPDATE messages SET tool_calls=?,message_uid=?,tool_call_uids=? WHERE id=1",
                     (json.dumps(calls), "shared-message", json.dumps({"same":"shared-uid"})))
        conn.execute("UPDATE messages SET tool_call_id=?,tool_call_uid=?,content=? WHERE id=2",
                     ("same", "shared-uid", "first result"))
        conn.execute("INSERT INTO messages (id,session_id,role,content,tool_call_id,tool_name,timestamp,tool_call_uid) VALUES (?,?,?,?,?,?,?,?)",
                     (3,"sess1","tool","second result","same","terminal",1700000003,"shared-uid"))
        conn.commit();conn.close()
        events = read_events(self.db)
        self.assertEqual(len(events), 2)
        self.assertEqual(len({e["id"] for e in events}), 2)
        self.assertEqual([e["result"] for e in events], ["first result", "second result"])

    def test_repeated_orphan_result_uid_uses_distinct_message_identities(self):
        conn = sqlite3.connect(self.db)
        conn.execute("ALTER TABLE messages ADD COLUMN message_uid TEXT")
        conn.execute("ALTER TABLE messages ADD COLUMN tool_call_uid TEXT")
        for row_id, uid, content in ((3,"orphan-a","first orphan"),(4,"orphan-b","second orphan")):
            conn.execute("INSERT INTO messages (id,session_id,role,content,tool_call_id,tool_name,timestamp,message_uid,tool_call_uid) VALUES (?,?,?,?,?,?,?,?,?)",
                         (row_id,"sess1","tool",content,"not-found","terminal",1700000000+row_id,uid,"reused-uid"))
        conn.commit();conn.close()
        orphans = [event for event in read_events(self.db) if "orphan-result" in event["tags"]]
        self.assertEqual(len(orphans), 2)
        self.assertEqual(len({event["id"] for event in orphans}), 2)
        self.assertEqual([event["result"] for event in orphans], ["first orphan", "second orphan"])

    def test_orphan_fallback_does_not_collide_with_pending_call(self):
        conn = sqlite3.connect(self.db)
        for column in ("message_uid", "tool_call_uids", "tool_call_uid"):
            conn.execute(f"ALTER TABLE messages ADD COLUMN {column} TEXT")
        conn.execute("UPDATE messages SET tool_call_uids=? WHERE id=1",
                     (json.dumps({"call_1":"same:orphan:4"}),))
        conn.execute("UPDATE messages SET id=5,tool_call_uid=?,content=? WHERE id=2",
                     ("same:orphan:4","real call result"))
        for row_id in (3, 4):
            conn.execute("INSERT INTO messages (id,session_id,role,content,tool_call_id,tool_name,timestamp,message_uid,tool_call_uid) VALUES (?,?,?,?,?,?,?,?,?)",
                         (row_id,"sess1","tool",f"orphan {row_id}","missing","terminal",1700000000+row_id,"same","unknown"))
        conn.commit();conn.close()
        events = read_events(self.db)
        self.assertEqual(len(events), 3)
        self.assertEqual(len({event["id"] for event in events}), 3)
        call = next(event for event in events if event["id"] == "sess1:same:orphan:4")
        self.assertEqual(call["result"], "real call result")
        self.assertEqual(len([event for event in events if "orphan-result" in event["tags"]]), 2)


if __name__ == "__main__":
    unittest.main()
