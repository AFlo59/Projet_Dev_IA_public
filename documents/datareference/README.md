# DataReference Module

## Vue d'ensemble

Le module **DataReference** implémente une architecture ETL (Extract, Transform, Load) à deux niveaux pour traiter et exposer les données de référence D&D. Il transforme les données JSON brutes collectées par DataCollection en une base de données structurée et optimisée, puis expose ces données via une API REST sécurisée.

## Architecture

### Structure des fichiers

```
datareference/
├── README.md                 # Documentation du module
├── api.py                   # Application FastAPI principale
├── api_routes.py            # Définition des routes API
├── bronze_to_silver.py      # Script ETL Bronze → Silver
├── import_json.py           # Script ETL JSON → Bronze
├── run_etl.sh              # Script orchestrateur ETL
├── check_tables.py         # Utilitaire de vérification des tables
├── wait-for-it.sh          # Script d'attente des dépendances
├── Dockerfile.api          # Image Docker pour l'API
├── Dockerfile.etl_bronze   # Image Docker pour l'ETL Bronze
├── Dockerfile.etl_silver   # Image Docker pour l'ETL Silver
├── requirements.txt        # Dépendances Python
├── init-scripts/           # Scripts d'initialisation BDD
│   └── 01-create-readuser.sh
└── tests/                  # Tests unitaires
    ├── test_api.py
    ├── test_etl_bronze.py
    └── test_etl_silver.py
```

### Architecture à trois couches

#### 1. **Couche Bronze** (Données brutes)
- **Base de données**: `bronze_db` (PostgreSQL)
- **Port**: 5435 (externe)
- **Rôle**: Stockage des données JSON brutes importées
- **Tables**: Structure dynamique basée sur les fichiers JSON sources

#### 2. **Couche Silver** (Données transformées)
- **Base de données**: `silver_db` (PostgreSQL) 
- **Port**: 5436 (externe)
- **Rôle**: Données normalisées et optimisées pour les requêtes
- **Tables**: Structure relationnelle optimisée

#### 3. **Couche API** (Exposition des données)
- **Service**: FastAPI avec authentification JWT
- **Port**: 5000
- **Rôle**: API REST sécurisée pour accéder aux données Silver

## Fonctionnalités principales

### 1. ETL Bronze (import_json.py)
- Import des fichiers JSON depuis DataCollection ou Azure Blob Storage
- Création automatique des tables basées sur la structure JSON
- Gestion des doublons et des mises à jour
- Parallélisation configurable des imports

### 2. ETL Silver (bronze_to_silver.py)
- Transformation des données Bronze en structure relationnelle
- Normalisation et optimisation des requêtes
- Création d'index pour les performances
- Dédoublonnage et nettoyage des données

### 3. API REST (api.py + api_routes.py)
- Authentification JWT sécurisée
- Endpoints pour toutes les catégories de données D&D
- Pagination et filtrage avancé
- Documentation automatique OpenAPI/Swagger

## Configuration

### Variables d'environnement

Le module utilise ces variables (configurées via `ENV_INFOS.md`) :

```bash
# Bases de données
BRONZE_DB_NAME=bronze_db
BRONZE_DB_HOST=datareference_bronze_postgres
BRONZE_DB_EXTERNAL_PORT=5435

SILVER_DB_NAME=silver_db  
SILVER_DB_HOST=datareference_silver_postgres
SILVER_DB_EXTERNAL_PORT=5436

# Authentification (valeurs génériques documentées)
DB_ADMIN_USER=[ADMIN_USERNAME]
DB_ADMIN_PASSWORD=[ADMIN_PASSWORD]
DB_READ_USER=[READ_USERNAME] 
DB_READ_PASSWORD=[READ_PASSWORD]

# JWT et sécurité
JWT_SECRET=[JWT_SECRET_KEY]
ENABLE_AUTH=true
CORS_ORIGINS=http://localhost,https://localhost

# Azure Blob Storage (optionnel)
AZURE_BLOB_CONNECTION_STRING=[AZURE_CONNECTION]
AZURE_BLOB_CONTAINER=jsons
JSON_BLOB_PATH=data/
```

## Utilisation

### Déploiement avec Docker Compose

Le module s'intègre automatiquement dans l'orchestration globale :

```bash
# Démarrage de tous les services
docker-compose up -d

# Suivi des logs ETL
docker-compose logs -f datareference_etl_bronze
docker-compose logs -f datareference_etl_silver

# Vérification de l'API
curl http://localhost:5000/api/v1/health
```

### ETL Manuel

```bash
# ETL Bronze (JSON → PostgreSQL)
docker-compose run datareference_etl_bronze

# ETL Silver (Bronze → Silver)  
docker-compose run datareference_etl_silver

# Vérification des tables
python check_tables.py
```

### Test de l'API

```bash
# Obtention d'un token JWT
curl -X POST http://localhost:5000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"password"}'

# Requête authentifiée
curl -H "Authorization: Bearer [TOKEN]" \
  http://localhost:5000/api/v1/spells?limit=10
```

## Endpoints API

### Authentification
- `POST /api/v1/auth/login` - Connexion et obtention du token JWT
- `POST /api/v1/auth/refresh` - Renouvellement du token

### Données de référence
- `GET /api/v1/spells` - Liste des sorts avec filtres
- `GET /api/v1/bestiary` - Créatures et monstres  
- `GET /api/v1/classes` - Classes de personnages
- `GET /api/v1/races` - Races jouables
- `GET /api/v1/backgrounds` - Historiques de personnage
- `GET /api/v1/items` - Objets et équipements
- `GET /api/v1/adventures` - Modules d'aventure

### Utilitaires
- `GET /api/v1/health` - État de santé du service
- `GET /api/v1/stats` - Statistiques des données
- `GET /docs` - Documentation Swagger interactive

## Structure des données

### Tables Bronze (exemples)
```sql
-- Tables dynamiques créées automatiquement
spells_aag          -- Sorts depuis Acquisitions & Adventures Guide  
spells_phb          -- Sorts depuis Player's Handbook
bestiary_mm         -- Créatures depuis Monster Manual
bestiary_mpmm       -- Créatures depuis Mordenkainen Presents
```

### Tables Silver (optimisées)
```sql
-- Structure relationnelle normalisée
spells              -- Table unifiée des sorts
spell_components    -- Composants des sorts
spell_classes       -- Relations sort-classe
creatures          -- Table unifiée des créatures  
creature_abilities -- Capacités des créatures
classes            -- Classes de personnages
class_features     -- Capacités de classe
```

## Performance et monitoring

### Métriques ETL
- Temps d'exécution des transformations
- Nombre d'enregistrements traités
- Détection et rapport des erreurs
- Suivi des doublons évités

### Monitoring API
- Logs détaillés avec niveaux configurables
- Métriques de performance des requêtes
- Monitoring de l'authentification
- Alertes sur les erreurs critiques

### Optimisations
- Index optimisés pour les requêtes fréquentes
- Cache des résultats pour les endpoints populaires
- Pagination intelligente des gros datasets
- Compression des réponses JSON

## Sécurité

### Authentification JWT
- Tokens sécurisés avec expiration configurable
- Algorithme HS256 avec clé secrète robuste
- Refresh tokens pour les sessions longues

### Autorisation
- Utilisateur read-only pour l'API
- Séparation des privilèges admin/lecture
- Validation des entrées utilisateur

### Protection réseau
- CORS configuré pour les origines autorisées
- Rate limiting sur les endpoints sensibles
- Logs de sécurité pour audit

## Intégration avec les autres modules

### Flux de données
1. **DataCollection** → collecte les JSON sources
2. **DataReference Bronze** → import en base brute
3. **DataReference Silver** → transformation optimisée  
4. **API DataReference** → exposition sécurisée
5. **LLMGameMaster** → consommation des données de référence
6. **WebApp** → interface utilisateur et orchestration

### Dépendances
- **Amont**: DataCollection (ou Azure Blob Storage)
- **Aval**: LLMGameMaster, WebApp
- **Base de données**: PostgreSQL 14+
- **Réseau**: dnd_network (Docker)

## Maintenance

### Mises à jour des données
- Re-exécution de l'ETL Bronze lors de nouvelles versions
- Transformation incrémentale Silver pour éviter les doublons
- Validation de cohérence entre les couches

### Sauvegarde
- Volumes Docker persistants pour les données
- Scripts de sauvegarde automatisés
- Point de restauration avant les mises à jour importantes

### Monitoring proactif
- Vérification périodique de l'intégrité des données
- Alertes sur les échecs ETL
- Supervision des performances API

## Troubleshooting

### Problèmes ETL
1. **Échec import Bronze**: Vérifier la connectivité aux sources de données
2. **Transformation Silver lente**: Analyser les index et requêtes
3. **Doublons détectés**: Consulter les logs de dédoublonnage

### Problèmes API  
1. **Erreurs authentification**: Vérifier la configuration JWT
2. **Performances dégradées**: Analyser les requêtes lentes
3. **CORS bloqués**: Valider la configuration des origines

### Logs utiles
- `docker-compose logs datareference_etl_bronze`
- `docker-compose logs datareference_etl_silver`  
- `docker-compose logs datareference_api`
- Fichiers de log dans les conteneurs : `/app/logs/`
