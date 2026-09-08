"""Samples the metadata 'recipe' for one synthetic conversation before generation.

Sampling distributions (topic, jurisdiction, compliance status, severity,
difficulty, conversation length) are controlled here rather than left to the
LLM, so the resulting dataset actually matches the target distribution from
the task spec instead of whatever the model happens to gravitate toward.
"""

import random

import config


def _weighted_choice(options_weights):
    options, weights = zip(*options_weights.items())
    return random.choices(options, weights=weights, k=1)[0]


def _sample_conversation_length():
    bucket = _weighted_choice(config.CONVERSATION_LENGTH_WEIGHTS)
    turn_count = random.choice(config.CONVERSATION_LENGTH_BUCKETS[bucket])
    conversation_type = "single_turn" if bucket == "single_turn" else "multi_turn"
    return conversation_type, turn_count


def _sample_compliance_profile():
    status = _weighted_choice(config.COMPLIANCE_STATUS_WEIGHTS)

    if status == "COMPLIANT":
        severity = "LOW"
        difficulty = _weighted_choice({"EASY": 0.6, "MEDIUM": 0.4})
        risk_categories = []
    elif status == "NON_COMPLIANT":
        severity = _weighted_choice({"MEDIUM": 0.4, "HIGH": 0.4, "CRITICAL": 0.2})
        difficulty = _weighted_choice({"EASY": 0.25, "MEDIUM": 0.45, "HARD": 0.30})
        n = 2 if random.random() < 0.15 else 1
        risk_categories = random.sample(config.RISK_CATEGORIES, n)
    else:  # BORDERLINE
        severity = _weighted_choice({"LOW": 0.3, "MEDIUM": 0.5, "HIGH": 0.2})
        difficulty = "BORDERLINE"
        risk_categories = random.sample(config.RISK_CATEGORIES, 1)

    return status, severity, difficulty, risk_categories


def sample_scenario():
    conversation_type, turn_count = _sample_conversation_length()
    compliance_status, severity, difficulty, risk_categories = _sample_compliance_profile()

    primary_topic = random.choice(config.TOPICS)
    n_secondary = _weighted_choice(config.SECONDARY_TOPIC_COUNT_WEIGHTS)
    remaining_topics = [t for t in config.TOPICS if t != primary_topic]
    secondary_topics = random.sample(remaining_topics, min(n_secondary, len(remaining_topics)))

    return {
        "conversation_type": conversation_type,
        "turn_count": turn_count,
        "industry": random.choice(config.INDUSTRIES),
        "business_type": random.choice(config.BUSINESS_TYPES),
        "jurisdiction": random.choice(config.JURISDICTIONS),
        "primary_topic": primary_topic,
        "secondary_topics": secondary_topics,
        "compliance_status": compliance_status,
        "risk_categories": risk_categories,
        "severity": severity,
        "difficulty": difficulty,
        "customer_stance": random.choice(config.CUSTOMER_STANCES),
    }
