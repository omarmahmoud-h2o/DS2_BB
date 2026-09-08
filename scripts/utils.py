"""Shared utilities: LLM JSON extraction and conversation schema validation."""

import json
import os
import re

VALID_COMPLIANCE_STATUSES = {"COMPLIANT", "NON_COMPLIANT", "BORDERLINE"}
VALID_SEVERITIES          = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
VALID_DIFFICULTIES        = {"EASY", "MEDIUM", "HARD", "BORDERLINE"}

REQUIRED_LLM_FIELDS = [
    "customer_intent", "messages", "problematic_turns",
    "problematic_spans", "reasoning_summary", "expected_ai_behavior",
]


def format_conversation_id(index):
    return f"SYN-BANK-{index:06d}"


def count_existing_lines(path):
    if not os.path.exists(path):
        return 0
    with open(path, encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())


def extract_json(response):
    """Pull a JSON object out of a raw LLM response, tolerating markdown fences."""
    if not response:
        return None
    text = response.strip()
    text = re.sub(r'^```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```$', '', text)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None


def validate_conversation(record, valid_risk_categories):
    """Validate an assembled conversation record against the expected schema.

    Returns (is_valid, list_of_error_strings).
    """
    errors = []

    for field in REQUIRED_LLM_FIELDS:
        if field not in record:
            errors.append(f"missing field: {field}")
    if errors:
        return False, errors

    if record.get("compliance_status") not in VALID_COMPLIANCE_STATUSES:
        errors.append(f"invalid compliance_status: {record.get('compliance_status')}")
    if record.get("severity") not in VALID_SEVERITIES:
        errors.append(f"invalid severity: {record.get('severity')}")
    if record.get("difficulty") not in VALID_DIFFICULTIES:
        errors.append(f"invalid difficulty: {record.get('difficulty')}")
    for cat in record.get("risk_categories", []):
        if cat not in valid_risk_categories:
            errors.append(f"invalid risk_category: {cat}")

    messages = record.get("messages", [])
    if not isinstance(messages, list) or not messages:
        errors.append("messages must be a non-empty list")
        return False, errors

    expected_role = "customer"
    turns_by_number = {}
    for i, msg in enumerate(messages, start=1):
        if not isinstance(msg, dict):
            errors.append(f"message {i} is not an object")
            continue
        if msg.get("turn") != i:
            errors.append(f"message {i} has turn={msg.get('turn')}, expected {i}")
        if msg.get("role") != expected_role:
            errors.append(f"message {i} has role={msg.get('role')}, expected {expected_role}")
        if not str(msg.get("content", "")).strip():
            errors.append(f"message {i} has empty content")
        turns_by_number[i] = msg
        expected_role = "assistant" if expected_role == "customer" else "customer"

    problematic_turns = record.get("problematic_turns", [])
    problematic_spans = record.get("problematic_spans", [])
    compliance_status = record.get("compliance_status")

    if compliance_status == "COMPLIANT":
        if problematic_turns or problematic_spans:
            errors.append("COMPLIANT record must have empty problematic_turns/problematic_spans")
    elif not problematic_spans:
        errors.append(f"{compliance_status} record must have at least one problematic_span")

    for span in problematic_spans:
        turn_no = span.get("turn")
        msg = turns_by_number.get(turn_no)
        if msg is None:
            errors.append(f"problematic_span references missing turn {turn_no}")
            continue
        if msg.get("role") != "assistant":
            errors.append(f"problematic_span turn {turn_no} is not an assistant turn")
        if span.get("text", "") not in msg.get("content", ""):
            errors.append(f"problematic_span text not found verbatim in turn {turn_no}")
        if span.get("category") not in valid_risk_categories:
            errors.append(f"invalid problematic_span category: {span.get('category')}")

    for turn_no in problematic_turns:
        if turn_no not in turns_by_number:
            errors.append(f"problematic_turns references missing turn {turn_no}")

    return len(errors) == 0, errors
