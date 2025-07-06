from supabase_client import get_supabase_connection
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

def main():
    supabase = get_supabase_connection()

    now = datetime.now(ZoneInfo("Europe/Paris"))
    segment_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    # Pour passer au 1er jour du mois suivant (attention au passage décembre → janvier)
    if segment_start.month == 12:
        segment_end = segment_start.replace(year=segment_start.year + 1, month=1)
    else:
        segment_end = segment_start.replace(month=segment_start.month + 1)

    query = f"""
    WITH base AS (
        SELECT
            date_trunc('month', date) AS month,
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
            month,
            first_value(open) OVER (PARTITION BY month ORDER BY date) AS open,
            max(high) OVER (PARTITION BY month) AS high,
            min(low) OVER (PARTITION BY month) AS low,
            last_value(close) OVER (PARTITION BY month ORDER BY date ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) AS close,
            sum(volume) OVER (PARTITION BY month) AS volume
        FROM base
    )
    INSERT INTO btc_m (date, open, high, low, close, volume)
    SELECT DISTINCT
        month AS date,
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
        print(f"✅ Mois de {segment_start.strftime('%Y-%m')} mis à jour avec succès.")
    except Exception as e:
        print("❌ Échec RPC :", str(e))

if __name__ == "__main__":
    main()
