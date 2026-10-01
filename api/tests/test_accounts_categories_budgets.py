from tests.helpers import account_id, category_id


def test_new_default_account_replaces_old(client, seeded):
    created = client.post(
        "/api/accounts", json={"name": "HDFC", "kind": "bank", "is_default": True}
    )
    assert created.status_code == 201
    accounts = {a["name"]: a for a in client.get("/api/accounts").json()}
    assert accounts["HDFC"]["is_default"] is True
    assert accounts["UPI"]["is_default"] is False


def test_default_account_rules(client, seeded):
    upi = account_id(seeded)
    assert client.patch(f"/api/accounts/{upi}", json={"archived": True}).status_code == 422
    assert client.patch(f"/api/accounts/{upi}", json={"is_default": False}).status_code == 422
    cash = account_id(seeded, "Cash")
    assert client.patch(f"/api/accounts/{cash}", json={"is_default": True}).status_code == 200
    assert client.patch(f"/api/accounts/{upi}", json={"archived": True}).status_code == 200


def test_duplicate_account_name_conflicts(client, seeded):
    response = client.post("/api/accounts", json={"name": "UPI", "kind": "upi"})
    assert response.status_code == 409


def test_create_subcategory_with_normalised_aliases(client, seeded):
    response = client.post(
        "/api/categories",
        json={
            "name": "Biryani",
            "kind": "expense",
            "parent_id": category_id(seeded, "Food"),
            "aliases": ["  Biryani ", "BIRYANI", "dum   biryani"],
        },
    )
    assert response.status_code == 201
    assert response.json()["aliases"] == ["biryani", "dum biryani"]


def test_category_nesting_rules(client, seeded):
    groceries = category_id(seeded, "Groceries")
    salary = category_id(seeded, "Salary")
    food = category_id(seeded, "Food")
    deep = {"name": "Veg", "kind": "expense", "parent_id": groceries}
    assert client.post("/api/categories", json=deep).status_code == 422  # max one level
    wrong_kind = {"name": "Bonus", "kind": "expense", "parent_id": salary}
    assert client.post("/api/categories", json=wrong_kind).status_code == 422
    # A parent with children can't itself become a child.
    transport = category_id(seeded, "Transport")
    assert client.patch(f"/api/categories/{food}", json={"parent_id": transport}).status_code == 422
    assert client.patch(f"/api/categories/{food}", json={"parent_id": food}).status_code == 422


def test_alias_must_be_unique(client, seeded):
    response = client.post(
        "/api/categories", json={"name": "Drinks", "kind": "expense", "aliases": ["chai"]}
    )
    assert response.status_code == 409
    assert "Tea & snacks" in response.json()["detail"]


def test_duplicate_category_name_conflicts(client, seeded):
    response = client.post("/api/categories", json={"name": "Food", "kind": "expense"})
    assert response.status_code == 409


def test_archiving_a_group_archives_children(client, seeded):
    food = category_id(seeded, "Food")
    groceries = category_id(seeded, "Groceries")
    assert client.patch(f"/api/categories/{food}", json={"archived": True}).status_code == 200
    by_id = {c["id"]: c for c in client.get("/api/categories").json()}
    assert by_id[groceries]["archived"] is True
    restore_child = client.patch(f"/api/categories/{groceries}", json={"archived": False})
    assert restore_child.status_code == 422
    assert client.patch(f"/api/categories/{food}", json={"archived": False}).status_code == 200
    assert client.patch(f"/api/categories/{groceries}", json={"archived": False}).status_code == 200


def test_budget_lifecycle(client, seeded):
    food = category_id(seeded, "Food")
    assert client.put(f"/api/budgets/{food}", json={"amount_paise": 600000}).status_code == 200
    assert (
        client.put(f"/api/budgets/{food}", json={"amount_paise": 700000}).json()["amount_paise"]
        == 700000
    )
    assert client.get("/api/budgets").json() == [{"category_id": food, "amount_paise": 700000}]
    assert client.delete(f"/api/budgets/{food}").status_code == 204
    assert client.delete(f"/api/budgets/{food}").status_code == 404


def test_budget_only_for_expense_categories(client, seeded):
    salary = category_id(seeded, "Salary")
    assert client.put(f"/api/budgets/{salary}", json={"amount_paise": 100}).status_code == 422
