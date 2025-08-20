"""
Tests pour le module LLM Service (llm_service.py)
Test des services d'intelligence artificielle
"""

import pytest
import asyncio
import os
import sys
from unittest.mock import patch, MagicMock, AsyncMock

# Ajouter le répertoire parent au path pour les imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm_service import (
    LLMService,
    OpenAIService,
    AnthropicService,
    LLMConfig,
    LLMResponse
)

class TestLLMService:
    """Tests pour le service LLM principal"""
    
    @pytest.fixture
    def llm_config(self):
        """Configuration de test pour LLM"""
        return LLMConfig(
            openai_api_key="test_openai_key",
            openai_model="gpt-4",
            openai_max_tokens=1000,
            anthropic_api_key="test_anthropic_key",
            anthropic_model="claude-3-sonnet",
            anthropic_max_tokens=1000,
            primary_provider="openai",
            fallback_enabled=True
        )
    
    @pytest.fixture
    def llm_service(self, llm_config):
        """Instance du service LLM"""
        return LLMService(llm_config)
    
    @pytest.mark.asyncio
    async def test_generate_text_openai_success(self, llm_service):
        """Test de génération de texte avec OpenAI"""
        with patch.object(llm_service.openai_service, 'generate_text') as mock_generate:
            # Mock de la réponse OpenAI
            mock_response = LLMResponse(
                text="Les aventuriers entrent dans une taverne mystérieuse...",
                provider="openai",
                model="gpt-4",
                tokens_used=45,
                cost=0.002,
                success=True
            )
            mock_generate.return_value = mock_response
            
            result = await llm_service.generate_text(
                prompt="Décris une taverne fantastique",
                language="French",
                context="fantasy_tavern"
            )
            
            assert result.success
            assert result.provider == "openai"
            assert "taverne" in result.text.lower()
            assert result.tokens_used > 0
            assert result.cost >= 0
    
    @pytest.mark.asyncio
    async def test_generate_text_with_fallback(self, llm_service):
        """Test de génération avec fallback vers Anthropic"""
        with patch.object(llm_service.openai_service, 'generate_text') as mock_openai, \
             patch.object(llm_service.anthropic_service, 'generate_text') as mock_anthropic:
            
            # OpenAI échoue
            mock_openai.side_effect = Exception("OpenAI API Error")
            
            # Anthropic réussit
            mock_anthropic_response = LLMResponse(
                text="Dans cette taverne sombre et enfumée...",
                provider="anthropic",
                model="claude-3-sonnet",
                tokens_used=38,
                cost=0.001,
                success=True
            )
            mock_anthropic.return_value = mock_anthropic_response
            
            result = await llm_service.generate_text(
                prompt="Décris une taverne fantastique",
                language="French"
            )
            
            assert result.success
            assert result.provider == "anthropic"
            assert "taverne" in result.text.lower()
    
    @pytest.mark.asyncio
    async def test_generate_text_all_providers_fail(self, llm_service):
        """Test quand tous les providers échouent"""
        with patch.object(llm_service.openai_service, 'generate_text') as mock_openai, \
             patch.object(llm_service.anthropic_service, 'generate_text') as mock_anthropic:
            
            # Les deux providers échouent
            mock_openai.side_effect = Exception("OpenAI API Error")
            mock_anthropic.side_effect = Exception("Anthropic API Error")
            
            result = await llm_service.generate_text(
                prompt="Test prompt",
                language="French"
            )
            
            assert not result.success
            assert "error" in result.text.lower()
            assert result.provider == "error"
    
    @pytest.mark.asyncio
    async def test_generate_character_description(self, llm_service):
        """Test de génération de description de personnage"""
        with patch.object(llm_service.openai_service, 'generate_text') as mock_generate:
            mock_response = LLMResponse(
                text="Gareth est un paladin humain de taille imposante...",
                provider="openai",
                model="gpt-4",
                tokens_used=75,
                cost=0.003,
                success=True
            )
            mock_generate.return_value = mock_response
            
            result = await llm_service.generate_character_description(
                character_class="paladin",
                race="human",
                background="noble",
                name="Gareth",
                language="French"
            )
            
            assert result.success
            assert "Gareth" in result.text
            assert "paladin" in result.text.lower()
    
    @pytest.mark.asyncio
    async def test_generate_narrative_response(self, llm_service):
        """Test de génération de réponse narrative"""
        with patch.object(llm_service.openai_service, 'generate_text') as mock_generate:
            mock_response = LLMResponse(
                text="Le dragon rugit et crache un souffle de flammes...",
                provider="openai",
                model="gpt-4",
                tokens_used=120,
                cost=0.005,
                success=True
            )
            mock_generate.return_value = mock_response
            
            result = await llm_service.generate_narrative_response(
                user_action="J'attaque le dragon avec mon épée",
                context="combat_dragon",
                campaign_setting="medieval_fantasy",
                language="French"
            )
            
            assert result.success
            assert "dragon" in result.text.lower()
            assert result.tokens_used > 0

class TestOpenAIService:
    """Tests spécifiques au service OpenAI"""
    
    @pytest.fixture
    def openai_service(self):
        """Instance du service OpenAI"""
        config = LLMConfig(
            openai_api_key="test_key",
            openai_model="gpt-4",
            openai_max_tokens=1000
        )
        return OpenAIService(config)
    
    @pytest.mark.asyncio
    async def test_openai_generate_success(self, openai_service):
        """Test de génération OpenAI réussie"""
        with patch('openai.ChatCompletion.acreate') as mock_create:
            # Mock de la réponse OpenAI
            mock_create.return_value = {
                "choices": [{
                    "message": {
                        "content": "Voici une description magique..."
                    }
                }],
                "usage": {
                    "total_tokens": 85,
                    "prompt_tokens": 20,
                    "completion_tokens": 65
                }
            }
            
            result = await openai_service.generate_text(
                prompt="Génère une description magique",
                language="French"
            )
            
            assert result.success
            assert result.provider == "openai"
            assert result.tokens_used == 85
            assert "magique" in result.text.lower()
    
    @pytest.mark.asyncio
    async def test_openai_api_error(self, openai_service):
        """Test de gestion d'erreur API OpenAI"""
        with patch('openai.ChatCompletion.acreate') as mock_create:
            mock_create.side_effect = Exception("API rate limit exceeded")
            
            result = await openai_service.generate_text(
                prompt="Test prompt",
                language="French"
            )
            
            assert not result.success
            assert "error" in result.text.lower()
            assert result.tokens_used == 0
    
    @pytest.mark.asyncio
    async def test_openai_prompt_formatting(self, openai_service):
        """Test du formatage des prompts OpenAI"""
        with patch('openai.ChatCompletion.acreate') as mock_create:
            mock_create.return_value = {
                "choices": [{"message": {"content": "Test response"}}],
                "usage": {"total_tokens": 10, "prompt_tokens": 5, "completion_tokens": 5}
            }
            
            await openai_service.generate_text(
                prompt="Test prompt",
                language="French",
                context="tavern_scene",
                system_instructions="Tu es un maître de jeu expert"
            )
            
            # Vérifier que l'appel a été fait avec les bons paramètres
            mock_create.assert_called_once()
            call_args = mock_create.call_args[1]
            
            assert "messages" in call_args
            assert len(call_args["messages"]) >= 2  # System + user message
            assert call_args["model"] == "gpt-4"
            assert call_args["max_tokens"] == 1000

class TestAnthropicService:
    """Tests spécifiques au service Anthropic"""
    
    @pytest.fixture
    def anthropic_service(self):
        """Instance du service Anthropic"""
        config = LLMConfig(
            anthropic_api_key="test_key",
            anthropic_model="claude-3-sonnet",
            anthropic_max_tokens=1000
        )
        return AnthropicService(config)
    
    @pytest.mark.asyncio
    async def test_anthropic_generate_success(self, anthropic_service):
        """Test de génération Anthropic réussie"""
        with patch('anthropic.Anthropic.messages.create') as mock_create:
            # Mock de la réponse Anthropic
            mock_response = MagicMock()
            mock_response.content = [MagicMock()]
            mock_response.content[0].text = "Claude génère une réponse créative..."
            mock_response.usage.input_tokens = 25
            mock_response.usage.output_tokens = 60
            mock_create.return_value = mock_response
            
            result = await anthropic_service.generate_text(
                prompt="Crée une histoire fantastique",
                language="French"
            )
            
            assert result.success
            assert result.provider == "anthropic"
            assert result.tokens_used == 85  # input + output
            assert "créative" in result.text.lower()
    
    @pytest.mark.asyncio
    async def test_anthropic_api_error(self, anthropic_service):
        """Test de gestion d'erreur API Anthropic"""
        with patch('anthropic.Anthropic.messages.create') as mock_create:
            mock_create.side_effect = Exception("Anthropic API unavailable")
            
            result = await anthropic_service.generate_text(
                prompt="Test prompt",
                language="French"
            )
            
            assert not result.success
            assert "error" in result.text.lower()

class TestLLMConfig:
    """Tests pour la configuration LLM"""
    
    def test_config_validation(self):
        """Test de validation de la configuration"""
        # Configuration valide
        config = LLMConfig(
            openai_api_key="sk-test",
            openai_model="gpt-4",
            anthropic_api_key="test-key"
        )
        
        assert config.openai_api_key == "sk-test"
        assert config.primary_provider == "openai"  # Default
        assert config.fallback_enabled is True  # Default
    
    def test_config_from_env(self):
        """Test de chargement depuis les variables d'environnement"""
        with patch.dict(os.environ, {
            'OPENAI_API_KEY': 'env_openai_key',
            'ANTHROPIC_API_KEY': 'env_anthropic_key',
            'OPENAI_MODEL': 'gpt-3.5-turbo'
        }):
            config = LLMConfig.from_env()
            
            assert config.openai_api_key == 'env_openai_key'
            assert config.anthropic_api_key == 'env_anthropic_key'
            assert config.openai_model == 'gpt-3.5-turbo'

class TestLLMPerformance:
    """Tests de performance pour les services LLM"""
    
    @pytest.fixture
    def llm_service(self):
        config = LLMConfig(
            openai_api_key="test_key",
            openai_model="gpt-4",
            openai_max_tokens=500
        )
        return LLMService(config)
    
    @pytest.mark.asyncio
    async def test_concurrent_requests(self, llm_service):
        """Test de requêtes concurrentes"""
        with patch.object(llm_service.openai_service, 'generate_text') as mock_generate:
            # Simuler des réponses rapides
            mock_response = LLMResponse(
                text="Réponse rapide",
                provider="openai",
                model="gpt-4",
                tokens_used=10,
                cost=0.001,
                success=True
            )
            mock_generate.return_value = mock_response
            
            # Lancer 5 requêtes concurrentes
            tasks = []
            for i in range(5):
                task = llm_service.generate_text(
                    prompt=f"Prompt {i}",
                    language="French"
                )
                tasks.append(task)
            
            import time
            start_time = time.time()
            results = await asyncio.gather(*tasks)
            end_time = time.time()
            
            # Vérifier que toutes les requêtes ont réussi
            assert all(result.success for result in results)
            assert len(results) == 5
            
            # Le temps total devrait être proche du temps d'une seule requête
            # (grâce à la concurrence)
            assert end_time - start_time < 2.0  # Moins de 2 secondes
    
    @pytest.mark.asyncio
    async def test_response_time(self, llm_service):
        """Test du temps de réponse"""
        with patch.object(llm_service.openai_service, 'generate_text') as mock_generate:
            mock_response = LLMResponse(
                text="Réponse test",
                provider="openai",
                model="gpt-4",
                tokens_used=20,
                cost=0.001,
                success=True
            )
            mock_generate.return_value = mock_response
            
            import time
            start_time = time.time()
            
            result = await llm_service.generate_text(
                prompt="Prompt simple",
                language="French"
            )
            
            end_time = time.time()
            response_time = end_time - start_time
            
            assert result.success
            assert response_time < 1.0  # Moins d'une seconde avec mock

class TestLLMErrorHandling:
    """Tests de gestion d'erreurs pour les services LLM"""
    
    @pytest.fixture
    def llm_service(self):
        config = LLMConfig(
            openai_api_key="test_key",
            anthropic_api_key="test_key"
        )
        return LLMService(config)
    
    @pytest.mark.asyncio
    async def test_invalid_api_key(self, llm_service):
        """Test avec clé API invalide"""
        with patch.object(llm_service.openai_service, 'generate_text') as mock_generate:
            mock_generate.side_effect = Exception("Invalid API key")
            
            result = await llm_service.generate_text(
                prompt="Test",
                language="French"
            )
            
            assert not result.success
            assert "error" in result.text.lower()
    
    @pytest.mark.asyncio
    async def test_rate_limit_error(self, llm_service):
        """Test de gestion des limites de débit"""
        with patch.object(llm_service.openai_service, 'generate_text') as mock_generate:
            mock_generate.side_effect = Exception("Rate limit exceeded")
            
            result = await llm_service.generate_text(
                prompt="Test",
                language="French"
            )
            
            assert not result.success
            assert "rate" in result.text.lower() or "limit" in result.text.lower()
    
    @pytest.mark.asyncio
    async def test_timeout_error(self, llm_service):
        """Test de gestion des timeouts"""
        with patch.object(llm_service.openai_service, 'generate_text') as mock_generate:
            mock_generate.side_effect = asyncio.TimeoutError("Request timeout")
            
            result = await llm_service.generate_text(
                prompt="Test",
                language="French"
            )
            
            assert not result.success
            assert "timeout" in result.text.lower()

if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 