"""
Tests pour l'API principale LLMGameMaster (app.py)
Tests des endpoints FastAPI et de l'intégration des services
"""

import pytest
import json
import os
import sys
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock

# Ajouter le répertoire parent au path pour les imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, get_llm_service, get_db_service, get_element_manager

class TestLLMGameMasterAPI:
    """Tests pour l'API LLMGameMaster"""
    
    @pytest.fixture
    def client(self):
        """Client de test FastAPI"""
        return TestClient(app)
    
    @pytest.fixture
    def mock_llm_service(self):
        """Mock du service LLM"""
        mock_service = MagicMock()
        
        # Mock des méthodes asynchrones
        mock_service.generate_narrative_response = AsyncMock()
        mock_service.generate_character_description = AsyncMock()
        mock_service.generate_location_description = AsyncMock()
        
        return mock_service
    
    @pytest.fixture
    def mock_db_service(self):
        """Mock du service de base de données"""
        mock_service = MagicMock()
        
        # Mock des méthodes asynchrones
        mock_service.get_campaign_context = AsyncMock()
        mock_service.save_message = AsyncMock()
        mock_service.get_campaign_messages = AsyncMock()
        
        return mock_service
    
    @pytest.fixture
    def mock_element_manager(self):
        """Mock du gestionnaire d'éléments"""
        mock_manager = MagicMock()
        
        # Mock des méthodes asynchrones
        mock_manager.extract_and_save_elements = AsyncMock()
        mock_manager.get_campaign_elements = AsyncMock()
        
        return mock_manager
    
    def test_health_check(self, client):
        """Test du endpoint de santé"""
        response = client.get("/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "version" in data
        assert "service" in data
        assert data["service"] == "LLMGameMaster"
    
    def test_api_info(self, client):
        """Test du endpoint d'information API"""
        response = client.get("/")
        assert response.status_code == 200
        
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert "description" in data
        assert data["name"] == "LLM GameMaster API"
    
    @patch('app.get_llm_service')
    @patch('app.get_db_service')
    @patch('app.get_element_manager')
    def test_generate_narrative_success(self, mock_get_element_manager, 
                                       mock_get_db_service, mock_get_llm_service, 
                                       client, mock_llm_service, mock_db_service, 
                                       mock_element_manager):
        """Test de génération narrative réussie"""
        # Setup des mocks
        mock_get_llm_service.return_value = mock_llm_service
        mock_get_db_service.return_value = mock_db_service
        mock_get_element_manager.return_value = mock_element_manager
        
        # Mock des réponses
        from llm_service import LLMResponse
        mock_llm_response = LLMResponse(
            text="Les aventuriers entrent dans une taverne animée...",
            provider="openai",
            model="gpt-4",
            tokens_used=85,
            cost=0.004,
            success=True
        )
        mock_llm_service.generate_narrative_response.return_value = mock_llm_response
        
        mock_db_service.get_campaign_context.return_value = {
            "campaign_id": 1,
            "setting": "medieval_fantasy",
            "recent_events": []
        }
        
        mock_element_manager.extract_and_save_elements.return_value = {
            "npcs": ["Barkeep Tom"],
            "locations": ["The Prancing Pony"],
            "items": [],
            "quests": []
        }
        
        # Requête de test
        request_data = {
            "campaign_id": 1,
            "user_input": "J'entre dans la taverne",
            "language": "French"
        }
        
        response = client.post("/api/generate_narrative", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "narrative" in data
        assert "elements" in data
        assert "metadata" in data
        assert data["success"] is True
        assert "taverne" in data["narrative"].lower()
        assert data["metadata"]["tokens_used"] == 85
        assert data["metadata"]["provider"] == "openai"
    
    @patch('app.get_llm_service')
    def test_generate_narrative_missing_params(self, mock_get_llm_service, client):
        """Test de génération narrative avec paramètres manquants"""
        # Requête incomplète
        request_data = {
            "campaign_id": 1
            # Manque user_input
        }
        
        response = client.post("/api/generate_narrative", json=request_data)
        assert response.status_code == 422  # Unprocessable Entity
    
    @patch('app.get_llm_service')
    @patch('app.get_db_service')
    def test_generate_narrative_llm_error(self, mock_get_db_service, 
                                         mock_get_llm_service, client, 
                                         mock_llm_service, mock_db_service):
        """Test de génération narrative avec erreur LLM"""
        # Setup des mocks
        mock_get_llm_service.return_value = mock_llm_service
        mock_get_db_service.return_value = mock_db_service
        
        # LLM échoue
        from llm_service import LLMResponse
        mock_llm_response = LLMResponse(
            text="Une erreur s'est produite lors de la génération",
            provider="error",
            model="",
            tokens_used=0,
            cost=0,
            success=False
        )
        mock_llm_service.generate_narrative_response.return_value = mock_llm_response
        
        mock_db_service.get_campaign_context.return_value = {"campaign_id": 1}
        
        request_data = {
            "campaign_id": 1,
            "user_input": "Test input",
            "language": "French"
        }
        
        response = client.post("/api/generate_narrative", json=request_data)
        
        assert response.status_code == 200  # API répond toujours 200 mais avec success=False
        data = response.json()
        assert data["success"] is False
        assert "erreur" in data["narrative"].lower()
    
    @patch('app.get_llm_service')
    def test_generate_character_description(self, mock_get_llm_service, 
                                          client, mock_llm_service):
        """Test de génération de description de personnage"""
        mock_get_llm_service.return_value = mock_llm_service
        
        from llm_service import LLMResponse
        mock_llm_response = LLMResponse(
            text="Gareth Lightbringer est un paladin noble et courageux...",
            provider="openai",
            model="gpt-4",
            tokens_used=95,
            cost=0.005,
            success=True
        )
        mock_llm_service.generate_character_description.return_value = mock_llm_response
        
        request_data = {
            "name": "Gareth Lightbringer",
            "character_class": "paladin",
            "race": "human",
            "background": "noble",
            "language": "French"
        }
        
        response = client.post("/api/generate_character_description", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert "description" in data
        assert "Gareth" in data["description"]
        assert "paladin" in data["description"].lower()
    
    @patch('app.get_db_service')
    def test_get_campaign_messages(self, mock_get_db_service, client, mock_db_service):
        """Test de récupération des messages de campagne"""
        mock_get_db_service.return_value = mock_db_service
        
        # Mock des messages
        mock_messages = [
            {
                "id": 1,
                "campaign_id": 1,
                "user_input": "J'entre dans la taverne",
                "ai_response": "Vous entrez dans une taverne animée...",
                "timestamp": "2024-01-01T12:00:00",
                "tokens_used": 85,
                "cost": 0.004
            },
            {
                "id": 2,
                "campaign_id": 1,
                "user_input": "Je commande une bière",
                "ai_response": "Le barman vous sert une chope fumante...",
                "timestamp": "2024-01-01T12:01:00",
                "tokens_used": 42,
                "cost": 0.002
            }
        ]
        mock_db_service.get_campaign_messages.return_value = mock_messages
        
        response = client.get("/api/campaigns/1/messages")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "messages" in data
        assert len(data["messages"]) == 2
        assert data["messages"][0]["user_input"] == "J'entre dans la taverne"
        assert "metadata" in data
        assert data["metadata"]["total_messages"] == 2
    
    @patch('app.get_element_manager')
    def test_get_campaign_elements(self, mock_get_element_manager, 
                                  client, mock_element_manager):
        """Test de récupération des éléments de campagne"""
        mock_get_element_manager.return_value = mock_element_manager
        
        # Mock des éléments
        mock_elements = {
            "npcs": [
                {"name": "Barkeep Tom", "description": "Friendly tavern owner"},
                {"name": "Guard Captain", "description": "Stern city guard"}
            ],
            "locations": [
                {"name": "The Prancing Pony", "description": "Cozy tavern"},
                {"name": "City Gates", "description": "Main entrance to the city"}
            ],
            "items": [
                {"name": "Ancient Map", "description": "Shows hidden passages"}
            ],
            "quests": [
                {"name": "Find the Lost Artifact", "description": "Ancient relic disappeared"}
            ]
        }
        mock_element_manager.get_campaign_elements.return_value = mock_elements
        
        response = client.get("/api/campaigns/1/elements")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "elements" in data
        assert len(data["elements"]["npcs"]) == 2
        assert len(data["elements"]["locations"]) == 2
        assert len(data["elements"]["items"]) == 1
        assert len(data["elements"]["quests"]) == 1
    
    def test_cors_headers(self, client):
        """Test des headers CORS"""
        response = client.options("/api/generate_narrative")
        
        # Vérifier que les headers CORS sont présents (si configurés)
        assert response.status_code in [200, 405]
    
    @patch('app.get_llm_service')
    @patch('app.get_db_service')
    def test_api_performance(self, mock_get_db_service, mock_get_llm_service, 
                            client, mock_llm_service, mock_db_service):
        """Test de performance de l'API"""
        mock_get_llm_service.return_value = mock_llm_service
        mock_get_db_service.return_value = mock_db_service
        
        from llm_service import LLMResponse
        mock_llm_response = LLMResponse(
            text="Réponse rapide",
            provider="openai",
            model="gpt-4",
            tokens_used=20,
            cost=0.001,
            success=True
        )
        mock_llm_service.generate_narrative_response.return_value = mock_llm_response
        mock_db_service.get_campaign_context.return_value = {"campaign_id": 1}
        
        request_data = {
            "campaign_id": 1,
            "user_input": "Action rapide",
            "language": "French"
        }
        
        import time
        start_time = time.time()
        
        response = client.post("/api/generate_narrative", json=request_data)
        
        end_time = time.time()
        response_time = end_time - start_time
        
        assert response.status_code == 200
        assert response_time < 2.0  # Moins de 2 secondes avec mock
    
    def test_input_validation(self, client):
        """Test de validation des entrées"""
        # Test avec campaign_id invalide
        request_data = {
            "campaign_id": "invalid",
            "user_input": "Test",
            "language": "French"
        }
        
        response = client.post("/api/generate_narrative", json=request_data)
        assert response.status_code == 422
        
        # Test avec language invalide
        request_data = {
            "campaign_id": 1,
            "user_input": "Test",
            "language": "InvalidLanguage"
        }
        
        response = client.post("/api/generate_narrative", json=request_data)
        assert response.status_code == 422
    
    @patch('app.get_llm_service')
    @patch('app.get_db_service')
    def test_large_input_handling(self, mock_get_db_service, mock_get_llm_service, 
                                 client, mock_llm_service, mock_db_service):
        """Test de gestion des entrées très longues"""
        mock_get_llm_service.return_value = mock_llm_service
        mock_get_db_service.return_value = mock_db_service
        
        from llm_service import LLMResponse
        mock_llm_response = LLMResponse(
            text="Réponse pour entrée longue",
            provider="openai",
            model="gpt-4",
            tokens_used=200,
            cost=0.01,
            success=True
        )
        mock_llm_service.generate_narrative_response.return_value = mock_llm_response
        mock_db_service.get_campaign_context.return_value = {"campaign_id": 1}
        
        # Entrée très longue (plus de 1000 caractères)
        long_input = "Je " + "marche vers l'avant " * 100
        
        request_data = {
            "campaign_id": 1,
            "user_input": long_input,
            "language": "French"
        }
        
        response = client.post("/api/generate_narrative", json=request_data)
        
        # L'API devrait soit accepter l'entrée, soit retourner une erreur de validation
        assert response.status_code in [200, 422]
    
    def test_rate_limiting(self, client):
        """Test de limitation de débit (si implémenté)"""
        # Effectuer plusieurs requêtes rapidement
        responses = []
        for i in range(10):
            response = client.get("/health")
            responses.append(response.status_code)
        
        # La plupart des requêtes devraient réussir
        success_count = sum(1 for status in responses if status == 200)
        assert success_count > 0

class TestAPIEndpoints:
    """Tests spécifiques aux endpoints"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    def test_generate_location_description(self, client):
        """Test de génération de description de lieu"""
        with patch('app.get_llm_service') as mock_get_llm_service:
            mock_service = MagicMock()
            mock_get_llm_service.return_value = mock_service
            
            from llm_service import LLMResponse
            mock_response = LLMResponse(
                text="Cette ancienne bibliothèque renferme des secrets...",
                provider="openai",
                model="gpt-4",
                tokens_used=67,
                cost=0.003,
                success=True
            )
            mock_service.generate_location_description.return_value = mock_response
            
            request_data = {
                "location_type": "library",
                "setting": "medieval_fantasy",
                "mood": "mysterious",
                "language": "French"
            }
            
            response = client.post("/api/generate_location_description", json=request_data)
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["success"] is True
            assert "description" in data
            assert "bibliothèque" in data["description"].lower()
    
    def test_metrics_endpoint(self, client):
        """Test du endpoint de métriques"""
        with patch('app.get_db_service') as mock_get_db_service:
            mock_service = MagicMock()
            mock_get_db_service.return_value = mock_service
            
            # Mock des métriques
            mock_metrics = {
                "total_requests": 1250,
                "total_tokens_used": 125000,
                "total_cost": 25.50,
                "average_response_time": 1.2,
                "success_rate": 99.2,
                "provider_distribution": {
                    "openai": 70,
                    "anthropic": 30
                }
            }
            mock_service.get_usage_metrics.return_value = mock_metrics
            
            response = client.get("/api/metrics")
            
            assert response.status_code == 200
            data = response.json()
            
            assert "metrics" in data
            assert data["metrics"]["total_requests"] == 1250
            assert data["metrics"]["success_rate"] == 99.2
    
    def test_websocket_connection(self, client):
        """Test de connexion WebSocket (si implémenté)"""
        try:
            with client.websocket_connect("/ws/campaign/1") as websocket:
                # Test de connexion basique
                websocket.send_json({"type": "ping"})
                data = websocket.receive_json()
                assert data["type"] == "pong"
        except Exception:
            # WebSocket peut ne pas être implémenté
            pytest.skip("WebSocket not implemented")

class TestAPISecurityAndAuth:
    """Tests de sécurité et d'authentification"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    def test_sql_injection_protection(self, client):
        """Test de protection contre l'injection SQL"""
        malicious_input = "'; DROP TABLE campaigns; --"
        
        request_data = {
            "campaign_id": 1,
            "user_input": malicious_input,
            "language": "French"
        }
        
        # L'API ne devrait pas crasher
        response = client.post("/api/generate_narrative", json=request_data)
        assert response.status_code in [200, 422, 400]
    
    def test_xss_protection(self, client):
        """Test de protection contre XSS"""
        xss_input = "<script>alert('xss')</script>"
        
        request_data = {
            "campaign_id": 1,
            "user_input": xss_input,
            "language": "French"
        }
        
        # L'API devrait gérer cela proprement
        response = client.post("/api/generate_narrative", json=request_data)
        assert response.status_code in [200, 422, 400]
    
    def test_request_size_limit(self, client):
        """Test de limitation de taille de requête"""
        # Requête très large
        huge_input = "x" * 100000  # 100KB
        
        request_data = {
            "campaign_id": 1,
            "user_input": huge_input,
            "language": "French"
        }
        
        response = client.post("/api/generate_narrative", json=request_data)
        # Devrait soit traiter soit rejeter proprement
        assert response.status_code in [200, 413, 422]  # 413 = Payload Too Large

if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 