"""Explainable retrospective heuristics, NOT an execution-time safety gate."""

import json
import re

LEVELS = ("info", "low", "medium", "high", "critical")
CREDENTIAL_PATH = re.compile(
    r"(?:\.hermes[/\\]\.env|[/\\]\.ssh[/\\]|[/\\]auth\.json\b|"
    r"[/\\](?:credentials|secrets?|id_rsa|id_ed25519)(?:[/\\\s'\"]|$)|"
    r"\b(?:private[_-]?key|api[_-]?key|password)\s*[:=])", re.I
)
DESTRUCTIVE = re.compile(
    r"\b(?:rm\s+(?:-[a-z]*[rf][a-z]*\s+)+|mkfs(?:\.[\w]+)?\s|"
    r"dd\s+if=|git\s+(?:reset\s+--hard|clean\s+-[a-z]*f|push\s+--force)|"
    r"(?:DROP\s+(?:TABLE|DATABASE))\b)", re.I
)
REMOTE_CODE = re.compile(r"\b(?:curl|wget)\b[^\n|]*\|\s*(?:ba)?sh\b", re.I)
OUTBOUND = re.compile(r"\b(?:git\s+push|curl\b[^\n]*(?:-X\s*(?:POST|PUT|DELETE)|--data\b)|"
                      r"\b(?:POST|PUT|DELETE)\s+https?://)", re.I)
PYTHON_OUTBOUND = re.compile(r"\b(?:requests|httpx|aiohttp)\.(?:post|put|patch|delete)\s*\(", re.I)
INTERACTION = re.compile(r"\b(?:click_at_xy|fill_input|\.click\s*\(|\.submit\s*\()", re.I)


def _failed_result(result):
    try:
        value = json.loads(result)
    except (ValueError, TypeError):
        return bool(re.search(r"(?im)^(?:Error\b|Fatal\b|Traceback \(most recent call last\))|\bCONNECTION_REQUIRED\b",
                              str(result)))
    return isinstance(value, dict) and (
        value.get("success") is False or value.get("is_error") is True
        or (isinstance(value.get("exit_code"), int) and value["exit_code"] != 0)
        or bool(value.get("error"))
        or (isinstance(value.get("status"), str) and value["status"].lower() in {"error", "failed"})
    )


def classify_event(tool, arguments, result=""):
    """Return the most severe matching label, evidence and independent tags."""
    name = str(tool).lower().split(".")[-1]
    text = arguments if isinstance(arguments, str) else json.dumps(arguments, ensure_ascii=False, default=str)
    tags, reasons = set(), []
    level = "low"

    def add(severity, tag, reason):
        nonlocal level
        if LEVELS.index(severity) > LEVELS.index(level):
            level = severity
        tags.add(tag)
        reasons.append(reason)

    if name in {"read_file", "search_files", "web_search", "web_extract", "open", "find"}:
        tags.add("search" if name in {"web_search", "web_extract"} else "read")
    elif name in {"write_file", "patch"}:
        add("medium", "file-write", "Local file content may be changed.")
    elif name in {"terminal", "execute_code"}:
        add("medium", "opaque-code" if name == "execute_code" else "shell",
            "Code or a shell command can have side effects; review its arguments.")
    elif name == "browser_exec":
        add("medium", "browser", "Browser automation can have side effects.")
    elif name in {"tool_call", "delegate_task"}:
        add("medium", "needs-review", "Nested/delegated actions require review of child calls.")
    elif name in {"browser_vault", "manage_connections"}:
        add("high", "credential-access", "Credential or account authorization capability was invoked.")
    elif name in {"memory", "skill_manage", "cronjob_manage"}:
        add("medium", "configuration-write", "Persistent agent state may be modified.")
    elif name not in {"calculator", "time", "weather", "finance", "sports", "page_info"}:
        add("medium", "needs-review", "Unrecognized tool; effect cannot be inferred safely.")

    if name in {"read_file", "search_files", "write_file", "patch", "terminal", "execute_code", "browser_exec", "tool_call"} and CREDENTIAL_PATH.search(text):
        add("critical", "credential-access", "Action references a credential or private-key location.")
    if name == "tool_call" and re.search(r'"name"\s*:\s*"browser_vault"', text):
        add("critical", "credential-access", "Nested call requests credential-vault access.")
    if name in {"terminal", "execute_code", "tool_call", "browser_exec"}:
        if DESTRUCTIVE.search(text):
            add("critical", "destructive", "Command resembles a destructive operation.")
        if REMOTE_CODE.search(text):
            add("critical", "remote-code", "Downloads code and pipes it to a shell.")
        if OUTBOUND.search(text):
            add("high", "external-write", "Command resembles an outbound write or push.")
        if PYTHON_OUTBOUND.search(text):
            add("high", "external-write", "Code calls an outbound HTTP write method.")
    if name == "browser_exec" and INTERACTION.search(text):
        add("high", "interaction", "Browser code performs an interaction; inspect its target and result.")
    if re.search(r"(?:^|[_-])(?:send|post|publish|create|update|delete|upload|transfer)(?:$|[_-])", name):
        add("high", "external-write", "Tool name suggests an externally visible change.")
    if name in {"execute_code", "browser_exec"} and re.search(r"\b(?:web_search|search_query|search_query=)\b", text):
        tags.add("search")
    if _failed_result(result):
        tags.add("failure")
        reasons.append("Tool result reports failure; risk label describes the attempted action.")
    if not reasons:
        reasons.append("Read-only or low-risk tool pattern; classification is heuristic.")
    return {"severity": level, "tags": sorted(tags), "reasons": reasons}
