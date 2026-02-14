#!/usr/bin/env python3
import argparse
import csv
import json
import math
from pathlib import Path


def mae(y_true, y_pred):
    return sum(abs(a - b) for a, b in zip(y_true, y_pred)) / len(y_true)


def rmse(y_true, y_pred):
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(y_true, y_pred)) / len(y_true))


def wape(y_true, y_pred):
    denom = sum(abs(v) for v in y_true)
    if denom == 0:
        return 0.0
    return sum(abs(a - b) for a, b in zip(y_true, y_pred)) / denom


def parse_args():
    parser = argparse.ArgumentParser(description="Train CatBoost baseline for M5 small sample")
    parser.add_argument(
        "--data",
        default="datasets/small_sample/processed/train_features_CA_1_top300_clean.csv",
        help="Path to prepared train CSV",
    )
    parser.add_argument("--val-days", type=int, default=28, help="Validation window length")
    parser.add_argument("--iterations", type=int, default=400, help="CatBoost iterations")
    parser.add_argument("--out-dir", default="artifacts/baseline", help="Output dir for model/metrics")
    return parser.parse_args()


def load_rows(path):
    rows = []
    with path.open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            day_idx = int(row["d"].split("_")[1])
            rows.append((day_idx, row))
    return rows


def main():
    args = parse_args()
    data_path = Path(args.data)
    if not data_path.exists():
        raise FileNotFoundError(f"Data file not found: {data_path}")

    try:
        from catboost import CatBoostRegressor, Pool
    except ImportError as exc:
        raise RuntimeError(
            "catboost is not available in this environment. "
            "Keep this script and run it where catboost is installed."
        ) from exc

    rows = load_rows(data_path)
    if not rows:
        raise RuntimeError("Input dataset is empty")

    max_day = max(day for day, _ in rows)
    val_start = max_day - args.val_days + 1

    feature_cols = [
        "item_id",
        "dept_id",
        "cat_id",
        "sell_price",
        "wday",
        "month",
        "year",
        "snap_CA",
        "is_event",
        "lag_1",
        "lag_7",
        "lag_28",
        "roll_mean_7",
        "roll_mean_28",
    ]
    cat_cols = {"item_id", "dept_id", "cat_id"}
    cat_indices = [i for i, c in enumerate(feature_cols) if c in cat_cols]

    x_train, y_train = [], []
    x_val, y_val = [], []
    naive_pred = []

    for day_idx, row in rows:
        x = []
        for col in feature_cols:
            if col in cat_cols:
                x.append(row[col])
            else:
                x.append(float(row[col]))
        y = float(row["sales_qty"])

        if day_idx >= val_start:
            x_val.append(x)
            y_val.append(y)
            naive_pred.append(float(row["lag_7"]))
        else:
            x_train.append(x)
            y_train.append(y)

    if not x_train or not x_val:
        raise RuntimeError("Invalid split: train or validation is empty")

    train_pool = Pool(x_train, y_train, cat_features=cat_indices)
    val_pool = Pool(x_val, y_val, cat_features=cat_indices)

    model = CatBoostRegressor(
        loss_function="RMSE",
        eval_metric="RMSE",
        iterations=args.iterations,
        learning_rate=0.1,
        depth=8,
        random_seed=42,
        verbose=100,
    )
    model.fit(train_pool, eval_set=val_pool, use_best_model=True)
    pred = model.predict(val_pool)

    metrics = {
        "split": {
            "max_day": max_day,
            "val_start_day": val_start,
            "val_days": args.val_days,
            "train_rows": len(x_train),
            "val_rows": len(x_val),
        },
        "naive_lag7": {
            "MAE": mae(y_val, naive_pred),
            "RMSE": rmse(y_val, naive_pred),
            "WAPE": wape(y_val, naive_pred),
        },
        "catboost": {
            "MAE": mae(y_val, pred),
            "RMSE": rmse(y_val, pred),
            "WAPE": wape(y_val, pred),
        },
    }

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    model_path = out_dir / "catboost_model.cbm"
    metrics_path = out_dir / "metrics.json"
    model.save_model(str(model_path))
    metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    print(json.dumps(metrics, indent=2))
    print(f"model_saved_to={model_path}")
    print(f"metrics_saved_to={metrics_path}")


if __name__ == "__main__":
    main()
