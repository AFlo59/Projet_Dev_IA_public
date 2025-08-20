import logging
import json
from typing import Dict, List, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

def setup_logging(log_file: str, log_level: str = "INFO"):
    """Set up logging configuration"""
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {log_level}")
    
    logging.basicConfig(
        level=numeric_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )

def format_campaign_data(campaign: Dict) -> Dict:
    """Format campaign data for prompt templates"""
    # Check if campaign contains Settings field or Setting field
    if 'Settings' in campaign:
        setting = campaign.get("Settings", "Forgotten Realms")
    else:
        setting = campaign.get("Setting", "Forgotten Realms")
        
    return {
        "id": campaign.get("Id"),
        "name": campaign.get("Name", "Unknown Campaign"),
        "description": campaign.get("Description", ""),
        "setting": setting,
        "settings": setting,  # Add both fields for compatibility
        "level": campaign.get("StartingLevel", 1),
        "language": campaign.get("Language", "English"),
        "created_at": format_datetime(campaign.get("CreatedAt")),
        "updated_at": format_datetime(campaign.get("UpdatedAt"))
    }

def format_character_data(character: Dict) -> Dict:
    """Format character data for prompt templates"""
    return {
        "id": character.get("Id"),
        "name": character.get("Name", "Unknown Character"),
        "race": character.get("Race", "Human"),
        "class": character.get("Class", "Fighter"),
        "level": character.get("Level", 1),
        "background": character.get("Background", ""),
        "alignment": character.get("Alignment", "Neutral"),
        "stats": format_character_stats(character.get("Stats", {})),
        "equipment": character.get("Equipment", ""),
        "description": character.get("Description", "")
    }

def format_character_stats(stats: Dict) -> Dict:
    """Format character stats for prompt templates"""
    default_stats = {
        "strength": 10,
        "dexterity": 10,
        "constitution": 10,
        "intelligence": 10,
        "wisdom": 10,
        "charisma": 10,
        "hp": 10,
        "ac": 10
    }
    
    if isinstance(stats, str):
        try:
            parsed_stats = json.loads(stats)
            if isinstance(parsed_stats, dict):
                stats = parsed_stats
            else:
                stats = {}
        except:
            stats = {}
    
    return {**default_stats, **stats}

def format_message_history(messages: List[Dict]) -> List[Dict]:
    """Format message history for prompt templates"""
    formatted_messages = []
    
    for message in messages:
        formatted_messages.append({
            "id": message.get("Id"),
            "type": message.get("MessageType", "user"),
            "content": message.get("Content", ""),
            "user_id": message.get("UserId"),
            "character_id": message.get("CharacterId"),
            "timestamp": format_datetime(message.get("CreatedAt"))
        })
    
    # Reverse to get chronological order (oldest first)
    return list(reversed(formatted_messages))

def format_datetime(dt):
    """Format datetime for prompt templates"""
    if not dt:
        return ""
    
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
        except:
            return dt
    
    return dt.strftime("%Y-%m-%d %H:%M:%S")

def convert_dice_notation(notation: str) -> str:
    """Convert dice notation to descriptive text"""
    import re
    
    # Examples: 2d6+3, 1d20-2
    dice_pattern = re.compile(r'(\d+)d(\d+)([+-]\d+)?')
    
    def replace_dice(match):
        count = int(match.group(1))
        sides = int(match.group(2))
        modifier = match.group(3) or ""
        
        if count == 1:
            return f"a d{sides}{modifier}"
        else:
            return f"{count}d{sides}{modifier}"
    
    return dice_pattern.sub(replace_dice, notation)

def safe_json_loads(json_str: str, default=None) -> Any:
    """Safely load JSON string"""
    if not json_str:
        return default
    
    try:
        return json.loads(json_str)
    except:
        return default 