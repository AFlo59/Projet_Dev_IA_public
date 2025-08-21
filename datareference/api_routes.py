#!/usr/bin/env python3
import os
import json
import time
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import APIRouter, Depends, HTTPException, status, Security, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import List, Dict, Any, Optional
import logging
import jwt
from datetime import datetime, timedelta

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration de sécurité
security = HTTPBearer()
JWT_SECRET = os.getenv('JWT_SECRET_KEY') or os.getenv('JWT_SECRET')
JWT_ALGORITHM = "HS256"

# Configuration de la base de données selon ENV_INFOS.md
SILVER_DB_HOST = os.getenv('SILVER_DB_HOST', 'datareference_silver_postgres')
SILVER_DB_PORT = os.getenv('SILVER_DB_PORT', '5432')  # Port interne est 5432, externe est 5436
SILVER_DB_NAME = os.getenv('SILVER_DB_NAME', 'silver_db')
DB_READ_USER = os.getenv('DB_READ_USER')
DB_READ_PASSWORD = os.getenv('DB_READ_PASSWORD')

# Création du router
router = APIRouter(prefix="/api", tags=["D&D Reference Data"])

def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    """Vérifie la validité du token JWT"""
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide ou expiré",
            headers={"WWW-Authenticate": "Bearer"},
        )

def get_database_connection():
    """Alias for compatibility with tests"""
    return get_db_connection()

def get_db_connection():
    """Établit une connexion à la base de données Silver"""
    try:
        conn = psycopg2.connect(
            host=SILVER_DB_HOST,
            port=SILVER_DB_PORT,
            dbname=SILVER_DB_NAME,
            user=DB_READ_USER,
            password=DB_READ_PASSWORD
        )
        return conn
    except Exception as e:
        logger.error(f"Erreur de connexion à la base de données: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service de base de données non disponible"
        )

@router.get("/info")
def get_api_info(token: str = Depends(verify_token)):
    """Récupère les informations de l'API"""
    return {
        "name": "D&D DataReference API",
        "version": "1.0.0",
        "database": SILVER_DB_NAME,
        "database_host": SILVER_DB_HOST
    }

@router.get("/schemas")
def get_schemas(token: str = Depends(verify_token)):
    """Récupère la liste des schémas disponibles"""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT schema_name 
                FROM information_schema.schemata 
                WHERE schema_name NOT IN ('pg_catalog', 'information_schema', 'pg_toast', 'public')
                ORDER BY schema_name
            """)
            schemas = [row['schema_name'] for row in cur.fetchall()]
        return {"schemas": schemas}
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des schémas: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération des schémas: {str(e)}"
        )
    finally:
        conn.close()

@router.get("/tables/{schema}")
def get_tables(schema: str, token: str = Depends(verify_token)):
    """Récupère la liste des tables dans un schéma"""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = %s
                AND table_type = 'BASE TABLE'
                ORDER BY table_name
            """, (schema,))
            tables = [row['table_name'] for row in cur.fetchall()]
        return {"schema": schema, "tables": tables}
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des tables: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération des tables: {str(e)}"
        )
    finally:
        conn.close()

@router.get("/columns/{schema}/{table}")
def get_columns(schema: str, table: str, token: str = Depends(verify_token)):
    """Récupère la liste des colonnes d'une table"""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns 
                WHERE table_schema = %s
                AND table_name = %s
                ORDER BY ordinal_position
            """, (schema, table))
            columns = cur.fetchall()
        return {"schema": schema, "table": table, "columns": columns}
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des colonnes: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération des colonnes: {str(e)}"
        )
    finally:
        conn.close()

@router.get("/data/{schema}/{table}")
def get_table_data(
    schema: str, 
    table: str, 
    limit: int = Query(100, ge=1, le=1000), 
    offset: int = Query(0, ge=0),
    order_by: str = "id",
    order_dir: str = "asc",
    token: str = Depends(verify_token)
):
    """Récupère les données d'une table"""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Vérifier que la table existe
            cur.execute("""
                SELECT 1 FROM information_schema.tables 
                WHERE table_schema = %s AND table_name = %s
            """, (schema, table))
            if not cur.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Table {schema}.{table} non trouvée"
                )
            
            # Vérifier que la colonne de tri existe
            cur.execute("""
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = %s AND table_name = %s AND column_name = %s
            """, (schema, table, order_by))
            if not cur.fetchone():
                order_by = "id"  # Fallback to id if column doesn't exist
            
            # Validation de order_dir
            if order_dir.lower() not in ["asc", "desc"]:
                order_dir = "asc"
            
            # Récupérer les colonnes
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_schema = %s AND table_name = %s
                ORDER BY ordinal_position
            """, (schema, table))
            columns = [row['column_name'] for row in cur.fetchall()]
            
            # Récupérer le compte total
            cur.execute(f"SELECT COUNT(*) FROM {schema}.{table}")
            total_count = cur.fetchone()['count']
            
            # Récupérer les données
            query = f"SELECT * FROM {schema}.{table} ORDER BY {order_by} {order_dir} LIMIT %s OFFSET %s"
            cur.execute(query, (limit, offset))
            rows = cur.fetchall()
            
            return {
                "schema": schema,
                "table": table,
                "columns": columns,
                "total_count": total_count,
                "limit": limit,
                "offset": offset,
                "order_by": order_by,
                "order_dir": order_dir,
                "data": rows
            }
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des données: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération des données: {str(e)}"
        )
    finally:
        conn.close()

@router.get("/record/{schema}/{table}/{id}")
def get_record_by_id(
    schema: str, 
    table: str, 
    id: int,
    token: str = Depends(verify_token)
):
    """Récupère un enregistrement spécifique par son ID"""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Vérifier que la table existe
            cur.execute("""
                SELECT 1 FROM information_schema.tables 
                WHERE table_schema = %s AND table_name = %s
            """, (schema, table))
            if not cur.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Table {schema}.{table} non trouvée"
                )
            
            # Vérifier que la colonne id existe
            cur.execute("""
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = %s AND table_name = %s AND column_name = 'id'
            """, (schema, table))
            if not cur.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"La table {schema}.{table} n'a pas de colonne 'id'"
                )
            
            # Récupérer l'enregistrement
            cur.execute(f"SELECT * FROM {schema}.{table} WHERE id = %s", (id,))
            record = cur.fetchone()
            
            if not record:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Enregistrement avec id={id} non trouvé dans {schema}.{table}"
                )
            
            return {
                "schema": schema,
                "table": table,
                "id": id,
                "data": record
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de l'enregistrement: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération de l'enregistrement: {str(e)}"
        )
    finally:
        conn.close()

@router.get("/search")
def search_data(
    query: str,
    schema: Optional[str] = None,
    table: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    token: str = Depends(verify_token)
):
    """Recherche dans les données en utilisant une requête textuelle"""
    conn = get_db_connection()
    try:
        results = []
        
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Construire la requête pour obtenir les tables à rechercher
            tables_query = """
                SELECT table_schema, table_name 
                FROM information_schema.tables 
                WHERE table_type = 'BASE TABLE'
            """
            
            query_params = []
            
            # Filtrer par schéma si spécifié
            if schema:
                tables_query += " AND table_schema = %s"
                query_params.append(schema)
            else:
                tables_query += " AND table_schema NOT IN ('pg_catalog', 'information_schema', 'pg_toast', 'public')"
            
            # Filtrer par table si spécifiée
            if table:
                tables_query += " AND table_name = %s"
                query_params.append(table)
            
            # Exécuter la requête pour obtenir les tables
            cur.execute(tables_query, query_params)
            tables = [(row['table_schema'], row['table_name']) for row in cur.fetchall()]
            
            # Recherche dans chaque table
            for table_schema, table_name in tables:
                try:
                    # Récupérer les colonnes de type texte
                    cur.execute("""
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_schema = %s AND table_name = %s
                        AND data_type IN ('text', 'character varying', 'varchar', 'jsonb')
                    """, (table_schema, table_name))
                    
                    text_columns = [row['column_name'] for row in cur.fetchall()]
                    
                    if text_columns:
                        # Construire la condition de recherche pour les colonnes texte
                        text_conditions = []
                        search_values = []
                        
                        for col in text_columns:
                            if col == 'json_data':
                                # Recherche dans JSONB
                                text_conditions.append(f"json_data::text ILIKE %s")
                            else:
                                # Recherche dans les colonnes texte normales
                                text_conditions.append(f"\"{col}\"::text ILIKE %s")
                            
                            search_values.append(f"%{query}%")
                        
                        # Exécuter la recherche
                        search_sql = f"""
                            SELECT * FROM {table_schema}.{table_name}
                            WHERE {' OR '.join(text_conditions)}
                            LIMIT %s
                        """
                        cur.execute(search_sql, search_values + [limit])
                        
                        rows = cur.fetchall()
                        if rows:
                            results.append({
                                "schema": table_schema,
                                "table": table_name,
                                "count": len(rows),
                                "data": rows
                            })
                except Exception as table_error:
                    logger.warning(f"Erreur lors de la recherche dans {table_schema}.{table_name}: {table_error}")
                    continue
        
        return {
            "query": query,
            "schema_filter": schema,
            "table_filter": table,
            "total_results": sum(r['count'] for r in results),
            "result_tables": len(results),
            "results": results
        }
    
    except Exception as e:
        logger.error(f"Erreur lors de la recherche: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la recherche: {str(e)}"
        )
    finally:
        conn.close()

@router.get("/dnd/{category}")
def get_dnd_category(
    category: str,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    token: str = Depends(verify_token)
):
    """
    Récupère des données par catégorie D&D
    
    Catégories disponibles:
    - monsters: Créatures et monstres
    - spells: Sorts
    - items: Objets magiques
    - classes: Classes de personnage
    - races: Races de personnage
    - backgrounds: Historiques
    - feats: Talents
    """
    
    # Mapping des catégories aux schémas/tables
    category_mapping = {
        "adventures": {"schema": "adventure", "table": "fusion_adventure"},
        "books": {"schema": "book", "table": "fusion_book"},
        "monsters": {"schema": "bestiary", "table": "fusion_monsters"},
        "legendarygroups": {"schema": "bestiary", "table": "legendarygroups"},
        "fluff_bestiary": {"schema": "bestiary", "table": "fusion_fluff_bestiary"},
        "spells": {"schema": "spells", "table": "fusion_spells"},
        "fluff_spells": {"schema": "spells", "table": "fusion_fluff_spells"},
        "classes": {"schema": "class", "table": "fusion_class"},
        "actions": {"schema": "main", "table": "actions"},
        "foundry_actions": {"schema": "main", "table": "foundry_actions"},
        "backgrounds": {"schema": "main", "table": "background"},
        "fluff_backgrounds": {"schema": "main", "table": "fluff_backgrounds"},
        "charcreationoptions": {"schema": "main", "table": "charcreationoptions"},
        "fluff_charcreationoptions": {"schema": "main", "table": "fluff_charcreationoptions"},
        "conditions&diseases": {"schema": "main", "table": "conditionsdiseases"},
        "fluff_conditions&diseases": {"schema": "main", "table": "fluff_conditionsdiseases"},
        "deities": {"schema": "main", "table": "deities"},
        "encounters": {"schema": "main", "table": "encounters"},
        "feats": {"schema": "main", "table": "feats"},
        "fluff_feats": {"schema": "main", "table": "fluff_feats"},
        "foundry_feats": {"schema": "main", "table": "foundry_feats"},
        "items": {"schema": "main", "table": "items"},
        "fluff_items": {"schema": "main", "table": "fluff_items"},
        "foundry_items": {"schema": "main", "table": "foundry_items"},
        "items_base": {"schema": "main", "table": "items_base"},
        "languages": {"schema": "main", "table": "languages"},
        "fluff_languages": {"schema": "main", "table": "fluff_languages"},
        "life": {"schema": "main", "table": "life"},
        "loot": {"schema": "main", "table": "loot"},
        "magicvariants": {"schema": "main", "table": "magicvariants"},
        "makebrew_creature": {"schema": "main", "table": "makebrew_creature"},
        "makecards": {"schema": "main", "table": "makecards"},
        "monsterfeatures": {"schema": "main", "table": "monsterfeatures"},
        "msbcr": {"schema": "main", "table": "msbcr"},
        "names": {"schema": "main", "table": "names"},
        "objects": {"schema": "main", "table": "objects"},
        "fluff_objects": {"schema": "main", "table": "fluff_objects"},
        "optionalfeatures": {"schema": "main", "table": "optionalfeatures"},
        "fluff_optionalfeatures": {"schema": "main", "table": "fluff_optionalfeatures"},
        "foundry_optionalfeatures": {"schema": "main", "table": "foundry_optionalfeatures"},
        "psionics": {"schema": "main", "table": "psionics"},
        "foundry_psionics": {"schema": "main", "table": "foundry_psionics"},
        "races": {"schema": "main", "table": "races"},
        "fluff_races": {"schema": "main", "table": "fluff_races"},
        "foundry_races": {"schema": "main", "table": "foundry_races"},
        "recipes": {"schema": "main", "table": "recipes"},
        "fluff_recipes": {"schema": "main", "table": "fluff_recipes"},
        "rewards": {"schema": "main", "table": "rewards"},
        "fluff_rewards": {"schema": "main", "table": "fluff_rewards"},
        "foundry_rewards": {"schema": "main", "table": "foundry_rewards"},
        "senses": {"schema": "main", "table": "senses"},
        "skills": {"schema": "main", "table": "skills"},
        "tables": {"schema": "main", "table": "tables"},
        "trapshazards": {"schema": "main", "table": "trapshazards"},
        "fluff_trapshazards": {"schema": "main", "table": "fluff_trapshazards"},
        "variantrules": {"schema": "main", "table": "variantrules"},
        "vehicles": {"schema": "main", "table": "vehicles"},
        "fluff_vehicles": {"schema": "main", "table": "fluff_vehicles"},
        "foundry_vehicles": {"schema": "main", "table": "foundry_vehicles"}
    }
    
    if category not in category_mapping:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Catégorie '{category}' non reconnue. Catégories disponibles: {', '.join(category_mapping.keys())}"
        )
    
    schema = category_mapping[category]["schema"]
    table = category_mapping[category]["table"]
    
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Vérifier que la table existe
            cur.execute("""
                SELECT 1 FROM information_schema.tables 
                WHERE table_schema = %s AND table_name = %s
            """, (schema, table))
            
            if not cur.fetchone():
                # Si la table de fusion n'existe pas, essayer avec une autre table du même schéma
                cur.execute("""
                    SELECT table_name FROM information_schema.tables
                    WHERE table_schema = %s
                    AND table_type = 'BASE TABLE'
                    LIMIT 1
                """, (schema,))
                
                alt_table = cur.fetchone()
                if not alt_table:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Données pour la catégorie '{category}' non disponibles"
                    )
                
                table = alt_table['table_name']
            
            # Récupérer le compte total
            cur.execute(f"SELECT COUNT(*) FROM {schema}.{table}")
            total_count = cur.fetchone()['count']
            
            # Récupérer les données
            cur.execute(f"SELECT * FROM {schema}.{table} ORDER BY id LIMIT %s OFFSET %s", (limit, offset))
            rows = cur.fetchall()
            
            return {
                "category": category,
                "schema": schema,
                "table": table,
                "total_count": total_count,
                "limit": limit,
                "offset": offset,
                "data": rows
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des données de catégorie: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération des données: {str(e)}"
        )
    finally:
        conn.close()

@router.get("/statistics")
def get_database_statistics(token: str = Depends(verify_token)):
    """Récupère des statistiques sur la base de données"""
    conn = get_db_connection()
    try:
        stats = {
            "schemas": {},
            "total_tables": 0,
            "total_records": 0
        }
        
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Récupérer tous les schémas
            cur.execute("""
                SELECT schema_name 
                FROM information_schema.schemata 
                WHERE schema_name NOT IN ('pg_catalog', 'information_schema', 'pg_toast', 'public')
            """)
            
            schemas = [row['schema_name'] for row in cur.fetchall()]
            
            # Pour chaque schéma, récupérer les tables et le nombre d'enregistrements
            for schema in schemas:
                stats["schemas"][schema] = {
                    "tables": [],
                    "total_tables": 0,
                    "total_records": 0
                }
                
                # Récupérer toutes les tables du schéma
                cur.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = %s
                    AND table_type = 'BASE TABLE'
                """, (schema,))
                
                tables = [row['table_name'] for row in cur.fetchall()]
                stats["schemas"][schema]["total_tables"] = len(tables)
                stats["total_tables"] += len(tables)
                
                # Pour chaque table, récupérer le nombre d'enregistrements
                for table in tables:
                    try:
                        cur.execute(f"SELECT COUNT(*) FROM {schema}.{table}")
                        count = cur.fetchone()['count']
                        
                        stats["schemas"][schema]["tables"].append({
                            "name": table,
                            "records": count
                        })
                        
                        stats["schemas"][schema]["total_records"] += count
                        stats["total_records"] += count
                    except Exception as e:
                        logger.warning(f"Erreur lors du comptage des enregistrements dans {schema}.{table}: {e}")
                        stats["schemas"][schema]["tables"].append({
                            "name": table,
                            "records": "Erreur"
                        })
        
        return stats
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des statistiques: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération des statistiques: {str(e)}"
        )
    finally:
        conn.close() 