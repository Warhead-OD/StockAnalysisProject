"""Unit tests for metrics calculation.
"""

import pandas as pd
import pytest

from src.analysis import metrics


def test_compute_all_basic():
    df = pd.DataFrame({
        "date": pd.date_range("2023-01-01", periods=3, freq="D"),
        "return": [0.01, -0.02, 0.03],
    })
    result = metrics.compute_all(df)
    assert "annualized_return" in result
    assert "sharpe_ratio" in result


def test_compute_all_missing_return():
    df = pd.DataFrame({"date": [1, 2, 3]})
    with pytest.raises(ValueError):
        metrics.compute_all(df)

