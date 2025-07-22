import os
import sys
import pandas as pd
import numpy as np
import joblib
from dotenv import load_dotenv
from datetime import datetime
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error
from supabase_client import login_user
import ta
import time

# Ajouter le dossier modules au path
sys.path.append(os.path.abspath(os.path.join(os.getcwd(), '..', 'modules')))

# ==========================================
# 🔐 Connexion Supabase
# ==========================================
load_dotenv()
supabase = login_user(None, None)
if not supabase:
    raise Exception("❌ Connexion Supabase échouée.")
print("✅ Connexion Supabase OK.")

# ==========================================
# ⚙️ Paramètres
# ==========================================
tables = ["btc_t15", "btc_h", "btc_d"]
targets = ["shifted_open", "shifted_high", "shifted_low", "shifted_close", "shifted_volume"]
model_dir = "/tmp/models/"
os.makedirs(model_dir, exist_ok=True)
bucket_name = "models"

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
# ✅ Récupération des données Supabase
# ==========================================
def fetch_table(table):
    response = supabase.table(table).select("*").order("date", desc=True).limit(100000).execute()
    rows = response.data[::-1]
    df = pd.DataFrame(rows)
    return df

# ==========================================
# ✅ Upload Supabase avec retry
# ==========================================
def upload_with_retry(file_path, file_name, retries=3):
    for attempt in range(retries):
        try:
            with open(file_path, "rb") as f:
                supabase.storage.from_(bucket_name).upload(file_name, f, {"upsert": "true"})
            print(f"✅ Modèle uploadé dans Supabase : {file_name}")
            return
        except Exception as e:
            print(f"⚠️ Tentative {attempt+1}/{retries} échouée pour {file_name} : {e}")
            time.sleep(3)
    print(f"❌ Upload abandonné pour {file_name} après {retries} échecs.")

# ==========================================
# ✅ Entraînement modèles
# ==========================================
for table in tables:
    print(f"\n📥 Récupération des données : {table}")
    df = fetch_table(table)
    print(f"✅ Table {table} prête : {len(df)} lignes")

    # Ajout KPI
    df = add_primary_kpis(df)

    # Cibles = variations relatives avec protection division par zéro
    for col in ["open", "high", "low", "close", "volume"]:
        df[f"shifted_{col}"] = np.where(
            df[col] != 0,
            (df[col].shift(-1) - df[col]) / df[col],
            0
        )

    # Nettoyage
    df = df.dropna()
    X = df.drop(columns=["date"] + targets)
    X = X.replace([np.inf, -np.inf], np.nan).dropna()

    for target in targets:
        y = df.loc[X.index, target]
        y = y.replace([np.inf, -np.inf], np.nan).dropna()

        # Ajuster X si y a été filtré
        X = X.loc[y.index]

        print(f"\n⚡ Entraînement modèle pour {table} → {target}")
        model = RandomForestRegressor(n_estimators=100, max_depth=None, random_state=42, n_jobs=-1)
        model.fit(X, y)
        
        # Prédictions & métriques (train set)
        pred = model.predict(X)
        mae = mean_absolute_error(y, pred)
        rmse = mean_squared_error(y, pred) ** 0.5
        mape = np.mean(np.abs((y - pred) / (y + 1e-8))) * 100  # ✅ évite division par 0
        
        print(f"✅ {target} | RMSE: {rmse:.6f} | MAPE: {mape:.2f}%")

        # Sauvegarde modèle compressé
        model_name = f"rf_model_{table}_{target}.pkl"
        local_path = os.path.join(model_dir, model_name)
        joblib.dump(model, local_path, compress=3)
        print(f"💾 Modèle compressé sauvegardé localement : {local_path}")

        # Upload avec retry
        upload_with_retry(local_path, model_name)
