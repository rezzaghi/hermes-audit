# Hermes Audit

A local, read-only audit viewer for Hermes Agent sessions. It reads Hermes's `state.db` and generates **one self-contained HTML file**: no server, CDN, account, or runtime dependencies. Search the recorded messages and tool calls; filter by severity, tool, tag, session, type, or failure; inspect arguments/results and why an action was flagged.

![No live data in repository](https://img.shields.io/badge/data-local%20only-617568)

## Quick start

Requires Python 3.10+ and a Hermes installation with `state.db` (modern Hermes). From the cloned repository:

```bash
python -m hermes_audit --out audit-report.html
```

Open `audit-report.html` in a browser. The default database is `$HERMES_HOME/state.db` if set, otherwise `~/.hermes/state.db`. You can also install the command:

```bash
python -m pip install -e .
hermes-audit --out audit-report.html
```

### Useful options

```bash
# Another Hermes profile or machine:
python -m hermes_audit --db /path/to/state.db --out audit-report.html

# One session, optionally including its child/delegated/compression sessions:
python -m hermes_audit --session SESSION_ID --lineage --out investigation.html

# Share a focused example: only high/critical tool actions, no chat messages:
python -m hermes_audit --min-severity high --out high-risk.html

python -m hermes_audit --help
```

The source database is opened **read-only**; the tool does not change Hermes or require a login. Running it again makes a fresh snapshot. It does not live-refresh an already-open report.

## What the report does

- Pairs tool calls with recorded results and retains user/assistant messages for context. An unmatched tool result remains visible.
- Applies **explainable heuristic** labels: `critical`, `high`, `medium`, `low`, and `info` (conversation context). Examples: a credential-file reference or destructive shell command is critical; an external send/push or browser click is high; a local edit or opaque code execution is medium; a straightforward search is low. An unknown tool defaults to review, not "safe."
- Lets you search across tool arguments, results, messages, reasons, and personal notes. Filters combine, and sorting supports time or severity. Long reports load records in batches.
- Lets you add tags, notes, or an override severity to any record. These are stored in your browser's local storage, **not** Hermes's database; **Export tags / Import tags** moves them between browsers or machines. If browser storage is blocked on `file://`, export before closing the page.
- Includes a best-effort secret scrubber and escapes all transcript text so an HTML/script string from a tool result cannot run as page code. The report has a restrictive Content Security Policy and makes no network requests.

## Privacy and limitations

**Do not push generated reports, databases, or exported annotations to GitHub.** They can contain private messages, paths, and tool output. `.gitignore` blocks generated HTML and common database filenames, but review `git status` before pushing. Generated HTML files are written with owner-only permissions (`0600`). Redaction covers familiar key formats, authorization headers, and common token/password fields, including JSON-encoded tool results; **it cannot recognize every secret or personal detail**. Review the HTML before sharing it.

Classification is retrospective and rule-based. It is **not a security boundary**, an approval system, or a verdict that an action was harmful. A failed dangerous action remains labeled by the action attempted. Some wrapper tools execute several steps in one call; the report shows the recorded wrapper arguments/results, not each internal browser network request. System prompts and provider reasoning fields are deliberately omitted.

Default report scope is all sessions in the chosen database. `--session` filters to one; `--lineage` includes descendants, **not ancestors**. A session split from an earlier parent may require exporting the parent instead.

## Development

Python runtime uses the standard library. Node and Playwright are **test-only** dependencies.

```bash
npm ci
npx playwright install chromium
npm test
```

The suite exercises SQLite ingestion, failure pairing, severity rules, redaction, static HTML safety, keyword/tag filtering, browser storage, and real Chromium rendering. Browser fixtures are synthetic and clearly labeled; no real Hermes conversation is checked into this repository.

## License

MIT. The Git repository is local until you choose to publish it.
