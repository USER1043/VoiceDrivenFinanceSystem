# app/ai/parser.py

import re
from functools import lru_cache
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

MODEL_NAME = "google/flan-t5-base"

VALID_PATTERNS = [
    r"^set \w+ budget to \d+$",
    r"^add expense \d+ \w+$",
    r"^remind me to .+ on \d+$",
    r"^check balance$",
]

@lru_cache(maxsize=1)
def _load_model():
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_NAME)
    model.eval()
    return tokenizer, model


def _is_valid_command(cmd: str) -> bool:
    return any(re.match(p, cmd) for p in VALID_PATTERNS)


def normalize_command(text: str) -> str:
    """
    Normalize natural language into a STRICT finance command.
    Falls back safely if AI output is invalid.
    """

    if not text or len(text.strip()) < 3:
        return text.lower().strip()

    tokenizer, model = _load_model()

    prompt = f"""
You are a STRICT command normalizer.

You MUST output EXACTLY ONE command.
DO NOT invent placeholders.
DO NOT explain.
DO NOT add symbols.

Choose ONE format ONLY:

1. set <category> budget to <amount>
2. add expense <amount> <category>
3. remind me to <name> on <day>
4. check balance

### Examples

User: paid 40 for tea
Command: add expense 40 tea

User: dont let me spend more than 23 on pen
Command: set pen budget to 23

User: how much money is left
Command: check balance

User: remind me to pay rent on 10
Command: remind me to pay rent on 10

### Now convert:

User: {text}
Command:
""".strip()

    inputs = tokenizer(prompt, return_tensors="pt", truncation=True)

    outputs = model.generate(
        **inputs,
        max_length=24,
        do_sample=False,
        num_beams=5,
        early_stopping=True,
    )

    command = tokenizer.decode(outputs[0], skip_special_tokens=True)
    command = command.lower().strip()

    # 🛑 HARD VALIDATION
    if _is_valid_command(command):
        return command

    # 🔁 SAFETY FALLBACK (VERY IMPORTANT)
    return text.lower().strip()
