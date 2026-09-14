"""Shared utilities: LLM JSON extraction and FAG record schema validation."""

import json
import os
import re

import config
from policy_categories import derive_policy_categories, expected_breach, unexplained_breach

VALID_SEVERITIES     = {"MEDIUM", "HIGH", "CRITICAL"}
VALID_DIFFICULTIES   = {"EASY", "MEDIUM", "HARD"}
VALID_ADVICE_TIERS   = set(config.ADVICE_TIERS)
VALID_PRODUCT_SCOPES = {"corps_act", "non_corps_act"}

REQUIRED_LLM_FIELDS = [
    "customer_intent", "messages", "problematic_turns",
    "problematic_spans", "reasoning_summary", "expected_ai_behavior",
]

_BOOL_FIELDS = ["financial_advice_breach", "is_corps_question",
                "denial_present", "contestable"]


def format_conversation_id(index):
    return f"SYN-FAG-{index:06d}"


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


def validate_conversation(record):
    """Validate an assembled FAG record. Returns (is_valid, list_of_errors)."""
    errors = []

    for field in REQUIRED_LLM_FIELDS:
        if field not in record:
            errors.append(f"missing field: {field}")
    if errors:
        return False, errors

    # ── scalar fields ────────────────────────────────────────────
    for field in _BOOL_FIELDS:
        if not isinstance(record.get(field), bool):
            errors.append(f"{field} must be a bool, got {record.get(field)!r}")

    breach = record.get("financial_advice_breach")
    tier   = record.get("advice_tier")
    scope  = record.get("product_scope")

    if tier not in VALID_ADVICE_TIERS:
        errors.append(f"invalid advice_tier: {tier}")
    if scope not in VALID_PRODUCT_SCOPES:
        errors.append(f"invalid product_scope: {scope}")
    if record.get("difficulty") not in VALID_DIFFICULTIES:
        errors.append(f"invalid difficulty: {record.get('difficulty')}")

    signals = record.get("signal_categories") or []
    for sig in signals:
        if sig not in config.SIGNAL_CATEGORIES:
            errors.append(f"invalid signal_category: {sig}")

    # The policy rule itself: the label must follow from tier + scope.
    if tier in VALID_ADVICE_TIERS and scope in VALID_PRODUCT_SCOPES:
        if breach != expected_breach(tier, scope):
            errors.append(
                f"label/policy mismatch: advice_tier={tier} on {scope} implies "
                f"breach={expected_breach(tier, scope)}, record says {breach}"
            )

    # Severity is meaningful only for a breach.
    severity = record.get("severity")
    if breach is True and severity not in VALID_SEVERITIES:
        errors.append(f"breach record needs a severity, got {severity!r}")
    if breach is False and severity is not None:
        errors.append(f"non-breach record must have severity=None, got {severity!r}")

    # A Corps question is by definition about a Corps Act product.
    if record.get("is_corps_question") and scope != "corps_act":
        errors.append("is_corps_question=True requires product_scope=corps_act")

    # ── messages ─────────────────────────────────────────────────
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

    # ── spans ────────────────────────────────────────────────────
    problematic_turns = record.get("problematic_turns", [])
    problematic_spans = record.get("problematic_spans", [])

    if breach is False:
        if problematic_turns or problematic_spans:
            errors.append("non-breach record must have empty problematic_turns/problematic_spans")
    elif not problematic_spans:
        errors.append("breach record must have at least one problematic_span")

    span_categories = set()
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
        category = span.get("category")
        if category not in config.SIGNAL_CATEGORIES:
            errors.append(f"invalid problematic_span category: {category}")
        elif category not in signals:
            errors.append(f"span category {category} is not in the record's signal_categories")
        span_categories.add(category)

    # Every declared signal must actually be evidenced by a span.
    if breach is True:
        for sig in signals:
            if sig not in span_categories:
                errors.append(f"signal_category {sig} has no annotated span")

    for turn_no in problematic_turns:
        if turn_no not in turns_by_number:
            errors.append(f"problematic_turns references missing turn {turn_no}")

    # ── derived policy categories ────────────────────────────────
    if "policy_categories" in record:
        if record["policy_categories"] != derive_policy_categories(record):
            errors.append("policy_categories do not match derivation from signals + context")

    if unexplained_breach(record):
        errors.append("breach is not explained by any production policy category")

    return len(errors) == 0, errors
