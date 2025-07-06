# run_all_updates.py
import time
import subprocess

while True:
    subprocess.run(["python3", "update_btc_t15.py"])
    subprocess.run(["python3", "update_btc_h.py"])
    subprocess.run(["python3", "update_btc_d.py"])
    subprocess.run(["python3", "update_btc_w.py"])
    subprocess.run(["python3", "update_btc_m.py"])
    subprocess.run(["python3", "update_btc_y.py"])
    time.sleep(60)  # relance toutes les minutes
