from supabase_client import login_user
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import pandas as pd
import os
from dotenv import load_dotenv

def main():
    load_dotenv()

    # Connexion Supabase authentifiée
    email = os.getenv("SUPABASE_EMAIL")
    password = os.getenv("SUPABASE_PASSWORD")
    supabase = login_user(email, password)

    if not supabase:
        print("❌ Échec de l'authentification Supabase")
        return

    # Définir la période du mois en cours (1er jour → début mois suivant)
    now = datetime.now(ZoneInfo("Europe/Paris"))
    segment_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if segment_start.month == 12:
        segment_end = segment_start.replace(year=segment_start.year + 1, month=1)
    else:
        segment_end = segment_start.replace(month=segment_start.month + 1)

    print(f"📌 Agrégation mensuelle pour : {segment_start} → {segment_end}")

    try:
        # 1. Récupération des bougies minute
        response = supabase.table("bitcoin_prices_minits") \
            .select("*") \
            .gte("date", segment_start.isoformat()) \
            .lt("date", segment_end.isoformat()) \
            .execute()

        if not response.data or len(response.data) == 0:
            print("⚠️ Aucune donnée trouvée pour ce mois.")
            return

        df = pd.DataFrame(response.data)
        df['date'] = pd.to_datetime(df['date'])

        # 2. Agrégation mensuelle
        df['slot'] = df['date'].dt.to_period('M').apply(lambda r: r.start_time)
        agg = df.groupby('slot').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }).reset_index()

        # 3. Préparer pour Supabase
        records = []
        for _, row in agg.iterrows():
            records.append({
                "date": row['slot'].strftime('%Y-%m-%dT%H:%M:%S'),
                "open": float(row['open']),
                "high": float(row['high']),
                "low": float(row['low']),
                "close": float(row['close']),
                "volume": float(row['volume'])
            })

        # 4. Upsert dans btc_m
        supabase.table("btc_m").upsert(records).execute()

        print(f"✅ Mois {segment_start.strftime('%Y-%m')} mis à jour ({len(records)} lignes).")

    except Exception as e:
        print("❌ Erreur :", str(e))

if __name__ == "__main__":
    main()
