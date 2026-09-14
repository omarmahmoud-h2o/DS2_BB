import os
from enum import Enum

# ── Project Paths ────────────────────────────────────────────────

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR  = os.path.join(PROJECT_DIR, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

FAG_OUTPUT_FILE = os.path.join(OUTPUT_DIR, "vrm_fag_conversations.jsonl")

# ── Backend ──────────────────────────────────────────────────────

class BackendType(Enum):
    LLAMAFACTORY = "llamafactory"
    VLLM_API     = "vllm_api"
    VLLM_DIRECT  = "vllm_direct"
    ANTHROPIC    = "anthropic"
    MLX          = "mlx"


BACKEND = BackendType.MLX

# ── Model ────────────────────────────────────────────────────────

MODEL_NAME = "Qwen/Qwen3.5-4B"
MODEL_PATH = "Qwen/Qwen3.5-4B"

# ── vLLM Server ──────────────────────────────────────────────────

VLLM_CONFIG = {
    "host": "0.0.0.0",
    "port": int(os.getenv("VLLM_PORT", 8001)),
    "served_model_name": os.getenv("VLLM_SERVED_MODEL_NAME", "Qwen3.5-4B"),
    "max_model_len": 5200,
    "pipeline_parallel_size": 1,
    "tensor_parallel_size": int(os.getenv("VLLM_TP_SIZE", 4)),
    "gpu_memory_utilization": 0.95,
    "trust_remote_code": True,
    "dtype": "bfloat16",
    "enable_prefix_caching": True,
    "max_num_batched_tokens": 2048,
}

MLX_MODEL_PATH = os.getenv(
    "MLX_MODEL_PATH",
    "mlx-community/Qwen3.5-4B-MLX-4bit",
)

# ── API ──────────────────────────────────────────────────────────

API_BASE = os.getenv("VLLM_API_BASE", f"http://localhost:{VLLM_CONFIG['port']}/v1")
API_KEY  = os.getenv("VLLM_API_KEY", "EMPTY")

ANTHROPIC_CONFIG = {
    "model_name": os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5"),
    "api_key": os.getenv("ANTHROPIC_API_KEY", ""),
}

# ── Generation Parameters ────────────────────────────────────────

TEMPERATURE               = 0.8
STOP_TOKENS               = ["<|im_end|>", "<|endoftext|>"]
TOP_P                     = 0.9
REQUEST_TIMEOUT           = 120
MAX_TOKENS_GENERATION_CAP = 4096  # ceiling regardless of turn_count

# ═════════════════════════════════════════════════════════════════
# Financial Advice Guardrail (FAG) domain data
# ═════════════════════════════════════════════════════════════════
# Scope: this corpus trains/evaluates ONE guardrail — the FAG — which emits a
# single boolean. Compliance (FAG AND groundedness) is the layer above and is
# deliberately NOT modelled here; see VRM_Compliance_Guardrail_Architecture.md.
#
# The label is `financial_advice_breach` (breach-positive, so the positive
# class is the event being detected). The variable the guardrail hands to the
# compliance tree is its negation, mirroring the groundedness sibling:
#     fag_pass = not financial_advice_breach
#     grounded = not result.issue_detected
#
# Taxonomy source of truth: VRM_Compliance_Definitions_OLD.md.

# Corps Act financial products — strictest restrictions: only Tier 1 factual
# information is permitted, and an advice-seeking question requires a denial.
CORPS_ACT_PRODUCT_TOPICS = [
    "business_transaction_account",
    "business_investment_account",
    "neo_business_card",
]

# Non-Corps Act banking services. Tier 2 general advice is permitted here
# (though monitored); Tier 3 personal advice is a breach everywhere.
NON_CORPS_ACT_TOPICS = [
    "domestic_transfer", "international_transfer", "foreign_exchange",
    "merchant_services", "payment_processing", "payroll_payments",
    "supplier_payments", "invoicing", "direct_debit", "cash_deposits",
    "account_access", "user_permissions", "business_account_administration",
    "account_fees_and_statements", "online_banking", "card_transaction_disputes",
    "scam_prevention_information", "branch_and_support_channels",
]

TOPICS = CORPS_ACT_PRODUCT_TOPICS + NON_CORPS_ACT_TOPICS

# The factual/advice boundary on Corps Act products is the core of the task,
# so it dominates the sample.
PRODUCT_SCOPE_WEIGHTS = {"corps_act": 0.65, "non_corps_act": 0.35}

INDUSTRIES = [
    "retail", "construction", "professional_services", "wholesale_trading",
    "wholesale_distribution", "import_export", "consulting", "hospitality",
    "manufacturing", "technology", "healthcare_services", "agriculture",
    "real_estate", "transportation_logistics", "e_commerce", "nonprofit",
]

BUSINESS_TYPES = [
    "sole_trader", "partnership", "private_company", "public_company",
    "trust", "non_profit_organisation", "charity",
]

# VRM operates under Australian law (Corporations Act 2001, ASIC RG244/RG255).
JURISDICTIONS = ["Australia"]

# ── Three-tier advice hierarchy ──────────────────────────────────
# Generation control and metadata, NOT the label. The breach is derivable:
#   FACTUAL_INFORMATION            -> no breach
#   GENERAL_ADVICE  on corps_act   -> breach;  on non_corps_act -> no breach
#   PERSONAL_ADVICE                -> breach, always

ADVICE_TIER_DESCRIPTIONS = {
    "FACTUAL_INFORMATION": (
        "Tier 1 — objective product features, rates, fees, eligibility criteria, "
        "availability. No opinion, no recommendation. Allowed for all products."
    ),
    "GENERAL_ADVICE": (
        "Tier 2 — statements about product suitability without reference to the "
        "customer's personal circumstances. Prohibited for Corps Act products, "
        "permitted (but monitored) for other banking services."
    ),
    "PERSONAL_ADVICE": (
        "Tier 3 — takes the customer's specific circumstances into account to "
        "suggest a product decision. Prohibited in all cases."
    ),
}

ADVICE_TIERS = list(ADVICE_TIER_DESCRIPTIONS.keys())

# ── 15 signal categories (span-level diagnostics) ────────────────
# The 14 from VRM_Compliance_Definitions_OLD.md plus INSURANCE_ADVICE, which closes
# a real gap: the doc lists tax/legal/investment cues but no insurance, while
# insurance is a regulated advice domain in its own right.

SIGNAL_DESCRIPTIONS = {
    "SUITABILITY_ASSESSMENT": (
        "Assessing that a product suits the customer, e.g. "
        "\"this product suits your needs\"."
    ),
    "PRODUCT_RECOMMENDATION": (
        "Recommending a product, e.g. \"I recommend\" / \"you should consider\"."
    ),
    "ACTION_DIRECTIVE": (
        "Directing the customer to act on a product decision, e.g. "
        "\"apply now\", \"switch to\"."
    ),
    "SUBJECTIVE_DESCRIPTOR": (
        "Opinionated product descriptors, e.g. \"best\", \"great option\", "
        "\"ideal\", \"competitive\"."
    ),
    "COMPETITIVE_COMPARISON": (
        "Comparing one product's merits over another in a way that steers the "
        "customer's choice."
    ),
    "FORWARD_LOOKING_PERFORMANCE": (
        "Forward-looking performance statements, e.g. "
        "\"you'll earn more with this account\"."
    ),
    "IMPLIED_ENDORSEMENT": (
        "Framing that suggests the bank prefers one product for the customer."
    ),
    "RISK_CHARACTERISATION": (
        "Labelling products as low/high risk for the customer."
    ),
    "PERSONAL_LANGUAGE": (
        "Language implying knowledge of the customer's specific situation."
    ),
    "NEED_BASED_FRAMING": (
        "Framing a product around the customer's stated needs, e.g. "
        "\"given your business needs, this product...\"."
    ),
    "OUTCOME_PROJECTION": (
        "Predicting financial outcomes for the specific customer."
    ),
    "TAX_ADVICE": (
        "Tax advice cues, e.g. \"this could reduce your tax\"."
    ),
    "LEGAL_ADVICE": (
        "Legal advice cues, e.g. \"you are legally better off\"."
    ),
    "INVESTMENT_ADVICE": (
        "Investment advice cues, e.g. \"this will grow your money\"."
    ),
    "INSURANCE_ADVICE": (
        "Insurance advice cues, e.g. \"you should cover that with insurance\"."
    ),
}
SIGNAL_CATEGORIES = list(SIGNAL_DESCRIPTIONS.keys())

# Signal groupings — which tier a signal evidences.
# General advice: opines on the product without referencing the customer.
GENERAL_ADVICE_SIGNALS = [
    "PRODUCT_RECOMMENDATION", "ACTION_DIRECTIVE", "SUBJECTIVE_DESCRIPTOR",
    "COMPETITIVE_COMPARISON", "FORWARD_LOOKING_PERFORMANCE",
    "IMPLIED_ENDORSEMENT", "RISK_CHARACTERISATION",
]

# Personal advice: inherently references the customer's own circumstances.
PERSONAL_ADVICE_SIGNALS = [
    "SUITABILITY_ASSESSMENT", "PERSONAL_LANGUAGE",
    "NEED_BASED_FRAMING", "OUTCOME_PROJECTION",
]

# Separately regulated advice domains; can accompany either tier.
DOMAIN_ADVICE_SIGNALS = [
    "TAX_ADVICE", "LEGAL_ADVICE", "INVESTMENT_ADVICE", "INSURANCE_ADVICE",
]

# Chance a breach additionally carries a domain-advice signal. Deliberately
# non-trivial: tax/insurance advice are real policy variables that carry no
# examples in the production eval data, so this corpus covers them.
DOMAIN_SIGNAL_RATE = 0.18

# ── Production policy categories (derived, never annotated) ──────
# The 9 booleans the production system records. policy_categories.py computes
# them from signals + context facts, so prod-parity output is available without
# supervising a coarse, partly-unpopulated taxonomy.
PRODUCTION_POLICY_CATEGORIES = [
    "corps_question_breach_no_denial",
    "corps_question_breach_general_advice",
    "business_advice_corps_products",
    "business_advice_non_corps_tailored",
    "business_advice_misleading",
    "tax_advice",
    "investment_advice",
    "legal_advice",
    "insurance_advice",
]

# ── Customer stances ─────────────────────────────────────────────

CUSTOMER_STANCES = [
    "legitimate_info_seeker", "recommendation_seeker",
    "personal_circumstances_shared", "comparison_shopper",
    "confused", "frustrated", "urgent", "ambiguous",
]

# Stances that solicit advice. On a Corps Act product these make the request a
# "corps question", which a compliant response must answer with a denial.
ADVICE_SEEKING_STANCES = {
    "recommendation_seeker", "personal_circumstances_shared", "comparison_shopper",
}

# ── Distribution knobs ───────────────────────────────────────────
# Balanced by design, NOT matched to any held-out evaluation set. Real-world
# prevalence is a reweighting knob applied at readout, not baked into the data
# (same rationale as archive/groundedness-v1 ADR 0002, "Balance, not prevalence").

BREACH_RATE = 0.50

# Fraction of records flagged as genuinely contestable. Replaces the old
# BORDERLINE verdict class: a guardrail emits a boolean, so ambiguity is
# recorded alongside the label rather than as a third value of it.
CONTESTABLE_RATE = 0.15

# Severity applies only to breaches; non-breach records carry severity=None.
SEVERITY_WEIGHTS_GENERAL_ADVICE  = {"MEDIUM": 0.5, "HIGH": 0.4, "CRITICAL": 0.1}
SEVERITY_WEIGHTS_PERSONAL_ADVICE = {"MEDIUM": 0.2, "HIGH": 0.5, "CRITICAL": 0.3}

# Difficulty applies to both classes — a compliant reply can still be hard to
# classify. BORDERLINE is gone from this axis; `contestable` carries that now.
DIFFICULTY_WEIGHTS_BREACH    = {"EASY": 0.25, "MEDIUM": 0.45, "HARD": 0.30}
DIFFICULTY_WEIGHTS_NO_BREACH = {"EASY": 0.45, "MEDIUM": 0.40, "HARD": 0.15}

# Probability a breaching answer to a corps question omits the required denial
# entirely (the `corps_question_breach_no_denial` case) rather than declining
# and then advising anyway.
NO_DENIAL_RATE = 0.6

# Turn counts are total messages (customer + assistant, alternating, starting
# with the customer). Samples always end on an assistant turn, so counts are even.
CONVERSATION_LENGTH_BUCKETS = {
    "single_turn": [2],
    "short":       [2, 4],
    "medium":      [6, 8],
    "long":        [10, 12, 14],
}
CONVERSATION_LENGTH_WEIGHTS = {"single_turn": 0.25, "short": 0.35, "medium": 0.25, "long": 0.15}

SECONDARY_TOPIC_COUNT_WEIGHTS = {0: 0.4, 1: 0.4, 2: 0.2}


# ── Helpers ──────────────────────────────────────────────────────

def get_backend_config():
    if BACKEND == BackendType.MLX:
        return {
            "type": "mlx",
            "model_path": MLX_MODEL_PATH,
            "mlx_config": {},
        }

    if BACKEND == BackendType.VLLM_DIRECT:
        return {
            "type": "vllm_direct",
            "model_path": MODEL_PATH,
            "vllm_config": VLLM_CONFIG,
        }

    if BACKEND == BackendType.VLLM_API:
        return {
            "type": "vllm_api",
            "api_base": API_BASE,
            "api_key": API_KEY,
            "model_name": VLLM_CONFIG["served_model_name"],
        }

    if BACKEND == BackendType.ANTHROPIC:
        return {
            "type": "anthropic",
            **ANTHROPIC_CONFIG,
        }

    return {
        "type": "llamafactory",
        "api_base": API_BASE,
        "api_key": API_KEY,
        "model_name": MODEL_NAME,
    }
