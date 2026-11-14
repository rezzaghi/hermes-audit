"""Read Hermes's SQLite sessions without changing the source database."""

import json
import sqlite3
from collections import defaultdict, deque
from pathlib import Path
from .classify import classify_event, _failed_result


def _decode_json(value):
    if not value:
        return None
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return None


def _unique_id(base, disambiguator, seen):
    candidate = base
    if candidate in seen:
        candidate = f"{base}:{disambiguator}"
    counter = 1
    while candidate in seen:
        candidate = f"{base}:{disambiguator}:{counter}"
        counter += 1
    seen.add(candidate)
    return candidate


def read_events(db_path, session_id=None, include_lineage=False):
    db_path = Path(db_path).expanduser().resolve()
    if not db_path.is_file():
        raise FileNotFoundError(f"Hermes database not found: {db_path}")
    conn = sqlite3.connect(db_path.as_uri() + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        sessions = conn.execute("SELECT id, title, source, parent_session_id FROM sessions").fetchall()
        if session_id and not any(s["id"] == session_id for s in sessions):
            raise ValueError(f"Session not found: {session_id}")
        if session_id:
            selected = {session_id}
            if include_lineage:
                while True:
                    children = {s["id"] for s in sessions if s["parent_session_id"] in selected}
                    if children <= selected:
                        break
                    selected.update(children)
            sessions = [s for s in sessions if s["id"] in selected]
        events = []
        by_uid = defaultdict(deque)
        by_provider = defaultdict(deque)
        paired = set()
        seen_ids = set()
        columns = {column["name"] for column in conn.execute("PRAGMA table_info(messages)")}
        optional = ("message_uid", "tool_call_uids", "tool_call_uid")
        extra = ", ".join(column if column in columns else f"NULL AS {column}" for column in optional)
        for session in sessions:
            rows = conn.execute(
                "SELECT id, role, content, tool_call_id, tool_calls, tool_name, timestamp, " + extra + " "
                "FROM messages WHERE session_id = ? ORDER BY id", (session["id"],)
            )
            for row in rows:
                if row["role"] in {"user", "assistant"} and row["content"]:
                    events.append({
                        "id": _unique_id(f"{session['id']}:{row['message_uid'] or row['id']}:message", row["id"], seen_ids), "kind": "message",
                        "role": row["role"], "session_id": session["id"],
                        "session_title": session["title"] or session["id"],
                        "source": session["source"] or "unknown", "timestamp": row["timestamp"],
                        "tool": "message", "arguments": {}, "result": row["content"],
                        "failed": False, "tags": [row["role"]],
                    })
                if row["role"] == "assistant":
                    calls = _decode_json(row["tool_calls"])
                    if not isinstance(calls, list):
                        continue
                    identities = _decode_json(row["tool_call_uids"])
                    for index, call in enumerate(calls):
                        if not isinstance(call, dict):
                            continue
                        fn = call.get("function") or {}
                        if not isinstance(fn, dict):
                            fn = {}
                        raw = fn.get("arguments", call.get("arguments", {}))
                        try:
                            arguments = json.loads(raw) if isinstance(raw, str) else raw
                        except ValueError:
                            arguments = raw
                        uid = None
                        if isinstance(identities, dict):
                            uid = identities.get(call.get("id"))
                        elif isinstance(identities, list) and index < len(identities):
                            uid = identities[index]
                        if not isinstance(uid, str) or not uid:
                            uid = None
                        identity = uid or f"{row['message_uid'] or row['id']}:{index}"
                        event_id = _unique_id(f"{session['id']}:{identity}", f"{row['message_uid'] or row['id']}:{index}", seen_ids)
                        event = {
                            "id": event_id,
                            "kind": "tool", "role": "assistant",
                            "session_id": session["id"],
                            "session_title": session["title"] or session["id"],
                            "source": session["source"] or "unknown",
                            "timestamp": row["timestamp"],
                            "tool": fn.get("name") or call.get("name") or "unknown",
                            "arguments": arguments,
                            "result": "",
                            "failed": False,
                            "tags": [],
                        }
                        events.append(event)
                        if uid:
                            by_uid[(session["id"], uid)].append(event)
                        if call.get("id"):
                            by_provider[(session["id"], call["id"])].append(event)
                elif row["role"] == "tool":
                    if row["tool_call_uid"]:
                        pending = by_uid[(session["id"], row["tool_call_uid"])]
                        while pending and pending[0]["id"] in paired:
                            pending.popleft()
                        event = pending.popleft() if pending else None
                    else:
                        pending = by_provider[(session["id"], row["tool_call_id"])]
                        while pending and pending[0]["id"] in paired:
                            pending.popleft()
                        event = pending.popleft() if pending else None
                    if event is not None and event["id"] in paired:
                        event = None
                    if event is None:
                        orphan_id = _unique_id(f"{session['id']}:{row['message_uid'] or row['id']}:orphan", row["id"], seen_ids)
                        event = {
                            "id": orphan_id, "kind": "tool",
                            "role": "tool", "session_id": session["id"],
                            "session_title": session["title"] or session["id"],
                            "source": session["source"] or "unknown", "timestamp": row["timestamp"],
                            "tool": row["tool_name"] or "unknown", "arguments": {}, "result": "",
                            "failed": False, "tags": ["orphan-result"],
                        }
                        events.append(event)
                    paired.add(event["id"])
                    event["result"] = row["content"] or ""
                    event["failed"] = _failed_result(event["result"])
        for event in events:
            if event["kind"] == "message":
                event["severity"] = "info"
                event["reasons"] = ["Conversation context, not a tool action."]
                continue
            labels = classify_event(event["tool"], event["arguments"], event["result"])
            event["severity"] = labels["severity"]
            event["reasons"] = labels["reasons"]
            event["tags"] = sorted(set(event["tags"] + labels["tags"]))
        events.sort(key=lambda e: (e["timestamp"] or 0, e["id"]))
        return events
    finally:
        conn.close()
