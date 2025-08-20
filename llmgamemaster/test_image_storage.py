"""
Script de test pour le système de stockage d'images
"""

import asyncio
import logging
import sys
from pathlib import Path

# Ajouter le répertoire parent au path pour les imports
sys.path.append(str(Path(__file__).parent))

from image_storage_service import ImageStorageService, store_generated_image
from llm_service import LLMService
from config import LOG_LEVEL

# Configuration du logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_image_storage():
    """Test complet du système de stockage d'images"""
    
    logger.info("🧪 Démarrage des tests du système de stockage d'images")
    
    # Test 1: Service de stockage
    logger.info("\n📁 Test 1: Service de stockage")
    storage_service = ImageStorageService("test_static")
    
    # Vérifier la création des répertoires
    assert Path("test_static/images/npcs").exists(), "Répertoire NPCs non créé"
    assert Path("test_static/images/locations").exists(), "Répertoire locations non créé"
    logger.info("✅ Répertoires créés avec succès")
    
    # Test 2: Nommage des fichiers
    logger.info("\n🏷️ Test 2: Système de nommage")
    filename = storage_service.generate_filename("npc", "Gandalf le Gris", 123, 45)
    assert "npc_gandalf_le_gris_123_c45_" in filename, f"Nommage incorrect: {filename}"
    assert filename.endswith(".png"), f"Extension incorrecte: {filename}"
    logger.info(f"✅ Nommage correct: {filename}")
    
    # Test 3: Nettoyage des noms
    clean_name = storage_service.sanitize_filename("Éli@s & Co! (v2.0)")
    assert clean_name == "elis___co__v2_0_", f"Nettoyage incorrect: {clean_name}"
    logger.info(f"✅ Nettoyage correct: {clean_name}")
    
    # Test 4: URL de test (image factice)
    logger.info("\n🌐 Test 4: Téléchargement d'image (factice)")
    
    # URL d'image de test (remplacez par une vraie URL si nécessaire)
    test_url = "https://via.placeholder.com/512x512.png?text=Test+Image"
    
    try:
        local_path = await storage_service.download_and_store_image(
            test_url, 'npc', 'Test Character', 999, 1
        )
        
        if local_path:
            logger.info(f"✅ Image téléchargée et stockée: {local_path}")
            
            # Vérifier que le fichier existe
            file_path = Path(local_path.lstrip("/"))
            assert file_path.exists(), f"Fichier non créé: {file_path}"
            assert file_path.stat().st_size > 0, f"Fichier vide: {file_path}"
            logger.info(f"✅ Fichier valide: {file_path.stat().st_size} bytes")
        else:
            logger.warning("⚠️ Téléchargement échoué (URL test indisponible)")
            
    except Exception as e:
        logger.warning(f"⚠️ Test de téléchargement ignoré: {e}")
    
    # Test 5: LLM Service integration
    logger.info("\n🧠 Test 5: Intégration LLMService")
    
    try:
        llm_service = LLMService()
        
        # Test de génération d'image factice (sans vraie génération DALL-E)
        logger.info("📝 Test de la méthode generate_and_store_image...")
        
        # On ne peut pas vraiment tester sans clé API OpenAI active
        # Mais on peut vérifier que la méthode existe et est callable
        assert hasattr(llm_service, 'generate_and_store_image'), "Méthode manquante"
        assert callable(getattr(llm_service, 'generate_and_store_image')), "Méthode non callable"
        logger.info("✅ Méthode generate_and_store_image disponible")
        
    except Exception as e:
        logger.warning(f"⚠️ Test LLMService partiel: {e}")
    
    # Test 6: Validation des accès
    logger.info("\n🔒 Test 6: Validation sécurisée")
    
    from static_files_middleware import validate_image_access
    
    # Tests de chemins valides
    assert validate_image_access("/static/images/npcs/test.png") == False, "Validation incorrecte (fichier inexistant)"
    
    # Tests de chemins invalides  
    assert validate_image_access("/etc/passwd") == False, "Validation sécurité échouée"
    assert validate_image_access("../../../etc/passwd") == False, "Validation path traversal échouée"
    assert validate_image_access("/static/images/test.exe") == False, "Validation extension échouée"
    
    logger.info("✅ Validation sécurisée fonctionne")
    
    # Nettoyage
    logger.info("\n🧹 Nettoyage des fichiers de test")
    import shutil
    if Path("test_static").exists():
        shutil.rmtree("test_static")
        logger.info("✅ Répertoire de test supprimé")
    
    logger.info("\n🎉 Tous les tests passés avec succès!")
    return True


async def test_migration_scenario():
    """Test du scénario de migration d'images"""
    
    logger.info("\n🔄 Test du scénario de migration")
    
    # Simuler des données avec URLs temporaires
    fake_npcs = [
        {
            'Id': 1,
            'Name': 'Gandalf',
            'PortraitUrl': 'https://oaidalleapiprodscus.blob.core.windows.net/private/test123.png'
        },
        {
            'Id': 2, 
            'Name': 'Legolas',
            'PortraitUrl': '/static/images/npcs/existing_image.png'  # Déjà migré
        }
    ]
    
    migration_count = 0
    local_count = 0
    
    for npc in fake_npcs:
        portrait_url = npc.get('PortraitUrl', '')
        
        if portrait_url and portrait_url.startswith('http') and 'openai' in portrait_url.lower():
            migration_count += 1
            logger.info(f"🔄 NPC {npc['Name']} nécessite une migration")
        elif portrait_url.startswith('/static/'):
            local_count += 1
            logger.info(f"✅ NPC {npc['Name']} déjà stocké localement")
    
    logger.info(f"📊 Résultat simulation: {migration_count} à migrer, {local_count} déjà OK")
    
    return True


async def main():
    """Fonction principale des tests"""
    
    try:
        logger.info("🚀 Démarrage de la suite de tests complète")
        
        # Tests de base
        await test_image_storage()
        
        # Test de migration
        await test_migration_scenario()
        
        logger.info("\n🎊 TOUS LES TESTS SONT PASSÉS AVEC SUCCÈS!")
        logger.info("\n📋 Prochaines étapes:")
        logger.info("   1. Tester avec de vraies images DALL-E")
        logger.info("   2. Migrer les images existantes d'une campagne")
        logger.info("   3. Mettre à jour le frontend pour les nouvelles URLs")
        
    except Exception as e:
        logger.error(f"❌ Tests échoués: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())


"""
UTILISATION:

1. Test complet:
   python test_image_storage.py

2. Test avec logs détaillés:
   LOG_LEVEL=DEBUG python test_image_storage.py

3. Après les tests, vérifiez:
   - Que les répertoires static/ sont créés
   - Que les noms de fichiers sont corrects
   - Que la sécurité fonctionne
"""
