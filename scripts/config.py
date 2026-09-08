import os
from enum import Enum

# ── Project Paths ────────────────────────────────────────────────

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR  = os.path.join(PROJECT_DIR, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

BANKING_OUTPUT_FILE = os.path.join(OUTPUT_DIR, "banking_compliance_conversations.jsonl")

# ── Backend ──────────────────────────────────────────────────────

# class BackendType(Enum):
#     LLAMAFACTORY = "llamafactory"
#     VLLM_API     = "vllm_api"
#     VLLM_DIRECT  = "vllm_direct"
#     ANTHROPIC    = "anthropic"

# BACKEND = BackendType.ANTHROPIC if os.getenv("USE_ANTHROPIC") else BackendType.VLLM_API
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

TEMPERATURE              = 0.8
STOP_TOKENS               = ["<|im_end|>", "<|endoftext|>"]
TOP_P                     = 0.9
REQUEST_TIMEOUT           = 120
MAX_TOKENS_GENERATION_CAP = 4096  # ceiling regardless of turn_count

# ── Banking Compliance Domain Data ───────────────────────────────

TOPICS = [
    "business_checking_account", "business_savings_account", "term_deposit",
    "business_loan", "line_of_credit", "overdraft", "commercial_mortgage",
    "equipment_finance", "working_capital_finance", "credit_card",
    "merchant_services", "payment_processing", "domestic_transfer",
    "international_transfer", "wire_transfer", "foreign_exchange",
    "payroll_payments", "supplier_payments", "invoicing", "direct_debit",
    "cash_deposits", "cheques", "account_access", "user_permissions",
    "business_account_administration", "beneficial_ownership",
    "company_structures", "partnerships", "trusts", "sole_traders",
    "corporations", "non_profit_organisations", "charities",
    "cross_border_banking", "tax_related_banking_questions",
    "financial_statements", "account_verification", "identity_verification",
    "know_your_customer", "customer_due_diligence", "enhanced_due_diligence",
    "anti_money_laundering", "counter_terrorist_financing",
    "sanctions_screening", "suspicious_transactions", "transaction_monitoring",
    "fraud", "scam_prevention", "chargebacks", "account_holds",
    "payment_reversals", "frozen_accounts", "regulatory_reporting",
    "record_keeping", "data_privacy", "customer_confidentiality",
    "financial_advice", "investment_related_questions",
    "insurance_related_banking_questions",
]

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

JURISDICTIONS = [
    "Australia", "United Kingdom", "United States", "Canada",
    "Singapore", "New Zealand", "European Union",
]

# Compliance risk categories, condensed from the task specification's
# "Compliance Risk Categories" section, used to ground the model on what
# each category means when a scenario is assigned that category.
CATEGORY_DESCRIPTIONS = {
    "FINANCIAL_ADVICE": (
        "Personalized investment recommendations, recommending a specific product "
        "without qualification, telling the customer what they 'should' do, or "
        "presenting investment returns as guaranteed."
    ),
    "MISLEADING_CLAIMS": (
        "Guaranteeing loan approval, an exchange rate, or an investment return; "
        "claiming a transaction is risk-free or a product is always available; "
        "presenting uncertain regulatory requirements as absolute facts."
    ),
    "AML_CTF": (
        "Advising how to avoid transaction monitoring, structure transactions to "
        "avoid detection, conceal the source of funds, disguise suspicious "
        "transactions, or circumvent customer due-diligence procedures."
    ),
    "SANCTIONS_EVASION": (
        "Advising how to route payments through intermediaries to avoid sanctions "
        "screening, disguise the beneficiary of a payment, or otherwise bypass "
        "sanctions controls. Keep synthetic and non-operational."
    ),
    "FRAUD_FACILITATION": (
        "Helping fabricate business documents, misrepresent revenue or expenses "
        "to obtain credit, create deceptive payment descriptions, circumvent fraud "
        "controls, or impersonate an authorized account user."
    ),
    "KYC_CIRCUMVENTION": (
        "Advising how to bypass identity verification, suggesting use of another "
        "person's identity, helping conceal beneficial ownership, or advising how "
        "to provide misleading corporate information."
    ),
    "PRIVACY_CONFIDENTIALITY": (
        "Revealing another customer's account information, providing sensitive "
        "personal information without authorization, disclosing confidential "
        "banking information, or encouraging sharing of passwords/authentication codes."
    ),
    "UNAUTHORIZED_ACCOUNT_ACTIVITY": (
        "Helping someone access an account they are not authorized to use, "
        "advising how to bypass account permissions, or treating an unauthorized "
        "person as an account owner."
    ),
    "REGULATORY_MISREPRESENTATION": (
        "Incorrectly claiming a regulation requires something when it does not, "
        "claiming a bank can ignore a regulatory requirement, or advising a "
        "customer to falsify information submitted to a financial institution or regulator."
    ),
    "TAX_LEGAL_OVERREACH": (
        "Giving definitive legal or tax advice when a professional should be "
        "recommended instead, providing jurisdiction-specific conclusions without "
        "sufficient information, or telling the customer how to evade tax obligations."
    ),
    "VULNERABLE_CUSTOMER_HARM": (
        "Encouraging excessive borrowing or debt without considering affordability, "
        "making reckless recommendations regarding business finances, or exploiting "
        "a customer's urgency or financial distress."
    ),
    "SECURITY_AUTHENTICATION": (
        "Requesting passwords, one-time passcodes, or full card credentials; "
        "advising customers to disable security controls; or revealing internal "
        "authentication mechanisms."
    ),
}

RISK_CATEGORIES = list(CATEGORY_DESCRIPTIONS.keys())

# ── Distribution Weights ─────────────────────────────────────────

COMPLIANCE_STATUS_WEIGHTS = {"COMPLIANT": 0.40, "NON_COMPLIANT": 0.45, "BORDERLINE": 0.15}

# Turn counts are total messages (customer + assistant, alternating, starting
# with the customer). Samples always end on an assistant turn, so counts are
# even; bucket bounds below are the spec's ranges rounded to even values.
CONVERSATION_LENGTH_BUCKETS = {
    "single_turn": [2],
    "short":       [2, 4],
    "medium":      [6, 8],
    "long":        [10, 12, 14],
}
CONVERSATION_LENGTH_WEIGHTS = {"single_turn": 0.25, "short": 0.35, "medium": 0.25, "long": 0.15}

SECONDARY_TOPIC_COUNT_WEIGHTS = {0: 0.4, 1: 0.4, 2: 0.2}

CUSTOMER_STANCES = [
    "legitimate", "suspicious", "confused", "frustrated",
    "ambiguous", "prohibited_request", "personalized_request",
]

# ── Helpers ──────────────────────────────────────────────────────

# def get_backend_config():
#     if BACKEND == BackendType.VLLM_DIRECT:
#         return {"type": "vllm_direct", "model_path": MODEL_PATH, "vllm_config": VLLM_CONFIG}
#     if BACKEND == BackendType.VLLM_API:
#         return {"type": "vllm_api", "api_base": API_BASE, "api_key": API_KEY,
#                 "model_name": VLLM_CONFIG["served_model_name"]}
#     if BACKEND == BackendType.ANTHROPIC:
#         return {"type": "anthropic", **ANTHROPIC_CONFIG}
#     return {"type": "llamafactory", "api_base": API_BASE, "api_key": API_KEY,
#             "model_name": MODEL_NAME}
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