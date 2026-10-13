"""Check that promotion never aliases a model using another run's score."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from scripts import promote


def test_missing_evaluation_fails():
    client = Mock()
    client.get_experiment_by_name.return_value = None
    with pytest.raises(ValueError, match="does not exist"):
        promote.get_latest_f1(client, "missing")


def test_nonfinite_f1_fails():
    client = Mock()
    client.get_experiment_by_name.return_value = SimpleNamespace(experiment_id="1")
    client.search_runs.return_value = [SimpleNamespace(
        data=SimpleNamespace(metrics={"f1_weighted": float("nan")}),
        info=SimpleNamespace(run_id="evaluated"),
    )]
    with pytest.raises(ValueError, match="invalid"):
        promote.get_latest_f1(client, "evaluation")


def test_version_lineage_mismatch_does_not_promote():
    client = Mock()
    client.search_model_versions.return_value = [SimpleNamespace(version="2", run_id="other", status="READY")]
    with pytest.raises(ValueError, match="does not match"):
        promote.promote(client, "finbert", "evaluated")
    client.set_registered_model_alias.assert_not_called()


def test_latest_version_promoted_when_lineage_matches():
    client = Mock()
    client.search_model_versions.return_value = [
        SimpleNamespace(version="2", run_id="old", status="READY"),
        SimpleNamespace(version="10", run_id="evaluated", status="READY"),
    ]
    assert promote.promote(client, "finbert", "evaluated") == "10"
    client.set_registered_model_alias.assert_called_once_with("finbert", "production", "10")


@pytest.mark.parametrize("score,allowed", [(0.55, False), (0.56, True), (0.57, True)])
def test_threshold_boundary(monkeypatch, capsys, score, allowed):
    monkeypatch.setattr(promote, "MlflowClient", Mock())
    monkeypatch.setattr(promote, "get_latest_f1", lambda *_: ("evaluated", score))
    monkeypatch.setattr(promote, "load_params", lambda: {"f1_threshold": 0.56})
    alias = Mock()
    monkeypatch.setattr(promote, "promote", alias)
    promote.main()
    assert alias.called == allowed
    if not allowed:
        assert "Model not promoted" in capsys.readouterr().out
