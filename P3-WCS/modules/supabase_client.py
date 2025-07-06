from supabase import create_client, Client
from dotenv import load_dotenv
import os

load_dotenv()

def get_supabase_connection() -> Client:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")

    if not url or not key:
        raise ValueError("❌ Les variables SUPABASE_URL ou SUPABASE_KEY sont manquantes ou vides.")

    print("✅ Connexion Supabase initialisée avec succès.")
    return create_client(url, key)
