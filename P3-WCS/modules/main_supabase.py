import os
from dotenv import load_dotenv
import pandas as pd
from trend_supabase import (
    get_interval,
    compute_trend_count,
    extract_trend_stats
)
from supabase_client import login_user

# Charger les variables d'environnement
load_dotenv()

# Mapping des tables sources → destinations
TABLES_MAP = {
    "bitcoin_prices_minits": "trend_stats_minits",
    "btc_t15": "trend_stats_15m",
    "btc_h": "trend_stats_hours",
    "btc_d": "trend_stats_days",
    "btc_w": "trend_stats_week",
    "btc_m": "trend_stats_month",
    "btc_y": "trend_stats_years",
}

def get_last_trend_info(supabase, dest_table):
    """Récupère trend_id et start_time de la dernière tendance."""
    try:
        response = supabase.table(dest_table) \
            .select("trend_id, start_time") \
            .order("trend_id", desc=True) \
            .limit(1) \
            .execute()
        if response.data and len(response.data) > 0:
            return response.data[0]["trend_id"], response.data[0]["start_time"]
        else:
            return 0, None
    except Exception as e:
        print(f"❌ Erreur get_last_trend_info pour {dest_table}: {e}")
        return 0, None

def fetch_source_data(supabase, table_name, last_start_time=None):
    """Récupère les données depuis Supabase avec filtre sur date."""
    try:
        if last_start_time:
            last_start_time = str(last_start_time)
            print(f"🛠️ Filtre appliqué : date >= {last_start_time}")
            response = supabase.table(table_name) \
                .select("*") \
                .gte("date", last_start_time) \
                .order("date", desc=False) \
                .execute()
        else:
            print(f"ℹ️ Aucun filtre appliqué pour {table_name}, récupération complète")
            response = supabase.table(table_name) \
                .select("*") \
                .order("date", desc=False) \
                .execute()

        if not response.data or len(response.data) == 0:
            print(f"⚠️ Aucune donnée pour {table_name}")
            return pd.DataFrame()

        return pd.DataFrame(response.data)
    except Exception as e:
        raise ValueError(f"❌ Erreur fetch_source_data pour {table_name}: {e}")

def fetch_minits_data_with_trend(supabase):
    """Requête optimisée pour bitcoin_prices_minits : récupère toutes les bougies depuis le début de la dernière tendance."""
    query = """
    WITH derniere_tendance AS (
        SELECT trend_id, start_time, end_time
        FROM trend_stats_minits
        ORDER BY end_time DESC
        LIMIT 1
    )
    SELECT 
        bp.date,
        bp.open,
        bp.high,
        bp.low,
        bp.close,
        bp.volume
    FROM 
        bitcoin_prices_minits bp
    CROSS JOIN 
        derniere_tendance dt
    WHERE 
        bp.date >= dt.start_time
    ORDER BY 
        bp.date;
    """

    response = supabase.rpc("execute_sql", {"query": query}).execute()
    if not response.data or len(response.data) == 0:
        print("⚠️ Aucune donnée récupérée via la requête spécifique")
        return pd.DataFrame()

    return pd.DataFrame(response.data)

def prepare_dataframe(df, table_name):
    """Convertit la date et prépare l'interval."""
    df['date'] = pd.to_datetime(df['date'])
    df.attrs["interval"] = get_interval(table_name)
    return df

def main():
    print("\n🔐 Authentification en cours...")
    supabase = login_user(os.getenv("SUPABASE_EMAIL"), os.getenv("SUPABASE_PASSWORD"))

    if not supabase:
        print("❌ Échec de l'authentification : arrêt du script.")
        return

    print("✅ Authentification réussie. Début du traitement des tables...\n")

    for source_table, dest_table in TABLES_MAP.items():
        print(f"\n📊 Traitement incrémental : {source_table} → {dest_table}")

        try:
            # 1. Récupérer la dernière tendance
            last_trend_id, last_start_time = get_last_trend_info(supabase, dest_table)
            if last_start_time is None:
                print("⚠️ Aucune tendance existante, démarrage complet")
                last_trend_id = 0

            print(f"⚡ Dernier trend_id : {last_trend_id}, start_time : {last_start_time}")
            start_id = last_trend_id if last_trend_id > 0 else 1

            # 2. Récupération des données
            if source_table == "bitcoin_prices_minits":
                df = fetch_minits_data_with_trend(supabase)
            else:
                df = fetch_source_data(supabase, source_table, last_start_time)

            if df.empty:
                print(f"⚠️ Aucune nouvelle donnée pour {source_table}")
                continue

            # 3. Préparer le DataFrame
            df = prepare_dataframe(df, source_table)

            # 4. Calcul des tendances
            df = compute_trend_count(df, start_id=start_id)
            trend_stats = extract_trend_stats(df)

            if trend_stats.empty:
                print(f"⚠️ Aucune nouvelle tendance détectée")
                continue

            # ✅ Conversion des dates avant envoi
            for col in trend_stats.columns:
                if "time" in col or col == "date":
                    trend_stats[col] = trend_stats[col].astype(str)

            # ✅ UPDATE de la première tendance avec last_trend_id
            first_record = trend_stats.iloc[0].to_dict()
            supabase.table(dest_table).update(first_record).eq("trend_id", last_trend_id).execute()

            # ✅ INSERT des suivantes
            next_records = trend_stats.iloc[1:].to_dict(orient="records")
            if next_records:
                supabase.table(dest_table).insert(next_records).execute()

            print(f"✅ Tendance {last_trend_id} mise à jour et {len(next_records)} nouvelles insérées")

        except Exception as e:
            print(f"❌ Erreur sur {source_table}: {e}")

    print("\n✅ Mise à jour incrémentale terminée pour toutes les tables.")

if __name__ == "__main__":
    main()
