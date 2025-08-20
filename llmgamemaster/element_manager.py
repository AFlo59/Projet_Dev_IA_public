import re
import logging
import threading
import time
import asyncio
from typing import Dict, List, Optional, Tuple
from db_service import DBService
from llm_service import LLMService

logger = logging.getLogger(__name__)

class ElementManager:
    """Manages the automatic creation and updating of campaign elements (NPCs, Locations, Quests)"""
    
    def __init__(self, db_service: DBService):
        self.db_service = db_service
        self.llm_service = LLMService()
        self._background_threads = []
        self._max_background_threads = 3  # Limiter le nombre de threads simultanés
    
    def _cleanup_background_threads(self):
        """Nettoyer les threads terminés"""
        self._background_threads = [t for t in self._background_threads if t.is_alive()]
    
    async def _generate_image_async(self, element_type: str, element_id: int, element_data: Dict, campaign_id: int):
        """Génère une image en arrière-plan pour un élément et la stocke localement"""
        try:
            # Ajouter l'ID à element_data pour le stockage
            element_data['id'] = element_id
            
            if element_type == 'npc':
                local_path = await self._generate_npc_portrait(element_data, campaign_id)
                if local_path:
                    self.db_service.update_npc(element_id, portrait_url=local_path)
                    logger.info(f"✅ Portrait généré et stocké pour NPC {element_data['name']}: {local_path}")
            elif element_type == 'location':
                local_path = await self._generate_location_image(element_data, campaign_id)
                if local_path:
                    self.db_service.update_location(element_id, image_url=local_path)
                    logger.info(f"✅ Image générée et stockée pour location {element_data['name']}: {local_path}")
        except Exception as e:
            logger.error(f"❌ Erreur lors de la génération d'image pour {element_type} {element_data.get('name', 'Unknown')}: {e}")
        finally:
            # Nettoyer les threads terminés
            self._cleanup_background_threads()
    
    def _start_background_image_generation(self, element_type: str, element_id: int, element_data: Dict, campaign_id: int):
        """Démarre la génération d'image en arrière-plan"""
        # Nettoyer les threads terminés
        self._cleanup_background_threads()
        
        # Limiter le nombre de threads simultanés
        if len(self._background_threads) >= self._max_background_threads:
            logger.info(f"⏳ Limite de threads atteinte, génération d'image pour {element_type} {element_data.get('name', 'Unknown')} mise en attente")
            return
        
        # Créer un nouveau thread pour la génération d'image
        thread = threading.Thread(
            target=self._generate_image_async,
            args=(element_type, element_id, element_data, campaign_id),
            daemon=True
        )
        thread.start()
        self._background_threads.append(thread)
        logger.info(f"🔄 Démarrage de la génération d'image en arrière-plan pour {element_type} {element_data.get('name', 'Unknown')}")
    
    async def process_narrative_response(self, campaign_id: int, narrative_response: str, language: str = "English", character_id: int = None) -> Dict[str, List[Dict]]:
        """
        Process a narrative response and automatically create/update elements
        Language-aware processing for different campaign languages
        Returns a summary of created/updated elements
        """
        created_elements = {
            'npcs': [],
            'locations': [],
            'quests': [],
            'character_movements': []
        }
        
        try:
            # First, check for explicit creation commands
            created_elements = self._process_explicit_creation_commands(campaign_id, narrative_response, language)
            
            # If no explicit commands found, try automatic extraction as fallback
            if not any(created_elements.values()):
                logger.info("No explicit creation commands found, trying automatic extraction")
                created_elements = await self._extract_elements_automatically_sync(campaign_id, narrative_response, language)
            
            # NOUVEAU: Détecter automatiquement les changements de location du character
            if character_id:
                location_movements = self._detect_character_location_changes(campaign_id, character_id, narrative_response, language)
                if location_movements:
                    created_elements['character_movements'] = location_movements
                    logger.info(f"🚶 Detected character location changes: {location_movements}")
            
        except Exception as e:
            logger.error(f"Error processing narrative response: {e}")
        
        return created_elements
    
    def _parse_optional_fields(self, optional_fields: str, element_name: str) -> Dict:
        """Parse optional fields from creation commands"""
        kwargs = {}
        if optional_fields:
            try:
                for field in optional_fields.split(', '):
                    if '=' in field:
                        key, value = field.split('=', 1)
                        key = key.strip()
                        value = value.strip()
                        # Convert numeric values
                        if value.isdigit():
                            kwargs[key] = int(value)
                        elif value.lower() in ['true', 'false']:
                            kwargs[key] = value.lower() == 'true'
                        else:
                            kwargs[key] = value
            except Exception as e:
                logger.warning(f"Error parsing optional fields for {element_name}: {e}")
        return kwargs
    
    def _process_explicit_creation_commands(self, campaign_id: int, text: str, language: str = "English") -> Dict[str, List[Dict]]:
        """Process explicit creation and update commands from the AI response"""
        created_elements = {
            'npcs': [],
            'locations': [],
            'quests': []
        }
        
        updated_elements = {
            'npcs': [],
            'locations': [],
            'quests': []
        }
        
        # Patterns for explicit creation commands
        npc_pattern = r'\[CREATE_NPC:name=([^,]+), race=([^,]+), class=([^,]+), description=([^\]]+?)(?:, ([^\]]+))?\]'
        location_pattern = r'\[CREATE_LOCATION:name=([^,]+), type=([^,]+), description=([^\]]+?)(?:, ([^\]]+))?\]'
        quest_pattern = r'\[CREATE_QUEST:title=([^,]+), type=([^,]+), description=([^\]]+?)(?:, ([^\]]+))?\]'
        
        # Patterns for update commands
        update_npc_pattern = r'\[UPDATE_NPC:name=([^,]+), ([^\]]+)\]'
        update_location_pattern = r'\[UPDATE_LOCATION:name=([^,]+), ([^\]]+)\]'
        update_quest_pattern = r'\[UPDATE_QUEST:title=([^,]+), ([^\]]+)\]'
        
        # Process creation commands
        created_elements = self._process_creation_commands(campaign_id, text, npc_pattern, location_pattern, quest_pattern)
        
        # Process update commands
        updated_elements = self._process_update_commands(campaign_id, text, update_npc_pattern, update_location_pattern, update_quest_pattern)
        
        # Combine results
        result = {
            'npcs': created_elements['npcs'] + updated_elements['npcs'],
            'locations': created_elements['locations'] + updated_elements['locations'],
            'quests': created_elements['quests'] + updated_elements['quests']
        }
        
        return result
    
    def _process_creation_commands(self, campaign_id: int, text: str, npc_pattern: str, location_pattern: str, quest_pattern: str) -> Dict[str, List[Dict]]:
        """Process creation commands"""
        created_elements = {
            'npcs': [],
            'locations': [],
            'quests': []
        }
        
        # Find NPC creation commands
        npc_matches = re.finditer(npc_pattern, text, re.IGNORECASE)
        for match in npc_matches:
            name = match.group(1).strip()
            race = match.group(2).strip()
            character_class = match.group(3).strip()
            description = match.group(4).strip()
            optional_fields = match.group(5) if match.group(5) else ""
            
            # Parse optional fields
            kwargs = self._parse_optional_fields(optional_fields, f"NPC {name}")
            
            # Use the simple explicit method
            result = self.create_npc_explicitly(campaign_id, name, race, character_class, description, **kwargs)
            if result:
                created_elements['npcs'].append(result)
                logger.info(f"Created NPC via explicit command: {name}")
        
        # Find location creation commands
        location_matches = re.finditer(location_pattern, text, re.IGNORECASE)
        for match in location_matches:
            name = match.group(1).strip()
            location_type = match.group(2).strip()
            description = match.group(3).strip()
            optional_fields = match.group(4) if match.group(4) else ""
            
            # Parse optional fields
            kwargs = self._parse_optional_fields(optional_fields, f"Location {name}")
            
            # Use the simple explicit method
            result = self.create_location_explicitly(campaign_id, name, location_type, description, **kwargs)
            if result:
                created_elements['locations'].append(result)
                logger.info(f"Created location via explicit command: {name}")
        
        # Find quest creation commands
        quest_matches = re.finditer(quest_pattern, text, re.IGNORECASE)
        for match in quest_matches:
            title = match.group(1).strip()
            quest_type = match.group(2).strip()
            description = match.group(3).strip()
            optional_fields = match.group(4) if match.group(4) else ""
            
            # Parse optional fields
            kwargs = self._parse_optional_fields(optional_fields, f"Quest {title}")
            
            # Use the simple explicit method
            result = self.create_quest_explicitly(campaign_id, title, quest_type, description, **kwargs)
            if result:
                created_elements['quests'].append(result)
                logger.info(f"Created quest via explicit command: {title}")
        
        return created_elements
    
    def _process_update_commands(self, campaign_id: int, text: str, update_npc_pattern: str, update_location_pattern: str, update_quest_pattern: str) -> Dict[str, List[Dict]]:
        """Process update commands"""
        updated_elements = {
            'npcs': [],
            'locations': [],
            'quests': []
        }
        
        # Find NPC update commands
        npc_matches = re.finditer(update_npc_pattern, text, re.IGNORECASE)
        for match in npc_matches:
            name = match.group(1).strip()
            update_fields = match.group(2).strip()
            
            # Parse update fields
            update_data = self._parse_update_fields(update_fields, f"NPC {name}")
            
            # Update NPC
            result = self.update_npc_explicitly(campaign_id, name, **update_data)
            if result:
                updated_elements['npcs'].append(result)
                logger.info(f"Updated NPC via explicit command: {name}")
        
        # Find location update commands
        location_matches = re.finditer(update_location_pattern, text, re.IGNORECASE)
        for match in location_matches:
            name = match.group(1).strip()
            update_fields = match.group(2).strip()
            
            # Parse update fields
            update_data = self._parse_update_fields(update_fields, f"Location {name}")
            
            # Update location
            result = self.update_location_explicitly(campaign_id, name, **update_data)
            if result:
                updated_elements['locations'].append(result)
                logger.info(f"Updated location via explicit command: {name}")
        
        # Find quest update commands
        quest_matches = re.finditer(update_quest_pattern, text, re.IGNORECASE)
        for match in quest_matches:
            title = match.group(1).strip()
            update_fields = match.group(2).strip()
            
            # Parse update fields
            update_data = self._parse_update_fields(update_fields, f"Quest {title}")
            
            # Update quest
            result = self.update_quest_explicitly(campaign_id, title, **update_data)
            if result:
                updated_elements['quests'].append(result)
                logger.info(f"Updated quest via explicit command: {title}")
        
        return updated_elements
    
    def _parse_update_fields(self, update_fields: str, element_name: str) -> Dict:
        """Parse update fields from update commands"""
        update_data = {}
        if update_fields:
            try:
                for field in update_fields.split(', '):
                    if '=' in field:
                        key, value = field.split('=', 1)
                        key = key.strip()
                        value = value.strip()
                        # Convert numeric values
                        if value.isdigit():
                            update_data[key] = int(value)
                        elif value.lower() in ['true', 'false']:
                            update_data[key] = value.lower() == 'true'
                        else:
                            update_data[key] = value
            except Exception as e:
                logger.warning(f"Error parsing update fields for {element_name}: {e}")
        return update_data
    

    def _create_or_update_npc(self, campaign_id: int, npc_data: Dict) -> Optional[Dict]:
        """Create a new NPC or update existing one"""
        try:
            # Check if NPC already exists
            existing_npc = self.db_service.get_npc_by_name(campaign_id, npc_data['name'])
            
            if existing_npc:
                # Update existing NPC
                logger.info(f"Updating existing NPC: {npc_data['name']}")
                result = self.db_service.update_npc(existing_npc['Id'], **npc_data)
                if result:
                    return {'action': 'updated', 'type': 'npc', 'name': npc_data['name'], 'id': existing_npc['Id']}
            else:
                # Create new NPC
                logger.info(f"Creating new NPC: {npc_data['name']}")
                result = self.db_service.create_campaign_npc(
                    campaign_id=campaign_id,
                    name=npc_data['name'],
                    npc_type=npc_data.get('type', 'Humanoid'),
                    race=npc_data['race'],
                    **{k: v for k, v in npc_data.items() if k not in ['name', 'type', 'race']}
                )
                if result:
                    # Start background image generation for new NPC
                    self._start_background_image_generation('npc', result['Id'], npc_data, campaign_id)
                    
                    return {'action': 'created', 'type': 'npc', 'name': npc_data['name'], 'id': result['Id']}
        
        except Exception as e:
            logger.error(f"Error creating/updating NPC {npc_data.get('name', 'Unknown')}: {e}")
        
        return None
    
    def _create_or_update_location(self, campaign_id: int, location_data: Dict) -> Optional[Dict]:
        """Create a new location or update existing one"""
        try:
            # Check if location already exists
            existing_location = self.db_service.get_location_by_name(campaign_id, location_data['name'])
            
            if existing_location:
                # Update existing location (mark as discovered if not already)
                logger.info(f"Updating existing location: {location_data['name']}")
                update_data = {k: v for k, v in location_data.items() if k != 'name'}
                if not existing_location.get('IsDiscovered', False):
                    update_data['is_discovered'] = True
                
                result = self.db_service.update_location(existing_location['Id'], **update_data)
                if result:
                    return {'action': 'updated', 'type': 'location', 'name': location_data['name'], 'id': existing_location['Id']}
            else:
                # Create new location
                logger.info(f"Creating new location: {location_data['name']}")
                result = self.db_service.create_campaign_location(
                    campaign_id=campaign_id,
                    name=location_data['name'],
                    location_type=location_data.get('type', 'Location'),
                    **{k: v for k, v in location_data.items() if k not in ['name', 'type']}
                )
                if result:
                    # Start background image generation for new location
                    self._start_background_image_generation('location', result['Id'], location_data, campaign_id)
                    
                    return {'action': 'created', 'type': 'location', 'name': location_data['name'], 'id': result['Id']}
        
        except Exception as e:
            logger.error(f"Error creating/updating location {location_data.get('name', 'Unknown')}: {e}")
        
        return None
    
    def _create_or_update_quest(self, campaign_id: int, quest_data: Dict) -> Optional[Dict]:
        """Create a new quest or update existing one"""
        try:
            # Check if quest already exists
            existing_quest = self.db_service.get_quest_by_title(campaign_id, quest_data['title'])
            
            if existing_quest:
                # Update existing quest
                logger.info(f"Updating existing quest: {quest_data['title']}")
                result = self.db_service.update_quest(existing_quest['Id'], **quest_data)
                if result:
                    return {'action': 'updated', 'type': 'quest', 'title': quest_data['title'], 'id': existing_quest['Id']}
            else:
                # Create new quest
                logger.info(f"Creating new quest: {quest_data['title']}")
                result = self.db_service.create_campaign_quest(
                    campaign_id=campaign_id,
                    title=quest_data['title'],
                    **{k: v for k, v in quest_data.items() if k != 'title'}
                )
                if result:
                    return {'action': 'created', 'type': 'quest', 'title': quest_data['title'], 'id': result['Id']}
        
        except Exception as e:
            logger.error(f"Error creating/updating quest {quest_data.get('title', 'Unknown')}: {e}")
        
        return None
    
    def create_npc_explicitly(self, campaign_id: int, name: str, race: str, character_class: str, description: str, **kwargs) -> Optional[Dict]:
        """Create an NPC explicitly with provided data"""
        try:
            npc_data = {
                'name': name,
                'race': race,
                'type': kwargs.get('type', 'Humanoid'),
                'class': character_class,
                'description': description,
                'level': kwargs.get('level', 1),
                'max_hit_points': kwargs.get('max_hit_points', 10),
                'current_hit_points': kwargs.get('current_hit_points', 10),
                'armor_class': kwargs.get('armor_class', 10),
                'strength': kwargs.get('strength', 10),
                'dexterity': kwargs.get('dexterity', 10),
                'constitution': kwargs.get('constitution', 10),
                'intelligence': kwargs.get('intelligence', 10),
                'wisdom': kwargs.get('wisdom', 10),
                'charisma': kwargs.get('charisma', 10),
                'alignment': kwargs.get('alignment'),
                'current_location': kwargs.get('current_location'),
                'status': kwargs.get('status', 'Active'),
                'notes': kwargs.get('notes'),
                **kwargs
            }
            
            result = self._create_or_update_npc(campaign_id, npc_data)
            if result:
                logger.info(f"Explicitly created NPC: {name}")
            return result
        except Exception as e:
            logger.error(f"Error creating NPC {name}: {e}")
            return None
    
    def create_location_explicitly(self, campaign_id: int, name: str, location_type: str, description: str, **kwargs) -> Optional[Dict]:
        """Create a location explicitly with provided data"""
        try:
            location_data = {
                'name': name,
                'type': location_type,
                'description': description,
                'short_description': kwargs.get('short_description'),
                'parent_location_id': kwargs.get('parent_location_id'),
                'is_discovered': kwargs.get('is_discovered', True),
                'is_accessible': kwargs.get('is_accessible', True),
                'climate': kwargs.get('climate'),
                'terrain': kwargs.get('terrain'),
                'population': kwargs.get('population'),
                'notes': kwargs.get('notes'),
                **kwargs
            }
            
            result = self._create_or_update_location(campaign_id, location_data)
            if result:
                logger.info(f"Explicitly created location: {name}")
            return result
        except Exception as e:
            logger.error(f"Error creating location {name}: {e}")
            return None
    
    def create_quest_explicitly(self, campaign_id: int, title: str, quest_type: str, description: str, **kwargs) -> Optional[Dict]:
        """Create a quest explicitly with provided data"""
        try:
            quest_data = {
                'title': title,
                'type': quest_type,
                'difficulty': kwargs.get('difficulty', 'Medium'),
                'status': kwargs.get('status', 'Available'),
                'description': description,
                'short_description': kwargs.get('short_description'),
                'reward': kwargs.get('reward'),
                'requirements': kwargs.get('requirements'),
                'required_level': kwargs.get('required_level'),
                'location_id': kwargs.get('location_id'),
                'quest_giver': kwargs.get('quest_giver'),
                'notes': kwargs.get('notes'),
                'progress': kwargs.get('progress'),
                **kwargs
            }
            
            result = self._create_or_update_quest(campaign_id, quest_data)
            if result:
                logger.info(f"Explicitly created quest: {title}")
            return result
        except Exception as e:
            logger.error(f"Error creating quest {title}: {e}")
            return None
    
    def update_npc_explicitly(self, campaign_id: int, name: str, **kwargs) -> Optional[Dict]:
        """Update an NPC explicitly with provided data"""
        try:
            # Find existing NPC by name
            existing_npc = self.db_service.get_npc_by_name(campaign_id, name)
            if not existing_npc:
                logger.warning(f"NPC {name} not found for update")
                return None
            
            # Update NPC with provided data
            result = self.db_service.update_npc(existing_npc['Id'], **kwargs)
            if result:
                logger.info(f"Explicitly updated NPC: {name}")
                return {'action': 'updated', 'type': 'npc', 'name': name, 'id': existing_npc['Id']}
            return None
        except Exception as e:
            logger.error(f"Error updating NPC {name}: {e}")
            return None
    
    def update_location_explicitly(self, campaign_id: int, name: str, **kwargs) -> Optional[Dict]:
        """Update a location explicitly with provided data"""
        try:
            # Find existing location by name
            existing_location = self.db_service.get_location_by_name(campaign_id, name)
            if not existing_location:
                logger.warning(f"Location {name} not found for update")
                return None
            
            # Update location with provided data
            result = self.db_service.update_location(existing_location['Id'], **kwargs)
            if result:
                logger.info(f"Explicitly updated location: {name}")
                return {'action': 'updated', 'type': 'location', 'name': name, 'id': existing_location['Id']}
            return None
        except Exception as e:
            logger.error(f"Error updating location {name}: {e}")
            return None
    
    def update_quest_explicitly(self, campaign_id: int, title: str, **kwargs) -> Optional[Dict]:
        """Update a quest explicitly with provided data"""
        try:
            # Find existing quest by title
            existing_quest = self.db_service.get_quest_by_title(campaign_id, title)
            if not existing_quest:
                logger.warning(f"Quest {title} not found for update")
                return None
            
            # Update quest with provided data
            result = self.db_service.update_quest(existing_quest['Id'], **kwargs)
            if result:
                logger.info(f"Explicitly updated quest: {title}")
                return {'action': 'updated', 'type': 'quest', 'title': title, 'id': existing_quest['Id']}
            return None
        except Exception as e:
            logger.error(f"Error updating quest {title}: {e}")
            return None
    
    async def _generate_npc_portrait(self, npc_data: Dict, campaign_id: int = None) -> Optional[str]:
        """Generate a portrait for an NPC and store it permanently"""
        try:
            name = npc_data['name']
            race = npc_data.get('race', 'Unknown')
            character_class = npc_data.get('class', 'Unknown')
            description = npc_data.get('description', '')
            npc_id = npc_data.get('id', 0)
            traits = ", ".join(description.split(".")[0].split()[:10])
            prompt = f"Portrait de {name}, {race} {character_class}, {traits}. Style fantasy, lumière dramatique."
            prompt = prompt[:750]
            
            # Générer et stocker l'image localement
            local_path = await self.llm_service.generate_and_store_image(
                prompt, 'npc', name, npc_id, campaign_id
            )
            
            if local_path:
                logger.info(f"Generated and stored portrait for NPC {name}: {local_path}")
                return local_path
            else:
                logger.error(f"Failed to generate portrait for NPC {name}")
                return None
                
        except Exception as e:
            logger.error(f"Error generating NPC portrait: {e}")
            return None

    async def _generate_location_image(self, location_data: Dict, campaign_id: int = None) -> Optional[str]:
        """Generate an image for a location and store it permanently"""
        try:
            name = location_data['name']
            location_type = location_data.get('type', 'Location')
            description = location_data.get('description', '')
            location_id = location_data.get('id', 0)
            climate = location_data.get('climate', 'mystérieuse')
            terrain = location_data.get('terrain', 'inconnu')
            traits = ", ".join(description.split(".")[0].split()[:10])
            prompt = f"Illustration de {name}, {location_type}, {traits}. Ambiance {climate}, terrain {terrain}, style fantasy."
            prompt = prompt[:750]
            
            # Générer et stocker l'image localement
            local_path = await self.llm_service.generate_and_store_image(
                prompt, 'location', name, location_id, campaign_id
            )
            
            if local_path:
                logger.info(f"Generated and stored image for location {name}: {local_path}")
                return local_path
            else:
                logger.error(f"Failed to generate image for location {name}")
                return None
                
        except Exception as e:
            logger.error(f"Error generating location image: {e}")
            return None 
    
    async def generate_missing_images_for_campaign(self, campaign_id: int) -> Dict[str, int]:
        """Génère les images manquantes pour tous les éléments d'une campagne"""
        results = {
            'npcs_generated': 0,
            'locations_generated': 0,
            'errors': 0
        }
        
        try:
            # Générer les portraits manquants pour les NPCs
            npcs = self.db_service.get_campaign_npcs(campaign_id)
            for npc in npcs:
                # Ne générer que si l'image est vraiment manquante (None, vide, ou chaîne vide)
                portrait_url = npc.get('PortraitUrl')
                if not portrait_url or portrait_url.strip() == '':
                    try:
                        npc_data = {
                            'name': npc['Name'],
                            'race': npc.get('Race', 'Unknown'),
                            'class': npc.get('Class', 'Unknown'),
                            'description': npc.get('Description', ''),
                            'type': npc.get('Type', 'Humanoid')
                        }
                        
                        new_portrait_url = await self._generate_npc_portrait(npc_data, campaign_id)
                        if new_portrait_url:
                            # Use asyncio.to_thread for sync DB call in async context
                            import asyncio
                            await asyncio.to_thread(self.db_service.update_npc, npc['Id'], portrait_url=new_portrait_url)
                            results['npcs_generated'] += 1
                            logger.info(f"✅ Portrait généré pour NPC existant: {npc['Name']}")
                        else:
                            logger.warning(f"⚠️ Échec de génération du portrait pour NPC {npc['Name']}")
                    except Exception as e:
                        logger.error(f"❌ Erreur lors de la génération du portrait pour NPC {npc['Name']}: {e}")
                        results['errors'] += 1
                else:
                    logger.info(f"ℹ️ NPC {npc['Name']} a déjà un portrait: {portrait_url[:50]}...")
            
            # Générer les images manquantes pour les locations
            locations = self.db_service.get_campaign_locations(campaign_id)
            for location in locations:
                # Ne générer que si l'image est vraiment manquante (None, vide, ou chaîne vide)
                image_url = location.get('ImageUrl')
                if not image_url or image_url.strip() == '':
                    try:
                        location_data = {
                            'name': location['Name'],
                            'type': location.get('Type', 'Location'),
                            'description': location.get('Description', '')
                        }
                        
                        new_image_url = await self._generate_location_image(location_data, campaign_id)
                        if new_image_url:
                            # Use asyncio.to_thread for sync DB call in async context
                            import asyncio
                            await asyncio.to_thread(self.db_service.update_location, location['Id'], image_url=new_image_url)
                            results['locations_generated'] += 1
                            logger.info(f"✅ Image générée pour location existante: {location['Name']}")
                        else:
                            logger.warning(f"⚠️ Échec de génération de l'image pour location {location['Name']}")
                    except Exception as e:
                        logger.error(f"❌ Erreur lors de la génération de l'image pour location {location['Name']}: {e}")
                        results['errors'] += 1
                else:
                    logger.info(f"ℹ️ Location {location['Name']} a déjà une image: {image_url[:50]}...")
            
            logger.info(f"🎨 Génération d'images terminée: {results['npcs_generated']} portraits NPC, {results['locations_generated']} images location, {results['errors']} erreurs")
            
        except Exception as e:
            logger.error(f"❌ Erreur lors de la génération d'images pour la campagne {campaign_id}: {e}")
            results['errors'] += 1
        
        return results
    
    def get_image_generation_status(self, campaign_id: int) -> Dict[str, any]:
        """Retourne le statut de génération d'images pour une campagne"""
        try:
            npcs = self.db_service.get_campaign_npcs(campaign_id)
            locations = self.db_service.get_campaign_locations(campaign_id)
            
            npcs_with_images = sum(1 for npc in npcs if npc.get('PortraitUrl'))
            locations_with_images = sum(1 for location in locations if location.get('ImageUrl'))
            
            total_npcs = len(npcs)
            total_locations = len(locations)
            
            return {
                'npcs': {
                    'total': total_npcs,
                    'with_images': npcs_with_images,
                    'missing_images': total_npcs - npcs_with_images
                },
                'locations': {
                    'total': total_locations,
                    'with_images': locations_with_images,
                    'missing_images': total_locations - locations_with_images
                },
                'background_threads': len(self._background_threads)
            }
        except Exception as e:
            logger.error(f"❌ Erreur lors de la récupération du statut d'images pour la campagne {campaign_id}: {e}")
            return {
                'npcs': {'total': 0, 'with_images': 0, 'missing_images': 0},
                'locations': {'total': 0, 'with_images': 0, 'missing_images': 0},
                'background_threads': 0,
                'error': str(e)
            }
    
    def _detect_character_location_changes(self, campaign_id: int, character_id: int, narrative_response: str, language: str = "English") -> List[Dict]:
        """
        Detect when the Game Master mentions that a character moves to a new location
        and automatically update the character's CurrentLocation
        """
        location_movements = []
        
        try:
            # Get existing locations for the campaign
            locations = self.db_service.get_campaign_locations(campaign_id)
            location_names = [loc.get('Name', '') for loc in locations if loc.get('Name')]
            
            if not location_names:
                return location_movements
            
            # Multi-language location movement patterns
            if language.lower() in ['french', 'français']:
                movement_patterns = [
                    r"tu te trouves (?:maintenant |désormais )?(?:dans|à|en|au|aux) (.+?)(?:\.|,|$)",
                    r"vous vous trouvez (?:maintenant |désormais )?(?:dans|à|en|au|aux) (.+?)(?:\.|,|$)",
                    r"tu te déplaces? vers (.+?)(?:\.|,|$)",
                    r"vous vous déplacez vers (.+?)(?:\.|,|$)",
                    r"tu (?:arrives?|entre.?|va.?) (?:dans|à|en|au|aux) (.+?)(?:\.|,|$)",
                    r"vous (?:arrivez|entrez|allez) (?:dans|à|en|au|aux) (.+?)(?:\.|,|$)",
                    r"direction (?:de |du |de la |des )?(.+?)(?:\.|,|$)",
                    r"(?:bienvenue|retour) (?:dans|à|en|au|aux) (.+?)(?:\.|,|$)"
                ]
            else:  # English
                movement_patterns = [
                    r"you (?:are )?(?:now |currently )?(?:in|at|inside) (.+?)(?:\.|,|$)",
                    r"you move (?:to|towards|into) (.+?)(?:\.|,|$)",
                    r"you (?:arrive|enter|go) (?:at|in|to) (.+?)(?:\.|,|$)",
                    r"you (?:travel|head|walk) (?:to|towards) (.+?)(?:\.|,|$)",
                    r"welcome to (.+?)(?:\.|,|$)",
                    r"(?:arriving|entering) (.+?)(?:\.|,|$)"
                ]
            
            # Search for movement patterns in the narrative
            for pattern in movement_patterns:
                matches = re.finditer(pattern, narrative_response, re.IGNORECASE | re.MULTILINE)
                for match in matches:
                    mentioned_location = match.group(1).strip()
                    
                    # Clean up the location name (remove articles, punctuation)
                    cleaned_location = self._clean_location_name(mentioned_location)
                    
                    # Find the best matching location from existing locations
                    best_match = self._find_best_location_match(cleaned_location, location_names)
                    
                    if best_match:
                        # Update character location in database
                        success = self.db_service.update_character_location(campaign_id, character_id, best_match)
                        
                        if success:
                            movement_info = {
                                'character_id': character_id,
                                'previous_location': self.db_service.get_character_location(campaign_id, character_id),
                                'new_location': best_match,
                                'mentioned_as': mentioned_location,
                                'pattern_matched': pattern,
                                'action': 'moved'
                            }
                            location_movements.append(movement_info)
                            logger.info(f"🚶 Auto-updated character {character_id} location to '{best_match}' (mentioned as '{mentioned_location}')")
                            break  # Only process the first movement per response
                    
        except Exception as e:
            logger.error(f"Error detecting character location changes: {e}")
        
        return location_movements
    
    def _clean_location_name(self, location_name: str) -> str:
        """Clean location name by removing articles and extra words"""
        # Remove common articles and prepositions (multi-language)
        articles = ['le', 'la', 'les', 'un', 'une', 'des', 'du', 'de', 'the', 'a', 'an']
        words = location_name.split()
        cleaned_words = []
        
        for word in words:
            word_clean = word.lower().strip('.,!?;:"()[]{}')
            if word_clean not in articles:
                cleaned_words.append(word.strip('.,!?;:"()[]{}'))
        
        return ' '.join(cleaned_words).title()
    
    def _find_best_location_match(self, mentioned_location: str, existing_locations: List[str]) -> str:
        """Find the best matching existing location for a mentioned location"""
        mentioned_lower = mentioned_location.lower()
        
        # Exact match first
        for location in existing_locations:
            if location.lower() == mentioned_lower:
                return location
        
        # Partial match (location name contains mentioned location or vice versa)
        for location in existing_locations:
            location_lower = location.lower()
            if (mentioned_lower in location_lower or 
                location_lower in mentioned_lower or
                self._calculate_similarity(mentioned_lower, location_lower) > 0.7):
                return location
        
        return None
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity ratio between two texts"""
        # Simple similarity based on common words
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union) if union else 0.0 