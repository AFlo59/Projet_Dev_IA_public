using DnDGameMaster.WebApp.Models;
using Microsoft.AspNetCore.Identity;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Infrastructure;
using Microsoft.Extensions.Logging;

namespace DnDGameMaster.WebApp.Data
{
    public static class SeedData
    {
        public static async Task InitializeAsync(
            UserManager<ApplicationUser> userManager,
            RoleManager<IdentityRole> roleManager)
        {
            // Create roles if they don't exist
            string[] roles = { "Admin", "GameMaster", "Player" };
            
            foreach (var role in roles)
            {
                if (!await roleManager.RoleExistsAsync(role))
                {
                    await roleManager.CreateAsync(new IdentityRole(role));
                }
            }
            
            // Create admin user if it doesn't exist
            var adminUser = await userManager.FindByEmailAsync("admin@dndgamemaster.com");
            
            if (adminUser == null)
            {
                adminUser = new ApplicationUser
                {
                    UserName = "admin@dndgamemaster.com",
                    Email = "admin@dndgamemaster.com",
                    EmailConfirmed = true,  // Déjà confirmé par défaut
                    FirstName = "Admin",
                    LastName = "User",
                    Created = DateTime.UtcNow
                };
                
                var result = await userManager.CreateAsync(adminUser, "Admin123!");
                
                if (result.Succeeded)
                {
                    await userManager.AddToRoleAsync(adminUser, "Admin");
                }
            }
            else if (!adminUser.EmailConfirmed)
            {
                // Si l'utilisateur existe mais n'est pas confirmé, confirmons-le
                adminUser.EmailConfirmed = true;
                await userManager.UpdateAsync(adminUser);
            }
            
            // Créer un utilisateur de test
            var testUser = await userManager.FindByEmailAsync("test@dndgamemaster.com");
            
            if (testUser == null)
            {
                testUser = new ApplicationUser
                {
                    UserName = "test@dndgamemaster.com",
                    Email = "test@dndgamemaster.com",
                    EmailConfirmed = true,  // Déjà confirmé par défaut
                    FirstName = "Test",
                    LastName = "User",
                    Created = DateTime.UtcNow
                };
                
                var result = await userManager.CreateAsync(testUser, "Test123!");
                
                if (result.Succeeded)
                {
                    await userManager.AddToRoleAsync(testUser, "Player");
                }
            }
            else if (!testUser.EmailConfirmed)
            {
                // Si l'utilisateur existe mais n'est pas confirmé, confirmons-le
                testUser.EmailConfirmed = true;
                await userManager.UpdateAsync(testUser);
            }
        }
        
        public static void CreateIdentitySchema(DatabaseFacade database, ILogger logger)
        {
            try
            {
                logger.LogInformation("Creating identity schema...");
                
                // Create schema using raw SQL
                var sql = @"
                    -- Users table
                    CREATE TABLE IF NOT EXISTS ""AspNetUsers"" (
                        ""Id"" TEXT PRIMARY KEY,
                        ""UserName"" TEXT,
                        ""NormalizedUserName"" TEXT,
                        ""Email"" TEXT,
                        ""NormalizedEmail"" TEXT,
                        ""EmailConfirmed"" BOOLEAN NOT NULL,
                        ""PasswordHash"" TEXT,
                        ""SecurityStamp"" TEXT,
                        ""ConcurrencyStamp"" TEXT,
                        ""PhoneNumber"" TEXT,
                        ""PhoneNumberConfirmed"" BOOLEAN NOT NULL,
                        ""TwoFactorEnabled"" BOOLEAN NOT NULL,
                        ""LockoutEnd"" TIMESTAMP,
                        ""LockoutEnabled"" BOOLEAN NOT NULL,
                        ""AccessFailedCount"" INTEGER NOT NULL,
                        ""FirstName"" TEXT,
                        ""LastName"" TEXT,
                        ""Created"" TIMESTAMP,
                        ""LastActive"" TIMESTAMP
                    );
                    
                    -- Roles table
                    CREATE TABLE IF NOT EXISTS ""AspNetRoles"" (
                        ""Id"" TEXT PRIMARY KEY,
                        ""Name"" TEXT,
                        ""NormalizedName"" TEXT,
                        ""ConcurrencyStamp"" TEXT
                    );
                    
                    -- User roles table
                    CREATE TABLE IF NOT EXISTS ""AspNetUserRoles"" (
                        ""UserId"" TEXT NOT NULL,
                        ""RoleId"" TEXT NOT NULL,
                        CONSTRAINT ""PK_AspNetUserRoles"" PRIMARY KEY (""UserId"", ""RoleId""),
                        CONSTRAINT ""FK_AspNetUserRoles_AspNetRoles_RoleId"" FOREIGN KEY (""RoleId"") REFERENCES ""AspNetRoles"" (""Id"") ON DELETE CASCADE,
                        CONSTRAINT ""FK_AspNetUserRoles_AspNetUsers_UserId"" FOREIGN KEY (""UserId"") REFERENCES ""AspNetUsers"" (""Id"") ON DELETE CASCADE
                    );
                    
                    -- User claims table
                    CREATE TABLE IF NOT EXISTS ""AspNetUserClaims"" (
                        ""Id"" SERIAL PRIMARY KEY,
                        ""UserId"" TEXT NOT NULL,
                        ""ClaimType"" TEXT,
                        ""ClaimValue"" TEXT,
                        CONSTRAINT ""FK_AspNetUserClaims_AspNetUsers_UserId"" FOREIGN KEY (""UserId"") REFERENCES ""AspNetUsers"" (""Id"") ON DELETE CASCADE
                    );
                    
                    -- User logins table
                    CREATE TABLE IF NOT EXISTS ""AspNetUserLogins"" (
                        ""LoginProvider"" TEXT NOT NULL,
                        ""ProviderKey"" TEXT NOT NULL,
                        ""ProviderDisplayName"" TEXT,
                        ""UserId"" TEXT NOT NULL,
                        CONSTRAINT ""PK_AspNetUserLogins"" PRIMARY KEY (""LoginProvider"", ""ProviderKey""),
                        CONSTRAINT ""FK_AspNetUserLogins_AspNetUsers_UserId"" FOREIGN KEY (""UserId"") REFERENCES ""AspNetUsers"" (""Id"") ON DELETE CASCADE
                    );
                    
                    -- User tokens table
                    CREATE TABLE IF NOT EXISTS ""AspNetUserTokens"" (
                        ""UserId"" TEXT NOT NULL,
                        ""LoginProvider"" TEXT NOT NULL,
                        ""Name"" TEXT NOT NULL,
                        ""Value"" TEXT,
                        CONSTRAINT ""PK_AspNetUserTokens"" PRIMARY KEY (""UserId"", ""LoginProvider"", ""Name""),
                        CONSTRAINT ""FK_AspNetUserTokens_AspNetUsers_UserId"" FOREIGN KEY (""UserId"") REFERENCES ""AspNetUsers"" (""Id"") ON DELETE CASCADE
                    );
                    
                    -- Role claims table
                    CREATE TABLE IF NOT EXISTS ""AspNetRoleClaims"" (
                        ""Id"" SERIAL PRIMARY KEY,
                        ""RoleId"" TEXT NOT NULL,
                        ""ClaimType"" TEXT,
                        ""ClaimValue"" TEXT,
                        CONSTRAINT ""FK_AspNetRoleClaims_AspNetRoles_RoleId"" FOREIGN KEY (""RoleId"") REFERENCES ""AspNetRoles"" (""Id"") ON DELETE CASCADE
                    );
                    
                    -- Create indexes
                    CREATE INDEX IF NOT EXISTS ""EmailIndex"" ON ""AspNetUsers"" (""NormalizedEmail"");
                    CREATE UNIQUE INDEX IF NOT EXISTS ""UserNameIndex"" ON ""AspNetUsers"" (""NormalizedUserName"");
                    CREATE UNIQUE INDEX IF NOT EXISTS ""RoleNameIndex"" ON ""AspNetRoles"" (""NormalizedName"");
                    CREATE INDEX IF NOT EXISTS ""IX_AspNetUserClaims_UserId"" ON ""AspNetUserClaims"" (""UserId"");
                    CREATE INDEX IF NOT EXISTS ""IX_AspNetUserLogins_UserId"" ON ""AspNetUserLogins"" (""UserId"");
                    CREATE INDEX IF NOT EXISTS ""IX_AspNetUserRoles_RoleId"" ON ""AspNetUserRoles"" (""RoleId"");
                    CREATE INDEX IF NOT EXISTS ""IX_AspNetRoleClaims_RoleId"" ON ""AspNetRoleClaims"" (""RoleId"");
                ";
                
                database.ExecuteSqlRaw(sql);
                logger.LogInformation("Identity schema created successfully");
                
                // Créer aussi les tables de jeu
                CreateGameTables(database, logger);
            }
            catch (Exception ex)
            {
                logger.LogError(ex, "Error creating identity schema");
                throw;
            }
        }
        
        private static void CreateGameTables(DatabaseFacade database, ILogger logger)
        {
            try
            {
                logger.LogInformation("Creating game tables manually...");
                
                var sql = @"
                    -- Campaigns table
                    CREATE TABLE IF NOT EXISTS ""Campaigns"" (
                        ""Id"" SERIAL PRIMARY KEY,
                        ""Name"" TEXT NOT NULL,
                        ""Description"" TEXT,
                        ""OwnerId"" TEXT,
                        ""IsPublic"" BOOLEAN NOT NULL DEFAULT FALSE,
                        ""CreatedAt"" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        ""UpdatedAt"" TIMESTAMP,
                        ""Setting"" TEXT,
                        ""ImageUrl"" TEXT,
                        CONSTRAINT ""FK_Campaigns_AspNetUsers_OwnerId"" FOREIGN KEY (""OwnerId"") REFERENCES ""AspNetUsers"" (""Id"") ON DELETE SET NULL
                    );
                    
                    -- Characters table
                    CREATE TABLE IF NOT EXISTS ""Characters"" (
                        ""Id"" SERIAL PRIMARY KEY,
                        ""Name"" TEXT NOT NULL,
                        ""Race"" TEXT,
                        ""Gender"" TEXT,
                        ""Class"" TEXT,
                        ""Level"" INTEGER NOT NULL DEFAULT 1,
                        ""Background"" TEXT,
                        ""Alignment"" TEXT,
                        ""UserId"" TEXT,
                        ""CreatedAt"" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        ""UpdatedAt"" TIMESTAMP,
                        ""Strength"" INTEGER NOT NULL DEFAULT 10,
                        ""Dexterity"" INTEGER NOT NULL DEFAULT 10,
                        ""Constitution"" INTEGER NOT NULL DEFAULT 10,
                        ""Intelligence"" INTEGER NOT NULL DEFAULT 10,
                        ""Wisdom"" INTEGER NOT NULL DEFAULT 10,
                        ""Charisma"" INTEGER NOT NULL DEFAULT 10,
                        ""Backstory"" TEXT,
                        ""ImageUrl"" TEXT,
                        ""HitPoints"" INTEGER NOT NULL DEFAULT 0,
                        ""ArmorClass"" INTEGER NOT NULL DEFAULT 10,
                        ""Speed"" INTEGER NOT NULL DEFAULT 30,
                        CONSTRAINT ""FK_Characters_AspNetUsers_UserId"" FOREIGN KEY (""UserId"") REFERENCES ""AspNetUsers"" (""Id"") ON DELETE SET NULL
                    );
                    
                    -- CampaignCharacters (junction table)
                    CREATE TABLE IF NOT EXISTS ""CampaignCharacters"" (
                        ""CampaignId"" INTEGER,
                        ""CharacterId"" INTEGER,
                        ""IsActive"" BOOLEAN NOT NULL DEFAULT TRUE,
                        ""JoinedAt"" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        CONSTRAINT ""PK_CampaignCharacters"" PRIMARY KEY (""CampaignId"", ""CharacterId""),
                        CONSTRAINT ""FK_CampaignCharacters_Campaigns_CampaignId"" FOREIGN KEY (""CampaignId"") REFERENCES ""Campaigns"" (""Id"") ON DELETE CASCADE,
                        CONSTRAINT ""FK_CampaignCharacters_Characters_CharacterId"" FOREIGN KEY (""CharacterId"") REFERENCES ""Characters"" (""Id"") ON DELETE CASCADE
                    );
                    
                    -- CampaignSessions table
                    CREATE TABLE IF NOT EXISTS ""CampaignSessions"" (
                        ""Id"" SERIAL PRIMARY KEY,
                        ""CampaignId"" INTEGER NOT NULL,
                        ""Title"" TEXT,
                        ""StartedAt"" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        ""EndedAt"" TIMESTAMP,
                        ""IsComplete"" BOOLEAN NOT NULL DEFAULT FALSE,
                        ""Summary"" TEXT,
                        CONSTRAINT ""FK_CampaignSessions_Campaigns_CampaignId"" FOREIGN KEY (""CampaignId"") REFERENCES ""Campaigns"" (""Id"") ON DELETE CASCADE
                    );
                    
                    -- CampaignMessages table
                    CREATE TABLE IF NOT EXISTS ""CampaignMessages"" (
                        ""Id"" SERIAL PRIMARY KEY,
                        ""CampaignId"" INTEGER NOT NULL,
                        ""CharacterId"" INTEGER,
                        ""UserId"" TEXT,
                        ""Content"" TEXT NOT NULL,
                        ""CreatedAt"" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        ""Type"" TEXT NOT NULL DEFAULT 'player',
                        ""SessionId"" INTEGER,
                        CONSTRAINT ""FK_CampaignMessages_Campaigns_CampaignId"" FOREIGN KEY (""CampaignId"") REFERENCES ""Campaigns"" (""Id"") ON DELETE CASCADE,
                        CONSTRAINT ""FK_CampaignMessages_Characters_CharacterId"" FOREIGN KEY (""CharacterId"") REFERENCES ""Characters"" (""Id"") ON DELETE SET NULL,
                        CONSTRAINT ""FK_CampaignMessages_AspNetUsers_UserId"" FOREIGN KEY (""UserId"") REFERENCES ""AspNetUsers"" (""Id"") ON DELETE SET NULL,
                        CONSTRAINT ""FK_CampaignMessages_CampaignSessions_SessionId"" FOREIGN KEY (""SessionId"") REFERENCES ""CampaignSessions"" (""Id"") ON DELETE SET NULL
                    );
                    
                    -- Create indexes
                    CREATE INDEX IF NOT EXISTS ""IX_Campaigns_OwnerId"" ON ""Campaigns"" (""OwnerId"");
                    CREATE INDEX IF NOT EXISTS ""IX_Characters_UserId"" ON ""Characters"" (""UserId"");
                    CREATE INDEX IF NOT EXISTS ""IX_CampaignCharacters_CharacterId"" ON ""CampaignCharacters"" (""CharacterId"");
                    CREATE INDEX IF NOT EXISTS ""IX_CampaignSessions_CampaignId"" ON ""CampaignSessions"" (""CampaignId"");
                    CREATE INDEX IF NOT EXISTS ""IX_CampaignMessages_CampaignId"" ON ""CampaignMessages"" (""CampaignId"");
                    CREATE INDEX IF NOT EXISTS ""IX_CampaignMessages_CharacterId"" ON ""CampaignMessages"" (""CharacterId"");
                    CREATE INDEX IF NOT EXISTS ""IX_CampaignMessages_UserId"" ON ""CampaignMessages"" (""UserId"");
                    CREATE INDEX IF NOT EXISTS ""IX_CampaignMessages_SessionId"" ON ""CampaignMessages"" (""SessionId"");
                ";
                
                database.ExecuteSqlRaw(sql);
                logger.LogInformation("Game tables created successfully");
            }
            catch (Exception ex)
            {
                logger.LogError(ex, "Error creating game tables");
                throw;
            }
        }
    }
} 