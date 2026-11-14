"""Build a static local audit report from Hermes sessions."""

import argparse
import os
import sqlite3
from pathlib import Path

from .core import read_events
from .classify import LEVELS
from .report import render_report


def main(argv=None):
    home = Path(os.environ.get("HERMES_HOME") or Path.home() / ".hermes")
    parser = argparse.ArgumentParser(description="Generate an offline, searchable Hermes audit HTML file")
    parser.add_argument("--db", type=Path, default=home / "state.db", help="Hermes state.db (read-only)")
    parser.add_argument("--out", type=Path, default=Path("audit-report.html"), help="Output HTML file")
    parser.add_argument("--session", help="Limit to this Hermes session ID")
    parser.add_argument("--lineage", action="store_true", help="Include descendant/compression sessions")
    parser.add_argument("--min-severity", choices=LEVELS, help="Export only actions at or above this level")
    args = parser.parse_args(argv)
    if args.lineage and not args.session:
        parser.error("--lineage requires --session")
    if args.db.expanduser().resolve() == args.out.expanduser().resolve():
        parser.error("output cannot overwrite the source database")
    try:
        events = read_events(args.db, args.session, args.lineage)
        if args.min_severity:
            threshold = LEVELS.index(args.min_severity)
            events = [event for event in events if event["kind"] == "tool"
                      and LEVELS.index(event["severity"]) >= threshold]
        output = render_report(events, args.out)
    except (OSError, ValueError, sqlite3.Error) as exc:
        parser.exit(1, f"hermes-audit: {exc}\n")
    print(f"Wrote {len(events)} records to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
