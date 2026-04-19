"""
inference.py  -  SageMaker XGBoost inference script
Uses only xgboost (native to the container) - no joblib dependency.
Model is saved in native XGBoost binary format as 'xgboost-model'.
"""

import os
import json
import xgboost as xgb

FEATURES = [
    "solar_radiation_wm2",
    "outdoor_temp_f",
    "humidity_pct",
    "uv_index",
    "system_size_dc_kw",
    "tilt_deg",
    "azimuth_deg",
    "hour_local",
    "month",
]


def model_fn(model_dir):
    model = xgb.Booster()
    model.load_model(os.path.join(model_dir, "xgboost-model"))
    print(f"Model loaded from {model_dir}/xgboost-model")
    return model


def input_fn(request_body, content_type="application/json"):
    if content_type == "application/json":
        data = json.loads(request_body)
        if isinstance(data, dict):
            data = [data]
        rows = []
        for item in data:
            feats = item.get("features", item)
            row = [float(feats[f]) for f in FEATURES]
            rows.append(row)
        return xgb.DMatrix(rows, feature_names=FEATURES)
    raise ValueError(f"Unsupported content type: {content_type}")


def predict_fn(input_data, model):
    return model.predict(input_data).tolist()


def output_fn(predictions, accept="application/json"):
    if accept == "application/json":
        return json.dumps({"predictions": predictions}), "application/json"
    raise ValueError(f"Unsupported accept type: {accept}")
