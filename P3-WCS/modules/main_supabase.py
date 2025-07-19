import os
from dotenv import load_dotenv
import pandas as pd
from trend_supabase import (
    get_supabase_connection,
    add_primary_kpis,
    clean_indicators,
    compute_trend_count,
    extract_trend_stats,
)

# Chargement des variables d'environnement
load_dotenv()

# Mapping des tables sources → tables destinations
TABLES_MAP = {
    "bitcoin_prices_minits": "trend_stats_minits",
    "btc_t15": "trend_stats_15m",
    "btc_h": "trend_stats_hours",
    "btc_d": "trend_stats_days",
    "btc_w": "trend_stats_week",
    "btc_m": "trend_stats_month",
    "btc_y": "trend_stats_years",
}

# Intervalle en minutes pour chaque table source
INTERVALS = {
    "bitcoin_prices_minits": 1,
    "btc_t15": 15,
    "btc_h": 60,
    "btc_d": 1440,
    "btc_w": 10080,
    "btc_m": 43200,
    "btc_y": 525600,
}


def main():
    supabase = get_supabase_connection()

    for source_table, dest_table in TABLES_MAP.items():
        print(f"\n📊 Traitement en cours : {source_table} → {dest_table}")

        try:
            # 1. Récupération et préparation des données
            df = add_primary_kpis(source_table)
            df = clean_indicators(df)
            df = compute_trend_count(df)

            # 2. Ajout de l'attribut interval
            df.attrs["interval"] = INTERVALS[source_table]

            # 3. Extraction des stats de tendance
            trend_stats = extract_trend_stats(df)

            if trend_stats.empty:
                print(f"⚠️ Aucun enregistrement à insérer pour {source_table}")
                continue

            # 4. Conversion en liste de dicts pour Supabase
            records = trend_stats.to_dict(orient="records")

            # 5. Upsert dans la table de destination
            response = supabase.table(dest_table).upsert(records).execute()

            print(f"✅ {len(records)} lignes insérées/actualisées dans {dest_table}")

        except Exception as e:
            print(f"❌ Erreur sur {source_table}: {e}")
            # Sauvegarde en CSV en cas d'échec Supabase
            fallback_file = f"fallback_{dest_table}.csv"
            trend_stats.to_csv(fallback_file, index=False)
            print(f"💾 Sauvegarde locale effectuée : {fallback_file}")

    print("\n🚀 Traitement terminé pour toutes les tables !")


if __name__ == "__main__":
    main()

