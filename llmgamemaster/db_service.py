import psycopg2
from psycopg2.extras import RealDictCursor
import logging
from config import (
    SILVER_DB_HOST, SILVER_DB_PORT, SILVER_DB_NAME, DB_READ_USER, DB_READ_PASSWORD,
    GAME_DB_HOST, GAME_DB_PORT, GAME_DB_NAME, GAME_DB_USER, GAME_DB_PASSWORD
)
from datetime import datetime

logger = logging.getLogger(__name__)

class DBService:
    def __init__(self):
        self.silver_conn = None
        self.game_conn = None
    
    def force_reconnect(self):
        """Force close all connections and recreate them"""
        logger.info("Forcing reconnection to databases...")
        
        # Close existing connections
        if self.silver_conn and not self.silver_conn.closed:
            self.silver_conn.close()
            logger.info("Closed Silver database connection")
        
        if self.game_conn and not self.game_conn.closed:
            self.game_conn.close()
            logger.info("Closed Game database connection")
        
        # Reset connection objects
        self.silver_conn = None
        self.game_conn = None
        
        # Recreate connections
        self.get_silver_db_connection()
        self.get_game_db_connection()
        
        logger.info("Database connections recreated successfully")
    
    def get_silver_db_connection(self):
        """Create a connection to the Silver database"""
        if self.silver_conn is None or self.silver_conn.closed:
            try:
                self.silver_conn = psycopg2.connect(
                    host=SILVER_DB_HOST,
                    port=SILVER_DB_PORT,
                    dbname=SILVER_DB_NAME,
                    user=DB_READ_USER,
                    password=DB_READ_PASSWORD,
                    cursor_factory=RealDictCursor
                )
                self.silver_conn.autocommit = True
                logger.info(f"Connected to Silver database at {SILVER_DB_HOST}:{SILVER_DB_PORT}/{SILVER_DB_NAME}")
            except Exception as e:
                logger.error(f"Error connecting to Silver database: {e}")
                raise
        return self.silver_conn
    
    def get_game_db_connection(self):
        """Create a connection to the Game database"""
        if self.game_conn is None or self.game_conn.closed:
            try:
                self.game_conn = psycopg2.connect(
                    host=GAME_DB_HOST,
                    port=GAME_DB_PORT,
                    dbname=GAME_DB_NAME,
                    user=GAME_DB_USER,
                    password=GAME_DB_PASSWORD,
                    cursor_factory=RealDictCursor
                )
                self.game_conn.autocommit = True
                logger.info(f"Connected to Game database at {GAME_DB_HOST}:{GAME_DB_PORT}/{GAME_DB_NAME}")
            except Exception as e:
                logger.error(f"Error connecting to Game database: {e}")
                raise
        return self.game_conn
    
    def close_connections(self):
        """Close all database connections"""
        if self.silver_conn and not self.silver_conn.closed:
            self.silver_conn.close()
            logger.info("Closed Silver database connection")
        
        if self.game_conn and not self.game_conn.closed:
            self.game_conn.close()
            logger.info("Closed Game database connection")
    
    def get_reference_data(self, schema, table, limit=100, search_query=None):
        """Get reference data from Silver database"""
        conn = self.get_silver_db_connection()
        try:
            with conn.cursor() as cur:
                if search_query:
                    # Get text columns for searching
                    cur.execute("""
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_schema = %s
                        AND table_name = %s
                        AND data_type IN ('character varying', 'text')
                    """, (schema, table))
                    
                    text_columns = [row["column_name"] for row in cur.fetchall()]
                    
                    if not text_columns:
                        return []
                    
                    # Build search conditions
                    search_conditions = " OR ".join([f"{col} ILIKE %s" for col in text_columns])
                    search_params = [f"%{search_query}%"] * len(text_columns)
                    
                    query = f"""
                        SELECT *
                        FROM {schema}.{table}
                        WHERE {search_conditions}
                        LIMIT %s
                    """
                    cur.execute(query, search_params + [limit])
                else:
                    query = f"""
                        SELECT *
                        FROM {schema}.{table}
                        LIMIT %s
                    """
                    cur.execute(query, (limit,))
                
                return cur.fetchall()
        except Exception as e:
            logger.error(f"Error retrieving reference data from {schema}.{table}: {e}")
            return []
    
    def get_campaign_data(self, campaign_id):
        """Get campaign data from Game database"""
        conn = self.get_game_db_connection()
        cursor = None
        try:
            cursor = conn.cursor()
            logger.info(f"[DB] Checking existence of Campaigns table...")
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'Campaigns'
                )
            """)
            result = cursor.fetchone()
            logger.info(f"[DB] Table existence result: {result}")
            logger.info(f"[DB] Result type: {type(result)}")
            
            # Handle both RealDictCursor and regular cursor results
            if result is None:
                logger.error("Table existence check returned None")
                return None
            
            # Check if it's a RealDictRow (dict-like) or tuple
            if hasattr(result, 'get'):
                # It's a RealDictRow, use dict access
                table_exists = result.get('exists', False)
            else:
                # It's a tuple, use index access
                table_exists = result[0] if len(result) > 0 else False
            
            logger.info(f"[DB] Table exists: {table_exists}")
            
            if not table_exists:
                logger.error("Table 'Campaigns' does not exist")
                return None
                
            logger.info(f"[DB] Querying campaign with Id={campaign_id}")
            cursor.execute("""
                SELECT *
                FROM "Campaigns"
                WHERE "Id" = %s
            """, (campaign_id,))
            result = cursor.fetchone()
            logger.info(f"[DB] Campaign query result: {result}")
            logger.info(f"[DB] Campaign result type: {type(result)}")
            
            if result is None:
                logger.error(f"Campaign with ID {campaign_id} not found")
                return None
            return result
        except Exception as e:
            logger.error(f"Error retrieving campaign data for campaign_id {campaign_id}: {e}")
            logger.error(f"Exception type: {type(e)}, args: {e.args}")
            return None
        finally:
            if cursor:
                cursor.close()
    
    def get_campaign_characters(self, campaign_id):
        """Get characters for a campaign from Game database"""
        conn = self.get_game_db_connection()
        cursor = None
        try:
            cursor = conn.cursor()
            # Check if tables exist
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'Characters'
                ) AND EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'CampaignCharacters'
                )
            """)
            
            tables_exist = cursor.fetchone()
            logger.info(f"[DB] Characters tables existence result: {tables_exist}, type: {type(tables_exist)}")
            
            # Handle both RealDictCursor and regular cursor results
            if tables_exist is None:
                logger.error("Tables existence check returned None")
                return []
                
            # Check if it's a RealDictRow (dict-like) or tuple
            if hasattr(tables_exist, 'get'):
                # It's a RealDictRow, use dict access
                exist_value = tables_exist.get('?column?', False)  # EXISTS query returns ?column?
            else:
                # It's a tuple, use index access
                exist_value = tables_exist[0] if len(tables_exist) > 0 else False
            
            if not exist_value:
                logger.error("Tables 'Characters' or 'CampaignCharacters' do not exist")
                return []
            
            # Execute query if tables exist
            cursor.execute("""
                SELECT c.*
                FROM "Characters" c
                JOIN "CampaignCharacters" cc ON c."Id" = cc."CharacterId"
                WHERE cc."CampaignId" = %s
            """, (campaign_id,))
            results = cursor.fetchall()
            logger.info(f"[DB] Found {len(results)} characters for campaign {campaign_id}")
            return results
        except Exception as e:
            logger.error(f"Error retrieving characters for campaign_id {campaign_id}: {e}")
            logger.error(f"Exception type: {type(e)}, args: {e.args}")
            return []
        finally:
            if cursor:
                cursor.close()
    
    def get_campaign_messages(self, campaign_id, limit=20):
        """Get message history for a campaign from Game database"""
        conn = self.get_game_db_connection()
        cursor = None
        try:
            cursor = conn.cursor()
            # Check if table exists
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'CampaignMessages'
                )
            """)
            
            result = cursor.fetchone()
            logger.info(f"[DB] CampaignMessages table existence result: {result}, type: {type(result)}")
            
            # Handle both RealDictCursor and regular cursor results
            if result is None:
                logger.error("Table existence check returned None")
                return []
                
            # Check if it's a RealDictRow (dict-like) or tuple
            if hasattr(result, 'get'):
                # It's a RealDictRow, use dict access
                table_exists = result.get('exists', False)
            else:
                # It's a tuple, use index access
                table_exists = result[0] if len(result) > 0 else False
            
            if not table_exists:
                logger.error("Table 'CampaignMessages' does not exist")
                return []
            
            # Check if SentAt column exists
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.columns
                    WHERE table_schema = 'public'
                    AND table_name = 'CampaignMessages'
                    AND column_name = 'SentAt'
                )
            """)
            
            result = cursor.fetchone()
            
            # Handle both RealDictCursor and regular cursor results
            if result is None:
                logger.error("SentAt column existence check returned None")
                return []
                
            if hasattr(result, 'get'):
                sentat_exists = result.get('exists', False)
            else:
                sentat_exists = result[0] if len(result) > 0 else False
            
            # Execute query based on available columns
            if sentat_exists:
                # Use SentAt column for ordering
                cursor.execute("""
                    SELECT *
                    FROM "CampaignMessages"
                    WHERE "CampaignId" = %s
                    ORDER BY "SentAt" DESC
                    LIMIT %s
                """, (campaign_id, limit))
            else:
                # Try CreatedAt or default to Id if neither exists
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.columns
                        WHERE table_schema = 'public'
                        AND table_name = 'CampaignMessages'
                        AND column_name = 'CreatedAt'
                    )
                """)
                result = cursor.fetchone()
                
                if result is None:
                    logger.error("CreatedAt column existence check returned None")
                    return []
                    
                if hasattr(result, 'get'):
                    createdat_exists = result.get('exists', False)
                else:
                    createdat_exists = result[0] if len(result) > 0 else False
                
                if createdat_exists:
                    cursor.execute("""
                        SELECT *
                        FROM "CampaignMessages"
                        WHERE "CampaignId" = %s
                        ORDER BY "CreatedAt" DESC
                        LIMIT %s
                    """, (campaign_id, limit))
                else:
                    # Fallback to Id if no timestamp columns exist
                    cursor.execute("""
                        SELECT *
                        FROM "CampaignMessages"
                        WHERE "CampaignId" = %s
                        ORDER BY "Id" DESC
                        LIMIT %s
                    """, (campaign_id, limit))
            
            results = cursor.fetchall()
            logger.info(f"[DB] Found {len(results)} messages for campaign {campaign_id}")
            return results
        except Exception as e:
            logger.error(f"Error retrieving messages for campaign_id {campaign_id}: {e}")
            logger.error(f"Exception type: {type(e)}, args: {e.args}")
            return []
        finally:
            if cursor:
                cursor.close()
    
    def save_campaign_message(self, campaign_id, message_type, content, user_id=None, character_id=None):
        """Save a campaign message to the database"""
        conn = self.get_game_db_connection()
        cursor = None
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO "CampaignMessages" (
                    "CampaignId", "MessageType", "Content", "UserId", "CharacterId", "SentAt"
                ) VALUES (%s, %s, %s, %s, %s, %s)
            """, (campaign_id, message_type, content, user_id, character_id, datetime.now()))
            
            logger.info(f"Saved campaign message: {message_type} for campaign {campaign_id}")
            return True
        except Exception as e:
            logger.error(f"Error saving campaign message: {e}")
            return False
        finally:
            if cursor:
                cursor.close()
    
    def get_monster_by_name(self, name):
        """Get monster data by name from Silver database"""
        conn = self.get_silver_db_connection()
        cursor = None
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT *
                FROM bestiary.fusion_bestiary
                WHERE name ILIKE %s
                LIMIT 1
            """, (f"%{name}%",))
            result = cursor.fetchone()
            return result
        except Exception as e:
            logger.error(f"Error retrieving monster data for name {name}: {e}")
            return None
        finally:
            if cursor:
                cursor.close()
    
    def get_spell_by_name(self, name):
        """Get spell data by name from Silver database"""
        conn = self.get_silver_db_connection()
        cursor = None
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT *
                FROM spells.fusion_spells
                WHERE name ILIKE %s
                LIMIT 1
            """, (f"%{name}%",))
            result = cursor.fetchone()
            return result
        except Exception as e:
            logger.error(f"Error retrieving spell data for name {name}: {e}")
            return None
        finally:
            if cursor:
                cursor.close()
    
    def update_character_content(self, character_id, description=None, portrait_url=None):
        """Update character description and portrait URL"""
        conn = self.get_game_db_connection()
        cursor = None
        try:
            cursor = conn.cursor()
            
            # Build update query dynamically based on provided parameters
            update_fields = []
            params = []
            
            if description is not None:
                update_fields.append('"Description" = %s')
                params.append(description)
            
            if portrait_url is not None:
                update_fields.append('"PortraitUrl" = %s')
                params.append(portrait_url)
            
            if not update_fields:
                logger.warning("No fields to update for character")
                return None
            
            # Add UpdatedAt field
            update_fields.append('"UpdatedAt" = NOW()')
            
            # Add character_id parameter
            params.append(character_id)
            
            query = f"""
                UPDATE "Characters"
                SET {', '.join(update_fields)}
                WHERE "Id" = %s
                RETURNING "Id", "UpdatedAt"
            """
            
            logger.info(f"[DB] Updating character {character_id} with query: {query}")
            logger.info(f"[DB] Parameters: {params}")
            
            cursor.execute(query, params)
            result = cursor.fetchone()
            
            if result:
                logger.info(f"[DB] Successfully updated character {character_id}")
                return result
            else:
                logger.warning(f"[DB] No character found with ID {character_id}")
                return None
                
        except Exception as e:
            logger.error(f"Error updating character {character_id}: {e}")
            logger.error(f"Exception type: {type(e)}, args: {e.args}")
            return None
        finally:
            if cursor:
                cursor.close()
    
    def update_character_location(self, campaign_id, character_id, location_name):
        """Update character location in a campaign"""
        conn = self.get_game_db_connection()
        cursor = None
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE "CampaignCharacters"
                SET "CurrentLocation" = %s
                WHERE "CampaignId" = %s AND "CharacterId" = %s
                RETURNING "Id"
            """, (location_name, campaign_id, character_id))
            result = cursor.fetchone()
            
            if result:
                conn.commit()  # Commit the transaction immediately
                logger.info(f"[DB] Successfully updated character {character_id} location to {location_name}")
                return result
            else:
                logger.warning(f"[DB] No character found with CampaignId {campaign_id} and CharacterId {character_id}")
                return None
                
        except Exception as e:
            conn.rollback()  # Rollback on error
            logger.error(f"Error updating character {character_id} location: {e}")
            return None
        finally:
            if cursor:
                cursor.close()
    
    def get_character_location(self, campaign_id, character_id):
        """Get the current location of a character in a campaign"""
        conn = self.get_game_db_connection()
        cursor = None
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT "CurrentLocation"
                FROM "CampaignCharacters"
                WHERE "CampaignId" = %s AND "CharacterId" = %s
                LIMIT 1
            """, (campaign_id, character_id))
            result = cursor.fetchone()
            
            if result:
                location = result['CurrentLocation']
                logger.info(f"[DB] Character {character_id} is currently in {location}")
                return location
            else:
                logger.warning(f"[DB] No character found with CampaignId {campaign_id} and CharacterId {character_id}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting character {character_id} location: {e}")
            return None
        finally:
            if cursor:
                cursor.close()
    
    # NPC Management Functions
    def create_campaign_npc(self, campaign_id, name, npc_type, race, **kwargs):
        """Create a new NPC for a campaign"""
        conn = self.get_game_db_connection()
        cursor = None
        try:
            cursor = conn.cursor()
            
            # Build insert query dynamically
            fields = ['"CampaignId"', '"Name"', '"Type"', '"Race"']
            values = [campaign_id, name, npc_type, race]
            placeholders = ['%s', '%s', '%s', '%s']
            
            # Optional fields
            optional_fields = {
                'class': '"Class"',
                'level': '"Level"',
                'max_hit_points': '"MaxHitPoints"',
                'current_hit_points': '"CurrentHitPoints"',
                'armor_class': '"ArmorClass"',
                'strength': '"Strength"',
                'dexterity': '"Dexterity"',
                'constitution': '"Constitution"',
                'intelligence': '"Intelligence"',
                'wisdom': '"Wisdom"',
                'charisma': '"Charisma"',
                'alignment': '"Alignment"',
                'description': '"Description"',
                'current_location': '"CurrentLocation"',
                'status': '"Status"',
                'notes': '"Notes"',
                'portrait_url': '"PortraitUrl"'
            }
            
            for key, field in optional_fields.items():
                if key in kwargs and kwargs[key] is not None:
                    fields.append(field)
                    values.append(kwargs[key])
                    placeholders.append('%s')
            
            query = f"""
                INSERT INTO "CampaignNPCs" ({', '.join(fields)})
                VALUES ({', '.join(placeholders)})
                RETURNING "Id", "CreatedAt"
            """
            
            logger.info(f"[DB] Creating NPC: {name} for campaign {campaign_id}")
            cursor.execute(query, values)
            result = cursor.fetchone()
            
            if result:
                logger.info(f"[DB] Successfully created NPC {name} with ID {result['Id']}")
                return result
            else:
                logger.error(f"[DB] Failed to create NPC {name}")
                return None
                
        except Exception as e:
            logger.error(f"Error creating NPC {name}: {e}")
            return None
        finally:
            if cursor:
                cursor.close()
    
    def get_campaign_npcs(self, campaign_id):
        """Get all NPCs for a campaign"""
        conn = self.get_game_db_connection()
        cursor = None
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT *
                FROM "CampaignNPCs"
                WHERE "CampaignId" = %s
                ORDER BY "CreatedAt" DESC
            """, (campaign_id,))
            results = cursor.fetchall()
            logger.info(f"[DB] Found {len(results)} NPCs for campaign {campaign_id}")
            return results
        except Exception as e:
            logger.error(f"Error retrieving NPCs for campaign {campaign_id}: {e}")
            return []
        finally:
            if cursor:
                cursor.close()
    
    def get_npc_by_name(self, campaign_id, name):
        """Get an NPC by name for a specific campaign"""
        conn = self.get_game_db_connection()
        cursor = None
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT *
                FROM "CampaignNPCs"
                WHERE "CampaignId" = %s AND "Name" ILIKE %s
                LIMIT 1
            """, (campaign_id, f"%{name}%"))
            result = cursor.fetchone()
            return result
        except Exception as e:
            logger.error(f"Error retrieving NPC {name} for campaign {campaign_id}: {e}")
            return None
        finally:
            if cursor:
                cursor.close()
    
    def update_npc(self, npc_id, **kwargs):
        """Update an existing NPC"""
        conn = self.get_game_db_connection()
        cursor = None
        try:
            cursor = conn.cursor()
            
            # Build update query dynamically
            update_fields = []
            params = []
            
            updatable_fields = {
                'name': '"Name"',
                'type': '"Type"',
                'race': '"Race"',
                'class': '"Class"',
                'level': '"Level"',
                'max_hit_points': '"MaxHitPoints"',
                'current_hit_points': '"CurrentHitPoints"',
                'armor_class': '"ArmorClass"',
                'strength': '"Strength"',
                'dexterity': '"Dexterity"',
                'constitution': '"Constitution"',
                'intelligence': '"Intelligence"',
                'wisdom': '"Wisdom"',
                'charisma': '"Charisma"',
                'alignment': '"Alignment"',
                'description': '"Description"',
                'current_location': '"CurrentLocation"',
                'status': '"Status"',
                'notes': '"Notes"',
                'portrait_url': '"PortraitUrl"'
            }
            
            for key, field in updatable_fields.items():
                if key in kwargs and kwargs[key] is not None:
                    update_fields.append(f'{field} = %s')
                    params.append(kwargs[key])
            
            if not update_fields:
                logger.warning("No fields to update for NPC")
                return None
            
            # Add UpdatedAt field
            update_fields.append('"UpdatedAt" = NOW()')
            params.append(npc_id)
            
            query = f"""
                UPDATE "CampaignNPCs"
                SET {', '.join(update_fields)}
                WHERE "Id" = %s
                RETURNING "Id", "UpdatedAt"
            """
            
            cursor.execute(query, params)
            result = cursor.fetchone()
            
            if result:
                logger.info(f"[DB] Successfully updated NPC {npc_id}")
                return result
            else:
                logger.warning(f"[DB] No NPC found with ID {npc_id}")
                return None
                
        except Exception as e:
            logger.error(f"Error updating NPC {npc_id}: {e}")
            return None
        finally:
            if cursor:
                cursor.close()
    
    # Location Management Functions
    def create_campaign_location(self, campaign_id, name, location_type, **kwargs):
        """Create a new location for a campaign"""
        conn = self.get_game_db_connection()
        cursor = None
        try:
            cursor = conn.cursor()
            
            # Build insert query dynamically
            fields = ['"CampaignId"', '"Name"', '"Type"']
            values = [campaign_id, name, location_type]
            placeholders = ['%s', '%s', '%s']
            
            # Optional fields
            optional_fields = {
                'description': '"Description"',
                'short_description': '"ShortDescription"',
                'parent_location_id': '"ParentLocationId"',
                'is_discovered': '"IsDiscovered"',
                'is_accessible': '"IsAccessible"',
                'climate': '"Climate"',
                'terrain': '"Terrain"',
                'population': '"Population"',
                'notes': '"Notes"',
                'image_url': '"ImageUrl"'
            }
            
            for key, field in optional_fields.items():
                if key in kwargs and kwargs[key] is not None:
                    fields.append(field)
                    values.append(kwargs[key])
                    placeholders.append('%s')
            
            query = f"""
                INSERT INTO "CampaignLocations" ({', '.join(fields)})
                VALUES ({', '.join(placeholders)})
                RETURNING "Id", "CreatedAt"
            """
            
            logger.info(f"[DB] Creating location: {name} for campaign {campaign_id}")
            cursor.execute(query, values)
            result = cursor.fetchone()
            
            if result:
                logger.info(f"[DB] Successfully created location {name} with ID {result['Id']}")
                return result
            else:
                logger.error(f"[DB] Failed to create location {name}")
                return None
                
        except Exception as e:
            logger.error(f"Error creating location {name}: {e}")
            return None
        finally:
            if cursor:
                cursor.close()
    
    def get_campaign_locations(self, campaign_id):
        """Get all locations for a campaign"""
        conn = self.get_game_db_connection()
        cursor = None
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT *
                FROM "CampaignLocations"
                WHERE "CampaignId" = %s
                ORDER BY "CreatedAt" DESC
            """, (campaign_id,))
            results = cursor.fetchall()
            logger.info(f"[DB] Found {len(results)} locations for campaign {campaign_id}")
            return results
        except Exception as e:
            logger.error(f"Error retrieving locations for campaign {campaign_id}: {e}")
            return []
        finally:
            if cursor:
                cursor.close()
    
    def get_location_by_name(self, campaign_id, name):
        """Get a location by name for a specific campaign"""
        conn = self.get_game_db_connection()
        cursor = None
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT *
                FROM "CampaignLocations"
                WHERE "CampaignId" = %s AND "Name" ILIKE %s
                LIMIT 1
            """, (campaign_id, f"%{name}%"))
            result = cursor.fetchone()
            return result
        except Exception as e:
            logger.error(f"Error retrieving location {name} for campaign {campaign_id}: {e}")
            return None
        finally:
            if cursor:
                cursor.close()
    
    def update_location(self, location_id, **kwargs):
        """Update an existing location"""
        conn = self.get_game_db_connection()
        cursor = None
        try:
            cursor = conn.cursor()
            
            # Build update query dynamically
            update_fields = []
            params = []
            
            updatable_fields = {
                'name': '"Name"',
                'type': '"Type"',
                'description': '"Description"',
                'short_description': '"ShortDescription"',
                'parent_location_id': '"ParentLocationId"',
                'is_discovered': '"IsDiscovered"',
                'is_accessible': '"IsAccessible"',
                'climate': '"Climate"',
                'terrain': '"Terrain"',
                'population': '"Population"',
                'notes': '"Notes"',
                'image_url': '"ImageUrl"'
            }
            
            for key, field in updatable_fields.items():
                if key in kwargs and kwargs[key] is not None:
                    update_fields.append(f'{field} = %s')
                    params.append(kwargs[key])
            
            if not update_fields:
                logger.warning("No fields to update for location")
                return None
            
            # Add UpdatedAt field
            update_fields.append('"UpdatedAt" = NOW()')
            params.append(location_id)
            
            query = f"""
                UPDATE "CampaignLocations"
                SET {', '.join(update_fields)}
                WHERE "Id" = %s
                RETURNING "Id", "UpdatedAt"
            """
            
            cursor.execute(query, params)
            result = cursor.fetchone()
            
            if result:
                logger.info(f"[DB] Successfully updated location {location_id}")
                return result
            else:
                logger.warning(f"[DB] No location found with ID {location_id}")
                return None
                
        except Exception as e:
            logger.error(f"Error updating location {location_id}: {e}")
            return None
        finally:
            if cursor:
                cursor.close()
    
    # Quest Management Functions
    def create_campaign_quest(self, campaign_id, title, **kwargs):
        """Create a new quest for a campaign"""
        conn = self.get_game_db_connection()
        cursor = None
        try:
            cursor = conn.cursor()
            
            # Build insert query dynamically
            fields = ['"CampaignId"', '"Title"']
            values = [campaign_id, title]
            placeholders = ['%s', '%s']
            
            # Optional fields
            optional_fields = {
                'description': '"Description"',
                'short_description': '"ShortDescription"',
                'type': '"Type"',
                'status': '"Status"',
                'reward': '"Reward"',
                'requirements': '"Requirements"',
                'required_level': '"RequiredLevel"',
                'location_id': '"LocationId"',
                'quest_giver': '"QuestGiver"',
                'difficulty': '"Difficulty"',
                'notes': '"Notes"',
                'progress': '"Progress"'
            }
            
            for key, field in optional_fields.items():
                if key in kwargs and kwargs[key] is not None:
                    fields.append(field)
                    values.append(kwargs[key])
                    placeholders.append('%s')
            
            query = f"""
                INSERT INTO "CampaignQuests" ({', '.join(fields)})
                VALUES ({', '.join(placeholders)})
                RETURNING "Id", "CreatedAt"
            """
            
            logger.info(f"[DB] Creating quest: {title} for campaign {campaign_id}")
            cursor.execute(query, values)
            result = cursor.fetchone()
            
            if result:
                logger.info(f"[DB] Successfully created quest {title} with ID {result['Id']}")
                return result
            else:
                logger.error(f"[DB] Failed to create quest {title}")
                return None
                
        except Exception as e:
            logger.error(f"Error creating quest {title}: {e}")
            return None
        finally:
            if cursor:
                cursor.close()
    
    def get_campaign_quests(self, campaign_id):
        """Get all quests for a campaign"""
        conn = self.get_game_db_connection()
        cursor = None
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT *
                FROM "CampaignQuests"
                WHERE "CampaignId" = %s
                ORDER BY "CreatedAt" DESC
            """, (campaign_id,))
            results = cursor.fetchall()
            logger.info(f"[DB] Found {len(results)} quests for campaign {campaign_id}")
            return results
        except Exception as e:
            logger.error(f"Error retrieving quests for campaign {campaign_id}: {e}")
            return []
        finally:
            if cursor:
                cursor.close()
    
    def get_quest_by_title(self, campaign_id, title):
        """Get a quest by title for a specific campaign"""
        conn = self.get_game_db_connection()
        cursor = None
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT *
                FROM "CampaignQuests"
                WHERE "CampaignId" = %s AND "Title" ILIKE %s
                LIMIT 1
            """, (campaign_id, f"%{title}%"))
            result = cursor.fetchone()
            return result
        except Exception as e:
            logger.error(f"Error retrieving quest {title} for campaign {campaign_id}: {e}")
            return None
        finally:
            if cursor:
                cursor.close()
    
    def update_quest(self, quest_id, **kwargs):
        """Update an existing quest"""
        conn = self.get_game_db_connection()
        cursor = None
        try:
            cursor = conn.cursor()
            
            # Build update query dynamically
            update_fields = []
            params = []
            
            updatable_fields = {
                'title': '"Title"',
                'description': '"Description"',
                'short_description': '"ShortDescription"',
                'type': '"Type"',
                'status': '"Status"',
                'reward': '"Reward"',
                'requirements': '"Requirements"',
                'required_level': '"RequiredLevel"',
                'location_id': '"LocationId"',
                'quest_giver': '"QuestGiver"',
                'difficulty': '"Difficulty"',
                'notes': '"Notes"',
                'progress': '"Progress"'
            }
            
            for key, field in updatable_fields.items():
                if key in kwargs and kwargs[key] is not None:
                    update_fields.append(f'{field} = %s')
                    params.append(kwargs[key])
            
            if not update_fields:
                logger.warning("No fields to update for quest")
                return None
            
            # Add UpdatedAt field and handle CompletedAt if status is 'Completed'
            update_fields.append('"UpdatedAt" = NOW()')
            if 'status' in kwargs and kwargs['status'] == 'Completed':
                update_fields.append('"CompletedAt" = NOW()')
            
            params.append(quest_id)
            
            query = f"""
                UPDATE "CampaignQuests"
                SET {', '.join(update_fields)}
                WHERE "Id" = %s
                RETURNING "Id", "UpdatedAt"
            """
            
            cursor.execute(query, params)
            result = cursor.fetchone()
            
            if result:
                logger.info(f"[DB] Successfully updated quest {quest_id}")
                return result
            else:
                logger.warning(f"[DB] No quest found with ID {quest_id}")
                return None
                
        except Exception as e:
            logger.error(f"Error updating quest {quest_id}: {e}")
            return None
        finally:
            if cursor:
                cursor.close()
    
    def update_campaign_content_status(self, campaign_id: int, status: str, error: str = None):
        """Update campaign content generation status"""
        try:
            conn = self.get_game_db_connection()
            cursor = conn.cursor()
            
            if status == "InProgress":
                query = """
                    UPDATE "Campaigns" 
                    SET "ContentGenerationStatus" = %s, "ContentGenerationStartedAt" = NOW(), "ContentGenerationError" = %s
                    WHERE "Id" = %s
                """
            elif status in ["Completed", "Failed"]:
                query = """
                    UPDATE "Campaigns" 
                    SET "ContentGenerationStatus" = %s, "ContentGenerationCompletedAt" = NOW(), "ContentGenerationError" = %s
                    WHERE "Id" = %s
                """
            else:
                query = """
                    UPDATE "Campaigns" 
                    SET "ContentGenerationStatus" = %s, "ContentGenerationError" = %s
                    WHERE "Id" = %s
                """
            
            cursor.execute(query, (status, error, campaign_id))
            cursor.close()
            conn.close()
            
            logger.info(f"[DB] Updated campaign {campaign_id} content status to {status}")
            return True
        except Exception as e:
            logger.error(f"Error updating campaign content status for campaign {campaign_id}: {str(e)}")
            return False
    
    def update_character_generation_status(self, campaign_id: int, status: str, error: str = None):
        """Update campaign character generation status"""
        try:
            conn = self.get_game_db_connection()
            cursor = conn.cursor()
            
            if status == "InProgress":
                query = """
                    UPDATE "Campaigns" 
                    SET "CharacterGenerationStatus" = %s, "CharacterGenerationStartedAt" = NOW(), "CharacterGenerationError" = %s
                    WHERE "Id" = %s
                """
            elif status in ["Completed", "Failed"]:
                query = """
                    UPDATE "Campaigns" 
                    SET "CharacterGenerationStatus" = %s, "CharacterGenerationCompletedAt" = NOW(), "CharacterGenerationError" = %s
                    WHERE "Id" = %s
                """
            else:
                query = """
                    UPDATE "Campaigns" 
                    SET "CharacterGenerationStatus" = %s, "CharacterGenerationError" = %s
                    WHERE "Id" = %s
                """
            
            cursor.execute(query, (status, error, campaign_id))
            cursor.close()
            conn.close()
            
            logger.info(f"[DB] Updated campaign {campaign_id} character generation status to {status}")
            return True
        except Exception as e:
            logger.error(f"Error updating character generation status for campaign {campaign_id}: {str(e)}")
            return False
    
    # Character Quest Management Functions
    def accept_quest(self, campaign_id: int, character_id: int, quest_id: int, **kwargs):
        """Accept a quest for a character"""
        conn = self.get_game_db_connection()
        cursor = None
        try:
            cursor = conn.cursor()
            
            # Check if quest is already accepted
            cursor.execute("""
                SELECT "Id" FROM "CharacterQuests"
                WHERE "CampaignId" = %s AND "CharacterId" = %s AND "QuestId" = %s
            """, (campaign_id, character_id, quest_id))
            
            if cursor.fetchone():
                logger.warning(f"[DB] Quest {quest_id} already accepted by character {character_id}")
                return None
            
            # Build insert query
            fields = ['"CampaignId"', '"CharacterId"', '"QuestId"']
            values = [campaign_id, character_id, quest_id]
            placeholders = ['%s', '%s', '%s']
            
            # Optional fields
            optional_fields = {
                'status': '"Status"',
                'progress': '"Progress"',
                'notes': '"Notes"'
            }
            
            for key, field in optional_fields.items():
                if key in kwargs and kwargs[key] is not None:
                    fields.append(field)
                    values.append(kwargs[key])
                    placeholders.append('%s')
            
            query = f"""
                INSERT INTO "CharacterQuests" ({', '.join(fields)})
                VALUES ({', '.join(placeholders)})
                RETURNING "Id", "AcceptedAt"
            """
            
            logger.info(f"[DB] Character {character_id} accepting quest {quest_id}")
            cursor.execute(query, values)
            result = cursor.fetchone()
            
            if result:
                logger.info(f"[DB] Successfully accepted quest {quest_id} for character {character_id}")
                return result
            else:
                logger.error(f"[DB] Failed to accept quest {quest_id} for character {character_id}")
                return None
                
        except Exception as e:
            logger.error(f"Error accepting quest {quest_id} for character {character_id}: {e}")
            return None
        finally:
            if cursor:
                cursor.close()
    
    def get_character_quests(self, campaign_id: int, character_id: int):
        """Get all quests for a character"""
        conn = self.get_game_db_connection()
        cursor = None
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT cq.*, q."Title", q."Description", q."Type", q."Difficulty", q."Reward"
                FROM "CharacterQuests" cq
                INNER JOIN "CampaignQuests" q ON cq."QuestId" = q."Id"
                WHERE cq."CampaignId" = %s AND cq."CharacterId" = %s
                ORDER BY cq."AcceptedAt" DESC
            """, (campaign_id, character_id))
            results = cursor.fetchall()
            logger.info(f"[DB] Found {len(results)} quests for character {character_id}")
            return results
        except Exception as e:
            logger.error(f"Error retrieving quests for character {character_id}: {e}")
            return []
        finally:
            if cursor:
                cursor.close()
    
    def update_character_quest(self, character_quest_id: int, **kwargs):
        """Update a character's quest progress"""
        conn = self.get_game_db_connection()
        cursor = None
        try:
            cursor = conn.cursor()
            
            # Build update query dynamically
            update_fields = []
            params = []
            
            updatable_fields = {
                'status': '"Status"',
                'progress': '"Progress"',
                'notes': '"Notes"'
            }
            
            for key, field in updatable_fields.items():
                if key in kwargs and kwargs[key] is not None:
                    update_fields.append(f'{field} = %s')
                    params.append(kwargs[key])
            
            if not update_fields:
                logger.warning("No fields to update for character quest")
                return None
            
            # Handle CompletedAt if status is 'Completed'
            if 'status' in kwargs and kwargs['status'] == 'Completed':
                update_fields.append('"CompletedAt" = NOW()')
            
            params.append(character_quest_id)
            
            query = f"""
                UPDATE "CharacterQuests"
                SET {', '.join(update_fields)}
                WHERE "Id" = %s
                RETURNING "Id", "Status"
            """
            
            cursor.execute(query, params)
            result = cursor.fetchone()
            
            if result:
                logger.info(f"[DB] Successfully updated character quest {character_quest_id}")
                return result
            else:
                logger.warning(f"[DB] No character quest found with ID {character_quest_id}")
                return None
                
        except Exception as e:
            logger.error(f"Error updating character quest {character_quest_id}: {e}")
            return None
        finally:
            if cursor:
                cursor.close() 