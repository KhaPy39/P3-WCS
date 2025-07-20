from supabase import create_client, Client
from dotenv import load_dotenv
import os

load_dotenv()

# Configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
SUPABASE_EMAIL = os.environ.get("SUPABASE_EMAIL")
SUPABASE_PASSWORD = os.environ.get("SUPABASE_PASSWORD")

def get_supabase_connection() -> Client:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")

    if not url or not key:
        raise ValueError("❌ Les variables SUPABASE_URL ou SUPABASE_KEY sont manquantes ou vides.")

    print("✅ Connexion Supabase initialisée avec succès.")
    return create_client(url, key)

def get_supabase_connection() -> Client:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")

    if not url or not key:
        raise ValueError("❌ Les variables SUPABASE_URL ou SUPABASE_KEY sont manquantes ou vides.")

    print("✅ Connexion Supabase initialisée avec succès.")
    return create_client(url, key)

def get_supabase_client():
    """Crée un client Supabase de base."""
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def login_user(email, password):
    """Authentifie un utilisateur et retourne un client authentifié."""
    
    supabase = get_supabase_client()
    
    try:
        # Authentifier l'utilisateur
        auth_response = supabase.auth.sign_in_with_password({
            "email": SUPABASE_EMAIL,
            "password": SUPABASE_PASSWORD
        })
        
        # Vérifier si l'authentification a réussi
        if auth_response.user:
            print(f"✅ Authentification réussie pour {auth_response.user.email}")
            
            # Stocker les tokens pour une utilisation ultérieure
            session_data = {
                "access_token": auth_response.session.access_token,
                "refresh_token": auth_response.session.refresh_token,
                "expires_at": auth_response.session.expires_at
            }
            
            # Vous pourriez sauvegarder ces tokens de manière sécurisée
            # pour les réutiliser plus tard
            
            return supabase  # Le client est déjà authentifié
        else:
            print("❌ Authentification échouée")
            return None
        
    except Exception as e:
        print(f"❌ Erreur d'authentification: {e}")
        return None

def restore_session(access_token, refresh_token):
    """Restaure une session existante."""
    
    supabase = get_supabase_client()
    
    try:
        # Restaurer la session
        supabase.auth.set_session(access_token, refresh_token)
        
        # Vérifier si la session est valide
        user = supabase.auth.get_user()
        
        if user:
            print(f"✅ Session restaurée pour {user.user.email}")
            return supabase
        else:
            print("❌ Session invalide")
            return None
            
    except Exception as e:
        print(f"❌ Erreur lors de la restauration de la session: {e}")
        return None

def authenticated_access():
    """Accès authentifié à la table trend_stats_minits."""
    
    # Authentifier l'utilisateur
    client = login_user("email", "passowrd")
    
    if not client:
        print("❌ Impossible de s'authentifier")
        return
    
    try:
        # Tester l'accès à la table
        response = client.table(f"{table_name}") \
            .select("trend_id, start_time") \
            .order("trend_id", desc=True) \
            .limit(1) \
            .execute()
        
        if response.data:
            print(f"✅ Accès réussi à {table_name}")
            print(f"Dernier trend_id: {response.data[0]['trend_id']}")
        else:
            print("⚠️ Aucune donnée trouvée dans trend_stats_minits")
            
    except Exception as e:
        print(f"❌ Erreur lors de l'accès à {table_name}: {e}")
