#!/usr/bin/env python3
"""
Script de vérification de la configuration LLM
Vérifie que OpenAI est bien configuré par défaut
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def check_config():
    """Vérifie la configuration LLM"""
    print("🔍 Vérification de la configuration LLM...")
    print("=" * 50)
    
    # Check LLM Provider
    llm_provider = os.getenv("LLM_PROVIDER", "openai")
    print(f"📋 LLM Provider: {llm_provider}")
    
    if llm_provider == "openai":
        print("✅ OpenAI configuré comme provider par défaut")
    else:
        print(f"⚠️  Provider actuel: {llm_provider} (pas OpenAI)")
    
    # Check OpenAI configuration
    openai_key = os.getenv("OPEN_AI_KEY", "")
    openai_model = os.getenv("OPEN_AI_MODEL", "gpt-4o")
    openai_max_token = os.getenv("OPEN_AI_MAX_TOKEN", "20000")
    
    print(f"\n🤖 Configuration OpenAI:")
    print(f"   • Clé API: {'✅ Configurée' if openai_key else '❌ Manquante'}")
    print(f"   • Modèle: {openai_model}")
    print(f"   • Max tokens: {openai_max_token}")
    
    # Check Anthropic configuration
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
    anthropic_model = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20240620")
    
    print(f"\n🧠 Configuration Anthropic:")
    print(f"   • Clé API: {'✅ Configurée' if anthropic_key else '❌ Manquante'}")
    print(f"   • Modèle: {anthropic_model}")
    
    # Test OpenAI import
    try:
        import openai
        print(f"\n📦 OpenAI Version: {openai.__version__}")
        if openai.__version__.startswith("0.28"):
            print("✅ Version OpenAI compatible (ancienne API)")
        else:
            print("⚠️  Version OpenAI pourrait être incompatible")
    except ImportError:
        print("\n❌ OpenAI non installé")
    
    # Test Anthropic import
    try:
        import anthropic
        print(f"📦 Anthropic Version: {anthropic.__version__}")
    except ImportError:
        print("❌ Anthropic non installé")
    
    print("\n" + "=" * 50)
    if llm_provider == "openai" and openai_key:
        print("🎉 Configuration OpenAI prête pour la génération !")
    else:
        print("⚠️  Problèmes de configuration détectés")

if __name__ == "__main__":
    check_config() 