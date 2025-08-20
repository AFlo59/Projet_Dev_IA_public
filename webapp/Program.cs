using DnDGameMaster.WebApp.Data;
using DnDGameMaster.WebApp.Models;
using DnDGameMaster.WebApp.Services;
using DnDGameMaster.WebApp.Services.Email;
using DnDGameMaster.WebApp.Services.Game;
using DnDGameMaster.WebApp.Services.LLM;
using DnDGameMaster.WebApp.Services.Reference;
using DnDGameMaster.WebApp.Services.Monitoring;
using Microsoft.AspNetCore.Identity;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.FileProviders;

var builder = WebApplication.CreateBuilder(args);

// Add services to the container.
builder.Services.AddControllersWithViews();

// Configure database context
var appDbConnectionString = GetConnectionString(
    builder.Configuration["APP_DB_HOST"] ?? "webapp_postgres",
    builder.Configuration["APP_DB_PORT"] ?? "5432",
    builder.Configuration["APP_DB_NAME"] ?? "app_db",
    builder.Configuration["DB_ADMIN_USER"] ?? throw new InvalidOperationException("DB_ADMIN_USER is required"),
    builder.Configuration["DB_ADMIN_PASSWORD"] ?? throw new InvalidOperationException("DB_ADMIN_PASSWORD is required")
);

// Log connection string for debugging (mask password for security)
Console.WriteLine($"App DB Connection: {MaskConnectionString(appDbConnectionString)}");

// Add unified database context
builder.Services.AddDbContext<ApplicationDbContext>(options =>
    options.UseNpgsql(appDbConnectionString));

// Configure Identity
builder.Services.AddIdentity<ApplicationUser, IdentityRole>(options => {
    options.SignIn.RequireConfirmedAccount = false;
    options.Password.RequiredLength = 8;
    options.Password.RequireDigit = true;
    options.Password.RequireNonAlphanumeric = true;
    options.Password.RequireUppercase = true;
    options.Password.RequireLowercase = true;
})
.AddEntityFrameworkStores<ApplicationDbContext>()
.AddDefaultTokenProviders();

// Configure cookie policy
builder.Services.ConfigureApplicationCookie(options => {
    options.Cookie.HttpOnly = true;
    options.ExpireTimeSpan = TimeSpan.FromDays(7);
    options.LoginPath = "/Account/Login";
    options.LogoutPath = "/Account/Logout";
    options.AccessDeniedPath = "/Account/AccessDenied";
    options.SlidingExpiration = true;
});

// Add email services
// builder.Services.AddTransient<BrevoEmailService>(); // Temporairement désactivé
builder.Services.AddTransient<BrevoSmtpEmailService>();
// builder.Services.AddTransient<IEmailService, FallbackEmailService>(); // Temporairement désactivé
builder.Services.AddScoped<IEmailService, BrevoSmtpEmailService>();

// Configure LLM service client
builder.Services.AddHttpClient<ILLMGameMasterService, LLMGameMasterService>(client => {
    var llmUrl = builder.Configuration["LLM_GAMEMASTER_API_URL"] ?? throw new InvalidOperationException("LLM_GAMEMASTER_API_URL is required");
    client.BaseAddress = new Uri(llmUrl);
    client.Timeout = TimeSpan.FromMinutes(5); // 5 minutes timeout for LLM requests
});

// Configure D&D reference service client (single registration)
builder.Services.AddHttpClient<IDataReferenceService, DataReferenceService>(client => {
    var dataRefUrl = builder.Configuration["DATA_REFERENCE_API_URL"] ?? throw new InvalidOperationException("DATA_REFERENCE_API_URL is required");
    client.BaseAddress = new Uri(dataRefUrl);
    client.Timeout = TimeSpan.FromMinutes(1); // 1 minute timeout for reference data
});

// Add a separate HttpClient for character generation with longer timeout
builder.Services.AddHttpClient("CharacterGeneration", client => {
    var llmUrl = builder.Configuration["LLM_GAMEMASTER_API_URL"] ?? throw new InvalidOperationException("LLM_GAMEMASTER_API_URL is required");
    client.BaseAddress = new Uri(llmUrl);
    client.Timeout = TimeSpan.FromMinutes(10); // 10 minutes timeout for character generation
});

// Add application services with unified context
builder.Services.AddScoped<ICampaignService, CampaignService>();
builder.Services.AddScoped<ICharacterService, CharacterService>();
builder.Services.AddScoped<IGameSessionService, GameSessionService>();
builder.Services.AddScoped<ILLMGameMasterService, LLMGameMasterService>();
builder.Services.AddScoped<ILLMService, LLMService>();
builder.Services.AddScoped<IJWTTokenService, JWTTokenService>();
builder.Services.AddScoped<IDataReferenceService, DataReferenceService>();
builder.Services.AddScoped<IAIMonitoringService, AIMonitoringService>();

// Add HttpContextAccessor for JWT authentication in LLM service
builder.Services.AddHttpContextAccessor();

var app = builder.Build();

// Configure the HTTP request pipeline.
if (app.Environment.IsDevelopment())
{
    app.UseMigrationsEndPoint();
}
else
{
    app.UseExceptionHandler("/Home/Error");
    app.UseHsts();
}

// Apply pending migrations
using (var scope = app.Services.CreateScope())
{
    var dbContext = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
    dbContext.Database.Migrate();
}

app.UseHttpsRedirection();

// Configurer les fichiers statiques correctement et avec un logging supplémentaire
app.Logger.LogInformation("Configuration des fichiers statiques dans wwwroot");

app.UseDefaultFiles();
app.UseStaticFiles(new StaticFileOptions
{
    OnPrepareResponse = ctx =>
    {
        // Désactiver la mise en cache pour le développement
        ctx.Context.Response.Headers.Append("Cache-Control", "no-cache, no-store");
        ctx.Context.Response.Headers.Append("Expires", "-1");
        app.Logger.LogInformation($"Serving static file: {ctx.File.Name}, Path: {ctx.File.PhysicalPath}");
    }
});

// Configuration pour servir les images générées par LLMGameMaster
app.UseStaticFiles(new StaticFileOptions
{
    RequestPath = "/images",
    FileProvider = new PhysicalFileProvider("/app/wwwroot/images"),
    OnPrepareResponse = ctx =>
    {
        ctx.Context.Response.Headers.Append("Cache-Control", "no-cache, no-store");
        app.Logger.LogInformation($"Serving LLM image: {ctx.File.Name}");
    }
});

// Afficher les répertoires actifs
app.Logger.LogInformation($"Content Root Path: {app.Environment.ContentRootPath}");
app.Logger.LogInformation($"Web Root Path: {app.Environment.WebRootPath}");

app.UseRouting();

app.UseAuthentication();
app.UseAuthorization();

app.MapControllerRoute(
    name: "default",
    pattern: "{controller=Home}/{action=Index}/{id?}");

// Create database and apply migrations if not exists
using (var scope = app.Services.CreateScope())
{
    var services = scope.ServiceProvider;
    var logger = services.GetRequiredService<ILogger<Program>>();
    
    try
    {
        logger.LogInformation("Attempting to connect to database and apply migrations...");
        
        // Add retry logic for database migrations
        const int maxRetries = 5;
        const int retryDelaySeconds = 10;
        
        // Handle database migrations with retries
        for (int attempt = 1; attempt <= maxRetries; attempt++)
        {
            try
            {
                logger.LogInformation($"Connecting to database (attempt {attempt}/{maxRetries})");
                var appContext = services.GetRequiredService<ApplicationDbContext>();
                
                // Check if the database exists, if not create it with schema
                logger.LogInformation("Ensuring database exists and creating schema if needed");
                
                // First check if the AspNetRoles table exists
                bool tableExists = false;
                try
                {
                    logger.LogInformation("Checking if AspNetRoles table exists...");
                    var conn = appContext.Database.GetDbConnection();
                    if (conn.State != System.Data.ConnectionState.Open)
                        conn.Open();
                    
                    using (var cmd = conn.CreateCommand())
                    {
                        cmd.CommandText = "SELECT EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'AspNetRoles')";
                        var result = cmd.ExecuteScalar();
                        tableExists = result != null && (bool)result;
                    }
                    
                    logger.LogInformation($"AspNetRoles table exists: {tableExists}");
                }
                catch (Exception ex)
                {
                    logger.LogWarning(ex, "Error checking for AspNetRoles table existence");
                }
                
                if (!tableExists)
                {
                    logger.LogWarning("Identity tables not found. Using manual creation to create the schema");
                    // Force schema creation
                    CreateIdentitySchema(appContext.Database, logger);
                }
                else
                {
                    // Apply any migrations
                    if (appContext.Database.GetPendingMigrations().Any())
                    {
                        logger.LogInformation("Applying pending migrations");
                        appContext.Database.Migrate();
                    }
                }
                
                logger.LogInformation("Database setup completed successfully");
                break;
            }
            catch (Exception ex)
            {
                logger.LogWarning(ex, $"Error connecting to database on attempt {attempt}/{maxRetries}");
                if (attempt == maxRetries)
                {
                    logger.LogError(ex, "Failed to connect to database after all retry attempts");
                    // Continue with the application, as the database might become available later
                }
                else
                {
                    logger.LogInformation($"Waiting {retryDelaySeconds} seconds before next attempt...");
                    Thread.Sleep(retryDelaySeconds * 1000);
                }
            }
        }
        
        // Initialize seed data if possible
        try
        {
            var userManager = services.GetRequiredService<UserManager<ApplicationUser>>();
            var roleManager = services.GetRequiredService<RoleManager<IdentityRole>>();
            await SeedData.InitializeAsync(userManager, roleManager);
            logger.LogInformation("Seed data initialization completed");
        }
        catch (Exception ex)
        {
            logger.LogError(ex, "An error occurred while seeding the database.");
        }
    }
    catch (Exception ex)
    {
        logger.LogError(ex, "An unexpected error occurred during database initialization.");
    }
}

app.Run();

// Helper method to build connection string
string GetConnectionString(string host, string port, string database, string username, string password)
{
    return $"Host={host};Port={port};Database={database};Username={username};Password={password};";
}

// Helper method to mask password in connection string for logging
string MaskConnectionString(string connectionString)
{
    return System.Text.RegularExpressions.Regex.Replace(
        connectionString,
        "Password=([^;]*)",
        "Password=******"
    );
}

// Helper method to create Identity schema manually
static void CreateIdentitySchema(Microsoft.EntityFrameworkCore.Infrastructure.DatabaseFacade database, ILogger logger)
{
    try
    {
        logger.LogInformation("Creating Identity schema tables manually...");
        
        var conn = database.GetDbConnection();
        if (conn.State != System.Data.ConnectionState.Open)
            conn.Open();
        
        using (var cmd = conn.CreateCommand())
        {
            // Create ASP.NET Identity schema
            cmd.CommandText = @"
CREATE TABLE IF NOT EXISTS ""AspNetRoles"" (
    ""Id"" text NOT NULL,
    ""Name"" character varying(256) NULL,
    ""NormalizedName"" character varying(256) NULL,
    ""ConcurrencyStamp"" text NULL,
    CONSTRAINT ""PK_AspNetRoles"" PRIMARY KEY (""Id"")
);

CREATE TABLE IF NOT EXISTS ""AspNetUsers"" (
    ""Id"" text NOT NULL,
    ""UserName"" character varying(256) NULL,
    ""NormalizedUserName"" character varying(256) NULL,
    ""Email"" character varying(256) NULL,
    ""NormalizedEmail"" character varying(256) NULL,
    ""EmailConfirmed"" boolean NOT NULL,
    ""PasswordHash"" text NULL,
    ""SecurityStamp"" text NULL,
    ""ConcurrencyStamp"" text NULL,
    ""PhoneNumber"" text NULL,
    ""PhoneNumberConfirmed"" boolean NOT NULL,
    ""TwoFactorEnabled"" boolean NOT NULL,
    ""LockoutEnd"" timestamp with time zone NULL,
    ""LockoutEnabled"" boolean NOT NULL,
    ""AccessFailedCount"" integer NOT NULL,
    ""FirstName"" text NULL,
    ""LastName"" text NULL,
    ""LastActive"" timestamp with time zone NULL,
    ""Created"" timestamp with time zone NOT NULL,
    CONSTRAINT ""PK_AspNetUsers"" PRIMARY KEY (""Id"")
);

CREATE TABLE IF NOT EXISTS ""AspNetRoleClaims"" (
    ""Id"" serial NOT NULL,
    ""RoleId"" text NOT NULL,
    ""ClaimType"" text NULL,
    ""ClaimValue"" text NULL,
    CONSTRAINT ""PK_AspNetRoleClaims"" PRIMARY KEY (""Id""),
    CONSTRAINT ""FK_AspNetRoleClaims_AspNetRoles_RoleId"" FOREIGN KEY (""RoleId"") REFERENCES ""AspNetRoles"" (""Id"") ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ""AspNetUserClaims"" (
    ""Id"" serial NOT NULL,
    ""UserId"" text NOT NULL,
    ""ClaimType"" text NULL,
    ""ClaimValue"" text NULL,
    CONSTRAINT ""PK_AspNetUserClaims"" PRIMARY KEY (""Id""),
    CONSTRAINT ""FK_AspNetUserClaims_AspNetUsers_UserId"" FOREIGN KEY (""UserId"") REFERENCES ""AspNetUsers"" (""Id"") ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ""AspNetUserLogins"" (
    ""LoginProvider"" text NOT NULL,
    ""ProviderKey"" text NOT NULL,
    ""ProviderDisplayName"" text NULL,
    ""UserId"" text NOT NULL,
    CONSTRAINT ""PK_AspNetUserLogins"" PRIMARY KEY (""LoginProvider"", ""ProviderKey""),
    CONSTRAINT ""FK_AspNetUserLogins_AspNetUsers_UserId"" FOREIGN KEY (""UserId"") REFERENCES ""AspNetUsers"" (""Id"") ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ""AspNetUserRoles"" (
    ""UserId"" text NOT NULL,
    ""RoleId"" text NOT NULL,
    CONSTRAINT ""PK_AspNetUserRoles"" PRIMARY KEY (""UserId"", ""RoleId""),
    CONSTRAINT ""FK_AspNetUserRoles_AspNetRoles_RoleId"" FOREIGN KEY (""RoleId"") REFERENCES ""AspNetRoles"" (""Id"") ON DELETE CASCADE,
    CONSTRAINT ""FK_AspNetUserRoles_AspNetUsers_UserId"" FOREIGN KEY (""UserId"") REFERENCES ""AspNetUsers"" (""Id"") ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ""AspNetUserTokens"" (
    ""UserId"" text NOT NULL,
    ""LoginProvider"" text NOT NULL,
    ""Name"" text NOT NULL,
    ""Value"" text NULL,
    CONSTRAINT ""PK_AspNetUserTokens"" PRIMARY KEY (""UserId"", ""LoginProvider"", ""Name""),
    CONSTRAINT ""FK_AspNetUserTokens_AspNetUsers_UserId"" FOREIGN KEY (""UserId"") REFERENCES ""AspNetUsers"" (""Id"") ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ""IX_AspNetRoleClaims_RoleId"" ON ""AspNetRoleClaims"" (""RoleId"");
CREATE UNIQUE INDEX IF NOT EXISTS ""RoleNameIndex"" ON ""AspNetRoles"" (""NormalizedName"");
CREATE INDEX IF NOT EXISTS ""IX_AspNetUserClaims_UserId"" ON ""AspNetUserClaims"" (""UserId"");
CREATE INDEX IF NOT EXISTS ""IX_AspNetUserLogins_UserId"" ON ""AspNetUserLogins"" (""UserId"");
CREATE INDEX IF NOT EXISTS ""IX_AspNetUserRoles_RoleId"" ON ""AspNetUserRoles"" (""RoleId"");
CREATE INDEX IF NOT EXISTS ""EmailIndex"" ON ""AspNetUsers"" (""NormalizedEmail"");
CREATE UNIQUE INDEX IF NOT EXISTS ""UserNameIndex"" ON ""AspNetUsers"" (""NormalizedUserName"");
";
            cmd.ExecuteNonQuery();
        }
        
        logger.LogInformation("Identity schema created successfully");
        
        // Créer aussi les tables de jeu
        CreateGameTables(database, logger);
    }
    catch (Exception ex)
    {
        logger.LogError(ex, "Failed to create Identity schema");
    }
}

// Helper method to create game tables manually
static void CreateGameTables(Microsoft.EntityFrameworkCore.Infrastructure.DatabaseFacade database, ILogger logger)
{
    try
    {
        logger.LogInformation("Creating game tables manually...");
        
        var conn = database.GetDbConnection();
        if (conn.State != System.Data.ConnectionState.Open)
            conn.Open();
        
        using (var cmd = conn.CreateCommand())
        {
            // Créer les tables de jeu
            cmd.CommandText = @"
-- Table des campagnes
CREATE TABLE IF NOT EXISTS ""Campaigns"" (
    ""Id"" serial NOT NULL,
    ""Name"" character varying(100) NOT NULL,
    ""Language"" character varying(50) NOT NULL DEFAULT 'English',
    ""Description"" character varying(1000) NULL,
    ""Settings"" character varying(500) NULL,
    ""StartingLevel"" integer NOT NULL DEFAULT 1,
    ""MaxPlayers"" integer NOT NULL DEFAULT 5,
    ""IsPublic"" boolean NOT NULL DEFAULT false,
    ""Status"" character varying(20) NOT NULL DEFAULT 'Active',
    ""CreatedAt"" timestamp with time zone NOT NULL DEFAULT now(),
    ""UpdatedAt"" timestamp with time zone NULL,
    ""OwnerId"" text NOT NULL,
    CONSTRAINT ""PK_Campaigns"" PRIMARY KEY (""Id""),
    CONSTRAINT ""FK_Campaigns_AspNetUsers_OwnerId"" FOREIGN KEY (""OwnerId"") REFERENCES ""AspNetUsers"" (""Id"") ON DELETE CASCADE
);

-- Table des personnages
CREATE TABLE IF NOT EXISTS ""Characters"" (
    ""Id"" serial NOT NULL,
    ""Name"" character varying(100) NOT NULL,
    ""Race"" character varying(50) NOT NULL,
    ""Class"" character varying(50) NOT NULL,
    ""Level"" integer NOT NULL DEFAULT 1,
    ""Alignment"" character varying(20) NULL,
    ""Background"" character varying(50) NULL,
    ""Strength"" integer NOT NULL DEFAULT 10,
    ""Dexterity"" integer NOT NULL DEFAULT 10,
    ""Constitution"" integer NOT NULL DEFAULT 10,
    ""Intelligence"" integer NOT NULL DEFAULT 10,
    ""Wisdom"" integer NOT NULL DEFAULT 10,
    ""Charisma"" integer NOT NULL DEFAULT 10,
    ""Description"" text NULL,
    ""Equipment"" text NULL,
    ""PortraitUrl"" text NULL,
    ""CreatedAt"" timestamp with time zone NOT NULL DEFAULT now(),
    ""UpdatedAt"" timestamp with time zone NULL,
    ""UserId"" text NOT NULL,
    CONSTRAINT ""PK_Characters"" PRIMARY KEY (""Id""),
    CONSTRAINT ""FK_Characters_AspNetUsers_UserId"" FOREIGN KEY (""UserId"") REFERENCES ""AspNetUsers"" (""Id"") ON DELETE CASCADE
);

-- Table des personnages dans les campagnes
CREATE TABLE IF NOT EXISTS ""CampaignCharacters"" (
    ""Id"" serial NOT NULL,
    ""CampaignId"" integer NOT NULL,
    ""CharacterId"" integer NOT NULL,
    ""IsActive"" boolean NOT NULL DEFAULT true,
    ""CurrentLocation"" character varying(100) NULL,
    ""JoinedAt"" timestamp with time zone NOT NULL DEFAULT now(),
    CONSTRAINT ""PK_CampaignCharacters"" PRIMARY KEY (""Id""),
    CONSTRAINT ""FK_CampaignCharacters_Campaigns_CampaignId"" FOREIGN KEY (""CampaignId"") REFERENCES ""Campaigns"" (""Id"") ON DELETE CASCADE,
    CONSTRAINT ""FK_CampaignCharacters_Characters_CharacterId"" FOREIGN KEY (""CharacterId"") REFERENCES ""Characters"" (""Id"") ON DELETE CASCADE
);

-- Table des sessions de jeu
CREATE TABLE IF NOT EXISTS ""CampaignSessions"" (
    ""Id"" serial NOT NULL,
    ""CampaignId"" integer NOT NULL,
    ""Name"" character varying(100) NULL,
    ""Description"" text NULL,
    ""Status"" character varying(20) NULL DEFAULT 'Scheduled',
    ""Summary"" text NULL,
    ""StartedAt"" timestamp with time zone NOT NULL DEFAULT now(),
    ""EndedAt"" timestamp with time zone NULL,
    CONSTRAINT ""PK_CampaignSessions"" PRIMARY KEY (""Id""),
    CONSTRAINT ""FK_CampaignSessions_Campaigns_CampaignId"" FOREIGN KEY (""CampaignId"") REFERENCES ""Campaigns"" (""Id"") ON DELETE CASCADE
);

-- Table des messages de campagne
CREATE TABLE IF NOT EXISTS ""CampaignMessages"" (
    ""Id"" serial NOT NULL,
    ""CampaignId"" integer NOT NULL,
    ""SessionId"" integer NULL,
    ""CharacterId"" integer NULL,
    ""MessageType"" character varying(20) NOT NULL,
    ""Content"" text NOT NULL,
    ""SentAt"" timestamp with time zone NOT NULL DEFAULT now(),
    CONSTRAINT ""PK_CampaignMessages"" PRIMARY KEY (""Id""),
    CONSTRAINT ""FK_CampaignMessages_Campaigns_CampaignId"" FOREIGN KEY (""CampaignId"") REFERENCES ""Campaigns"" (""Id"") ON DELETE CASCADE,
    CONSTRAINT ""FK_CampaignMessages_CampaignSessions_SessionId"" FOREIGN KEY (""SessionId"") REFERENCES ""CampaignSessions"" (""Id"") ON DELETE SET NULL,
    CONSTRAINT ""FK_CampaignMessages_Characters_CharacterId"" FOREIGN KEY (""CharacterId"") REFERENCES ""Characters"" (""Id"") ON DELETE SET NULL
);

-- Table des NPCs de campagne
CREATE TABLE IF NOT EXISTS ""CampaignNPCs"" (
    ""Id"" serial NOT NULL,
    ""CampaignId"" integer NOT NULL,
    ""Name"" character varying(100) NOT NULL,
    ""Type"" character varying(50) NOT NULL DEFAULT 'Humanoid',
    ""Race"" character varying(50) NOT NULL,
    ""Class"" character varying(50) NULL,
    ""Level"" integer NOT NULL DEFAULT 1,
    ""HitPoints"" integer NOT NULL DEFAULT 10,
    ""ArmorClass"" integer NOT NULL DEFAULT 10,
    ""Alignment"" character varying(50) NULL,
    ""Description"" character varying(2000) NULL,
    ""CurrentLocation"" character varying(100) NULL,
    ""Status"" character varying(20) NOT NULL DEFAULT 'Active',
    ""Notes"" character varying(500) NULL,
    ""PortraitUrl"" character varying(1000) NULL,
    ""CreatedAt"" timestamp with time zone NOT NULL DEFAULT now(),
    ""UpdatedAt"" timestamp with time zone NULL,
    CONSTRAINT ""PK_CampaignNPCs"" PRIMARY KEY (""Id""),
    CONSTRAINT ""FK_CampaignNPCs_Campaigns_CampaignId"" FOREIGN KEY (""CampaignId"") REFERENCES ""Campaigns"" (""Id"") ON DELETE CASCADE
);

-- Table des lieux de campagne
CREATE TABLE IF NOT EXISTS ""CampaignLocations"" (
    ""Id"" serial NOT NULL,
    ""CampaignId"" integer NOT NULL,
    ""Name"" character varying(100) NOT NULL,
    ""Type"" character varying(50) NOT NULL DEFAULT 'Location',
    ""Description"" character varying(2000) NULL,
    ""ShortDescription"" character varying(500) NULL,
    ""ParentLocationId"" integer NULL,
    ""IsDiscovered"" boolean NOT NULL DEFAULT false,
    ""IsAccessible"" boolean NOT NULL DEFAULT true,
    ""Climate"" character varying(50) NULL,
    ""Terrain"" character varying(50) NULL,
    ""Population"" character varying(50) NULL,
    ""Notes"" character varying(1000) NULL,
    ""ImageUrl"" character varying(1000) NULL,
    ""CreatedAt"" timestamp with time zone NOT NULL DEFAULT now(),
    ""UpdatedAt"" timestamp with time zone NULL,
    CONSTRAINT ""PK_CampaignLocations"" PRIMARY KEY (""Id""),
    CONSTRAINT ""FK_CampaignLocations_Campaigns_CampaignId"" FOREIGN KEY (""CampaignId"") REFERENCES ""Campaigns"" (""Id"") ON DELETE CASCADE,
    CONSTRAINT ""FK_CampaignLocations_CampaignLocations_ParentLocationId"" FOREIGN KEY (""ParentLocationId"") REFERENCES ""CampaignLocations"" (""Id"") ON DELETE SET NULL
);

-- Table des quêtes de campagne
CREATE TABLE IF NOT EXISTS ""CampaignQuests"" (
    ""Id"" serial NOT NULL,
    ""CampaignId"" integer NOT NULL,
    ""Title"" character varying(200) NOT NULL,
    ""Description"" character varying(2000) NULL,
    ""ShortDescription"" character varying(500) NULL,
    ""Type"" character varying(50) NOT NULL DEFAULT 'Side',
    ""Status"" character varying(50) NOT NULL DEFAULT 'Available',
    ""Reward"" character varying(500) NULL,
    ""Requirements"" character varying(500) NULL,
    ""RequiredLevel"" integer NULL,
    ""LocationId"" integer NULL,
    ""QuestGiver"" character varying(100) NULL,
    ""Difficulty"" character varying(50) NULL,
    ""Notes"" character varying(1000) NULL,
    ""Progress"" character varying(1000) NULL,
    ""CreatedAt"" timestamp with time zone NOT NULL DEFAULT now(),
    ""UpdatedAt"" timestamp with time zone NULL,
    ""CompletedAt"" timestamp with time zone NULL,
    CONSTRAINT ""PK_CampaignQuests"" PRIMARY KEY (""Id""),
    CONSTRAINT ""FK_CampaignQuests_Campaigns_CampaignId"" FOREIGN KEY (""CampaignId"") REFERENCES ""Campaigns"" (""Id"") ON DELETE CASCADE,
    CONSTRAINT ""FK_CampaignQuests_CampaignLocations_LocationId"" FOREIGN KEY (""LocationId"") REFERENCES ""CampaignLocations"" (""Id"") ON DELETE SET NULL
);

-- Index pour optimiser les recherches
CREATE INDEX IF NOT EXISTS ""IX_Campaigns_OwnerId"" ON ""Campaigns"" (""OwnerId"");
CREATE INDEX IF NOT EXISTS ""IX_Characters_UserId"" ON ""Characters"" (""UserId"");
CREATE UNIQUE INDEX IF NOT EXISTS ""IX_CampaignCharacters_CampaignId_CharacterId"" ON ""CampaignCharacters"" (""CampaignId"", ""CharacterId"");
CREATE INDEX IF NOT EXISTS ""IX_CampaignCharacters_CharacterId"" ON ""CampaignCharacters"" (""CharacterId"");
CREATE INDEX IF NOT EXISTS ""IX_CampaignSessions_CampaignId"" ON ""CampaignSessions"" (""CampaignId"");
CREATE INDEX IF NOT EXISTS ""IX_CampaignMessages_CampaignId"" ON ""CampaignMessages"" (""CampaignId"");
CREATE INDEX IF NOT EXISTS ""IX_CampaignMessages_SessionId"" ON ""CampaignMessages"" (""SessionId"");
CREATE INDEX IF NOT EXISTS ""IX_CampaignMessages_CharacterId"" ON ""CampaignMessages"" (""CharacterId"");
CREATE INDEX IF NOT EXISTS ""IX_CampaignNPCs_CampaignId"" ON ""CampaignNPCs"" (""CampaignId"");
CREATE INDEX IF NOT EXISTS ""IX_CampaignNPCs_Status"" ON ""CampaignNPCs"" (""Status"");
CREATE INDEX IF NOT EXISTS ""IX_CampaignLocations_CampaignId"" ON ""CampaignLocations"" (""CampaignId"");
CREATE INDEX IF NOT EXISTS ""IX_CampaignLocations_ParentLocationId"" ON ""CampaignLocations"" (""ParentLocationId"");
CREATE INDEX IF NOT EXISTS ""IX_CampaignQuests_CampaignId"" ON ""CampaignQuests"" (""CampaignId"");
CREATE INDEX IF NOT EXISTS ""IX_CampaignQuests_LocationId"" ON ""CampaignQuests"" (""LocationId"");
CREATE INDEX IF NOT EXISTS ""IX_CampaignQuests_Status"" ON ""CampaignQuests"" (""Status"");
";
            cmd.ExecuteNonQuery();
            
            // Accorder les permissions au gamemaster
            cmd.CommandText = @"
DO $$
BEGIN
  IF EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'gamemaster') THEN
    GRANT SELECT, INSERT, UPDATE ON TABLE ""Campaigns"" TO gamemaster;
    GRANT SELECT, INSERT, UPDATE ON TABLE ""Characters"" TO gamemaster;
    GRANT SELECT, INSERT, UPDATE ON TABLE ""CampaignCharacters"" TO gamemaster;
    GRANT SELECT, INSERT, UPDATE ON TABLE ""CampaignSessions"" TO gamemaster;
    GRANT SELECT, INSERT, UPDATE ON TABLE ""CampaignMessages"" TO gamemaster;
    GRANT SELECT, INSERT, UPDATE ON TABLE ""CampaignNPCs"" TO gamemaster;
    GRANT SELECT, INSERT, UPDATE ON TABLE ""CampaignLocations"" TO gamemaster;
    GRANT SELECT, INSERT, UPDATE ON TABLE ""CampaignQuests"" TO gamemaster;
    GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO gamemaster;
  END IF;
END
$$;";
            cmd.ExecuteNonQuery();
        }
        
        logger.LogInformation("Game tables created successfully");
    }
    catch (Exception ex)
    {
        logger.LogError(ex, "Failed to create game tables");
    }
} 