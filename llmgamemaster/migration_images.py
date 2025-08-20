"""
Script de migration pour convertir les URLs temporaires existantes en images stockées localement
"""

import asyncio
import logging
import sys
import os
from pathlib import Path

# Ajouter le répertoire parent au path pour les imports
sys.path.append(str(Path(__file__).parent))

from db_service import DBService
from image_storage_service import ImageStorageService
from config import LOG_LEVEL

# Configuration du logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ImageMigrator:
    """Service de migration des images existantes"""
    
    def __init__(self):
        self.db_service = DBService()
        self.image_storage = ImageStorageService()
        
    async def migrate_campaign_images(self, campaign_id: int = None) -> dict:
        """
        Migrer les images d'une campagne spécifique ou toutes les campagnes
        
        Args:
            campaign_id: ID de la campagne ou None pour toutes
            
        Returns:
            Statistiques de migration
        """
        stats = {
            'npcs_processed': 0,
            'npcs_migrated': 0,
            'locations_processed': 0,
            'locations_migrated': 0,
            'characters_processed': 0,
            'characters_migrated': 0,
            'errors': 0
        }
        
        try:
            logger.info(f"🔄 Starting image migration for campaign {campaign_id or 'ALL'}")
            
            # Migrer les NPCs
            await self._migrate_npcs(campaign_id, stats)
            
            # Migrer les Locations
            await self._migrate_locations(campaign_id, stats)
            
            # Migrer les Characters (si demandé)
            # await self._migrate_characters(campaign_id, stats)
            
            logger.info(f"✅ Migration completed: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"❌ Migration failed: {e}")
            stats['errors'] += 1
            return stats
    
    async def _migrate_npcs(self, campaign_id: int, stats: dict):
        """Migrer les portraits des NPCs"""
        try:
            if campaign_id:
                npcs = self.db_service.get_campaign_npcs(campaign_id)
            else:
                # Pour migrer tous les NPCs, il faudrait une méthode get_all_npcs
                # Pour l'instant, on ne traite qu'une campagne à la fois
                logger.warning("Migration de tous les NPCs non implémentée - spécifiez une campagne")
                return
            
            for npc in npcs:
                stats['npcs_processed'] += 1
                portrait_url = npc.get('PortraitUrl', '')
                
                # Vérifier si c'est une URL temporaire à migrer
                if portrait_url and portrait_url.startswith('http') and 'openai' in portrait_url.lower():
                    try:
                        logger.info(f"🔄 Migrating NPC {npc['Name']} portrait...")
                        
                        local_path = await self.image_storage.download_and_store_image(
                            portrait_url, 'npc', npc['Name'], npc['Id'], campaign_id
                        )
                        
                        if local_path:
                            # Mettre à jour la base de données
                            self.db_service.update_npc(npc['Id'], portrait_url=local_path)
                            stats['npcs_migrated'] += 1
                            logger.info(f"✅ Migrated NPC {npc['Name']}: {local_path}")
                        else:
                            logger.error(f"❌ Failed to migrate NPC {npc['Name']}")
                            stats['errors'] += 1
                            
                    except Exception as e:
                        logger.error(f"❌ Error migrating NPC {npc['Name']}: {e}")
                        stats['errors'] += 1
                else:
                    logger.debug(f"ℹ️ NPC {npc['Name']} - no migration needed")
                    
        except Exception as e:
            logger.error(f"❌ Error in NPC migration: {e}")
            stats['errors'] += 1
    
    async def _migrate_locations(self, campaign_id: int, stats: dict):
        """Migrer les images des locations"""
        try:
            if campaign_id:
                locations = self.db_service.get_campaign_locations(campaign_id)
            else:
                logger.warning("Migration de toutes les locations non implémentée - spécifiez une campagne")
                return
            
            for location in locations:
                stats['locations_processed'] += 1
                image_url = location.get('ImageUrl', '')
                
                # Vérifier si c'est une URL temporaire à migrer
                if image_url and image_url.startswith('http') and 'openai' in image_url.lower():
                    try:
                        logger.info(f"🔄 Migrating location {location['Name']} image...")
                        
                        local_path = await self.image_storage.download_and_store_image(
                            image_url, 'location', location['Name'], location['Id'], campaign_id
                        )
                        
                        if local_path:
                            # Mettre à jour la base de données
                            self.db_service.update_location(location['Id'], image_url=local_path)
                            stats['locations_migrated'] += 1
                            logger.info(f"✅ Migrated location {location['Name']}: {local_path}")
                        else:
                            logger.error(f"❌ Failed to migrate location {location['Name']}")
                            stats['errors'] += 1
                            
                    except Exception as e:
                        logger.error(f"❌ Error migrating location {location['Name']}: {e}")
                        stats['errors'] += 1
                else:
                    logger.debug(f"ℹ️ Location {location['Name']} - no migration needed")
                    
        except Exception as e:
            logger.error(f"❌ Error in location migration: {e}")
            stats['errors'] += 1
    
    async def get_migration_status(self, campaign_id: int = None) -> dict:
        """
        Obtenir le statut des images à migrer
        
        Returns:
            Statistiques des images nécessitant une migration
        """
        status = {
            'npcs_to_migrate': 0,
            'locations_to_migrate': 0,
            'total_npcs': 0,
            'total_locations': 0
        }
        
        try:
            if campaign_id:
                # Analyser les NPCs
                npcs = self.db_service.get_campaign_npcs(campaign_id)
                status['total_npcs'] = len(npcs)
                
                for npc in npcs:
                    portrait_url = npc.get('PortraitUrl', '')
                    if portrait_url and portrait_url.startswith('http') and 'openai' in portrait_url.lower():
                        status['npcs_to_migrate'] += 1
                
                # Analyser les locations
                locations = self.db_service.get_campaign_locations(campaign_id)
                status['total_locations'] = len(locations)
                
                for location in locations:
                    image_url = location.get('ImageUrl', '')
                    if image_url and image_url.startswith('http') and 'openai' in image_url.lower():
                        status['locations_to_migrate'] += 1
            
            logger.info(f"📊 Migration status: {status}")
            return status
            
        except Exception as e:
            logger.error(f"❌ Error getting migration status: {e}")
            return status


async def main():
    """Fonction principale pour exécuter la migration"""
    
    import argparse
    parser = argparse.ArgumentParser(description="Migrate temporary image URLs to local storage")
    parser.add_argument("--campaign-id", type=int, help="Campaign ID to migrate (required)")
    parser.add_argument("--status", action="store_true", help="Show migration status only")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be migrated without doing it")
    
    args = parser.parse_args()
    
    if not args.campaign_id:
        logger.error("❌ Campaign ID is required. Use --campaign-id <id>")
        return
    
    migrator = ImageMigrator()
    
    try:
        if args.status:
            # Afficher le statut seulement
            status = await migrator.get_migration_status(args.campaign_id)
            print(f"\n📊 Migration Status for Campaign {args.campaign_id}:")
            print(f"   NPCs to migrate: {status['npcs_to_migrate']}/{status['total_npcs']}")
            print(f"   Locations to migrate: {status['locations_to_migrate']}/{status['total_locations']}")
            print(f"   Total items to migrate: {status['npcs_to_migrate'] + status['locations_to_migrate']}")
        
        elif args.dry_run:
            # Mode dry-run
            logger.info("🧪 DRY RUN MODE - No changes will be made")
            status = await migrator.get_migration_status(args.campaign_id)
            print(f"\n🧪 DRY RUN for Campaign {args.campaign_id}:")
            print(f"   Would migrate {status['npcs_to_migrate']} NPC portraits")
            print(f"   Would migrate {status['locations_to_migrate']} location images")
            print(f"   Total: {status['npcs_to_migrate'] + status['locations_to_migrate']} images")
        
        else:
            # Migration réelle
            logger.info(f"🚀 Starting migration for campaign {args.campaign_id}")
            stats = await migrator.migrate_campaign_images(args.campaign_id)
            
            print(f"\n✅ Migration completed for Campaign {args.campaign_id}:")
            print(f"   NPCs migrated: {stats['npcs_migrated']}/{stats['npcs_processed']}")
            print(f"   Locations migrated: {stats['locations_migrated']}/{stats['locations_processed']}")
            print(f"   Errors: {stats['errors']}")
            
            if stats['errors'] > 0:
                print(f"\n⚠️ There were {stats['errors']} errors during migration. Check logs for details.")
    
    except Exception as e:
        logger.error(f"❌ Migration script failed: {e}")
        print(f"\n❌ Migration failed: {e}")
    
    finally:
        # Fermer les connexions
        migrator.db_service.close_connections()


if __name__ == "__main__":
    asyncio.run(main())


"""
UTILISATION DU SCRIPT:

1. Vérifier le statut des images à migrer:
   python migration_images.py --campaign-id 1 --status

2. Test en mode dry-run:
   python migration_images.py --campaign-id 1 --dry-run

3. Migration réelle:
   python migration_images.py --campaign-id 1

4. Avec logs détaillés:
   LOG_LEVEL=DEBUG python migration_images.py --campaign-id 1

NOTES:
- Les images temporaires sont identifiées par l'URL contenant 'openai'
- Les images déjà stockées localement ne sont pas remigrer
- Les images échouées restent inchangées dans la DB
- Les logs détaillent toutes les opérations
"""
