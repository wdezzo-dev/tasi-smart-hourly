# -*- coding: utf-8 -*-
"""
النظام الرئيسي — تاسي الذكي
يحلل السوق السعودي والأمريكي ويرسل التنبيهات لتيليجرام
"""
import os
import sys
import time
import warnings
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

import scoring
import db
import notify

warnings.filterwarnings("ignore")

try:
    import yfinance as yf
except ImportError:
    print("الحزمة yfinance غير مثبتة.")
    sys.exit(1)

TICKERS_FILE      = os.path.join(os.path.dirname(__file__), "tickers_tasi.csv")
OUTPUT_DIR        = os.path.join(os.path.dirname(__file__), "reports")
HISTORY_PERIOD    = "3mo"
INTERVAL          = "1h"
BATCH_SIZE        = 10
TOP_N             = 20
REQUEST_PAUSE_SEC = 2.0


def riyadh_now():
    return datetime.now(timezone.utc) + timedelta(hours=3)


def riyadh_hour_label(dt):
    h = dt.hour
    if h == 0:
        return "12am"
    if h < 12:
        return f"{h}am"
    if h == 12:
        return "12pm"
    return f"{h - 12}pm"


def load_universe(path=TICKERS_FILE):
    df = pd.read_csv(path, dtype=str)
    df["yahoo_symbol"] = df["code"].str.strip() + ".SR"
    return df


def fetch_batch(symbols, period=HISTORY_PERIOD):
    data = yf.download(
        tickers=" ".join(symbols),
        period=period,
        interval=INTERVAL,
        group_by="ticker",
        auto_adjust=False,
        threads=True,
        progress=False,
    )
    result = {}
    if len(symbols) == 1:
        sym = symbols[0]
        if not data.empty:
            result[sym] = data
        return result
    for sym in symbols:
        try:
            sub = data[sym].dropna(how="all")
            if not sub.empty:
                result[sym] = sub
        except Exception:
            continue
    return result


def build_report(universe_df):
    rows   = []
    failed = []
    symbols = universe_df["yahoo_symbol"].tolist()

    for i in range(0, len(symbols), BATCH_SIZE):
        batch = symbols[i:i + BATCH_SIZE]
        print(f"🇸🇦 جلب تاسي دفعة {i//BATCH_SIZE+1} "
              f"({i+1}-{min(i+BATCH_SIZE, len(symbols))} من {len(symbols)})...")
        try:
            batch_data = fetch_batch(batch)
        except Exception as e:
            print(f"  خطأ: {e}")
            failed.extend(batch)
            continue

        for sym in batch:
            df = batch_data.get(sym)
            if df is None or df.empty:
                failed.append(sym); continue
            try:
                result = scoring.compute_score(df)
            except Exception:
                failed.append(sym); continue
            if result is None:
                failed.append(sym); continue

            code = sym.replace(".SR", "")
            meta = universe_df.loc[universe_df["yahoo_symbol"] == sym].iloc[0]
            rows.append({
                "الرمز":             code,
                "الاسم":             meta["name"],
                "القطاع":            meta["sector"],
                "السعر":             result["close"],
                "التغير_20ساعة_%":    result["price_chg_20d_pct"],
                "RSI14":             result["rsi14"],
                "الدرجة":            result["total"],
                "التصنيف":           result["classification"],
                "تجميع_ذكي":        result["sub_scores"]["تجميع_ذكي"],
                "سيولة_ذكية":       result["sub_scores"]["سيولة_ذكية"],
                "تشبع_بيع_وارتداد": result["sub_scores"]["تشبع_بيع_وارتداد"],
                "اختراق_فني":        result["sub_scores"]["اختراق_فني"],
                "بنية_الاتجاه":     result["sub_scores"]["بنية_الاتجاه"],
                "عقوبة_تصريف":      result["penalty"],
                "أسباب_الاختيار":   " | ".join(result["signals"]) if result["signals"] else "لا توجد إشارات",
            })
        time.sleep(REQUEST_PAUSE_SEC)

    report_df = pd.DataFrame(rows)
    if not report_df.empty:
        report_df = report_df.sort_values("الدرجة", ascending=False).reset_index(drop=True)
        report_df.index += 1
        report_df.index.name = "الترتيب"

    print(f"\n✅ تاسي: تم تحليل {len(rows)} سهم. فشل {len(failed)}.")
    return report_df


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    stamp = riyadh_now()
    today_str = stamp.strftime("%Y-%m-%d")
    hour_label = riyadh_hour_label(stamp)
    report_label = f"{today_str} {hour_label}"

    # ══════════════════════════════
    # السوق السعودي (تاسي)
    # ══════════════════════════════
    print("=" * 50)
    print("🇸🇦 بدء تحليل السوق السعودي (تاسي)...")
    print("=" * 50)
    universe = load_universe()
    print(f"عدد الأسهم: {len(universe)}")

    report_df = build_report(universe)
    if not report_df.empty:
        n_saved = db.save_report(report_df, report_label)
        print(f"تم حفظ {n_saved} سهم في قاعدة البيانات.")
        top_sa = report_df.head(TOP_N).to_dict("records")
        notify.send_daily_alerts(top_sa, report_label)
        csv_path = os.path.join(OUTPUT_DIR, f"tasi_report_{today_str}_{hour_label}.csv")
        report_df.to_csv(csv_path, encoding="utf-8-sig")
        print(f"تم حفظ CSV: {csv_path}")
    else:
        print("لم تُنتج نتائج للسوق السعودي.")

    print("\n✅ اكتمل التحليل.")


if __name__ == "__main__":
    main()
