"""
Service de stockage permanent des images générées par IA
Télécharge et stocke localement les images temporaires de DALL-E
"""

import os
import re
import hashlib
import logging
import aiohttp
import asyncio
from pathlib import Path
from typing import Optional, Dict, Tuple
from urllib.parse import urlparse
from datetime import datetime

logger = logging.getLogger(__name__)

class ImageStorageService:
    """Service pour télécharger et stocker les images générées de manière permanente"""
    
    def __init__(self, base_storage_path: str = "static/images"):
        self.base_storage_path = Path(base_storage_path)
        self.ensure_directories()
        
    def ensure_directories(self):
        """Créer les dossiers de stockage nécessaires"""
        directories = [
            self.base_storage_path,
            self.base_storage_path / "characters",
            self.base_storage_path / "npcs", 
            self.base_storage_path / "locations",
            self.base_storage_path / "campaigns"
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
            logger.info(f"📁 Directory ensured: {directory}")
    
    def sanitize_filename(self, name: str) -> str:
        """Nettoyer un nom pour l'utiliser comme nom de fichier"""
        # Remplacer les caractères spéciaux par des underscores
        sanitized = re.sub(r'[^\w\s-]', '_', name)
        # Remplacer les espaces par des underscores
        sanitized = re.sub(r'\s+', '_', sanitized)
        # Supprimer les underscores multiples
        sanitized = re.sub(r'_+', '_', sanitized)
        # Supprimer les underscores au début et à la fin
        sanitized = sanitized.strip('_')
        # Limiter la longueur
        sanitized = sanitized[:50]
        
        return sanitized.lower()
    
    def generate_filename(self, element_type: str, element_name: str, element_id: int, 
                         campaign_id: int = None) -> str:
        """Générer un nom de fichier unique et descriptif"""
        
        # Nettoyer le nom
        clean_name = self.sanitize_filename(element_name)
        
        # Générer un timestamp pour l'unicité
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Construire le nom selon le type
        if campaign_id:
            filename = f"{element_type}_{clean_name}_{element_id}_c{campaign_id}_{timestamp}.png"
        else:
            filename = f"{element_type}_{clean_name}_{element_id}_{timestamp}.png"
            
        return filename
    
    def get_storage_path(self, element_type: str, filename: str) -> Path:
        """Obtenir le chemin de stockage pour un type d'élément"""
        
        type_mapping = {
            'character': 'characters',
            'npc': 'npcs',
            'location': 'locations',
            'campaign': 'campaigns'
        }
        
        subfolder = type_mapping.get(element_type, 'misc')
        return self.base_storage_path / subfolder / filename
    
    async def download_and_store_image(self, image_url: str, element_type: str, 
                                     element_name: str, element_id: int,
                                     campaign_id: int = None) -> Optional[str]:
        """
        Télécharger une image depuis une URL temporaire et la stocker localement
        
        Args:
            image_url: URL temporaire de l'image (DALL-E)
            element_type: Type d'élément ('character', 'npc', 'location', etc.)
            element_name: Nom de l'élément
            element_id: ID de l'élément en base
            campaign_id: ID de la campagne (optionnel)
            
        Returns:
            Chemin local de l'image stockée ou None si erreur
        """
        try:
            if not image_url or not image_url.startswith('http'):
                logger.warning(f"Invalid image URL: {image_url}")
                return None
            
            # Générer le nom de fichier
            filename = self.generate_filename(element_type, element_name, element_id, campaign_id)
            storage_path = self.get_storage_path(element_type, filename)
            
            logger.info(f"📥 Downloading image for {element_type} '{element_name}' from {image_url[:50]}...")
            
            # Télécharger l'image
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url, timeout=30) as response:
                    if response.status == 200:
                        # Lire le contenu de l'image
                        image_data = await response.read()
                        
                        # Vérifier que c'est bien une image
                        if len(image_data) < 1000:  # Image trop petite, probablement une erreur
                            logger.error(f"Downloaded image too small ({len(image_data)} bytes)")
                            return None
                        
                        # Sauvegarder l'image
                        with open(storage_path, 'wb') as f:
                            f.write(image_data)
                        
                        # Vérifier que le fichier a été créé avec succès
                        if storage_path.exists() and storage_path.stat().st_size > 0:
                            relative_path = f"/{storage_path.relative_to(self.base_storage_path.parent)}"
                            logger.info(f"✅ Image saved successfully: {relative_path}")
                            return relative_path
                        else:
                            logger.error(f"Failed to save image to {storage_path}")
                            return None
                    else:
                        logger.error(f"Failed to download image: HTTP {response.status}")
                        return None
                        
        except asyncio.TimeoutError:
            logger.error(f"Timeout downloading image from {image_url}")
            return None
        except Exception as e:
            logger.error(f"Error downloading and storing image: {e}")
            return None
    
    def get_image_info(self, local_path: str) -> Dict[str, any]:
        """Obtenir des informations sur une image stockée"""
        try:
            full_path = Path(local_path.lstrip('/'))
            
            if full_path.exists():
                stat = full_path.stat()
                return {
                    'exists': True,
                    'size': stat.st_size,
                    'created': datetime.fromtimestamp(stat.st_ctime),
                    'modified': datetime.fromtimestamp(stat.st_mtime),
                    'absolute_path': str(full_path.absolute())
                }
            else:
                return {'exists': False}
                
        except Exception as e:
            logger.error(f"Error getting image info for {local_path}: {e}")
            return {'exists': False, 'error': str(e)}
    
    def cleanup_old_images(self, days_old: int = 30) -> Dict[str, int]:
        """Nettoyer les anciennes images (optionnel, pour maintenance)"""
        try:
            from datetime import timedelta
            cutoff_date = datetime.now() - timedelta(days=days_old)
            
            stats = {'checked': 0, 'deleted': 0, 'errors': 0}
            
            for image_path in self.base_storage_path.rglob("*.png"):
                try:
                    stats['checked'] += 1
                    
                    # Vérifier la date de création
                    if datetime.fromtimestamp(image_path.stat().st_ctime) < cutoff_date:
                        image_path.unlink()  # Supprimer le fichier
                        stats['deleted'] += 1
                        logger.info(f"🗑️ Deleted old image: {image_path}")
                        
                except Exception as e:
                    stats['errors'] += 1
                    logger.error(f"Error deleting {image_path}: {e}")
            
            logger.info(f"🧹 Cleanup completed: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            return {'checked': 0, 'deleted': 0, 'errors': 1}
    
    async def migrate_existing_urls(self, db_service, campaign_id: int = None) -> Dict[str, int]:
        """
        Migrer les URLs temporaires existantes vers le stockage local
        
        Args:
            db_service: Service de base de données
            campaign_id: ID de campagne spécifique ou None pour toutes
            
        Returns:
            Statistiques de migration
        """
        stats = {'npcs_migrated': 0, 'locations_migrated': 0, 'characters_migrated': 0, 'errors': 0}
        
        try:
            # Migrer les NPCs
            if campaign_id:
                npcs = db_service.get_campaign_npcs(campaign_id)
            else:
                # TODO: Méthode pour récupérer tous les NPCs
                npcs = []
            
            for npc in npcs:
                portrait_url = npc.get('PortraitUrl', '')
                if portrait_url and portrait_url.startswith('http'):
                    try:
                        local_path = await self.download_and_store_image(
                            portrait_url, 'npc', npc['Name'], npc['Id'], campaign_id
                        )
                        if local_path:
                            db_service.update_npc(npc['Id'], portrait_url=local_path)
                            stats['npcs_migrated'] += 1
                            logger.info(f"✅ Migrated NPC {npc['Name']} image")
                    except Exception as e:
                        stats['errors'] += 1
                        logger.error(f"Error migrating NPC {npc['Name']} image: {e}")
            
            # Migrer les Locations
            if campaign_id:
                locations = db_service.get_campaign_locations(campaign_id)
            else:
                locations = []
                
            for location in locations:
                image_url = location.get('ImageUrl', '')
                if image_url and image_url.startswith('http'):
                    try:
                        local_path = await self.download_and_store_image(
                            image_url, 'location', location['Name'], location['Id'], campaign_id
                        )
                        if local_path:
                            db_service.update_location(location['Id'], image_url=local_path)
                            stats['locations_migrated'] += 1
                            logger.info(f"✅ Migrated location {location['Name']} image")
                    except Exception as e:
                        stats['errors'] += 1
                        logger.error(f"Error migrating location {location['Name']} image: {e}")
            
            logger.info(f"📦 Migration completed: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Error during migration: {e}")
            stats['errors'] += 1
            return stats


# Instance globale du service
image_storage_service = ImageStorageService()


# Fonction helper pour les autres services
async def store_generated_image(image_url: str, element_type: str, element_name: str, 
                               element_id: int, campaign_id: int = None) -> Optional[str]:
    """
    Fonction helper pour stocker une image générée
    
    Args:
        image_url: URL temporaire de l'image
        element_type: 'character', 'npc', 'location', etc.
        element_name: Nom de l'élément
        element_id: ID en base de données
        campaign_id: ID de la campagne (optionnel)
        
    Returns:
        Chemin local de l'image ou None si erreur
    """
    return await image_storage_service.download_and_store_image(
        image_url, element_type, element_name, element_id, campaign_id
    )
