"""Produce an offline, self-contained report from already-classified events."""

import json
import os
import tempfile
from pathlib import Path

from .privacy import redact_value

ASSETS = Path(__file__).parent / "assets"


def render_report(events, output):
    """Write one static HTML file; never put raw database content in markup."""
    output = Path(output).expanduser()
    safe = redact_value(events)
    data = json.dumps({"version": 1, "events": safe}, ensure_ascii=False, separators=(",", ":"))
    data = (data.replace("&", "\\u0026").replace("<", "\\u003c")
            .replace(">", "\\u003e").replace("\u2028", "\\u2028")
            .replace("\u2029", "\\u2029"))
    css = (ASSETS / "style.css").read_text(encoding="utf-8")
    logic = (ASSETS / "logic.js").read_text(encoding="utf-8")
    app = (ASSETS / "app.js").read_text(encoding="utf-8")
    page = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; connect-src 'none'; base-uri 'none'; form-action 'none'">
<title>Hermes Audit · Local trace</title><style>{css}</style></head><body>
<div class="shell">
  <header class="topbar"><div class="brand"><span class="mark">H/</span><span>HERMES AUDIT</span><small>OFFLINE TRACE</small></div>
    <div class="top-actions"><span id="report-meta"></span><button id="export-annotations" type="button">Export tags</button><label class="import-button" for="import-annotations">Import tags</label><input type="file" id="import-annotations" accept="application/json,.json" hidden></div>
  </header>
  <aside class="sidebar" aria-label="Filters">
    <div class="sidebar-head"><span>INSPECT</span><span class="quiet">01 / FILTERS</span></div>
    <label for="query">Search</label><input id="query" type="search" placeholder="Keywords across logs…" autocomplete="off">
    <label for="session-filter">Session</label><select id="session-filter"><option value="">All sessions</option></select>
    <label for="severity-filter">Severity</label><select id="severity-filter"><option value="">All severities</option></select>
    <label for="tag-filter">Tag</label><select id="tag-filter"><option value="">All tags</option></select>
    <label for="tool-filter">Tool</label><select id="tool-filter"><option value="">All tools</option></select>
    <label for="kind-filter">Record type</label><select id="kind-filter"><option value="">All records</option><option value="tool">Tool calls</option><option value="message">Messages</option></select>
    <label class="checkbox"><input type="checkbox" id="only-failures"> Failures only</label>
    <button id="clear-filters" type="button">Reset filters</button>
    <div class="sidebar-note"><b>Review aid, not a safety verdict.</b><p>Rules flag patterns in recorded actions. Unrecognized tools need inspection; absence of a flag is not proof of safety.</p><p>Redaction is best-effort. This file can still hold private conversation data.</p></div>
  </aside>
  <main class="workspace"><div class="workspace-head"><div><div class="eyebrow">LOCAL / READ-ONLY SOURCE</div><h1>Action timeline</h1><p id="report-description">Search, filter, inspect, and annotate recorded activity.</p></div>
  <div class="summary" id="summary"></div></div>
  <div class="list-bar"><strong id="visible-count">0 records</strong><div><label for="sort-order">Order</label><select id="sort-order"><option value="newest">Newest first</option><option value="oldest">Oldest first</option><option value="severity">Highest severity</option></select></div></div>
  <div id="events" aria-live="polite"></div><button id="load-more" class="load-more" type="button" hidden>Load more</button><p id="storage-warning" role="status" hidden></p></main>
</div>
<script id="report-data" type="application/json">{data}</script><script>{logic}</script><script>{app}</script>
</body></html>'''
    output.parent.mkdir(parents=True, exist_ok=True)
    staged = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=output.parent,
                                         prefix=".audit-", suffix=".tmp", delete=False) as handle:
            staged = Path(handle.name)
            os.chmod(staged, 0o600)
            handle.write(page)
        os.replace(staged, output)
    finally:
        if staged is not None:
            staged.unlink(missing_ok=True)
    return output
