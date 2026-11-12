from src.config.validation import validate_task_input


def test_empty_task_rejected():
    result = validate_task_input("   ")
    assert result.ok is False
    assert any("required" in e.lower() for e in result.errors)


def test_valid_task_trimmed():
    result = validate_task_input("  Plan my week  ", background="  ctx  ")
    assert result.ok is True
    assert result.task == "Plan my week"
    assert result.background == "ctx"


def test_task_too_long_rejected():
    result = validate_task_input("x" * 50, max_length=10)
    assert result.ok is False
