# LLMGameMaster Module

## Vue d'ensemble

Le module **LLMGameMaster** est le cœur intelligent du système D&D GameMaster AI. Il fournit une interface d'intelligence artificielle basée sur les grands modèles de langage (LLM) pour générer du contenu narratif, gérer les campagnes, et assister les maîtres de jeu dans leurs parties de D&D.

## Architecture

### Structure des fichiers

```
llmgamemaster/
├── README.md                    # Documentation du module
├── app.py                      # Application FastAPI principale (2593 lignes)
├── config.py                   # Configuration centralisée
├── auth.py                     # Système d'authentification
├── auth_routes.py              # Routes d'authentification
├── llm_service.py              # Service LLM (OpenAI/Anthropic)
├── db_service.py               # Service base de données (1261 lignes)
├── element_manager.py          # Gestionnaire d'éléments de campagne
├── utils.py                    # Utilitaires et helpers
├── async_utils.py              # Utilitaires asynchrones
├── image_storage_service.py    # Gestion du stockage d'images
├── static_files_middleware.py  # Middleware pour fichiers statiques
├── verify_config.py            # Validation de configuration
├── Dockerfile                  # Image Docker
├── requirements.txt            # Dépendances Python
├── SECURITY_SETUP.md          # Guide de sécurité
├── MIGRATION_SECURITY.md      # Guide migration sécurisée
├── static/                    # Fichiers statiques (images générées)
├── templates/                 # Templates Jinja2 pour génération
└── tests/                     # Tests unitaires
    ├── test_app.py
    ├── test_auth.py
    └── test_image_storage.py
```

## Fonctionnalités principales

### 1. Génération de contenu narratif
- **Descriptions d'environnements** : Lieux, tavernes, donjons
- **Personnages non-joueurs (PNJ)** : Caractéristiques, motivations, dialogues
- **Événements et quêtes** : Hooks, complications, résolutions
- **Ambiance et immersion** : Descriptions sensorielles détaillées

### 2. Gestion de campagnes
- **Création et configuration** de nouvelles campagnes
- **Suivi de l'état** : session courante, progression
- **Persistance des données** : historique, personnages, lieux
- **Synchronisation** avec l'application web

### 3. Support multi-LLM
- **OpenAI GPT-4o** : Modèle principal recommandé
- **Anthropic Claude** : Alternative robuste
- **Configuration flexible** : Switch entre providers
- **Optimisation des prompts** : Adaptés à chaque modèle

### 4. Gestion d'images
- **Génération d'images** : Via DALL-E (OpenAI)
- **Stockage persistant** : Système de fichiers local
- **Optimisation** : Compression et redimensionnement
- **Sécurité** : Validation et sandboxing des uploads

## Configuration

### Variables d'environnement

Le module utilise ces variables (configurées via `ENV_INFOS.md`) :

```bash
# Base de données Silver (lecture seule)
SILVER_DB_HOST=datareference_silver_postgres
SILVER_DB_NAME=silver_db
DB_READ_USER=[READ_USERNAME]
DB_READ_PASSWORD=[READ_PASSWORD]

# Base de données App (écriture)
APP_DB_HOST=webapp_postgres
APP_DB_NAME=app_db
GAME_DB_USER=[GAME_USERNAME]
GAME_DB_PASSWORD=[GAME_PASSWORD]

# LLM Provider Configuration
LLM_PROVIDER=openai

# OpenAI Configuration
OPEN_AI_KEY=[API_KEY]
OPEN_AI_MODEL=gpt-4o
OPEN_AI_MAX_TOKEN=13000

# Anthropic Configuration (alternative)
ANTHROPIC_API_KEY=[API_KEY]
ANTHROPIC_MODEL=claude-3-5-sonnet-20240620
ANTHROPIC_MAX_TOKEN=20000

# Configuration stockage images
IMAGE_STORAGE_PATH=static
BASE_IMAGE_URL=http://localhost:5001
```

### Configuration des modèles

Le service supporte plusieurs configurations LLM :

```python
# Modèles OpenAI supportés
OPENAI_MODELS = [
    "gpt-4o",           # Recommandé
    "gpt-4",            # Performance élevée  
    "gpt-3.5-turbo"     # Économique
]

# Modèles Anthropic supportés
ANTHROPIC_MODELS = [
    "claude-3-5-sonnet-20240620",  # Recommandé
    "claude-3-sonnet-20240229",    # Alternative
    "claude-3-haiku-20240307"      # Rapide
]
```

## API Endpoints

### Authentification
- `POST /api/auth/login` - Connexion utilisateur
- `POST /api/auth/refresh` - Renouvellement token
- `GET /api/auth/user` - Informations utilisateur courant

### Campagnes
- `GET /api/campaigns` - Liste des campagnes utilisateur
- `POST /api/campaigns` - Création nouvelle campagne
- `GET /api/campaigns/{id}` - Détails campagne
- `PUT /api/campaigns/{id}` - Mise à jour campagne
- `DELETE /api/campaigns/{id}` - Suppression campagne

### Génération de contenu
- `POST /api/generate/location` - Génération de lieu
- `POST /api/generate/npc` - Génération de PNJ
- `POST /api/generate/quest` - Génération de quête
- `POST /api/generate/event` - Génération d'événement
- `POST /api/generate/description` - Description libre

### Éléments de campagne
- `GET /api/elements/{campaign_id}` - Liste des éléments
- `POST /api/elements` - Création d'élément
- `PUT /api/elements/{id}` - Mise à jour élément
- `DELETE /api/elements/{id}` - Suppression élément

### Images
- `POST /api/images/generate` - Génération d'image IA
- `GET /api/images/{filename}` - Récupération d'image
- `DELETE /api/images/{filename}` - Suppression d'image

### Chat/Discussion
- `POST /api/chat` - Interaction conversationnelle avec l'IA
- `GET /api/chat/history/{campaign_id}` - Historique des conversations

## Architecture technique

### Services principaux

#### 1. **LLMService** (llm_service.py)
```python
class LLMService:
    def __init__(self, provider: str = "openai")
    async def generate_content(self, prompt: str, context: dict)
    async def generate_image(self, description: str)
    def format_context(self, campaign_data: dict, character_data: list)
```

#### 2. **DBService** (db_service.py)
```python
class DBService:
    async def get_silver_connection()  # Lecture données référence
    async def get_app_connection()     # Écriture données jeu
    async def create_campaign(campaign_data: dict)
    async def get_campaign_context(campaign_id: int)
```

#### 3. **ElementManager** (element_manager.py)
```python
class ElementManager:
    async def create_element(element_data: dict)
    async def update_element(element_id: int, updates: dict)
    async def get_campaign_elements(campaign_id: int)
    async def sync_with_webapp(campaign_id: int)
```

### Architecture asynchrone

Le service utilise FastAPI avec support asynchrone complet :

```python
# Traitement parallèle des requêtes LLM
async with aiohttp.ClientSession() as session:
    tasks = [
        generate_location_description(context),
        generate_npc_dialogue(context),
        generate_quest_hooks(context)
    ]
    results = await asyncio.gather(*tasks)
```

## Prompts et contexte

### Structure des prompts

Le service utilise des prompts sophistiqués avec contexte D&D :

```python
def build_context_prompt(campaign_data, character_data, reference_data):
    """
    Construit un prompt contextualisé incluant :
    - Informations de campagne (thème, niveau, progression)
    - Données des personnages (races, classes, historiques)  
    - Données de référence D&D (sorts, monstres, règles)
    - Historique des interactions précédentes
    """
```

### Optimisations de performance

- **Cache des prompts** : Évite la régénération identique
- **Compression du contexte** : Réduction de la taille des prompts
- **Parallélisation** : Requêtes LLM simultanées quand possible
- **Retry intelligent** : Gestion des erreurs temporaires

## Gestion des données

### Base Silver (lecture seule)
```sql
-- Accès aux données de référence D&D
SELECT * FROM spells WHERE level <= 3;
SELECT * FROM creatures WHERE challenge_rating <= 5;
SELECT * FROM classes WHERE name = 'Wizard';
```

### Base App (lecture/écriture)
```sql
-- Gestion des campagnes et éléments générés
campaigns, characters, campaign_elements,
locations, npcs, quests, chat_history
```

### Synchronisation

Le service maintient la cohérence entre :
- Données générées par l'IA (LLMGameMaster)
- Interface utilisateur (WebApp)
- Persistance des états de campagne

## Performance et monitoring

### Métriques LLM
- Temps de réponse par provider
- Utilisation des tokens (coût)
- Taux de succès/échec des requêtes
- Qualité des réponses générées

### Monitoring système
- Consommation mémoire (cache des contextes)
- Utilisation CPU (traitement asynchrone)
- Stockage images (espace disque)
- Connexions base de données

### Optimisations
- Cache Redis pour les contextes fréquents (à implémenter)
- Compression des images générées
- Pool de connexions DB optimisé
- Rate limiting intelligent par utilisateur

## Sécurité

### Authentification
- JWT tokens avec expiration
- Validation des permissions par campagne
- Isolation des données utilisateur

### Validation des entrées
- Sanitisation des prompts utilisateur
- Validation des paramètres de génération
- Protection contre l'injection de prompts

### Protection des clés API
- Variables d'environnement sécurisées
- Rotation périodique des clés
- Monitoring des quotas et coûts

## Intégration avec les autres modules

### Flux de données
1. **WebApp** → Demande de génération via API
2. **LLMGameMaster** → Requête contexte depuis DataReference
3. **LLMGameMaster** → Génération contenu via LLM
4. **LLMGameMaster** → Persistance en base App
5. **WebApp** → Affichage du contenu généré

### Dépendances
- **DataReference API** : Données de référence D&D
- **PostgreSQL** : Stockage des campagnes et éléments
- **OpenAI/Anthropic APIs** : Génération de contenu
- **Système de fichiers** : Stockage des images

## Déploiement

### Docker
```bash
# Construction de l'image
docker build -t llmgamemaster .

# Exécution avec variables d'environnement
docker run -p 5001:5001 \
  -e OPEN_AI_KEY=[KEY] \
  -e SILVER_DB_HOST=postgres \
  llmgamemaster
```

### Docker Compose
Le service s'intègre dans l'orchestration globale :

```yaml
llm_gamemaster:
  build: ./llmgamemaster
  ports:
    - "5001:5001"
  environment:
    - LLM_PROVIDER=openai
    - OPEN_AI_KEY=[MASKED]
  depends_on:
    - datareference_api
    - webapp_postgres
```

## Tests et qualité

### Tests unitaires
```bash
# Exécution des tests
python -m pytest tests/

# Tests spécifiques
python -m pytest tests/test_llm_service.py
python -m pytest tests/test_auth.py
```

### Tests d'intégration
- Validation de la génération de contenu
- Test des APIs avec authentification
- Vérification de la persistance des données

### Qualité du contenu généré
- Validation de la cohérence D&D
- Test de la créativité et variabilité
- Vérification du respect du contexte

## Troubleshooting

### Problèmes LLM
1. **Erreurs API** : Vérifier les clés et quotas
2. **Réponses incohérentes** : Ajuster les prompts et température
3. **Latence élevée** : Optimiser la taille des prompts

### Problèmes de base de données
1. **Connexions échouées** : Vérifier la configuration réseau
2. **Permissions insuffisantes** : Contrôler les utilisateurs DB
3. **Données manquantes** : Vérifier le statut DataReference

### Problèmes d'images
1. **Stockage plein** : Nettoyer les images anciennes
2. **Génération échouée** : Vérifier DALL-E API
3. **Performances** : Optimiser la compression

### Logs utiles
- `/app/logs/llm_service.log`
- `/app/logs/db_operations.log`
- `/app/logs/auth.log`
- `docker-compose logs llm_gamemaster`
