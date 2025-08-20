# DataCollection Module

## Vue d'ensemble

Le module **DataCollection** est responsable de la collecte automatisée des données de référence D&D depuis le dépôt GitHub officiel `5etools-mirror-3/5etools-src`. Il télécharge et organise les fichiers JSON contenant les règles, monstres, sorts, et autres éléments de jeu, ainsi que les images associées.

## Architecture

### Structure des fichiers

```
datacollection/
├── download_local.py        # Script de téléchargement LOCAL uniquement
├── download_blob.py         # Script de téléchargement + upload Azure Blob
├── azure_blob_setup.py      # Configuration Azure Blob Storage
├── docker-compose.yml       # Configuration Docker pour le module
├── Dockerfile               # Image Docker pour l'exécution
├── requirements.txt         # Dépendances Python
├── env.example             # Template de configuration (.env)
├── .gitignore              # Exclusions Git (données, logs, secrets)
└── Output/                 # Répertoire de sortie (exclu du Git)
    ├── data/               # Fichiers JSON organisés par catégorie
    └── images/             # Images organisées par source
```

### Fonctionnalités principales

1. **Téléchargement intelligent**
   - **Mise à jour seulement si nécessaire** : Comparaison MD5 pour les fichiers JSON
   - **Skip automatique** : Évite de re-télécharger les images existantes
   - Récupération des fichiers JSON depuis le dépôt GitHub `5etools-src`
   - Téléchargement des images depuis `5e.tools/img`
   - Préservation de la structure hiérarchique des dossiers

2. **Deux modes de fonctionnement**
   - **`download_local.py`** : Stockage local uniquement (rapide pour développement)
   - **`download_blob.py`** : Stockage local + upload Azure Blob Storage (production)
   - Arguments `--json` et `--images` (par défaut : les deux)

3. **Configuration flexible**
   - **Variables d'environnement** : Toute la configuration via `.env`
   - Sources GitHub configurables (`GITHUB_OWNER`, `GITHUB_REPO`, etc.)
   - URLs et répertoires personnalisables

4. **Gestion d'erreurs et retry**
   - Retry automatique sur les erreurs réseau temporaires
   - Logging détaillé des opérations
   - Gestion des timeouts et erreurs SSL

## Configuration

### Variables d'environnement

Le module utilise un fichier `.env` pour toute la configuration. Copiez `env.example` vers `.env` et personnalisez :

```bash
# Configuration Azure Blob Storage (pour download_blob.py)
AZURE__Blob__ConnectionString=DefaultEndpointsProtocol=https;AccountName=...
AZURE__Blob__JsonContainer=jsons
AZURE__Blob__ImageContainer=images

# Configuration GitHub (personnalisable)
GITHUB_OWNER=5etools-mirror-3
GITHUB_REPO=5etools-src
GITHUB_BRANCH=main

# Configuration URLs et répertoires
SITE_IMG_BASE=https://5e.tools/img
OUTPUT_DIR=Output
LOGS_DIR=Logs
```

### Configuration par défaut

Si aucune variable n'est définie, le module utilise des valeurs par défaut sensées :
- **Repository**: `5etools-mirror-3/5etools-src`
- **Branch**: `main`
- **Base URL images**: `https://5e.tools/img`
- **Répertoires**: `Output/` et `Logs/`

## Utilisation

### Prérequis

1. **Configuration** : Copiez `env.example` vers `.env` et configurez vos variables
2. **Dépendances** : `pip install -r requirements.txt`

### Exécution locale

#### Mode local uniquement (développement)
```bash
# Par défaut : télécharge JSON + images
python download_local.py

# Seulement les JSON
python download_local.py --json

# Seulement les images  
python download_local.py --images

# Les deux explicitement
python download_local.py --json --images
```

#### Mode avec Azure Blob Storage (production)
```bash
# Par défaut : télécharge JSON + images + upload Azure
python download_blob.py

# Options spécifiques disponibles
python download_blob.py --json    # JSON seulement
python download_blob.py --images  # Images seulement
```

### Exécution avec Docker

```bash
# Construction de l'image
docker build -t datacollection .

# Exécution (par défaut = download_blob.py)
docker run --env-file .env -v $(pwd)/Output:/app/Output datacollection

# Avec docker-compose
docker-compose up datacollection
```

### Intégration Docker Compose

Le module s'intègre dans l'architecture globale et utilise `env_file: - .env` pour la configuration sécurisée.

## Données collectées

### Fichiers JSON
- **Actions**: Actions de combat et capacités spéciales
- **Adventures**: Modules d'aventure officiels  
- **Backgrounds**: Historiques de personnage
- **Bestiary**: Créatures et monstres
- **Classes**: Classes de personnage et sous-classes
- **Spells**: Sorts et cantrips
- **Books**: Livres et suppléments officiels

### Images
- Images de créatures organisées par source (MM, MPMM, etc.)
- Images de races, classes, et objets
- Illustrations d'aventures et de lieux

## Sortie des données

Les données sont organisées dans le répertoire `Output/` :

```
Output/
├── data/
│   ├── bestiary/            # Créatures par livre source
│   ├── spells/              # Sorts par source
│   ├── class/               # Classes et sous-classes
│   ├── adventures/          # Modules d'aventure
│   └── [autres catégories]
└── images/
    ├── bestiary/            # Images de créatures
    ├── races/               # Images de races
    ├── classes/             # Images de classes
    └── [autres catégories]
```

## Logging et monitoring

- Logs détaillés dans le répertoire `Logs/`
- Suivi des téléchargements réussis/échoués
- Métriques de performance (temps de téléchargement, taille des fichiers)

## Dépendances

### Python (requirements.txt)
- `requests` : Requêtes HTTP avec retry automatique
- `python-dotenv` : Gestion des variables d'environnement
- `azure-storage-blob` : Support Azure Blob Storage (pour download_blob.py)

### Système
- Python 3.10+
- Docker (optionnel)
- Accès internet pour GitHub API et 5e.tools CDN

## Performance et optimisations

### Mise à jour intelligente
- **JSON** : Comparaison MD5 des contenus (skip si identique)
- **Images** : Vérification d'existence (skip si présent)
- **Azure Blob** : Upload seulement si fichier mis à jour localement

### Logs et monitoring
- Logs séparés par type de contenu (`JsonScraper`, `ImageScraper`)
- Compteurs de fichiers traités vs skippés
- Temps d'exécution détaillé par opération

### Gestion mémoire
- Streaming pour gros fichiers images
- Téléchargement JSON en mémoire pour comparaison hash

## Intégration avec les autres modules

Les données collectées alimentent la chaîne ETL :
1. **DataCollection** → Collecte les données brutes
2. **DataReference (Bronze)** → Import des données en base
3. **DataReference (Silver)** → Transformation et optimisation
4. **LLMGameMaster** → Utilisation des données de référence

## Maintenance

### Mise à jour des sources
- Vérification régulière des nouvelles versions du dépôt source
- Adaptation aux changements de structure des données
- Test de compatibilité avec les modules suivants

### Performance
- Optimisation des requêtes réseau (retry intelligent)
- Gestion de la bande passante
- Évitement de la surcharge du serveur source
- Skip automatique des fichiers non modifiés

## Sécurité

### Protection des données sensibles
- **Variables d'environnement** : Configuration via `.env` (exclu du Git)
- **Clés Azure** : Stockage sécurisé, jamais en dur dans le code
- **GitHub API** : Utilisation de l'API publique, pas de tokens requis

### Bonnes pratiques
- `.gitignore` configuré pour exclure `.env`, données téléchargées
- Validation des URLs et chemins avant téléchargement  
- Gestion d'erreurs robuste (pas d'exposition d'informations sensibles)

## Troubleshooting

### Erreurs communes
1. **Erreurs de configuration** : Vérifier que `.env` existe et est correctement formaté
2. **Erreurs Azure Blob** : Vérifier la clé de connexion dans `.env`
3. **Erreurs réseau** : Vérifier la connectivité GitHub et 5e.tools
4. **Espace disque** : S'assurer d'avoir suffisamment d'espace libre
5. **Permissions** : Vérifier les droits d'écriture sur les répertoires

### Logs utiles
- **JSON** : `Logs/JsonScraper.log`
- **Images** : `Logs/ImageScraper.log`  
- Chercher `SKIP` pour voir les fichiers non re-téléchargés
- Chercher `ERROR` pour identifier les problèmes
- Analyser les temps de réponse pour détecter les lenteurs

### Commandes de diagnostic
```bash
# Vérifier la configuration
python -c "from dotenv import load_dotenv; load_dotenv(); import os; print('GitHub:', os.getenv('GITHUB_OWNER', 'DEFAULT'))"

# Test de connectivité
python -c "import requests; print(requests.get('https://api.github.com/repos/5etools-mirror-3/5etools-src').status_code)"

# Vérifier les permissions
python -c "import os; print('Output writable:', os.access('Output', os.W_OK))"
```
