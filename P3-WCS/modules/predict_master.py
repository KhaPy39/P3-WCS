import os
import sys
import argparse
import pandas as pd
from datetime import timedelta
import joblib
from dotenv import load_dotenv
import numpy as np
import ta

# Ajouter le dossier modules au path
sys.path.append(os.path.abspath(os.path.join(os.getcwd(), '..', 'modules')))
from supabase_client import login_user

# ==========================================
# 🔐 Auth Supabase
# ==========================================
load_dotenv()
supabase = login_user(None, None)
if not supabase:
    raise Exception("❌ Connexion Supabase échouée.")
print("✅ Connexion Supabase OK.")

# ==========================================
# ⚙️ Paramètres
# ==========================================
interval_to_table = {
    "btc_t15": ("pred_15m", timedelta(minutes=15), 10),
    "btc_h": ("pred_hours", timedelta(hours=1), 10),
    "btc_d": ("pred_days", timedelta(days=1), 5)
}

targets = ["shifted_open", "shifted_high", "shifted_low", "shifted_close", "shifted_volume"]

model_dir = "/tmp/models/"
os.makedirs(model_dir, exist_ok=True)
bucket_name = "models"

# ==========================================
# ✅ Télécharger modèle depuis Supabase
# ==========================================
def download_model_from_supabase(file_name, dest_path):
    try:
        res = supabase.storage.from_(bucket_name).download(file_name)
        with open(dest_path, "wb") as f:
            f.write(res)
        print(f"✅ Modèle téléchargé : {file_name}")
    except Exception as e:
        raise Exception(f"⚠️ Erreur téléchargement Supabase pour {file_name} : {e}")

def load_model(table, target):
    file_name = f"rf_model_{table}_{target}.pkl"
    local_path = os.path.join(model_dir, file_name)
    if not os.path.exists(local_path):
        print(f"📥 Téléchargement du modèle {file_name}...")
        download_model_from_supabase(file_name, local_path)
    return joblib.load(local_path)

# ==========================================
# ✅ Ajout KPI
# ==========================================
def add_primary_kpis(df):
    df["date"] = pd.to_datetime(df["date"])
    for w in [7, 20, 99]:
        if len(df) >= w:
            df[f"ema_{w}"] = ta.trend.ema_indicator(close=df["close"], window=w, fillna=False)
    macd = ta.trend.MACD(close=df["close"], window_slow=26, window_fast=12, window_sign=9)
    df["macd"] = macd.macd()
    df["macd_signal"] = macd.macd_signal()
    df["rsi"] = ta.momentum.rsi(close=df["close"], window=14)
    boll = ta.volatility.BollingerBands(close=df["close"], window=20, window_dev=2)
    df["boll_b"] = boll.bollinger_pband()
    df["stoch_rsi"] = ta.momentum.stochrsi(close=df["close"], window=14, smooth1=3, smooth2=3)
    df["volume_ma20"] = df["volume"].rolling(window=20).mean()
    df["body_size"] = df["close"] - df["open"]
    df["amplitude"] = df["high"] - df["low"]
    df["upper_wick"] = df["high"] - df[["close", "open"]].max(axis=1)
    df["lower_wick"] = df[["close", "open"]].min(axis=1) - df["low"]
    df["efficiency_ratio"] = np.where(df["amplitude"] != 0, df["body_size"].abs() / df["amplitude"], 0)
    for col in ["open", "high", "low", "close", "volume", "body_size", "amplitude"]:
        df[f"{col}_pct_change_1"] = df[col].pct_change()
    return df

# ==========================================
# ✅ Récupération des 200 dernières lignes
# ==========================================
def get_last_data_block(table):
    response = supabase.table(table).select("*").order("date", desc=True).limit(201).execute()
    rows = response.data[::-1]
    if len(rows) < 200:
        raise Exception(f"⚠️ Pas assez de données dans {table}")
    df = pd.DataFrame(rows)
    df = df.iloc[:-1]  # Supprimer la dernière ligne (en cours)
    return df.tail(200)

# ==========================================
# ✅ UPSERT prédiction
# ==========================================
def insert_prediction(pred_table, new_date, new_row):
    supabase.table(pred_table).upsert(new_row, on_conflict="date").execute()
    print(f"✅ UPSERT {pred_table} | {new_date} | Close = {new_row['close']:.2f}")

# ==========================================
# ✅ Nouvelle logique : Translation Vec
