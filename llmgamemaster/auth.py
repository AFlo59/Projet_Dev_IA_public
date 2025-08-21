"""
Système d'authentification JWT pour l'API LLM GameMaster
"""
import jwt
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import HTTPException, status, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import os
from config import (
    GAME_DB_HOST, GAME_DB_PORT, GAME_DB_NAME, GAME_DB_USER, GAME_DB_PASSWORD,
    AUTH_DB_HOST, AUTH_DB_PORT, AUTH_DB_NAME, AUTH_DB_USER, AUTH_DB_PASSWORD,
    JWT_SECRET_KEY, JWT_ALGORITHM, JWT_EXPIRATION_HOURS
)
import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

# JWT Configuration is now imported from config.py

# Bearer token security scheme
security = HTTPBearer()

class JWTAuth:
    """Gestionnaire d'authentification JWT"""
    
    @staticmethod
    def create_access_token(user_data: Dict[str, Any]) -> str:
        """
        Crée un token JWT pour un utilisateur
        """
        try:
            payload = {
                "user_id": user_data.get("id"),
                "email": user_data.get("email"),
                "username": user_data.get("username", ""),
                "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS),
                "iat": datetime.utcnow(),
                "type": "access"
            }
            
            token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
            logger.info(f"JWT token created for user {user_data.get('email')}")
            return token
            
        except Exception as e:
            logger.error(f"Error creating JWT token: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not create access token"
            )
    
    @staticmethod
    def verify_token(token: str) -> Dict[str, Any]:
        """
        Vérifie et décode un token JWT
        """
        try:
            payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
            
            # Vérifier que le token n'est pas expiré
            if datetime.utcnow() > datetime.fromtimestamp(payload["exp"]):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token expired"
                )
            
            return payload
            
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expired"
            )
        except (jwt.DecodeError, jwt.InvalidTokenError) as e:
            logger.warning(f"Invalid JWT token: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
    
    @staticmethod
    def get_user_from_db(user_id: str) -> Optional[Dict[str, Any]]:
        """
        Récupère les informations utilisateur depuis la base de données
        """
        try:
            conn = psycopg2.connect(
                host=AUTH_DB_HOST,
                port=AUTH_DB_PORT,
                database=AUTH_DB_NAME,
                user=AUTH_DB_USER,  # Utilisateur admin - SEULEMENT pour authentification
                password=AUTH_DB_PASSWORD,
                cursor_factory=RealDictCursor
            )
            
            with conn.cursor() as cursor:
                cursor.execute(
                    'SELECT "Id", "Email", "UserName", "EmailConfirmed" FROM "AspNetUsers" WHERE "Id" = %s',
                    (user_id,)
                )
                user = cursor.fetchone()
                
                if user:
                    return {
                        "id": user["Id"],
                        "email": user["Email"],
                        "username": user["UserName"],
                        "email_confirmed": user["EmailConfirmed"]
                    }
                    
            conn.close()
            return None
            
        except Exception as e:
            logger.error(f"Database error when fetching user: {str(e)}")
            return None


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """
    Dependency pour récupérer l'utilisateur actuel depuis le token JWT
    """
    try:
        # Vérifier le token
        payload = JWTAuth.verify_token(credentials.credentials)
        user_id = payload.get("user_id")
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload"
            )
        
        # Vérifier que l'utilisateur existe toujours en base
        user = JWTAuth.get_user_from_db(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        
        # Ajouter les infos du payload au user
        user.update({
            "token_exp": payload.get("exp"),
            "token_iat": payload.get("iat")
        })
        
        return user
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_current_user: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )


async def get_optional_user(request: Request) -> Optional[Dict[str, Any]]:
    """
    Dependency optionnelle pour récupérer l'utilisateur si authentifié
    Utilisée pour les endpoints qui peuvent fonctionner avec ou sans auth
    """
    try:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return None
            
        token = auth_header.replace("Bearer ", "")
        payload = JWTAuth.verify_token(token)
        user_id = payload.get("user_id")
        
        if user_id:
            return JWTAuth.get_user_from_db(user_id)
        
        return None
        
    except:
        # Si erreur d'auth, retourner None (pas d'erreur)
        return None


# Fonction utilitaire pour valider les permissions de campagne
async def validate_campaign_access(user: Dict[str, Any], campaign_id: int) -> bool:
    """
    Vérifie si l'utilisateur a accès à une campagne spécifique
    """
    try:
        conn = psycopg2.connect(
            host=GAME_DB_HOST,
            port=GAME_DB_PORT,
            database=GAME_DB_NAME,
            user=GAME_DB_USER,
            password=GAME_DB_PASSWORD,
            cursor_factory=RealDictCursor
        )
        
        with conn.cursor() as cursor:
            # Vérifier si l'utilisateur est le créateur de la campagne
            cursor.execute(
                'SELECT "Id" FROM "Campaigns" WHERE "Id" = %s AND "UserId" = %s',
                (campaign_id, user["id"])
            )
            
            if cursor.fetchone():
                conn.close()
                return True
            
            # Vérifier si l'utilisateur est un joueur dans la campagne
            cursor.execute(
                '''
                SELECT c."Id" FROM "Characters" c 
                WHERE c."CampaignId" = %s AND c."UserId" = %s
                ''',
                (campaign_id, user["id"])
            )
            
            if cursor.fetchone():
                conn.close()
                return True
        
        conn.close()
        return False
        
    except Exception as e:
        logger.error(f"Error validating campaign access: {str(e)}")
        return False
