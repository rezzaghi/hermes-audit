"""Best-effort secret scrubbing before anything enters the HTML artifact."""

import json
import re

REDACTED = "[REDACTED]"
SENSITIVE_FIELD = re.compile(r"^(?:(?:x[_-]?)?api[_-]?key|client[_-]?secret|secret[_-]?key|access[_-]?token|refresh[_-]?token|token|secret|password|passwd|authorization|private[_-]?key|cookie)$", re.I)
PATTERNS = (
    (re.compile(r"(?i)\b(Bearer\s+)[A-Za-z0-9._~+/=-]{8,}"), r"\1" + REDACTED),
    (re.compile(r"(?i)(Authorization:\s*(?:Basic|Bearer)\s+)[^\s'\"]+"), r"\1" + REDACTED),
    (re.compile(r"(?i)(Cookie:\s*)[^\r\n'\"]+"), r"\1" + REDACTED),
    (re.compile(r"(?i)(\b(?:client[_-]?secret|x[_-]?api[_-]?key|secret[_-]?key)\s*[:=]\s*['\"]?)[^\s'\";,]+"), r"\1" + REDACTED),
    (re.compile(r"(?i)([?&](?:access_token|refresh_token|token|api_key|key|secret|password)=)[^&#\s]+"), r"\1" + REDACTED),
    (re.compile(r"(?i)(\b(?:API_KEY|ACCESS_TOKEN|REFRESH_TOKEN|PASSWORD|SECRET|AUTH_TOKEN)\s*[:=]\s*['\"]?)[^\s'\";,]+"), r"\1" + REDACTED),
    (re.compile(r"\b(?:sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16})\b"), REDACTED),
)


def redact_text(text):
    value = str(text)
    for pattern, replacement in PATTERNS:
        value = pattern.sub(replacement, value)
    return value


def redact_value(value):
    if isinstance(value, str):
        if value.lstrip().startswith(("{", "[")):
            try:
                decoded = json.loads(value)
            except (ValueError, TypeError):
                pass
            else:
                if isinstance(decoded, (dict, list)):
                    return json.dumps(redact_value(decoded), ensure_ascii=False)
        return redact_text(value)
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    if isinstance(value, dict):
        return {key: REDACTED if SENSITIVE_FIELD.fullmatch(str(key)) else redact_value(item)
                for key, item in value.items()}
    return value
