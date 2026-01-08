import pytest
from app.utils.validation import validate_budget_slots


def test_valid_budget_slots():
    slots = {"category": "food", "amount": 5000}
    validate_budget_slots(slots)  # should not raise


def test_missing_category():
    slots = {"category": None, "amount": 5000}
    with pytest.raises(ValueError):
        validate_budget_slots(slots)


def test_missing_amount():
    slots = {"category": "food", "amount": None}
    with pytest.raises(ValueError):
        validate_budget_slots(slots)


def test_negative_amount():
    slots = {"category": "food", "amount": -100}
    with pytest.raises(ValueError):
        validate_budget_slots(slots)
