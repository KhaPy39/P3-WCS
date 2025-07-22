import os
import sys
import pandas as pd
import numpy as np
from dotenv import load_dotenv
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error, mean_absolute_percentage_error
import joblib
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
tables = ["btc_t15", "btc_h", "btc_d"]
targets = ["shifted_open", "shifted_high", "shifted_low", "shifted_close", "shifted_volume"]
max_rows = 500_000
local_model_dir = "/tmp/models/"
bucket_name = "models"

os.makedirs(local_model_dir, exist_ok=True)

# ==========================================
# ✅ Fonction Upload vers Supabase Storage
# ==========================================
def upload_model_to_supabase(file_path, file_name):
    try:
        with open(file_path, "rb") as f:
            supabase.storage.from_(bucket_name).upload(file_name, f, {"upsert": "true"})
        print(f"✅ Modèle uploadé/updaté dans Supabase Storage : {file_name}")
    except Exception as e:
        print(f"⚠️ Échec upload Supabase : {file_name} | Erreur : {e}")

# ==========================================
# ✅ Ajout KPI (version locale)
# ==========================================
def add_primary_kpis(df):
    df["date"] = pd.to_datetime(df["date"])

    # EMA dynamiques
    for w in [7, 20, 99]:
        if len(df) >= w:
            df[f"ema_{w}"] = ta.trend.ema_indicator(close=df["close"], window=w, fillna=False)

    # MACD
    macd = ta.trend.MACD(close=df["close"], window_slow=26, window_fast=12, window_sign=9)
    df["macd"] = macd.macd()
    df["macd_signal"] = macd.macd_signal()

    # RSI
    df["rsi"] = ta.momentum.rsi(close=df["close"], window=14)

    # Bollinger %B
    boll = ta.volatility.BollingerBands(close=df["close"], window=20, window_dev=2)
    df["boll_b"] = boll.bollinger_pband()

    # Stochastic RSI
    df["stoch_rsi"] = ta.momentum.stochrsi(close=df["close"], window=14, smooth1=3, smooth2=3)

    # Moyenne mobile volume
    df["volume_ma20"] = df["volume"].rolling(window=20).mean()

    # Analyse chandelle
    df["body_size"] = df["close"] - df["open"]
    df["amplitude"] = df["high"] - df["low"]
    df["upper_wick"] = df["high"] - df[["close", "open"]].max(axis=1)
    df["lower_wick"] = df[["close", "open"]].min(axis=1) - df["low"]
    df["efficiency_ratio"] = np.where(df["amplitude"] != 0, df["body_size"].abs() / df["amplitude"], 0)

    # Variations %
    for col in ["open", "high", "low", "close", "volume", "body_size", "amplitude"]:
        df[f"{col}_pct_change_1"] = df[col].pct_change()

    return df.dropna()

# ==========================================
# 🔄 Fonction récupération Supabase + préparation
# ==========================================
def fetch_and_prepare(table_name):
    print(f"\n📥 Récupération des données : {table_name}")
    response = supabase.table(table_name).select("*").order("date").execute()
    data = response.data
    if not data:
        print(f"⚠️ Table vide : {table_name}")
        return None

    df = pd.DataFrame(data)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)

    # Ajout KPI locaux
    df = add_primary_kpis(df)

    # Ajout colonnes shifted
    for col in ["open", "high", "low", "close", "volume"]:
        df[f"shifted_{col}"] = df[col].shift(-1)
    df.dropna(inplace=True)

    if len(df) > max_rows:
        df = df.tail(max_rows)
    return df

# ==========================================
# 🤖 Boucle d'entraînement par table et target
# ==========================================
for table in tables:
    df = fetch_and_prepare(table)
    if df is None:
        continue

    # Features (sans date + targets)
    drop_cols = ["date"] + [f"shifted_{c}" for c in ["open", "high", "low", "close", "volume"]]
    features = df.drop(columns=drop_cols)

    # Nettoyage inf & NaN
    features = features.replace([np.inf, -np.inf], np.nan)
    features = features.dropna()

    # Conversion en float32
    features = features.astype(np.float32)

    print(f"\n✅ Table {table} prête : {features.shape[0]} lignes")

    for target_col in targets:
        print(f"\n⚡ Entraînement modèle pour {table} → {target_col}")

        y = df[target_col].loc[features.index]  # Alignement indices
        model = RandomForestRegressor(n_estimators=100, max_depth=10, random_state=42)
        model.fit(features, y)

        pred = model.predict(features)
        mse = mean_squared_error(y, pred)
        rmse = mse ** 0.5
        mape = mean_absolute_percentage_error(y, pred)
        print(f"✅ {target_col} | RMSE: {rmse:.2f} | MAPE: {mape:.2%}")

        # Sauvegarde locale (debug) + upload Supabase
        file_name = f"rf_model_{table}_{target_col}.pkl"
        local_path = os.path.join(local_model_dir, file_name)

        joblib.dump(model, local_path, compress=3)
        print(f"💾 Modèle sauvegardé localement : {local_path}")

        upload_model_to_supabase(local_path, file_name)
