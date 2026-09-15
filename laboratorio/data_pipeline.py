import json
from pathlib import Path

import numpy as np
import pandas as pd
from django.conf import settings


SEED = 20260615
BASE_DATE = "2026-06-15"
MODULES = ["checkout", "cupons", "carrinho", "estoque", "pagamento"] + [f"modulo_{i:02d}" for i in range(6, 51)]
FEATURES = ["churn_lines", "commit_frequency", "size_loc", "previous_defects"]


def data_paths():
    base = Path(settings.BASE_DIR)
    return {
        "raw": base / "data/raw/module_versions.csv",
        "events": base / "data/raw/change_events.csv",
        "treated": base / "data/treated/module_versions.csv",
        "log": base / "data/treated/preparation_log.json",
    }


def aggregate_change_metrics(events):
    required = {"change_id", "module", "version", "commit_id", "lines_added", "lines_removed"}
    missing = required.difference(events.columns)
    if missing:
        raise ValueError(f"Colunas ausentes: {', '.join(sorted(missing))}")
    unique_changes = events.drop_duplicates(subset=["change_id"]).copy()
    unique_changes["churn_part"] = unique_changes["lines_added"] + unique_changes["lines_removed"]
    return (
        unique_changes.groupby(["module", "version"], as_index=False)
        .agg(churn_lines=("churn_part", "sum"), commit_frequency=("commit_id", "nunique"))
        .sort_values(["version", "module"])
        .reset_index(drop=True)
    )


def generate_synthetic_data(force=False):
    paths = data_paths()
    for path in paths.values():
        path.parent.mkdir(parents=True, exist_ok=True)
    if paths["raw"].exists() and paths["events"].exists() and not force:
        return paths

    rng = np.random.default_rng(SEED)
    events = []
    rows = []
    previous = {module: 0 for module in MODULES}
    module_effect = {module: float(rng.normal(0, 0.45)) for module in MODULES}
    change_counter = 1
    for version in range(1, 21):
        for module_index, module in enumerate(MODULES, start=1):
            frequency = int(max(1, rng.poisson(3 + module_index % 4)))
            size_loc = int(180 + module_index * 31 + version * 7 + rng.integers(0, 160))
            churn = 0
            commit_ids = []
            for commit_no in range(frequency):
                commit_id = f"SIM-COMMIT-{version:02d}{module_index:02d}{commit_no:02d}"
                commit_ids.append(commit_id)
                added = int(rng.integers(1, 65))
                removed = int(rng.integers(0, 42))
                churn += added + removed
                events.append(
                    {
                        "change_id": f"SIM-CHANGE-{change_counter:05d}",
                        "module": module,
                        "version": version,
                        "commit_id": commit_id,
                        "lines_added": added,
                        "lines_removed": removed,
                    }
                )
                change_counter += 1
            logit = -3.8 + 0.0065 * churn + 0.16 * frequency + 0.00035 * size_loc + 0.34 * previous[module] + module_effect[module] + float(rng.normal(0, 0.65))
            chance = 1 / (1 + np.exp(-logit))
            label = int(rng.binomial(1, min(0.94, max(0.03, chance))))
            defect_id = f"SIM-DEF-{version:02d}{module_index:02d}" if label else ""
            declared_fix = bool(label and rng.random() < 0.65)
            linked_test = f"SIM-TEST-{version:02d}{module_index:02d}" if declared_fix and rng.random() < 0.78 else ""
            rows.append(
                {
                    "record_id": f"SIM-MV-{version:02d}{module_index:02d}",
                    "module": module,
                    "version": version,
                    "feature_available_version": version,
                    "label_available_version": version + 1,
                    "churn_lines": churn,
                    "commit_frequency": len(set(commit_ids)),
                    "size_loc": size_loc,
                    "previous_defects": previous[module],
                    "defect_next_version": label,
                    "defect_id": defect_id,
                    "severity": rng.choice(["baixa", "media", "alta", "critica"], p=[0.3, 0.38, 0.24, 0.08]) if label else "",
                    "declared_fix": declared_fix,
                    "linked_test": linked_test,
                    "source": "historico_sintetico",
                }
            )
            previous[module] = label

    raw = pd.DataFrame(rows)
    duplicate_rows = raw.sample(10, random_state=SEED)
    raw = pd.concat([raw, duplicate_rows], ignore_index=True)
    missing_indexes = raw.sample(12, random_state=SEED + 1).index
    raw.loc[missing_indexes, "churn_lines"] = np.nan
    inconsistent_indexes = raw[raw["declared_fix"]].sample(6, random_state=SEED + 2).index
    raw.loc[inconsistent_indexes, "defect_id"] = "SIM-DEF-INEXISTENTE"
    event_frame = pd.DataFrame(events)
    event_frame = pd.concat([event_frame, event_frame.sample(8, random_state=SEED)], ignore_index=True)
    raw.to_csv(paths["raw"], index=False, encoding="utf-8")
    event_frame.to_csv(paths["events"], index=False, encoding="utf-8")
    return paths


def inspect_raw():
    paths = generate_synthetic_data()
    raw = pd.read_csv(paths["raw"])
    issues = {
        "duplicate_record_ids": int(raw.duplicated(subset=["record_id"]).sum()),
        "missing_churn": int(raw["churn_lines"].isna().sum()),
        "inconsistent_defect_links": int((raw["defect_id"] == "SIM-DEF-INEXISTENTE").sum()),
        "declared_fixes_without_test": int(((raw["declared_fix"] == True) & raw["linked_test"].fillna("").eq("")).sum()),
    }
    return raw, issues


def prepare_data(force=False):
    paths = generate_synthetic_data(force=force)
    raw, issues = inspect_raw()
    treated = raw.drop_duplicates(subset=["record_id"], keep="first").copy()
    treated["churn_imputed"] = treated["churn_lines"].isna()
    module_medians = treated.groupby("module")["churn_lines"].transform("median")
    treated["churn_lines"] = treated["churn_lines"].fillna(module_medians).fillna(treated["churn_lines"].median()).round().astype(int)
    treated["link_consistent"] = ~treated["defect_id"].eq("SIM-DEF-INEXISTENTE")
    treated["fix_verified"] = treated["declared_fix"] & treated["linked_test"].fillna("").ne("") & treated["link_consistent"]
    treated = treated.sort_values(["version", "module"]).reset_index(drop=True)
    treated.to_csv(paths["treated"], index=False, encoding="utf-8")
    transformations = [
        "Duplicidades removidas por record_id, preservando o primeiro registro e o bruto.",
        "Churn ausente imputado pela mediana do mesmo modulo; fallback global apenas se o modulo nao tiver observacoes.",
        "Rotulos de defeito nunca foram imputados.",
        "Vinculos inexistentes foram marcados como inconsistentes, sem apagar a linha.",
        "Correcao declarada so e verificada quando ha defeito, teste e vinculo coerente.",
    ]
    log = {
        "seed": SEED,
        "base_date": BASE_DATE,
        "raw_rows": len(raw),
        "treated_rows": len(treated),
        "issues": issues,
        "transformations": transformations,
    }
    paths["log"].write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
    return treated, log

