from typing import Dict, Optional
import json

from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain_openai import ChatOpenAI


llm = ChatOpenAI(
    model="gpt-3.5-turbo",
    temperature=0
)

budget_slot_prompt = PromptTemplate(
    input_variables=["text"],
    template="""
Extract budget details from the text.

Return JSON ONLY in this format:
{{
  "category": string | null,
  "amount": number | null
}}

Text:
{text}
"""
)

budget_chain = LLMChain(
    llm=llm,
    prompt=budget_slot_prompt
)


def extract_budget_slots(text: str) -> Dict[str, Optional[str | float]]:
    try:
        response = budget_chain.run(text=text)
        return json.loads(response)
    except Exception:
        return {"category": None, "amount": None}


# -----------------------------
# Reminder Slots
# -----------------------------
reminder_prompt = PromptTemplate(
    input_variables=["text"],
    template="""
Extract reminder details.

Return JSON ONLY:
{{
  "name": string | null,
  "day": number | null,
  "frequency": "weekly" | "monthly" | null
}}

Text:
{text}
"""
)

reminder_chain = LLMChain(llm=llm, prompt=reminder_prompt)


def extract_reminder_slots(text: str) -> Dict:
    try:
        return json.loads(reminder_chain.run(text=text))
    except Exception:
        return {"name": None, "day": None, "frequency": None}


# -----------------------------
# Transaction Slots
# -----------------------------
transaction_prompt = PromptTemplate(
    input_variables=["text"],
    template="""
Extract expense details.

Return JSON ONLY:
{{
  "category": string | null,
  "amount": number | null,
  "description": string | null
}}

Text:
{text}
"""
)

transaction_chain = LLMChain(llm=llm, prompt=transaction_prompt)


def extract_transaction_slots(text: str) -> Dict:
    try:
        return json.loads(transaction_chain.run(text=text))
    except Exception:
        return {
            "category": None,
            "amount": None,
            "description": None
        }
