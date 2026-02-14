#!/usr/bin/env python3
import argparse
import json
import math
from pathlib import Path

import pandas as pd
from catboost import CatBoostRegressor, Pool


def mae(y_true, y_pred):
    return float((y_true - y_pred).abs().mean())


def rmse(y_true, y_pred):
    return float(math.sqrt(((y_true - y_pred) ** 2).mean()))


def wape(y_true, y_pred):
    denom = y_true.abs().sum()
    if denom == 0:
        return 0.0
    return float((y_true - y_pred).abs().sum() / denom)


def parse_args():
    p = argparse.ArgumentParser(description="Run test inference for trained CatBoost model")
    p.add_argument("--artifacts-dir", default="artifacts/catboost_1000", help="Directory with model and metadata")
    p.add_argument("--val-days", type=int, default=28, help="Validation window size")
    return p.parse_args()


def main():
    args = parse_args()
    artifacts_dir = Path(args.artifacts_dir)

    model_path = artifacts_dir / "model.cbm"
    features_path = artifacts_dir / "feature_columns.json"
    prepared_path = artifacts_dir / "prepared_data.csv.gz"
    out_metrics = artifacts_dir / "test_run_metrics.json"
    out_predictions = artifacts_dir / "test_run_predictions.csv"
    out_daily = artifacts_dir / "test_run_daily_metrics.csv"

    for path in [model_path, features_path, prepared_path]:
        if not path.exists():
            raise FileNotFoundError(f"Required artifact not found: {path}")

    meta = json.loads(features_path.read_text(encoding="utf-8"))
    feature_cols = meta["feature_cols"]
    cat_cols = meta["cat_cols"]
    cat_idx = [feature_cols.index(c) for c in cat_cols]

    df = pd.read_csv(prepared_path, compression="gzip")
    max_day = int(df["d_num"].max())
    val_start = max_day - args.val_days + 1
    test_df = df[df["d_num"] >= val_start].copy()

    y_true = test_df["sales_qty"]
    naive = test_df["lag_7"]

    model = CatBoostRegressor()
    model.load_model(str(model_path))
    pool = Pool(test_df[feature_cols], test_df["sales_qty"], cat_features=cat_idx)
    pred = pd.Series(model.predict(pool), index=test_df.index)

    metrics = {
        "split": {
            "max_day": max_day,
            "val_start_day": int(val_start),
            "val_days": int(args.val_days),
            "rows": int(len(test_df)),
        },
        "naive_lag7": {
            "MAE": mae(y_true, naive),
            "RMSE": rmse(y_true, naive),
            "WAPE": wape(y_true, naive),
        },
        "catboost": {
            "MAE": mae(y_true, pred),
            "RMSE": rmse(y_true, pred),
            "WAPE": wape(y_true, pred),
            "bias_pct": float((pred.sum() - y_true.sum()) / y_true.sum()) if y_true.sum() else 0.0,
        },
    }

    daily = (
        test_df.assign(pred_catboost=pred.values)
        .groupby("d", as_index=False)
        .apply(
            lambda x: pd.Series(
                {
                    "MAE": mae(x["sales_qty"], x["pred_catboost"]),
                    "RMSE": rmse(x["sales_qty"], x["pred_catboost"]),
                    "WAPE": wape(x["sales_qty"], x["pred_catboost"]),
                }
            )
        )
        .reset_index(drop=True)
    )

    test_df[["date", "d", "store_id", "item_id", "sales_qty"]].assign(
        pred_catboost=pred.values,
        pred_naive_lag7=naive.values,
        abs_err_catboost=(test_df["sales_qty"] - pred).abs().values,
    ).to_csv(out_predictions, index=False)
    daily.to_csv(out_daily, index=False)
    out_metrics.write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    print(json.dumps(metrics, indent=2))
    print(f"saved_predictions={out_predictions}")
    print(f"saved_daily_metrics={out_daily}")
    print(f"saved_metrics={out_metrics}")


if __name__ == "__main__":
    main()
