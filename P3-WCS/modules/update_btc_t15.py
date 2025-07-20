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

    # Définir la tranche actuelle (15 min)
    now = datetime.now(ZoneInfo("Europe/Paris"))
    minute = (now.minute // 15) * 15
    segment_start = now.replace(minute=minute, second=0, microsecond=0)
    segment_end = segment_start + timedelta(minutes=15)

    print(f"📌 Agrégation pour la tranche : {segment_start} → {segment_end}")

    try:
        # 1. Récupération des bougies depuis bitcoin_prices_minits
        response = supabase.table("bitcoin_prices_minits") \
            .select("*") \
            .gte("date", segment_start.isoformat()) \
            .lt("date", segment_end.isoformat()) \
            .execute()

        if not response.data or len(response.data) == 0:
            print(f"⚠️ Aucune donnée trouvée pour ce segment.")
            return

        df = pd.DataFrame(response.data)
        df['date'] = pd.to_datetime(df['date'])

        # 2. Création du slot d'agrégation (troncature en 15 min)
        df['slot'] = df['date'].dt.floor('15T')

        # 3. Agrégation (open = 1ère valeur, close = dernière, high = max, low = min, volume = somme)
        agg = df.groupby('slot').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }).reset_index()

        # 4. Préparer les données pour upsert
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

        # 5. Upsert dans btc_t15
        supabase.table("btc_t15").upsert(records).execute()

        print(f"✅ Segment {segment_start.strftime('%Y-%m-%d %H:%M')} mis à jour ({len(records)} lignes).")

    except Exception as e:
        print("❌ Erreur :", str(e))

if __name__ == "__main__":
    main()

