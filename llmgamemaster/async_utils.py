import asyncio
import time
from typing import List, Dict, Any, Callable, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

logger = logging.getLogger(__name__)

class ContentGenerationOptimizer:
    """Optimiseur pour la génération de contenu avec gestion intelligente du parallélisme"""
    
    def __init__(self, max_workers: int = 4, batch_size: int = 3):
        self.max_workers = max_workers
        self.batch_size = batch_size
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        
    async def generate_content_parallel(self, 
                                      campaign: Dict[str, Any], 
                                      content_types: List[str]) -> Dict[str, Any]:
        """
        Génère du contenu en parallèle avec optimisation intelligente
        """
        start_time = time.time()
        results = {
            "locations": [],
            "npcs": [],
            "quests": [],
            "images": [],
            "performance": {
                "total_time": 0,
                "parallel_efficiency": 0,
                "bottlenecks": []
            }
        }
        
        try:
            # PHASE 1: Génération des locations en parallèle
            if "locations" in content_types:
                logger.info("🏗️ Starting parallel location generation")
                locations_start = time.time()
                
                # Générer la ville principale et les sous-lieux en parallèle
                main_town_task = asyncio.create_task(self._generate_main_town(campaign))
                
                # Attendons la ville principale avant de générer les sous-lieux
                main_town = await main_town_task
                results["locations"].append(main_town)
                
                # Générer les sous-lieux en parallèle
                sub_locations = await self._generate_sub_locations_parallel(campaign, main_town)
                results["locations"].extend(sub_locations)
                
                locations_time = time.time() - locations_start
                logger.info(f"✅ Locations generated in {locations_time:.2f}s")
                
            # PHASE 2: Génération des NPCs en parallèle par location
            if "npcs" in content_types and results["locations"]:
                logger.info("👥 Starting parallel NPC generation")
                npcs_start = time.time()
                
                all_npcs = await self._generate_npcs_parallel(campaign, results["locations"])
                results["npcs"] = all_npcs
                
                npcs_time = time.time() - npcs_start
                logger.info(f"✅ NPCs generated in {npcs_time:.2f}s")
                
            # PHASE 3: Génération des quêtes en parallèle
            if "quests" in content_types and results["npcs"]:
                logger.info("📜 Starting parallel quest generation")
                quests_start = time.time()
                
                quests = await self._generate_quests_parallel(campaign, results["locations"], results["npcs"])
                results["quests"] = quests
                
                quests_time = time.time() - quests_start
                logger.info(f"✅ Quests generated in {quests_time:.2f}s")
                
            # PHASE 4: Génération des images en arrière-plan (non-bloquant)
            if "images" in content_types:
                logger.info("🎨 Starting background image generation")
                asyncio.create_task(self._generate_images_background(campaign["Id"], results))
                
            # Calcul des métriques de performance
            total_time = time.time() - start_time
            results["performance"]["total_time"] = total_time
            results["performance"]["parallel_efficiency"] = self._calculate_efficiency(results)
            
            logger.info(f"🚀 Total content generation completed in {total_time:.2f}s")
            return results
            
        except Exception as e:
            logger.error(f"❌ Error in parallel content generation: {str(e)}")
            results["error"] = str(e)
            return results
    
    async def _generate_main_town(self, campaign: Dict[str, Any]) -> Dict[str, Any]:
        """Génère la ville principale"""
        from app import generate_main_town  # Import local pour éviter les cycles
        return await generate_main_town(campaign)
    
    async def _generate_sub_locations_parallel(self, 
                                             campaign: Dict[str, Any], 
                                             main_town: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Génère les sous-lieux en parallèle"""
        # Types de lieux à générer
        location_types = [
            {"type": "Castle", "priority": 1},
            {"type": "Market", "priority": 2}, 
            {"type": "Inn", "priority": 2},
            {"type": "Temple", "priority": 3},
            {"type": "Guild Hall", "priority": 3},
            {"type": "Library", "priority": 3}
        ]
        
        # Créer les tâches en parallèle
        tasks = []
        for i, location_info in enumerate(location_types[:5]):  # Max 5 locations
            task = asyncio.create_task(
                self._generate_single_location(campaign, main_town, location_info["type"])
            )
            tasks.append(task)
        
        # Exécuter en parallèle avec limite
        sub_locations = []
        for batch in self._batch_tasks(tasks, self.batch_size):
            batch_results = await asyncio.gather(*batch, return_exceptions=True)
            for result in batch_results:
                if isinstance(result, Exception):
                    logger.error(f"Location generation failed: {result}")
                else:
                    sub_locations.append(result)
        
        return sub_locations
    
    async def _generate_single_location(self, 
                                      campaign: Dict[str, Any], 
                                      main_town: Dict[str, Any], 
                                      location_type: str) -> Dict[str, Any]:
        """Génère un seul lieu"""
        from app import generate_location_name, generate_location_description, db_service
        
        # Génération en parallèle du nom et de la description
        name_task = asyncio.create_task(generate_location_name(campaign, location_type))
        
        location_name = await name_task
        description_task = asyncio.create_task(
            generate_location_description(campaign, location_type, location_name)
        )
        
        location_description = await description_task
        
        # Création en base
        location_data = {
            "type": location_type,
            "description": location_description,
            "short_description": location_description[:200] + "..." if len(location_description) > 200 else location_description,
            "is_discovered": True,
            "is_accessible": True,
            "parent_location_id": main_town["id"],
            "climate": main_town.get("climate", "Temperate"),
            "terrain": main_town.get("terrain", "Plains"), 
            "population": "Small"
        }
        
        location_id = db_service.create_campaign_location(campaign["Id"], location_name, location_type, **location_data)
        if location_id:
            location_data["id"] = location_id["Id"]
            location_data["name"] = location_name
            return location_data
        else:
            raise Exception(f"Failed to create location {location_name}")
    
    async def _generate_npcs_parallel(self, 
                                    campaign: Dict[str, Any], 
                                    locations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Génère tous les NPCs en parallèle par location"""
        from app import generate_location_npcs
        
        tasks = []
        for location in locations:
            # 2 NPCs pour la ville principale, 1-2 pour les autres
            npc_count = 2 if location.get("type") == "Town" else 1
            task = asyncio.create_task(generate_location_npcs(campaign, location, npc_count))
            tasks.append(task)
        
        all_npcs = []
        for batch in self._batch_tasks(tasks, self.batch_size):
            batch_results = await asyncio.gather(*batch, return_exceptions=True)
            for result in batch_results:
                if isinstance(result, Exception):
                    logger.error(f"NPC generation failed: {result}")
                else:
                    all_npcs.extend(result)
        
        return all_npcs
    
    async def _generate_quests_parallel(self, 
                                      campaign: Dict[str, Any], 
                                      locations: List[Dict[str, Any]], 
                                      npcs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Génère les quêtes en parallèle"""
        from app import generate_single_quest
        import random
        
        if not npcs:
            return []
        
        # Sélectionner les NPCs pour les quêtes
        main_town = next((loc for loc in locations if loc.get("type") == "Town"), None)
        if not main_town:
            return []
        
        # NPCs hors de la ville principale pour la quête principale
        sub_location_npcs = [npc for npc in npcs if npc.get("current_location") != main_town["name"]]
        
        tasks = []
        
        # 1 Quête principale
        if sub_location_npcs:
            main_quest_npc = random.choice(sub_location_npcs)
            main_quest_location = next(loc for loc in locations if loc["name"] == main_quest_npc["current_location"])
            
            task = asyncio.create_task(
                generate_single_quest(campaign, main_quest_location, main_quest_npc, "Main")
            )
            tasks.append(task)
        
        # 2 Quêtes secondaires
        remaining_npcs = [npc for npc in npcs if npc.get("current_location") != main_town["name"]]
        if len(remaining_npcs) >= 2:
            side_quest_npcs = random.sample(remaining_npcs, min(2, len(remaining_npcs)))
            
            for npc in side_quest_npcs:
                quest_location = next(loc for loc in locations if loc["name"] == npc["current_location"])
                task = asyncio.create_task(
                    generate_single_quest(campaign, quest_location, npc, "Side")
                )
                tasks.append(task)
        
        # Exécuter toutes les quêtes en parallèle
        quests = []
        quest_results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in quest_results:
            if isinstance(result, Exception):
                logger.error(f"Quest generation failed: {result}")
            else:
                quests.append(result)
        
        return quests
    
    async def _generate_images_background(self, 
                                        campaign_id: int, 
                                        content_results: Dict[str, Any]) -> None:
        """Génère les images en arrière-plan de manière non-bloquante"""
        from app import db_service, element_manager
        
        try:
            logger.info(f"🎨 Starting background image generation for campaign {campaign_id}")
            
            # Mettre à jour le statut
            db_service.update_campaign_content_status(campaign_id, "ImagesInProgress")
            
            # Créer les tâches d'images en parallèle
            image_tasks = []
            
            # Images des NPCs
            for npc in content_results.get("npcs", []):
                if not npc.get('portrait_url'):
                    task = asyncio.create_task(self._generate_npc_image(npc))
                    image_tasks.append(task)
            
            # Images des locations
            for location in content_results.get("locations", []):
                if not location.get('image_url'):
                    task = asyncio.create_task(self._generate_location_image(location))
                    image_tasks.append(task)
            
            # Exécuter par batches pour ne pas surcharger l'API
            for batch in self._batch_tasks(image_tasks, 2):  # Batches plus petits pour les images
                await asyncio.gather(*batch, return_exceptions=True)
                await asyncio.sleep(1)  # Pause entre les batches pour respecter les rate limits
            
            # Mettre à jour le statut final
            db_service.update_campaign_content_status(campaign_id, "ImagesCompleted")
            logger.info(f"✅ Background image generation completed for campaign {campaign_id}")
            
        except Exception as e:
            logger.error(f"❌ Error in background image generation: {str(e)}")
            db_service.update_campaign_content_status(campaign_id, "Failed", str(e))
    
    async def _generate_npc_image(self, npc: Dict[str, Any]) -> Optional[str]:
        """Génère une image pour un NPC"""
        try:
            from app import element_manager, db_service
            
            npc_data = {
                'name': npc['name'],
                'race': npc.get('race', 'Unknown'),
                'class': npc.get('class', 'Unknown'),
                'description': npc.get('description', ''),
                'type': npc.get('type', 'Humanoid')
            }
            
            portrait_url = element_manager._generate_npc_portrait(npc_data)
            if portrait_url:
                db_service.update_npc(npc['id'], portrait_url=portrait_url)
                logger.info(f"✅ Portrait generated for NPC {npc['name']}")
                return portrait_url
            else:
                logger.warning(f"⚠️ Failed to generate portrait for NPC {npc['name']}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error generating portrait for NPC {npc.get('name')}: {str(e)}")
            return None
    
    async def _generate_location_image(self, location: Dict[str, Any]) -> Optional[str]:
        """Génère une image pour une location"""
        try:
            from app import element_manager, db_service
            
            location_data = {
                'name': location['name'],
                'type': location.get('type', 'Location'),
                'description': location.get('description', '')
            }
            
            image_url = element_manager._generate_location_image(location_data)
            if image_url:
                db_service.update_location(location['id'], image_url=image_url)
                logger.info(f"✅ Image generated for location {location['name']}")
                return image_url
            else:
                logger.warning(f"⚠️ Failed to generate image for location {location['name']}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error generating image for location {location.get('name')}: {str(e)}")
            return None
    
    def _batch_tasks(self, tasks: List[asyncio.Task], batch_size: int) -> List[List[asyncio.Task]]:
        """Divise les tâches en batches"""
        batches = []
        for i in range(0, len(tasks), batch_size):
            batches.append(tasks[i:i + batch_size])
        return batches
    
    def _calculate_efficiency(self, results: Dict[str, Any]) -> float:
        """Calcule l'efficacité du parallélisme"""
        total_items = len(results.get("locations", [])) + len(results.get("npcs", [])) + len(results.get("quests", []))
        total_time = results["performance"]["total_time"]
        
        if total_items == 0 or total_time == 0:
            return 0.0
        
        # Estimation du temps séquentiel (basé sur des moyennes)
        estimated_sequential_time = (
            len(results.get("locations", [])) * 10 +  # 10s par location
            len(results.get("npcs", [])) * 8 +        # 8s par NPC  
            len(results.get("quests", [])) * 12       # 12s par quête
        )
        
        if estimated_sequential_time == 0:
            return 100.0
        
        efficiency = min(100.0, (estimated_sequential_time / total_time) * 100 / self.max_workers)
        return round(efficiency, 2)
    
    def cleanup(self):
        """Nettoie les ressources"""
        self.executor.shutdown(wait=True)

# Instance globale de l'optimiseur
content_optimizer = ContentGenerationOptimizer(max_workers=4, batch_size=3) 