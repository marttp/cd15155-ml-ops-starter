"""Quality gates reject excessive or unavailable drift scores."""
import pytest

from scripts.run_deepchecks import assess_scores

PARAMS = {"property_drift_threshold": 0.5, "prediction_drift_threshold": 0.6}


@pytest.mark.parametrize("property_score,prediction_score", [(0.51, 0.2), (0.2, 0.61), (float("nan"), 0.2)])
def test_bad_drift_rejected(property_score, prediction_score):
    with pytest.raises(ValueError):
        assess_scores(property_score, prediction_score, PARAMS)


def test_threshold_boundary_passes():
    assert assess_scores(0.5, 0.6, PARAMS) == {"property_drift": 0.5, "prediction_drift": 0.6}
