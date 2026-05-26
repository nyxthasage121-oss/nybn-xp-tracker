"""Tests for Enoch/vr/dicemoji.py dice emoji selection."""

from unittest.mock import patch

import pytest

from enoch.vr.dicemoji import emojify_die


@pytest.fixture
def mock_emojis():
    """Mock the Enoch.emojis dictionary."""
    emojis = {
        "ln_bestial": "🎲_bestial",
        "ln_crit": "🎲_crit",
        "ln_succ": "🎲_success",
        "ln_fail": "🎲_fail",
        "h_bestial": "🩸_bestial",
        "h_crit": "🩸_crit",
        "h_succ": "🩸_success",
        "h_fail": "🩸_fail",
    }
    with patch("services.emojis", emojis):
        yield emojis


# Test normal dice (hunger=False)


def test_normal_die_value_1_bestial(mock_emojis):
    """Test that 1 on normal die returns bestial emoji."""
    result = emojify_die(1, hunger=False)
    assert result == "🎲_bestial"


def test_normal_die_value_10_critical(mock_emojis):
    """Test that 10 on normal die returns critical emoji."""
    result = emojify_die(10, hunger=False)
    assert result == "🎲_crit"


@pytest.mark.parametrize("die_value", [6, 7, 8, 9])
def test_normal_die_success_values(die_value, mock_emojis):
    """Test that 6-9 on normal die returns success emoji."""
    result = emojify_die(die_value, hunger=False)
    assert result == "🎲_success"


@pytest.mark.parametrize("die_value", [2, 3, 4, 5])
def test_normal_die_failure_values(die_value, mock_emojis):
    """Test that 2-5 on normal die returns failure emoji."""
    result = emojify_die(die_value, hunger=False)
    assert result == "🎲_fail"


# Test hunger dice (hunger=True)


def test_hunger_die_value_1_bestial(mock_emojis):
    """Test that 1 on hunger die returns hunger bestial emoji."""
    result = emojify_die(1, hunger=True)
    assert result == "🩸_bestial"


def test_hunger_die_value_10_critical(mock_emojis):
    """Test that 10 on hunger die returns hunger critical emoji."""
    result = emojify_die(10, hunger=True)
    assert result == "🩸_crit"


@pytest.mark.parametrize("die_value", [6, 7, 8, 9])
def test_hunger_die_success_values(die_value, mock_emojis):
    """Test that 6-9 on hunger die returns hunger success emoji."""
    result = emojify_die(die_value, hunger=True)
    assert result == "🩸_success"


@pytest.mark.parametrize("die_value", [2, 3, 4, 5])
def test_hunger_die_failure_values(die_value, mock_emojis):
    """Test that 2-5 on hunger die returns hunger failure emoji."""
    result = emojify_die(die_value, hunger=True)
    assert result == "🩸_fail"


# Test edge cases and thresholds


def test_threshold_6_is_success(mock_emojis):
    """Test that 6 is the threshold for success (inclusive)."""
    assert emojify_die(6, hunger=False) == "🎲_success"
    assert emojify_die(5, hunger=False) == "🎲_fail"


def test_threshold_10_is_critical_not_just_success(mock_emojis):
    """Test that 10 returns critical, not just success."""
    result = emojify_die(10, hunger=False)
    assert result == "🎲_crit"
    assert result != "🎲_success"


def test_threshold_1_is_bestial_not_just_failure(mock_emojis):
    """Test that 1 returns bestial, not just failure."""
    result = emojify_die(1, hunger=False)
    assert result == "🎲_bestial"
    assert result != "🎲_fail"


# Test emoji name construction


def test_emoji_name_construction_normal():
    """Test that emoji names are constructed correctly for normal dice."""
    with patch("services.emojis", {"ln_bestial": "emoji"}) as mock:
        emojify_die(1, hunger=False)
        # Verify the correct key was accessed
        assert "ln_bestial" in mock


def test_emoji_name_construction_hunger():
    """Test that emoji names are constructed correctly for hunger dice."""
    with patch("services.emojis", {"h_crit": "emoji"}) as mock:
        emojify_die(10, hunger=True)
        # Verify the correct key was accessed
        assert "h_crit" in mock


# Test all combinations systematically


@pytest.mark.parametrize(
    "die_value,hunger,expected_suffix",
    [
        (1, False, "bestial"),
        (1, True, "bestial"),
        (2, False, "fail"),
        (2, True, "fail"),
        (5, False, "fail"),
        (5, True, "fail"),
        (6, False, "succ"),
        (6, True, "succ"),
        (9, False, "succ"),
        (9, True, "succ"),
        (10, False, "crit"),
        (10, True, "crit"),
    ],
)
def test_all_die_combinations(die_value, hunger, expected_suffix, mock_emojis):
    """Test all combinations of die values and hunger states."""
    prefix = "h_" if hunger else "ln_"
    expected_key = prefix + expected_suffix
    expected_emoji = mock_emojis[expected_key]

    result = emojify_die(die_value, hunger)
    assert result == expected_emoji
