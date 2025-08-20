#!/usr/bin/env python3
import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import logging
from datetime import datetime
import time
import traceback
import sys
import re
import hashlib

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('silver_transformation.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

logger.info("=== DÉMARRAGE DU PROCESSUS ETL BRONZE VERS SILVER ===")

# Chargement des variables d'environnement
load_dotenv()

# Configuration de la base de données selon ENV_INFOS.md et docker-compose.yml
BRONZE_DB_HOST = os.getenv('BRONZE_DB_HOST', 'datareference_bronze_postgres')
BRONZE_DB_PORT = os.getenv('BRONZE_DB_PORT', '5432')
BRONZE_DB_NAME = os.getenv('BRONZE_DB_NAME', 'bronze_db')
SILVER_DB_HOST = os.getenv('SILVER_DB_HOST', 'datareference_silver_postgres')
SILVER_DB_PORT = os.getenv('SILVER_DB_PORT', '5432')
SILVER_DB_NAME = os.getenv('SILVER_DB_NAME', 'silver_db')
DB_ADMIN_USER = os.getenv('DB_ADMIN_USER')
DB_ADMIN_PASSWORD = os.getenv('DB_ADMIN_PASSWORD')
DB_READ_USER = os.getenv('DB_READ_USER')
DB_READ_PASSWORD = os.getenv('DB_READ_PASSWORD')

# 🔒 Système de suivi pour éviter les doublons
TRANSFORMATION_TRACKING_TABLE = 'transformation_tracking'
TRANSFORMATION_TRACKING_SCHEMA = 'public'

logger.info(f"Configuration - BRONZE: {BRONZE_DB_HOST}:{BRONZE_DB_PORT}/{BRONZE_DB_NAME}")
logger.info(f"Configuration - SILVER: {SILVER_DB_HOST}:{SILVER_DB_PORT}/{SILVER_DB_NAME}")

def get_db_connection(db_name):
    """Create a connection to the specified database with retry logic"""
    max_attempts = 30
    retry_interval = 5
    
    # Configuration selon le type de base
    if db_name == 'bronze_db':
        db_host = BRONZE_DB_HOST
        db_port = BRONZE_DB_PORT
        db_name = BRONZE_DB_NAME
    elif db_name == 'silver_db':
        db_host = SILVER_DB_HOST
        db_port = SILVER_DB_PORT
        db_name = SILVER_DB_NAME
    else:
        # Pour postgres (création de bases)
        db_host = BRONZE_DB_HOST  # Utiliser le même hôte que bronze pour créer silver
        db_port = BRONZE_DB_PORT
    
    logger.info(f"Tentative de connexion à {db_name} avec l'utilisateur: {DB_ADMIN_USER}, hôte: {db_host}, port: {db_port}")
    
    for attempt in range(max_attempts):
        try:
            conn = psycopg2.connect(
                dbname=db_name,
                user=DB_ADMIN_USER,
                password=DB_ADMIN_PASSWORD,
                host=db_host,
                port=db_port
            )
            conn.autocommit = True
            logger.info(f"Connexion réussie à {db_name}")
            return conn
        except psycopg2.OperationalError as e:
            error_str = str(e)
            logger.warning(f"Tentative {attempt+1}/{max_attempts}: Échec de connexion à {db_name}. Erreur: {e}")
            
            # Si l'erreur indique que la base n'existe pas et qu'on n'essaie pas déjà postgres
            if "database" in error_str and "does not exist" in error_str and db_name != 'postgres':
                try:
                    # Essayer de se connecter à postgres pour pouvoir créer la base
                    logger.info(f"Tentative de connexion à postgres pour créer {db_name}...")
                    postgres_conn = psycopg2.connect(
                        dbname='postgres',
                        user=DB_ADMIN_USER,
                        password=DB_ADMIN_PASSWORD,
                        host=db_host,
                        port=db_port
                    )
                    postgres_conn.autocommit = True
                    
                    # Vérifier si la base existe déjà
                    cur = postgres_conn.cursor()
                    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
                    if not cur.fetchone():
                        # Créer la base si elle n'existe pas
                        logger.info(f"Création de la base de données {db_name}...")
                        cur.execute(f"CREATE DATABASE {db_name}")
                        logger.info(f"Base de données {db_name} créée avec succès")
                    else:
                        logger.info(f"La base de données {db_name} existe déjà")
                    
                    # Fermer la connexion à postgres
                    postgres_conn.close()
                    
                    # Réessayer avec la nouvelle base
                    continue
                except Exception as postgres_err:
                    logger.error(f"Échec de connexion à postgres: {postgres_err}")
            
            # Attendre avant de réessayer
            if attempt < max_attempts - 1:
                logger.info(f"Nouvelle tentative dans {retry_interval} secondes...")
                time.sleep(retry_interval)
    
    raise ConnectionError(f"Impossible de se connecter à la base de données {db_name} après {max_attempts} tentatives")

def create_silver_users():
    """Create necessary users in the Silver database."""
    try:
        # Se connecter directement à la base silver_db
        logger.info("Création de l'utilisateur readuser dans silver_db")
        conn = psycopg2.connect(
            dbname=SILVER_DB_NAME,
            user=DB_ADMIN_USER,
            password=DB_ADMIN_PASSWORD,
            host=SILVER_DB_HOST,
            port=SILVER_DB_PORT
        )
        conn.autocommit = True
        
        with conn.cursor() as cur:
            # Vérifier si readuser existe
            logger.info(f"Vérification de l'existence de l'utilisateur {DB_READ_USER}...")
            cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (DB_READ_USER,))
            if not cur.fetchone():
                # Créer l'utilisateur en lecture seule
                logger.info(f"Création de l'utilisateur {DB_READ_USER}...")
                cur.execute(
                    f"CREATE USER {DB_READ_USER} WITH PASSWORD %s",
                    (DB_READ_PASSWORD,)
                )
                logger.info(f"✅ Utilisateur {DB_READ_USER} créé dans silver_db")
            else:
                logger.info(f"L'utilisateur {DB_READ_USER} existe déjà")
            
            # Attribuer les privilèges à l'utilisateur en lecture
            logger.info(f"Attribution des privilèges à {DB_READ_USER}...")
            cur.execute(f"""
                GRANT CONNECT ON DATABASE {SILVER_DB_NAME} TO {DB_READ_USER};
            """)
            
        conn.close()
        logger.info("✅ Configuration des utilisateurs terminée dans silver_db")
    except Exception as e:
        logger.error(f"❌ Erreur lors de la création des utilisateurs dans silver_db: {str(e)}")
        logger.error(traceback.format_exc())
        raise

def setup_silver_schema():
    """Set up schemas in the Silver database."""
    logger.info("Configuration des schémas dans silver_db...")
    
    try:
        bronze_conn = get_db_connection('bronze_db')
        silver_conn = get_db_connection('silver_db')
        
        # Get schemas from bronze_db
        with bronze_conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT schema_name 
                FROM information_schema.schemata 
                WHERE schema_name NOT IN ('pg_catalog', 'information_schema', 'pg_toast', 'public')
            """)
            schemas = [row['schema_name'] for row in cur.fetchall()]
            
            # If no schemas found, create at least main and content schemas
            if not schemas:
                schemas = ['main', 'bestiary', 'class', 'spells', 'items', 'rules', 'races', 'book', 'adventure']
                logger.info(f"Aucun schéma trouvé dans bronze_db, création des schémas par défaut: {schemas}")
        
        # Create schemas in silver_db
        with silver_conn.cursor() as cur:
            for schema in schemas:
                logger.info(f"Création du schéma {schema} dans silver_db...")
                cur.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
                cur.execute(f"GRANT USAGE ON SCHEMA {schema} TO {DB_READ_USER}")
                cur.execute(f"GRANT SELECT ON ALL TABLES IN SCHEMA {schema} TO {DB_READ_USER}")
                cur.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA {schema} GRANT SELECT ON TABLES TO {DB_READ_USER}")
            
            schemas_str = ", ".join(schemas) if schemas else 'aucun'
            logger.info(f"✅ Schémas créés dans silver_db: {schemas_str}")
        
        bronze_conn.close()
        silver_conn.close()
    except Exception as e:
        logger.error(f"❌ Erreur lors de la configuration des schémas: {str(e)}")
        logger.error(traceback.format_exc())
        raise

def get_all_tables(conn, schema):
    """Get all tables in a schema with their names and patterns."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = %s
            AND table_type = 'BASE TABLE'
        """, (schema,))
        tables = [row['table_name'] for row in cur.fetchall()]
        
        # Trier les tables par type
        schema_prefix_tables = []  # tables like schema_xxx
        fluff_prefix_tables = []   # tables like fluff_schema_xxx
        other_tables = []          # all other tables
        
        for table in tables:
            if table.startswith(f"{schema}_"):
                schema_prefix_tables.append(table)
            elif table.startswith(f"fluff_{schema}_"):
                fluff_prefix_tables.append(table)
            else:
                other_tables.append(table)
        
        return schema_prefix_tables, fluff_prefix_tables, other_tables

def get_table_columns(conn, schema, table):
    """Get all columns in a table."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ordinal_position
        """, (schema, table))
        return [(row['column_name'], row['data_type']) for row in cur.fetchall()]

def collect_all_columns_from_tables(bronze_conn, schema, tables):
    """Collect all unique columns from a set of tables."""
    all_columns = {}
    
    for table in tables:
        logger.info(f"Collecte des colonnes de {schema}.{table}...")
        try:
            columns = get_table_columns(bronze_conn, schema, table)
            
            for col_name, col_type in columns:
                # Skip id column as we'll create our own
                if col_name != 'id':
                    # Keep the most flexible type if column exists in multiple tables
                    if col_name in all_columns:
                        # Prefer TEXT over other types for flexibility
                        if col_type.upper() == 'TEXT' or all_columns[col_name].upper() == 'TEXT':
                            all_columns[col_name] = 'TEXT'
                        # Prefer JSONB for complex types
                        elif col_type.upper() == 'JSONB' or all_columns[col_name].upper() == 'JSONB':
                            all_columns[col_name] = 'JSONB'
                        # For numeric, prefer larger types
                        elif 'INT' in col_type.upper() and 'INT' in all_columns[col_name].upper():
                            if 'BIGINT' in col_type.upper() or 'BIGINT' in all_columns[col_name].upper():
                                all_columns[col_name] = 'BIGINT'
                            else:
                                all_columns[col_name] = 'INTEGER'
                        # Default to the existing type
                        else:
                            pass  # Keep existing type
                    else:
                        all_columns[col_name] = col_type
        except Exception as e:
            logger.warning(f"⚠️ Erreur lors de la collecte des colonnes pour {schema}.{table}: {str(e)}")
    
    return all_columns

def create_fusion_table(bronze_conn, silver_conn, schema, table_prefix, fusion_table_name):
    """Create a fusion table by combining tables with the same prefix.
    
    Args:
        bronze_conn: Connection to bronze_db
        silver_conn: Connection to silver_db
        schema: Schema name
        table_prefix: Prefix of tables to merge (e.g., 'spells_', 'fluff_spells_')
        fusion_table_name: Name of the fusion table to create
    """
    try:
        # Get all tables in the schema
        with bronze_conn.cursor() as bronze_cur:
            bronze_cur.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = %s
                AND table_type = 'BASE TABLE'
            """, (schema,))
            all_tables = [row[0] for row in bronze_cur.fetchall()]
        
        # Filter tables by prefix
        prefix_tables = [t for t in all_tables if t.startswith(table_prefix)]
        
        if not prefix_tables:
            logger.warning(f"⚠️ Aucune table trouvée avec le préfixe '{table_prefix}' dans le schéma '{schema}'")
            return
        
        # 🔒 Vérifier si la transformation est nécessaire
        source_hash = calculate_tables_hash(bronze_conn, schema, prefix_tables)
        if source_hash and not is_transformation_needed(silver_conn, schema, fusion_table_name, 'fusion', source_hash):
            return
        
        # Marquer la transformation comme en cours
        if source_hash:
            update_transformation_status(silver_conn, schema, prefix_tables, schema, fusion_table_name, 'fusion', source_hash, 0, 'in_progress')
        
        logger.info(f"Fusion des tables {prefix_tables} en {schema}.{fusion_table_name}")
        
        # Verify which tables actually exist and are accessible
        existing_tables = []
        for table in prefix_tables:
            try:
                # Test if the table is actually accessible with a simple query
                with bronze_conn.cursor() as test_cur:
                    test_cur.execute(f"SELECT 1 FROM {schema}.{table} LIMIT 1")
                    existing_tables.append(table)
                    logger.info(f"✓ Table {schema}.{table} existe et est accessible")
            except Exception as e:
                logger.warning(f"⚠️ Table {schema}.{table} existe dans information_schema mais n'est pas accessible: {str(e)}")
        
        if not existing_tables:
            logger.warning(f"⚠️ Aucune table accessible avec le préfixe '{table_prefix}' dans le schéma '{schema}'")
            return
        
        # Collect all columns from all tables
        all_columns = collect_all_columns_from_tables(bronze_conn, schema, existing_tables)
        
        if not all_columns:
            logger.warning(f"⚠️ Aucune colonne trouvée dans les tables à fusionner pour {schema}.{fusion_table_name}")
            return
        
        # Add metadata columns for the fusion table
        all_columns_list = [f"id SERIAL PRIMARY KEY", f"source_table TEXT", f"original_id INTEGER"]
        all_columns_list.extend([f"{col_name} {col_type}" for col_name, col_type in all_columns.items()])
        
        # Create the fusion table in silver_db
        with silver_conn.cursor() as silver_cur:
            # Créer l'extension dblink si elle n'existe pas
            silver_cur.execute("CREATE EXTENSION IF NOT EXISTS dblink")
            
            # Drop the fusion table if it exists
            silver_cur.execute(f"DROP TABLE IF EXISTS {schema}.{fusion_table_name}")
            
            # Create the fusion table
            create_table_sql = f"""
                CREATE TABLE {schema}.{fusion_table_name} (
                    {", ".join(all_columns_list)}
                )
            """
            silver_cur.execute(create_table_sql)
            
            # Insert data from each table
            for table in existing_tables:
                try:
                    # Get columns from this table
                    columns = get_table_columns(bronze_conn, schema, table)
                    table_columns = [col[0] for col in columns if col[0] != 'id']
                    
                    if not table_columns:
                        logger.warning(f"⚠️ Aucune colonne trouvée pour {schema}.{table}, ignorée")
                        continue
                    
                    # Map columns between source and destination
                    insert_cols = ["source_table", "original_id"]
                    
                    # Get all possible columns for the fusion table (excluding metadata columns)
                    all_column_names = list(all_columns.keys())
                    
                    # Create full column list for insert
                    full_insert_cols = ["source_table", "original_id"]
                    full_insert_cols.extend(all_column_names)
                    
                    # Build the complete SQL query with proper formatting
                    # Prepare column lists and types
                    dblink_select = ["id"]
                    
                    # Add all columns, using NULL for missing ones
                    for col in all_column_names:
                        if col in table_columns:
                            dblink_select.append(f"\"{col}\"")
                        else:
                            dblink_select.append("NULL")
                    
                    # Prepare column types for dblink
                    dblink_types = ["source_table TEXT", "original_id INTEGER"]
                    for col_name, col_type in all_columns.items():
                        dblink_types.append(f"\"{col_name}\" {col_type}")
                    
                    # Create the column list string for INSERT
                    column_list_str = ", ".join([f"\"{c}\"" for c in full_insert_cols])
                    
                    # Use proper SQL syntax for the dblink query with dollar quoting to avoid escaping issues
                    dblink_sql = f"""
                        INSERT INTO {schema}.{fusion_table_name} ({column_list_str})
                        SELECT * FROM dblink(
                            'host={BRONZE_DB_HOST} port={BRONZE_DB_PORT} dbname={BRONZE_DB_NAME} user={DB_ADMIN_USER} password={DB_ADMIN_PASSWORD}',
                            $DLSQL$SELECT '{table}', id, {", ".join(dblink_select[1:])} FROM {schema}.{table}$DLSQL$
                        ) AS t ({", ".join(dblink_types)})
                    """
                    
                    # Log what we're doing
                    logger.info(f"Insertion des données de {schema}.{table} vers {schema}.{fusion_table_name}")
                    
                    try:
                        # Try to execute the insert
                        silver_cur.execute(dblink_sql)
                        
                        # Get count of inserted rows using dollar quoting for consistent string handling
                        silver_cur.execute(f"SELECT COUNT(*) FROM {schema}.{fusion_table_name} WHERE source_table = $${table}$$")
                        inserted_count = silver_cur.fetchone()[0]
                        logger.info(f"✅ {inserted_count} lignes fusionnées depuis {schema}.{table}")
                    except Exception as insert_err:
                        logger.error(f"❌ Erreur lors de l'insertion des données de {schema}.{table}: {str(insert_err)}")
                        logger.error(traceback.format_exc())
                
                except Exception as e:
                    logger.error(f"❌ Erreur lors de la fusion des données de {schema}.{table}: {str(e)}")
                    logger.error(traceback.format_exc())
            
            # Grant privileges to read user
            silver_cur.execute(f"GRANT SELECT ON {schema}.{fusion_table_name} TO {DB_READ_USER}")
            
            # Add indexing for better performance
            try:
                logger.info(f"Création d'index sur source_table pour {schema}.{fusion_table_name}")
                silver_cur.execute(f"CREATE INDEX idx_{fusion_table_name}_source_table ON {schema}.{fusion_table_name} (source_table)")
                logger.info(f"Index créé sur source_table")
            except Exception as idx_err:
                logger.warning(f"⚠️ Erreur lors de la création de l'index: {str(idx_err)}")
            
            # Obtenir le nombre total de lignes fusionnées
            silver_cur.execute(f"SELECT COUNT(*) FROM {schema}.{fusion_table_name}")
            total_rows = silver_cur.fetchone()[0]
            
        # 🔒 Marquer la transformation comme réussie
        if source_hash:
            update_transformation_status(silver_conn, schema, prefix_tables, schema, fusion_table_name, 'fusion', source_hash, total_rows, 'success')
            
        logger.info(f"✅ Table de fusion {schema}.{fusion_table_name} créée avec succès ({total_rows} lignes)")
            
    except Exception as e:
        # 🔒 Marquer la transformation comme échouée
        if 'source_hash' in locals() and source_hash:
            update_transformation_status(silver_conn, schema, prefix_tables if 'prefix_tables' in locals() else [], schema, fusion_table_name, 'fusion', source_hash, 0, 'error', str(e))
        
        logger.error(f"❌ Erreur lors de la création de la table de fusion {schema}.{fusion_table_name}: {str(e)}")
        logger.error(traceback.format_exc())

def copy_table(bronze_conn, silver_conn, schema, table):
    """Copy a table from bronze to silver."""
    try:
        logger.info(f"Copie de la table {schema}.{table}")
        
        # Vérifier que la table existe et est accessible
        try:
            with bronze_conn.cursor() as test_cur:
                test_cur.execute(f"SELECT 1 FROM {schema}.{table} LIMIT 1")
                logger.info(f"✓ Table {schema}.{table} existe et est accessible")
        except Exception as e:
            logger.warning(f"⚠️ Table {schema}.{table} existe dans information_schema mais n'est pas accessible: {str(e)}")
            return
        
        # 🔒 Vérifier si la transformation est nécessaire
        source_hash = calculate_tables_hash(bronze_conn, schema, [table])
        if source_hash and not is_transformation_needed(silver_conn, schema, table, 'copy', source_hash):
            return
        
        # Marquer la transformation comme en cours
        if source_hash:
            update_transformation_status(silver_conn, schema, [table], schema, table, 'copy', source_hash, 0, 'in_progress')
        
        # Get columns from source table
        columns = get_table_columns(bronze_conn, schema, table)
        
        if not columns:
            logger.warning(f"⚠️ Aucune colonne trouvée dans {schema}.{table}, table ignorée")
            return
        
        column_list = [col_name for col_name, _ in columns]
        column_defs = [f"{col_name} {col_type}" for col_name, col_type in columns]
        
        # Create the destination table
        with silver_conn.cursor() as silver_cur, bronze_conn.cursor() as bronze_cur:
            # Drop the table if it exists
            silver_cur.execute(f"DROP TABLE IF EXISTS {schema}.{table}")
            
            # Create the table
            column_defs_str = ", ".join(column_defs)
            create_table_sql = f"""
                CREATE TABLE {schema}.{table} (
                    {column_defs_str}
                )
            """
            silver_cur.execute(create_table_sql)
            
            # Compter les lignes à copier
            bronze_cur.execute(f"SELECT COUNT(*) FROM {schema}.{table}")
            row_count = bronze_cur.fetchone()[0]
            logger.info(f"Copie de {row_count} lignes de {schema}.{table}")
            
            # Utiliser dblink pour copier les données entre les bases
            try:
                # Vérifier si l'extension dblink est disponible
                silver_cur.execute("CREATE EXTENSION IF NOT EXISTS dblink")
                
                # Préparer les types de colonnes pour dblink
                column_types = [f"{col_name} {col_type}" for col_name, col_type in columns]
                
                # Construire la requête dblink
                column_list_str = ", ".join(column_list)
                column_types_str = ", ".join(column_types)
                
                dblink_sql = f"""
                    INSERT INTO {schema}.{table} ({column_list_str})
                    SELECT {column_list_str} FROM dblink(
                        'host={BRONZE_DB_HOST} port={BRONZE_DB_PORT} dbname={BRONZE_DB_NAME} user={DB_ADMIN_USER} password={DB_ADMIN_PASSWORD}',
                        'SELECT {column_list_str} FROM {schema}.{table}'
                    ) AS t ({column_types_str})
                """
                silver_cur.execute(dblink_sql)
                
                # Vérifier le nombre de lignes insérées
                silver_cur.execute(f"SELECT COUNT(*) FROM {schema}.{table}")
                inserted_count = silver_cur.fetchone()[0]
                logger.info(f"✅ {inserted_count} lignes copiées dans {schema}.{table}")
            except Exception as insert_error:
                logger.error(f"❌ Erreur lors de la copie des données: {str(insert_error)}")
                
                # Essayer une approche ligne par ligne si nécessaire
                logger.info(f"Tentative de copie ligne par ligne pour {schema}.{table}")
                
                # Utiliser une approche par bloc pour éviter de surcharger la mémoire
                batch_size = 100
                offset = 0
                inserted_count = 0
                
                while True:
                    column_list_str = ", ".join(column_list)
                    bronze_cur.execute(f"SELECT {column_list_str} FROM {schema}.{table} LIMIT {batch_size} OFFSET {offset}")
                    rows = bronze_cur.fetchall()
                    
                    if not rows:
                        break
                    
                    # Insérer chaque ligne individuellement
                    placeholders = ", ".join(['%s'] * len(column_list))
                    insert_stmt = f"INSERT INTO {schema}.{table} ({column_list_str}) VALUES ({placeholders})"
                    
                    for row in rows:
                        try:
                            silver_cur.execute(insert_stmt, row)
                            inserted_count += 1
                        except Exception as row_error:
                            logger.warning(f"⚠️ Erreur lors de l'insertion d'une ligne: {str(row_error)}")
                        
                    offset += batch_size
                    logger.info(f"  Progression: {inserted_count} lignes copiées")
                
                logger.info(f"✅ {inserted_count} lignes copiées par approche ligne par ligne dans {schema}.{table}")
            
            # Grant privileges
            silver_cur.execute(f"GRANT SELECT ON {schema}.{table} TO {DB_READ_USER}")
            
            # Obtenir le nombre de lignes copiées
            silver_cur.execute(f"SELECT COUNT(*) FROM {schema}.{table}")
            copied_rows = silver_cur.fetchone()[0]
            
        # 🔒 Marquer la transformation comme réussie
        if source_hash:
            update_transformation_status(silver_conn, schema, [table], schema, table, 'copy', source_hash, copied_rows, 'success')
            
        logger.info(f"✅ Table {schema}.{table} copiée avec succès ({copied_rows} lignes)")
        
    except Exception as e:
        # 🔒 Marquer la transformation comme échouée
        if 'source_hash' in locals() and source_hash:
            update_transformation_status(silver_conn, schema, [table], schema, table, 'copy', source_hash, 0, 'error', str(e))
            
        logger.error(f"❌ Erreur lors de la copie de la table {schema}.{table}: {str(e)}")
        logger.error(traceback.format_exc())

def process_schema(bronze_conn, silver_conn, schema):
    """Process a schema by identifying table patterns and creating appropriate fusion tables."""
    try:
        logger.info(f"Traitement du schéma {schema}...")
        
        # Get all tables in the schema, grouped by pattern
        schema_tables, fluff_tables, other_tables = get_all_tables(bronze_conn, schema)
        
        logger.info(f"Trouvé dans {schema}: {len(schema_tables)} tables préfixées, {len(fluff_tables)} tables fluff, {len(other_tables)} autres tables")
        
        # 1. Process schema-specific fusion tables
        if schema_tables:
            # For schemas like bestiary, class, etc.
            if schema in ['bestiary', 'class', 'spells', 'adventure', 'book']:
                fusion_name = f"fusion_{schema}"
                if schema == 'bestiary':
                    fusion_name = "fusion_monsters"  # Special case for bestiary
                
                create_fusion_table(bronze_conn, silver_conn, schema, f"{schema}_", fusion_name)
            # General fusion for schema-prefixed tables
            else:
                create_fusion_table(bronze_conn, silver_conn, schema, f"{schema}_", f"fusion_{schema}")
        
        # 2. Process fluff fusion tables
        if fluff_tables:
            create_fusion_table(bronze_conn, silver_conn, schema, f"fluff_{schema}_", f"fusion_fluff_{schema}")
        
        # 3. Copy other tables directly
        for table in other_tables:
            copy_table(bronze_conn, silver_conn, schema, table)
        
    except Exception as e:
        logger.error(f"❌ Erreur lors du traitement du schéma {schema}: {str(e)}")
        logger.error(traceback.format_exc())

def create_transformation_tracking_table(conn):
    """Crée la table de suivi des transformations si elle n'existe pas"""
    try:
        with conn.cursor() as cur:
            cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {TRANSFORMATION_TRACKING_SCHEMA}.{TRANSFORMATION_TRACKING_TABLE} (
                id SERIAL PRIMARY KEY,
                source_schema TEXT NOT NULL,
                source_tables TEXT NOT NULL,
                target_schema TEXT NOT NULL,
                target_table TEXT NOT NULL,
                transformation_type TEXT NOT NULL,  -- 'fusion' ou 'copy'
                source_hash TEXT NOT NULL,
                row_count INTEGER NOT NULL,
                status TEXT NOT NULL,  -- 'success', 'error', 'in_progress'
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(source_schema, target_table, transformation_type)
            )
            """)
            # Grant access to readuser
            cur.execute(f"GRANT SELECT ON {TRANSFORMATION_TRACKING_SCHEMA}.{TRANSFORMATION_TRACKING_TABLE} TO {DB_READ_USER}")
        conn.commit()
        logger.info("✅ Table de suivi des transformations initialisée")
        return True
    except Exception as e:
        logger.error(f"❌ Impossible de créer la table de suivi: {str(e)}")
        return False

def calculate_tables_hash(bronze_conn, schema, tables):
    """Calcule un hash basé sur le nombre de lignes et la structure des tables source"""
    try:
        hash_data = []
        
        for table in tables:
            with bronze_conn.cursor() as cur:
                # Compter les lignes
                cur.execute(f"SELECT COUNT(*) FROM {schema}.{table}")
                row_count = cur.fetchone()[0]
                
                # Obtenir la structure de la table (colonnes)
                cur.execute("""
                    SELECT column_name, data_type 
                    FROM information_schema.columns 
                    WHERE table_schema = %s AND table_name = %s 
                    ORDER BY ordinal_position
                """, (schema, table))
                columns = cur.fetchall()
                
                table_info = f"{table}:{row_count}:{str(columns)}"
                hash_data.append(table_info)
        
        # Calculer le hash de l'ensemble
        combined_data = "|".join(sorted(hash_data))
        return hashlib.md5(combined_data.encode('utf-8')).hexdigest()
    except Exception as e:
        logger.warning(f"⚠️ Erreur lors du calcul du hash pour {schema}: {str(e)}")
        return None

def is_transformation_needed(silver_conn, source_schema, target_table, transformation_type, source_hash):
    """Vérifie si la transformation est nécessaire"""
    try:
        with silver_conn.cursor() as cur:
            cur.execute(f"""
            SELECT status, source_hash FROM {TRANSFORMATION_TRACKING_SCHEMA}.{TRANSFORMATION_TRACKING_TABLE}
            WHERE source_schema = %s AND target_table = %s AND transformation_type = %s
            """, (source_schema, target_table, transformation_type))
            result = cur.fetchone()
            
            if result:
                status, existing_hash = result
                if status == 'success' and existing_hash == source_hash:
                    logger.info(f"✓ {target_table} déjà transformé avec succès - ignoré.")
                    return False
                elif status == 'success' and existing_hash != source_hash:
                    logger.info(f"🔄 {target_table} nécessite une mise à jour (données modifiées).")
                    return True
                else:
                    logger.info(f"🔄 {target_table} nécessite un nouveau traitement (statut: {status}).")
                    return True
            else:
                logger.info(f"🆕 {target_table} pas encore transformé.")
                return True
    except Exception as e:
        logger.warning(f"⚠️ Erreur lors de la vérification de {target_table}: {str(e)}")
        # En cas d'erreur, on considère que la transformation est nécessaire
        return True

def update_transformation_status(silver_conn, source_schema, source_tables, target_schema, target_table, transformation_type, source_hash, row_count, status, error_message=None):
    """Met à jour le statut de transformation"""
    try:
        with silver_conn.cursor() as cur:
            cur.execute(f"""
            INSERT INTO {TRANSFORMATION_TRACKING_SCHEMA}.{TRANSFORMATION_TRACKING_TABLE}
            (source_schema, source_tables, target_schema, target_table, transformation_type, source_hash, row_count, status, error_message, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (source_schema, target_table, transformation_type) 
            DO UPDATE SET 
                source_tables = EXCLUDED.source_tables,
                target_schema = EXCLUDED.target_schema,
                source_hash = EXCLUDED.source_hash,
                row_count = EXCLUDED.row_count,
                status = EXCLUDED.status,
                error_message = EXCLUDED.error_message,
                updated_at = CURRENT_TIMESTAMP
            """, (source_schema, ",".join(source_tables), target_schema, target_table, transformation_type, source_hash, row_count, status, error_message))
        silver_conn.commit()
        logger.info(f"📊 Statut mis à jour pour {target_table}: {status}")
    except Exception as e:
        logger.error(f"❌ Impossible de mettre à jour le statut pour {target_table}: {str(e)}")

def main():
    logger.info("Démarrage du processus de transformation Bronze vers Silver...")
    try:
        # Création de la connexion à la base de données bronze
        bronze_conn = get_db_connection('bronze_db')
        
        # Création et configuration de la base de données silver
        create_silver_users()
        setup_silver_schema()
        
        # Connexion à silver après la configuration
        silver_conn = get_db_connection('silver_db')
        
        # Initialiser la table de suivi
        create_transformation_tracking_table(silver_conn)

        # Lecture des schémas
        logger.info("Récupération des schémas de bronze_db...")
        with bronze_conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT DISTINCT table_schema 
                FROM information_schema.tables 
                WHERE table_schema NOT IN ('pg_catalog', 'information_schema', 'public')
            """)
            schemas = [row['table_schema'] for row in cur.fetchall()]
        
        if not schemas:
            schemas = ['main', 'bestiary', 'class', 'spells', 'items', 'rules', 'races', 'book', 'adventure']
            logger.info(f"Aucun schéma trouvé dans bronze_db, utilisation des schémas par défaut: {schemas}")
        else:
            logger.info(f"Schémas trouvés: {schemas}")
        
        # Traitement des schémas
        for schema in schemas:
            if schema == 'main':
                # Pour le schéma main, copier directement toutes les tables
                logger.info("Traitement spécial du schéma main (copie directe)...")
                with bronze_conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT table_name 
                        FROM information_schema.tables 
                        WHERE table_schema = 'main' 
                        AND table_type = 'BASE TABLE'
                    """)
                    main_tables = [row['table_name'] for row in cur.fetchall()]
                    
                    for table in main_tables:
                        copy_table(bronze_conn, silver_conn, 'main', table)
            else:
                # Pour les autres schémas, traiter selon le modèle
                process_schema(bronze_conn, silver_conn, schema)
        
        # Fermeture des connexions
        bronze_conn.close()
        silver_conn.close()
        
        logger.info("✅ Processus de transformation Bronze vers Silver terminé avec succès")
        return 0
    except Exception as e:
        logger.error(f"❌ Erreur lors de la transformation Bronze vers Silver: {str(e)}")
        logger.error(traceback.format_exc())
        return 1

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except Exception as e:
        logger.error(f"❌ Erreur non gérée: {str(e)}")
        logger.error(traceback.format_exc())
        sys.exit(1)