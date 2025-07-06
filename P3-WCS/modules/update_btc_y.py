from supabase_client import get_supabase_connection
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

def main():
    supabase = get_supabase_connection()

    now = datetime.now(ZoneInfo("Europe/Paris"))
    segment_start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    segment_end = segment_start.replace(year=segment_start.year + 1)

    query = f"""
    WITH base AS (
        SELECT
            date_trunc('year', date) AS year,
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
            year,
            first_value(open) OVER (PARTITION BY year ORDER BY date) AS open,
            max(high) OVER (PARTITION BY year) AS high,
            min(low) OVER (PARTITION BY year) AS low,
            last_value(close) OVER (PARTITION BY year ORDER BY date ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) AS close,
            sum(volume) OVER (PARTITION BY year) AS volume
        FROM base
    )
    INSERT INTO btc_y (date, open, high, low, close, volume)
    SELECT DISTINCT
        year AS date,
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
        print(f"✅ Année {segment_start.year} mise à jour avec succès.")
    except Exception as e:
        print("❌ Échec RPC :", str(e))

if __name__ == "__main__":
    main()
