"""Spending questions (answered straight away) and budget alerts (M3)."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.models import PendingAction
from tests.helpers import account_id, add_txn, category_id

NOW = datetime.now(ZoneInfo("Asia/Kolkata"))
THIS_MONTH = NOW.replace(day=1, hour=12, minute=0, second=0, microsecond=0).isoformat()
LAST_MONTH = (NOW.replace(day=1) - timedelta(days=3)).replace(hour=12).isoformat()


def _ask(client, text):
    response = client.post("/api/commands", json={"text": text})
    assert response.status_code == 200, response.text
    out = response.json()
    assert out["status"] == "answer", out
    assert out["action"] is None
    return out


def _budget(client, seeded, name, rupees):
    response = client.put(
        f"/api/budgets/{category_id(seeded, name)}", json={"amount_paise": rupees * 100}
    )
    assert response.status_code == 200, response.text


def test_total_for_a_category(client, seeded):
    add_txn(client, seeded, 45000, "Groceries", THIS_MONTH)
    add_txn(client, seeded, 30000, "Eating out", THIS_MONTH)
    add_txn(client, seeded, 99900, "Groceries", LAST_MONTH)  # other month: not counted
    add_txn(client, seeded, 5000, "Fuel", THIS_MONTH)  # other category
    out = _ask(client, "how much did I spend on food this month")
    assert out["message"] == "You spent ₹750 on Food this month, across 2 payments."
    assert out["answer"]["total_paise"] == 75000
    assert [(i["label"], i["amount_paise"]) for i in out["answer"]["items"]] == [
        ("Groceries", 45000),
        ("Eating out", 30000),
    ]
    assert seeded.scalars(select(PendingAction)).all() == []  # questions write nothing


def test_total_mentions_the_budget(client, seeded):
    _budget(client, seeded, "Food", 1000)
    add_txn(client, seeded, 25000, "Groceries", THIS_MONTH)
    out = _ask(client, "how much did I spend on food")
    assert out["message"] == "You spent ₹250 on Food this month. That's 25% of your ₹1,000 budget."


def test_nothing_spent(client, seeded):
    out = _ask(client, "how much did I spend on fuel last month?")
    assert out["message"] == "You haven't spent anything on Fuel last month."
    assert out["answer"]["total_paise"] == 0


def test_income_and_account_filters(client, seeded):
    add_txn(client, seeded, 8500000, "Salary", THIS_MONTH, kind="income")
    add_txn(client, seeded, 2000, "Tea & snacks", THIS_MONTH, account_id=account_id(seeded, "Cash"))
    add_txn(client, seeded, 3000, "Tea & snacks", THIS_MONTH)
    assert _ask(client, "how much did I earn this month")["message"] == (
        "You received ₹85,000 this month."
    )
    assert _ask(client, "how much did I spend in cash this month")["message"] == (
        "You spent ₹20 using Cash this month."
    )


def test_merchant_search(client, seeded):
    add_txn(client, seeded, 12000, "Eating out", THIS_MONTH, merchant="Chai Point")
    add_txn(client, seeded, 8000, "Tea & snacks", THIS_MONTH, merchant="chai point")
    add_txn(client, seeded, 50000, "Groceries", THIS_MONTH, merchant="DMart")
    out = _ask(client, "how much did I spend at chai point this month")
    assert out["message"] == "You spent ₹200 at Chai Point this month, across 2 payments."
    top = _ask(client, "top merchants this month")
    assert (
        top["message"] == "This month, you spent the most at DMart (₹500), then Chai Point (₹200)."
    )


def test_top_categories(client, seeded):
    add_txn(client, seeded, 40000, "Groceries", THIS_MONTH)
    add_txn(client, seeded, 20000, "Eating out", THIS_MONTH)
    add_txn(client, seeded, 30000, "Fuel", THIS_MONTH)
    add_txn(client, seeded, 10000, None, THIS_MONTH)
    out = _ask(client, "where did my money go this month")
    assert out["message"] == (
        "This month, most went on Food (₹600), then Transport (₹300) and Uncategorised (₹100)."
    )
    assert [i["label"] for i in out["answer"]["items"]] == ["Food", "Transport", "Uncategorised"]


def test_budget_questions(client, seeded):
    assert _ask(client, "how's my budget")["message"] == (
        "You haven't set any budgets yet. Try “set food budget to 5000”."
    )
    _budget(client, seeded, "Food", 1000)
    _budget(client, seeded, "Transport", 500)
    add_txn(client, seeded, 30000, "Groceries", THIS_MONTH)
    add_txn(client, seeded, 60000, "Fuel", THIS_MONTH)
    out = _ask(client, "how much is left in my food budget")
    assert out["message"] == (
        "This month, you've used ₹300 of your ₹1,000 Food budget (30%): ₹700 left."
    )
    overall = _ask(client, "how are my budgets doing")
    assert overall["message"] == (
        "This month, 1 of 2 budgets are over. Transport: ₹100 over. Food: ₹700 left."
    )
    assert [(i["label"], i["limit_paise"]) for i in overall["answer"]["items"]] == [
        ("Transport", 50000),
        ("Food", 100000),
    ]
    assert _ask(client, "how much is left in my shopping budget")["message"].startswith(
        "You haven't set a Shopping budget."
    )


def test_other_users_data_is_not_counted(client, seeded, request):
    add_txn(client, seeded, 45000, "Groceries", THIS_MONTH)  # the admin's, in dev mode
    request.getfixturevalue("accounts_mode")
    signup = client.post(
        "/api/auth/signup",
        json={"email": "friend@example.com", "password": "a long friend passphrase"},
    )
    assert signup.status_code == 204, signup.text
    assert _ask(client, "how much did I spend this month")["message"] == (
        "You haven't spent anything this month."
    )


# ---------- Budget alerts ----------


def test_alerts_when_crossing_80_and_100_percent(client, seeded):
    _budget(client, seeded, "Food", 1000)
    first = add_txn(client, seeded, 50000, "Groceries", THIS_MONTH)
    assert first["alerts"] == []
    second = add_txn(client, seeded, 35000, "Eating out", THIS_MONTH)
    assert [(a["level"], a["name"], a["message"]) for a in second["alerts"]] == [
        ("warning", "Food", "You've used 85% of your Food budget (₹850 of ₹1,000).")
    ]
    third = add_txn(client, seeded, 5000, "Groceries", THIS_MONTH)
    assert third["alerts"] == []  # still between 80% and 100%: no repeat
    fourth = add_txn(client, seeded, 20000, "Groceries", THIS_MONTH)
    assert [(a["level"], a["message"]) for a in fourth["alerts"]] == [
        ("over", "You're ₹100 over your Food budget.")
    ]
    assert add_txn(client, seeded, 1000, "Groceries", THIS_MONTH)["alerts"] == []


def test_alert_for_subcategory_and_parent_budgets(client, seeded):
    _budget(client, seeded, "Food", 10000)
    _budget(client, seeded, "Groceries", 1000)
    out = add_txn(client, seeded, 100000, "Groceries", THIS_MONTH)
    assert [(a["name"], a["level"]) for a in out["alerts"]] == [("Groceries", "over")]
    assert out["alerts"][0]["message"] == "You've used all of your Groceries budget."


def test_alerts_name_a_past_month_and_skip_income(client, seeded):
    _budget(client, seeded, "Food", 1000)
    out = add_txn(client, seeded, 90000, "Groceries", LAST_MONTH)
    month = datetime.fromisoformat(LAST_MONTH).strftime("%B")
    assert out["alerts"][0]["message"].startswith(
        f"You've used 90% of your Food budget for {month}"
    )
    income = add_txn(client, seeded, 90000, "Salary", THIS_MONTH, kind="income")
    assert income["alerts"] == []


def test_voice_confirm_speaks_the_alert(client, seeded):
    _budget(client, seeded, "Transport", 200)
    out = client.post("/api/commands", json={"text": "paid 180 for auto"}).json()
    confirmed = client.post(f"/api/pending-actions/{out['action']['id']}/confirm").json()
    assert confirmed["message"] == (
        "Saved ₹180. You've used 90% of your Transport budget (₹180 of ₹200)."
    )
    assert confirmed["alerts"][0]["level"] == "warning"


def test_budget_close_to_its_limit(client, seeded):
    _budget(client, seeded, "Food", 1000)
    add_txn(client, seeded, 81500, "Groceries", THIS_MONTH)
    assert _ask(client, "how's my budget")["message"] == (
        "This month, your budget is close to its limit. Food: ₹185 left."
    )
    assert _ask(client, "how much did I spend on food")["message"].endswith(
        "That's 82% of your ₹1,000 budget."  # rounded like the app's meters
    )
