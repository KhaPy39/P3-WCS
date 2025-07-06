import subprocess
import time

scripts = [
    "modules/update_btc_t15.py",
    "modules/update_btc_h.py",
    "modules/update_btc_d.py",
    "modules/update_btc_w.py",
    "modules/update_btc_m.py",
    "modules/update_btc_y.py"
]

while True:
    print("🚀 Lancement de la mise à jour complète...")
    for script in scripts:
        try:
            print(f"▶️ Exécution : {script}", flush=True)
            subprocess.run(["python3", script], check=True)
        except Exception as e:
            print(f"❌ Erreur dans {script} : {e}", flush=True)
    print("✅ Mise à jour terminée. Nouvelle exécution dans 60 secondes.\n", flush=True)
    time.sleep(60)

