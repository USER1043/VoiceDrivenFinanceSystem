import csv
import io

import pytest

from app import auth
from app.config import get_settings
from tests.conftest import make_settings
from tests.helpers import add_txn, category_id


def test_month_summary(client, seeded):
    add_txn(client, seeded, 20000, "Groceries", "2026-09-01T10:00:00+05:30")
    add_txn(client, seeded, 5000, "Tea & snacks", "2026-09-01T18:00:00+05:30")
    add_txn(client, seeded, 1500000, "Rent", "2026-09-05T09:00:00+05:30")
    add_txn(client, seeded, 999, None, "2026-09-30T23:59:00+05:30")
    add_txn(client, seeded, 5000000, "Salary", "2026-09-01T09:00:00+05:30", kind="income")
    add_txn(client, seeded, 40000, "Groceries", "2026-08-20T10:00:00+05:30")  # previous month
    food = category_id(seeded, "Food")
    client.put(f"/api/budgets/{food}", json={"amount_paise": 30000})

    s = client.get("/api/summary?month=2026-09").json()
    assert s["income_paise"] == 5000000
    assert s["expense_paise"] == 20000 + 5000 + 1500000 + 999
    assert s["previous_expense_paise"] == 40000
    assert s["by_category"] == [
        {"category_id": category_id(seeded, "Home"), "name": "Home", "spent_paise": 1500000},
        {"category_id": food, "name": "Food", "spent_paise": 25000},  # children rolled up
        {"category_id": None, "name": "Uncategorised", "spent_paise": 999},
    ]
    assert s["budgets"] == [
        {"category_id": food, "name": "Food", "amount_paise": 30000, "spent_paise": 25000}
    ]
    assert len(s["daily"]) == 30
    assert s["daily"][0] == {"day": "2026-09-01", "expense_paise": 25000}
    assert s["daily"][29] == {"day": "2026-09-30", "expense_paise": 999}


def test_empty_month_summary(client, seeded):
    s = client.get("/api/summary?month=2027-02").json()
    assert s["expense_paise"] == 0
    assert s["by_category"] == []
    assert len(s["daily"]) == 28


def test_csv_export(client, seeded):
    add_txn(
        client, seeded, 12345, "Groceries", "2026-09-01T10:05:00+05:30", merchant="=HYPERLINK(1)"
    )
    response = client.get("/api/export/transactions.csv")
    assert response.status_code == 200
    assert "attachment" in response.headers["content-disposition"]
    rows = list(csv.DictReader(io.StringIO(response.text)))
    assert rows == [
        {
            "date": "2026-09-01",
            "time": "10:05",
            "type": "expense",
            "amount_inr": "123.45",
            "account": "UPI",
            "category": "Food > Groceries",
            "merchant": "'=HYPERLINK(1)",
            "note": "",
            "source": "manual",
        }
    ]


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/accounts"),
        ("POST", "/api/accounts"),
        ("GET", "/api/categories"),
        ("PATCH", "/api/categories/1"),
        ("GET", "/api/transactions"),
        ("POST", "/api/transactions"),
        ("DELETE", "/api/transactions/1"),
        ("GET", "/api/budgets"),
        ("PUT", "/api/budgets/1"),
        ("GET", "/api/summary"),
        ("GET", "/api/export/transactions.csv"),
    ],
)
def test_everything_requires_login(client, seeded, method, path):
    settings = make_settings(auth_mode="password", owner_password_hash=auth.hash_password("x" * 12))
    client.app.dependency_overrides[get_settings] = lambda: settings
    assert client.request(method, path, json={}).status_code == 401
