**DS²-INSTRUCT: Synthetic Business Banking Compliance Conversation Generator**


> A zero-shot framework that generates synthetic business banking / financial compliance conversations, labeled COMPLIANT / NON_COMPLIANT / BORDERLINE, for training and evaluating a financial compliance detection system.

## Setup

```bash
conda env create -f environment.yml
conda activate ds2
```


## Usage

### Local vLLM (Qwen 72B)

Run generation + validation for 200 conversations:
```bash
bash shell/run_pipeline_qwen72b.sh 200
```

### Anthropic

```bash
export USE_ANTHROPIC=1
export ANTHROPIC_API_KEY=<your-key>
bash shell/run_pipeline_anthropic.sh 200
```

### Running stages directly

```bash
python scripts/generate_conversations.py --count 200
python scripts/validate_conversations.py --input output/banking_compliance_conversations.jsonl
```

## Output

Conversations are written as JSONL to `output/banking_compliance_conversations.jsonl`, one record per line, in the schema described in [Task description.md](Task description.md) and demonstrated in [synthetic_conversations.jsonl](synthetic_conversations.jsonl).
