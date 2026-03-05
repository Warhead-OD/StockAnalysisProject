"""
Unit tests for metrics calculation.
"""

import pandas as pd
import pytest

from src.analysis import metrics


def test_compute_all_basic():
    """
    Test basic computation of metrics with valid input DataFrame.
    Verifies that expected keys are present in the result.
    """

    df = pd.DataFrame({
        "date": pd.date_range("2023-01-01", periods=3, freq="D"),
        "return": [0.01, -0.02, 0.03],
    })
    result = metrics.compute_all(df)
    assert "annualized_return" in result
    assert "sharpe_ratio" in result


def test_compute_all_missing_return():
    """
    Test that compute_all raises ValueError when 'return' column is missing.
    """
    
    df = pd.DataFrame({"date": [1, 2, 3]})
    with pytest.raises(ValueError):
        metrics.compute_all(df)

