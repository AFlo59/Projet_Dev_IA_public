#!/usr/bin/env python3
import os
import json
import time
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, Depends, HTTPException, status, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import jwt
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import logging
import api_routes

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Chargement des variables d'environnement
load_dotenv()

# Configuration de l'API
app = FastAPI(
    title="D&D DataReference API",
    description="API pour accéder aux données de référence D&D",
    version="1.0.0"
)

# Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Peut être modifié pour restreindre aux origines autorisées
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration de sécurité
security = HTTPBearer()
JWT_SECRET = os.getenv('JWT_SECRET_KEY') or os.getenv('JWT_SECRET')
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_MINUTES = 60

# Configuration de la base de données selon ENV_INFOS.md
SILVER_DB_HOST = os.getenv('SILVER_DB_HOST', 'datareference_silver_postgres')
SILVER_DB_PORT = os.getenv('SILVER_DB_PORT', '5432')  # Port interne est 5432, externe est 5436
SILVER_DB_NAME = os.getenv('SILVER_DB_NAME', 'silver_db')
DB_READ_USER = os.getenv('DB_READ_USER')
DB_READ_PASSWORD = os.getenv('DB_READ_PASSWORD')

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

def create_access_token(data: dict, expires_delta: timedelta = None):
    """Crée un token JWT"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=JWT_EXPIRATION_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return encoded_jwt

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

@app.get("/")
def read_root():
    """Point de terminaison racine pour vérifier que l'API est en ligne"""
    return {"message": "D&D DataReference API est en ligne"}

@app.post("/token")
def login_for_access_token(username: str, password: str):
    """Génère un token JWT pour l'authentification"""
    # Utiliser les variables d'environnement définies dans ENV_INFOS.md
    DB_ADMIN_USER = os.getenv('DB_ADMIN_USER')
    DB_ADMIN_PASSWORD = os.getenv('DB_ADMIN_PASSWORD')
    DB_READ_USER = os.getenv('DB_READ_USER')
    DB_READ_PASSWORD = os.getenv('DB_READ_PASSWORD')

    # Vérifier les identifiants
    if (username == DB_ADMIN_USER and password == DB_ADMIN_PASSWORD) or \
       (username == DB_READ_USER and password == DB_READ_PASSWORD):
        access_token = create_access_token(data={"sub": username})
        return {"access_token": access_token, "token_type": "bearer"}
    
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Identifiants incorrects",
        headers={"WWW-Authenticate": "Bearer"},
    )

@app.get("/schemas", dependencies=[Security(verify_token)])
def get_schemas():
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

@app.get("/tables/{schema}", dependencies=[Security(verify_token)])
def get_tables(schema: str):
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

@app.get("/data/{schema}/{table}", dependencies=[Security(verify_token)])
def get_table_data(schema: str, table: str, limit: int = 100, offset: int = 0):
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
            cur.execute(f"SELECT * FROM {schema}.{table} ORDER BY id LIMIT %s OFFSET %s", (limit, offset))
            rows = cur.fetchall()
            
            return {
                "schema": schema,
                "table": table,
                "columns": columns,
                "total_count": total_count,
                "limit": limit,
                "offset": offset,
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

@app.get("/search", dependencies=[Security(verify_token)])
def search_data(query: str, schema: Optional[str] = None, limit: int = 100):
    """Recherche dans les données en utilisant une requête textuelle"""
    conn = get_db_connection()
    try:
        results = []
        
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Si un schéma est spécifié, limiter la recherche à ce schéma
            if schema:
                cur.execute("""
                    SELECT table_schema, table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = %s
                    AND table_type = 'BASE TABLE'
                """, (schema,))
            else:
                cur.execute("""
                    SELECT table_schema, table_name 
                    FROM information_schema.tables 
                    WHERE table_schema NOT IN ('pg_catalog', 'information_schema', 'pg_toast', 'public')
                    AND table_type = 'BASE TABLE'
                """)
            
            tables = [(row['table_schema'], row['table_name']) for row in cur.fetchall()]
            
            # Recherche dans chaque table
            for table_schema, table_name in tables:
                try:
                    # Récupérer les colonnes de type texte
                    cur.execute("""
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_schema = %s AND table_name = %s
                        AND data_type IN ('text', 'character varying')
                    """, (table_schema, table_name))
                    
                    text_columns = [row['column_name'] for row in cur.fetchall()]
                    
                    if text_columns:
                        # Construire la condition de recherche
                        search_conditions = " OR ".join([f"\"{col}\"::text ILIKE %s" for col in text_columns])
                        search_values = [f"%{query}%" for _ in text_columns]
                        
                        # Exécuter la recherche
                        search_sql = f"""
                            SELECT * FROM {table_schema}.{table_name}
                            WHERE {search_conditions}
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
        
        return {"query": query, "results": results}
    
    except Exception as e:
        logger.error(f"Erreur lors de la recherche: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la recherche: {str(e)}"
        )
    finally:
        conn.close()

# Include API routes
app.include_router(api_routes.router)

@app.get("/health")
async def health_check():
    """Endpoint de vérification de santé"""
    return {"status": "ok", "message": "API is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000) 