"""LLM input/output sanitization and prompt injection detection."""
from __future__ import annotations

import re

# Patterns that indicate prompt injection attempts
_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?previous\s+(instructions|prompts)", re.IGNORECASE),
    re.compile(r"forget\s+(everything|all|your\s+instructions)", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+", re.IGNORECASE),
    re.compile(r"new\s+instructions?\s*:", re.IGNORECASE),
    re.compile(r"system\s*:\s*", re.IGNORECASE),
    re.compile(r"<\|(im_start|system|user|assistant)\|>", re.IGNORECASE),
    re.compile(r"```system", re.IGNORECASE),
    re.compile(r"\[INST\]", re.IGNORECASE),
    re.compile(r"disregard\s+(your|the|all)\s+", re.IGNORECASE),
]

# Dangerous content in LLM output
_OUTPUT_DANGER_PATTERNS = [
    re.compile(r"<script[^>]*>", re.IGNORECASE),
    re.compile(r"javascript\s*:", re.IGNORECASE),
    re.compile(r"on\w+\s*=\s*[\"']", re.IGNORECASE),
]

# Max input length to prevent token budget abuse
MAX_USER_INPUT_CHARS = 50_000


class SecurityError(Exception):
    pass


def sanitize_user_input(text: str, *, max_length: int = MAX_USER_INPUT_CHARS) -> str:
    if len(text) > max_length:
        raise SecurityError(f"Input exceeds maximum length ({len(text)} > {max_length})")
    return text


def detect_injection(text: str) -> list[str]:
    findings = []
    for pattern in _INJECTION_PATTERNS:
        m = pattern.search(text)
        if m:
            findings.append(m.group(0)[:80])
    return findings


def validate_llm_output(text: str) -> str:
    for pattern in _OUTPUT_DANGER_PATTERNS:
        if pattern.search(text):
            return pattern.sub("[REMOVED]", text)
    return text


def safe_json_parse(raw: str) -> dict | list | None:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r'^```\w*\n?', '', raw)
        raw = re.sub(r'\n?```$', '', raw)
        raw = raw.strip()

    import json
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Try to extract JSON from markdown code block
    m = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Try to find first { ... } or [ ... ]
    for opener, closer in [("{", "}"), ("[", "]")]:
        start = raw.find(opener)
        if start == -1:
            continue
        depth = 0
        for i in range(start, len(raw)):
            if raw[i] == opener:
                depth += 1
            elif raw[i] == closer:
                depth -= 1
            if depth == 0:
                try:
                    return json.loads(raw[start:i + 1])
                except json.JSONDecodeError:
                    break
    return None
