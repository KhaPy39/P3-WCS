import os
from dotenv import load_dotenv
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo

from trend_supabase import (
    add_primary_kpis,
    clean_indicators,
    compute_trend_count,
    extract_trend_stats
)
from supabase_client import login_user

# Charger variables d'environnement
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
    """Récupère le dernier trend_id et start_time depuis Supabase."""
    query = f"SELECT trend_id, start_time FROM {dest_table} ORDER BY trend_id DESC LIMIT 1;"
    response = supabase.postgrest.rpc("execute_sql", {"query": query}).execute()

    if response.data:
        return response.data[0]["trend_id"], response.data[0]["start_time"]
    return 0, None


def fetch_source_data(supabase, table_name, last_start_time=None):
    """Lit les données depuis Supabase, filtrées si nécessaire."""
    if last_start_time:
        query = f"SELECT * FROM {table_name} WHERE date >= '{last_start_time}' ORDER BY date;"
    else:
        query = f"SELECT * FROM {table_name} ORDER BY date;"

    response = supabase.postgrest.rpc("execute_sql", {"query": query}).execute()

    if not response.data:
        raise ValueError(f"⛔ Aucun enregistrement trouvé dans {table_name}")

    return pd.DataFrame(response.data)


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
            # 1. Récupérer dernier trend_id et start_time
            last_trend_id, last_start_time = get_last_trend_info(supabase, dest_table)
            print(f"⚡ Dernier trend_id : {last_trend_id}, start_time : {last_start_time}")

            # 2. Charger les données sources (filtrées)
            df = fetch_source_data(supabase, source_table, last_start_time)

            if df.empty:
                print(f"⚠️ Aucune nouvelle donnée pour {source_table}")
                continue

            # 3. Pipeline KPI et nettoyage
            df = add_primary_kpis(source_table)
            df = clean_indicators(df)

            # 4. Recalcul des tendances à partir du dernier trend_id
            df = compute_trend_count(df, start_id=last_trend_id + 1)

            # 5. Extraire les stats de tendance
            trend_stats = extract_trend_stats(df)

            if trend_stats.empty:
                print(f"⚠️ Aucune nouvelle tendance détectée dans {source_table}")
                continue

            # 6. Upsert dans la table destination
            records = trend_stats.to_dict(orient="records")
            supabase.table(dest_table).upsert(records).execute()

            print(f"✅ {len(records)} tendances mises à jour dans {dest_table}")

        except Exception as e:
            print(f"❌ Erreur sur {source_table}: {e}")

    print("\n✅ Mise à jour incrémentale terminée pour toutes les tables.")


if __name__ == "__main__":
    main()

