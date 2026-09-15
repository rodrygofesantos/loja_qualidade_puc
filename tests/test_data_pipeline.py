import pandas as pd
import pytest
from django.test import override_settings

from laboratorio.data_pipeline import aggregate_change_metrics, inspect_raw, prepare_data


@pytest.mark.engenharia
def test_churn_and_frequency_do_not_double_count_change_rows():
    events = pd.DataFrame([
        {"change_id": "A", "module": "checkout", "version": 1, "commit_id": "C1", "lines_added": 10, "lines_removed": 2},
        {"change_id": "A", "module": "checkout", "version": 1, "commit_id": "C1", "lines_added": 10, "lines_removed": 2},
        {"change_id": "B", "module": "checkout", "version": 1, "commit_id": "C1", "lines_added": 3, "lines_removed": 1},
        {"change_id": "C", "module": "checkout", "version": 1, "commit_id": "C2", "lines_added": 4, "lines_removed": 0},
    ])
    result = aggregate_change_metrics(events).iloc[0]
    assert result.churn_lines == 20
    assert result.commit_frequency == 2


@pytest.mark.engenharia
def test_preparation_is_reproducible_and_preserves_traceability(tmp_path):
    with override_settings(BASE_DIR=tmp_path):
        first, first_log = prepare_data(force=True)
        second, second_log = prepare_data(force=True)
        assert first_log["raw_rows"] == 1010
        assert first_log["treated_rows"] == 1000
        assert first_log["issues"]["duplicate_record_ids"] == 10
        assert first_log == second_log
        pd.testing.assert_frame_equal(first, second)
        assert first["defect_next_version"].isna().sum() == 0
        assert first["record_id"].is_unique
        assert (~first["link_consistent"]).sum() > 0

