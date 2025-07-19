from supabase_client import get_supabase_connection
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

def main():
    supabase = get_supabase_connection()

    now = datetime.now(ZoneInfo("Europe/Paris"))
    # Troncature à la tranche de 15 minutes en cours
    minute = (now.minute // 15) * 15
    segment_start = now.replace(minute=minute, second=0, microsecond=0)
    segment_end = segment_start + timedelta(minutes=15)

    query = f"""
    WITH base AS (
        SELECT
            date_trunc('minute', date) - interval '1 minute' * (extract(minute from date)::int % 15) AS slot,
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
            slot,
            first_value(open) OVER (PARTITION BY slot ORDER BY date) AS open,
            max(high) OVER (PARTITION BY slot) AS high,
            min(low) OVER (PARTITION BY slot) AS low,
            last_value(close) OVER (PARTITION BY slot ORDER BY date ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) AS close,
            sum(volume) OVER (PARTITION BY slot) AS volume
        FROM base
    )
    INSERT INTO btc_t15 (date, open, high, low, close, volume)
    SELECT DISTINCT
        slot AS date,
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
        print(f"✅ Segment {segment_start.strftime('%Y-%m-%d %H:%M')} mis à jour avec succès.")
    except Exception as e:
        print("❌ Échec RPC :", str(e))

if __name__ == "__main__":
    main()
