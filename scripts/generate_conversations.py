import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import random
import argparse
from tqdm import tqdm

import config
import prompts
from model_backends import setup_model_backend, call_model
from scenario_sampler import sample_scenario
from utils import extract_json, validate_conversation, format_conversation_id, count_existing_lines


def compute_max_tokens(turn_count):
    return min(config.MAX_TOKENS_GENERATION_CAP, 400 + 180 * turn_count)


def assemble_record(conversation_id, scenario, llm_fields):
    return {
        "conversation_id": conversation_id,
        "conversation_type": scenario["conversation_type"],
        "industry": scenario["industry"],
        "business_type": scenario["business_type"],
        "jurisdiction": scenario["jurisdiction"],
        "primary_topic": scenario["primary_topic"],
        "secondary_topics": scenario["secondary_topics"],
        "customer_intent": llm_fields.get("customer_intent"),
        "compliance_status": scenario["compliance_status"],
        "risk_categories": scenario["risk_categories"],
        "severity": scenario["severity"],
        "difficulty": scenario["difficulty"],
        "messages": llm_fields.get("messages"),
        "problematic_turns": llm_fields.get("problematic_turns"),
        "problematic_spans": llm_fields.get("problematic_spans"),
        "reasoning_summary": llm_fields.get("reasoning_summary"),
        "expected_ai_behavior": llm_fields.get("expected_ai_behavior"),
    }


def generate_one(conversation_id, scenario, temperature, max_retries):
    max_tokens = compute_max_tokens(scenario["turn_count"])
    prompt = prompts.build_conversation_prompt(scenario)
    last_errors = ["no attempts made"]

    for attempt in range(max_retries + 1):
        response = call_model(prompt, max_tokens, temperature)
        parsed = extract_json(response)
        if parsed is None:
            last_errors = ["model response was not valid/parseable JSON"]
            continue
        record = assemble_record(conversation_id, scenario, parsed)
        ok, errors = validate_conversation(record, config.RISK_CATEGORIES)
        if ok:
            return record, []
        last_errors = errors

    return None, last_errors


def main(count, output, start_index, max_retries, temperature, seed):
    if seed is not None:
        random.seed(seed)

    ok, model = setup_model_backend()
    if not ok:
        print("Failed to set up model backend")
        return

    if start_index is None:
        start_index = count_existing_lines(output) + 1

    written, dropped = 0, 0
    status_counts = {}

    os.makedirs(os.path.dirname(output) or ".", exist_ok=True)
    with open(output, "a", encoding="utf-8") as f:
        for i in tqdm(range(count), desc="Generating conversations"):
            idx = start_index + i
            scenario = sample_scenario()
            conversation_id = format_conversation_id(idx)

            record, errors = generate_one(conversation_id, scenario, temperature, max_retries)
            if record is None:
                dropped += 1
                tqdm.write(f"  dropped {conversation_id}: {errors[:2]}")
                continue

            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            f.flush()
            written += 1
            status_counts[record["compliance_status"]] = status_counts.get(record["compliance_status"], 0) + 1

    print(f"\nmodel={model}  written={written}  dropped={dropped} -> {output}")
    print(f"compliance_status distribution: {status_counts}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=50)
    ap.add_argument("--output", default=config.BANKING_OUTPUT_FILE)
    ap.add_argument("--start_index", type=int, default=None,
                     help="conversation_id start index; defaults to continuing after existing lines in --output")
    ap.add_argument("--max_retries", type=int, default=2)
    ap.add_argument("--temperature", type=float, default=config.TEMPERATURE)
    ap.add_argument("--seed", type=int, default=None)
    a = ap.parse_args()
    main(a.count, a.output, a.start_index, a.max_retries, a.temperature, a.seed)
