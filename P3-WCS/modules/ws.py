import websocket
import json
import threading
import signal
import datetime
import time
from zoneinfo import ZoneInfo
import os
from supabase import create_client, Client

# Paramètres Supabase
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
SUPABASE_EMAIL = os.environ.get("SUPABASE_EMAIL")
SUPABASE_PASSWORD = os.environ.get("SUPABASE_PASSWORD")

for var in ["SUPABASE_URL", "SUPABASE_KEY", "SUPABASE_EMAIL", "SUPABASE_PASSWORD"]:
    if not os.environ.get(var):
        print(f"[WARNING] Variable d'environnement '{var}' non définie !")

# Authentification Supabase avec attachement du token
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
auth_response = supabase.auth.sign_in_with_password({
    "email": SUPABASE_EMAIL,
    "password": SUPABASE_PASSWORD
})

# Session avec token JWT
if auth_response.session:
    supabase.auth.set_session(
        auth_response.session.access_token,
        auth_response.session.refresh_token
    )
    print("Authentification réussie et session active")
else:
    print("Authentification échouée")
    exit(1)
if auth_response.session is None:
    print("❌ Aucun token reçu. L’authentification a échoué.")

    
# -----------------------------------------------------------------------------------
# Variable de contrôle pour arrêt propre
# -----------------------------------------------------------------------------------
running = True
ws = None

# -----------------------------------------------------------------------------------
# Fonction d'enregistrement des données dans Supabase
# -----------------------------------------------------------------------------------

def save_to_supabase(timestamp, open_price, high_price, low_price, close_price, volume):
    try:
        date = datetime.datetime.fromtimestamp(timestamp / 1000, tz=ZoneInfo("Europe/Paris")).isoformat()
        data = {
            "date": date,
            "open": round(open_price, 3),
            "high": round(high_price, 3),
            "low": round(low_price, 3),
            "close": round(close_price, 3),
            "volume": round(volume, 3)
        }
        response = supabase.table("bitcoin_prices_minits").upsert(data, on_conflict="date").execute()
        print("✅ Données insérées :", response.data)
    except Exception as e:
        print("❌ Erreur d'insertion Supabase :", e)


# -----------------------------------------------------------------------------------
# Gestion des messages WebSocket
# -----------------------------------------------------------------------------------
def on_message(ws, message):
    try:
        data = json.loads(message)
        if "e" in data and data["e"] == "kline":
            candle = data["k"]
            save_to_supabase(
                timestamp=candle["t"],
                open_price=float(candle["o"]),
                high_price=float(candle["h"]),
                low_price=float(candle["l"]),
                close_price=float(candle["c"]),
                volume=float(candle["v"])
            )
        else:
            print("Message ignoré :", data)
    except Exception as e:
        print("Erreur de parsing :", e)

# -----------------------------------------------------------------------------------
# Fonction de monitoring des erreurs, logs et de fermeture du WebSocket
# -----------------------------------------------------------------------------------
def on_error(ws, error):
    print("Erreur WebSocket :", error)

def on_close(ws, close_status_code, close_msg):
    print("🔻 WebSocket fermé")

def on_open(ws):
    print("WebSocket connecté à Binance")
    payload = {
        "method": "SUBSCRIBE",
        "params": ["BTCUSDC@kline_1m"],
        "id": 1
    }
    ws.send(json.dumps(payload))

# -----------------------------------------------------------------------------------
# Fonction de démarrage du Websocket
# -----------------------------------------------------------------------------------

def start_websocket():
    global ws
    socket = "wss://stream.binance.com:9443/ws/btcusdc@kline_1m"
    ws = websocket.WebSocketApp(
        socket,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    while running:
        ws.run_forever()
        time.sleep(1)

# -----------------------------------------------------------------------------------
# Fonction arrêt du Websocket
# -----------------------------------------------------------------------------------

def stop_websocket(signal_received=None, frame=None):
    global running, ws
    print("\n🛑 Interruption demandée")
    running = False
    if ws:
        ws.close()
    time.sleep(1)
    os._exit(0)

# -----------------------------------------------------------------------------------
# Lancement
# -----------------------------------------------------------------------------------
websocket_thread = threading.Thread(target=start_websocket)
websocket_thread.daemon = True
websocket_thread.start()

signal.signal(signal.SIGINT, stop_websocket)

while running:
    time.sleep(0.5)