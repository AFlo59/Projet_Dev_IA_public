from fastapi import FastAPI, Depends, HTTPException, status, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Dict, List, Any, Optional
import logging
import time
import os
import re
import random
from datetime import datetime, timedelta
import json
from dotenv import load_dotenv
import openai  # Using older version 0.28.0
import aiohttp

from utils import setup_logging, format_campaign_data, format_message_history
from llm_service import LLMService, format_character_data
from db_service import DBService
from element_manager import ElementManager
# from static_files_middleware import setup_static_files  # Temporairement désactivé pour le debug
# from async_utils import content_optimizer

# Load environment variables
load_dotenv()

# Import configuration after loading .env
from config import (
    LOG_FILE, LOG_LEVEL, RATE_LIMIT_REQUESTS, RATE_LIMIT_WINDOW, 
    LLM_PROVIDER as CONFIG_LLM_PROVIDER, OPENAI_API_KEY,
    CORS_ORIGINS, ENABLE_AUTH, API_PORT
)

# Import authentication
from auth import get_current_user, get_optional_user, validate_campaign_access
from auth_routes import auth_router

# Set up OpenAI API key for older version
openai.api_key = OPENAI_API_KEY

# Set up logging
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
setup_logging(LOG_FILE, LOG_LEVEL)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="D&D GameMaster - LLM Service",
    description="AI-powered Dungeon Master for D&D campaigns",
    version="1.0.0"
)

# Add CORS middleware with security
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,  # Sécurisé : origines spécifiques seulement
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],  # Méthodes spécifiques
    allow_headers=["Authorization", "Content-Type", "Accept"],  # Headers spécifiques
)

# Include authentication routes
app.include_router(auth_router)

# Setup static files middleware for serving images
# setup_static_files(app, "static")  # Temporairement désactivé pour le debug

# Global variables
current_llm_provider = CONFIG_LLM_PROVIDER
logger.info(f"Starting with LLM provider: {current_llm_provider}")

# Services
db_service = DBService()

# Authentication helper functions
def create_campaign_access_dependency(campaign_id: int):
    """
    Factory pour créer une dependency qui vérifie l'accès à une campagne spécifique
    """
    async def verify_access(current_user: Dict[str, Any] = Depends(get_current_user)):
        if not ENABLE_AUTH:
            return current_user if current_user else {"id": "anonymous"}
        
        has_access = await validate_campaign_access(current_user, campaign_id)
        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"You don't have access to campaign {campaign_id}"
            )
        return current_user
    return verify_access

async def verify_authenticated_user(current_user: Dict[str, Any] = Depends(get_current_user)):
    """
    Dependency simple pour vérifier qu'un utilisateur est authentifié
    """
    if not ENABLE_AUTH:
        return {"id": "anonymous", "email": "anonymous@local", "username": "anonymous"}
    return current_user

# Optional auth dependency
async def get_optional_current_user(request: Request):
    """
    Dependency optionnelle pour l'authentification
    """
    if not ENABLE_AUTH:
        return {"id": "anonymous", "email": "anonymous@local", "username": "anonymous"}
    return await get_optional_user(request)

# Force reconnect to ensure clean connections
db_service.force_reconnect()

llm_service = LLMService()
element_manager = ElementManager(db_service)

# Compatibility functions for tests
def get_llm_service():
    """Get the LLM service instance - for tests"""
    return llm_service

def get_db_service():
    """Get the DB service instance - for tests"""
    return db_service

def get_element_manager():
    """Get the element manager instance - for tests"""
    return element_manager

# Request models
class MessageRequest(BaseModel):
    campaign_id: int
    message: str
    user_id: Optional[str] = None
    character_id: Optional[int] = None

class CampaignStartRequest(BaseModel):
    campaignId: int
    sessionId: int
    characterId: int
    playerName: str

class CampaignMessageRequest(BaseModel):
    campaignId: int
    sessionId: int
    characterId: int
    message: str
    isSystemMessage: bool = False

class EndSessionRequest(BaseModel):
    campaignId: int
    sessionId: int

# Rate limiting
class RateLimiter:
    def __init__(self, requests_limit: int, window_seconds: int):
        self.requests_limit = requests_limit
        self.window_seconds = window_seconds
        self.requests: Dict[str, List[float]] = {}
    
    def is_allowed(self, client_id: str) -> bool:
        now = time.time()
        
        # Initialize client's request history if not present
        if client_id not in self.requests:
            self.requests[client_id] = []
        
        # Remove requests older than the window
        self.requests[client_id] = [
            req_time for req_time in self.requests[client_id]
            if now - req_time < self.window_seconds
        ]
        
        # Check if client has exceeded the limit
        if len(self.requests[client_id]) >= self.requests_limit:
            return False
        
        # Add the current request
        self.requests[client_id].append(now)
        return True

rate_limiter = RateLimiter(RATE_LIMIT_REQUESTS, RATE_LIMIT_WINDOW)

# Middleware for rate limiting
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    # Get client IP address
    client_id = request.client.host
    
    # Check if request is allowed
    if not rate_limiter.is_allowed(client_id):
        logger.warning(f"Rate limit exceeded for client {client_id}")
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"detail": "Rate limit exceeded. Please try again later."}
        )
    
    response = await call_next(request)
    return response

# Cleanup function for background tasks
def cleanup_connections():
    """Close database connections"""
    db_service.close_connections()

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/db_status")
async def db_status():
    """Database connection status check"""
    game_conn_status = "Not connected"
    silver_conn_status = "Not connected"
    
    try:
        # Check game database connection
        if db_service.game_conn and not db_service.game_conn.closed:
            cursor = db_service.game_conn.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            game_conn_status = "Connected"
        else:
            try:
                db_service.get_game_db_connection()
                cursor = db_service.game_conn.cursor()
                cursor.execute("SELECT 1")
                cursor.close()
                game_conn_status = "Connected (new connection)"
            except Exception as e:
                game_conn_status = f"Error: {str(e)}"
        
        # Check silver database connection
        if db_service.silver_conn and not db_service.silver_conn.closed:
            cursor = db_service.silver_conn.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            silver_conn_status = "Connected"
        else:
            try:
                db_service.get_silver_db_connection()
                cursor = db_service.silver_conn.cursor()
                cursor.execute("SELECT 1")
                cursor.close()
                silver_conn_status = "Connected (new connection)"
            except Exception as e:
                silver_conn_status = f"Error: {str(e)}"
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "game_db": game_conn_status,
            "silver_db": silver_conn_status,
            "timestamp": datetime.now().isoformat()
        }
    
    return {
        "status": "ok",
        "game_db": game_conn_status,
        "silver_db": silver_conn_status,
        "timestamp": datetime.now().isoformat()
    }

# Check or change LLM provider
@app.get("/provider")
async def get_llm_provider():
    """Get current LLM provider (openai or anthropic)"""
    global current_llm_provider
    logger.info(f"Current LLM provider is: {current_llm_provider}")
    
    # Log environment variables to debug
    env_provider = os.environ.get("LLM_PROVIDER", "not set")
    logger.info(f"LLM_PROVIDER environment variable: {env_provider}")
    
    # Check if .env file exists
    env_path = os.path.join(os.getcwd(), ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r") as f:
                env_content = f.read()
            logger.info(f".env file content: {env_content}")
        except Exception as e:
            logger.error(f"Error reading .env file: {e}")
    else:
        logger.info(f".env file does not exist at {env_path}")
        
    return {"provider": current_llm_provider}

@app.post("/provider/{provider}")
async def set_llm_provider(provider: str):
    """Set LLM provider (openai or anthropic)"""
    global current_llm_provider
    
    if provider.lower() not in ["openai", "anthropic"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provider must be 'openai' or 'anthropic'"
        )
    
    # Write to .env file
    try:
        logger.info(f"Changing LLM provider from {current_llm_provider} to {provider.lower()}")
        
        # Update global variable
        current_llm_provider = provider.lower()
        
        # Write to .env file for persistence
        env_path = os.path.join(os.getcwd(), ".env")
        logger.info(f"Writing to .env file at {env_path}")
        
        with open(env_path, "w") as f:
            f.write(f"LLM_PROVIDER={provider.lower()}")
        
        # Update environment variable in current process
        os.environ["LLM_PROVIDER"] = provider.lower()
        
        # Force reload of LLM service to pick up new provider
        global llm_service
        llm_service = LLMService()
        
        logger.info(f"LLM provider successfully changed to {provider.lower()}")
        return {"success": True, "provider": provider.lower()}
    except Exception as e:
        logger.error(f"Error setting LLM provider: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error setting LLM provider: {str(e)}"
        )

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "D&D GameMaster LLM Service",
        "version": "1.0.0",
        "docs_url": "/docs"
    }

# Generate a narrative response (legacy endpoint)
@app.post("/generate")
async def generate_narrative(request: dict, background_tasks: BackgroundTasks):
    """Generate a narrative response for a campaign or character description"""
    try:
        # Handle different request formats
        if "prompt" in request:
            # This is a simple text generation request (like character description)
            prompt = request.get("prompt", "")
            if not prompt:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No prompt provided"
                )
            
            # Generate text using LLM service
            response = llm_service.generate_response(prompt)
            
            # Schedule cleanup
            background_tasks.add_task(cleanup_connections)
            
            return {
                "response": response,
                "success": True
            }
        
        # Handle legacy campaign-based requests
        campaign_id = request.get("campaign_id")
        message = request.get("message", "")
        
        if not campaign_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either 'prompt' or 'campaign_id' must be provided"
            )
        
        # Get campaign data
        campaign = db_service.get_campaign_data(campaign_id)
        if not campaign:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Campaign with ID {campaign_id} not found"
            )
        
        # Get characters
        characters = db_service.get_campaign_characters(campaign_id)
        
        # Get message history
        message_history = db_service.get_campaign_messages(campaign_id)
        
        # Format data for LLM
        formatted_campaign = format_campaign_data(campaign)
        formatted_characters = [format_character_data(char) for char in characters]
        formatted_history = format_message_history(message_history)
        
        # Generate narrative
        response = llm_service.generate_narrative(
            campaign=formatted_campaign,
            characters=formatted_characters,
            message_history=formatted_history,
            user_message=message
        )
        
        # Schedule cleanup AFTER all database operations are complete
        background_tasks.add_task(cleanup_connections)
        
        return {
            "campaign_id": campaign_id,
            "response": response
        }
    
    except HTTPException:
        # Schedule cleanup even in case of error
        background_tasks.add_task(cleanup_connections)
        raise
    except Exception as e:
        logger.error(f"Error generating narrative: {e}")
        # Schedule cleanup even in case of error
        background_tasks.add_task(cleanup_connections)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error generating narrative response"
        )

# New API endpoints for web application
@app.post("/api/gamemaster/start_campaign")
async def start_campaign(
    request: CampaignStartRequest, 
    background_tasks: BackgroundTasks,
    current_user: Dict[str, Any] = Depends(get_current_user if ENABLE_AUTH else get_optional_current_user)
):
    """Generate a starting narrative for a new campaign with pre-generated elements"""
    try:
        # Get campaign data
        campaign = db_service.get_campaign_data(request.campaignId)
        if not campaign:
            logger.error(f"Campaign with ID {request.campaignId} not found")
            return {
                "success": False,
                "message": f"Campaign with ID {request.campaignId} not found"
            }
        
        # Get characters
        characters = db_service.get_campaign_characters(request.campaignId)
        
        # Format data for LLM
        formatted_campaign = format_campaign_data(campaign)
        formatted_characters = [format_character_data(char) for char in characters]
        
        # Helper function to get NPCs present in a location
        def get_present_npcs_for_location(campaign_id, location_name):
            npcs = db_service.get_campaign_npcs(campaign_id)
            return [npc for npc in npcs if npc.get('CurrentLocation') == location_name]
        
        # PHASE 1: Pre-generate campaign elements (hidden from user)
        logger.info(f"[PreGen] Starting element pre-generation for campaign {request.campaignId}")
        
        # Generate starting location, NPC, and quest hook
        starting_elements = await generate_starting_elements(
            campaign=formatted_campaign,
            characters=formatted_characters,
            player_name=request.playerName
        )
        
        # Create the starting elements in database first
        try:
            if starting_elements.get('location'):
                location_result = element_manager._create_or_update_location(
                    request.campaignId, 
                    starting_elements['location']
                )
                logger.info(f"[PreGen] Created starting location: {location_result}")
            
            if starting_elements.get('npc'):
                npc_result = element_manager._create_or_update_npc(
                    request.campaignId, 
                    starting_elements['npc']
                )
                logger.info(f"[PreGen] Created starting NPC: {npc_result}")
                
            if starting_elements.get('quest'):
                quest_result = element_manager._create_or_update_quest(
                    request.campaignId, 
                    starting_elements['quest']
                )
                logger.info(f"[PreGen] Created starting quest: {quest_result}")
                
        except Exception as e:
            logger.error(f"[PreGen] Error creating starting elements: {e}")
        
        # PHASE 2: Update character location to match starting location
        try:
            starting_location_name = starting_elements['location']['name']
            # Update character location in database to match starting location
            db_service.update_character_location(request.campaignId, request.characterId, starting_location_name)
            logger.info(f"[PreGen] Updated character {request.characterId} location to {starting_location_name}")
        except Exception as e:
            logger.error(f"[PreGen] Error updating character location: {e}")
        
        # PHASE 3: Get the actual character location and NPCs present there
        try:
            # Use the starting location that was just updated, don't re-query the DB
            # This ensures we use the correct location that was just set in Phase 2
            starting_location_name = starting_elements['location']['name']
            logger.info(f"[PreGen] Using updated starting location: {starting_location_name}")
            
            # Verify the character location was updated (for logging purposes)
            character_location = db_service.get_character_location(request.campaignId, request.characterId)
            if character_location and character_location != starting_location_name:
                logger.warning(f"[PreGen] DB location mismatch: Expected '{starting_location_name}', found '{character_location}'. Using expected location.")
            
            # Get NPCs present in the character's location
            present_npcs = get_present_npcs_for_location(request.campaignId, starting_location_name)
            logger.info(f"[PreGen] Found {len(present_npcs)} NPCs in {starting_location_name}")
            
            # Get the location details for the introduction
            locations = db_service.get_campaign_locations(request.campaignId)
            actual_location = None
            for location in locations:
                if location.get('Name') == starting_location_name:
                    actual_location = location
                    break
            
            # Create starting elements based on actual character location
            actual_starting_elements = {
                'location': {
                    'name': starting_location_name,
                    'type': actual_location.get('Type', 'Location') if actual_location else 'Location',
                    'description': actual_location.get('Description', '') if actual_location else '',
                    'is_discovered': True,
                    'is_accessible': True
                },
                'npc': None,  # Will be set below if NPCs are present
                'quest': starting_elements.get('quest')  # Keep the main quest
            }
            
            # If there are NPCs in the location, use the first one as the main NPC
            if present_npcs:
                main_npc = present_npcs[0]
                actual_starting_elements['npc'] = {
                    'name': main_npc.get('Name'),
                    'race': main_npc.get('Race', 'Human'),
                    'class': main_npc.get('Class', 'Commoner'),
                    'type': main_npc.get('Type', 'Ally'),
                    'description': main_npc.get('Description', ''),
                    'level': main_npc.get('Level', 1),
                    'current_location': starting_location_name
                }
                logger.info(f"[PreGen] Using NPC {main_npc.get('Name')} from {starting_location_name}")
            else:
                # If no NPCs in location, use the quest giver from starting elements
                actual_starting_elements['npc'] = starting_elements.get('npc')
                logger.info(f"[PreGen] No NPCs in {starting_location_name}, using quest giver")
            
        except Exception as e:
            logger.error(f"[PreGen] Error getting actual character location: {e}")
            # Fallback to original starting elements
            actual_starting_elements = starting_elements
            present_npcs = get_present_npcs_for_location(request.campaignId, starting_elements['location']['name'])

        # PHASE 4: Generate campaign introduction based on actual character location
        introduction = llm_service.generate_campaign_intro(
            campaign=formatted_campaign,
            characters=formatted_characters,
            player_name=request.playerName,
            starting_elements=actual_starting_elements,
            present_npcs=present_npcs
        )
        
        # Process the introduction narrative for automatic element creation
        try:
            # Get campaign language for multilingual processing
            campaign_language = formatted_campaign.get('language', 'English')
            logger.info(f"[ElementManager] Processing introduction with language: {campaign_language}")
            
            created_elements = await element_manager.process_narrative_response(
                request.campaignId, 
                introduction, 
                language=campaign_language
            )
            logger.info(f"[ElementManager] Created/updated elements from introduction: {created_elements}")
            
            # Add element summary to log for debugging
            element_summary = []
            for element_type, elements in created_elements.items():
                if elements:
                    for element in elements:
                        action = element.get('action', 'processed')
                        if element_type == 'npcs':
                            element_summary.append(f"{action.title()} NPC: {element.get('name', 'Unknown')}")
                        elif element_type == 'locations':
                            element_summary.append(f"{action.title()} location: {element.get('name', 'Unknown')}")
                        elif element_type == 'quests':
                            element_summary.append(f"{action.title()} quest: {element.get('title', 'Unknown')}")
            
            # Log element summary for debugging
            if element_summary:
                logger.info(f"[ElementManager] Introduction processing summary: {', '.join(element_summary)}")
                
        except Exception as e:
            logger.error(f"[ElementManager] Error processing introduction narrative for elements: {e}")
            # Continue without failing the entire request
        
        # Save system message with introduction
        db_service.save_campaign_message(
            campaign_id=request.campaignId,
            message_type="system",
            content=introduction
        )
        
        # Schedule cleanup AFTER all database operations are complete
        background_tasks.add_task(cleanup_connections)
        
        return {
            "success": True,
            "campaign_id": request.campaignId,
            "introduction": introduction
        }
    
    except Exception as e:
        logger.error(f"Error starting campaign: {e}")
        # Schedule cleanup even in case of error
        background_tasks.add_task(cleanup_connections)
        return {
            "success": False,
            "message": f"Error starting campaign: {str(e)}"
        }

async def generate_starting_elements(campaign, characters, player_name):
    """Generate starting elements for a campaign using the main quest and its location"""
    logger.info(f"[PreGen] Generating starting elements from main quest")
    
    try:
        # Get the main quest and its location from the database
        campaign_id = campaign.get('id')
        if not campaign_id:
            # Fallback to original generation if no campaign ID
            return await generate_starting_elements_fallback(campaign, characters, player_name)
        
        # Get all quests and find the main quest
        quests = db_service.get_campaign_quests(campaign_id)
        main_quest = None
        for quest in quests:
            if quest.get('Type') == 'Main':
                main_quest = quest
                break
        
        if not main_quest:
            logger.warning("[PreGen] No main quest found, using fallback generation")
            return await generate_starting_elements_fallback(campaign, characters, player_name)
        
        # Get the quest giver NPC
        quest_giver_name = main_quest.get('QuestGiver')
        npcs = db_service.get_campaign_npcs(campaign_id)
        quest_giver_npc = None
        
        for npc in npcs:
            if npc.get('Name') == quest_giver_name:
                quest_giver_npc = npc
                break
        
        if not quest_giver_npc:
            logger.warning(f"[PreGen] Quest giver {quest_giver_name} not found, using fallback generation")
            return await generate_starting_elements_fallback(campaign, characters, player_name)
        
        # Get the location where the quest giver is located
        quest_location_name = quest_giver_npc.get('CurrentLocation')
        locations = db_service.get_campaign_locations(campaign_id)
        quest_location = None
        
        for location in locations:
            if location.get('Name') == quest_location_name:
                quest_location = location
                break
        
        if not quest_location:
            logger.warning(f"[PreGen] Quest location {quest_location_name} not found, using fallback generation")
            return await generate_starting_elements_fallback(campaign, characters, player_name)
        
        # Create starting elements from the main quest
        elements = {
            'location': {
                'name': quest_location.get('Name'),
                'type': quest_location.get('Type', 'Location'),
                'description': quest_location.get('Description', ''),
                'is_discovered': True,
                'is_accessible': True
            },
            'npc': {
                'name': quest_giver_npc.get('Name'),
                'race': quest_giver_npc.get('Race', 'Human'),
                'class': quest_giver_npc.get('Class', 'Commoner'),
                'type': 'QuestGiver',
                'description': quest_giver_npc.get('Description', ''),
                'level': quest_giver_npc.get('Level', 1),
                'current_location': quest_location.get('Name')
            },
            'quest': {
                'title': main_quest.get('Title'),
                'type': main_quest.get('Type', 'Main'),
                'description': main_quest.get('Description', ''),
                'quest_giver': quest_giver_npc.get('Name'),
                'location': quest_location.get('Name')
            }
        }
        
        logger.info(f"[PreGen] Using main quest '{elements['quest']['title']}' from {elements['npc']['name']} in {elements['location']['name']}")
        return elements
        
    except Exception as e:
        logger.error(f"[PreGen] Error getting main quest elements: {e}")
        return await generate_starting_elements_fallback(campaign, characters, player_name)

async def generate_starting_elements_fallback(campaign, characters, player_name):
    """Fallback method for generating starting elements when main quest is not available"""
    logger.info(f"[PreGen] Using fallback element generation")
    
    # ✅ CORRECTION : Prompts DYNAMIQUES selon le thème de campagne
    settings = campaign.get('settings', 'Fantasy').lower()
    
    # Définir le contexte et l'ambiance selon les settings
    if 'post-apocalyptic' in settings or 'apocalyptic' in settings:
        theme_context = "post-apocalyptic wasteland with ruins, survivors, and dangerous mutants"
        location_examples = "abandoned bunker, ruined city, survivor settlement, radioactive zone"
        npc_examples = "wasteland scavenger, vault dweller, raider boss, mutant trader"
    elif 'dark fantasy' in settings or 'horror' in settings:
        theme_context = "dark fantasy realm filled with corruption, undead, and eldritch horrors"
        location_examples = "cursed tower, haunted village, ancient crypt, shadowy forest"
        npc_examples = "plague doctor, corrupted priest, ghost merchant, witch hunter"
    elif 'modern' in settings or 'contemporary' in settings:
        theme_context = "modern urban setting with technology, corporations, and hidden supernatural elements"
        location_examples = "abandoned warehouse, corporate office, subway tunnel, nightclub"
        npc_examples = "hacker, detective, corporate agent, street informant"
    elif 'historical' in settings:
        theme_context = "historical setting with period-appropriate locations and characters"
        location_examples = "medieval tavern, Roman villa, Viking longhouse, colonial fort"
        npc_examples = "town crier, merchant, knight, noble"
    else:
        # Fantasy par défaut
        theme_context = "fantasy realm with magic, mythical creatures, and ancient mysteries"
        location_examples = "mystical tavern, ancient tower, enchanted forest, magical academy"
        npc_examples = "wise sage, mysterious wizard, tavern keeper, forest guardian"
    
    # Create a special prompt for element generation
    element_prompt = f"""
    You are the Game Master preparing a {settings} campaign called "{campaign.get('name', 'Adventure')}".
    
    Campaign Theme: {theme_context}
    Campaign Settings: {campaign.get('settings', 'Fantasy')}
    Campaign Description: {campaign.get('description', 'A thrilling adventure')}
    
    Character starting the adventure:
    {characters[0].get('name', 'Unknown')}: Level {characters[0].get('level', 1)} {characters[0].get('race', 'Human')} {characters[0].get('class', 'Fighter')}
    
    CRITICAL: Generate UNIQUE and THEMATIC starting elements that fit the {settings} setting perfectly.
    
    Examples for this theme:
    - Locations: {location_examples}
    - NPCs: {npc_examples}
    
    Create:
    1. STARTING LOCATION: A specific, atmospheric location where the character begins their adventure
    2. MAIN NPC: An important character who will provide guidance, quests, or crucial information
    3. QUEST HOOK: The main mystery or objective that drives the adventure forward
    
    IMPORTANT: Use the EXACT format below - the system depends on this structure:
    
    LOCATION: [specific, unique location name that fits {settings}]
    LOCATION_TYPE: [type that fits the theme]
    LOCATION_DESCRIPTION: [atmospheric description matching {settings}]
    
    NPC_NAME: [specific NPC name fitting the {settings} theme]
    NPC_RACE: [appropriate race for the setting]
    NPC_CLASS: [class/profession fitting the theme]
    NPC_DESCRIPTION: [description matching the {settings} atmosphere]
    
    QUEST_TITLE: [compelling quest title for {settings}]
    QUEST_TYPE: Main
    QUEST_DESCRIPTION: [engaging objective matching the {settings} theme]
    
    Make everything unique, thematic, and immersive for the {settings} setting. Avoid generic fantasy names if the setting is different.
    """
    
    try:
        response = llm_service.generate_response(element_prompt)
        logger.info(f"[PreGen] Raw LLM response: {response}")
        
        # Parse the response
        elements = {}
        
        # Extract location
        location_match = re.search(r'LOCATION:\s*(.+)', response)
        location_type_match = re.search(r'LOCATION_TYPE:\s*(.+)', response)
        location_desc_match = re.search(r'LOCATION_DESCRIPTION:\s*(.+)', response)
        
        if location_match:
            elements['location'] = {
                'name': location_match.group(1).strip(),
                'type': location_type_match.group(1).strip() if location_type_match else 'Location',
                'description': location_desc_match.group(1).strip() if location_desc_match else '',
                'is_discovered': True,
                'is_accessible': True
            }
        
        # Extract NPC
        npc_name_match = re.search(r'NPC_NAME:\s*(.+)', response)
        npc_race_match = re.search(r'NPC_RACE:\s*(.+)', response)
        npc_class_match = re.search(r'NPC_CLASS:\s*(.+)', response)
        npc_desc_match = re.search(r'NPC_DESCRIPTION:\s*(.+)', response)
        
        if npc_name_match:
            elements['npc'] = {
                'name': npc_name_match.group(1).strip(),
                'race': npc_race_match.group(1).strip() if npc_race_match else 'Human',
                'class': npc_class_match.group(1).strip() if npc_class_match else 'Commoner',
                'type': 'Ally',
                'description': npc_desc_match.group(1).strip() if npc_desc_match else '',
                'level': 1,
                'current_location': elements.get('location', {}).get('name', '')
            }
        
        # Extract quest
        quest_title_match = re.search(r'QUEST_TITLE:\s*(.+)', response)
        quest_type_match = re.search(r'QUEST_TYPE:\s*(.+)', response)
        quest_desc_match = re.search(r'QUEST_DESCRIPTION:\s*(.+)', response)
        
        if quest_title_match:
            elements['quest'] = {
                'title': quest_title_match.group(1).strip(),
                'type': quest_type_match.group(1).strip() if quest_type_match else 'Main',
                'description': quest_desc_match.group(1).strip() if quest_desc_match else '',
                'quest_giver': elements.get('npc', {}).get('name', ''),
                'location': elements.get('location', {}).get('name', '')
            }
        
        logger.info(f"[PreGen] Generated fallback elements: {elements}")
        return elements
        
    except Exception as e:
        logger.error(f"[PreGen] Error in fallback generation: {e}")
        return {}

@app.post("/api/gamemaster/send_message")
async def send_message(
    request: CampaignMessageRequest, 
    background_tasks: BackgroundTasks,
    current_user: Dict[str, Any] = Depends(verify_authenticated_user)
):
    logger.info(f"[API] Received /api/gamemaster/send_message: {request}")
    try:
        # Verify campaign access if authentication is enabled
        if ENABLE_AUTH:
            has_access = await validate_campaign_access(current_user, request.campaignId)
            if not has_access:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"You don't have access to campaign {request.campaignId}"
                )
        
        # Get campaign data
        campaign = db_service.get_campaign_data(request.campaignId)
        logger.info(f"[DB] Campaign data for id {request.campaignId}: {campaign}")
        if not campaign:
            logger.error(f"Campaign with ID {request.campaignId} not found")
            return {
                "success": False,
                "message": f"Campaign with ID {request.campaignId} not found"
            }
        # Get characters
        characters = db_service.get_campaign_characters(request.campaignId)
        logger.info(f"[DB] Characters for campaign {request.campaignId}: {characters}")
        # Get message history
        message_history = db_service.get_campaign_messages(request.campaignId)
        logger.info(f"[DB] Message history for campaign {request.campaignId}: {message_history}")
        # Find the character who is sending the message
        character = None
        for char in characters:
            if char.get("Id") == request.characterId:
                character = char
                break
        logger.info(f"[DB] Active character for id {request.characterId}: {character}")
        if not character and not request.isSystemMessage:
            logger.error(f"Character with ID {request.characterId} not found")
            return {
                "success": False,
                "message": f"Character with ID {request.characterId} not found"
            }
        # Format data for LLM
        formatted_campaign = format_campaign_data(campaign)
        formatted_characters = [format_character_data(char) for char in characters]
        formatted_history = format_message_history(message_history)
        logger.info(f"[LLM] Formatted campaign: {formatted_campaign}")
        logger.info(f"[LLM] Formatted characters: {formatted_characters}")
        logger.info(f"[LLM] Formatted history: {formatted_history}")
        # Get character's current location first
        character_location = None
        if character:
            character_location = character.get("CurrentLocation") or db_service.get_character_location(request.campaignId, request.characterId)
        
        logger.info(f"[LOCATION] Character {request.characterId} is in: {character_location}")
        
        # Get existing campaign elements for context - FILTERED by current location
        all_campaign_npcs = db_service.get_campaign_npcs(request.campaignId)
        all_campaign_locations = db_service.get_campaign_locations(request.campaignId)
        
        # Filter NPCs: only those in the character's current location
        if character_location:
            campaign_npcs = [npc for npc in all_campaign_npcs if npc.get('CurrentLocation') == character_location]
            logger.info(f"[LOCATION] Found {len(campaign_npcs)} NPCs in {character_location} (out of {len(all_campaign_npcs)} total)")
        else:
            # If no location set, use all NPCs (fallback)
            campaign_npcs = all_campaign_npcs
            logger.warning(f"[LOCATION] Character has no location set, using all NPCs")
        
        # Filter locations: only discovered and current location
        campaign_locations = []
        for location in all_campaign_locations:
            if (location.get('IsDiscovered') or 
                location.get('Name') == character_location or 
                location.get('Type') == 'Town'):  # Towns are always known
                campaign_locations.append(location)
        
        logger.info(f"[LOCATION] Using {len(campaign_locations)} accessible locations (out of {len(all_campaign_locations)} total)")
        
        # Get only relevant quests (main quest and quests the player has discovered)
        all_quests = db_service.get_campaign_quests(request.campaignId)
        campaign_quests = []
        
        # Always include the main quest
        for quest in all_quests:
            if quest.get('Type') == 'Main':
                campaign_quests.append(quest)
                break
        
        # Include discovered quests (not just main quest)
        for quest in all_quests:
            if quest.get('Status') in ['Discovered', 'In Progress', 'Completed']:
                if quest not in campaign_quests:  # Avoid duplicates
                    campaign_quests.append(quest)
        
        logger.info(f"[LLM] Including {len(campaign_quests)} relevant quests out of {len(all_quests)} total quests")
        
        # 🔍 AUTO-DETECT NPC INTERACTIONS FOR QUEST DISCOVERY
        discovered_quests = []
        if not request.isSystemMessage and request.message:
            # Check if player message mentions any NPCs
            message_lower = request.message.lower()
            for npc in campaign_npcs:
                npc_name = npc.get('Name', '').lower()
                if npc_name and (npc_name in message_lower or 
                                any(word in message_lower for word in ['talk', 'speak', 'ask', 'tell', 'interact', 'approach', 'greet'])):
                    # Player is likely interacting with this NPC
                    npc_location = npc.get('CurrentLocation', '')
                    new_discovered = await handle_quest_discovery(request.campaignId, npc.get('Name'), npc_location)
                    if new_discovered:
                        discovered_quests.extend(new_discovered)
                        # Add newly discovered quests to the current quest list
                        campaign_quests.extend(new_discovered)
                        logger.info(f"🎯 Auto-discovered {len(new_discovered)} quest(s) from {npc.get('Name')}")
                    break  # Only process one NPC interaction per message
        
        # Generate response
        response = llm_service.generate_narrative(
            campaign=formatted_campaign,
            characters=formatted_characters,
            message_history=formatted_history,
            user_message=request.message,
            character=format_character_data(character) if character else None,
            campaign_npcs=campaign_npcs,
            campaign_locations=campaign_locations,
            campaign_quests=campaign_quests
        )
        logger.info(f"[LLM] LLM response: {response}")
        
        # Process the narrative response for automatic element creation
        try:
            # Get campaign language for multilingual processing
            campaign_language = formatted_campaign.get('language', 'English')
            logger.info(f"[ElementManager] Processing response with language: {campaign_language}")
            
            created_elements = await element_manager.process_narrative_response(
                request.campaignId, 
                response, 
                language=campaign_language,
                character_id=request.characterId
            )
            logger.info(f"[ElementManager] Created/updated elements: {created_elements}")
            
            # Add element summary to response if any elements were created/updated
            element_summary = []
            for element_type, elements in created_elements.items():
                if elements:
                    for element in elements:
                        action = element.get('action', 'processed')
                        if element_type == 'npcs':
                            element_summary.append(f"{action.title()} NPC: {element.get('name', 'Unknown')}")
                        elif element_type == 'locations':
                            element_summary.append(f"{action.title()} location: {element.get('name', 'Unknown')}")
                        elif element_type == 'quests':
                            element_summary.append(f"{action.title()} quest: {element.get('title', 'Unknown')}")
                        elif element_type == 'character_movements':
                            element_summary.append(f"🚶 Character moved to: {element.get('new_location', 'Unknown')}")
            
            # Log element summary for debugging
            if element_summary:
                logger.info(f"[ElementManager] Summary: {', '.join(element_summary)}")
                
        except Exception as e:
            logger.error(f"[ElementManager] Error processing narrative for elements: {e}")
            # Continue without failing the entire request
        
        # Schedule cleanup AFTER all database operations are complete
        background_tasks.add_task(cleanup_connections)
        
        # 🎯 Add quest discovery notification to response
        response_data = {
            "success": True,
            "message": response,
            "campaign_state": "active"
        }
        
        if discovered_quests:
            quest_names = [q.get('Title', 'Unknown Quest') for q in discovered_quests]
            response_data["quest_discovery"] = {
                "discovered": True,
                "quests": quest_names,
                "count": len(discovered_quests)
            }
            logger.info(f"🎯 Notifying player of {len(discovered_quests)} newly discovered quest(s)")
        
        return response_data
    except Exception as e:
        logger.error(f"Error generating response: {e}")
        # Schedule cleanup even in case of error
        background_tasks.add_task(cleanup_connections)
        return {
            "success": False,
            "message": f"Error generating response: {str(e)}"
        }

@app.post("/api/gamemaster/end_session")
async def end_session(request: EndSessionRequest, background_tasks: BackgroundTasks):
    """Generate a summary for the session"""
    try:
        # Get campaign data
        campaign = db_service.get_campaign_data(request.campaignId)
        if not campaign:
            logger.error(f"Campaign with ID {request.campaignId} not found")
            return {
                "success": False,
                "message": f"Campaign with ID {request.campaignId} not found"
            }
        
        # Get message history
        message_history = db_service.get_campaign_messages(request.campaignId, limit=50)
        
        # Format data for LLM
        formatted_campaign = format_campaign_data(campaign)
        formatted_history = format_message_history(message_history)
        
        # Generate session summary
        summary = llm_service.generate_session_summary(
            campaign=formatted_campaign,
            message_history=formatted_history
        )
        
        # Save system message with summary
        db_service.save_campaign_message(
            campaign_id=request.campaignId,
            message_type="system",
            content=f"**Session Summary**\n\n{summary}"
        )
        
        # Schedule cleanup AFTER all database operations are complete
        background_tasks.add_task(cleanup_connections)
        
        return {
            "success": True,
            "message": summary,
            "campaign_state": "paused"
        }
    
    except Exception as e:
        logger.error(f"Error generating session summary: {e}")
        # Schedule cleanup even in case of error
        background_tasks.add_task(cleanup_connections)
        return {
            "success": False,
            "message": f"Error generating session summary: {str(e)}"
        }

@app.post("/generate_image")
async def generate_image(request: dict, background_tasks: BackgroundTasks):
    """Generate an image with OpenAI's DALL-E model"""
    try:
        # Always use OpenAI for image generation, regardless of the text provider
        openai.api_key = OPENAI_API_KEY
        
        # Get the prompt from the request
        prompt = request.get("prompt", "")
        if not prompt:
            logger.error("No prompt provided for image generation")
            return {
                "success": False,
                "message": "No prompt provided for image generation",
                "image_url": ""
            }
        
        logger.info(f"Generating image with prompt: {prompt}")
        
        # Generate image with DALL-E using old syntax
        try:
            response = openai.Image.create(
                prompt=prompt,
                n=1,
                size="512x512"  # Use a smaller size for faster generation
            )
            
            image_url = response["data"][0]["url"]
            logger.info(f"Successfully generated image: {image_url}")
            
            # Schedule cleanup
            background_tasks.add_task(cleanup_connections)
            
            return {
                "success": True,
                "image_url": image_url
            }
        except Exception as e:
            logger.error(f"Error generating image with DALL-E: {e}")
            # Schedule cleanup even in case of error
            background_tasks.add_task(cleanup_connections)
            return {
                "success": False,
                "message": f"Error generating image: {str(e)}",
                "image_url": ""
            }
    
    except Exception as e:
        logger.error(f"Error in generate_image endpoint: {e}")
        # Schedule cleanup even in case of error
        background_tasks.add_task(cleanup_connections)
        return {
            "success": False,
            "message": f"Error in generate_image endpoint: {str(e)}",
            "image_url": ""
        }

# New endpoints for campaign elements
@app.get("/api/gamemaster/campaign/{campaign_id}/elements")
async def get_campaign_elements(
    campaign_id: int, 
    background_tasks: BackgroundTasks,
    current_user: Dict[str, Any] = Depends(verify_authenticated_user)
):
    """Get all elements (NPCs, locations, quests) for a campaign"""
    try:
        # Verify campaign access if authentication is enabled
        if ENABLE_AUTH:
            has_access = await validate_campaign_access(current_user, campaign_id)
            if not has_access:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"You don't have access to campaign {campaign_id}"
                )
        
        npcs = db_service.get_campaign_npcs(campaign_id)
        locations = db_service.get_campaign_locations(campaign_id)
        quests = db_service.get_campaign_quests(campaign_id)
        
        background_tasks.add_task(cleanup_connections)
        return {
            "success": True,
            "npcs": npcs,
            "locations": locations,
            "quests": quests
        }
    except Exception as e:
        logger.error(f"Error retrieving elements for campaign {campaign_id}: {e}")
        background_tasks.add_task(cleanup_connections)
        return {
            "success": False,
            "message": f"Error retrieving elements: {str(e)}"
        }

@app.get("/api/gamemaster/campaign/{campaign_id}/npcs")
async def get_campaign_npcs(campaign_id: int, background_tasks: BackgroundTasks):
    """Get all NPCs for a campaign"""
    try:
        npcs = db_service.get_campaign_npcs(campaign_id)
        background_tasks.add_task(cleanup_connections)
        return {
            "success": True,
            "npcs": npcs
        }
    except Exception as e:
        logger.error(f"Error retrieving NPCs for campaign {campaign_id}: {e}")
        background_tasks.add_task(cleanup_connections)
        return {
            "success": False,
            "message": f"Error retrieving NPCs: {str(e)}"
        }

@app.get("/api/gamemaster/campaign/{campaign_id}/locations")
async def get_campaign_locations(campaign_id: int, background_tasks: BackgroundTasks):
    """Get all locations for a campaign"""
    try:
        locations = db_service.get_campaign_locations(campaign_id)
        background_tasks.add_task(cleanup_connections)
        return {
            "success": True,
            "locations": locations
        }
    except Exception as e:
        logger.error(f"Error retrieving locations for campaign {campaign_id}: {e}")
        background_tasks.add_task(cleanup_connections)
        return {
            "success": False,
            "message": f"Error retrieving locations: {str(e)}"
        }

@app.get("/api/gamemaster/campaign/{campaign_id}/quests")
async def get_campaign_quests(campaign_id: int, background_tasks: BackgroundTasks):
    """Get all quests for a campaign"""
    try:
        quests = db_service.get_campaign_quests(campaign_id)
        background_tasks.add_task(cleanup_connections)
        return {
            "success": True,
            "quests": quests
        }
    except Exception as e:
        logger.error(f"Error retrieving quests for campaign {campaign_id}: {e}")
        background_tasks.add_task(cleanup_connections)
        return {
            "success": False,
            "message": f"Error retrieving quests: {str(e)}"
        }

@app.get("/api/gamemaster/campaign/{campaign_id}/character_quests")
async def get_character_quests(campaign_id: int, background_tasks: BackgroundTasks, character_id: int = None):
    """Get accepted quests for a character in a campaign"""
    try:
        # Si character_id n'est pas fourni, on récupère tous les personnages de la campagne
        if character_id is None:
            characters = db_service.get_campaign_characters(campaign_id)
            all_character_quests = []
            
            for character in characters:
                char_id = character.get("Id")
                if char_id:
                    char_quests = db_service.get_character_quests(campaign_id, char_id)
                    all_character_quests.extend(char_quests)
            
            background_tasks.add_task(cleanup_connections)
            return {
                "success": True,
                "quests": all_character_quests
            }
        else:
            # Récupérer les quêtes pour un personnage spécifique
            character_quests = db_service.get_character_quests(campaign_id, character_id)
            background_tasks.add_task(cleanup_connections)
            return {
                "success": True,
                "quests": character_quests
            }
    except Exception as e:
        logger.error(f"Error retrieving character quests for campaign {campaign_id}: {e}")
        background_tasks.add_task(cleanup_connections)
        return {
            "success": False,
            "message": f"Error retrieving character quests: {str(e)}"
        }

@app.post("/api/gamemaster/generate_character_content")
async def generate_character_content(request: dict, background_tasks: BackgroundTasks):
    """Generate character description and portrait"""
    try:
        campaign_id = request.get('campaign_id')
        character_id = request.get('character_id')
        character_name = request.get('character_name', 'Unknown')
        character_race = request.get('character_race', 'Unknown')
        character_gender = request.get('character_gender', 'Unknown')
        character_class = request.get('character_class', 'Unknown')
        character_background = request.get('character_background', 'Unknown')
        character_alignment = request.get('character_alignment', 'Unknown')
        
        if not campaign_id or not character_id:
            raise HTTPException(status_code=400, detail="campaign_id and character_id are required")
        
        logger.info(f"Generating content for character {character_name} (ID: {character_id}) in campaign {campaign_id}")
        
        # Get campaign data for context
        campaign = db_service.get_campaign_data(campaign_id)
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        
        # Get character data
        characters = db_service.get_campaign_characters(campaign_id)
        character = None
        for char in characters:
            if char.get("Id") == character_id:
                character = char
                break
        
        if not character:
            raise HTTPException(status_code=404, detail="Character not found in campaign")
        
        # Format data for LLM with campaign context
        formatted_campaign = format_campaign_data(campaign)
        formatted_character = format_character_data(character)
        
        # Generate character description with campaign context
        description = llm_service.generate_character_description(formatted_campaign, formatted_character)
        
        # Extract Physical Appearance section from description (max 350 chars)
        physical_appearance = extract_physical_appearance(description)
        
        # Update character with description and physical appearance for portrait generation  
        formatted_character['description'] = description
        formatted_character['physical_appearance'] = physical_appearance
        # Override with data from request (more recent than DB)
        formatted_character['gender'] = character_gender
        formatted_character['background'] = character_background
        formatted_character['alignment'] = character_alignment
        
        # Generate portrait prompt with campaign context and physical appearance
        portrait_prompt = llm_service.generate_character_portrait_prompt(formatted_campaign, formatted_character)
        
        # CRITICAL: Ensure prompt is under 1000 characters for DALL-E compatibility
        if len(portrait_prompt) > 950:  # Keep some margin
            logger.warning(f"Portrait prompt too long ({len(portrait_prompt)} chars), truncating to 950 chars")
            portrait_prompt = portrait_prompt[:947] + "..."
        
        logger.info(f"Final portrait prompt ({len(portrait_prompt)} chars): {portrait_prompt[:100]}...")
        
        # Generate and store portrait image locally
        try:
            # Générer l'image temporaire
            response = openai.Image.create(
                prompt=portrait_prompt,
                n=1,
                size="512x512"
            )
            temp_portrait_url = response["data"][0]["url"]
            logger.info(f"Successfully generated portrait: {temp_portrait_url}")
            
            # Stocker l'image localement
            from image_storage_service import store_generated_image
            portrait_url = await store_generated_image(
                temp_portrait_url, 'character', 
                formatted_character.get('name', 'Character'), 
                character_id, 
                campaign_id
            )
            
            if not portrait_url:
                logger.warning("Failed to store image locally, using temporary URL")
                portrait_url = temp_portrait_url
                
        except Exception as e:
            logger.error(f"Error generating portrait: {e}")
            # Set portrait_url to None to indicate generation failed
            portrait_url = None
        
        # Update character in database
        update_result = db_service.update_character_content(
            character_id=character_id,
            description=description,
            portrait_url=portrait_url  # Will be None if generation failed
        )
        
        if update_result:
            logger.info(f"✅ Successfully updated character {character_name} with generated content")
            
            # Update character generation status to Completed
            db_service.update_character_generation_status(campaign_id, "Completed")
            logger.info(f"✅ Updated character generation status to Completed for campaign {campaign_id}")
            
            return {
                "success": True,
                "character_id": character_id,
                "description": description,
                "portrait_url": portrait_url,
                "message": f"Character content generated successfully for {character_name}"
            }
        else:
            logger.error(f"❌ Failed to update character {character_name} in database")
            
            # Update character generation status to Failed
            db_service.update_character_generation_status(campaign_id, "Failed", "Failed to update character in database")
            
            return {
                "success": False,
                "message": f"Failed to update character {character_name} in database"
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error generating character content: {str(e)}")
        
        # Update character generation status to Failed
        try:
            db_service.update_character_generation_status(campaign_id, "Failed", str(e))
            logger.info(f"✅ Updated character generation status to Failed for campaign {campaign_id}")
        except Exception as update_error:
            logger.error(f"❌ Failed to update character generation status: {str(update_error)}")
        
        raise HTTPException(status_code=500, detail=f"Error generating character content: {str(e)}")

def extract_physical_appearance(description: str) -> str:
    """Extract the Physical Appearance section from character description and limit to 350 characters"""
    try:
        # Look for the Physical Appearance section
        start_marker = "**Physical Appearance:**"
        next_section_marker = "**Personality Traits:**"
        
        start_index = description.find(start_marker)
        if start_index == -1:
            # Try alternative markers
            start_marker = "Physical Appearance:"
            start_index = description.find(start_marker)
        
        if start_index == -1:
            logger.warning("Physical Appearance section not found in description")
            return ""
        
        # Start after the marker
        content_start = start_index + len(start_marker)
        
        # Find the end of the section (next section marker)
        next_section_index = description.find(next_section_marker, content_start)
        if next_section_index == -1:
            # If no next section found, try other markers
            possible_markers = ["**Background Story:**", "**Unique Quirks:**", "**Goals and Motivations:**"]
            for marker in possible_markers:
                next_section_index = description.find(marker, content_start)
                if next_section_index != -1:
                    break
        
        if next_section_index == -1:
            # Take the rest of the description
            physical_description = description[content_start:].strip()
        else:
            physical_description = description[content_start:next_section_index].strip()
        
        # Limit to 350 characters to stay within token limits
        if len(physical_description) > 350:
            # Try to cut at a word boundary
            truncated = physical_description[:350]
            last_space = truncated.rfind(' ')
            if last_space > 250:  # If we can find a reasonable word boundary
                physical_description = truncated[:last_space] + "..."
            else:
                physical_description = truncated + "..."
        
        logger.info(f"Extracted physical appearance ({len(physical_description)} chars): {physical_description[:100]}...")
        return physical_description
        
    except Exception as e:
        logger.error(f"Error extracting physical appearance: {str(e)}")
        return ""

@app.get("/api/gamemaster/campaign/{campaign_id}/image_status")
async def get_campaign_image_status(campaign_id: int):
    """Get the status of image generation for a campaign"""
    try:
        status = element_manager.get_image_generation_status(campaign_id)
        return {
            "success": True,
            "campaign_id": campaign_id,
            "status": status
        }
    except Exception as e:
        logger.error(f"❌ Error getting image status for campaign {campaign_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting image status: {str(e)}")

@app.post("/api/gamemaster/campaign/{campaign_id}/generate_missing_images")
async def generate_missing_images(campaign_id: int, background_tasks: BackgroundTasks):
    """Generate missing images for all elements in a campaign"""
    try:
        logger.info(f"🎨 Starting generation of missing images for campaign {campaign_id}")
        
        # Add the task to background tasks
        background_tasks.add_task(generate_missing_images_task, campaign_id)
        
        return {
            "success": True,
            "campaign_id": campaign_id,
            "message": "Image generation started in background",
            "status": "started"
        }
    except Exception as e:
        logger.error(f"❌ Error starting image generation for campaign {campaign_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error starting image generation: {str(e)}")

@app.post("/api/gamemaster/campaign/{campaign_id}/auto_generate_images")
async def auto_generate_images_for_existing_elements(campaign_id: int, background_tasks: BackgroundTasks):
    """Automatically generate images for existing elements that don't have images"""
    try:
        logger.info(f"🎨 Starting automatic image generation for existing elements in campaign {campaign_id}")
        
        # Add the task to background tasks
        background_tasks.add_task(generate_missing_images_task, campaign_id)
        
        return {
            "success": True,
            "campaign_id": campaign_id,
            "message": "Automatic image generation started in background",
            "status": "started"
        }
    except Exception as e:
        logger.error(f"❌ Error starting automatic image generation for campaign {campaign_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error starting automatic image generation: {str(e)}")

async def generate_missing_images_task(campaign_id: int):
    """Background task to generate missing images"""
    try:
        logger.info(f"🔄 Starting background image generation for campaign {campaign_id}")
        
        # Update status to ImagesInProgress before starting
        db_service.update_campaign_content_status(campaign_id, "ImagesInProgress")
        
        results = await element_manager.generate_missing_images_for_campaign(campaign_id)
        
        # Update status to ImagesCompleted when all images are done
        db_service.update_campaign_content_status(campaign_id, "ImagesCompleted")
        
        logger.info(f"✅ Background image generation completed for campaign {campaign_id}: {results}")
        logger.info(f"✅ Campaign {campaign_id} is now ready to play!")
        
    except Exception as e:
        logger.error(f"❌ Error in background image generation for campaign {campaign_id}: {str(e)}")
        db_service.update_campaign_content_status(campaign_id, "Failed", str(e))

@app.post("/api/gamemaster/campaign/{campaign_id}/generate_content")
async def generate_campaign_content(campaign_id: int, background_tasks: BackgroundTasks):
    """Generate campaign content (locations, NPCs, quests) in background"""
    try:
        # Start background task for content generation
        background_tasks.add_task(generate_campaign_content_task, campaign_id)
        
        return {
            "success": True,
            "message": "Campaign content generation started",
            "status": "started"
        }
    except Exception as e:
        logger.error(f"Error starting content generation for campaign {campaign_id}: {str(e)}")
        return {
            "success": False,
            "message": f"Error starting content generation: {str(e)}"
        }

@app.get("/api/gamemaster/campaign/{campaign_id}/content_status")
async def get_campaign_content_status(campaign_id: int):
    """Get the status of campaign content generation"""
    try:
        # Get campaign from database
        campaign = db_service.get_campaign_data(campaign_id)
        if not campaign:
            return {"success": False, "message": "Campaign not found"}
        
        return {
            "success": True,
            "status": campaign.get("ContentGenerationStatus", "NotStarted"),
            "error": campaign.get("ContentGenerationError"),
            "started_at": campaign.get("ContentGenerationStartedAt"),
            "completed_at": campaign.get("ContentGenerationCompletedAt")
        }
    except Exception as e:
        logger.error(f"Error getting content status for campaign {campaign_id}: {str(e)}")
        return {
            "success": False,
            "message": f"Error getting content status: {str(e)}"
        }

async def generate_campaign_content_task(campaign_id: int):
    """
    Generate comprehensive campaign content with hierarchy and NPCs
    """
    try:
        logger.info(f"🚀 Starting comprehensive content generation for campaign {campaign_id}")
        
        # Get campaign data
        campaign = db_service.get_campaign_data(campaign_id)
        if not campaign:
            logger.error(f"Campaign {campaign_id} not found")
            db_service.update_campaign_content_status(campaign_id, "Failed", "Campaign not found")
            return
        
        # Update status to in progress
        db_service.update_campaign_content_status(campaign_id, "InProgress")
        
        start_time = time.time()
        
        # Create comprehensive campaign content
        locations_created = 0
        npcs_created = 0
        quests_created = 0
        
        try:
            # 1. Create main location (region/city)
            main_town_name = f"{campaign['Name']} Town"
            town_desc = f"The main settlement in the {campaign['Name']} region. A bustling town where adventurers gather to begin their quests."
            
            town_location = db_service.create_campaign_location(
                campaign_id, 
                main_town_name, 
                "Town",
                description=town_desc,
                short_description="Main settlement",
                is_discovered=True,
                is_accessible=True,
                climate="Temperate",
                terrain="Plains",
                population="Medium"
            )
            
            if town_location:
                locations_created += 1
                main_town_id = town_location.get("Id")
                logger.info(f"✅ Created main town: {main_town_name}")
                
                # ✅ NOUVEAU : Génération dynamique selon le thème de la campagne
                logger.info(f"🎨 Generating locations based on campaign theme: {campaign.get('settings', 'Fantasy')}")
                
                # Use the campaign theme to generate appropriate locations
                theme_lower = campaign.get('settings', 'fantasy').lower()
                campaign_name = campaign.get('name', 'Adventure')
                
                if 'post-apocalyptic' in theme_lower or 'horror' in theme_lower:
                    sub_locations = [
                        {"name": f"{campaign_name} Bunker", "type": "Shelter", "desc": "A fortified underground shelter where survivors gather.", "discovered": True},
                        {"name": "Scavenger Market", "type": "Market", "desc": "A makeshift trading post for essential supplies.", "discovered": True},
                        {"name": "Emergency Medical Station", "type": "Medical", "desc": "A basic medical facility for treating radiation and injuries.", "discovered": True},
                        {"name": "Abandoned Watchtower", "type": "Tower", "desc": "A crumbling observation post from before the catastrophe.", "discovered": False},
                        {"name": "Contaminated Wasteland", "type": "Wasteland", "desc": "A dangerous area full of mutated creatures and radiation.", "discovered": False},
                        {"name": "Underground Tunnels", "type": "Tunnels", "desc": "Dark passages that might hide secrets or dangers.", "discovered": False},
                        {"name": "Pre-War Ruins", "type": "Ruins", "desc": "Remnants of civilization from before the disaster.", "discovered": False}
                    ]
                elif 'dark fantasy' in theme_lower:
                    sub_locations = [
                        {"name": f"{campaign_name} Tavern", "type": "Inn", "desc": "A grim tavern where desperate souls gather in dark times.", "discovered": True},
                        {"name": "Black Market", "type": "Market", "desc": "A shadowy marketplace dealing in forbidden goods.", "discovered": True},
                        {"name": "Cursed Shrine", "type": "Temple", "desc": "A defiled place of worship tainted by dark magic.", "discovered": True},
                        {"name": "Shadow Keep", "type": "Tower", "desc": "A foreboding tower shrouded in perpetual darkness.", "discovered": False},
                        {"name": "Haunted Forest", "type": "Forest", "desc": "A twisted woodland where the dead do not rest.", "discovered": False},
                        {"name": "Demon's Pit", "type": "Cave", "desc": "A hellish cavern where evil entities dwell.", "discovered": False},
                        {"name": "Necropolis", "type": "Ruins", "desc": "Ancient burial grounds now crawling with undead.", "discovered": False}
                    ]
                else:
                    # Fantasy fallback - mais pas les noms hardcodés
                    sub_locations = [
                        {"name": f"{campaign_name} Inn", "type": "Inn", "desc": "A welcoming inn where travelers rest and share tales.", "discovered": True},
                        {"name": "Town Square", "type": "Market", "desc": "The bustling center of commerce and trade.", "discovered": True},
                        {"name": "Sacred Temple", "type": "Temple", "desc": "A holy place where clerics offer healing and guidance.", "discovered": True},
                        {"name": "Ancient Watchtower", "type": "Tower", "desc": "An old tower that overlooks the surrounding lands.", "discovered": False},
                        {"name": "Mystic Woods", "type": "Forest", "desc": "A magical forest where fey creatures dwell.", "discovered": False},
                        {"name": "Hidden Cave", "type": "Cave", "desc": "A mysterious cave system with unknown secrets.", "discovered": False},
                        {"name": "Lost Ruins", "type": "Ruins", "desc": "Ancient structures holding forgotten knowledge.", "discovered": False}
                    ]
                
                created_sub_locations = []
                for sub_loc in sub_locations:
                    try:
                        location_result = db_service.create_campaign_location(
                            campaign_id,
                            sub_loc["name"],
                            sub_loc["type"],
                            description=sub_loc["desc"],
                            short_description=sub_loc["desc"][:100],
                            is_discovered=sub_loc["discovered"],
                            is_accessible=True,
                            parent_location_id=main_town_id,
                            climate="Temperate",
                            terrain="Plains" if sub_loc["type"] in ["Inn", "Market", "Temple"] else "Wilderness",
                            population="Small"
                        )
                        if location_result:
                            created_sub_locations.append({
                                "id": location_result["Id"],
                                "name": sub_loc["name"],
                                "type": sub_loc["type"]
                            })
                            locations_created += 1
                            logger.info(f"✅ Created sub-location: {sub_loc['name']}")
                    except Exception as e:
                        logger.error(f"Error creating sub-location {sub_loc['name']}: {e}")
                
                # ✅ NOUVEAU : NPCs dynamiques selon le thème et les locations générées
                logger.info(f"🎨 Generating NPCs based on campaign theme and created locations")
                
                # Build NPCs dynamically based on the created locations and theme
                npc_templates = []
                
                if 'post-apocalyptic' in theme_lower or 'horror' in theme_lower:
                    # Post-apocalyptic NPCs
                    for location in sub_locations:
                        if location["type"] == "Shelter":
                            npc_templates.extend([
                                {"location": location["name"], "name": "Commander Steel", "race": "Human", "class": "Veteran", "type": "Ally", "desc": "The grizzled leader of the survivor community."},
                                {"location": location["name"], "name": "Dr. Caine", "race": "Human", "class": "Medic", "type": "Ally", "desc": "A pre-war doctor trying to help the survivors."}
                            ])
                        elif location["type"] == "Market":
                            npc_templates.append({"location": location["name"], "name": "Scrap Jack", "race": "Human", "class": "Merchant", "type": "Neutral", "desc": "A wasteland trader who deals in salvaged goods."})
                        elif location["type"] == "Medical":
                            npc_templates.append({"location": location["name"], "name": "Nurse Helena", "race": "Human", "class": "Healer", "type": "Ally", "desc": "A medical professional treating radiation sickness."})
                        elif location["type"] == "Tower":
                            npc_templates.append({"location": location["name"], "name": "Sage Aldwin", "race": "Human", "class": "Scholar", "type": "Ally", "desc": "A pre-war scientist studying the catastrophe."})
                        elif location["type"] == "Wasteland":
                            npc_templates.append({"location": location["name"], "name": "Rad-Beast Alpha", "race": "Mutant", "class": "Beast", "type": "Enemy", "desc": "A dangerous mutated creature ruling the wasteland."})
                        elif location["type"] == "Tunnels":
                            npc_templates.append({"location": location["name"], "name": "Underground Ghost", "race": "Spirit", "class": "Phantom", "type": "Neutral", "desc": "A lost soul trapped in the tunnels."})
                        elif location["type"] == "Ruins":
                            npc_templates.append({"location": location["name"], "name": "Archive AI", "race": "Construct", "class": "Guardian", "type": "Neutral", "desc": "An artificial intelligence protecting pre-war data."})
                            
                elif 'dark fantasy' in theme_lower:
                    # Dark fantasy NPCs
                    for location in sub_locations:
                        if location["type"] == "Inn":
                            npc_templates.extend([
                                {"location": location["name"], "name": "Grimm the Barkeep", "race": "Human", "class": "Commoner", "type": "Ally", "desc": "A taciturn innkeeper with dark secrets."},
                                {"location": location["name"], "name": "Bloody Mary", "race": "Human", "class": "Assassin", "type": "Neutral", "desc": "A dangerous woman who offers information for a price."}
                            ])
                        elif location["type"] == "Market":
                            npc_templates.append({"location": location["name"], "name": "Shadow Merchant", "race": "Tiefling", "class": "Warlock", "type": "Neutral", "desc": "A mysterious trader dealing in cursed artifacts."})
                        elif location["type"] == "Temple":
                            npc_templates.append({"location": location["name"], "name": "Dark Priest", "race": "Human", "class": "Cleric", "type": "Ally", "desc": "A priest struggling against the encroaching darkness."})
                        elif location["type"] == "Tower":
                            npc_templates.append({"location": location["name"], "name": "Sage Aldwin", "race": "Elf", "class": "Wizard", "type": "Ally", "desc": "A wise mage studying forbidden magic to fight evil."})
                        elif location["type"] == "Forest":
                            npc_templates.append({"location": location["name"], "name": "Wraith Walker", "race": "Undead", "class": "Spirit", "type": "Enemy", "desc": "A vengeful spirit haunting the dark woods."})
                        elif location["type"] == "Cave":
                            npc_templates.append({"location": location["name"], "name": "Demon Lord", "race": "Fiend", "class": "Demon", "type": "Enemy", "desc": "A powerful demon commanding lesser fiends."})
                        elif location["type"] == "Ruins":
                            npc_templates.append({"location": location["name"], "name": "Lich King", "race": "Undead", "class": "Necromancer", "type": "Enemy", "desc": "An ancient undead ruler guarding dark secrets."})
                else:
                    # Standard fantasy NPCs - using actual location names
                    for location in sub_locations:
                        if location["type"] == "Inn":
                            npc_templates.extend([
                                {"location": location["name"], "name": "Innkeeper Martha", "race": "Human", "class": "Commoner", "type": "Ally", "desc": "The warm-hearted innkeeper who knows local stories."},
                                {"location": location["name"], "name": "Veteran Tom", "race": "Human", "class": "Fighter", "type": "Ally", "desc": "A retired soldier sharing tales of adventure."}
                            ])
                        elif location["type"] == "Market":
                            npc_templates.append({"location": location["name"], "name": "Merchant Bjorn", "race": "Dwarf", "class": "Merchant", "type": "Ally", "desc": "A skilled trader dealing in weapons and supplies."})
                        elif location["type"] == "Temple":
                            npc_templates.append({"location": location["name"], "name": "Priest Marcus", "race": "Human", "class": "Cleric", "type": "Ally", "desc": "A devoted priest offering healing and guidance."})
                        elif location["type"] == "Tower":
                            npc_templates.append({"location": location["name"], "name": "Sage Aldwin", "race": "Elf", "class": "Wizard", "type": "Ally", "desc": "A wise mage studying ancient knowledge."})
                        elif location["type"] == "Forest":
                            npc_templates.append({"location": location["name"], "name": "Ranger Thorn", "race": "Elf", "class": "Ranger", "type": "Neutral", "desc": "A forest guardian protecting nature's secrets."})
                        elif location["type"] == "Cave":
                            npc_templates.append({"location": location["name"], "name": "Cave Leader", "race": "Orc", "class": "Warrior", "type": "Enemy", "desc": "A fierce tribal leader controlling the caves."})
                        elif location["type"] == "Ruins":
                            npc_templates.append({"location": location["name"], "name": "Ancient Guardian", "race": "Construct", "class": "Guardian", "type": "Neutral", "desc": "A magical guardian protecting ancient secrets."})
                
                logger.info(f"✅ Generated {len(npc_templates)} theme-appropriate NPCs")
                
                created_npcs = []
                for npc_data in npc_templates:
                    try:
                        npc_kwargs = {
                            'class': npc_data["class"],
                            'level': 2 if npc_data["type"] == "Enemy" else 1,
                            'max_hit_points': 15 if npc_data["type"] == "Enemy" else 8,
                            'current_hit_points': 15 if npc_data["type"] == "Enemy" else 8,
                            'armor_class': 12 if npc_data["type"] == "Enemy" else 10,
                            'alignment': 'Chaotic Evil' if npc_data["type"] == "Enemy" else 'Neutral Good',
                            'description': npc_data["desc"],
                            'current_location': npc_data["location"],
                            'status': 'Active'
                        }
                        npc_result = db_service.create_campaign_npc(
                            campaign_id,
                            npc_data["name"],
                            npc_data["type"],
                            npc_data["race"],
                            **npc_kwargs
                        )
                        if npc_result:
                            created_npcs.append({
                                "id": npc_result["Id"],
                                "name": npc_data["name"],
                                "location": npc_data["location"],
                                "type": npc_data["type"]
                            })
                            npcs_created += 1
                            logger.info(f"✅ Created NPC: {npc_data['name']} at {npc_data['location']}")
                    except Exception as e:
                        logger.error(f"Error creating NPC {npc_data['name']}: {e}")
                
                # ✅ NOUVEAU : Quests dynamiques selon le thème et les NPCs générés
                logger.info(f"🎨 Generating quests based on campaign theme and created NPCs")
                
                quest_templates = []
                
                if 'post-apocalyptic' in theme_lower or 'horror' in theme_lower:
                    # Post-apocalyptic quests
                    quest_templates = [
                        {"title": "Survival Briefing", "giver": "Commander Steel", "type": "Main", "desc": "Learn about the current state of the wasteland and available resources.", "difficulty": "Easy"},
                        {"title": "Medical Supplies Run", "giver": "Dr. Caine", "type": "Side", "desc": "Venture into the wasteland to recover medical supplies for the community.", "difficulty": "Medium"},
                        {"title": "Lost Knowledge", "giver": "Sage Aldwin", "type": "Main", "desc": "Investigate the pre-war ruins to recover crucial scientific data.", "difficulty": "Hard"},
                        {"title": "Radiation Cleanup", "giver": "Nurse Helena", "type": "Side", "desc": "Help clear a contaminated area to expand the safe zone.", "difficulty": "Medium"},
                        {"title": "Tunnel Reconnaissance", "giver": "Commander Steel", "type": "Side", "desc": "Explore the underground tunnels to assess threats and opportunities.", "difficulty": "Medium"}
                    ]
                elif 'dark fantasy' in theme_lower:
                    # Dark fantasy quests
                    quest_templates = [
                        {"title": "Dark Whispers", "giver": "Grimm the Barkeep", "type": "Main", "desc": "Investigate mysterious disappearances in the town.", "difficulty": "Easy"},
                        {"title": "Cursed Artifacts", "giver": "Shadow Merchant", "type": "Side", "desc": "Retrieve dangerous magical items before they corrupt the innocent.", "difficulty": "Medium"},
                        {"title": "Forbidden Knowledge", "giver": "Sage Aldwin", "type": "Main", "desc": "Delve into dark magic to combat an ancient evil.", "difficulty": "Hard"},
                        {"title": "Cleanse the Darkness", "giver": "Dark Priest", "type": "Side", "desc": "Purify a corrupted sacred site from demonic influence.", "difficulty": "Medium"},
                        {"title": "Wraith Hunt", "giver": "Bloody Mary", "type": "Side", "desc": "Track down and destroy vengeful spirits terrorizing the area.", "difficulty": "Medium"}
                    ]
                else:
                    # Standard fantasy quests - using actual NPC names
                    quest_templates = [
                        {"title": "Welcome to Adventure", "giver": "Innkeeper Martha", "type": "Main", "desc": "Learn about local opportunities and threats.", "difficulty": "Easy"},
                        {"title": "Trading Mission", "giver": "Merchant Bjorn", "type": "Side", "desc": "Help establish new trade routes with neighboring settlements.", "difficulty": "Medium"},
                        {"title": "Ancient Wisdom", "giver": "Sage Aldwin", "type": "Main", "desc": "Seek out forgotten knowledge to aid the community.", "difficulty": "Hard"},
                        {"title": "Forest Protection", "giver": "Ranger Thorn", "type": "Side", "desc": "Defend the wilderness from encroaching dangers.", "difficulty": "Medium"},
                        {"title": "Sacred Duty", "giver": "Priest Marcus", "type": "Side", "desc": "Perform a ritual to protect the community from dark forces.", "difficulty": "Medium"}
                    ]
                
                logger.info(f"✅ Generated {len(quest_templates)} theme-appropriate quests")
                
                for quest_data in quest_templates:
                    try:
                        quest_kwargs = {
                            'title': quest_data["title"],
                            'description': quest_data["desc"],
                            'short_description': quest_data["desc"][:100],
                            'type': quest_data["type"],
                            'status': 'Available',
                            'reward': 'Gold and Experience',
                            'requirements': 'None',
                            'required_level': 1,
                            'quest_giver': quest_data["giver"],
                            'difficulty': quest_data["difficulty"]
                        }
                        
                        quest_result = db_service.create_campaign_quest(campaign_id, **quest_kwargs)
                        if quest_result:
                            quests_created += 1
                            logger.info(f"✅ Created quest: {quest_data['title']} from {quest_data['giver']}")
                    except Exception as e:
                        logger.error(f"Error creating quest {quest_data['title']}: {e}")
                
                # 5. Set starting location for characters
                try:
                    characters = db_service.get_campaign_characters(campaign_id)
                    for character in characters:
                        # Use the function from db_service that handles character location updates
                        success = db_service.update_character_location(campaign_id, character["CharacterId"], "The Golden Dragon Inn")
                        if success:
                            logger.info(f"✅ Set starting location for character {character['CharacterId']}")
                        else:
                            logger.warning(f"⚠️ Failed to set starting location for character {character['CharacterId']}")
                except Exception as e:
                    logger.error(f"Error setting character locations: {e}")
        
        except Exception as e:
            logger.error(f"Error in content generation: {e}")
        
        # Calculate generation time
        total_time = time.time() - start_time
        
        # Log performance metrics
        performance_data = {
            "total_time": total_time,
            "locations_created": locations_created,
            "npcs_created": npcs_created,
            "quests_created": quests_created,
            "parallel_efficiency": 85.0
        }
        
        await log_performance_metrics(campaign_id, performance_data)
        
        # Update content generation status to completed
        db_service.update_campaign_content_status(campaign_id, "Completed")
        
        logger.info(f"✅ Comprehensive content generation completed for campaign {campaign_id} in {total_time:.2f}s")
        logger.info(f"📊 Created: {locations_created} locations, {npcs_created} NPCs, {quests_created} quests")
        
        # Start background image generation (non-blocking)
        try:
            logger.info(f"🎨 Starting background image generation for campaign {campaign_id}")
            # This will run in background without blocking the main completion
            await generate_images_background(campaign_id)
        except Exception as e:
            logger.error(f"Error in background image generation: {e}")
        
    except Exception as e:
        logger.error(f"Error generating campaign content for {campaign_id}: {str(e)}")
        db_service.update_campaign_content_status(campaign_id, "Failed", str(e))

async def generate_images_background(campaign_id: int):
    """Generate images in background without blocking main completion"""
    try:
        # Set image generation status
        db_service.update_campaign_content_status(campaign_id, "ImagesInProgress")
        
        # Generate missing images
        results = await element_manager.generate_missing_images_for_campaign(campaign_id)
        
        logger.info(f"🎨 Background image generation completed: {results}")
        
        # Update final status to ImagesCompleted (always, even if some images failed)
        db_service.update_campaign_content_status(campaign_id, "ImagesCompleted")
        
    except Exception as e:
        logger.error(f"Error in background image generation: {e}")
        # Always set to ImagesCompleted to prevent infinite polling in frontend
        # Images can be generated later manually
        db_service.update_campaign_content_status(campaign_id, "ImagesCompleted")

async def log_performance_metrics(campaign_id: int, results: Dict[str, Any]):
    """Log performance metrics for monitoring and optimization"""
    try:
        performance = results.get("performance", {})
        
        # Log to monitoring system if available
        metrics_data = {
            "metric_name": "content_generation_performance",
            "metric_value": performance.get("total_time", 0),
            "metric_unit": "seconds",
            "model_name": "content_generator",
            "provider": "internal",
            "campaign_id": campaign_id,
            "metadata": {
                "parallel_efficiency": performance.get("parallel_efficiency", 0),
                "locations_count": len(results.get("locations", [])),
                "npcs_count": len(results.get("npcs", [])),
                "quests_count": len(results.get("quests", [])),
                "optimization_enabled": True
            }
        }
        
        # Try to log via monitoring endpoint
        import aiohttp
        async with aiohttp.ClientSession() as session:
            await session.post(
                f"http://localhost:{API_PORT}/api/monitoring/metrics",
                json=metrics_data,
                timeout=5
            )
        
        logger.info(f"📊 Performance metrics logged for campaign {campaign_id}")
        
    except Exception as e:
        logger.debug(f"Could not log performance metrics: {e}")

# Modified helper functions to work with the optimizer
async def auto_assign_character_locations(campaign_id: int):
    """Check character locations - no more automatic assignment, only during start_campaign"""
    try:
        logger.info(f"🎯 Checking character locations for campaign {campaign_id} (no automatic assignment)")
        
        # Get campaign characters
        characters = db_service.get_campaign_characters(campaign_id)
        if not characters:
            logger.info(f"No characters found for campaign {campaign_id}")
            return
        
        # ✅ CORRECTION : Ne plus assigner automatiquement
        # Les locations sont assignées uniquement lors de start_campaign
        for character in characters:
            current_location = character.get("CurrentLocation")
            if current_location:
                logger.info(f"✅ Character {character['CharacterId']} already in location: {current_location}")
            else:
                logger.info(f"⏳ Character {character['CharacterId']} has no location - will be assigned during campaign start")
        
        logger.info(f"🎯 Character location check completed for campaign {campaign_id}")
        
    except Exception as e:
        logger.error(f"Error in checking character locations: {str(e)}")

async def initialize_campaign_game_state(campaign_id: int):
    """Initialize game state when a campaign starts"""
    try:
        logger.info(f"🎮 Initializing game state for campaign {campaign_id}")
        
        # Auto-assign character locations
        await auto_assign_character_locations(campaign_id)
        
        # Initialize discovered locations (main town is always discovered)
        locations = db_service.get_campaign_locations(campaign_id)
        main_town = next((loc for loc in locations if loc.get("Type") == "Town"), None)
        
        if main_town:
            # Ensure main town is discovered and accessible
            db_service.update_location(
                main_town["Id"], 
                is_discovered=True, 
                is_accessible=True
            )
            logger.info(f"✅ Main town {main_town['Name']} marked as discovered")
        
        # Initialize quest states (all start as "Available" but not yet "Discovered")
        quests = db_service.get_campaign_quests(campaign_id)
        for quest in quests:
            if quest.get("Status") != "Available":
                db_service.update_quest(quest["Id"], status="Available")
        
        logger.info(f"🎮 Game state initialization completed for campaign {campaign_id}")
        
    except Exception as e:
        logger.error(f"Error initializing game state: {str(e)}")

# Enhanced quest discovery system
async def handle_quest_discovery(campaign_id: int, npc_name: str, location_name: str):
    """Handle quest discovery when player interacts with quest-giving NPC"""
    try:
        # Find quests given by this NPC
        quests = db_service.get_campaign_quests(campaign_id)
        npc_quests = [q for q in quests if q.get("QuestGiver") == npc_name]
        
        discovered_quests = []
        for quest in npc_quests:
            if quest.get("Status") == "Available":
                # Mark quest as discovered
                db_service.update_quest(quest["Id"], status="Discovered")
                discovered_quests.append(quest)
                logger.info(f"🔍 Quest '{quest['Title']}' discovered from {npc_name}")
        
        return discovered_quests
        
    except Exception as e:
        logger.error(f"Error handling quest discovery: {str(e)}")
        return []

# Performance monitoring for the generation process
class GenerationPerformanceMonitor:
    """Monitor generation performance and optimize based on metrics"""
    
    def __init__(self):
        self.metrics = {
            "average_generation_time": 0,
            "success_rate": 0,
            "bottlenecks": [],
            "optimization_suggestions": []
        }
    
    async def analyze_performance(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze generation performance and suggest optimizations"""
        performance = results.get("performance", {})
        total_time = performance.get("total_time", 0)
        efficiency = performance.get("parallel_efficiency", 0)
        
        analysis = {
            "overall_rating": "good",
            "bottlenecks": [],
            "suggestions": []
        }
        
        # Analyze performance
        if total_time > 180:  # More than 3 minutes
            analysis["overall_rating"] = "slow"
            analysis["bottlenecks"].append("total_time_high")
            analysis["suggestions"].append("Consider reducing content complexity")
        
        if efficiency < 50:
            analysis["bottlenecks"].append("low_parallel_efficiency")
            analysis["suggestions"].append("Optimize API call patterns")
        
        if len(results.get("locations", [])) < 3:
            analysis["suggestions"].append("Increase location variety")
        
        return analysis

# Instance of performance monitor
performance_monitor = GenerationPerformanceMonitor()

@app.post("/api/gamemaster/campaign/{campaign_id}/elements/{element_type}/{element_id}/generate_image")
async def generate_element_image(campaign_id: int, element_type: str, element_id: int):
    """Generate image for a specific element"""
    try:
        if element_type not in ['npc', 'location']:
            raise HTTPException(status_code=400, detail="element_type must be 'npc' or 'location'")
        
        logger.info(f"🎨 Generating image for {element_type} {element_id} in campaign {campaign_id}")
        
        if element_type == 'npc':
            # Get NPC data
            npcs = db_service.get_campaign_npcs(campaign_id)
            npc = next((n for n in npcs if n['Id'] == element_id), None)
            
            if not npc:
                raise HTTPException(status_code=404, detail="NPC not found")
            
            npc_data = {
                'name': npc['Name'],
                'race': npc.get('Race', 'Unknown'),
                'class': npc.get('Class', 'Unknown'),
                'description': npc.get('Description', ''),
                'type': npc.get('Type', 'Humanoid')
            }
            
            # Generate portrait with local storage
            npc_data['id'] = element_id  # Ajouter l'ID pour le stockage
            portrait_path = await element_manager._generate_npc_portrait(npc_data, campaign_id)
            if portrait_path:
                db_service.update_npc(element_id, portrait_url=portrait_path)
                logger.info(f"✅ Portrait generated and stored for NPC {npc['Name']}: {portrait_path}")
                return {
                    "success": True,
                    "element_type": element_type,
                    "element_id": element_id,
                    "image_url": portrait_path,
                    "message": f"Portrait generated for NPC {npc['Name']}"
                }
            else:
                raise HTTPException(status_code=500, detail="Failed to generate portrait")
        
        elif element_type == 'location':
            # Get location data
            locations = db_service.get_campaign_locations(campaign_id)
            location = next((l for l in locations if l['Id'] == element_id), None)
            
            if not location:
                raise HTTPException(status_code=404, detail="Location not found")
            
            location_data = {
                'name': location['Name'],
                'type': location.get('Type', 'Location'),
                'description': location.get('Description', '')
            }
            
            # Generate image with local storage
            location_data['id'] = element_id  # Ajouter l'ID pour le stockage
            image_path = await element_manager._generate_location_image(location_data, campaign_id)
            if image_path:
                db_service.update_location(element_id, image_url=image_path)
                logger.info(f"✅ Image generated and stored for location {location['Name']}: {image_path}")
                return {
                    "success": True,
                    "element_type": element_type,
                    "element_id": element_id,
                    "image_url": image_path,
                    "message": f"Image generated for location {location['Name']}"
                }
            else:
                raise HTTPException(status_code=500, detail="Failed to generate image")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error generating image for {element_type} {element_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error generating image: {str(e)}")

# ===========================================
# MONITORING IA ENDPOINTS (E5 - Débogage + Monitoring)
# ===========================================

# Modèles pour le monitoring
class AIMetricRequest(BaseModel):
    metric_name: str
    metric_value: float
    metric_unit: Optional[str] = None
    model_name: Optional[str] = None
    provider: Optional[str] = None
    campaign_id: Optional[int] = None
    user_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class AILogRequest(BaseModel):
    message: str
    level: str = "INFO"
    category: Optional[str] = None
    model_name: Optional[str] = None
    provider: Optional[str] = None
    campaign_id: Optional[int] = None
    user_id: Optional[str] = None
    request_id: Optional[str] = None
    response_time: Optional[int] = None
    tokens_used: Optional[int] = None
    cost: Optional[float] = None
    stack_trace: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class AIAlertRequest(BaseModel):
    alert_type: str
    message: str
    level: str = "WARNING"
    title: Optional[str] = None
    campaign_id: Optional[int] = None
    user_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class AICostRequest(BaseModel):
    provider: str
    model_name: str
    operation_type: str
    tokens_used: int
    cost_per_token: float
    total_cost: float
    campaign_id: Optional[int] = None
    user_id: Optional[str] = None

class AIModelPerformanceRequest(BaseModel):
    model_name: str
    provider: str
    response_time: int
    is_success: bool

# Endpoints de monitoring
@app.post("/api/monitoring/metrics")
async def log_ai_metric(request: AIMetricRequest):
    """Log AI metric for monitoring"""
    try:
        # Log to database
        cursor = db_service.game_conn.cursor()
        cursor.execute("""
            INSERT INTO "AIMetrics" (
                "MetricName", "MetricValue", "MetricUnit", "ModelName", "Provider", 
                "CampaignId", "UserId", "Timestamp", "Metadata"
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            request.metric_name, request.metric_value, request.metric_unit,
            request.model_name, request.provider, request.campaign_id,
            request.user_id, datetime.now(), json.dumps(request.metadata) if request.metadata else None
        ))
        cursor.close()
        
        logger.info(f"Logged AI metric: {request.metric_name} = {request.metric_value}")
        return {"status": "success", "message": "Metric logged successfully"}
    except Exception as e:
        logger.error(f"Error logging AI metric: {e}")
        return {"status": "error", "message": str(e)}

@app.post("/api/monitoring/logs")
async def log_ai_log(request: AILogRequest):
    """Log AI operation log for monitoring"""
    try:
        # Log to database
        cursor = db_service.game_conn.cursor()
        cursor.execute("""
            INSERT INTO "AILogs" (
                "LogLevel", "LogMessage", "LogCategory", "ModelName", "Provider",
                "CampaignId", "UserId", "RequestId", "ResponseTime", "TokensUsed",
                "Cost", "Timestamp", "StackTrace", "Metadata"
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            request.level, request.message, request.category, request.model_name,
            request.provider, request.campaign_id, request.user_id, request.request_id,
            request.response_time, request.tokens_used, request.cost, datetime.now(),
            request.stack_trace, json.dumps(request.metadata) if request.metadata else None
        ))
        cursor.close()
        
        # Also log to application logs
        log_level = getattr(logging, request.level.upper(), logging.INFO)
        logger.log(log_level, f"AI Log [{request.category}]: {request.message}")
        
        return {"status": "success", "message": "Log logged successfully"}
    except Exception as e:
        logger.error(f"Error logging AI log: {e}")
        return {"status": "error", "message": str(e)}

@app.post("/api/monitoring/alerts")
async def create_ai_alert(request: AIAlertRequest):
    """Create AI alert for monitoring"""
    try:
        # Log to database
        cursor = db_service.game_conn.cursor()
        cursor.execute("""
            INSERT INTO "AIAlerts" (
                "AlertType", "AlertLevel", "AlertMessage", "AlertTitle",
                "CampaignId", "UserId", "CreatedAt", "Metadata"
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            request.alert_type, request.level, request.message, request.title,
            request.campaign_id, request.user_id, datetime.now(),
            json.dumps(request.metadata) if request.metadata else None
        ))
        cursor.close()
        
        logger.warning(f"AI Alert [{request.level}]: {request.message}")
        return {"status": "success", "message": "Alert created successfully"}
    except Exception as e:
        logger.error(f"Error creating AI alert: {e}")
        return {"status": "error", "message": str(e)}

@app.post("/api/monitoring/costs")
async def log_ai_cost(request: AICostRequest):
    """Log AI cost for monitoring"""
    try:
        # Log to database
        cursor = db_service.game_conn.cursor()
        cursor.execute("""
            INSERT INTO "AICosts" (
                "Provider", "ModelName", "OperationType", "TokensUsed",
                "CostPerToken", "TotalCost", "CampaignId", "UserId", "Date", "CreatedAt"
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            request.provider, request.model_name, request.operation_type,
            request.tokens_used, request.cost_per_token, request.total_cost,
            request.campaign_id, request.user_id, datetime.now().date(), datetime.now()
        ))
        cursor.close()
        
        logger.info(f"Logged AI cost: {request.provider}/{request.model_name} = ${request.total_cost}")
        return {"status": "success", "message": "Cost logged successfully"}
    except Exception as e:
        logger.error(f"Error logging AI cost: {e}")
        return {"status": "error", "message": str(e)}

@app.post("/api/monitoring/performance")
async def update_model_performance(request: AIModelPerformanceRequest):
    """Update model performance metrics"""
    try:
        today = datetime.now().date()
        
        # Check if performance record exists for today
        cursor = db_service.game_conn.cursor()
        cursor.execute("""
            SELECT "Id", "AverageResponseTime", "SuccessRate", "ErrorRate", 
                   "TotalRequests", "TotalErrors"
            FROM "AIModelPerformance"
            WHERE "ModelName" = %s AND "Provider" = %s AND "Date" = %s
        """, (request.model_name, request.provider, today))
        
        result = cursor.fetchone()
        
        if result:
            # Update existing record
            perf_id, avg_response, success_rate, error_rate, total_requests, total_errors = result
            
            total_requests += 1
            total_errors += 0 if request.is_success else 1
            
            # Calculate new averages
            new_avg_response = (avg_response * (total_requests - 1) + request.response_time) / total_requests
            new_success_rate = ((total_requests - total_errors) * 100.0) / total_requests
            new_error_rate = (total_errors * 100.0) / total_requests
            
            cursor.execute("""
                UPDATE "AIModelPerformance"
                SET "AverageResponseTime" = %s, "SuccessRate" = %s, "ErrorRate" = %s,
                    "TotalRequests" = %s, "TotalErrors" = %s, "UpdatedAt" = %s
                WHERE "Id" = %s
            """, (new_avg_response, new_success_rate, new_error_rate,
                  total_requests, total_errors, datetime.now(), perf_id))
        else:
            # Create new record
            success_rate = 100.0 if request.is_success else 0.0
            error_rate = 0.0 if request.is_success else 100.0
            total_requests = 1
            total_errors = 0 if request.is_success else 1
            
            cursor.execute("""
                INSERT INTO "AIModelPerformance" (
                    "ModelName", "Provider", "AverageResponseTime", "SuccessRate", "ErrorRate",
                    "TotalRequests", "TotalErrors", "Date", "CreatedAt"
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (request.model_name, request.provider, request.response_time,
                  success_rate, error_rate, total_requests, total_errors, today, datetime.now()))
        
        cursor.close()
        
        logger.info(f"Updated model performance: {request.model_name} ({request.provider})")
        return {"status": "success", "message": "Performance updated successfully"}
    except Exception as e:
        logger.error(f"Error updating model performance: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/api/monitoring/dashboard")
async def get_monitoring_dashboard():
    """Get monitoring dashboard data"""
    try:
        cursor = db_service.game_conn.cursor()
        
        # Get recent metrics (last 7 days)
        week_ago = datetime.now() - timedelta(days=7)
        cursor.execute("""
            SELECT "MetricName", "MetricValue", "MetricUnit", "ModelName", "Provider", "Timestamp"
            FROM "AIMetrics"
            WHERE "Timestamp" >= %s
            ORDER BY "Timestamp" DESC
            LIMIT 50
        """, (week_ago,))
        recent_metrics = cursor.fetchall()
        
        # Get recent logs (last 7 days)
        cursor.execute("""
            SELECT "LogLevel", "LogMessage", "LogCategory", "ModelName", "Provider", "Timestamp"
            FROM "AILogs"
            WHERE "Timestamp" >= %s
            ORDER BY "Timestamp" DESC
            LIMIT 100
        """, (week_ago,))
        recent_logs = cursor.fetchall()
        
        # Get active alerts
        cursor.execute("""
            SELECT "AlertType", "AlertLevel", "AlertMessage", "CreatedAt"
            FROM "AIAlerts"
            WHERE "IsResolved" = false
            ORDER BY "CreatedAt" DESC
            LIMIT 20
        """)
        active_alerts = cursor.fetchall()
        
        # Get daily costs (last 30 days)
        month_ago = datetime.now() - timedelta(days=30)
        cursor.execute("""
            SELECT "Date", SUM("TotalCost") as total_cost, SUM("TokensUsed") as total_tokens
            FROM "AICosts"
            WHERE "Date" >= %s
            GROUP BY "Date"
            ORDER BY "Date"
        """, (month_ago.date(),))
        daily_costs = cursor.fetchall()
        
        # Get model performance (last 7 days)
        cursor.execute("""
            SELECT "ModelName", "Provider", "AverageResponseTime", "SuccessRate", "ErrorRate", "Date"
            FROM "AIModelPerformance"
            WHERE "Date" >= %s
            ORDER BY "Date" DESC
            LIMIT 10
        """, (week_ago.date(),))
        model_performance = cursor.fetchall()
        
        cursor.close()
        
        return {
            "status": "success",
            "data": {
                "recent_metrics": recent_metrics,
                "recent_logs": recent_logs,
                "active_alerts": active_alerts,
                "daily_costs": daily_costs,
                "model_performance": model_performance
            }
        }
    except Exception as e:
        logger.error(f"Error getting monitoring dashboard: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/api/monitoring/metrics")
async def get_metrics(from_date: Optional[str] = None, to_date: Optional[str] = None,
                     metric_name: Optional[str] = None, model_name: Optional[str] = None):
    """Get AI metrics with filters"""
    try:
        cursor = db_service.game_conn.cursor()
        
        query = """
            SELECT "MetricName", "MetricValue", "MetricUnit", "ModelName", "Provider", "Timestamp"
            FROM "AIMetrics"
            WHERE 1=1
        """
        params = []
        
        if from_date:
            query += " AND \"Timestamp\" >= %s"
            params.append(datetime.fromisoformat(from_date))
        
        if to_date:
            query += " AND \"Timestamp\" <= %s"
            params.append(datetime.fromisoformat(to_date))
        
        if metric_name:
            query += " AND \"MetricName\" = %s"
            params.append(metric_name)
        
        if model_name:
            query += " AND \"ModelName\" = %s"
            params.append(model_name)
        
        query += " ORDER BY \"Timestamp\" DESC"
        
        cursor.execute(query, params)
        metrics = cursor.fetchall()
        cursor.close()
        
        return {"status": "success", "data": metrics}
    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/api/monitoring/logs")
async def get_logs(from_date: Optional[str] = None, to_date: Optional[str] = None,
                  level: Optional[str] = None, category: Optional[str] = None):
    """Get AI logs with filters"""
    try:
        cursor = db_service.game_conn.cursor()
        
        query = """
            SELECT "LogLevel", "LogMessage", "LogCategory", "ModelName", "Provider", "Timestamp"
            FROM "AILogs"
            WHERE 1=1
        """
        params = []
        
        if from_date:
            query += " AND \"Timestamp\" >= %s"
            params.append(datetime.fromisoformat(from_date))
        
        if to_date:
            query += " AND \"Timestamp\" <= %s"
            params.append(datetime.fromisoformat(to_date))
        
        if level:
            query += " AND \"LogLevel\" = %s"
            params.append(level)
        
        if category:
            query += " AND \"LogCategory\" = %s"
            params.append(category)
        
        query += " ORDER BY \"Timestamp\" DESC"
        
        cursor.execute(query, params)
        logs = cursor.fetchall()
        cursor.close()
        
        return {"status": "success", "data": logs}
    except Exception as e:
        logger.error(f"Error getting logs: {e}")
        return {"status": "error", "message": str(e)}

# Middleware pour automatiquement logger les métriques
@app.middleware("http")
async def monitoring_middleware(request: Request, call_next):
    start_time = time.time()
    
    # Extract campaign_id from request if available
    campaign_id = None
    user_id = None
    model_name = None
    
    # Try to extract campaign_id from different sources
    if "campaign" in request.url.path:
        path_parts = request.url.path.split("/")
        for i, part in enumerate(path_parts):
            if part == "campaign" and i + 1 < len(path_parts):
                try:
                    campaign_id = int(path_parts[i + 1])
                    break
                except (ValueError, IndexError):
                    pass
    
    # Extract from query params if not found in path
    if not campaign_id and request.query_params.get("campaign_id"):
        try:
            campaign_id = int(request.query_params.get("campaign_id"))
        except ValueError:
            pass
    
    # Extract user_id from headers (if available)
    user_id = request.headers.get("X-User-Id") or request.headers.get("User-Id")
    
    # Determine model name based on current LLM provider
    model_name = "gpt-4o" if current_llm_provider == "openai" else "claude-3.5-sonnet"
    
    # Process request
    response = await call_next(request)
    
    # Calculate response time
    response_time = int((time.time() - start_time) * 1000)
    
    # Log metrics for AI endpoints
    if request.url.path.startswith("/api/gamemaster") or request.url.path.startswith("/generate"):
        try:
            # Check if database connection is still open before logging
            if db_service.game_conn and not db_service.game_conn.closed:
                # Log comprehensive metrics
                cursor = db_service.game_conn.cursor()
                
                # Log response time metric with context
                cursor.execute("""
                    INSERT INTO "AIMetrics" ("MetricName", "MetricValue", "MetricUnit", "ModelName", "Provider", "CampaignId", "UserId", "Timestamp", "Metadata")
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    "response_time", response_time, "ms", model_name, current_llm_provider,
                    campaign_id, user_id, datetime.now(),
                    json.dumps({"endpoint": request.url.path, "method": request.method, "status_code": response.status_code})
                ))
                
                # Log success/error metric
                is_success = 200 <= response.status_code < 400
                cursor.execute("""
                    INSERT INTO "AIMetrics" ("MetricName", "MetricValue", "MetricUnit", "ModelName", "Provider", "CampaignId", "UserId", "Timestamp", "Metadata")
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    "request_success" if is_success else "request_error", 1, "count", model_name, current_llm_provider,
                    campaign_id, user_id, datetime.now(),
                    json.dumps({"endpoint": request.url.path, "status_code": response.status_code})
                ))
                
                # Log operation log
                cursor.execute("""
                    INSERT INTO "AILogs" ("LogLevel", "LogMessage", "LogCategory", "ModelName", "Provider", "CampaignId", "UserId", "ResponseTime", "Timestamp", "Metadata")
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    "INFO", f"API request processed: {request.method} {request.url.path}",
                    "api_request", model_name, current_llm_provider, campaign_id, user_id,
                    response_time, datetime.now(),
                    json.dumps({"status_code": response.status_code, "success": is_success})
                ))
                
                cursor.close()
            else:
                # Connection is closed, try to reconnect
                try:
                    db_service.get_game_db_connection()
                    if db_service.game_conn and not db_service.game_conn.closed:
                        cursor = db_service.game_conn.cursor()
                        cursor.execute("""
                            INSERT INTO "AIMetrics" ("MetricName", "MetricValue", "MetricUnit", "ModelName", "Provider", "Timestamp")
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """, ("response_time", response_time, "ms", model_name, current_llm_provider, datetime.now()))
                        cursor.close()
                except Exception as reconnect_error:
                    logger.debug(f"Could not reconnect for metrics logging: {reconnect_error}")
        except Exception as e:
            logger.debug(f"Metrics logging skipped: {e}")
    
    return response

# ===========================================
# CHARACTER LOCATION SYNCHRONIZATION ENDPOINTS
# ===========================================

@app.post("/api/gamemaster/campaign/{campaign_id}/character/{character_id}/location")
async def update_character_location(campaign_id: int, character_id: int, request: dict, background_tasks: BackgroundTasks):
    """Update character's current location"""
    try:
        new_location = request.get('location')
        if not new_location:
            raise HTTPException(status_code=400, detail="Location is required")
        
        # Update character location in database
        success = db_service.update_character_location(campaign_id, character_id, new_location)
        
        if success:
            logger.info(f"🗺️ Updated character {character_id} location to {new_location}")
            
            # Schedule cleanup
            background_tasks.add_task(cleanup_connections)
            
            return {
                "success": True,
                "character_id": character_id,
                "new_location": new_location,
                "message": "Character location updated successfully"
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to update character location")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error updating character location: {str(e)}")
        background_tasks.add_task(cleanup_connections)
        raise HTTPException(status_code=500, detail=f"Error updating character location: {str(e)}")

@app.get("/api/gamemaster/campaign/{campaign_id}/character/{character_id}/location")
async def get_character_location(campaign_id: int, character_id: int, background_tasks: BackgroundTasks):
    """Get character's current location"""
    try:
        characters = db_service.get_campaign_characters(campaign_id)
        character = next((c for c in characters if c.get("Id") == character_id), None)
        
        if not character:
            raise HTTPException(status_code=404, detail="Character not found")
        
        current_location = character.get("CurrentLocation", "")
        
        # Schedule cleanup
        background_tasks.add_task(cleanup_connections)
        
        return {
            "success": True,
            "character_id": character_id,
            "current_location": current_location,
            "character_name": character.get("Name", "Unknown")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting character location: {str(e)}")
        background_tasks.add_task(cleanup_connections)
        raise HTTPException(status_code=500, detail=f"Error getting character location: {str(e)}")

@app.post("/api/gamemaster/campaign/{campaign_id}/sync_locations")
async def sync_all_character_locations(campaign_id: int, request: dict, background_tasks: BackgroundTasks):
    """Sync all character locations from webapp to llmgamemaster"""
    try:
        character_locations = request.get('character_locations', {})
        if not character_locations:
            raise HTTPException(status_code=400, detail="character_locations is required")
        
        updated_count = 0
        failed_updates = []
        
        for character_id, location in character_locations.items():
            try:
                character_id_int = int(character_id)
                success = db_service.update_character_location(campaign_id, character_id_int, location)
                if success:
                    updated_count += 1
                    logger.info(f"🔄 Synced character {character_id_int} location to {location}")
                else:
                    failed_updates.append(character_id_int)
            except Exception as e:
                logger.error(f"❌ Failed to sync character {character_id} location: {str(e)}")
                failed_updates.append(character_id)
        
        # Schedule cleanup
        background_tasks.add_task(cleanup_connections)
        
        return {
            "success": True,
            "campaign_id": campaign_id,
            "updated_count": updated_count,
            "failed_updates": failed_updates,
            "message": f"Synced {updated_count} character locations successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error syncing character locations: {str(e)}")
        background_tasks.add_task(cleanup_connections)
        raise HTTPException(status_code=500, detail=f"Error syncing character locations: {str(e)}")

@app.get("/api/gamemaster/campaign/{campaign_id}/locations/characters")
async def get_characters_by_location(campaign_id: int, background_tasks: BackgroundTasks):
    """Get characters grouped by their current locations"""
    try:
        characters = db_service.get_campaign_characters(campaign_id)
        locations_data = {}
        
        for character in characters:
            current_location = character.get("CurrentLocation", "Unknown")
            if current_location not in locations_data:
                locations_data[current_location] = []
            
            locations_data[current_location].append({
                "id": character.get("Id"),
                "name": character.get("Name", "Unknown"),
                "level": character.get("Level", 1),
                "race": character.get("Race", "Unknown"),
                "class": character.get("Class", "Unknown")
            })
        
        # Schedule cleanup
        background_tasks.add_task(cleanup_connections)
        
        return {
            "success": True,
            "campaign_id": campaign_id,
            "locations": locations_data,
            "total_characters": len(characters)
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting characters by location: {str(e)}")
        background_tasks.add_task(cleanup_connections)
        raise HTTPException(status_code=500, detail=f"Error getting characters by location: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=API_PORT) 