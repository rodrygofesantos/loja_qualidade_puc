import json

import joblib
import pytest
from django.test import override_settings

from laboratorio.data_pipeline import FEATURES
from laboratorio.ml import CUTS, predict_risk, train_model


@pytest.mark.engenharia
def test_temporal_training_is_reproducible_and_has_no_future_feature(tmp_path):
    model_path = tmp_path / "artifacts/model/model.joblib"
    metadata_path = tmp_path / "artifacts/model/metadata.json"
    with override_settings(BASE_DIR=tmp_path, LAB_MODEL_PATH=model_path, LAB_MODEL_METADATA_PATH=metadata_path):
        first = train_model(force=True)
        first_artifact = joblib.load(model_path)
        first_coefficients = first_artifact["pipeline"].named_steps["classifier"].coef_.copy()
        second = train_model(force=True)
        second_artifact = joblib.load(model_path)
        assert first == second
        assert (first_coefficients == second_artifact["pipeline"].named_steps["classifier"].coef_).all()
        assert first["features"] == FEATURES
        assert "defect_next_version" not in first["features"]
        assert CUTS["train"][1] < CUTS["validation"][0] <= CUTS["validation"][1] < CUTS["test"][0]
        assert first["test_metrics"]["observations"] == 150


@pytest.mark.engenharia
def test_real_model_separates_demonstration_profiles():
    low, low_explanation, metadata = predict_risk({"churn_lines": 18, "commit_frequency": 1, "size_loc": 220, "previous_defects": 0})
    high, high_explanation, _ = predict_risk({"churn_lines": 980, "commit_frequency": 14, "size_loc": 3600, "previous_defects": 5})
    assert 0 <= low < 0.8
    assert 0.8 <= high <= 1
    assert set(low_explanation) == set(FEATURES)
    assert set(high_explanation) == set(FEATURES)
    assert metadata["model_version"] == "risk-logreg-v1"

