
import pandas as pd
import numpy as np
from datetime import timedelta
import ta
from supabase_client import get_supabase_connection



###----------------------------------------------------------------------------------
# Préalable - Fonction de conversion de l'intervalle d'une table
# Cette fonction retourne l'intervalle temporel d'une table en minutes (par défaut),
###----------------------------------------------------------------------------------
def get_interval(table_name: str, unit: str = "minutes") -> int:
    """
    Retourne l'intervalle temporel d'une table en minutes (par défaut),
    ou converti dans une autre unité : 'seconds', 'hours', 'days', etc.
    """
    base_minutes = {
        'bitcoint_prices_minits': 1,
        'btc_t15': 15,
        'btc_h': 60,
        'btc_d': 1440,
        'btc_w': 10080,
        'btc_m': 43200,
        'btc_y': 525600
    }

    conversion = {
        "minutes": 1,
        "seconds": 60,
        "hours": 1/60,
        "days": 1/1440,
        "weeks": 1/10080,
        "years": 1/525600
    }

    if table_name not in base_minutes:
        raise ValueError(f"⛔ Table inconnue : {table_name}")

    if unit not in conversion:
        raise ValueError(f"⛔ Unité inconnue : {unit}")

    return int(base_minutes[table_name] * conversion[unit])


###----------------------------------------------------------------------------------
# 1 - Récupération des données dans la database et génération DataFrame
###----------------------------------------------------------------------------------
def add_primary_kpis(table_name: str) -> pd.DataFrame:
    ### Connexion à la base Supabae ###
    supabase = get_supabase_connection()
    query = f"SELECT * FROM {table_name};"
    response = supabase.postgrest.rpc("execute_sql", {"query": query}).execute()
    if not response.data:
        raise ValueError(f"⛔ Aucun enregistrement trouvé dans {table_name}")
    else:
        df = pd.DataFrame(response.data)
    
    df['date'] = pd.to_datetime(df['date'])
    df.attrs["interval"] = get_interval(table_name)
    
    freq_map = {
    "bitcoin_prices_minits": "min",
    "btc_t15": "15min",
    "btc_h": "H",
    "btc_d": "D",
    "btc_w": "W",
    "btc_m": "M",
    "btc_y": "Y"
}

    freq = freq_map.get(table_name, "min")
    
    
    date_range = pd.date_range(start=df['date'].min(), end=df['date'].max(), freq=freq)
    missing_dates = date_range.difference(df['date'])
    
    if table_name == "bitcoin_prices_minits":
        date_range = pd.date_range(start=df['date'].min(), end=df['date'].max(), freq='min')
        missing_dates = date_range.difference(df['date'])

        if not missing_dates.empty:
            debut = missing_dates[0]
            fin = missing_dates[0]

            for i in range(1, len(missing_dates)):
                if missing_dates[i] == fin + timedelta(minutes=1):
                    fin = missing_dates[i]
                else:
                    print(f"☢️ Période manquante : {debut} à {fin}")
                    debut = fin = missing_dates[i]

            print(f"☢️ Période manquante : {debut} à {fin}")
            raise ValueError("⛔ Traitement interrompu : incohérence des données.")
    

    # Ajout horodatage
    df['Year'] = df['date'].dt.year
    df['Month'] = df['date'].dt.month
    df['Day'] = df['date'].dt.day
    df['Hour'] = df['date'].dt.hour
    df['Minute'] = df['date'].dt.minute

    # EMA dynamiques
    ema_windows = [7, 20, 99]
    ema_cols = []

    for w in ema_windows:
        if len(df) >= w:
            col_name = f"ema_{w}"
            df[col_name] = ta.trend.ema_indicator(close=df["close"], window=w, fillna=False)
            ema_cols.append(col_name)

    # Stocker dynamiquement les EMA réellement créées
    df.attrs["ema_cols"] = ema_cols


    # MACD
    macd = ta.trend.MACD(
        close=df["close"],
        window_slow=26,
        window_fast=12,
        window_sign=9,
        fillna=False
    )
    df["macd"] = macd.macd()
    df["macd_signal"] = macd.macd_signal()

    # RSI
    df["rsi"] = ta.momentum.rsi(close=df["close"], window=14, fillna=False)

    # Bollinger
    boll = ta.volatility.BollingerBands(close=df["close"], window=20, window_dev=2, fillna=False)
    df["boll_b"] = boll.bollinger_pband()

    # Stoch RSI
    df["stoch_rsi"] = ta.momentum.stochrsi(close=df["close"], window=14, smooth1=3, smooth2=3, fillna=False)

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

    return df


###----------------------------------------------------------------------------------
# 2 - Création fonction clean-up DataFrame et nettoyage
# Intégration des KPI analytiques
###----------------------------------------------------------------------------------
def clean_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Déduction dynamique de toutes les fenêtres utilisées
    windows = []

    for key in ["ema_short", "ema_long", "ema_max"]:
        colname = df.attrs.get(key)
        if colname and "ema_" in colname:
            try:
                windows.append(int(colname.split("ema_")[1]))
            except:
                pass

    # Fenêtres fixes pour les autres indicateurs
    windows += [26, 14, 20, 20]  # MACD, RSI, Bollinger, volume MA

    # Ffill / bfill sur les indicateurs techniques
    ema_cols = df.attrs.get("ema_cols", [])
    ffill_cols = ema_cols + ['macd', 'macd_signal', 'rsi', 'boll_b', 'stoch_rsi', 'volume_ma20']
    ffill_cols = [col for col in ffill_cols if col in df.columns]

    # Sécurisation du remplissage
    filled = df[ffill_cols].ffill().bfill()

    if len(filled) == len(df):
        df[ffill_cols] = filled
    else:
        print("⚠️ Mismatch de tailles — fallback colonne par colonne")
        for col in ffill_cols:
            df[col] = df[col].ffill().bfill()

    # Fillna = 0 sur les variations
    variation_cols = [col for col in df.columns if col.endswith("_pct_change_1")]
    df[variation_cols] = df[variation_cols].fillna(0)

    # Colonnes combinées
    short = df.attrs.get("ema_short")
    long = df.attrs.get("ema_long")

    if short in df.columns and long in df.columns:
        df["ema_ratio"] = df[short] / df[long]

    if "macd" in df.columns and "macd_signal" in df.columns:
        df["macd_diff"] = df["macd"] - df["macd_signal"]

    if "boll_b" in df.columns:
        df["boll_deviation"] = df["boll_b"] - 0.5

    return df


###----------------------------------------------------------------------------------
# 3 - Création fonction révélatrice des tendances et étiquettage
###----------------------------------------------------------------------------------
def compute_trend_count(df, start_id=0):
    """
    Ajoute trend_id et trend_count. Reprend à partir de start_id si mode incrémental.
    """
    trend_ids = [start_id]
    trend_count = [0]
    current_id = start_id
    current_count = 0
    last_direction = None

    for i in range(1, len(df)):
        prev_close = df["close"].iloc[i - 1]
        curr_close = df["close"].iloc[i]

        if curr_close > prev_close:
            direction = 1
        elif curr_close < prev_close:
            direction = -1
        else:
            direction = last_direction if last_direction is not None else 0

        # Incrémente trend_id si la direction change
        if direction != last_direction and last_direction is not None:
            current_id += 1
            current_count = 0  # Reset compteur

        # Sinon, on poursuit la tendance
        if direction == last_direction:
            current_count += 1
        else:
            current_count = 0

        trend_ids.append(current_id)
        trend_count.append(current_count)
        last_direction = direction

    df["trend_id"] = trend_ids
    df["trend_count"] = trend_count
    return df
# ************************************************************************
#   SCRIPTS CONTROLES JUSQU'ICI (14/07/2025 - 09:30:00 UTC+2)
# ************************************************************************

###----------------------------------------------------------------------------------
# 4 - Fonction d'extraction par tendance
# Note : Cette fonction remplace l'ancienne version low-res, car la durée est désormais fiable via ("date", "count")
###----------------------------------------------------------------------------------
def extract_trend_stats(df: pd.DataFrame) -> pd.DataFrame:
    """
    Extrait les statistiques clés de chaque tendance identifiée par trend_id.

    Cette fonction suppose que :
    - Le DataFrame `df` contient déjà une colonne 'trend_id' (issue de compute_trend_count).
    - L'attribut df.attrs["interval"] est défini, exprimé en minutes.

    Elle renvoie un DataFrame avec :
    - Les dates de début/fin
    - Le nombre de bougies (duration)
    - L'évolution de prix (delta_price)
    - La pente normalisée (slope)
    - Scores dérivés : trend_efficiency, risk_score, trend_score
    - Signal recalibré (STRONG / MEDIUM / WEAK)
    - Type de tendance (Haussière, Baissière, Neutre)
    """

    if "interval" not in df.attrs:
        raise ValueError("⛔ df.attrs['interval'] est requis pour normaliser le slope.")

    interval = df.attrs["interval"]

    # Agrégation des tendances par trend_id
    stats = df.groupby("trend_id").agg(
        start_time=("date", "first"),
        end_time=("date", "last"),
        duration=("date", "count"),  # nombre de bougies réelles
        start_price=("open", "first"),
        end_price=("close", "last"),
        max_price=("high", "max"),
        min_price=("low", "min")
    ).reset_index()

    # --- Calculs dérivés ---
    stats["delta_price"] = stats["end_price"] - stats["start_price"]
    stats["log_delta_price"] = np.log(stats["end_price"] / stats["start_price"])
    stats["slope"] = stats["delta_price"] / (stats["duration"] * interval)
    stats["amplitude_price"] = stats["max_price"] - stats["min_price"]
    stats["log_amplitude_price"] = np.log(stats["max_price"] / stats["min_price"])
    stats["amplitude_slope"] = stats["amplitude_price"] / (stats["duration"] * interval)

    # --- Ratios ---
    stats["trend_efficiency"] = np.where(stats["amplitude_price"] != 0,
                                         abs(stats["delta_price"]) / stats["amplitude_price"], 0)
    stats["risk_score"] = np.where(stats["slope"] != 0,
                                   stats["amplitude_slope"] / abs(stats["slope"]), 0)

    # --- Trend Score (inchangé) ---
    norm_slope = stats["slope"].abs() / (stats["slope"].abs().max() + 1e-9)
    norm_risk = stats["risk_score"] / (stats["risk_score"].max() + 1e-9)
    norm_efficiency = stats["trend_efficiency"]
    stats["trend_score"] = ((norm_slope * 0.5) + (norm_efficiency * 0.4) - (norm_risk * 0.1)) * 100

    # --- Signal recalibré (dynamique par quantiles) ---
    p50 = stats["trend_score"].quantile(0.50)
    p75 = stats["trend_score"].quantile(0.75)

    def classify_signal(score):
        if score >= p75:
            return "STRONG"
        elif score >= p50:
            return "MEDIUM"
        else:
            return "WEAK"

    stats["signal_trade"] = stats["trend_score"].apply(classify_signal)

    # --- Classification tendance avec seuil adaptatif ---
    stats["slope_pct"] = stats["delta_price"] / stats["start_price"]
    threshold = max(stats["slope_pct"].abs().median() * 0.5, 0.0001)

    def classify_trend(row):
        if row["slope_pct"] > threshold:
            return "Haussière"
        elif row["slope_pct"] < -threshold:
            return "Baissière"
        else:
            return "Neutre"

    stats["trend_type"] = stats.apply(classify_trend, axis=1)

    return stats
