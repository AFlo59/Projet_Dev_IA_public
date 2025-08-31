-- Create game database user if it doesn't exist
-- Note: GAME_DB_USER and GAME_DB_PASSWORD are environment variables in the container
DO $$
DECLARE
    game_user text := coalesce(nullif(current_setting('GAME_DB_USER', true), ''), 'gamemaster');
    game_password text := coalesce(nullif(current_setting('GAME_DB_PASSWORD', true), ''), 'GAMEMASTER');
BEGIN
  IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = game_user) THEN
    EXECUTE format('CREATE USER %I WITH PASSWORD %L', game_user, game_password);
    RAISE NOTICE 'User % created successfully', game_user;
  ELSE
    RAISE NOTICE 'User % already exists', game_user;
  END IF;
END
$$;

-- Add tables creation script
CREATE TABLE IF NOT EXISTS "Campaigns" (
    "Id" serial NOT NULL,
    "Name" character varying(100) NOT NULL,
    "Language" character varying(50) NOT NULL DEFAULT 'English',
    "Description" character varying(1000) NULL,
    "Settings" character varying(500) NULL,
    "StartingLevel" integer NOT NULL DEFAULT 1,
    "MaxPlayers" integer NOT NULL DEFAULT 5,
    "IsPublic" boolean NOT NULL DEFAULT false,
    "Status" character varying(20) NOT NULL DEFAULT 'Active',
    "ContentGenerationStatus" character varying(20) NOT NULL DEFAULT 'NotStarted',
    "ContentGenerationStartedAt" timestamp with time zone NULL,
    "ContentGenerationCompletedAt" timestamp with time zone NULL,
    "ContentGenerationError" character varying(1000) NULL,
    "CharacterGenerationStatus" character varying(20) NOT NULL DEFAULT 'NotStarted',
    "CharacterGenerationStartedAt" timestamp with time zone NULL,
    "CharacterGenerationCompletedAt" timestamp with time zone NULL,
    "CharacterGenerationError" character varying(1000) NULL,
    "CreatedAt" timestamp with time zone NOT NULL DEFAULT now(),
    "UpdatedAt" timestamp with time zone NULL,
    "OwnerId" text NOT NULL,
    CONSTRAINT "PK_Campaigns" PRIMARY KEY ("Id")
);

CREATE TABLE IF NOT EXISTS "Characters" (
    "Id" serial NOT NULL,
    "Name" character varying(100) NOT NULL,
    "Race" character varying(50) NOT NULL,
    "Gender" character varying(20) NULL,
    "Class" character varying(50) NOT NULL,
    "Level" integer NOT NULL DEFAULT 1,
    "Alignment" character varying(20) NULL,
    "Background" character varying(50) NULL,
    "Strength" integer NOT NULL DEFAULT 10,
    "Dexterity" integer NOT NULL DEFAULT 10,
    "Constitution" integer NOT NULL DEFAULT 10,
    "Intelligence" integer NOT NULL DEFAULT 10,
    "Wisdom" integer NOT NULL DEFAULT 10,
    "Charisma" integer NOT NULL DEFAULT 10,
    "Description" text NULL,
    "PhysicalAppearance" character varying(1000) NULL,
    "Equipment" text NULL,
    "PortraitUrl" text NULL,
    "CreatedAt" timestamp with time zone NOT NULL DEFAULT now(),
    "UpdatedAt" timestamp with time zone NULL,
    "UserId" text NOT NULL,
    CONSTRAINT "PK_Characters" PRIMARY KEY ("Id")
);

CREATE TABLE IF NOT EXISTS "CampaignCharacters" (
    "Id" serial NOT NULL,
    "CampaignId" integer NOT NULL,
    "CharacterId" integer NOT NULL,
    "IsActive" boolean NOT NULL DEFAULT true,
    "CurrentLocationId" integer NULL,
    "CurrentLocation" character varying(100) NULL,
    "JoinedAt" timestamp with time zone NOT NULL DEFAULT now(),
    CONSTRAINT "PK_CampaignCharacters" PRIMARY KEY ("Id")
);


CREATE TABLE IF NOT EXISTS "CampaignSessions" (
    "Id" serial NOT NULL,
    "CampaignId" integer NOT NULL,
    "Name" character varying(100) NULL,
    "Description" text NULL,
    "Status" character varying(20) NULL DEFAULT 'Scheduled',
    "Summary" text NULL,
    "StartedAt" timestamp with time zone NOT NULL DEFAULT now(),
    "EndedAt" timestamp with time zone NULL,
    CONSTRAINT "PK_CampaignSessions" PRIMARY KEY ("Id")
);

CREATE TABLE IF NOT EXISTS "CampaignMessages" (
    "Id" serial NOT NULL,
    "CampaignId" integer NOT NULL,
    "SessionId" integer NULL,
    "CharacterId" integer NULL,
    "MessageType" character varying(20) NOT NULL,
    "Content" text NOT NULL,
    "SentAt" timestamp with time zone NOT NULL DEFAULT now(),
    "UserId" text NULL,
    CONSTRAINT "PK_CampaignMessages" PRIMARY KEY ("Id")
);

-- The AspNetUsers foreign key constraints will be added by EF Core migrations
-- when the application runs. We're not adding them here to avoid dependency issues.

ALTER TABLE "CampaignCharacters" 
ADD CONSTRAINT "FK_CampaignCharacters_Campaigns_CampaignId" 
FOREIGN KEY ("CampaignId") REFERENCES "Campaigns" ("Id") ON DELETE CASCADE;

ALTER TABLE "CampaignCharacters" 
ADD CONSTRAINT "FK_CampaignCharacters_Characters_CharacterId" 
FOREIGN KEY ("CharacterId") REFERENCES "Characters" ("Id") ON DELETE CASCADE;

-- Add foreign key constraint for CurrentLocationId (after CampaignLocations table is created)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_tables WHERE tablename = 'CampaignLocations') THEN
        IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'FK_CampaignCharacters_CampaignLocations_CurrentLocationId') THEN
            ALTER TABLE "CampaignCharacters" 
            ADD CONSTRAINT "FK_CampaignCharacters_CampaignLocations_CurrentLocationId" 
            FOREIGN KEY ("CurrentLocationId") REFERENCES "CampaignLocations" ("Id") ON DELETE SET NULL;
        END IF;
    END IF;
END
$$;

ALTER TABLE "CampaignSessions" 
ADD CONSTRAINT "FK_CampaignSessions_Campaigns_CampaignId" 
FOREIGN KEY ("CampaignId") REFERENCES "Campaigns" ("Id") ON DELETE CASCADE;

ALTER TABLE "CampaignMessages" 
ADD CONSTRAINT "FK_CampaignMessages_Campaigns_CampaignId" 
FOREIGN KEY ("CampaignId") REFERENCES "Campaigns" ("Id") ON DELETE CASCADE;

ALTER TABLE "CampaignMessages" 
ADD CONSTRAINT "FK_CampaignMessages_CampaignSessions_SessionId" 
FOREIGN KEY ("SessionId") REFERENCES "CampaignSessions" ("Id") ON DELETE SET NULL;

ALTER TABLE "CampaignMessages" 
ADD CONSTRAINT "FK_CampaignMessages_Characters_CharacterId" 
FOREIGN KEY ("CharacterId") REFERENCES "Characters" ("Id") ON DELETE SET NULL;

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS "IX_Campaigns_OwnerId" ON "Campaigns" ("OwnerId");
CREATE INDEX IF NOT EXISTS "IX_Characters_UserId" ON "Characters" ("UserId");
CREATE UNIQUE INDEX IF NOT EXISTS "IX_CampaignCharacters_CampaignId_CharacterId" ON "CampaignCharacters" ("CampaignId", "CharacterId");
CREATE INDEX IF NOT EXISTS "IX_CampaignCharacters_CharacterId" ON "CampaignCharacters" ("CharacterId");
CREATE INDEX IF NOT EXISTS "IX_CampaignCharacters_CurrentLocationId" ON "CampaignCharacters" ("CurrentLocationId");
CREATE INDEX IF NOT EXISTS "IX_CampaignSessions_CampaignId" ON "CampaignSessions" ("CampaignId");
CREATE INDEX IF NOT EXISTS "IX_CampaignMessages_CampaignId" ON "CampaignMessages" ("CampaignId");
CREATE INDEX IF NOT EXISTS "IX_CampaignMessages_SessionId" ON "CampaignMessages" ("SessionId");
CREATE INDEX IF NOT EXISTS "IX_CampaignMessages_CharacterId" ON "CampaignMessages" ("CharacterId");

-- Clean up duplicate characters in campaigns (keep only the first one for each user per campaign)
DO $$
DECLARE
    duplicate_record RECORD;
BEGIN
    -- Find and remove duplicate characters (keep the one with the lowest Id)
    FOR duplicate_record IN 
        SELECT cc1."Id" as duplicate_id
        FROM "CampaignCharacters" cc1
        INNER JOIN "Characters" c1 ON cc1."CharacterId" = c1."Id"
        WHERE EXISTS (
            SELECT 1 
            FROM "CampaignCharacters" cc2
            INNER JOIN "Characters" c2 ON cc2."CharacterId" = c2."Id"
            WHERE cc2."CampaignId" = cc1."CampaignId" 
            AND c2."UserId" = c1."UserId"
            AND cc2."Id" < cc1."Id"
        )
    LOOP
        DELETE FROM "CampaignCharacters" WHERE "Id" = duplicate_record.duplicate_id;
        RAISE NOTICE 'Removed duplicate CampaignCharacter with Id: %', duplicate_record.duplicate_id;
    END LOOP;
END
$$;

-- Grant connection privileges to the current database
DO $$
DECLARE
  current_db TEXT;
  game_user text := coalesce(nullif(current_setting('GAME_DB_USER', true), ''), 'gamemaster');
BEGIN
  SELECT current_database() INTO current_db;
  EXECUTE format('GRANT CONNECT ON DATABASE %I TO %I', current_db, game_user);
END
$$;

-- Create public schema if it doesn't exist
CREATE SCHEMA IF NOT EXISTS public;

-- Create new game tables for LLM GameMaster
CREATE TABLE IF NOT EXISTS "CampaignNPCs" (
    "Id" serial NOT NULL,
    "CampaignId" integer NOT NULL,
    "Name" character varying(100) NOT NULL,
    "Type" character varying(50) NOT NULL DEFAULT 'Humanoid',
    "Race" character varying(50) NOT NULL,
    "Class" character varying(50) NULL,
    "Level" integer NOT NULL DEFAULT 1,
    "MaxHitPoints" integer NOT NULL DEFAULT 10,
    "CurrentHitPoints" integer NOT NULL DEFAULT 10,
    "ArmorClass" integer NOT NULL DEFAULT 10,
    "Strength" integer NOT NULL DEFAULT 10,
    "Dexterity" integer NOT NULL DEFAULT 10,
    "Constitution" integer NOT NULL DEFAULT 10,
    "Intelligence" integer NOT NULL DEFAULT 10,
    "Wisdom" integer NOT NULL DEFAULT 10,
    "Charisma" integer NOT NULL DEFAULT 10,
    "Alignment" character varying(50) NULL,
    "Description" character varying(2000) NULL,
    "CurrentLocationId" integer NULL,
    "CurrentLocation" character varying(100) NULL,
    "Status" character varying(20) NOT NULL DEFAULT 'Active',
    "Notes" character varying(500) NULL,
    "PortraitUrl" character varying(1000) NULL,
    "CreatedAt" timestamp with time zone NOT NULL DEFAULT now(),
    "UpdatedAt" timestamp with time zone NULL,
    CONSTRAINT "PK_CampaignNPCs" PRIMARY KEY ("Id")
);

CREATE TABLE IF NOT EXISTS "CampaignLocations" (
    "Id" serial NOT NULL,
    "CampaignId" integer NOT NULL,
    "Name" character varying(100) NOT NULL,
    "Type" character varying(50) NOT NULL DEFAULT 'Location',
    "Description" character varying(2000) NULL,
    "ShortDescription" character varying(500) NULL,
    "ParentLocationId" integer NULL,
    "IsDiscovered" boolean NOT NULL DEFAULT false,
    "IsAccessible" boolean NOT NULL DEFAULT true,
    "Climate" character varying(50) NULL,
    "Terrain" character varying(50) NULL,
    "Population" character varying(50) NULL,
    "Notes" character varying(1000) NULL,
    "ImageUrl" character varying(1000) NULL,
    "CreatedAt" timestamp with time zone NOT NULL DEFAULT now(),
    "UpdatedAt" timestamp with time zone NULL,
    CONSTRAINT "PK_CampaignLocations" PRIMARY KEY ("Id")
);

CREATE TABLE IF NOT EXISTS "CampaignQuests" (
    "Id" serial NOT NULL,
    "CampaignId" integer NOT NULL,
    "Title" character varying(200) NOT NULL,
    "Description" character varying(2000) NULL,
    "ShortDescription" character varying(500) NULL,
    "Type" character varying(50) NOT NULL DEFAULT 'Side',
    "Status" character varying(50) NOT NULL DEFAULT 'Available',
    "Reward" character varying(500) NULL,
    "Requirements" character varying(500) NULL,
    "RequiredLevel" integer NULL,
    "LocationId" integer NULL,
    "QuestGiver" character varying(100) NULL,
    "Difficulty" character varying(50) NULL,
    "Notes" character varying(1000) NULL,
    "Progress" character varying(1000) NULL,
    "CreatedAt" timestamp with time zone NOT NULL DEFAULT now(),
    "UpdatedAt" timestamp with time zone NULL,
    "CompletedAt" timestamp with time zone NULL,
    CONSTRAINT "PK_CampaignQuests" PRIMARY KEY ("Id")
);

-- Table pour les quêtes acceptées par les personnages
CREATE TABLE IF NOT EXISTS "CharacterQuests" (
    "Id" serial NOT NULL,
    "CampaignId" integer NOT NULL,
    "CharacterId" integer NOT NULL,
    "QuestId" integer NOT NULL,
    "Status" character varying(50) NOT NULL DEFAULT 'Accepted',
    "AcceptedAt" timestamp with time zone NOT NULL DEFAULT now(),
    "CompletedAt" timestamp with time zone NULL,
    "Progress" character varying(1000) NULL,
    "Notes" character varying(1000) NULL,
    CONSTRAINT "PK_CharacterQuests" PRIMARY KEY ("Id")
);

-- Add foreign key constraints for new tables
ALTER TABLE "CampaignNPCs" 
ADD CONSTRAINT "FK_CampaignNPCs_Campaigns_CampaignId" 
FOREIGN KEY ("CampaignId") REFERENCES "Campaigns" ("Id") ON DELETE CASCADE;

-- Add foreign key constraint for CurrentLocationId
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'FK_CampaignNPCs_CampaignLocations_CurrentLocationId') THEN
        ALTER TABLE "CampaignNPCs" 
        ADD CONSTRAINT "FK_CampaignNPCs_CampaignLocations_CurrentLocationId" 
        FOREIGN KEY ("CurrentLocationId") REFERENCES "CampaignLocations" ("Id") ON DELETE SET NULL;
    END IF;
END
$$;

ALTER TABLE "CampaignLocations" 
ADD CONSTRAINT "FK_CampaignLocations_Campaigns_CampaignId" 
FOREIGN KEY ("CampaignId") REFERENCES "Campaigns" ("Id") ON DELETE CASCADE;

ALTER TABLE "CampaignLocations" 
ADD CONSTRAINT "FK_CampaignLocations_CampaignLocations_ParentLocationId" 
FOREIGN KEY ("ParentLocationId") REFERENCES "CampaignLocations" ("Id") ON DELETE SET NULL;

ALTER TABLE "CampaignQuests" 
ADD CONSTRAINT "FK_CampaignQuests_Campaigns_CampaignId" 
FOREIGN KEY ("CampaignId") REFERENCES "Campaigns" ("Id") ON DELETE CASCADE;

ALTER TABLE "CampaignQuests" 
ADD CONSTRAINT "FK_CampaignQuests_CampaignLocations_LocationId" 
FOREIGN KEY ("LocationId") REFERENCES "CampaignLocations" ("Id") ON DELETE SET NULL;

-- Add foreign key constraints for CharacterQuests
ALTER TABLE "CharacterQuests" 
ADD CONSTRAINT "FK_CharacterQuests_Campaigns_CampaignId" 
FOREIGN KEY ("CampaignId") REFERENCES "Campaigns" ("Id") ON DELETE CASCADE;

ALTER TABLE "CharacterQuests" 
ADD CONSTRAINT "FK_CharacterQuests_Characters_CharacterId" 
FOREIGN KEY ("CharacterId") REFERENCES "Characters" ("Id") ON DELETE CASCADE;

ALTER TABLE "CharacterQuests" 
ADD CONSTRAINT "FK_CharacterQuests_CampaignQuests_QuestId" 
FOREIGN KEY ("QuestId") REFERENCES "CampaignQuests" ("Id") ON DELETE CASCADE;

-- Create indexes for new tables
CREATE INDEX IF NOT EXISTS "IX_CampaignNPCs_CampaignId" ON "CampaignNPCs" ("CampaignId");
CREATE INDEX IF NOT EXISTS "IX_CampaignNPCs_Status" ON "CampaignNPCs" ("Status");
CREATE INDEX IF NOT EXISTS "IX_CampaignNPCs_CurrentLocationId" ON "CampaignNPCs" ("CurrentLocationId");
CREATE INDEX IF NOT EXISTS "IX_CampaignLocations_CampaignId" ON "CampaignLocations" ("CampaignId");
CREATE INDEX IF NOT EXISTS "IX_CampaignLocations_ParentLocationId" ON "CampaignLocations" ("ParentLocationId");
CREATE INDEX IF NOT EXISTS "IX_CampaignQuests_CampaignId" ON "CampaignQuests" ("CampaignId");
CREATE INDEX IF NOT EXISTS "IX_CampaignQuests_LocationId" ON "CampaignQuests" ("LocationId");
CREATE INDEX IF NOT EXISTS "IX_CampaignQuests_Status" ON "CampaignQuests" ("Status");

-- Create indexes for CharacterQuests
CREATE INDEX IF NOT EXISTS "IX_CharacterQuests_CampaignId" ON "CharacterQuests" ("CampaignId");
CREATE INDEX IF NOT EXISTS "IX_CharacterQuests_CharacterId" ON "CharacterQuests" ("CharacterId");
CREATE INDEX IF NOT EXISTS "IX_CharacterQuests_QuestId" ON "CharacterQuests" ("QuestId");
CREATE INDEX IF NOT EXISTS "IX_CharacterQuests_Status" ON "CharacterQuests" ("Status");

-- Add constraints for CampaignNPCs statistics and hit points
DO $$
BEGIN
    -- MaxHitPoints constraint
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'CK_CampaignNPCs_MaxHitPoints') THEN
        ALTER TABLE "CampaignNPCs" ADD CONSTRAINT "CK_CampaignNPCs_MaxHitPoints" 
        CHECK ("MaxHitPoints" >= 1 AND "MaxHitPoints" <= 1000);
    END IF;
    
    -- CurrentHitPoints constraint
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'CK_CampaignNPCs_CurrentHitPoints') THEN
        ALTER TABLE "CampaignNPCs" ADD CONSTRAINT "CK_CampaignNPCs_CurrentHitPoints" 
        CHECK ("CurrentHitPoints" >= 0 AND "CurrentHitPoints" <= 1000);
    END IF;
    
    -- CurrentHitPoints not greater than MaxHitPoints constraint
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'CK_CampaignNPCs_CurrentHitPoints_Not_Greater_Than_Max') THEN
        ALTER TABLE "CampaignNPCs" ADD CONSTRAINT "CK_CampaignNPCs_CurrentHitPoints_Not_Greater_Than_Max" 
        CHECK ("CurrentHitPoints" <= "MaxHitPoints");
    END IF;
    
    -- Strength constraint
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'CK_CampaignNPCs_Strength') THEN
        ALTER TABLE "CampaignNPCs" ADD CONSTRAINT "CK_CampaignNPCs_Strength" 
        CHECK ("Strength" >= 1 AND "Strength" <= 30);
    END IF;
    
    -- Dexterity constraint
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'CK_CampaignNPCs_Dexterity') THEN
        ALTER TABLE "CampaignNPCs" ADD CONSTRAINT "CK_CampaignNPCs_Dexterity" 
        CHECK ("Dexterity" >= 1 AND "Dexterity" <= 30);
    END IF;
    
    -- Constitution constraint
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'CK_CampaignNPCs_Constitution') THEN
        ALTER TABLE "CampaignNPCs" ADD CONSTRAINT "CK_CampaignNPCs_Constitution" 
        CHECK ("Constitution" >= 1 AND "Constitution" <= 30);
    END IF;
    
    -- Intelligence constraint
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'CK_CampaignNPCs_Intelligence') THEN
        ALTER TABLE "CampaignNPCs" ADD CONSTRAINT "CK_CampaignNPCs_Intelligence" 
        CHECK ("Intelligence" >= 1 AND "Intelligence" <= 30);
    END IF;
    
    -- Wisdom constraint
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'CK_CampaignNPCs_Wisdom') THEN
        ALTER TABLE "CampaignNPCs" ADD CONSTRAINT "CK_CampaignNPCs_Wisdom" 
        CHECK ("Wisdom" >= 1 AND "Wisdom" <= 30);
    END IF;
    
    -- Charisma constraint
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'CK_CampaignNPCs_Charisma') THEN
        ALTER TABLE "CampaignNPCs" ADD CONSTRAINT "CK_CampaignNPCs_Charisma" 
        CHECK ("Charisma" >= 1 AND "Charisma" <= 30);
    END IF;
END $$;

-- Grant schema usage privileges
DO $$
DECLARE
    game_user text := coalesce(nullif(current_setting('GAME_DB_USER', true), ''), 'gamemaster');
BEGIN
    EXECUTE format('GRANT USAGE ON SCHEMA public TO %I', game_user);
END
$$;

-- SUPPRIMER d'abord toutes les permissions par défaut
-- Ceci est essentiel pour éviter que l'utilisateur de jeu hérite des permissions
DO $$
DECLARE
    admin_user text := coalesce(nullif(current_setting('POSTGRES_USER', true), ''), current_user);
    game_user text := coalesce(nullif(current_setting('GAME_DB_USER', true), ''), 'gamemaster');
BEGIN
  -- Révoquer tous les privilèges par défaut
  EXECUTE format('ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA public REVOKE ALL ON TABLES FROM %I', admin_user, game_user);
  EXECUTE format('ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA public REVOKE ALL ON SEQUENCES FROM %I', admin_user, game_user);
  EXECUTE format('ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA public REVOKE ALL ON FUNCTIONS FROM %I', admin_user, game_user);
END
$$;

-- RÉVOQUER toutes les permissions sur TOUTES les tables existantes
DO $$
DECLARE
  t_name text;
  game_user text := coalesce(nullif(current_setting('GAME_DB_USER', true), ''), 'gamemaster');
BEGIN
  FOR t_name IN SELECT tablename FROM pg_tables WHERE schemaname = 'public'
  LOOP
    EXECUTE format('REVOKE ALL PRIVILEGES ON TABLE %I FROM %I', t_name, game_user);
  END LOOP;
END
$$;

-- Donner les permissions UNIQUEMENT sur les tables spécifiques de jeu
DO $$
DECLARE
    game_user text := coalesce(nullif(current_setting('GAME_DB_USER', true), ''), 'gamemaster');
BEGIN
    EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE "Campaigns" TO %I', game_user);
    EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE "Characters" TO %I', game_user);
    EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE "CampaignCharacters" TO %I', game_user);
    EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE "CampaignSessions" TO %I', game_user);
    EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE "CampaignMessages" TO %I', game_user);
    EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE "CampaignNPCs" TO %I', game_user);
    EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE "CampaignLocations" TO %I', game_user);
    EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE "CampaignQuests" TO %I', game_user);
    EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE "CharacterQuests" TO %I', game_user);
END
$$;

-- UNIQUEMENT accès minimal requis à AspNetUsers (seulement pour les champs nécessaires)
-- Cela est nécessaire car les tables de jeu ont des références vers l'utilisateur
DO $$
DECLARE
    game_user text := coalesce(nullif(current_setting('GAME_DB_USER', true), ''), 'gamemaster');
BEGIN
  IF EXISTS (SELECT 1 FROM pg_tables WHERE tablename = 'AspNetUsers') THEN
    EXECUTE format('GRANT SELECT (Id, UserName) ON TABLE "AspNetUsers" TO %I', game_user);
  END IF;
END
$$;

-- S'assurer que l'utilisateur de jeu a accès aux séquences des tables de jeu uniquement
DO $$
DECLARE
    game_user text := coalesce(nullif(current_setting('GAME_DB_USER', true), ''), 'gamemaster');
BEGIN
    EXECUTE format('GRANT USAGE, SELECT ON SEQUENCE "Campaigns_Id_seq" TO %I', game_user);
    EXECUTE format('GRANT USAGE, SELECT ON SEQUENCE "Characters_Id_seq" TO %I', game_user);
    EXECUTE format('GRANT USAGE, SELECT ON SEQUENCE "CampaignCharacters_Id_seq" TO %I', game_user);
    EXECUTE format('GRANT USAGE, SELECT ON SEQUENCE "CampaignSessions_Id_seq" TO %I', game_user);
    EXECUTE format('GRANT USAGE, SELECT ON SEQUENCE "CampaignMessages_Id_seq" TO %I', game_user);
    EXECUTE format('GRANT USAGE, SELECT ON SEQUENCE "CampaignNPCs_Id_seq" TO %I', game_user);
    EXECUTE format('GRANT USAGE, SELECT ON SEQUENCE "CampaignLocations_Id_seq" TO %I', game_user);
    EXECUTE format('GRANT USAGE, SELECT ON SEQUENCE "CampaignQuests_Id_seq" TO %I', game_user);
    EXECUTE format('GRANT USAGE, SELECT ON SEQUENCE "CharacterQuests_Id_seq" TO %I', game_user);
END
$$;

-- Fonction pour gérer automatiquement les privilèges uniquement sur les tables de jeu
CREATE OR REPLACE FUNCTION manage_game_user_privileges() 
RETURNS event_trigger AS $$
DECLARE
    obj record;
    table_name text;
    is_game_table boolean;
    game_user text := coalesce(nullif(current_setting('GAME_DB_USER', true), ''), 'gamemaster');
BEGIN
    FOR obj IN SELECT * FROM pg_event_trigger_ddl_commands() WHERE command_tag = 'CREATE TABLE' LOOP
        -- Extraire le nom de la table sans les guillemets
        table_name := regexp_replace(obj.object_identity, '^"?([^"]*)"?$', '\1');
        
        -- Vérifier si c'est une table de jeu
        is_game_table := 
            table_name LIKE '%Campaigns' OR 
            table_name LIKE '%Characters' OR 
            table_name LIKE '%CampaignCharacters' OR
            table_name LIKE '%CampaignSessions' OR
            table_name LIKE '%CampaignMessages' OR
            table_name LIKE '%CampaignNPCs' OR
            table_name LIKE '%CampaignLocations' OR
            table_name LIKE '%CampaignQuests';
            
        -- Vérifier si c'est une table ASP.NET Identity ou une table de référence
        IF table_name LIKE 'AspNet%' OR table_name = '__EFMigrationsHistory' OR table_name LIKE 'import_tracking' THEN
            -- Pour les tables AspNet* et de suivi, révoquer explicitement tous les privilèges
            EXECUTE format('REVOKE ALL PRIVILEGES ON TABLE %s FROM %I', obj.object_identity, game_user);
            RAISE NOTICE 'Revoked ALL permissions from % on system table %', game_user, obj.object_identity;
        ELSIF is_game_table THEN
            -- Pour les tables de jeu, accorder les privilèges appropriés
            EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE %s TO %I', obj.object_identity, game_user);
            RAISE NOTICE 'Granted permissions to % on game table %', game_user, obj.object_identity;
        ELSIF table_name LIKE 'AI%' THEN
            -- 🔒 Pour les tables de monitoring IA, permissions restreintes
            IF table_name = 'AIAlertThresholds' THEN
                EXECUTE format('GRANT SELECT ON TABLE %s TO %I', obj.object_identity, game_user);
                RAISE NOTICE 'Granted READ-ONLY permissions to % on monitoring table %', game_user, obj.object_identity;
            ELSIF table_name = 'AIModelPerformance' THEN
                EXECUTE format('GRANT SELECT, INSERT, UPDATE ON TABLE %s TO %I', obj.object_identity, game_user);
                RAISE NOTICE 'Granted SELECT/INSERT/UPDATE permissions to % on performance table %', game_user, obj.object_identity;
            ELSE
                EXECUTE format('GRANT SELECT, INSERT ON TABLE %s TO %I', obj.object_identity, game_user);
                RAISE NOTICE 'Granted SELECT/INSERT permissions to % on monitoring table %', game_user, obj.object_identity;
            END IF;
        ELSE
            -- Pour toutes les autres tables (tables de référence), révoquer par défaut
            EXECUTE format('REVOKE ALL PRIVILEGES ON TABLE %s FROM %I', obj.object_identity, game_user);
            RAISE NOTICE 'Revoked ALL permissions from % on reference table %', game_user, obj.object_identity;
        END IF;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- Créer le trigger d'événement
DROP EVENT TRIGGER IF EXISTS gamemaster_privileges_trigger;
CREATE EVENT TRIGGER gamemaster_privileges_trigger ON ddl_command_end
WHEN TAG IN ('CREATE TABLE')
EXECUTE FUNCTION manage_game_user_privileges(); 

-- ===========================================
-- TABLES DE MONITORING IA (E5 - Débogage + Monitoring)
-- ===========================================

-- Table pour les métriques de performance IA
CREATE TABLE IF NOT EXISTS "AIMetrics" (
    "Id" serial NOT NULL,
    "MetricName" character varying(100) NOT NULL,
    "MetricValue" numeric(10,4) NOT NULL,
    "MetricUnit" character varying(20) NULL,
    "ModelName" character varying(100) NULL,
    "Provider" character varying(50) NULL,
    "CampaignId" integer NULL,
    "UserId" text NULL,
    "Timestamp" timestamp with time zone NOT NULL DEFAULT now(),
    "Metadata" jsonb NULL,
    CONSTRAINT "PK_AIMetrics" PRIMARY KEY ("Id")
);

-- Table pour les logs d'utilisation IA
CREATE TABLE IF NOT EXISTS "AILogs" (
    "Id" serial NOT NULL,
    "LogLevel" character varying(20) NOT NULL DEFAULT 'INFO',
    "LogMessage" text NOT NULL,
    "LogCategory" character varying(50) NULL,
    "ModelName" character varying(100) NULL,
    "Provider" character varying(50) NULL,
    "CampaignId" integer NULL,
    "UserId" text NULL,
    "RequestId" character varying(100) NULL,
    "ResponseTime" integer NULL,
    "TokensUsed" integer NULL,
    "Cost" numeric(10,6) NULL,
    "Timestamp" timestamp with time zone NOT NULL DEFAULT now(),
    "StackTrace" text NULL,
    "Metadata" jsonb NULL,
    CONSTRAINT "PK_AILogs" PRIMARY KEY ("Id")
);

-- Table pour les alertes IA
CREATE TABLE IF NOT EXISTS "AIAlerts" (
    "Id" serial NOT NULL,
    "AlertType" character varying(50) NOT NULL,
    "AlertLevel" character varying(20) NOT NULL DEFAULT 'WARNING',
    "AlertMessage" text NOT NULL,
    "AlertTitle" character varying(200) NULL,
    "IsResolved" boolean NOT NULL DEFAULT false,
    "ResolvedAt" timestamp with time zone NULL,
    "ResolvedBy" text NULL,
    "CampaignId" integer NULL,
    "UserId" text NULL,
    "CreatedAt" timestamp with time zone NOT NULL DEFAULT now(),
    "UpdatedAt" timestamp with time zone NULL,
    "Metadata" jsonb NULL,
    CONSTRAINT "PK_AIAlerts" PRIMARY KEY ("Id")
);

-- Table pour les seuils d'alerte configurables
CREATE TABLE IF NOT EXISTS "AIAlertThresholds" (
    "Id" serial NOT NULL,
    "MetricName" character varying(100) NOT NULL,
    "ThresholdType" character varying(20) NOT NULL, -- 'MIN', 'MAX', 'AVERAGE'
    "ThresholdValue" numeric(10,4) NOT NULL,
    "AlertLevel" character varying(20) NOT NULL DEFAULT 'WARNING',
    "IsActive" boolean NOT NULL DEFAULT true,
    "Description" text NULL,
    "CreatedAt" timestamp with time zone NOT NULL DEFAULT now(),
    "UpdatedAt" timestamp with time zone NULL,
    CONSTRAINT "PK_AIAlertThresholds" PRIMARY KEY ("Id")
);

-- Table pour les coûts et quotas IA
CREATE TABLE IF NOT EXISTS "AICosts" (
    "Id" serial NOT NULL,
    "Provider" character varying(50) NOT NULL,
    "ModelName" character varying(100) NOT NULL,
    "OperationType" character varying(50) NOT NULL, -- 'COMPLETION', 'EMBEDDING', 'IMAGE_GENERATION'
    "TokensUsed" integer NOT NULL DEFAULT 0,
    "CostPerToken" numeric(10,8) NOT NULL,
    "TotalCost" numeric(10,6) NOT NULL,
    "CampaignId" integer NULL,
    "UserId" text NULL,
    "Date" date NOT NULL DEFAULT CURRENT_DATE,
    "CreatedAt" timestamp with time zone NOT NULL DEFAULT now(),
    CONSTRAINT "PK_AICosts" PRIMARY KEY ("Id")
);

-- Table pour les performances des modèles IA
CREATE TABLE IF NOT EXISTS "AIModelPerformance" (
    "Id" serial NOT NULL,
    "ModelName" character varying(100) NOT NULL,
    "Provider" character varying(50) NOT NULL,
    "AverageResponseTime" integer NOT NULL,
    "SuccessRate" numeric(5,2) NOT NULL,
    "ErrorRate" numeric(5,2) NOT NULL,
    "TotalRequests" integer NOT NULL DEFAULT 0,
    "TotalErrors" integer NOT NULL DEFAULT 0,
    "Date" date NOT NULL DEFAULT CURRENT_DATE,
    "CreatedAt" timestamp with time zone NOT NULL DEFAULT now(),
    "UpdatedAt" timestamp with time zone NULL,
    CONSTRAINT "PK_AIModelPerformance" PRIMARY KEY ("Id")
);

-- Add foreign key constraints for monitoring tables
ALTER TABLE "AIMetrics" 
ADD CONSTRAINT "FK_AIMetrics_Campaigns_CampaignId" 
FOREIGN KEY ("CampaignId") REFERENCES "Campaigns" ("Id") ON DELETE SET NULL;

ALTER TABLE "AILogs" 
ADD CONSTRAINT "FK_AILogs_Campaigns_CampaignId" 
FOREIGN KEY ("CampaignId") REFERENCES "Campaigns" ("Id") ON DELETE SET NULL;

ALTER TABLE "AIAlerts" 
ADD CONSTRAINT "FK_AIAlerts_Campaigns_CampaignId" 
FOREIGN KEY ("CampaignId") REFERENCES "Campaigns" ("Id") ON DELETE SET NULL;

ALTER TABLE "AICosts" 
ADD CONSTRAINT "FK_AICosts_Campaigns_CampaignId" 
FOREIGN KEY ("CampaignId") REFERENCES "Campaigns" ("Id") ON DELETE SET NULL;

-- Create indexes for monitoring tables
CREATE INDEX IF NOT EXISTS "IX_AIMetrics_Timestamp" ON "AIMetrics" ("Timestamp");
CREATE INDEX IF NOT EXISTS "IX_AIMetrics_MetricName" ON "AIMetrics" ("MetricName");
CREATE INDEX IF NOT EXISTS "IX_AIMetrics_ModelName" ON "AIMetrics" ("ModelName");
CREATE INDEX IF NOT EXISTS "IX_AIMetrics_CampaignId" ON "AIMetrics" ("CampaignId");

CREATE INDEX IF NOT EXISTS "IX_AILogs_Timestamp" ON "AILogs" ("Timestamp");
CREATE INDEX IF NOT EXISTS "IX_AILogs_LogLevel" ON "AILogs" ("LogLevel");
CREATE INDEX IF NOT EXISTS "IX_AILogs_LogCategory" ON "AILogs" ("LogCategory");
CREATE INDEX IF NOT EXISTS "IX_AILogs_CampaignId" ON "AILogs" ("CampaignId");
CREATE INDEX IF NOT EXISTS "IX_AILogs_RequestId" ON "AILogs" ("RequestId");

CREATE INDEX IF NOT EXISTS "IX_AIAlerts_CreatedAt" ON "AIAlerts" ("CreatedAt");
CREATE INDEX IF NOT EXISTS "IX_AIAlerts_AlertType" ON "AIAlerts" ("AlertType");
CREATE INDEX IF NOT EXISTS "IX_AIAlerts_AlertLevel" ON "AIAlerts" ("AlertLevel");
CREATE INDEX IF NOT EXISTS "IX_AIAlerts_IsResolved" ON "AIAlerts" ("IsResolved");

CREATE INDEX IF NOT EXISTS "IX_AIAlertThresholds_MetricName" ON "AIAlertThresholds" ("MetricName");
CREATE INDEX IF NOT EXISTS "IX_AIAlertThresholds_IsActive" ON "AIAlertThresholds" ("IsActive");

CREATE INDEX IF NOT EXISTS "IX_AICosts_Date" ON "AICosts" ("Date");
CREATE INDEX IF NOT EXISTS "IX_AICosts_Provider" ON "AICosts" ("Provider");
CREATE INDEX IF NOT EXISTS "IX_AICosts_ModelName" ON "AICosts" ("ModelName");

CREATE INDEX IF NOT EXISTS "IX_AIModelPerformance_Date" ON "AIModelPerformance" ("Date");
CREATE INDEX IF NOT EXISTS "IX_AIModelPerformance_ModelName" ON "AIModelPerformance" ("ModelName");
CREATE INDEX IF NOT EXISTS "IX_AIModelPerformance_Provider" ON "AIModelPerformance" ("Provider");


-- Migration: Add CurrentLocationId columns if they don't exist (for existing databases)
DO $$
BEGIN
    -- Add CurrentLocationId to CampaignCharacters if not exists
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'CampaignCharacters' AND column_name = 'CurrentLocationId') THEN
        ALTER TABLE "CampaignCharacters" ADD COLUMN "CurrentLocationId" integer NULL;
        CREATE INDEX IF NOT EXISTS "IX_CampaignCharacters_CurrentLocationId" ON "CampaignCharacters" ("CurrentLocationId");
        
        -- Add foreign key if CampaignLocations exists
        IF EXISTS (SELECT 1 FROM pg_tables WHERE tablename = 'CampaignLocations') THEN
            ALTER TABLE "CampaignCharacters" 
            ADD CONSTRAINT "FK_CampaignCharacters_CampaignLocations_CurrentLocationId" 
            FOREIGN KEY ("CurrentLocationId") REFERENCES "CampaignLocations" ("Id") ON DELETE SET NULL;
        END IF;
        
        RAISE NOTICE 'Added CurrentLocationId column to CampaignCharacters';
    END IF;
    
    -- Add CurrentLocationId to CampaignNPCs if not exists
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'CampaignNPCs' AND column_name = 'CurrentLocationId') THEN
        ALTER TABLE "CampaignNPCs" ADD COLUMN "CurrentLocationId" integer NULL;
        CREATE INDEX IF NOT EXISTS "IX_CampaignNPCs_CurrentLocationId" ON "CampaignNPCs" ("CurrentLocationId");
        
        -- Add foreign key
        ALTER TABLE "CampaignNPCs" 
        ADD CONSTRAINT "FK_CampaignNPCs_CampaignLocations_CurrentLocationId" 
        FOREIGN KEY ("CurrentLocationId") REFERENCES "CampaignLocations" ("Id") ON DELETE SET NULL;
        
        RAISE NOTICE 'Added CurrentLocationId column to CampaignNPCs';
    END IF;
END
$$;

-- Insert default alert thresholds
INSERT INTO "AIAlertThresholds" ("MetricName", "ThresholdType", "ThresholdValue", "AlertLevel", "Description") VALUES
('response_time', 'MAX', 10000, 'WARNING', 'Response time exceeds 10 seconds'),
('response_time', 'MAX', 30000, 'ERROR', 'Response time exceeds 30 seconds'),
('error_rate', 'MAX', 5.0, 'WARNING', 'Error rate exceeds 5%'),
('error_rate', 'MAX', 15.0, 'ERROR', 'Error rate exceeds 15%'),
('cost_per_day', 'MAX', 50.0, 'WARNING', 'Daily cost exceeds $50'),
('cost_per_day', 'MAX', 100.0, 'ERROR', 'Daily cost exceeds $100'),
('tokens_per_request', 'MAX', 5000, 'WARNING', 'Tokens per request exceeds 5000'),
('success_rate', 'MIN', 90.0, 'WARNING', 'Success rate below 90%'),
('success_rate', 'MIN', 80.0, 'ERROR', 'Success rate below 80%');

-- 🔒 SÉCURITÉ: l'utilisateur de jeu a SEULEMENT les droits nécessaires pour écrire les logs de monitoring
-- L'admin webapp garde le contrôle total pour l'administration
DO $$
DECLARE
    game_user text := coalesce(nullif(current_setting('GAME_DB_USER', true), ''), 'gamemaster');
BEGIN
    EXECUTE format('GRANT SELECT, INSERT ON TABLE "AIMetrics" TO %I', game_user);
    EXECUTE format('GRANT SELECT, INSERT ON TABLE "AILogs" TO %I', game_user);
    EXECUTE format('GRANT SELECT, INSERT ON TABLE "AIAlerts" TO %I', game_user);
    EXECUTE format('GRANT SELECT ON TABLE "AIAlertThresholds" TO %I', game_user); -- Lecture seule pour les seuils
    EXECUTE format('GRANT SELECT, INSERT ON TABLE "AICosts" TO %I', game_user);
    EXECUTE format('GRANT SELECT, INSERT, UPDATE ON TABLE "AIModelPerformance" TO %I', game_user); -- UPDATE nécessaire pour la performance

    -- Grant usage on sequences for monitoring tables (nécessaire pour INSERT)
    EXECUTE format('GRANT USAGE, SELECT ON SEQUENCE "AIMetrics_Id_seq" TO %I', game_user);
    EXECUTE format('GRANT USAGE, SELECT ON SEQUENCE "AILogs_Id_seq" TO %I', game_user);
    EXECUTE format('GRANT USAGE, SELECT ON SEQUENCE "AIAlerts_Id_seq" TO %I', game_user);
    EXECUTE format('GRANT USAGE, SELECT ON SEQUENCE "AICosts_Id_seq" TO %I', game_user);
    EXECUTE format('GRANT USAGE, SELECT ON SEQUENCE "AIModelPerformance_Id_seq" TO %I', game_user);
END
$$;