"""
Middleware pour servir les fichiers statiques (images) stockés localement
"""

from fastapi import Request, Response
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import logging
import mimetypes

logger = logging.getLogger(__name__)

class ImageStaticFiles(StaticFiles):
    """
    Classe personnalisée pour servir les images stockées avec logs appropriés
    """
    
    def __init__(self, *, directory: str = "static", **kwargs):
        # S'assurer que le répertoire existe
        Path(directory).mkdir(parents=True, exist_ok=True)
        super().__init__(directory=directory, **kwargs)
        logger.info(f"📁 Static files middleware initialized for directory: {directory}")
    
    async def __call__(self, scope, receive, send):
        """
        Gérer les requêtes de fichiers statiques avec logs
        """
        if scope["type"] == "http":
            request = Request(scope, receive)
            
            # Vérifier si c'est une requête d'image
            if request.url.path.startswith("/static/images/"):
                logger.debug(f"📷 Serving image: {request.url.path}")
                
                # Ajouter les headers appropriés pour les images
                response = await super().__call__(scope, receive, send)
                return response
        
        return await super().__call__(scope, receive, send)


def setup_static_files(app, static_directory: str = "static"):
    """
    Configurer le middleware de fichiers statiques pour l'application
    
    Args:
        app: Instance FastAPI
        static_directory: Répertoire des fichiers statiques
    """
    try:
        # Créer le répertoire s'il n'existe pas
        static_path = Path(static_directory)
        static_path.mkdir(parents=True, exist_ok=True)
        
        # Créer les sous-répertoires d'images
        images_path = static_path / "images"
        images_path.mkdir(exist_ok=True)
        
        for subdir in ["characters", "npcs", "locations", "campaigns"]:
            (images_path / subdir).mkdir(exist_ok=True)
        
        # Monter le répertoire statique
        app.mount("/static", ImageStaticFiles(directory=str(static_path)), name="static")
        
        logger.info(f"✅ Static files middleware configured for {static_directory}")
        
        # Log des types MIME supportés pour les images
        image_types = ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg']
        for ext in image_types:
            mime_type = mimetypes.guess_type(f"test{ext}")[0]
            logger.debug(f"📄 {ext} -> {mime_type}")
            
    except Exception as e:
        logger.error(f"❌ Error setting up static files middleware: {e}")


def get_image_url(local_path: str, base_url: str = "") -> str:
    """
    Convertir un chemin local en URL publique
    
    Args:
        local_path: Chemin local de l'image (ex: "/static/images/npcs/...")
        base_url: URL de base du serveur (optionnel)
        
    Returns:
        URL complète pour accéder à l'image
    """
    if not local_path:
        return ""
    
    # S'assurer que le chemin commence par /static
    if not local_path.startswith("/static"):
        if local_path.startswith("static"):
            local_path = "/" + local_path
        else:
            local_path = "/static/" + local_path.lstrip("/")
    
    # Construire l'URL complète
    if base_url:
        return f"{base_url.rstrip('/')}{local_path}"
    else:
        return local_path


def validate_image_access(local_path: str) -> bool:
    """
    Valider qu'un chemin d'image est sécurisé et accessible
    
    Args:
        local_path: Chemin local de l'image
        
    Returns:
        True si l'accès est autorisé
    """
    try:
        # Vérifier que le chemin est dans le répertoire static
        if not local_path.startswith("/static/images/"):
            logger.warning(f"🚫 Image access denied - invalid path: {local_path}")
            return False
        
        # Vérifier que le fichier existe
        file_path = Path(local_path.lstrip("/"))
        if not file_path.exists():
            logger.warning(f"🚫 Image access denied - file not found: {local_path}")
            return False
        
        # Vérifier l'extension
        allowed_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg'}
        if file_path.suffix.lower() not in allowed_extensions:
            logger.warning(f"🚫 Image access denied - invalid extension: {local_path}")
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error validating image access for {local_path}: {e}")
        return False
