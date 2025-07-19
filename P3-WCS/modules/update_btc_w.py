from supabase_client import get_supabase_connection
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

def main():
    supabase = get_supabase_connection()

    now = datetime.now(ZoneInfo("Europe/Paris"))
    # Troncature au début de la semaine (lundi à 00h00)
    segment_start = now - timedelta(days=now.weekday())
    segment_start = segment_start.replace(hour=0, minute=0, second=0, microsecond=0)
    segment_end = segment_start + timedelta(weeks=1)

    query = f"""
    WITH base AS (
        SELECT
            date_trunc('week', date) AS week,
            date,
            open,
            high,
            low,
            close,
            volume
        FROM bitcoin_prices_minits
        WHERE date >= '{segment_start}' AND date < '{segment_end}'
    ),
    windowed AS (
        SELECT
            week,
            first_value(open) OVER (PARTITION BY week ORDER BY date) AS open,
            max(high) OVER (PARTITION BY week) AS high,
            min(low) OVER (PARTITION BY week) AS low,
            last_value(close) OVER (PARTITION BY week ORDER BY date ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) AS close,
            sum(volume) OVER (PARTITION BY week) AS volume
        FROM base
    )
    INSERT INTO btc_w (date, open, high, low, close, volume)
    SELECT DISTINCT
        week AS date,
        open,
        high,
        low,
        close,
        volume
    FROM windowed
    ON CONFLICT (date) DO UPDATE SET
        open = EXCLUDED.open,
        high = EXCLUDED.high,
        low = EXCLUDED.low,
        close = EXCLUDED.close,
        volume = EXCLUDED.volume;
    """

    try:
        response = supabase.postgrest.rpc("execute_sql", {"query": query}).execute()
        print(f"✅ Semaine du {segment_start.strftime('%Y-%m-%d')} mise à jour avec succès.")
    except Exception as e:
        print("❌ Échec RPC :", str(e))

if __name__ == "__main__":
    main()
