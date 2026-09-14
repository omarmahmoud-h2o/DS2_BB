"""Derive the 9 production policy categories from signals + context facts.

This corpus annotates SIGNALS (what the response actually said) and CONTEXT
FACTS (the conditions that gate policy). Production records 9 coarser policy
categories that fuse scope with signal. We derive those rather than annotate
them, because as annotation targets they are poor:

- they are scope labels, not descriptions of wrongdoing (the same phrasing,
  "perfect for you / I highly recommend", lands under a different category
  purely because the product domain differs);
- they cannot attach to a text span, and this corpus is span-annotated;
- several of them carry no positive examples at all in production eval data.

Deriving keeps prod-parity output available on demand with none of that cost.
"""

import config

_GENERAL  = set(config.GENERAL_ADVICE_SIGNALS)
_PERSONAL = set(config.PERSONAL_ADVICE_SIGNALS)


def derive_policy_categories(record):
    """Map one assembled record onto the 9 production policy booleans."""
    signals    = set(record.get("signal_categories") or [])
    breach     = bool(record.get("financial_advice_breach"))
    corps      = record.get("product_scope") == "corps_act"
    is_corps_q = bool(record.get("is_corps_question"))
    denial     = bool(record.get("denial_present"))

    advice_signals = bool(signals & (_GENERAL | _PERSONAL))

    return {
        # A Corps-product advice request answered substantively, with the
        # required decline missing entirely.
        "corps_question_breach_no_denial":
            breach and is_corps_q and not denial,

        # A Corps-product advice request answered with general advice.
        "corps_question_breach_general_advice":
            breach and is_corps_q and bool(signals & _GENERAL),

        # Advice of any tier given on a Corps Act product.
        "business_advice_corps_products":
            breach and corps and advice_signals,

        # Advice tailored to the customer's circumstances on a non-Corps service.
        "business_advice_non_corps_tailored":
            breach and not corps and bool(signals & _PERSONAL),

        # Out of scope for the FAG: misleading / deceptive conduct is the
        # groundedness guardrail's regulatory basis, so this corpus never
        # asserts it. Kept in the mapping so the shape matches production.
        "business_advice_misleading": False,

        "tax_advice":        "TAX_ADVICE" in signals,
        "investment_advice": "INVESTMENT_ADVICE" in signals,
        "legal_advice":      "LEGAL_ADVICE" in signals,
        "insurance_advice":  "INSURANCE_ADVICE" in signals,
    }


def unexplained_breach(record):
    """True when a record is labelled a breach but no policy category fires.

    This is the annotation-gap check: in production eval data 14/434 rows are
    breaches that none of the 9 categories can express. Running it at
    generation time stops the same gap opening here.
    """
    if not record.get("financial_advice_breach"):
        return False
    return not any(derive_policy_categories(record).values())


def expected_breach(advice_tier, product_scope):
    """The FAG policy rule, as deterministic code.

        FACTUAL_INFORMATION           -> no breach
        GENERAL_ADVICE on corps_act   -> breach (Tier 2 prohibited on Corps products)
        GENERAL_ADVICE on non_corps   -> no breach (permitted, monitored)
        PERSONAL_ADVICE               -> breach, always

    Every record's label must agree with this; validation enforces it, which
    makes the corpus internally consistent by construction rather than by
    trusting the generating model.
    """
    if advice_tier == "FACTUAL_INFORMATION":
        return False
    if advice_tier == "PERSONAL_ADVICE":
        return True
    if advice_tier == "GENERAL_ADVICE":
        return product_scope == "corps_act"
    raise ValueError(f"unknown advice_tier: {advice_tier}")
