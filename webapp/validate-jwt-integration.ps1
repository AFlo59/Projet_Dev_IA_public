# 🔍 Script de Validation JWT - WebApp Integration
# Vérifie que l'intégration JWT est correctement configurée

Write-Host "🔍 Validation de l'intégration JWT WebApp <-> API LLM" -ForegroundColor Cyan
Write-Host "=================================================" -ForegroundColor Cyan

$errors = @()
$warnings = @()

# 1. Vérifier la configuration appsettings.json
Write-Host "`n1️⃣  Vérification de webapp/appsettings.json..." -ForegroundColor Yellow

$appsettingsPath = "appsettings.json"
if (Test-Path $appsettingsPath) {
    $appsettings = Get-Content $appsettingsPath | ConvertFrom-Json
    
    # Vérifier LLM_JWT_SECRET_KEY
    if ($appsettings.LLM_JWT_SECRET_KEY) {
        if ($appsettings.LLM_JWT_SECRET_KEY.Length -ge 32) {
            Write-Host "   ✅ LLM_JWT_SECRET_KEY configurée (${$appsettings.LLM_JWT_SECRET_KEY.Length} caractères)" -ForegroundColor Green
        } else {
            $errors += "❌ LLM_JWT_SECRET_KEY trop courte (${$appsettings.LLM_JWT_SECRET_KEY.Length} chars, minimum 32)"
        }
        
        if ($appsettings.LLM_JWT_SECRET_KEY -eq "your-very-secure-secret-key-change-this-in-production-minimum-32-characters") {
            $warnings += "⚠️  LLM_JWT_SECRET_KEY utilise la valeur par défaut - CHANGEZ-LA !"
        }
    } else {
        $errors += "❌ LLM_JWT_SECRET_KEY manquante dans appsettings.json"
    }
    
    # Vérifier LLM_ENABLE_AUTH
    if ($appsettings.LLM_ENABLE_AUTH -eq "true") {
        Write-Host "   ✅ LLM_ENABLE_AUTH activée" -ForegroundColor Green
    } else {
        $warnings += "⚠️  LLM_ENABLE_AUTH désactivée - l'authentification JWT ne sera pas utilisée"
    }
    
    # Vérifier LLM_JWT_EXPIRATION_HOURS
    if ($appsettings.LLM_JWT_EXPIRATION_HOURS) {
        Write-Host "   ✅ LLM_JWT_EXPIRATION_HOURS configurée ($($appsettings.LLM_JWT_EXPIRATION_HOURS)h)" -ForegroundColor Green
    } else {
        $warnings += "⚠️  LLM_JWT_EXPIRATION_HOURS non configurée (utilise 24h par défaut)"
    }
} else {
    $errors += "❌ Fichier webapp/appsettings.json introuvable"
}

# 2. Vérifier la configuration API LLM
Write-Host "`n2️⃣  Vérification de llmgamemaster/.env..." -ForegroundColor Yellow

$llmEnvPath = "../llmgamemaster/.env"
if (Test-Path $llmEnvPath) {
    $llmEnv = Get-Content $llmEnvPath
    
    $jwtSecretLine = $llmEnv | Where-Object { $_ -match "^JWT_SECRET_KEY=" }
    $enableAuthLine = $llmEnv | Where-Object { $_ -match "^ENABLE_AUTH=" }
    
    if ($jwtSecretLine) {
        $jwtSecret = $jwtSecretLine -replace "JWT_SECRET_KEY=", ""
        if ($jwtSecret.Length -ge 32) {
            Write-Host "   ✅ JWT_SECRET_KEY configurée dans l'API LLM ($($jwtSecret.Length) caractères)" -ForegroundColor Green
            
            # Vérifier que les clés sont identiques
            if ($appsettings -and $appsettings.LLM_JWT_SECRET_KEY -eq $jwtSecret) {
                Write-Host "   ✅ Clés JWT synchronisées entre WebApp et API LLM" -ForegroundColor Green
            } else {
                $errors += "❌ Clés JWT différentes entre WebApp et API LLM - ELLES DOIVENT ÊTRE IDENTIQUES !"
            }
        } else {
            $errors += "❌ JWT_SECRET_KEY API LLM trop courte ($($jwtSecret.Length) chars, minimum 32)"
        }
    } else {
        $errors += "❌ JWT_SECRET_KEY manquante dans llmgamemaster/.env"
    }
    
    if ($enableAuthLine) {
        $enableAuth = $enableAuthLine -replace "ENABLE_AUTH=", ""
        if ($enableAuth -eq "true") {
            Write-Host "   ✅ ENABLE_AUTH activée dans l'API LLM" -ForegroundColor Green
        } else {
            $warnings += "⚠️  ENABLE_AUTH désactivée dans l'API LLM"
        }
    } else {
        $warnings += "⚠️  ENABLE_AUTH non configurée dans l'API LLM"
    }
} else {
    $errors += "❌ Fichier llmgamemaster/.env introuvable"
}

# 3. Vérifier les fichiers de service
Write-Host "`n3️⃣  Vérification des fichiers de service..." -ForegroundColor Yellow

$requiredFiles = @(
    "Services/LLM/IJWTTokenService.cs",
    "Services/LLM/JWTTokenService.cs"
)

foreach ($file in $requiredFiles) {
    if (Test-Path $file) {
        Write-Host "   ✅ $file présent" -ForegroundColor Green
    } else {
        $errors += "❌ Fichier manquant : $file"
    }
}

# Vérifier que LLMGameMasterService.cs a été modifié
$llmServicePath = "Services/LLM/LLMGameMasterService.cs"
if (Test-Path $llmServicePath) {
    $llmServiceContent = Get-Content $llmServicePath -Raw
    if ($llmServiceContent -match "ConfigureAuthenticationAsync") {
        Write-Host "   ✅ LLMGameMasterService.cs modifié pour JWT" -ForegroundColor Green
    } else {
        $errors += "❌ LLMGameMasterService.cs non modifié pour JWT"
    }
} else {
    $errors += "❌ LLMGameMasterService.cs introuvable"
}

# 4. Vérifier le fichier de projet
Write-Host "`n4️⃣  Vérification des dépendances..." -ForegroundColor Yellow

$csprojPath = "DnDGameMaster.WebApp.csproj"
if (Test-Path $csprojPath) {
    $csprojContent = Get-Content $csprojPath -Raw
    if ($csprojContent -match "System.IdentityModel.Tokens.Jwt") {
        Write-Host "   ✅ Dépendance JWT présente dans le projet" -ForegroundColor Green
    } else {
        $errors += "❌ Dépendance System.IdentityModel.Tokens.Jwt manquante"
    }
} else {
    $errors += "❌ Fichier de projet DnDGameMaster.WebApp.csproj introuvable"
}

# 5. Résumé et recommandations
Write-Host "`n📊 RÉSUMÉ DE LA VALIDATION" -ForegroundColor Cyan
Write-Host "=========================" -ForegroundColor Cyan

if ($errors.Count -eq 0) {
    Write-Host "`n🎉 INTÉGRATION JWT VALIDÉE AVEC SUCCÈS !" -ForegroundColor Green
    Write-Host "Votre application WebApp est correctement configurée pour l'authentification JWT." -ForegroundColor Green
} else {
    Write-Host "`n❌ ERREURS DÉTECTÉES ($($errors.Count))" -ForegroundColor Red
    foreach ($error in $errors) {
        Write-Host "   $error" -ForegroundColor Red
    }
}

if ($warnings.Count -gt 0) {
    Write-Host "`n⚠️  AVERTISSEMENTS ($($warnings.Count))" -ForegroundColor Yellow
    foreach ($warning in $warnings) {
        Write-Host "   $warning" -ForegroundColor Yellow
    }
}

# Instructions suivantes
Write-Host "`n📋 PROCHAINES ÉTAPES" -ForegroundColor Cyan
Write-Host "==================" -ForegroundColor Cyan

if ($errors.Count -gt 0) {
    Write-Host "1. Corrigez les erreurs listées ci-dessus" -ForegroundColor Yellow
    Write-Host "2. Relancez ce script pour vérifier" -ForegroundColor Yellow
    Write-Host "3. Redémarrez les services : docker-compose restart" -ForegroundColor Yellow
} else {
    Write-Host "1. Redémarrez les services : docker-compose restart" -ForegroundColor Green
    Write-Host "2. Testez l'application : connectez-vous et envoyez un message à une campagne" -ForegroundColor Green
    Write-Host "3. Vérifiez les logs pour confirmer l'authentification JWT" -ForegroundColor Green
}

Write-Host "`n🔍 Validation terminée." -ForegroundColor Cyan

# Code de sortie
if ($errors.Count -gt 0) {
    exit 1
} else {
    exit 0
}
