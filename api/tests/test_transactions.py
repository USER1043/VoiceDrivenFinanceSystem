import pytest
from sqlalchemy import select

from app.models import Account, AccountKind, AuditLog, User
from tests.helpers import account_id, add_txn, category_id


def test_create_get_update_delete_with_audit(client, seeded):
    txn = add_txn(client, seeded, merchant="DMart", note="weekly")
    assert txn["amount_paise"] == 10000
    assert txn["source"] == "manual"
    assert txn["occurred_at"].endswith("+05:30")

    assert client.get(f"/api/transactions/{txn['id']}").json()["merchant"] == "DMart"

    patched = client.patch(f"/api/transactions/{txn['id']}", json={"amount_paise": 12550})
    assert patched.status_code == 200
    assert patched.json()["amount_paise"] == 12550
    assert patched.json()["merchant"] == "DMart"  # untouched fields stay

    assert client.delete(f"/api/transactions/{txn['id']}").status_code == 204
    assert client.get(f"/api/transactions/{txn['id']}").status_code == 404

    actions = seeded.scalars(
        select(AuditLog.action).where(AuditLog.entity == "transaction").order_by(AuditLog.id)
    ).all()
    assert actions == ["create", "update", "delete"]
    update = seeded.scalar(select(AuditLog).where(AuditLog.action == "update"))
    assert update.before["amount_paise"] == 10000
    assert update.after["amount_paise"] == 12550


@pytest.mark.parametrize(
    "override",
    [
        {"amount_paise": 0},
        {"amount_paise": -5},
        {"amount_paise": 10**12},
        {"occurred_at": "2026-09-15T12:00:00"},  # no timezone
    ],
    ids=["zero", "negative", "absurd", "naive-datetime"],
)
def test_rejects_bad_input(client, seeded, override):
    body = {
        "amount_paise": 100,
        "occurred_at": "2026-09-15T12:00:00+05:30",
        "account_id": account_id(seeded),
        **override,
    }
    assert client.post("/api/transactions", json=body).status_code == 422


def test_category_must_match_kind(client, seeded):
    body = {
        "kind": "income",
        "amount_paise": 100,
        "occurred_at": "2026-09-15T12:00:00+05:30",
        "account_id": account_id(seeded),
        "category_id": category_id(seeded, "Groceries"),
    }
    response = client.post("/api/transactions", json=body)
    assert response.status_code == 422
    assert "expense" in response.json()["detail"]


def test_cannot_use_another_users_account(client, seeded):
    other = User(email="other@example.com")
    seeded.add(other)
    seeded.flush()
    foreign = Account(user_id=other.id, name="Theirs", kind=AccountKind.CASH)
    seeded.add(foreign)
    seeded.flush()
    body = {
        "amount_paise": 100,
        "occurred_at": "2026-09-15T12:00:00+05:30",
        "account_id": foreign.id,
    }
    assert client.post("/api/transactions", json=body).status_code == 404


def test_archived_account_blocks_new_but_allows_editing_old(client, seeded):
    cash = account_id(seeded, "Cash")
    txn = add_txn(client, seeded, account_id=cash)
    assert client.patch(f"/api/accounts/{cash}", json={"archived": True}).status_code == 200
    body = {"amount_paise": 100, "occurred_at": "2026-09-15T12:00:00+05:30", "account_id": cash}
    assert client.post("/api/transactions", json=body).status_code == 422
    assert client.patch(f"/api/transactions/{txn['id']}", json={"note": "fix"}).status_code == 200


def test_patch_nulls(client, seeded):
    txn = add_txn(client, seeded)
    cleared = client.patch(f"/api/transactions/{txn['id']}", json={"category_id": None})
    assert cleared.status_code == 200
    assert cleared.json()["category_id"] is None
    assert (
        client.patch(f"/api/transactions/{txn['id']}", json={"amount_paise": None}).status_code
        == 422
    )


def test_month_filter_uses_owner_timezone(client, seeded):
    late_sept = add_txn(client, seeded, when="2026-09-30T23:30:00+05:30")
    early_oct = add_txn(client, seeded, when="2026-10-01T00:10:00+05:30")  # still 30 Sep in UTC
    sept = [t["id"] for t in client.get("/api/transactions?month=2026-09").json()["items"]]
    octo = [t["id"] for t in client.get("/api/transactions?month=2026-10").json()["items"]]
    assert sept == [late_sept["id"]]
    assert octo == [early_oct["id"]]


def test_filters_and_ordering(client, seeded):
    chai = add_txn(
        client,
        seeded,
        category="Tea & snacks",
        merchant="Chaiwala",
        when="2026-09-02T09:00:00+05:30",
    )
    rent = add_txn(client, seeded, category="Rent", when="2026-09-01T09:00:00+05:30")
    pct = add_txn(
        client, seeded, category=None, note="100% legit", when="2026-09-03T09:00:00+05:30"
    )

    page = client.get("/api/transactions?month=2026-09").json()
    assert [t["id"] for t in page["items"]] == [pct["id"], chai["id"], rent["id"]]  # newest first
    assert page["total"] == 3

    food = client.get(f"/api/transactions?category_id={category_id(seeded, 'Food')}").json()
    assert [t["id"] for t in food["items"]] == [chai["id"]]  # parent includes children

    assert client.get("/api/transactions?q=chaiw").json()["total"] == 1
    assert client.get("/api/transactions?q=%25").json()["total"] == 1  # literal %, not wildcard
    assert client.get("/api/transactions?uncategorised=true").json()["items"][0]["id"] == pct["id"]

    paged = client.get("/api/transactions?limit=2&offset=2").json()
    assert [t["id"] for t in paged["items"]] == [rent["id"]]
    assert paged["total"] == 3


def test_bad_month_is_rejected(client, seeded):
    assert client.get("/api/transactions?month=2026-13").status_code == 422
