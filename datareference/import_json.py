# ✅ Fichier complet corrigé : import_json.py

#!/usr/bin/env python3
import os
import json
import time
import psycopg2
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv
import hashlib
import sys
import logging
import traceback

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

logger.info("=== DÉMARRAGE DU PROCESSUS D'IMPORT BRONZE DB ===")

# Chargement des variables d'environnement
load_dotenv()

# Variables d'environnement selon ENV_INFOS.md et docker-compose.yml
BRONZE_DB_HOST = os.getenv('BRONZE_PG_HOST', 'datareference_bronze_postgres')
BRONZE_DB_PORT = os.getenv('BRONZE_PG_PORT', '5432')
BRONZE_DB_NAME = os.getenv('BRONZE_DB_NAME', 'bronze_db')
DB_ADMIN_USER = os.getenv('POSTGRES_USER')
DB_ADMIN_PASSWORD = os.getenv('POSTGRES_PASSWORD')
DB_READ_USER = os.getenv('DB_READ_USER')
DB_READ_PASSWORD = os.getenv('DB_READ_PASSWORD')

# Pour compatibilité avec le reste du script
PG_HOST = BRONZE_DB_HOST
PG_PORT = BRONZE_DB_PORT
PG_DB = BRONZE_DB_NAME
PG_USER = DB_ADMIN_USER
PG_PASSWORD = DB_ADMIN_PASSWORD

# Variables pour Azure Blob Storage selon ENV_INFOS.md
AZURE_CONN = os.getenv('AZURE_BLOB_STORAGE_CONNECTION_STRING')
AZURE_CONTAINER = os.getenv('AZURE_BLOB_JSON_CONTAINER', 'jsons')
JSON_BLOB_PATH = os.getenv('AZURE_JSON_PATH', 'data/')

logger.info(f"Configuration Azure: CONN={bool(AZURE_CONN)}, CONTAINER={AZURE_CONTAINER}, PATH={JSON_BLOB_PATH}")
logger.info(f"Configuration PostgreSQL: HOST={PG_HOST}, PORT={PG_PORT}, DB={PG_DB}, USER={PG_USER}")

# Suivi des fichiers déjà importés avec succès
IMPORT_TRACKING_TABLE = 'import_tracking'
IMPORT_TRACKING_SCHEMA = 'public'  # Use public schema which is always accessible
failed_imports = set()

# Cache en mémoire pour le suivi des fichiers lorsque la base de données n'est pas disponible
memory_tracking = {}

def sanitize_name(name):
    """Sanitize a name to be used as a SQL identifier."""
    # SQL reserved keywords that should be prefixed
    reserved = set([
        "all", "analyse", "analyze", "and", "any", "array", "as", "asc", 
        "asymmetric", "authorization", "between", "binary", "both", "case", 
        "cast", "check", "collate", "column", "constraint", "create", "cross", 
        "current_catalog", "current_date", "current_role", "current_schema", 
        "current_time", "current_timestamp", "current_user", "default", 
        "deferrable", "desc", "distinct", "do", "else", "end", "except", 
        "false", "fetch", "for", "foreign", "freeze", "from", "full", "grant", 
        "group", "having", "ilike", "in", "initially", "inner", "intersect", 
        "into", "is", "isnull", "join", "lateral", "leading", "left", "like", 
        "limit", "localtime", "localtimestamp", "natural", "not", "notnull", 
        "null", "offset", "on", "only", "or", "order", "outer", "over", 
        "overlaps", "placing", "primary", "references", "returning", "right", 
        "select", "session_user", "similar", "some", "symmetric", "table", 
        "then", "to", "trailing", "true", "union", "unique", "user", "using", 
        "variadic", "verbose", "when", "where", "window", "with"
    ])
    
    # Replace non-alphanumeric characters with underscore
    name = ''.join(c if c.isalnum() else '_' for c in name)
    
    # If name starts with digit or is a reserved keyword, prefix it
    if not name:
        name = 'c_empty'
    elif name[0].isdigit() or name.lower() in reserved:
        name = 'c_' + name
        
    return name.lower()

def flatten_json(obj, prefix=""):
    """Aplatit un objet JSON de manière plus robuste avec limitation de la taille des clés et des valeurs."""
    MAX_KEY_LENGTH = 58  # PostgreSQL limite les noms de colonnes à 63 caractères
    MAX_TEXT_LENGTH = 8000  # Limite de taille pour éviter l'erreur "row is too big"
    
    out = {}
    def _flatten(x, name=''):
        if isinstance(x, dict):
            for a in x:
                # Éviter les noms de clés trop longs
                safe_name = name + sanitize_name(a)[:MAX_KEY_LENGTH] + "_"
                if len(safe_name) > MAX_KEY_LENGTH:
                    safe_name = safe_name[:MAX_KEY_LENGTH] + "_"
                _flatten(x[a], safe_name)
        elif isinstance(x, list):
            # Pour les listes, stocker en JSON
            json_str = json.dumps(x)
            if len(json_str) > MAX_TEXT_LENGTH:
                json_str = json.dumps({"warning": "List truncated", "length": len(x)})
            out[name[:-1]] = json_str
        else:
            # Pour les valeurs scalaires
            key = name[:-1]
            if key:  # S'assurer que la clé n'est pas vide
                value = x
                if isinstance(value, str) and len(value) > MAX_TEXT_LENGTH:
                    value = value[:MAX_TEXT_LENGTH] + "... [truncated]"
                out[key] = value
    
    try:
        _flatten(obj)
    except Exception as e:
        logger.warning(f"Erreur lors de l'aplatissement du JSON: {str(e)}")
        # En cas d'erreur, stocker l'objet entier en JSON
        out = {"json_data": json.dumps(obj)}
    
    return out

def create_schema_if_not_exists(cursor, schema):
    """Crée un schéma s'il n'existe pas et accorde les privilèges."""
    cursor.execute(f"""
    DO $$ BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = '{schema}') THEN
            EXECUTE 'CREATE SCHEMA {schema}';
        END IF;
    END $$;
    """)
    cursor.execute(f"GRANT USAGE ON SCHEMA {schema} TO {DB_READ_USER};")
    cursor.execute(f"GRANT SELECT ON ALL TABLES IN SCHEMA {schema} TO {DB_READ_USER};")
    cursor.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA {schema} GRANT SELECT ON TABLES TO {DB_READ_USER};")

def create_tracking_table_if_not_exists(conn):
    """Crée la table de suivi des imports si elle n'existe pas"""
    try:
        with conn.cursor() as cur:
            cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {IMPORT_TRACKING_SCHEMA}.{IMPORT_TRACKING_TABLE} (
                id SERIAL PRIMARY KEY,
                file_path TEXT NOT NULL UNIQUE,
                file_hash TEXT NOT NULL,
                schema_name TEXT NOT NULL,
                table_name TEXT NOT NULL,
                row_count INTEGER NOT NULL,
                status TEXT NOT NULL,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            # Grant access to readuser
            cur.execute(f"GRANT SELECT ON {IMPORT_TRACKING_SCHEMA}.{IMPORT_TRACKING_TABLE} TO {DB_READ_USER}")
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Impossible de créer la table de suivi: {str(e)}")
        logger.error("Le suivi sera effectué en mémoire uniquement.")
        return False

def is_file_already_imported(conn, file_path, file_hash):
    """Vérifie si le fichier a déjà été importé avec succès"""
    # Vérifier d'abord en mémoire
    if file_path in memory_tracking:
        return memory_tracking[file_path]['status'] == 'success' and memory_tracking[file_path]['file_hash'] == file_hash
    
    # Ensuite vérifier en base de données
    try:
        with conn.cursor() as cur:
            cur.execute(f"""
            SELECT status FROM {IMPORT_TRACKING_SCHEMA}.{IMPORT_TRACKING_TABLE}
            WHERE file_path = %s AND file_hash = %s
            """, (file_path, file_hash))
            result = cur.fetchone()
            if result:
                # Mettre à jour le cache mémoire
                memory_tracking[file_path] = {'status': result[0], 'file_hash': file_hash}
                return result[0] == 'success'
        return False
    except Exception:
        # En cas d'erreur, utiliser uniquement le cache en mémoire
        return False

def update_import_status(conn, file_path, file_hash, schema, table, row_count, status, error_message=None):
    """Met à jour le statut d'importation d'un fichier"""
    # Mettre à jour le cache en mémoire
    memory_tracking[file_path] = {
        'file_hash': file_hash,
        'schema': schema,
        'table': table, 
        'row_count': row_count,
        'status': status,
        'error_message': error_message
    }
    
    # Tenter de mettre à jour en base de données
    try:
        with conn.cursor() as cur:
            cur.execute(f"""
            INSERT INTO {IMPORT_TRACKING_SCHEMA}.{IMPORT_TRACKING_TABLE}
            (file_path, file_hash, schema_name, table_name, row_count, status, error_message, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (file_path) 
            DO UPDATE SET 
                file_hash = EXCLUDED.file_hash,
                schema_name = EXCLUDED.schema_name,
                table_name = EXCLUDED.table_name,
                row_count = EXCLUDED.row_count,
                status = EXCLUDED.status,
                error_message = EXCLUDED.error_message,
                updated_at = CURRENT_TIMESTAMP
            """, (file_path, file_hash, schema, table, row_count, status, error_message))
        conn.commit()
    except Exception as e:
        # En cas d'erreur, on log mais on continue
        logger.error(f"Impossible de mettre à jour le statut en base de données: {str(e)}")
        logger.error("Le suivi est maintenu en mémoire uniquement.")

def calculate_file_hash(content):
    """Calcule un hash du contenu du fichier"""
    return hashlib.md5(content.encode('utf-8') if isinstance(content, str) else content).hexdigest()

def process_blob(blob_name, content, conn):
    """Traite un fichier JSON et l'importe dans la base de données"""
    file_hash = calculate_file_hash(content)
    
    # Vérifier si le fichier a déjà été traité avec succès
    if is_file_already_imported(conn, blob_name, file_hash):
        logger.info(f"✓ {blob_name} déjà importé avec succès - ignoré.")
        return True

    parts = blob_name.split('/')
    schema = sanitize_name(parts[-2]) if len(parts) > 2 else 'main'
    table = sanitize_name(parts[-1].replace('.json', ''))
    
    try:
        data = json.loads(content)
        # Utiliser une nouvelle connexion avec autocommit pour éviter les problèmes
        # de "set_session cannot be used inside a transaction"
        logger.info(f"Connexion pour traitement de {blob_name} vers {schema}.{table} avec utilisateur {DB_ADMIN_USER}")
        process_conn = psycopg2.connect(
            host=PG_HOST, 
            port=PG_PORT, 
            dbname=PG_DB, 
            user=DB_ADMIN_USER,  # Utiliser explicitement DB_ADMIN_USER ici
            password=DB_ADMIN_PASSWORD
        )
        process_conn.autocommit = True
        
        with process_conn.cursor() as cur:
            create_schema_if_not_exists(cur, schema)
            
            # Analyser les données JSON
            if isinstance(data, list):
                array_data = data
            elif isinstance(data, dict) and any(isinstance(v, list) for v in data.values()):
                # Si c'est un dictionnaire contenant des listes, prendre la première liste trouvée
                array_data = next((v for v in data.values() if isinstance(v, list)), [data])
            else:
                # Sinon, envelopper les données dans une liste
                array_data = [data]
            
            # Aplatir les données JSON avec limitation de taille
            try:
                # Analyser TOUS les éléments pour identifier toutes les colonnes possibles
                all_columns = set()
                all_flats = []
                
                # Parcourir tous les éléments pour collecter toutes les colonnes possibles
                logger.info(f"Analyse de {len(array_data)} éléments pour déterminer le schéma...")
                for i, item in enumerate(array_data):
                    try:
                        flat = flatten_json(item)
                        all_flats.append(flat)
                        all_columns.update(flat.keys())
                        if i > 0 and i % 100 == 0:
                            logger.info(f"  Analysé {i}/{len(array_data)} éléments, {len(all_columns)} colonnes identifiées")
                    except Exception as e:
                        logger.warning(f"Erreur lors de l'analyse de l'item {i}: {str(e)}")
                
                # Si aucune colonne n'a été identifiée, utiliser JSON brut
                if not all_columns:
                    raise ValueError("Aucune colonne identifiée, utilisation de JSON brut")
                
                # Créer la table avec toutes les colonnes identifiées
                logger.info(f"Création de la table avec {len(all_columns)} colonnes")
                cols_def = []
                for col in all_columns:
                    # Limiter la taille des noms de colonnes et éviter les doublons
                    col_name = sanitize_name(col)[:58]  # PostgreSQL limite à 63 caractères
                    # Éviter le conflit avec la colonne id SERIAL PRIMARY KEY
                    if col_name.lower() == 'id':
                        col_name = 'json_id'  # Renommer pour éviter le conflit
                    cols_def.append(f"{col_name} TEXT")  # Toutes les colonnes en TEXT pour flexibilité
                
                # Ajouter une colonne JSON pour les données qui ne rentrent pas dans le schéma
                cols_def.append("json_data JSONB")
                
                # Drop table first if it exists
                cur.execute(f"DROP TABLE IF EXISTS {schema}.{table}")
                
                # Create table with all possible columns
                create_table_sql = f"""
                CREATE TABLE {schema}.{table} (
                    id SERIAL PRIMARY KEY,
                    {', '.join(cols_def)},
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
                logger.debug(f"Création de la table avec: {create_table_sql}")
                cur.execute(create_table_sql)
                
                # Maintenant, insérer les données en conservant une copie JSON complète
                inserted_count = 0
                logger.info(f"Insertion de {len(array_data)} éléments dans la table...")
                
                for i, (item, flat) in enumerate(zip(array_data, all_flats)):
                    try:
                        # Utiliser les colonnes actuelles de l'élément, pas toutes les colonnes
                        cols = list(flat.keys())
                        vals = list(flat.values())
                        
                        # Ajouter le JSON complet
                        cols.append("json_data")
                        vals.append(json.dumps(item))
                        
                        # Construire la requête SQL d'insertion
                        placeholders = ", ".join(["%s"] * len(vals))
                        insert_sql = f"""
                        INSERT INTO {schema}.{table} 
                        ({', '.join(cols)})
                        VALUES ({placeholders})
                        """
                        
                        cur.execute(insert_sql, vals)
                        inserted_count += 1
                        
                        if i > 0 and i % 100 == 0:
                            logger.info(f"  Inséré {i}/{len(array_data)} éléments")
                    except Exception as e:
                        logger.error(f"❌ Erreur lors de l'insertion de l'item {i}: {str(e)}")
                        # Essayer d'insérer avec uniquement json_data comme fallback
                        try:
                            cur.execute(
                                f"INSERT INTO {schema}.{table} (json_data) VALUES (%s)",
                                [json.dumps(item)]
                            )
                            inserted_count += 1
                            logger.info(f"  ✓ Item {i} inséré en mode JSON uniquement après échec initial")
                        except Exception as fallback_err:
                            logger.error(f"  ❌ Échec également du fallback JSON pour l'item {i}: {str(fallback_err)}")
                
                logger.info(f"✅ {inserted_count} lignes importées dans {schema}.{table}")
                update_import_status(conn, blob_name, file_hash, schema, table, inserted_count, 'success')
                
            except Exception as e:
                # En cas d'échec de l'approche aplatie, utiliser JSON brut
                logger.warning(f"Échec de l'approche aplatie pour {blob_name}: {str(e)}")
                logger.info(f"Tentative d'importation en mode JSON brut pour {blob_name}")
                
                # Drop table if it exists
                cur.execute(f"DROP TABLE IF EXISTS {schema}.{table}")
                
                # Create table with JSON column
                create_table_sql = f"""
                CREATE TABLE {schema}.{table} (
                    id SERIAL PRIMARY KEY,
                    json_data JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
                cur.execute(create_table_sql)
                
                # Insert data as JSON
                inserted_count = 0
                for i, item in enumerate(array_data):
                    try:
                        cur.execute(
                            f"INSERT INTO {schema}.{table} (json_data) VALUES (%s)",
                            [json.dumps(item)]
                        )
                        inserted_count += 1
                        
                        if i > 0 and i % 100 == 0:
                            logger.info(f"  Inséré {i}/{len(array_data)} éléments (mode JSON brut)")
                    except Exception as e:
                        logger.error(f"❌ Erreur lors de l'insertion JSON de l'item {i}: {str(e)}")
                
                logger.info(f"✅ {inserted_count} lignes importées en mode JSON brut dans {schema}.{table}")
                update_import_status(conn, blob_name, file_hash, schema, table, inserted_count, 'success')
            
            # Accorder les privilèges à l'utilisateur en lecture
            cur.execute(f"GRANT SELECT ON {schema}.{table} TO {DB_READ_USER}")
            
            return True
    except Exception as e:
        error_message = f"❌ Erreur lors du traitement de {blob_name}: {str(e)}"
        logger.error(error_message)
        logger.error(traceback.format_exc())
        update_import_status(conn, blob_name, file_hash, schema, table, 0, 'error', error_message)
        failed_imports.add(blob_name)
        return False
    finally:
        # Fermer la connexion dédiée au traitement
        if 'process_conn' in locals() and process_conn:
            process_conn.close()

def wait_for_database(max_attempts=30, retry_interval=5):
    """Attend que la base de données soit disponible"""
    logger.info(f"Attente de la disponibilité de la base de données PostgreSQL à {PG_HOST}:{PG_PORT}...")
    
    for attempt in range(max_attempts):
        try:
            # D'abord se connecter à postgres (qui devrait toujours exister)
            logger.info(f"Tentative de connexion à la base postgres avec l'utilisateur {PG_USER} (tentative {attempt+1}/{max_attempts})...")
            conn = psycopg2.connect(
                host=PG_HOST,
                port=PG_PORT,
                dbname="postgres",  # Se connecter à la base postgres par défaut
                user=PG_USER,       # Utiliser l'utilisateur admin configuré
                password=PG_PASSWORD
            )
            conn.autocommit = True
            
            # Vérifier si notre base cible existe
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (PG_DB,))
                if not cur.fetchone():
                    logger.info(f"La base de données {PG_DB} n'existe pas, création...")
                    cur.execute(f"CREATE DATABASE {PG_DB}")
                    logger.info(f"Base de données {PG_DB} créée")
                else:
                    logger.info(f"La base de données {PG_DB} existe déjà")
            
            conn.close()
            
            # Maintenant se connecter à notre base cible
            logger.info(f"Tentative de connexion à la base {PG_DB}...")
            target_conn = psycopg2.connect(
                host=PG_HOST,
                port=PG_PORT,
                dbname=PG_DB,  # Se connecter à bronze_db configurée
                user=PG_USER,
                password=PG_PASSWORD
            )
            target_conn.autocommit = True
            
            # Créer l'utilisateur en lecture seule s'il n'existe pas
            create_users_if_not_exist(target_conn)
            
            logger.info("✅ Connexion à la base de données établie avec succès!")
            return target_conn
        except Exception as e:
            logger.warning(f"❌ Échec de connexion à la base de données (tentative {attempt+1}/{max_attempts}): {str(e)}")
            if attempt < max_attempts - 1:
                logger.info(f"Nouvelle tentative dans {retry_interval} secondes...")
                time.sleep(retry_interval)
    
    logger.error(f"❌ Impossible de se connecter à la base de données après {max_attempts} tentatives.")
    raise Exception("Échec de connexion à la base de données")

def create_users_if_not_exist(conn):
    """Créer l'utilisateur en lecture seule s'il n'existe pas"""
    try:
        with conn.cursor() as cur:
            # Vérifier si l'utilisateur existe
            cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (DB_READ_USER,))
            if not cur.fetchone():
                # Créer l'utilisateur
                logger.info(f"Création de l'utilisateur {DB_READ_USER}...")
                cur.execute(f"CREATE USER {DB_READ_USER} WITH PASSWORD %s", (DB_READ_PASSWORD,))
                logger.info(f"✅ Utilisateur {DB_READ_USER} créé")
            else:
                logger.info(f"L'utilisateur {DB_READ_USER} existe déjà")
    except Exception as e:
        logger.error(f"❌ Erreur lors de la création de l'utilisateur: {str(e)}")
        logger.error(traceback.format_exc())
        raise

def main():
    logger.info("Démarrage du processus d'importation de données...")
    
    # Attendre que la base de données soit disponible
    try:
        conn = wait_for_database()
    except Exception as e:
        logger.error(f"❌ Échec de connexion à la base de données: {str(e)}")
        sys.exit(1)
    
    # Créer la table de suivi des imports
    create_tracking_table_if_not_exists(conn)
    
    # Si pas de Azure connection string, chercher des fichiers locaux
    if not AZURE_CONN:
        logger.info("Aucune connexion Azure configurée, recherche des fichiers JSON locaux...")
        local_path = '/app/data'
        
        if not os.path.exists(local_path):
            logger.error(f"❌ Le répertoire local {local_path} n'existe pas")
            sys.exit(1)
        
        # Récupérer tous les fichiers JSON récursivement
        json_files = []
        for root, dirs, files in os.walk(local_path):
            for file in files:
                if file.endswith('.json'):
                    json_files.append(os.path.join(root, file))
        
        if not json_files:
            logger.warning("⚠️ Aucun fichier JSON trouvé localement")
            sys.exit(0)
        
        logger.info(f"Traitement de {len(json_files)} fichiers JSON locaux...")
        
        for file_path in json_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Convertir le chemin absolu en chemin relatif pour le suivi
                rel_path = os.path.relpath(file_path, local_path)
                process_blob(rel_path, content, conn)
            except Exception as e:
                logger.error(f"❌ Erreur lors du traitement du fichier {file_path}: {str(e)}")
                logger.error(traceback.format_exc())
    else:
        # Traitement des fichiers depuis Azure Blob Storage
        logger.info("Connexion à Azure Blob Storage...")
        try:
            blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONN)
            container_client = blob_service_client.get_container_client(AZURE_CONTAINER)
            
            # Lister tous les blobs
            blobs = list(container_client.list_blobs(name_starts_with=JSON_BLOB_PATH))
            
            if not blobs:
                logger.warning(f"⚠️ Aucun blob trouvé dans {AZURE_CONTAINER}/{JSON_BLOB_PATH}")
                sys.exit(0)
            
            logger.info(f"Traitement de {len(blobs)} blobs depuis Azure...")
            
            for blob in blobs:
                try:
                    blob_client = container_client.get_blob_client(blob.name)
                    download_stream = blob_client.download_blob()
                    content = download_stream.readall()
                    content_str = content.decode('utf-8')
                    
                    process_blob(blob.name, content_str, conn)
                except Exception as e:
                    logger.error(f"❌ Erreur lors du traitement du blob {blob.name}: {str(e)}")
                    logger.error(traceback.format_exc())
        except Exception as e:
            logger.error(f"❌ Erreur lors de la connexion à Azure Blob Storage: {str(e)}")
            logger.error(traceback.format_exc())
            sys.exit(1)
    
    # Résumé
    if failed_imports:
        logger.warning(f"⚠️ {len(failed_imports)} imports ont échoué:")
        for file_path in failed_imports:
            logger.warning(f"  - {file_path}")
        sys.exit(1)
    else:
        logger.info("✅ Tous les imports ont réussi")
        sys.exit(0)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"❌ Erreur non gérée: {str(e)}")
        logger.error(traceback.format_exc())
        sys.exit(1)