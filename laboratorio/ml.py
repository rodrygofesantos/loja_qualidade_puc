import json
import platform
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from django.conf import settings
from sklearn.dummy import DummyClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix, f1_score, precision_score, recall_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from laboratorio.data_pipeline import FEATURES, SEED, prepare_data


MODEL_VERSION = "risk-logreg-v1"
CUTS = {"train": [1, 14], "validation": [15, 17], "test": [18, 20], "data_cut": 21}


def artifact_paths():
    return Path(settings.LAB_MODEL_PATH), Path(settings.LAB_MODEL_METADATA_PATH)


def _metrics(y_true, predicted):
    return {
        "confusion_matrix": confusion_matrix(y_true, predicted, labels=[0, 1]).tolist(),
        "precision": float(precision_score(y_true, predicted, zero_division=0)),
        "recall": float(recall_score(y_true, predicted, zero_division=0)),
        "f1": float(f1_score(y_true, predicted, zero_division=0)),
        "observations": int(len(y_true)),
    }


def train_model(force=False):
    model_path, metadata_path = artifact_paths()
    if model_path.exists() and metadata_path.exists() and not force:
        return json.loads(metadata_path.read_text(encoding="utf-8"))
    frame, _ = prepare_data(force=False)
    eligible = frame[frame["label_available_version"] <= CUTS["data_cut"]].copy()
    train = eligible[eligible["version"].between(*CUTS["train"])]
    validation = eligible[eligible["version"].between(*CUTS["validation"])]
    test = eligible[eligible["version"].between(*CUTS["test"])]
    pipeline = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            ("classifier", LogisticRegression(random_state=SEED, max_iter=1000, class_weight="balanced")),
        ]
    )
    pipeline.fit(train[FEATURES], train["defect_next_version"])
    baseline = DummyClassifier(strategy="most_frequent")
    baseline.fit(train[FEATURES], train["defect_next_version"])
    metadata = {
        "model_version": MODEL_VERSION,
        "seed": SEED,
        "features": FEATURES,
        "feature_timing": "Atributos disponiveis no fechamento da versao v; rotulo conhecido em v+1.",
        "cuts": CUTS,
        "validation_metrics": _metrics(validation["defect_next_version"], pipeline.predict(validation[FEATURES])),
        "test_metrics": _metrics(test["defect_next_version"], pipeline.predict(test[FEATURES])),
        "baseline_test_metrics": _metrics(test["defect_next_version"], baseline.predict(test[FEATURES])),
        "libraries": {"python": platform.python_version(), "scikit_learn": sklearn.__version__, "pandas": pd.__version__},
        "limitations": [
            "Dados inteiramente sinteticos e insuficientes para validar uso em producao.",
            "O escore nao e uma probabilidade calibrada de defeito em producao.",
            "Associacao estatistica nao demonstra causalidade.",
            "O teste final nao orientou hiperparametros nem candidatos demonstrativos.",
        ],
    }
    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"pipeline": pipeline, "features": FEATURES, "model_version": MODEL_VERSION}, model_path)
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return metadata


def load_artifact():
    model_path, metadata_path = artifact_paths()
    if not model_path.exists() or not metadata_path.exists():
        raise RuntimeError("Artefato de risco ausente. Execute: python manage.py train_risk_model")
    try:
        artifact = joblib.load(model_path)
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError("Artefato de risco corrompido ou incompativel; treine novamente.") from exc
    if artifact.get("model_version") != metadata.get("model_version") or artifact.get("features") != metadata.get("features"):
        raise RuntimeError("Metadados e pipeline do modelo sao incompativeis.")
    return artifact, metadata


def predict_risk(features):
    artifact, metadata = load_artifact()
    ordered = artifact["features"]
    frame = pd.DataFrame([{name: features.get(name) for name in ordered}])
    pipeline = artifact["pipeline"]
    score = float(pipeline.predict_proba(frame)[0, 1])
    transformed = pipeline.named_steps["scaler"].transform(pipeline.named_steps["imputer"].transform(frame))
    coefficients = pipeline.named_steps["classifier"].coef_[0]
    explanation = {
        name: float(value * coefficient)
        for name, value, coefficient in zip(ordered, transformed[0], coefficients, strict=True)
    }
    return score, explanation, metadata

