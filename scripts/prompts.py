"""Prompt construction for synthetic Financial Advice Guardrail conversations.

Scope is one guardrail. The FAG answers a single question — does this response
recommend or opine on a financial product? — and emits one boolean. Compliance
(FAG AND groundedness) is the layer above and is not modelled here.

Policy source of truth: VRM_Compliance_Definitions_OLD.md.
"""

import json

import config

SYSTEM_PROMPT = """You are an expert synthetic-data generator specializing in Australian business \
banking and financial-advice policy under the Corporations Act 2001 (s766B) and ASIC guidance \
RG244/RG255.

Generate a realistic synthetic conversation between:
- Customer: an Australian business banking customer, business owner, finance employee, accountant, \
or authorized representative.
- VRM Assistant: the bank's AI business-banking assistant, which may provide ONLY objective, factual \
information about products and services — never a recommendation, opinion, or statement that could \
influence the customer's decision about a financial product.

The conversation trains a detector that decides, for each assistant response, whether it breaches \
financial advice policy.

The three-tier advice hierarchy:
- Tier 1 — FACTUAL_INFORMATION: objective product features, rates, fees, eligibility, availability. \
No opinion, no recommendation. Allowed for all products.
- Tier 2 — GENERAL_ADVICE: statements about product suitability that do NOT reference the customer's \
personal circumstances. A BREACH for Corps Act products (Business Transaction Account, Business \
Investment Account, Neo Business Card); PERMITTED for other banking services.
- Tier 3 — PERSONAL_ADVICE: takes the customer's specific circumstances into account to suggest a \
product decision. A breach in all cases.

The critical boundary: factual information about a product is allowed; an opinion about whether the \
customer should choose it is not.

Evaluate the customer and the assistant separately. A customer asking "which account should I get?" \
does not itself create a breach — the label below describes the ASSISTANT's response only.

Realism requirements:
- Customers sound authentic: informal language, typos, abbreviations, business terminology, \
imprecise wording, frustration, urgency. They naturally ask for recommendations and opinions.
- Neither party names RG244/RG255/s766B or uses words like "compliant" or "breach". The policy is \
invisible to both speakers.
- Do not make breaches blatant, and do not make clean responses stiff walls of disclaimer. A breach \
is often a single phrase — "perfect for your situation", "the better option", "you'd earn more" — \
inside an otherwise accurate, genuinely helpful answer.
- In multi-turn conversations maintain context, don't restate prior turns, and let any drift into \
advice emerge gradually as the customer reveals more.

Safety constraint: keep all names, businesses, account numbers and identifiers fictional. Product \
features, rates and fees must be plausible but invented — do not state real CBA rates, and do not \
invent specific laws or numeric regulatory thresholds."""

OUTPUT_SCHEMA_HINT = {
    "customer_intent": "one sentence describing what the customer is trying to accomplish",
    "messages": [
        {"turn": 1, "role": "customer", "content": "..."},
        {"turn": 2, "role": "assistant", "content": "..."},
    ],
    "problematic_turns": "turn numbers containing a breach (empty when there is no breach)",
    "problematic_spans": [
        {
            "turn": 2,
            "text": "exact verbatim substring copied from that turn's assistant content",
            "category": "one of the required signal categories",
            "reason": "why this span crosses from factual information into advice",
        }
    ],
    "reasoning_summary": "1-3 sentences explaining the label in terms of the advice tiers",
    "expected_ai_behavior": "1-2 sentences on what the assistant should have done / did correctly",
}


def _signal_guidance(signal_categories):
    if not signal_categories:
        return ("None — the assistant's responses must not exhibit any advice signal.")
    return "\n".join(f"- {s}: {config.SIGNAL_DESCRIPTIONS[s]}" for s in signal_categories)


def _response_requirements(scenario):
    """Explicit, scenario-specific instructions for what the assistant must do."""
    reqs = []
    breach = scenario["financial_advice_breach"]
    tier = scenario["advice_tier"]
    corps_q = scenario["is_corps_question"]
    denial = scenario["denial_present"]

    if breach:
        reqs.append(f"The assistant's response MUST cross into {tier}.")
        reqs.append("Every signal category listed above must appear in at least one annotated span.")
        if corps_q and not denial:
            reqs.append(
                "The customer is asking for advice on a Corps Act product, which policy requires the "
                "assistant to decline. It does NOT decline — it answers the request substantively. "
                "No disclaimer, no redirect to a banker."
            )
        elif corps_q and denial:
            reqs.append(
                "The customer is asking for advice on a Corps Act product. The assistant offers a "
                "brief disclaimer or redirect, then goes on to give the advice anyway — the decline "
                "is present but hollow."
            )
    else:
        reqs.append(f"The assistant must stay within {tier} in every response.")
        if corps_q:
            reqs.append(
                "The customer is asking for advice on a Corps Act product. The assistant must "
                "decline to recommend and point to a banker or licensed adviser, while still being "
                "genuinely useful with factual product information."
            )
        if scenario["signal_categories"]:
            reqs.append(
                "The assistant may make general statements about how the service suits certain "
                "situations — permitted here because the topic is NOT a Corps Act product — but it "
                "must never reference this customer's own circumstances, needs or numbers."
            )
        reqs.append("problematic_turns and problematic_spans MUST both be empty arrays.")

    if scenario["contestable"]:
        reqs.append(
            "Write the key passage so a reasonable reviewer could argue the label either way, and "
            "make reasoning_summary explain precisely where that ambiguity sits."
        )
    return "\n".join(f"- {r}" for r in reqs)


def build_conversation_prompt(scenario):
    turn_count = scenario["turn_count"]
    breach = scenario["financial_advice_breach"]

    return f"""{SYSTEM_PROMPT}

## Fixed scenario parameters (do not change these; write the conversation to match them)

- conversation_type: {scenario['conversation_type']}
- total_messages_required: {turn_count} (alternate customer/assistant starting with the customer, turns numbered 1..{turn_count})
- industry: {scenario['industry']}
- business_type: {scenario['business_type']}
- jurisdiction: {scenario['jurisdiction']}
- product_scope: {scenario['product_scope']}
- primary_topic: {scenario['primary_topic']}
- secondary_topics: {json.dumps(scenario['secondary_topics'])}
- customer_stance: {scenario['customer_stance']}
- is_corps_question: {json.dumps(scenario['is_corps_question'])} (customer is seeking advice on a Corps Act product)
- financial_advice_breach (the label, fixed): {json.dumps(breach)}
- advice_tier (fixed): {scenario['advice_tier']} — {config.ADVICE_TIER_DESCRIPTIONS[scenario['advice_tier']]}
- severity (fixed): {scenario['severity']}
- difficulty (fixed): {scenario['difficulty']}
- required signal categories (fixed): {json.dumps(scenario['signal_categories'])}

Signal definitions for this scenario:
{_signal_guidance(scenario['signal_categories'])}

## What the assistant must do

{_response_requirements(scenario)}

## Span annotation rules

- Each problematic_spans entry's "text" must be an EXACT verbatim substring of the assistant's \
"content" for the turn it cites — do not paraphrase, truncate with ellipses, or summarize.
- Annotate only the specific sentence(s) that cross the line, never the whole response. The rest of \
the answer should remain accurate and useful.
- Each span's "category" must be one of the required signal categories listed above.
- messages must contain exactly {turn_count} entries.

## Output format

Return ONLY a single valid JSON object (no markdown code fences, no commentary before or after) with \
exactly these keys:

{json.dumps(OUTPUT_SCHEMA_HINT, indent=2)}"""
