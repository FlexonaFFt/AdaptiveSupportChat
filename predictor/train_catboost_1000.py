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


def build_dataset(data_dir: Path, store_id: str, top_n: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    sales_path = data_dir / "sales_train_validation.csv"
    calendar_path = data_dir / "calendar.csv"
    prices_path = data_dir / "sell_prices.csv"

    sales = pd.read_csv(sales_path)
    sales = sales[sales["store_id"] == store_id].copy()
    d_cols = [c for c in sales.columns if c.startswith("d_")]

    sales["total_sales"] = sales[d_cols].sum(axis=1)
    selected = sales[["item_id", "total_sales"]].sort_values("total_sales", ascending=False).head(top_n)
    selected_items = selected["item_id"].tolist()

    sales = sales[sales["item_id"].isin(selected_items)].copy()
    sales = sales.drop(columns=["total_sales"])

    long_df = sales.melt(
        id_vars=["id", "item_id", "dept_id", "cat_id", "store_id", "state_id"],
        value_vars=d_cols,
        var_name="d",
        value_name="sales_qty",
    )

    calendar_cols = [
        "d",
        "date",
        "wm_yr_wk",
        "wday",
        "month",
        "year",
        "event_type_1",
        "event_type_2",
        "snap_CA",
    ]
    calendar = pd.read_csv(calendar_path, usecols=calendar_cols)

    prices = pd.read_csv(prices_path, usecols=["store_id", "item_id", "wm_yr_wk", "sell_price"])
    prices = prices[(prices["store_id"] == store_id) & (prices["item_id"].isin(selected_items))].copy()

    df = long_df.merge(calendar, on="d", how="left")
    df = df.merge(prices, on=["store_id", "item_id", "wm_yr_wk"], how="left")

    df["date"] = pd.to_datetime(df["date"])
    df["d_num"] = df["d"].str.split("_").str[1].astype(int)
    df = df.sort_values(["item_id", "d_num"]).reset_index(drop=True)

    # Calendar and event features
    df["is_event"] = ((df["event_type_1"].notna()) | (df["event_type_2"].notna())).astype(int)
    df["weekofyear"] = df["date"].dt.isocalendar().week.astype(int)

    # Fill missing prices per item
    df["sell_price"] = df.groupby("item_id")["sell_price"].ffill().fillna(0.0)

    # Demand lag/rolling features
    g = df.groupby("item_id")["sales_qty"]
    df["lag_1"] = g.shift(1)
    df["lag_7"] = g.shift(7)
    df["lag_14"] = g.shift(14)
    df["lag_28"] = g.shift(28)
    df["roll_mean_7"] = g.shift(1).rolling(7).mean().reset_index(level=0, drop=True)
    df["roll_mean_28"] = g.shift(1).rolling(28).mean().reset_index(level=0, drop=True)
    df["roll_std_7"] = g.shift(1).rolling(7).std().reset_index(level=0, drop=True)
    df["roll_std_28"] = g.shift(1).rolling(28).std().reset_index(level=0, drop=True)

    # Price dynamics
    pg = df.groupby("item_id")["sell_price"]
    df["price_lag_1"] = pg.shift(1)
    df["price_change_1"] = (df["sell_price"] - df["price_lag_1"]).fillna(0.0)
    df["price_rel_7"] = (
        df["sell_price"] / pg.shift(1).rolling(7).mean().reset_index(level=0, drop=True).replace(0, pd.NA) - 1.0
    ).fillna(0.0)

    # Drop warm-up rows where long lags/rollings are undefined
    required = ["lag_28", "roll_mean_28", "roll_std_28"]
    df = df.dropna(subset=required).copy()

    return df, selected


def parse_args():
    p = argparse.ArgumentParser(description="Train a stronger CatBoost model for M5 (single store)")
    p.add_argument("--data-dir", default="datasets/small_sample", help="Directory with original M5 CSV files")
    p.add_argument("--store-id", default="CA_1", help="Store ID")
    p.add_argument("--top-n", type=int, default=1000, help="Number of items to keep")
    p.add_argument("--val-days", type=int, default=28, help="Validation window size")
    p.add_argument("--iterations", type=int, default=3000, help="Max CatBoost iterations")
    p.add_argument("--out-dir", default="artifacts/catboost_1000", help="Output artifact directory")
    return p.parse_args()


def main():
    args = parse_args()
    data_dir = Path(args.data_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    df, selected = build_dataset(data_dir, args.store_id, args.top_n)

    feature_cols = [
        "item_id",
        "dept_id",
        "cat_id",
        "sell_price",
        "wday",
        "month",
        "year",
        "weekofyear",
        "snap_CA",
        "is_event",
        "lag_1",
        "lag_7",
        "lag_14",
        "lag_28",
        "roll_mean_7",
        "roll_mean_28",
        "roll_std_7",
        "roll_std_28",
        "price_change_1",
        "price_rel_7",
    ]
    cat_cols = ["item_id", "dept_id", "cat_id"]
    target_col = "sales_qty"

    max_day = int(df["d_num"].max())
    val_start = max_day - args.val_days + 1
    train_df = df[df["d_num"] < val_start].copy()
    val_df = df[df["d_num"] >= val_start].copy()

    train_pool = Pool(
        train_df[feature_cols],
        train_df[target_col],
        cat_features=[feature_cols.index(c) for c in cat_cols],
    )
    val_pool = Pool(
        val_df[feature_cols],
        val_df[target_col],
        cat_features=[feature_cols.index(c) for c in cat_cols],
    )

    model = CatBoostRegressor(
        loss_function="RMSE",
        eval_metric="RMSE",
        iterations=args.iterations,
        learning_rate=0.05,
        depth=10,
        l2_leaf_reg=8.0,
        bootstrap_type="Bernoulli",
        subsample=0.8,
        random_seed=42,
        verbose=100,
    )
    model.fit(train_pool, eval_set=val_pool, use_best_model=True, early_stopping_rounds=200)

    pred = pd.Series(model.predict(val_pool), index=val_df.index)
    naive = val_df["lag_7"]
    y_true = val_df[target_col]

    metrics = {
        "config": {
            "store_id": args.store_id,
            "top_n": args.top_n,
            "val_days": args.val_days,
            "iterations": args.iterations,
            "rows_total": int(len(df)),
            "rows_train": int(len(train_df)),
            "rows_val": int(len(val_df)),
            "max_day": max_day,
            "val_start_day": int(val_start),
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
            "best_iteration": int(model.get_best_iteration()),
        },
    }

    model_path = out_dir / "model.cbm"
    metrics_path = out_dir / "metrics.json"
    features_path = out_dir / "feature_columns.json"
    selected_path = out_dir / "selected_items.csv"
    prepared_path = out_dir / "prepared_data.csv.gz"
    val_pred_path = out_dir / "val_predictions.csv"

    model.save_model(str(model_path))
    metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    features_path.write_text(json.dumps({"feature_cols": feature_cols, "cat_cols": cat_cols}, indent=2), encoding="utf-8")
    selected.to_csv(selected_path, index=False)
    df.to_csv(prepared_path, index=False, compression="gzip")
    val_df[["date", "d", "d_num", "store_id", "item_id", "sales_qty"]].assign(
        pred_catboost=pred.values,
        pred_naive_lag7=naive.values,
    ).to_csv(val_pred_path, index=False)

    print(json.dumps(metrics, indent=2))
    print(f"saved_model={model_path}")
    print(f"saved_metrics={metrics_path}")
    print(f"saved_features={features_path}")
    print(f"saved_selected_items={selected_path}")
    print(f"saved_prepared_data={prepared_path}")
    print(f"saved_val_predictions={val_pred_path}")


if __name__ == "__main__":
    main()
