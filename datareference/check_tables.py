#!/usr/bin/env python3
"""
check_tables.py - Script pour vérifier si les tables nécessaires existent
dans la base de données Silver avant de démarrer l'API.
"""
import os
import sys
import time
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
import traceback

# Configuration du logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Variables d'environnement pour la base de données
SILVER_DB_HOST = os.getenv("SILVER_DB_HOST", os.getenv("SILVER_PG_HOST", "datareference_silver_postgres"))
SILVER_DB_PORT = os.getenv("SILVER_DB_PORT", os.getenv("SILVER_PG_PORT", "5432"))
SILVER_DB_NAME = os.getenv("SILVER_DB_NAME", "silver_db")
DB_ADMIN_USER = os.getenv("DB_ADMIN_USER") or os.getenv("POSTGRES_USER")
DB_ADMIN_PASSWORD = os.getenv("DB_ADMIN_PASSWORD") or os.getenv("POSTGRES_PASSWORD")

# Liste des schémas/tables essentiels à vérifier
REQUIRED_TABLES = [
    ("bestiary", "fusion_monsters"),
    ("spells", "fusion_spells"),
    ("class", "fusion_class"),
    ("main", "tables"),
    ("main", "trapshazards")
]

def get_db_connection():
    """Tente de se connecter à la base de données Silver"""
    try:
        conn = psycopg2.connect(
            host=SILVER_DB_HOST,
            port=SILVER_DB_PORT,
            dbname=SILVER_DB_NAME,
            user=DB_ADMIN_USER,
            password=DB_ADMIN_PASSWORD
        )
        conn.autocommit = True
        return conn
    except Exception as e:
        logger.error(f"Erreur de connexion à la base Silver: {str(e)}")
        return None

def check_table_exists(conn, schema, table):
    """Vérifie si une table existe dans un schéma spécifique"""
    try:
        with conn.cursor() as cur:
            # D'abord vérifier si le schéma existe
            cur.execute("""
                SELECT 1 FROM information_schema.schemata
                WHERE schema_name = %s
            """, (schema,))
            
            if not cur.fetchone():
                logger.warning(f"Le schéma {schema} n'existe pas")
                return False
                
            # Ensuite vérifier si la table existe
            cur.execute("""
                SELECT 1 FROM information_schema.tables 
                WHERE table_schema = %s AND table_name = %s
            """, (schema, table))
            
            table_exists = cur.fetchone() is not None
            if not table_exists:
                logger.warning(f"La table {schema}.{table} n'existe pas")
            return table_exists
    except Exception as e:
        logger.error(f"Erreur lors de la vérification de {schema}.{table}: {str(e)}")
        logger.error(traceback.format_exc())
        return False

def check_all_tables():
    """Vérifie si toutes les tables requises existent"""
    conn = get_db_connection()
    if not conn:
        return REQUIRED_TABLES  # Considérer toutes les tables comme manquantes
    
    try:
        missing_tables = []
        
        # Vérifier chaque table requise
        for schema, table in REQUIRED_TABLES:
            if not check_table_exists(conn, schema, table):
                missing_tables.append((schema, table))
        
        return missing_tables
    except Exception as e:
        logger.error(f"Erreur lors de la vérification des tables: {str(e)}")
        logger.error(traceback.format_exc())
        return REQUIRED_TABLES
    finally:
        conn.close()

def main():
    max_attempts = 60  # Nombre maximum de tentatives (10 minutes)
    attempt = 0
    wait_time = 10  # Temps d'attente entre les tentatives (en secondes)
    
    logger.info("=== VÉRIFICATION DES TABLES POUR L'API ===")
    logger.info(f"Connexion à {SILVER_DB_HOST}:{SILVER_DB_PORT}/{SILVER_DB_NAME} avec l'utilisateur {DB_ADMIN_USER}")
    
    while attempt < max_attempts:
        missing_tables = check_all_tables()
        
        if not missing_tables:
            logger.info("✅ Toutes les tables requises existent dans la base Silver!")
            sys.exit(0)  # Succès
        
        attempt += 1
        # Formatons correctement les tables manquantes
        missing_table_names = [f"{schema}.{table}" for schema, table in missing_tables]
        logger.info(f"⚠️ Tables manquantes: {', '.join(missing_table_names)}. Nouvel essai dans {wait_time} secondes... ({attempt}/{max_attempts})")
        time.sleep(wait_time)
    
    # Formatons correctement les tables manquantes dans le message d'erreur final
    missing_table_names = [f"{schema}.{table}" for schema, table in missing_tables]
    logger.error(f"❌ Échec après {max_attempts} tentatives. Certaines tables sont toujours manquantes: {', '.join(missing_table_names)}")
    
    # Si nous sommes en développement, continuer quand même
    if os.environ.get("ENVIRONMENT") == "development":
        logger.warning("⚠️ Mode développement détecté, démarrage de l'API malgré les tables manquantes...")
        sys.exit(0)
    else:
        sys.exit(1)  # Échec

if __name__ == "__main__":
    main() 