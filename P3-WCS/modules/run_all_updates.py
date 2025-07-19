import subprocess
import time

# PHASE 1 : Mise à jour des tables de prix
price_update_scripts = [
    "P3-WCS/modules/update_btc_t15.py",
    "P3-WCS/modules/update_btc_h.py",
    "P3-WCS/modules/update_btc_d.py",
    "P3-WCS/modules/update_btc_w.py",
    "P3-WCS/modules/update_btc_m.py",
    "P3-WCS/modules/update_btc_y.py"
]

# PHASE 2 : Mise à jour des tendances et statistiques Supabase
# trend_update_script = "P3-WCS/modules/main_supabase.py" Scripts en attente de finalisation

while True:
    print("\n🚀 DÉMARRAGE DU PROCESSUS COMPLET")
    print("=" * 50)

    # -------------------
    # Phase 1 : Prix
    # -------------------
    print("\n📌 PHASE 1 : Mise à jour des tables prix")
    for script in price_update_scripts:
        try:
            print(f"▶️ Exécution : {script}", flush=True)
            subprocess.run(["python3", script], check=True)
            print(f"✅ {script} terminé avec succès\n")
        except subprocess.CalledProcessError as e:
            print(f"❌ Erreur dans {script} : {e}\n")
        time.sleep(2)  # Pause pour éviter surcharge API/DB

    # -------------------
    # Phase 2 : Tendances
    # -------------------
    print("\n📌 PHASE 2 : Calcul des tendances et upsert Supabase")
    try:
        print(f"▶️ Exécution : {trend_update_script}")
        subprocess.run(["python3", trend_update_script], check=True)
        print(f"✅ {trend_update_script} terminé avec succès\n")
    except subprocess.CalledProcessError as e:
        print(f"❌ Erreur dans {trend_update_script} : {e}\n")

    print("✅ Toutes les mises à jour sont terminées.")
    print("=" * 50)

    print("\n⏳ Nouvelle exécution dans 60 secondes...\n")
    time.sleep(60)
