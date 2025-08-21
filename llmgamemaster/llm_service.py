import os
import logging
import json
from typing import Dict, List, Any, Optional
import openai  # Using older version 0.28.0
from anthropic import Anthropic
from jinja2 import Environment, FileSystemLoader
from config import (
    OPENAI_API_KEY, OPENAI_MODEL, OPENAI_MAX_TOKENS,
    ANTHROPIC_API_KEY, ANTHROPIC_MODEL, ANTHROPIC_MAX_TOKENS,
    LLM_PROVIDER, TEMPLATES_DIR
)

logger = logging.getLogger(__name__)

# Compatibility classes for tests
class OpenAIService:
    """Compatibility class for tests - wraps LLMService"""
    def __init__(self):
        self.llm_service = LLMService()
    
    def __getattr__(self, name):
        return getattr(self.llm_service, name)

class AnthropicService:
    """Compatibility class for tests - wraps LLMService"""
    def __init__(self):
        self.llm_service = LLMService()
    
    def __getattr__(self, name):
        return getattr(self.llm_service, name)

class LLMConfig:
    """Compatibility configuration class for tests"""
    def __init__(self, provider="openai", model="gpt-4o", max_tokens=4000, temperature=0.7):
        self.provider = provider
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature

class LLMResponse:
    """Compatibility response class for tests"""
    def __init__(self, content, usage=None, model="gpt-4o"):
        self.content = content
        self.usage = usage or {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        self.model = model

class LLMService:
    def __init__(self):
        # Set up OpenAI client for older version
        openai.api_key = OPENAI_API_KEY
        
        # Set up Anthropic client (only if API key is provided)
        if ANTHROPIC_API_KEY:
            try:
                self.anthropic = Anthropic(api_key=ANTHROPIC_API_KEY)
            except Exception as e:
                logger.warning(f"Failed to initialize Anthropic client: {e}")
                self.anthropic = None
        else:
            logger.info("No Anthropic API key provided, using OpenAI only")
            self.anthropic = None
        
        # Set up Jinja2 template environment
        self.template_env = Environment(
            loader=FileSystemLoader(TEMPLATES_DIR),
            trim_blocks=True,
            lstrip_blocks=True
        )
    
    def get_template(self, template_name: str) -> Any:
        """Get a Jinja2 template by name"""
        try:
            return self.template_env.get_template(f"{template_name}.jinja2")
        except Exception as e:
            logger.error(f"Error loading template {template_name}: {e}")
            raise
    
    def render_prompt(self, template_name: str, **kwargs) -> str:
        """Render a prompt template with provided context"""
        try:
            template = self.get_template(template_name)
            return template.render(**kwargs)
        except Exception as e:
            logger.error(f"Error rendering template {template_name}: {e}")
            # Fallback to simple prompt if template fails
            return f"You are a D&D Game Master. Please respond to the following: {kwargs.get('message', '')}"
    
    def generate_response(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Generate a response from the LLM based on the prompt"""
        try:
            if LLM_PROVIDER == "anthropic":
                return self._generate_with_anthropic(prompt, system_prompt)
            else:
                return self._generate_with_openai(prompt, system_prompt)
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            # Fallback error message
            return "I'm sorry, I encountered an error while trying to respond. Please try again later."
    
    def _generate_with_openai(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Generate a response using OpenAI's API"""
        import time
        start_time = time.time()
        
        try:
            messages = []
            
            if system_prompt:
                messages.append({
                    "role": "system",
                    "content": system_prompt
                })
            
            messages.append({
                "role": "user",
                "content": prompt
            })
            
            logger.info(f"Sending request to OpenAI with model: {OPENAI_MODEL}")
            
            # Using the OpenAI API 0.28.0 format
            response = openai.ChatCompletion.create(
                model=OPENAI_MODEL,
                messages=messages,
                max_tokens=OPENAI_MAX_TOKENS,
                temperature=0.7,
                top_p=1.0,
                frequency_penalty=0.0,
                presence_penalty=0.0,
            )
            
            # Calculate metrics
            response_time = int((time.time() - start_time) * 1000)
            tokens_used = response.usage.total_tokens if hasattr(response, 'usage') else 0
            
            # Log metrics to database
            try:
                from datetime import datetime
                from app import db_service
                import json
                
                if db_service.game_conn and not db_service.game_conn.closed:
                    cursor = db_service.game_conn.cursor()
                    
                    # Log LLM response time
                    cursor.execute("""
                        INSERT INTO "AIMetrics" ("MetricName", "MetricValue", "MetricUnit", "ModelName", "Provider", "Timestamp", "Metadata")
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        "llm_response_time", response_time, "ms", OPENAI_MODEL, "openai", datetime.now(),
                        json.dumps({"tokens_used": tokens_used, "prompt_length": len(prompt)})
                    ))
                    
                    # Log token usage
                    if tokens_used > 0:
                        cursor.execute("""
                            INSERT INTO "AIMetrics" ("MetricName", "MetricValue", "MetricUnit", "ModelName", "Provider", "Timestamp")
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """, ("tokens_used", tokens_used, "tokens", OPENAI_MODEL, "openai", datetime.now()))
                    
                    # Log successful LLM call
                    cursor.execute("""
                        INSERT INTO "AILogs" ("LogLevel", "LogMessage", "LogCategory", "ModelName", "Provider", "ResponseTime", "TokensUsed", "Timestamp")
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        "INFO", f"OpenAI API call successful - {tokens_used} tokens", "llm_call",
                        OPENAI_MODEL, "openai", response_time, tokens_used, datetime.now()
                    ))
                    
                    cursor.close()
            except Exception as metrics_error:
                logger.debug(f"Could not log LLM metrics: {metrics_error}")
            
            return response.choices[0].message.content
        
        except Exception as e:
            # Log error metrics
            error_response_time = int((time.time() - start_time) * 1000)
            try:
                from datetime import datetime
                from app import db_service
                
                if db_service.game_conn and not db_service.game_conn.closed:
                    cursor = db_service.game_conn.cursor()
                    cursor.execute("""
                        INSERT INTO "AILogs" ("LogLevel", "LogMessage", "LogCategory", "ModelName", "Provider", "ResponseTime", "Timestamp", "StackTrace")
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        "ERROR", f"OpenAI API error: {str(e)}", "llm_error",
                        OPENAI_MODEL, "openai", error_response_time, datetime.now(), str(e)
                    ))
                    cursor.close()
            except Exception as metrics_error:
                logger.debug(f"Could not log error metrics: {metrics_error}")
            
            logger.error(f"OpenAI API error: {e}")
            raise
    
    def _generate_with_anthropic(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Generate a response using Anthropic's API"""
        try:
            logger.info(f"Sending request to Anthropic with model: {ANTHROPIC_MODEL}")
            
            response = self.anthropic.messages.create(
                model=ANTHROPIC_MODEL,
                max_tokens=ANTHROPIC_MAX_TOKENS,
                system=system_prompt if system_prompt else "You are a helpful D&D Game Master assistant.",
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            
            return response.content[0].text
        
        except Exception as e:
            logger.error(f"Anthropic API error: {e}")
            raise
    
    def generate_campaign_intro(self, campaign: Dict, characters: List[Dict], player_name: str, starting_elements: Optional[Dict] = None, present_npcs: Optional[List[Dict]] = None) -> str:
        """Generate a campaign introduction for a new player using campaign_start template"""
        try:
            # ✅ CORRECTION : Utiliser le template campaign_start.jinja2 DIRECTEMENT
            prompt = self.render_prompt(
                "campaign_start",
                campaign=campaign,
                characters=characters,
                player_name=player_name,
                starting_elements=starting_elements or {},
                present_npcs=present_npcs or []
            )
            logger.info(f"[TEMPLATE] Using campaign_start.jinja2 template for campaign {campaign.get('name')}")
            logger.info(f"[TEMPLATE] Starting elements: {starting_elements}")
            
            # Get system prompt
            system_prompt = self.render_prompt(
                "system_prompt",
                campaign=campaign
            )
            # Generate response
            response = self.generate_response(prompt, system_prompt)
            logger.info(f"[TEMPLATE] Generated campaign intro response: {response[:200]}...")
            return response
        except Exception as e:
            logger.error(f"Error generating campaign introduction: {e}")
            return "Welcome to the campaign! I'm your Game Master, and I'll be guiding you through this adventure. Let's begin our journey together!"
            
    def generate_campaign_start(self, campaign: Dict, characters: List[Dict]) -> str:
        """Generate a campaign starting narrative"""
        try:
            # Get prompt template
            prompt = self.render_prompt(
                "narrative_response",
                campaign=campaign,
                characters=characters,
                message_type="campaign_start"
            )
            
            # Get system prompt
            system_prompt = self.render_prompt(
                "system_prompt",
                campaign=campaign
            )
            
            # Generate response
            return self.generate_response(prompt, system_prompt)
        
        except Exception as e:
            logger.error(f"Error generating campaign start: {e}")
            return "I'm sorry, I encountered an error while trying to start the campaign. Please try again later."
            
    def generate_narrative(self, campaign: Dict, characters: List[Dict], 
                           message_history: List[Dict], user_message: str,
                           character: Optional[Dict] = None, 
                           campaign_npcs: Optional[List[Dict]] = None,
                           campaign_locations: Optional[List[Dict]] = None,
                           campaign_quests: Optional[List[Dict]] = None) -> str:
        """Generate a narrative response for the campaign"""
        try:
            logger.info(f"[LLM] generate_narrative called with campaign={campaign}, characters={characters}, user_message={user_message}, character={character}")
            # Get prompt template
            prompt = self.render_prompt(
                "narrative_response",
                campaign=campaign,
                characters=characters,
                message_history=message_history,
                user_message=user_message,
                active_character=character,
                message_type="narrative",
                campaign_npcs=campaign_npcs or [],
                campaign_locations=campaign_locations or [],
                campaign_quests=campaign_quests or []
            )
            logger.info(f"[LLM] Rendered prompt: {prompt}")
            # Get system prompt
            system_prompt = self.render_prompt(
                "system_prompt",
                campaign=campaign
            )
            logger.info(f"[LLM] Rendered system prompt: {system_prompt}")
            # Generate response
            response = self.generate_response(prompt, system_prompt)
            logger.info(f"[LLM] Final LLM response: {response}")
            return response
        except Exception as e:
            logger.error(f"Error generating narrative: {e}")
            return "I'm sorry, I encountered an error while trying to continue the story. Please try again later."
    
    def generate_session_summary(self, campaign: Dict, message_history: List[Dict]) -> str:
        """Generate a summary of the session"""
        try:
            # Get prompt template
            prompt = self.render_prompt(
                "session_summary",
                campaign=campaign,
                message_history=message_history
            )
            
            # Get system prompt
            system_prompt = self.render_prompt(
                "system_prompt",
                campaign=campaign
            )
            
            # Generate response
            return self.generate_response(prompt, system_prompt)
        
        except Exception as e:
            logger.error(f"Error generating session summary: {e}")
            return "The session has concluded. We'll resume our adventure next time!"

    def generate_text(self, prompt: str) -> str:
        """Generate simple text response for general prompts like character descriptions"""
        try:
            logger.info(f"Generating text for prompt: {prompt[:100]}...")
            
            # Use a simple system prompt for general text generation
            system_prompt = "You are a helpful assistant that generates detailed and creative content for D&D games. Provide clear, engaging, and appropriate responses."
            
            return self.generate_response(prompt, system_prompt)
        except Exception as e:
            logger.error(f"Error generating text: {e}")
            return "I'm sorry, I encountered an error while generating the text. Please try again later."

    def generate_character_description(self, campaign: Dict, character: Dict) -> str:
        """Generate a detailed character description using campaign context"""
        try:
            logger.info(f"Generating character description for {character.get('name', 'Unknown')} in campaign {campaign.get('name', 'Unknown')}")
            
            # Get prompt template
            prompt = self.render_prompt(
                "character_description",
                campaign=campaign,
                character=character
            )
            
            logger.info(f"Character description prompt: {prompt[:200]}...")
            
            # Use a specialized system prompt for character descriptions
            system_prompt = "You are an expert D&D character creator and storyteller. Generate rich, immersive character descriptions that fit perfectly within the given campaign setting. Be creative, detailed, and authentic to D&D 5e lore."
            
            return self.generate_response(prompt, system_prompt)
        except Exception as e:
            logger.error(f"Error generating character description: {e}")
            return "A mysterious adventurer whose story has yet to be fully told."

    def generate_character_portrait_prompt(self, campaign: Dict, character: Dict) -> str:
        """Generate a portrait prompt for character image generation"""
        try:
            logger.info(f"Generating portrait prompt for {character.get('name', 'Unknown')}")
            
            # Get prompt template
            prompt = self.render_prompt(
                "character_portrait",
                campaign=campaign,
                character=character
            )
            
            logger.info(f"Portrait prompt: {prompt[:200]}...")
            
            return prompt
        except Exception as e:
            logger.error(f"Error generating portrait prompt: {e}")
            # Fallback to simple prompt
            return f"Fantasy portrait of a {character.get('race', 'Human')} {character.get('class', 'Adventurer')}, {character.get('gender', 'unknown gender')}, with {character.get('background', 'Commoner')} background. Character named {character.get('name', 'Unknown')}. {character.get('alignment', 'Neutral')} alignment. D&D style, fantasy artwork, detailed, high quality."

    def generate_image(self, prompt: str) -> Optional[str]:
        """Generate an image using OpenAI's DALL-E model"""
        try:
            import openai
            
            # Generate image with DALL-E
            response = openai.Image.create(
                prompt=prompt,
                n=1,
                size="512x512"
            )
            
            image_url = response["data"][0]["url"]
            logger.info(f"Successfully generated image: {image_url}")
            return image_url
            
        except Exception as e:
            logger.error(f"Error generating image: {e}")
            return None
    
    async def generate_and_store_image(self, prompt: str, element_type: str, 
                                     element_name: str, element_id: int, 
                                     campaign_id: int = None) -> Optional[str]:
        """
        Générer une image et la stocker localement de manière permanente
        
        Args:
            prompt: Prompt pour DALL-E
            element_type: Type d'élément ('character', 'npc', 'location')
            element_name: Nom de l'élément
            element_id: ID de l'élément en base
            campaign_id: ID de la campagne (optionnel)
            
        Returns:
            Chemin local de l'image stockée ou None si erreur
        """
        try:
            # Générer l'image avec DALL-E (URL temporaire)
            temp_url = self.generate_image(prompt)
            if not temp_url:
                return None
            
            # Stocker l'image localement
            from image_storage_service import store_generated_image
            local_path = await store_generated_image(
                temp_url, element_type, element_name, element_id, campaign_id
            )
            
            if local_path:
                logger.info(f"✅ Image generated and stored: {local_path}")
                return local_path
            else:
                logger.warning(f"Failed to store image locally, returning temp URL: {temp_url}")
                return temp_url  # Fallback vers l'URL temporaire
                
        except Exception as e:
            logger.error(f"Error in generate_and_store_image: {e}")
            return None

def format_campaign_data(campaign):
    """Format campaign data for use in templates"""
    # Rename Setting to Settings if it exists but Settings doesn't
    if campaign.get('Setting') and not campaign.get('Settings'):
        campaign['Settings'] = campaign['Setting']
    
    return {
        'name': campaign.get('Name', 'D&D Adventure'),
        'settings': campaign.get('Settings', ''),
        'description': campaign.get('Description', ''),
        'language': campaign.get('Language', 'English'),
        'level': campaign.get('StartingLevel', 1)
    }

def format_character_data(character):
    """Format character data for use in templates"""
    if not character:
        return None
    
    return {
        'name': character.get('Name', 'Unknown'),
        'race': character.get('Race', 'Human'),
        'class': character.get('Class', 'Adventurer'),
        'gender': character.get('Gender', 'Unknown'),
        'level': character.get('Level', 1),
        'background': character.get('Background', 'Commoner'),
        'alignment': character.get('Alignment', 'Neutral'),
        'strength': character.get('Strength', 10),
        'dexterity': character.get('Dexterity', 10),
        'constitution': character.get('Constitution', 10),
        'intelligence': character.get('Intelligence', 10),
        'wisdom': character.get('Wisdom', 10),
        'charisma': character.get('Charisma', 10),
        'description': character.get('Description', ''),
        'portrait_url': character.get('PortraitUrl', ''),
        'equipment': character.get('Equipment', '')
    } 