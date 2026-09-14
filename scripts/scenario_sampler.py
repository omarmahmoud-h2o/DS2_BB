"""Samples the metadata 'recipe' for one synthetic FAG conversation.

Distributions are fixed in code rather than left to the LLM so the corpus
matches an intended design instead of whatever the model gravitates toward.

The label is binary: `financial_advice_breach`. The advice tier is a
generation control that determines it, per VRM_Compliance_Definitions_OLD.md:

    FACTUAL_INFORMATION           -> no breach
    GENERAL_ADVICE on corps_act   -> breach
    GENERAL_ADVICE on non_corps   -> NO breach (permitted, monitored)
    PERSONAL_ADVICE               -> breach, always

Permitted general advice is deliberately annotated with its signals but no
spans: it is a hard negative in which advisory language is present and the
correct label is still "no breach", which is what stops a detector collapsing
into "recommendation words => breach".
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


def _sample_signals(advice_tier):
    """Signals the response exhibits, consistent with its advice tier."""
    if advice_tier == "PERSONAL_ADVICE":
        # Personal advice must reference the customer's own circumstances.
        anchor = random.choice(config.PERSONAL_ADVICE_SIGNALS)
        pool = [s for s in config.GENERAL_ADVICE_SIGNALS + config.PERSONAL_ADVICE_SIGNALS
                if s != anchor]
        signals = [anchor] + random.sample(pool, 1 if random.random() < 0.45 else 0)
    elif advice_tier == "GENERAL_ADVICE":
        n = 2 if random.random() < 0.35 else 1
        signals = random.sample(config.GENERAL_ADVICE_SIGNALS, n)
    else:  # FACTUAL_INFORMATION
        return []

    if random.random() < config.DOMAIN_SIGNAL_RATE:
        signals.append(random.choice(config.DOMAIN_ADVICE_SIGNALS))
    return signals


def _sample_advice_profile(product_scope):
    """Draw (breach, advice_tier, signals, severity) as one coherent recipe."""
    breach = random.random() < config.BREACH_RATE
    corps = product_scope == "corps_act"

    if breach:
        # On Corps Act products general advice is already a breach; off them,
        # only personal advice is.
        if corps:
            advice_tier = _weighted_choice({"GENERAL_ADVICE": 0.45, "PERSONAL_ADVICE": 0.55})
        else:
            advice_tier = "PERSONAL_ADVICE"
        severity = _weighted_choice(
            config.SEVERITY_WEIGHTS_PERSONAL_ADVICE if advice_tier == "PERSONAL_ADVICE"
            else config.SEVERITY_WEIGHTS_GENERAL_ADVICE
        )
    else:
        # Off Corps Act products, permitted general advice is a valid
        # non-breach outcome and makes the most useful hard negative.
        if corps:
            advice_tier = "FACTUAL_INFORMATION"
        else:
            advice_tier = _weighted_choice(
                {"FACTUAL_INFORMATION": 0.7, "GENERAL_ADVICE": 0.3}
            )
        severity = None  # severity is meaningless without a breach

    return breach, advice_tier, _sample_signals(advice_tier), severity


def _sample_denial(is_corps_question, breach):
    """Whether the assistant issued the decline a Corps question requires."""
    if not is_corps_question:
        return False          # no denial required by policy
    if not breach:
        return True           # a compliant answer to a Corps question declines
    # A breaching answer usually omits the decline outright; sometimes it
    # declines and then advises anyway.
    return random.random() >= config.NO_DENIAL_RATE


def sample_scenario():
    conversation_type, turn_count = _sample_conversation_length()

    product_scope = _weighted_choice(config.PRODUCT_SCOPE_WEIGHTS)
    topic_pool = (config.CORPS_ACT_PRODUCT_TOPICS if product_scope == "corps_act"
                  else config.NON_CORPS_ACT_TOPICS)
    primary_topic = random.choice(topic_pool)

    customer_stance = random.choice(config.CUSTOMER_STANCES)
    # A "Corps question" is an advice-seeking request about a Corps Act
    # product — the case where policy requires the assistant to decline.
    is_corps_question = (product_scope == "corps_act"
                         and customer_stance in config.ADVICE_SEEKING_STANCES)

    breach, advice_tier, signal_categories, severity = _sample_advice_profile(product_scope)

    n_secondary = _weighted_choice(config.SECONDARY_TOPIC_COUNT_WEIGHTS)
    remaining_topics = [t for t in config.TOPICS if t != primary_topic]
    secondary_topics = random.sample(remaining_topics, min(n_secondary, len(remaining_topics)))

    return {
        "conversation_type": conversation_type,
        "turn_count": turn_count,
        "industry": random.choice(config.INDUSTRIES),
        "business_type": random.choice(config.BUSINESS_TYPES),
        "jurisdiction": random.choice(config.JURISDICTIONS),
        # context facts — policy gating inputs, not wrongdoing
        "product_scope": product_scope,
        "is_corps_question": is_corps_question,
        "denial_present": _sample_denial(is_corps_question, breach),
        "primary_topic": primary_topic,
        "secondary_topics": secondary_topics,
        # the label
        "financial_advice_breach": breach,
        # metadata / diagnostics
        "advice_tier": advice_tier,
        "signal_categories": signal_categories,
        "severity": severity,
        "difficulty": _weighted_choice(
            config.DIFFICULTY_WEIGHTS_BREACH if breach
            else config.DIFFICULTY_WEIGHTS_NO_BREACH
        ),
        "contestable": random.random() < config.CONTESTABLE_RATE,
        "customer_stance": customer_stance,
    }
