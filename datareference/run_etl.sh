#!/bin/bash

# 🔄 Script de gestion des ETL DataReference
# Usage: ./run_etl.sh [bronze|silver|all] [--force]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if container exists and its status
check_container_status() {
    local container_name=$1
    local status=$(docker inspect --format '{{.State.Status}}' $container_name 2>/dev/null || echo "not_found")
    echo $status
}

# Function to check if databases are ready
check_databases() {
    print_status "Vérification de la disponibilité des bases de données..."
    
    # Check bronze database
    local bronze_status=$(docker exec datareference_bronze_postgres pg_isready -U ${DB_ADMIN_USER:-postgres} -d bronze_db 2>/dev/null && echo "ready" || echo "not_ready")
    if [ "$bronze_status" != "ready" ]; then
        print_error "Base de données Bronze non disponible"
        return 1
    fi
    
    # Check silver database  
    local silver_status=$(docker exec datareference_silver_postgres pg_isready -U ${DB_ADMIN_USER:-postgres} -d silver_db 2>/dev/null && echo "ready" || echo "not_ready")
    if [ "$silver_status" != "ready" ]; then
        print_error "Base de données Silver non disponible"
        return 1
    fi
    
    print_success "Bases de données disponibles"
    return 0
}

# Function to run bronze ETL
run_bronze_etl() {
    local force=$1
    print_status "Lancement de l'ETL Bronze (JSON -> Bronze DB)..."
    
    # Check if container already ran successfully
    local bronze_status=$(check_container_status "datareference_etl_bronze")
    
    if [ "$bronze_status" = "exited" ] && [ "$force" != "--force" ]; then
        print_warning "ETL Bronze déjà exécuté. Le script a une logique anti-duplication intégrée."
        print_warning "Utilisez --force pour forcer la ré-exécution."
        return 0
    fi
    
    # Remove existing container if it exists
    if [ "$bronze_status" != "not_found" ]; then
        print_status "Suppression du conteneur ETL Bronze existant..."
        docker rm -f datareference_etl_bronze >/dev/null 2>&1 || true
    fi
    
    # Run bronze ETL
    cd "$PROJECT_ROOT"
    print_status "Démarrage de l'ETL Bronze..."
    docker-compose up --build datareference_etl_bronze
    
    # Check result
    local exit_code=$(docker inspect --format '{{.State.ExitCode}}' datareference_etl_bronze 2>/dev/null || echo "1")
    if [ "$exit_code" = "0" ]; then
        print_success "ETL Bronze terminé avec succès"
        return 0
    else
        print_error "ETL Bronze a échoué (code: $exit_code)"
        return 1
    fi
}

# Function to run silver ETL
run_silver_etl() {
    local force=$1
    print_status "Lancement de l'ETL Silver (Bronze -> Silver DB)..."
    
    # Check if container already ran successfully
    local silver_status=$(check_container_status "datareference_etl_silver")
    
    if [ "$silver_status" = "exited" ] && [ "$force" != "--force" ]; then
        print_warning "ETL Silver déjà exécuté. Le script a une logique anti-duplication intégrée."
        print_warning "Utilisez --force pour forcer la ré-exécution."
        return 0
    fi
    
    # Remove existing container if it exists
    if [ "$silver_status" != "not_found" ]; then
        print_status "Suppression du conteneur ETL Silver existant..."
        docker rm -f datareference_etl_silver >/dev/null 2>&1 || true
    fi
    
    # Run silver ETL
    cd "$PROJECT_ROOT"
    print_status "Démarrage de l'ETL Silver..."
    docker-compose up --build datareference_etl_silver
    
    # Check result
    local exit_code=$(docker inspect --format '{{.State.ExitCode}}' datareference_etl_silver 2>/dev/null || echo "1")
    if [ "$exit_code" = "0" ]; then
        print_success "ETL Silver terminé avec succès"
        return 0
    else
        print_error "ETL Silver a échoué (code: $exit_code)"
        return 1
    fi
}

# Function to show ETL status
show_etl_status() {
    print_status "État des conteneurs ETL:"
    
    local bronze_status=$(check_container_status "datareference_etl_bronze")
    local silver_status=$(check_container_status "datareference_etl_silver")
    
    echo "  📦 ETL Bronze: $bronze_status"
    echo "  📦 ETL Silver: $silver_status"
    
    # Show logs tail if containers exist
    if [ "$bronze_status" != "not_found" ]; then
        echo ""
        print_status "Dernières lignes des logs ETL Bronze:"
        docker logs --tail 5 datareference_etl_bronze 2>/dev/null || print_warning "Aucun log disponible"
    fi
    
    if [ "$silver_status" != "not_found" ]; then
        echo ""
        print_status "Dernières lignes des logs ETL Silver:"
        docker logs --tail 5 datareference_etl_silver 2>/dev/null || print_warning "Aucun log disponible"
    fi
}

# Main function
main() {
    local action=${1:-"all"}
    local force=${2:-""}
    
    echo "🔄 Script de gestion des ETL DataReference"
    echo "========================================"
    
    case $action in
        "bronze")
            if ! check_databases; then
                exit 1
            fi
            run_bronze_etl $force
            ;;
        "silver")
            if ! check_databases; then
                exit 1
            fi
            run_silver_etl $force
            ;;
        "all")
            if ! check_databases; then
                exit 1
            fi
            if run_bronze_etl $force; then
                run_silver_etl $force
            else
                print_error "ETL Bronze a échoué, arrêt de la chaîne"
                exit 1
            fi
            ;;
        "status")
            show_etl_status
            ;;
        "help"|"--help"|"-h")
            echo "Usage: $0 [bronze|silver|all|status] [--force]"
            echo ""
            echo "Commandes:"
            echo "  bronze    - Lance uniquement l'ETL Bronze (JSON -> Bronze DB)"
            echo "  silver    - Lance uniquement l'ETL Silver (Bronze -> Silver DB)"
            echo "  all       - Lance les deux ETL dans l'ordre (défaut)"
            echo "  status    - Affiche l'état des conteneurs ETL"
            echo ""
            echo "Options:"
            echo "  --force   - Force la ré-exécution même si déjà fait"
            echo ""
            echo "Les scripts ETL ont une logique anti-duplication intégrée."
            ;;
        *)
            print_error "Action inconnue: $action"
            echo "Utilisez '$0 help' pour voir l'aide"
            exit 1
            ;;
    esac
}

# Check if script is run directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi 