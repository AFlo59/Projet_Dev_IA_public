#!/bin/bash
# 🔍 Script de Validation JWT - WebApp Integration
# Vérifie que l'intégration JWT est correctement configurée

echo "🔍 Validation de l'intégration JWT WebApp <-> API LLM"
echo "================================================="

errors=()
warnings=()

# Couleurs pour l'affichage
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 1. Vérifier la configuration appsettings.json
echo -e "\n1️⃣  Vérification de webapp/appsettings.json..."

if [ -f "appsettings.json" ]; then
    # Vérifier LLM_JWT_SECRET_KEY
    jwt_secret=$(grep -o '"LLM_JWT_SECRET_KEY"[^,]*' appsettings.json | cut -d'"' -f4)
    if [ ! -z "$jwt_secret" ]; then
        if [ ${#jwt_secret} -ge 32 ]; then
            echo -e "   ✅ LLM_JWT_SECRET_KEY configurée (${#jwt_secret} caractères)" | sed "s/^/    /"
        else
            errors+=("❌ LLM_JWT_SECRET_KEY trop courte (${#jwt_secret} chars, minimum 32)")
        fi
        
        if [ "$jwt_secret" == "your-very-secure-secret-key-change-this-in-production-minimum-32-characters" ]; then
            warnings+=("⚠️  LLM_JWT_SECRET_KEY utilise la valeur par défaut - CHANGEZ-LA !")
        fi
    else
        errors+=("❌ LLM_JWT_SECRET_KEY manquante dans appsettings.json")
    fi
    
    # Vérifier LLM_ENABLE_AUTH
    enable_auth=$(grep -o '"LLM_ENABLE_AUTH"[^,]*' appsettings.json | cut -d'"' -f4)
    if [ "$enable_auth" == "true" ]; then
        echo -e "   ✅ LLM_ENABLE_AUTH activée"
    else
        warnings+=("⚠️  LLM_ENABLE_AUTH désactivée - l'authentification JWT ne sera pas utilisée")
    fi
    
    # Vérifier LLM_JWT_EXPIRATION_HOURS
    expiration=$(grep -o '"LLM_JWT_EXPIRATION_HOURS"[^,]*' appsettings.json | cut -d'"' -f4)
    if [ ! -z "$expiration" ]; then
        echo -e "   ✅ LLM_JWT_EXPIRATION_HOURS configurée (${expiration}h)"
    else
        warnings+=("⚠️  LLM_JWT_EXPIRATION_HOURS non configurée (utilise 24h par défaut)")
    fi
else
    errors+=("❌ Fichier webapp/appsettings.json introuvable")
fi

# 2. Vérifier la configuration API LLM
echo -e "\n2️⃣  Vérification de llmgamemaster/.env..."

if [ -f "../llmgamemaster/.env" ]; then
    # Vérifier JWT_SECRET_KEY
    llm_jwt_secret=$(grep "^JWT_SECRET_KEY=" ../llmgamemaster/.env | cut -d'=' -f2)
    if [ ! -z "$llm_jwt_secret" ]; then
        if [ ${#llm_jwt_secret} -ge 32 ]; then
            echo -e "   ✅ JWT_SECRET_KEY configurée dans l'API LLM (${#llm_jwt_secret} caractères)"
            
            # Vérifier que les clés sont identiques
            if [ "$jwt_secret" == "$llm_jwt_secret" ]; then
                echo -e "   ✅ Clés JWT synchronisées entre WebApp et API LLM"
            else
                errors+=("❌ Clés JWT différentes entre WebApp et API LLM - ELLES DOIVENT ÊTRE IDENTIQUES !")
            fi
        else
            errors+=("❌ JWT_SECRET_KEY API LLM trop courte (${#llm_jwt_secret} chars, minimum 32)")
        fi
    else
        errors+=("❌ JWT_SECRET_KEY manquante dans llmgamemaster/.env")
    fi
    
    # Vérifier ENABLE_AUTH
    llm_enable_auth=$(grep "^ENABLE_AUTH=" ../llmgamemaster/.env | cut -d'=' -f2)
    if [ "$llm_enable_auth" == "true" ]; then
        echo -e "   ✅ ENABLE_AUTH activée dans l'API LLM"
    else
        warnings+=("⚠️  ENABLE_AUTH désactivée dans l'API LLM")
    fi
else
    errors+=("❌ Fichier llmgamemaster/.env introuvable")
fi

# 3. Vérifier les fichiers de service
echo -e "\n3️⃣  Vérification des fichiers de service..."

required_files=(
    "Services/LLM/IJWTTokenService.cs"
    "Services/LLM/JWTTokenService.cs"
)

for file in "${required_files[@]}"; do
    if [ -f "$file" ]; then
        echo -e "   ✅ $file présent"
    else
        errors+=("❌ Fichier manquant : $file")
    fi
done

# Vérifier que LLMGameMasterService.cs a été modifié
if [ -f "Services/LLM/LLMGameMasterService.cs" ]; then
    if grep -q "ConfigureAuthenticationAsync" "Services/LLM/LLMGameMasterService.cs"; then
        echo -e "   ✅ LLMGameMasterService.cs modifié pour JWT"
    else
        errors+=("❌ LLMGameMasterService.cs non modifié pour JWT")
    fi
else
    errors+=("❌ LLMGameMasterService.cs introuvable")
fi

# 4. Vérifier le fichier de projet
echo -e "\n4️⃣  Vérification des dépendances..."

if [ -f "DnDGameMaster.WebApp.csproj" ]; then
    if grep -q "System.IdentityModel.Tokens.Jwt" "DnDGameMaster.WebApp.csproj"; then
        echo -e "   ✅ Dépendance JWT présente dans le projet"
    else
        errors+=("❌ Dépendance System.IdentityModel.Tokens.Jwt manquante")
    fi
else
    errors+=("❌ Fichier de projet DnDGameMaster.WebApp.csproj introuvable")
fi

# 5. Résumé et recommandations
echo -e "\n📊 RÉSUMÉ DE LA VALIDATION"
echo "========================="

if [ ${#errors[@]} -eq 0 ]; then
    echo -e "\n🎉 ${GREEN}INTÉGRATION JWT VALIDÉE AVEC SUCCÈS !${NC}"
    echo -e "${GREEN}Votre application WebApp est correctement configurée pour l'authentification JWT.${NC}"
else
    echo -e "\n❌ ${RED}ERREURS DÉTECTÉES (${#errors[@]})${NC}"
    for error in "${errors[@]}"; do
        echo -e "   ${RED}$error${NC}"
    done
fi

if [ ${#warnings[@]} -gt 0 ]; then
    echo -e "\n⚠️  ${YELLOW}AVERTISSEMENTS (${#warnings[@]})${NC}"
    for warning in "${warnings[@]}"; do
        echo -e "   ${YELLOW}$warning${NC}"
    done
fi

# Instructions suivantes
echo -e "\n📋 PROCHAINES ÉTAPES"
echo "=================="

if [ ${#errors[@]} -gt 0 ]; then
    echo -e "${YELLOW}1. Corrigez les erreurs listées ci-dessus${NC}"
    echo -e "${YELLOW}2. Relancez ce script pour vérifier${NC}"
    echo -e "${YELLOW}3. Redémarrez les services : docker-compose restart${NC}"
else
    echo -e "${GREEN}1. Redémarrez les services : docker-compose restart${NC}"
    echo -e "${GREEN}2. Testez l'application : connectez-vous et envoyez un message à une campagne${NC}"
    echo -e "${GREEN}3. Vérifiez les logs pour confirmer l'authentification JWT${NC}"
fi

echo -e "\n🔍 Validation terminée."

# Code de sortie
if [ ${#errors[@]} -gt 0 ]; then
    exit 1
else
    exit 0
fi
