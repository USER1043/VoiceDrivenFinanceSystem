from enum import Enum
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain_openai import ChatOpenAI


class Intent(str, Enum):
    UPDATE_BUDGET = "UPDATE_BUDGET"
    CREATE_REMINDER = "CREATE_REMINDER"
    CHECK_BALANCE = "CHECK_BALANCE"
    ADD_EXPENSE = "ADD_EXPENSE"
    UNKNOWN = "UNKNOWN"


llm = ChatOpenAI(
    model="gpt-3.5-turbo",
    temperature=0
)

intent_prompt = PromptTemplate(
    input_variables=["text"],
    template="""
You are an intent classifier for a finance voice assistant.

Valid intents:
- UPDATE_BUDGET
- CREATE_REMINDER
- CHECK_BALANCE
- ADD_EXPENSE
- UNKNOWN

User text:
{text}

Return ONLY the intent name.
"""
)

intent_chain = LLMChain(
    llm=llm,
    prompt=intent_prompt
)


def detect_intent(text: str) -> Intent:
    if not text:
        return Intent.UNKNOWN

    try:
        result = intent_chain.run(text=text).strip()
        return Intent(result)
    except Exception:
        return Intent.UNKNOWN
