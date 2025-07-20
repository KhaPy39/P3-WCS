from supabase_client import login_user
from datetime import datetime
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

    # Définir la période de l'année en cours
    now = datetime.now(ZoneInfo("Europe/Paris"))
    segment_start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    segment_end = segment_start.replace(year=segment_start.year + 1)

    print(f"📌 Agrégation annuelle pour : {segment_start} → {segment_end}")

    try:
        # 1. Récupération des bougies minute
        response = supabase.table("bitcoin_prices_minits") \
            .select("*") \
            .gte("date", segment_start.isoformat()) \
            .lt("date", segment_end.isoformat()) \
            .execute()

        if not response.data or len(response.data) == 0:
            print("⚠️ Aucune donnée trouvée pour cette année.")
            return

        df = pd.DataFrame(response.data)
        df['date'] = pd.to_datetime(df['date'])

        # 2. Agrégation annuelle
        df['slot'] = df['date'].dt.to_period('Y').apply(lambda r: r.start_time)
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

        # 4. Upsert dans btc_y
        supabase.table("btc_y").upsert(records).execute()

        print(f"✅ Année {segment_start.year} mise à jour ({len(records)} lignes).")

    except Exception as e:
        print("❌ Erreur :", str(e))

if __name__ == "__main__":
    main()
