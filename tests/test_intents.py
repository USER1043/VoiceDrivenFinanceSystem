from app.intent.detector import detect_intent, Intent


def test_update_budget_intent():
    text = "set food budget to 5000"
    assert detect_intent(text) == Intent.UPDATE_BUDGET


def test_add_expense_intent():
    text = "I spent 250 on food"
    assert detect_intent(text) == Intent.ADD_EXPENSE


def test_create_reminder_intent():
    text = "remind me to pay rent"
    assert detect_intent(text) == Intent.CREATE_REMINDER


def test_check_balance_intent():
    text = "how much balance left"
    assert detect_intent(text) == Intent.CHECK_BALANCE


def test_unknown_intent():
    text = "hello how are you"
    assert detect_intent(text) == Intent.UNKNOWN
