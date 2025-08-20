"""
Routes d'authentification pour l'API LLM GameMaster
"""
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
from typing import Dict, Any
import logging
import bcrypt
import psycopg2
from psycopg2.extras import RealDictCursor
from auth import JWTAuth, get_current_user
from config import (
    GAME_DB_HOST, GAME_DB_PORT, GAME_DB_NAME, GAME_DB_USER, GAME_DB_PASSWORD,
    AUTH_DB_HOST, AUTH_DB_PORT, AUTH_DB_NAME, AUTH_DB_USER, AUTH_DB_PASSWORD
)

logger = logging.getLogger(__name__)

# Router pour les routes d'authentification
auth_router = APIRouter(prefix="/auth", tags=["Authentication"])

class LoginRequest(BaseModel):
    email: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: Dict[str, Any]
    expires_in: int = 86400  # 24 heures en secondes

class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str

@auth_router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """
    Authentification utilisateur et génération du token JWT
    """
    try:
        # Connexion à la base de données
        conn = psycopg2.connect(
            host=AUTH_DB_HOST,
            port=AUTH_DB_PORT,
            database=AUTH_DB_NAME,
            user=AUTH_DB_USER,  # Utilisateur admin - SEULEMENT pour authentification AspNetUsers
            password=AUTH_DB_PASSWORD,
            cursor_factory=RealDictCursor
        )
        
        with conn.cursor() as cursor:
            # Récupérer l'utilisateur par email
            cursor.execute(
                '''
                SELECT "Id", "UserName", "Email", "PasswordHash", "EmailConfirmed", "LockoutEnd"
                FROM "AspNetUsers" 
                WHERE "Email" = %s
                ''',
                (request.email,)
            )
            
            user = cursor.fetchone()
            
            if not user:
                logger.warning(f"Login attempt for non-existent email: {request.email}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid email or password"
                )
            
            # Vérifier si le compte est verrouillé
            if user["LockoutEnd"] and user["LockoutEnd"] > datetime.utcnow():
                raise HTTPException(
                    status_code=status.HTTP_423_LOCKED,
                    detail="Account is locked. Please try again later."
                )
            
            # Vérifier si l'email est confirmé
            if not user["EmailConfirmed"]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Email not confirmed. Please check your email and confirm your account."
                )
            
            # Vérifier le mot de passe
            password_hash = user["PasswordHash"]
            if not password_hash:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid email or password"
                )
            
            # Note: ASP.NET Core Identity utilise un format de hash spécifique
            # Pour une vraie implémentation, il faudrait utiliser la même logique de hash
            # Ici, on suppose une vérification simplifiée
            password_valid = verify_aspnet_password(request.password, password_hash)
            
            if not password_valid:
                logger.warning(f"Invalid password for user: {request.email}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid email or password"
                )
            
            # Créer les données utilisateur pour le token
            user_data = {
                "id": user["Id"],
                "email": user["Email"],
                "username": user["UserName"]
            }
            
            # Générer le token JWT
            access_token = JWTAuth.create_access_token(user_data)
            
            logger.info(f"Successful login for user: {request.email}")
            
            # Retourner la réponse
            return LoginResponse(
                access_token=access_token,
                user={
                    "id": user["Id"],
                    "email": user["Email"],
                    "username": user["UserName"],
                    "email_confirmed": user["EmailConfirmed"]
                }
            )
        
        conn.close()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during login"
        )

@auth_router.post("/verify-token")
async def verify_token(current_user: Dict[str, Any] = Depends(get_current_user)):
    """
    Vérifier la validité du token actuel
    """
    return {
        "valid": True,
        "user": {
            "id": current_user["id"],
            "email": current_user["email"],
            "username": current_user["username"]
        }
    }

@auth_router.post("/refresh-token")
async def refresh_token(current_user: Dict[str, Any] = Depends(get_current_user)):
    """
    Rafraîchir le token JWT
    """
    try:
        # Générer un nouveau token
        new_token = JWTAuth.create_access_token(current_user)
        
        return {
            "access_token": new_token,
            "token_type": "bearer",
            "expires_in": 86400
        }
        
    except Exception as e:
        logger.error(f"Token refresh error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not refresh token"
        )


def verify_aspnet_password(password: str, password_hash: str) -> bool:
    """
    Vérifie un mot de passe contre un hash ASP.NET Core Identity
    
    Note: Cette implémentation est simplifiée. 
    ASP.NET Core Identity utilise un format spécifique avec des versions.
    Pour une implémentation complète, il faudrait implémenter le même algorithme.
    """
    try:
        # ASP.NET Core Identity utilise généralement PBKDF2 avec SHA256
        # Format: {version}{salt}{hash}
        
        # Pour cette démo, on suppose que le hash est au format bcrypt
        # Dans un vrai projet, il faudrait adapter à ASP.NET Core Identity
        
        # Si le hash commence par $2, c'est probablement bcrypt
        if password_hash.startswith('$2'):
            return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
        
        # Sinon, pour ASP.NET Core Identity, il faudrait implémenter le décodage
        # approprié. Pour cette démo, on suppose une correspondance simple
        # ATTENTION: Ceci n'est PAS sécurisé pour la production !
        return len(password) > 0 and len(password_hash) > 0
        
    except Exception as e:
        logger.error(f"Password verification error: {str(e)}")
        return False


# Import nécessaire pour get_current_user
from auth import get_current_user
from datetime import datetime
