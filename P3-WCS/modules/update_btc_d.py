from supabase_client import get_supabase_connection
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

def main():
    supabase = get_supabase_connection()

    now = datetime.now(ZoneInfo("Europe/Paris"))
    segment_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    segment_end = segment_start + timedelta(days=1)

    query = f"""
    WITH base AS (
        SELECT
            date_trunc('day', date) AS day,
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
            day,
            first_value(open) OVER (PARTITION BY day ORDER BY date) AS open,
            max(high) OVER (PARTITION BY day) AS high,
            min(low) OVER (PARTITION BY day) AS low,
            last_value(close) OVER (PARTITION BY day ORDER BY date ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) AS close,
            sum(volume) OVER (PARTITION BY day) AS volume
        FROM base
    )
    INSERT INTO btc_d (date, open, high, low, close, volume)
    SELECT DISTINCT
        day AS date,
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
        print(f"✅ Segment {segment_start.strftime('%Y-%m-%d')} mis à jour avec succès.")
    except Exception as e:
        print("❌ Échec RPC :", str(e))

if __name__ == "__main__":
    main()
