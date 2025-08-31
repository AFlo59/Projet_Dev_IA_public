# Script de vérification de la configuration JWT
# Vérifie que toutes les variables JWT sont cohérentes entre les services

Write-Host "🔐 Vérification de la configuration JWT..." -ForegroundColor Cyan
Write-Host ""

# Vérifier si le fichier .env existe
if (Test-Path ".env") {
    Write-Host "✅ Fichier .env trouvé" -ForegroundColor Green
    
    # Lire le fichier .env
    $envContent = Get-Content ".env" | Where-Object { $_ -match "^JWT_|^LLM_JWT_" }
    
    Write-Host "📋 Variables JWT trouvées dans .env :" -ForegroundColor Yellow
    $envContent | ForEach-Object { Write-Host "   $_" -ForegroundColor Gray }
    
    # Extraire les valeurs
    $jwtSecret = ($envContent | Where-Object { $_ -match "^JWT_SECRET_KEY=" }) -replace "JWT_SECRET_KEY=", ""
    $llmJwtSecret = ($envContent | Where-Object { $_ -match "^LLM_JWT_SECRET_KEY=" }) -replace "LLM_JWT_SECRET_KEY=", ""
    
    Write-Host ""
    Write-Host "🔍 Analyse des valeurs :" -ForegroundColor Yellow
    Write-Host "   JWT_SECRET_KEY: $jwtSecret" -ForegroundColor Gray
    Write-Host "   LLM_JWT_SECRET_KEY: $llmJwtSecret" -ForegroundColor Gray
    
    # Vérifier la cohérence
    if ($jwtSecret -eq $llmJwtSecret -and $jwtSecret -ne "") {
        Write-Host ""
        Write-Host "✅ Configuration JWT cohérente !" -ForegroundColor Green
        Write-Host "   Les deux services utilisent la même clé secrète."
    } else {
        Write-Host ""
        Write-Host "❌ Configuration JWT INCOHÉRENTE !" -ForegroundColor Red
        Write-Host "   Les services utilisent des clés différentes."
        Write-Host ""
        Write-Host "🔧 Pour corriger :" -ForegroundColor Yellow
        Write-Host "   1. Assurez-vous que JWT_SECRET_KEY = LLM_JWT_SECRET_KEY dans .env"
        Write-Host "   2. Redémarrez les conteneurs Docker"
    }
} else {
    Write-Host "❌ Fichier .env non trouvé" -ForegroundColor Red
    Write-Host "   Créez un fichier .env à la racine du projet avec :"
    Write-Host "   JWT_SECRET_KEY=votre_cle_secrete_ici"
    Write-Host "   LLM_JWT_SECRET_KEY=votre_cle_secrete_ici"
}

Write-Host ""
Write-Host "📝 Vérification de docker-compose.yml..." -ForegroundColor Cyan

# Vérifier docker-compose.yml
if (Test-Path "docker-compose.yml") {
    $dockerCompose = Get-Content "docker-compose.yml"
    
    $webappJwt = ($dockerCompose | Where-Object { $_ -match "LLM_JWT_SECRET_KEY:" }) -replace ".*LLM_JWT_SECRET_KEY:\s*\$\{([^}]+)\}.*", '$1'
    $llmJwt = ($dockerCompose | Where-Object { $_ -match "JWT_SECRET_KEY:" } | Select-Object -First 1) -replace ".*JWT_SECRET_KEY:\s*\$\{([^}]+)\}.*", '$1'
    
    Write-Host "   WebApp utilise: $webappJwt" -ForegroundColor Gray
    Write-Host "   LLMGameMaster utilise: $llmJwt" -ForegroundColor Gray
    
    if ($webappJwt -eq $llmJwt) {
        Write-Host "✅ Configuration docker-compose.yml cohérente" -ForegroundColor Green
    } else {
        Write-Host "❌ Configuration docker-compose.yml incohérente" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "🎯 Résumé des actions à effectuer :" -ForegroundColor Cyan
Write-Host "   1. Vérifiez que JWT_SECRET_KEY = LLM_JWT_SECRET_KEY dans .env"
Write-Host "   2. Redémarrez les conteneurs : docker-compose down && docker-compose up -d"
Write-Host "   3. Vérifiez les logs pour confirmer l'authentification JWT"
