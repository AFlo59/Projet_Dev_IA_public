# WebApp Module

## Vue d'ensemble

Le module **WebApp** est l'interface utilisateur principale du système D&D GameMaster AI. Développé en ASP.NET Core MVC, il fournit une application web moderne et sécurisée pour la gestion des comptes utilisateurs, des campagnes, des personnages, et l'interaction avec l'IA Game Master.

## Architecture

### Structure des fichiers

```
webapp/
├── README.md                           # Documentation du module
├── Program.cs                         # Point d'entrée et configuration (590 lignes)
├── DnDGameMaster.WebApp.csproj       # Configuration du projet .NET
├── appsettings.json                  # Configuration de l'application
├── Dockerfile                        # Image Docker
├── init.sql                          # Script d'initialisation BDD (656 lignes)
├── entrypoint.sh                     # Script de démarrage Docker
├── validate-jwt-integration.sh       # Validation JWT (Linux)
├── validate-jwt-integration.ps1      # Validation JWT (Windows)
├── Controllers/                      # Contrôleurs MVC
│   ├── AccountController.cs          # Gestion des comptes
│   ├── AdminController.cs            # Interface d'administration
│   ├── CampaignController.cs         # Gestion des campagnes
│   ├── CharacterController.cs        # Gestion des personnages
│   └── HomeController.cs             # Page d'accueil
├── Views/                           # Vues Razor
│   ├── Account/                     # Vues de gestion compte
│   ├── Admin/                       # Interface admin
│   ├── Campaign/                    # Vues de campagne
│   ├── Character/                   # Vues de personnage
│   ├── Home/                        # Page d'accueil
│   └── Shared/                      # Layouts et partials
├── Models/                          # Modèles de données
│   ├── ApplicationUser.cs           # Modèle utilisateur Identity
│   ├── Campaign.cs                  # Modèle de campagne
│   ├── Character.cs                 # Modèle de personnage
│   ├── AICosts.cs                   # Suivi des coûts IA
│   ├── AIAlerts.cs                  # Système d'alertes
│   └── [autres modèles]
├── Services/                        # Services applicatifs
│   ├── Email/                       # Services d'email
│   ├── Game/                        # Services de jeu
│   ├── LLM/                         # Services IA
│   ├── Reference/                   # Services données référence
│   └── Monitoring/                  # Services de monitoring
├── Data/                           # Contexte Entity Framework
│   ├── ApplicationDbContext.cs      # Contexte principal
│   └── SeedData.cs                  # Données de test
├── ViewModels/                     # ViewModels pour les vues
├── wwwroot/                        # Fichiers statiques (CSS, JS, images)
├── Migrations/                     # Migrations Entity Framework
└── bin/, obj/                      # Fichiers de compilation
```

## Fonctionnalités principales

### 1. Gestion des utilisateurs
- **Inscription et authentification** : Système complet avec ASP.NET Identity
- **Vérification d'email** : Validation des comptes par email
- **Gestion des mots de passe** : Réinitialisation sécurisée
- **Profils utilisateur** : Personnalisation et préférences

### 2. Gestion des campagnes
- **Création de campagnes** : Assistant avec paramètres personnalisables
- **Tableau de bord** : Vue d'ensemble des campagnes actives
- **Collaboration** : Partage entre maître de jeu et joueurs
- **Historique** : Suivi des sessions et progression

### 3. Gestion des personnages
- **Création de personnages** : Formulaires guidés avec validation
- **Feuilles de personnage** : Interface complète D&D 5e
- **Progression** : Suivi des niveaux et équipements
- **Intégration campagne** : Liaison avec les campagnes actives

### 4. Interface IA Game Master
- **Chat interactif** : Discussion en temps réel avec l'IA
- **Génération de contenu** : Lieux, PNJ, quêtes, événements
- **Visualisation** : Affichage des éléments générés
- **Persistance** : Sauvegarde des interactions et contenus

### 5. Administration
- **Dashboard admin** : Vue d'ensemble du système
- **Monitoring IA** : Suivi des coûts et utilisation
- **Gestion utilisateurs** : Administration des comptes
- **Alertes système** : Notifications et seuils

## Configuration

### Variables d'environnement

Le module utilise ces variables (configurées via `ENV_INFOS.md`) :

```bash
# Base de données principale
APP_DB_HOST=webapp_postgres
APP_DB_NAME=app_db
DB_ADMIN_USER=[ADMIN_USERNAME]
DB_ADMIN_PASSWORD=[ADMIN_PASSWORD]
GAME_DB_USER=[GAME_USERNAME]
GAME_DB_PASSWORD=[GAME_PASSWORD]

# Services d'email
BREVO_API_KEY=[API_KEY]
BREVO_SECRET_KEY=[SECRET_KEY]
BREVO_FROM_EMAIL=[EMAIL]
BREVO_FROM_NAME="D&D GameMaster"

# Alternative email
MAILJET_API_KEY=[API_KEY]
MAILJET_SECRET_KEY=[SECRET_KEY]
MAILJET_FROM_EMAIL=[EMAIL]
MAILJET_FROM_NAME="D&D GameMaster"

# APIs des services internes
DATA_REFERENCE_API_URL=http://datareference_api:5000
LLM_GAMEMASTER_API_URL=http://llm_gamemaster:5001
```

### Configuration ASP.NET

```json
{
  "Logging": {
    "LogLevel": {
      "Default": "Information",
      "Microsoft.AspNetCore": "Warning"
    }
  },
  "ConnectionStrings": {
    "DefaultConnection": "Configuration via variables d'environnement"
  },
  "AllowedHosts": "*"
}
```

## Architecture technique

### Pattern MVC

#### **Contrôleurs**
- `HomeController` : Page d'accueil et navigation
- `AccountController` : Authentification et gestion compte
- `CampaignController` : CRUD campagnes
- `CharacterController` : CRUD personnages
- `AdminController` : Interface d'administration

#### **Modèles Entity Framework**
```csharp
public class Campaign
{
    public int Id { get; set; }
    public string Name { get; set; }
    public string Description { get; set; }
    public DateTime CreatedDate { get; set; }
    public string UserId { get; set; }
    public ApplicationUser User { get; set; }
    public List<Character> Characters { get; set; }
}
```

#### **Services injectés**
```csharp
public interface ILLMGameMasterService
{
    Task<string> GenerateContentAsync(string prompt, CampaignContext context);
    Task<List<GameElement>> GetCampaignElementsAsync(int campaignId);
}

public interface IDataReferenceService  
{
    Task<List<Spell>> GetSpellsAsync(SpellFilter filter);
    Task<List<Monster>> GetMonstersAsync(MonsterFilter filter);
}
```

### Architecture des services

#### 1. **Services Email**
```csharp
// Service principal avec fallback
public class FallbackEmailService : IEmailService
{
    private readonly BrevoSmtpEmailService _primaryService;
    private readonly MailjetSmtpEmailService _fallbackService;
}
```

#### 2. **Services Game**
```csharp
public class CampaignService
{
    public async Task<Campaign> CreateCampaignAsync(CreateCampaignViewModel model)
    public async Task<List<Campaign>> GetUserCampaignsAsync(string userId)
}
```

#### 3. **Services LLM**
```csharp
public class LLMGameMasterService : ILLMGameMasterService
{
    private readonly HttpClient _httpClient;
    private readonly IJWTTokenService _jwtTokenService;
}
```

### Base de données

#### **Schema principal**
```sql
-- Tables Identity ASP.NET
AspNetUsers, AspNetRoles, AspNetUserRoles, AspNetUserClaims

-- Tables application
Campaigns, Characters, CampaignCharacters, GameElements,
ChatMessages, AIUsageLogs, AIAlertThresholds, AIAlerts

-- Tables monitoring
AIUsageMetrics, SystemLogs, UserActivity
```

#### **Relations clés**
- Utilisateur → Campagnes (1:N)
- Campagne → Personnages (N:M via CampaignCharacters)
- Campagne → Éléments générés (1:N)
- Utilisateur → Messages chat (1:N)

## Interface utilisateur

### Design responsive
- **Framework CSS** : Bootstrap 5 personnalisé
- **JavaScript** : jQuery + modules custom
- **Responsive design** : Mobile-first approach
- **Accessibilité** : Standards WCAG 2.1

### Pages principales

#### **Dashboard utilisateur**
```html
<!-- Vue d'ensemble des campagnes actives -->
<div class="campaign-dashboard">
    @foreach(var campaign in Model.Campaigns) {
        <div class="campaign-card">
            <h3>@campaign.Name</h3>
            <p>@campaign.Description</p>
            <div class="campaign-stats">
                <span>@campaign.Characters.Count Personnages</span>
                <span>Session: @campaign.LastSession?.ToString("dd/MM/yyyy")</span>
            </div>
        </div>
    }
</div>
```

#### **Interface chat IA**
```javascript
// Chat en temps réel avec l'IA Game Master
class GameMasterChat {
    async sendMessage(message, campaignId) {
        const response = await fetch('/api/llm/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message, campaignId })
        });
        
        return await response.json();
    }
}
```

### Formulaires avancés

#### **Création de campagne**
- Wizard multi-étapes
- Validation côté client et serveur
- Intégration avec données de référence D&D
- Prévisualisation en temps réel

#### **Feuille de personnage**
- Interface complète D&D 5e
- Calculs automatiques (modificateurs, CA, etc.)
- Validation des règles
- Sauvegarde automatique

## Sécurité

### Authentification
- **ASP.NET Identity** : Gestion complète des utilisateurs
- **JWT Integration** : Communication sécurisée avec les APIs
- **Session management** : Cookies sécurisés
- **Two-factor auth** : Support 2FA (optionnel)

### Autorisation
```csharp
[Authorize]
public class CampaignController : Controller
{
    [HttpGet]
    public async Task<IActionResult> Details(int id)
    {
        // Vérification que l'utilisateur possède la campagne
        var campaign = await _campaignService.GetCampaignAsync(id);
        if (campaign.UserId != User.Identity.GetUserId())
            return Forbid();
        
        return View(campaign);
    }
}
```

### Protection CSRF
- Tokens anti-forgery automatiques
- Validation sur tous les formulaires POST
- Headers de sécurité configurés

### Validation des données
- Validation côté client (JavaScript)
- Validation côté serveur (Data Annotations)
- Sanitisation des entrées utilisateur
- Protection XSS

## Monitoring et administration

### Dashboard administrateur
- **Métriques d'utilisation** : Utilisateurs actifs, campagnes créées
- **Coûts IA** : Suivi des appels API et coûts
- **Performance** : Temps de réponse, erreurs
- **Sécurité** : Tentatives de connexion, activités suspectes

### Alertes système
```csharp
public class AIMonitoringService
{
    public async Task CheckThresholdsAsync()
    {
        var usage = await GetDailyUsageAsync();
        var thresholds = await GetAlertThresholdsAsync();
        
        if (usage.TotalCost > thresholds.DailyCostLimit)
        {
            await CreateAlertAsync("Seuil de coût quotidien dépassé");
        }
    }
}
```

### Logs structurés
- **Serilog** : Logging structuré
- **Niveaux** : Debug, Information, Warning, Error, Critical
- **Contexte** : UserId, CampaignId, Action
- **Archivage** : Rotation automatique des logs

## Performance

### Optimisations base de données
- **Entity Framework** : Lazy loading optimisé
- **Index** : Sur les requêtes fréquentes
- **Cache** : MemoryCache pour données statiques
- **Connection pooling** : Pool de connexions configuré

### Optimisations frontend
- **Bundling** : CSS/JS minifiés et groupés
- **CDN** : Ressources statiques externalisées
- **Lazy loading** : Chargement différé des images
- **Compression** : Gzip activé

### Mise en cache
```csharp
[ResponseCache(Duration = 3600, Location = ResponseCacheLocation.Client)]
public async Task<IActionResult> ReferenceData()
{
    var data = await _dataReferenceService.GetCachedDataAsync();
    return Json(data);
}
```

## Intégration avec les autres modules

### Architecture microservices
```csharp
// Communication avec LLMGameMaster
public class LLMGameMasterService : ILLMGameMasterService
{
    private readonly HttpClient _httpClient;
    
    public async Task<string> GenerateContentAsync(string prompt, CampaignContext context)
    {
        var request = new { prompt, context };
        var response = await _httpClient.PostAsJsonAsync("/api/generate", request);
        return await response.Content.ReadAsStringAsync();
    }
}
```

### Flux de données
1. **Utilisateur** → Action sur WebApp
2. **WebApp** → Appel API LLMGameMaster (via JWT)
3. **LLMGameMaster** → Requête DataReference pour contexte
4. **LLMGameMaster** → Génération contenu via LLM
5. **WebApp** → Persistance et affichage résultat

## Déploiement

### Docker
```dockerfile
FROM mcr.microsoft.com/dotnet/aspnet:8.0 AS runtime
WORKDIR /app
COPY . .
EXPOSE 80 443
ENTRYPOINT ["dotnet", "DnDGameMaster.WebApp.dll"]
```

### Configuration production
- **HTTPS** : Certificats SSL/TLS
- **Reverse proxy** : Nginx ou traefik
- **Load balancing** : Multiple instances
- **Health checks** : Monitoring automatique

### Variables d'environnement sécurisées
```bash
# Utilisation de secrets Docker/Kubernetes
docker run -d \
  --env-file /secure/webapp.env \
  --secret db_password \
  webapp:latest
```

## Tests

### Tests unitaires
```csharp
[TestClass]
public class CampaignControllerTests
{
    [TestMethod]
    public async Task CreateCampaign_ValidModel_ReturnsRedirect()
    {
        // Arrange
        var controller = new CampaignController(_mockService.Object);
        var model = new CreateCampaignViewModel { Name = "Test Campaign" };
        
        // Act
        var result = await controller.Create(model);
        
        // Assert
        Assert.IsInstanceOfType(result, typeof(RedirectToActionResult));
    }
}
```

### Tests d'intégration
```csharp
[TestClass]
public class WebApplicationTests : IClassFixture<WebApplicationFactory<Program>>
{
    [TestMethod]
    public async Task Homepage_ReturnsSuccessAndCorrectContentType()
    {
        var response = await _client.GetAsync("/");
        
        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        Assert.Equal("text/html; charset=utf-8", response.Content.Headers.ContentType.ToString());
    }
}
```

## Troubleshooting

### Problèmes courants

#### **Erreurs de connexion BDD**
```log
Error: Unable to connect to database
Solution: Vérifier les variables d'environnement et l'état du conteneur PostgreSQL
```

#### **Erreurs JWT**
```log
Error: JWT token validation failed
Solution: Vérifier la clé JWT_SECRET_KEY identique entre WebApp et LLMGameMaster
```

#### **Erreurs email**
```log
Error: Email service unavailable
Solution: Vérifier les clés API Brevo/Mailjet et la configuration SMTP
```

### Logs utiles
- `docker-compose logs webapp`
- `/app/logs/application.log`
- `/app/logs/security.log`
- Performance counters ASP.NET Core

### Debugging
```csharp
// Mode développement avec logs détaillés
if (app.Environment.IsDevelopment())
{
    app.UseDeveloperExceptionPage();
    app.UseSwagger();
    app.UseSwaggerUI();
}
```

### Health checks
```csharp
app.MapHealthChecks("/health", new HealthCheckOptions
{
    ResponseWriter = async (context, report) =>
    {
        context.Response.ContentType = "application/json";
        var response = new { status = report.Status.ToString() };
        await context.Response.WriteAsync(JsonSerializer.Serialize(response));
    }
});
```
