import pytest
from risk.position_sizing import calculate_position_size, PositionSizingResult

def test_long_standard_risk_sizing():
    """
    Equity: 10,000, Risk: 1% ($100 budget).
    Entry: 100.0, Stop: 98.0 -> Stop distance: 2.0.
    Risk quantity: floor(100 / 2.0) = 50.
    Cash required: 50 * 100 = 5,000 <= 10,000.
    Expected quantity: 50.
    """
    res = calculate_position_size(
        equity=10000.0,
        entry_price=100.0,
        stop_price=98.0,
        risk_percent=0.01,
        cash_available=10000.0,
        side="LONG",
    )
    assert res.is_approved is True
    assert res.quantity == 50
    assert res.risk_budget == 100.0
    assert res.risk_per_unit == 2.0
    assert res.cash_required == 5000.0
    assert res.estimated_risk == 100.0
    assert res.rejection_reason is None

def test_short_standard_risk_sizing():
    """
    Equity: 10,000, Risk: 1% ($100 budget).
    Entry: 100.0, Stop: 102.0 -> Stop distance: 2.0.
    Risk quantity: floor(100 / 2.0) = 50.
    Cash required: 50 * 100 = 5,000 <= 10,000.
    Expected quantity: 50.
    """
    res = calculate_position_size(
        equity=10000.0,
        entry_price=100.0,
        stop_price=102.0,
        risk_percent=0.01,
        cash_available=10000.0,
        side="SHORT",
    )
    assert res.is_approved is True
    assert res.quantity == 50
    assert res.risk_budget == 100.0
    assert res.risk_per_unit == 2.0
    assert res.cash_required == 5000.0
    assert res.estimated_risk == 100.0
    assert res.rejection_reason is None

def test_sizing_capped_by_available_cash():
    """
    Equity: 100,000, Risk: 1% ($1,000 budget).
    Entry: 100.0, Stop: 99.0 -> Stop distance: 1.0.
    Risk quantity: floor(1000 / 1.0) = 1000 shares ($100,000 cash).
    Available cash: only 15,000 -> Cash quantity: floor(15000 / 100) = 150 shares.
    Expected quantity: 150 shares (capped by cash).
    """
    res = calculate_position_size(
        equity=100000.0,
        entry_price=100.0,
        stop_price=99.0,
        risk_percent=0.01,
        cash_available=15000.0,
        side="LONG",
    )
    assert res.is_approved is True
    assert res.quantity == 150
    assert res.cash_required == 15000.0
    assert res.estimated_risk == 150.0  # 150 * $1.00 risk

def test_insufficient_cash_never_forces_one_unit():
    """
    Equity: 50.0, Risk: 1% ($0.50 budget).
    Entry: 100.0, Stop: 95.0.
    Cash available: 50.0.
    Entry price is 100.0, so cash allows 0 shares.
    Must reject and NOT force 1 share.
    """
    res = calculate_position_size(
        equity=50.0,
        entry_price=100.0,
        stop_price=95.0,
        risk_percent=0.01,
        cash_available=50.0,
        side="LONG",
    )
    assert res.is_approved is False
    assert res.quantity == 0
    assert "Calculated quantity is 0" in res.rejection_reason

def test_insufficient_risk_budget_never_forces_one_unit():
    """
    Equity: 1,000.0, Risk: 0.1% ($1.00 budget).
    Entry: 100.0, Stop: 95.0 -> Risk per share: $5.00.
    Risk quantity = floor(1.00 / 5.00) = 0.
    Must reject and NOT force 1 share.
    """
    res = calculate_position_size(
        equity=1000.0,
        entry_price=100.0,
        stop_price=95.0,
        risk_percent=0.001,
        cash_available=1000.0,
        side="LONG",
    )
    assert res.is_approved is False
    assert res.quantity == 0
    assert "Calculated quantity is 0" in res.rejection_reason

def test_invalid_stop_direction_long():
    """For LONG, stop_price >= entry_price is invalid and rejected."""
    res = calculate_position_size(
        equity=10000.0,
        entry_price=100.0,
        stop_price=105.0,
        risk_percent=0.01,
        side="LONG",
    )
    assert res.is_approved is False
    assert res.quantity == 0
    assert "Invalid stop for LONG" in res.rejection_reason

def test_invalid_stop_direction_short():
    """For SHORT, stop_price <= entry_price is invalid and rejected."""
    res = calculate_position_size(
        equity=10000.0,
        entry_price=100.0,
        stop_price=95.0,
        risk_percent=0.01,
        side="SHORT",
    )
    assert res.is_approved is False
    assert res.quantity == 0
    assert "Invalid stop for SHORT" in res.rejection_reason

def test_zero_stop_distance_rejected():
    """Stop equal to entry price must be rejected."""
    res = calculate_position_size(
        equity=10000.0,
        entry_price=100.0,
        stop_price=100.0,
        risk_percent=0.01,
        side="LONG",
    )
    assert res.is_approved is False
    assert res.quantity == 0

def test_non_positive_equity_rejected():
    """Zero or negative equity must fail closed."""
    res_zero = calculate_position_size(
        equity=0.0,
        entry_price=100.0,
        stop_price=95.0,
        risk_percent=0.01,
    )
    assert res_zero.is_approved is False
    assert res_zero.quantity == 0
    assert "Non-positive equity" in res_zero.rejection_reason

    res_neg = calculate_position_size(
        equity=-500.0,
        entry_price=100.0,
        stop_price=95.0,
        risk_percent=0.01,
    )
    assert res_neg.is_approved is False
    assert res_neg.quantity == 0

def test_invalid_risk_percent_rejected():
    """risk_percent must be in (0, 1.0]."""
    for bad_pct in [0.0, -0.01, 1.5]:
        res = calculate_position_size(
            equity=10000.0,
            entry_price=100.0,
            stop_price=95.0,
            risk_percent=bad_pct,
        )
        assert res.is_approved is False
        assert res.quantity == 0
        assert "Invalid risk_percent" in res.rejection_reason

def test_max_position_units_cap():
    """max_position_units caps the final quantity."""
    res = calculate_position_size(
        equity=10000.0,
        entry_price=100.0,
        stop_price=98.0,
        risk_percent=0.01,  # would yield 50 units
        max_position_units=20,
    )
    assert res.is_approved is True
    assert res.quantity == 20

