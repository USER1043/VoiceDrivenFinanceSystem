"""Offline rule-based parser: the last fallback, and the only one that needs no API key.

Handles the short, everyday phrasings people actually say:
"paid 180 for auto", "chai 20 cash", "450 swiggy yesterday", "salary credited 85k",
"set food budget to 6000", "got 500 from mom on gpay".

And questions: "how much did I spend on food this month", "top categories last month",
"where did I spend the most in August", "how much is left in my food budget".
"""

import re
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from app.models import AccountKind, CategoryKind
from app.nlu.raw import Metric, RawCommand
from app.nlu.vocab import VocabCategory, Vocabulary

_MULTIPLIERS = {
    "k": 1_000,
    "thousand": 1_000,
    "grand": 1_000,
    "lakh": 100_000,
    "lakhs": 100_000,
    "lac": 100_000,
    "lacs": 100_000,
    "hundred": 100,
}
_NUMBER = re.compile(
    r"(?<![\w.:])(?P<num>\d+(?:\.\d{1,2})?)(?:\s*(?P<mult>k|thousand|grand|lakhs?|lacs?|hundred))?"
    r"(?![\w:])(?!\s*(?:am|pm)\b)"
)
_CURRENCY_BEFORE = re.compile(r"(?:\brs\.?|\binr|₹)\s*$")
_CURRENCY_AFTER = re.compile(r"^\s*(?:rs\b|rupees?\b|bucks\b|inr\b|/-)")

_PRICE_CUE = re.compile(r"\b(?:for|of|paid|spent|cost|costs|costing|worth|is|was)\s*$")
_QUANTITY_AFTER = re.compile(
    r"^\s*(?:km|kms|kg|kgs|g|gm|grams?|litres?|liters?|ltrs?|l|x|pcs|pieces?|items?|people|"
    r"persons?|plates?|cups?|coffees?|teas?|chais?|tickets?|hours?|hrs?|mins?|minutes?|days?|"
    r"nights?|months?)\b"
)
_STAFF_PAY = re.compile(
    r"\b(?:maid|driver|cook|watchman|helper|servant|staff|nanny|gardener|bai|didi)'?s?\s+"
    r"(?:salary|pay|payment)\b|\b(?:paid|gave)\b.*\bsalary\b"
)
_QUESTION = re.compile(
    r"^(?:how|what|what's|whats|show|tell|list|which|when|where|did|do|am|have|give)\b|\?\s*$"
)
# Words that make a question (or an amount-less phrase) about money, not small talk.
_MONEY_TOPIC = re.compile(
    r"\b(?:spend|spent|spending|spends|expense|expenses|expenditure|cost|costs|paid|pay|money|"
    r"earn|earned|earnings|income|received|receive|made|make|budgets?|total|breakdown|"
    r"categor(?:y|ies)|merchants?|shops?|stores?|how\s+much)\b"
)
_QUERY_HINT = re.compile(
    r"\b(?:spending|expenses|expenditure|earnings|income|breakdown|summary|total|so\s+far|"
    r"top\s+\d*\s*(?:categor(?:y|ies)|merchants?|shops?|stores?|places?))\b"
)
_ASK_BUDGET = re.compile(r"\bbudgets?\b")
_ASK_MERCHANTS = re.compile(r"\b(?:merchants?|shops?|stores?|places?|apps?|restaurants?|who)\b")
_ASK_CATEGORIES = re.compile(
    r"\b(?:categor(?:y|ies)|breakdown|where\b.*\b(?:money|most|go|went)|most\s+on|"
    r"biggest|top)\b"
)
_ASK_INCOME = re.compile(
    r"\b(?:earn|earned|earnings|income|received|receive|credited|got\s+paid|"
    r"(?:did|do)\s+i\s+(?:make|get)|salary)\b"
)
_MONTHS = {
    name: index
    for index, names in enumerate(
        [
            ("january", "jan"), ("february", "feb"), ("march", "mar"), ("april", "apr"),
            ("may",), ("june", "jun"), ("july", "jul"), ("august", "aug"),
            ("september", "sep", "sept"), ("october", "oct"), ("november", "nov"),
            ("december", "dec"),
        ],
        start=1,
    )
    for name in names
}  # fmt: skip
_MONTH_NAME = re.compile(
    r"\b(?:in|during|for|of|since)\s+(?P<m>" + "|".join(_MONTHS) + r")\b(?:\s+(?P<y>20\d\d))?"
    r"|\b(?P<m2>" + "|".join(n for n in _MONTHS if len(n) > 3) + r")\b(?:\s+(?P<y2>20\d\d))?"
)
_PERIODS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(?:today|tonight|so\s+far\s+today)\b"), "today"),
    (re.compile(r"\byesterday\b"), "yesterday"),
    (re.compile(r"\b(?:last|past|previous)\s+week\b"), "last_week"),
    (re.compile(r"\bthis\s+week\b|\bweek\s+so\s+far\b"), "this_week"),
    (re.compile(r"\b(?:last|previous|past)\s+month\b"), "last_month"),
    (re.compile(r"\b(?:last|previous|past)\s+year\b"), "last_year"),
    (re.compile(r"\bthis\s+year\b|\byear\s+so\s+far\b"), "this_year"),
]
_LAST_DAYS = re.compile(r"\b(?:last|past|previous)\s+(?P<n>\d{1,3})\s+days?\b")
_QUERY_STOP = re.compile(
    r"\s+\b(?:this|last|past|previous|since|during|so|till|until|today|yesterday|in|on|by|"
    r"with|using|via|through)\b.*$"
)
_BUDGET = re.compile(
    r"\b(?:budget|limit|cap)\b|spend\s+(?:no\s+)?more\s+than|don'?t\s+(?:let\s+me\s+)?spend"
)
_INCOME = re.compile(
    r"\b(?:received|recieved|credited|salary|stipend|earned|income|refund(?:ed)?|cashback|"
    r"got\s+paid|reimbursed|reimbursement)\b|\bgot\s+(?:rs\.?\s*|₹\s*)?\d|\bgot\b.*\bfrom\b"
)

_ACCOUNT_WORDS: list[tuple[re.Pattern[str], AccountKind]] = [
    (re.compile(r"\b(?:in\s+|by\s+|with\s+|via\s+)?cash\b"), AccountKind.CASH),
    (
        re.compile(
            r"\b(?:credit|debit)\s+card\b|\b(?:on|by|with|via|using|through)\s+(?:my\s+)?card\b"
            r"|\bcard\s*$|\bswiped\b"
        ),
        AccountKind.CARD,
    ),
    (
        re.compile(r"\b(?:upi|gpay|g\s?pay|google\s+pay|phone\s?pe|paytm|bhim|scan(?:ned)?)\b"),
        AccountKind.UPI,
    ),
]

_DAYS_AGO = [
    (re.compile(r"\bday\s+before\s+yesterday\b"), 2),
    (re.compile(r"\byesterday\b|\blast\s+night\b"), 1),
]
_WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

_STOP = (
    r"for|on|via|using|with|by|through|in|yesterday|today|tonight|rs|inr|and|of|paid|cash|"
    r"card|upi|gpay|paytm|phonepe"
)
_MERCHANT = re.compile(
    rf"\b(?:at|from|to)\s+(?P<m>[a-z][\w&'.-]*(?:\s+(?!(?:{_STOP})\b)[a-z][\w&'.-]*){{0,3}})"
)
_NOT_MERCHANTS = {
    "home", "office", "work", "the", "my", "a", "me", "him", "her", "them", "it", "shop",
    "store", "market", "cash", "card", "upi", "mall", "petrol pump",
}  # fmt: skip


_UNITS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
    "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19,
}  # fmt: skip
_TENS = {
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70,
    "eighty": 80, "ninety": 90,
}  # fmt: skip
_SCALES = {"hundred": 100, "thousand": 1_000, "lakh": 100_000, "lakhs": 100_000}
_NUMBER_WORD = "|".join([*_UNITS, *_TENS, *_SCALES, "a", "and"])
_NUMBER_WORDS = re.compile(rf"\b(?:{_NUMBER_WORD})(?:[\s-]+(?:{_NUMBER_WORD}))*\b")


def _words_to_number(match: re.Match[str]) -> str:
    """'two hundred and fifty' -> '250'; leaves phrases without a number word alone."""
    words = [w for w in re.split(r"[\s-]+", match.group()) if w]
    has_digit_word = any(w in _UNITS or w in _TENS for w in words)
    a_scale = len(words) > 1 and words[0] == "a" and words[1] in _SCALES  # "a hundred"
    if not (has_digit_word or a_scale):
        return match.group()  # "lakh" in "1.2 lakh" stays a multiplier
    total = current = 0
    seen = False
    for word in words:
        if word in _UNITS:
            current += _UNITS[word]
            seen = True
        elif word in _TENS:
            current += _TENS[word]
            seen = True
        elif word == "a":
            current += 1 if not seen else 0
        elif word in _SCALES:
            scale = _SCALES[word]
            current = max(current, 1)
            if scale == 100:
                current *= 100
            else:
                total += current * scale
                current = 0
            seen = True
    if not seen:
        return match.group()
    return f" {total + current} "


def _normalise(text: str) -> str:
    text = text.lower().replace("₹", " ₹").replace("\u2019", "'")
    text = _NUMBER_WORDS.sub(_words_to_number, text)
    text = re.sub(r"(?<=\d),(?=\d)", "", text)  # 1,250 -> 1250
    text = re.sub(r"(?<=\d)(?=(?:rs|k)\b)", " ", text)  # 500rs -> 500 rs
    return re.sub(r"\s+", " ", text).strip()


def _amount(text: str) -> str | None:
    """Rupees as a decimal string. Prefers a number next to a currency word."""
    candidates: list[tuple[int, Decimal]] = []
    for match in _NUMBER.finditer(text):
        try:
            value = Decimal(match["num"]) * _MULTIPLIERS.get(match["mult"] or "", 1)
        except InvalidOperation:  # pragma: no cover - regex guarantees digits
            continue
        before, after = text[: match.start()], text[match.end() :]
        if _CURRENCY_BEFORE.search(before) or _CURRENCY_AFTER.match(after):
            rank = 3
        elif _PRICE_CUE.search(before):
            rank = 2
        elif _QUANTITY_AFTER.match(after):
            rank = 0  # "4 km", "2 coffees": a count, not a price
        else:
            rank = 1
        candidates.append((rank, value))
    if not candidates:
        return None
    # Best cue wins; among equals the larger number (prices outgrow counts: "2 teas 40").
    _, value = max(candidates, key=lambda c: (c[0], c[1]))
    return format(value.normalize(), "f")


def _strip_numbers(text: str) -> str:
    return _NUMBER.sub(" ", text)


def _category(text: str, vocab: Vocabulary, kind: CategoryKind) -> VocabCategory | None:
    """Longest name/alias that appears as whole words; subcategories win ties."""
    best: tuple[int, int, VocabCategory] | None = None
    for category in vocab.of_kind(kind):
        for phrase in (category.name.lower(), *category.aliases):
            # Tolerate plurals and verb endings: "coffees", "movies", "recharged".
            ending = r"(?:s|es|d|ed|ing)?"
            if phrase and re.search(rf"(?<![\w]){re.escape(phrase)}{ending}(?![\w])", text):
                score = (len(phrase), 1 if category.parent else 0, category)
                if best is None or score[:2] > best[:2]:
                    best = score
    return best[2] if best else None


def _account(text: str, vocab: Vocabulary) -> str | None:
    for account in vocab.accounts:
        name = account.name.lower()
        # Generic names ("Card", "Cash") are matched by the cue patterns below instead,
        # so "metro card recharge" doesn't mean "paid by card".
        if name not in ("card", "cash", "upi", "bank") and re.search(
            rf"\b{re.escape(name)}\b", text
        ):
            return account.name
    for pattern, kind in _ACCOUNT_WORDS:
        if pattern.search(text):
            match = next((a for a in vocab.accounts if a.kind == kind), None)
            if match:
                return match.name
    return None


def _date(text: str, today: date) -> str | None:
    for pattern, days in _DAYS_AGO:
        if pattern.search(text):
            return (today - timedelta(days=days)).isoformat()
    for index, name in enumerate(_WEEKDAYS):
        if re.search(rf"\b(?:on\s+|last\s+)?{name}\b", text):
            back = (today.weekday() - index) % 7 or 7
            return (today - timedelta(days=back)).isoformat()
    return None


def _merchant(text: str, category: VocabCategory | None) -> str | None:
    match = _MERCHANT.search(_strip_numbers(text))
    if not match:
        return None
    merchant = re.sub(r"^(?:the|a|an|my)\s+", "", match["m"].strip(" .'-"))
    if not merchant or merchant in _NOT_MERCHANTS or merchant in _WEEKDAYS:
        return None
    if category and merchant == category.name.lower():
        return None
    return merchant.title()


def _period(text: str, today: date) -> str | None:
    if match := _LAST_DAYS.search(text):
        return f"last_{match['n']}_days"
    for pattern, period in _PERIODS:
        if pattern.search(text):
            return period
    if match := _MONTH_NAME.search(text):
        month = _MONTHS[match["m"] or match["m2"]]
        year = int(match["y"] or match["y2"] or today.year)
        return f"{year}-{month:02d}"
    return None


def _query_merchant(text: str) -> str | None:
    match = re.search(r"\b(?:at|from|to)\s+(?P<m>[a-z][\w&'. -]*)", text)
    if not match:
        return None
    merchant = _QUERY_STOP.sub("", match["m"]).strip(" .'-?")
    merchant = re.sub(r"^(?:the|a|an|my)\s+", "", merchant)
    if not merchant or merchant in _NOT_MERCHANTS or len(merchant.split()) > 4:
        return None
    return merchant.title()


def _query(t: str, vocab: Vocabulary, today: date) -> RawCommand:
    metric: Metric = "total"
    if _ASK_BUDGET.search(t):
        metric = "budget"
    elif _ASK_MERCHANTS.search(t):
        metric = "top_merchants"
    elif _ASK_CATEGORIES.search(t):
        metric = "top_categories"
    kind = CategoryKind.INCOME if _ASK_INCOME.search(t) and metric != "budget" else None
    # "income" and "salary" pick the kind; they only name a category when nothing else does.
    words = re.sub(r"\b(?:income|spending|spend|spent|earnings)\b", " ", _strip_numbers(t))
    category = _category(words, vocab, kind or CategoryKind.EXPENSE)
    if category and kind and category.name.lower() in ("other income",):
        category = None
    merchant = _query_merchant(t)
    if merchant and category:
        if merchant.lower() in (category.name.lower(), *category.aliases):
            merchant = None  # "at dmart": the alias already says Groceries
        elif _category(words.replace(merchant.lower(), " "), vocab, category.kind) is None:
            category = None  # "at chai point" is a shop, not the Tea category
    return RawCommand(
        tool="query_spending",
        metric=metric,
        kind=kind.value if kind else "expense",
        category=category.name if category else None,
        merchant=merchant,
        account=_account(t, vocab),
        period=_period(t, today),
    )


def parse(text: str, vocab: Vocabulary, today: date) -> RawCommand:
    t = _normalise(text)
    if not t:
        return RawCommand(tool="clarify", question="I didn't catch that. What did you spend?")

    amount = _amount(t)
    # Numbers in "last 7 days", "top 5" or "august 2025" are not amounts.
    plain = _MONTH_NAME.sub(" ", _LAST_DAYS.sub(" ", re.sub(r"\btop\s+\d+", " ", t)))
    asking = _QUESTION.search(t) or (_amount(plain) is None and _QUERY_HINT.search(t))
    if asking:
        if _MONEY_TOPIC.search(t) or _category(_strip_numbers(t), vocab, CategoryKind.EXPENSE):
            return _query(t, vocab, today)
        return RawCommand(
            tool="unsupported",
            question="I can log spending and answer questions like "
            "“how much did I spend on food this month?”",
        )
    words = _strip_numbers(t)

    if _BUDGET.search(t):
        category = _category(words, vocab, CategoryKind.EXPENSE)
        if category is None:
            return RawCommand(tool="clarify", question="Which category is the budget for?")
        if amount is None:
            return RawCommand(
                tool="clarify", question=f"How much should the {category.name} budget be?"
            )
        return RawCommand(tool="set_budget", category=category.name, amount=amount)

    paying_staff = _STAFF_PAY.search(t)
    kind = CategoryKind.INCOME if _INCOME.search(t) and not paying_staff else CategoryKind.EXPENSE
    category = _category(words, vocab, kind)
    if amount is None:
        if category is None and kind == CategoryKind.EXPENSE:
            return RawCommand(
                tool="unsupported",
                question="I can log things like “paid 180 for auto” or set budgets.",
            )
        return RawCommand(tool="clarify", question="How much was it?")

    return RawCommand(
        tool="add_transaction",
        amount=amount,
        kind=kind.value,
        category=category.name if category else None,
        account=_account(t, vocab),
        merchant=_merchant(t, category),
        date=_date(t, today),
    )
