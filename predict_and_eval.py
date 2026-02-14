#!/usr/bin/env python3
import argparse
import csv
import json
import math
from collections import defaultdict
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
    p = argparse.ArgumentParser(description="Predict and evaluate CatBoost model on validation split")
    p.add_argument(
        "--data",
        default="datasets/small_sample/processed/train_features_CA_1_top300_clean.csv",
        help="Path to features CSV",
    )
    p.add_argument(
        "--model",
        default="artifacts/baseline/catboost_model.cbm",
        help="Path to CatBoost model",
    )
    p.add_argument("--val-days", type=int, default=28, help="Validation window size")
    p.add_argument("--out-dir", default="artifacts/baseline", help="Output folder")
    return p.parse_args()


def main():
    args = parse_args()
    data_path = Path(args.data)
    model_path = Path(args.model)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not data_path.exists():
        raise FileNotFoundError(f"Data not found: {data_path}")
    if not model_path.exists():
        raise FileNotFoundError(f"Model not found: {model_path}")

    from catboost import CatBoostRegressor, Pool

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

    rows = []
    with data_path.open(newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            day_idx = int(row["d"].split("_")[1])
            rows.append((day_idx, row))

    max_day = max(d for d, _ in rows)
    val_start = max_day - args.val_days + 1

    x_val = []
    y_val = []
    val_meta = []
    naive_pred = []

    for day_idx, row in rows:
        if day_idx < val_start:
            continue

        x = []
        for c in feature_cols:
            if c in cat_cols:
                x.append(row[c])
            else:
                x.append(float(row[c]))

        y = float(row["sales_qty"])
        x_val.append(x)
        y_val.append(y)
        naive_pred.append(float(row["lag_7"]))
        val_meta.append(
            {
                "date": row["date"],
                "d": row["d"],
                "store_id": row["store_id"],
                "item_id": row["item_id"],
                "actual": y,
            }
        )

    model = CatBoostRegressor()
    model.load_model(str(model_path))
    val_pool = Pool(x_val, y_val, cat_features=cat_indices)
    pred = model.predict(val_pool)

    # Save row-level predictions
    pred_path = out_dir / "val_predictions.csv"
    with pred_path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "d", "store_id", "item_id", "actual", "pred_catboost", "pred_naive_lag7"])
        for i, m in enumerate(val_meta):
            w.writerow(
                [
                    m["date"],
                    m["d"],
                    m["store_id"],
                    m["item_id"],
                    m["actual"],
                    float(pred[i]),
                    naive_pred[i],
                ]
            )

    # Overall metrics
    metrics = {
        "split": {
            "max_day": max_day,
            "val_start_day": val_start,
            "val_days": args.val_days,
            "val_rows": len(y_val),
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

    # Metrics by day
    day_actual = defaultdict(list)
    day_pred = defaultdict(list)
    for i, m in enumerate(val_meta):
        day_actual[m["d"]].append(m["actual"])
        day_pred[m["d"]].append(float(pred[i]))
    by_day = {}
    for d in sorted(day_actual.keys(), key=lambda x: int(x.split("_")[1])):
        by_day[d] = {
            "MAE": mae(day_actual[d], day_pred[d]),
            "RMSE": rmse(day_actual[d], day_pred[d]),
            "WAPE": wape(day_actual[d], day_pred[d]),
        }
    metrics["catboost_by_day"] = by_day

    metrics_path = out_dir / "metrics_eval.json"
    metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    print(json.dumps(metrics, indent=2))
    print(f"predictions_saved_to={pred_path}")
    print(f"metrics_saved_to={metrics_path}")


if __name__ == "__main__":
    main()
