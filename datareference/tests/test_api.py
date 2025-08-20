"""
Tests pour l'API REST DataReference (api.py et api_routes.py)
Tests des endpoints et de l'authentification
"""

import pytest
import json
import os
import sys
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

# Ajouter le répertoire parent au path pour les imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api import app
from api_routes import get_database_connection

class TestDataReferenceAPI:
    """Tests pour l'API DataReference"""
    
    @pytest.fixture
    def client(self):
        """Client de test FastAPI"""
        return TestClient(app)
    
    @pytest.fixture
    def mock_db_connection(self):
        """Mock de connexion à la base de données"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        return mock_conn, mock_cursor
    
    @pytest.fixture
    def auth_token(self, client):
        """Token d'authentification pour les tests"""
        # Mock de l'authentification
        test_credentials = {
            "username": "test_user",
            "password": "test_password"
        }
        
        with patch('api_routes.authenticate_user') as mock_auth:
            mock_auth.return_value = True
            response = client.post("/auth/login", json=test_credentials)
            
            if response.status_code == 200:
                return response.json().get("access_token", "test_token")
            else:
                return "test_token"  # Token de test par défaut
    
    def test_health_check(self, client):
        """Test du endpoint de santé"""
        response = client.get("/health")
        assert response.status_code == 200
        
        data = response.json()
        assert "status" in data
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "version" in data
    
    def test_api_info(self, client):
        """Test du endpoint d'information API"""
        response = client.get("/")
        assert response.status_code == 200
        
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert "description" in data
        assert data["name"] == "D&D Reference Data API"
    
    @patch('api_routes.get_database_connection')
    def test_get_monsters_success(self, mock_db_conn, client, auth_token):
        """Test de récupération des monstres avec succès"""
        # Setup du mock
        mock_conn, mock_cursor = self.setup_monsters_mock()
        mock_db_conn.return_value = mock_conn
        
        # Test avec authentification
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = client.get("/api/monsters", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "data" in data
        assert "pagination" in data
        assert len(data["data"]) == 3
        
        # Vérifier la structure des données
        monster = data["data"][0]
        assert "monster_index" in monster
        assert "name" in monster
        assert "challenge_rating" in monster
        assert "creature_type" in monster
    
    @patch('api_routes.get_database_connection')
    def test_get_monsters_with_filters(self, mock_db_conn, client, auth_token):
        """Test de récupération des monstres avec filtres"""
        mock_conn, mock_cursor = self.setup_monsters_mock()
        mock_db_conn.return_value = mock_conn
        
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        # Test avec filtre par type
        response = client.get("/api/monsters?creature_type=dragon", headers=headers)
        assert response.status_code == 200
        
        # Test avec filtre par CR
        response = client.get("/api/monsters?min_cr=5&max_cr=15", headers=headers)
        assert response.status_code == 200
        
        # Test avec pagination
        response = client.get("/api/monsters?page=1&limit=10", headers=headers)
        assert response.status_code == 200
    
    @patch('api_routes.get_database_connection')
    def test_get_monster_by_index(self, mock_db_conn, client, auth_token):
        """Test de récupération d'un monstre spécifique"""
        mock_conn, mock_cursor = self.setup_single_monster_mock()
        mock_db_conn.return_value = mock_conn
        
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = client.get("/api/monsters/ancient-red-dragon", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["monster_index"] == "ancient-red-dragon"
        assert data["name"] == "Ancient Red Dragon"
        assert data["challenge_rating"] == 24
    
    @patch('api_routes.get_database_connection')
    def test_get_monster_not_found(self, mock_db_conn, client, auth_token):
        """Test de récupération d'un monstre inexistant"""
        mock_conn, mock_cursor = self.setup_empty_mock()
        mock_db_conn.return_value = mock_conn
        
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = client.get("/api/monsters/nonexistent-monster", headers=headers)
        
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower()
    
    @patch('api_routes.get_database_connection')
    def test_get_spells_success(self, mock_db_conn, client, auth_token):
        """Test de récupération des sorts"""
        mock_conn, mock_cursor = self.setup_spells_mock()
        mock_db_conn.return_value = mock_conn
        
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = client.get("/api/spells", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "data" in data
        assert len(data["data"]) == 2
        
        spell = data["data"][0]
        assert "spell_index" in spell
        assert "name" in spell
        assert "level" in spell
        assert "school" in spell
    
    @patch('api_routes.get_database_connection')
    def test_get_spells_by_level(self, mock_db_conn, client, auth_token):
        """Test de récupération des sorts par niveau"""
        mock_conn, mock_cursor = self.setup_spells_mock()
        mock_db_conn.return_value = mock_conn
        
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = client.get("/api/spells?level=3", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
    
    @patch('api_routes.get_database_connection')
    def test_get_equipment_success(self, mock_db_conn, client, auth_token):
        """Test de récupération de l'équipement"""
        mock_conn, mock_cursor = self.setup_equipment_mock()
        mock_db_conn.return_value = mock_conn
        
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = client.get("/api/equipment", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "data" in data
        assert len(data["data"]) == 2
        
        item = data["data"][0]
        assert "equipment_index" in item
        assert "name" in item
        assert "equipment_category" in item
    
    def test_unauthorized_access(self, client):
        """Test d'accès sans authentification"""
        response = client.get("/api/monsters")
        assert response.status_code == 401
        
        data = response.json()
        assert "detail" in data
        assert "unauthorized" in data["detail"].lower() or "token" in data["detail"].lower()
    
    def test_invalid_token(self, client):
        """Test d'accès avec token invalide"""
        headers = {"Authorization": "Bearer invalid_token"}
        response = client.get("/api/monsters", headers=headers)
        
        assert response.status_code == 401
    
    @patch('api_routes.get_database_connection')
    def test_search_monsters(self, mock_db_conn, client, auth_token):
        """Test de recherche de monstres"""
        mock_conn, mock_cursor = self.setup_search_mock()
        mock_db_conn.return_value = mock_conn
        
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = client.get("/api/monsters/search?q=dragon", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "data" in data
        assert "search_query" in data
        assert data["search_query"] == "dragon"
    
    @patch('api_routes.get_database_connection')
    def test_api_performance(self, mock_db_conn, client, auth_token):
        """Test de performance de l'API"""
        mock_conn, mock_cursor = self.setup_large_dataset_mock()
        mock_db_conn.return_value = mock_conn
        
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        import time
        start_time = time.time()
        
        response = client.get("/api/monsters?limit=100", headers=headers)
        
        end_time = time.time()
        response_time = end_time - start_time
        
        assert response.status_code == 200
        assert response_time < 2.0  # Moins de 2 secondes
        
        data = response.json()
        assert len(data["data"]) <= 100
    
    @patch('api_routes.get_database_connection')
    def test_database_error_handling(self, mock_db_conn, client, auth_token):
        """Test de gestion d'erreurs de base de données"""
        # Simuler une erreur de base de données
        mock_db_conn.side_effect = Exception("Database connection failed")
        
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = client.get("/api/monsters", headers=headers)
        
        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
        assert "error" in data["detail"].lower()
    
    def test_cors_headers(self, client):
        """Test des headers CORS"""
        response = client.options("/api/monsters")
        
        # Vérifier la présence des headers CORS si configurés
        assert response.status_code in [200, 405]  # 405 si OPTIONS non supporté
    
    def test_rate_limiting(self, client, auth_token):
        """Test de limitation de débit (si implémenté)"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        # Effectuer plusieurs requêtes rapidement
        responses = []
        for i in range(10):
            response = client.get("/api/monsters", headers=headers)
            responses.append(response.status_code)
        
        # La plupart des requêtes devraient réussir
        success_count = sum(1 for status in responses if status == 200)
        assert success_count > 0  # Au moins quelques requêtes réussissent
    
    def test_input_validation(self, client, auth_token):
        """Test de validation des entrées"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        # Test de paramètres invalides
        response = client.get("/api/monsters?page=-1", headers=headers)
        assert response.status_code in [400, 422]  # Bad Request ou Unprocessable Entity
        
        response = client.get("/api/monsters?limit=0", headers=headers)
        assert response.status_code in [400, 422]
        
        response = client.get("/api/monsters?min_cr=invalid", headers=headers)
        assert response.status_code in [400, 422]
    
    # Méthodes helper pour setup des mocks
    
    def setup_monsters_mock(self):
        """Setup mock pour les monstres"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        
        # Données de test
        mock_cursor.fetchall.return_value = [
            ("goblin", "Goblin", "Small", "humanoid", 0.25, "Low", 15, 7, "30 ft."),
            ("orc", "Orc", "Medium", "humanoid", 0.5, "Low", 13, 15, "30 ft."),
            ("dragon", "Ancient Red Dragon", "Gargantuan", "dragon", 24, "Legendary", 22, 546, "40 ft., fly 80 ft.")
        ]
        
        mock_cursor.fetchone.return_value = (3,)  # Count total
        
        return mock_conn, mock_cursor
    
    def setup_single_monster_mock(self):
        """Setup mock pour un seul monstre"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        
        mock_cursor.fetchone.return_value = (
            "ancient-red-dragon", "Ancient Red Dragon", "Gargantuan", "dragon", 
            24, "Legendary", 22, 546, "40 ft., fly 80 ft.", 
            '{"walk": "40 ft.", "fly": "80 ft."}', 30, 10, 29, 18, 15, 23
        )
        
        return mock_conn, mock_cursor
    
    def setup_spells_mock(self):
        """Setup mock pour les sorts"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        
        mock_cursor.fetchall.return_value = [
            ("fireball", "Fireball", 3, "evocation", "1 action", "150 feet", "V,S,M"),
            ("magic-missile", "Magic Missile", 1, "evocation", "1 action", "120 feet", "V,S")
        ]
        
        mock_cursor.fetchone.return_value = (2,)  # Count
        
        return mock_conn, mock_cursor
    
    def setup_equipment_mock(self):
        """Setup mock pour l'équipement"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        
        mock_cursor.fetchall.return_value = [
            ("longsword", "Longsword", "Weapon", "Martial Melee", "15 gp", "3 lb."),
            ("plate", "Plate", "Armor", "Heavy Armor", "1,500 gp", "65 lb.")
        ]
        
        mock_cursor.fetchone.return_value = (2,)  # Count
        
        return mock_conn, mock_cursor
    
    def setup_empty_mock(self):
        """Setup mock pour résultat vide"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        
        mock_cursor.fetchone.return_value = None
        mock_cursor.fetchall.return_value = []
        
        return mock_conn, mock_cursor
    
    def setup_search_mock(self):
        """Setup mock pour la recherche"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        
        mock_cursor.fetchall.return_value = [
            ("ancient-red-dragon", "Ancient Red Dragon", "Gargantuan", "dragon", 24, "Legendary", 22, 546, "40 ft., fly 80 ft."),
            ("young-red-dragon", "Young Red Dragon", "Large", "dragon", 10, "Medium", 18, 178, "40 ft., fly 80 ft.")
        ]
        
        mock_cursor.fetchone.return_value = (2,)
        
        return mock_conn, mock_cursor
    
    def setup_large_dataset_mock(self):
        """Setup mock pour un grand dataset"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        
        # Simuler 100 monstres
        large_dataset = []
        for i in range(100):
            large_dataset.append((
                f"monster-{i}", f"Monster {i}", "Medium", "beast", 1, "Low", 12, 10, "30 ft."
            ))
        
        mock_cursor.fetchall.return_value = large_dataset
        mock_cursor.fetchone.return_value = (1000,)  # Count total
        
        return mock_conn, mock_cursor

class TestAPIAuth:
    """Tests spécifiques à l'authentification"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    def test_login_success(self, client):
        """Test de connexion réussie"""
        with patch('api_routes.authenticate_user') as mock_auth:
            mock_auth.return_value = True
            
            response = client.post("/auth/login", json={
                "username": "valid_user",
                "password": "valid_password"
            })
            
            assert response.status_code == 200
            data = response.json()
            assert "access_token" in data
            assert "token_type" in data
    
    def test_login_failure(self, client):
        """Test de connexion échouée"""
        with patch('api_routes.authenticate_user') as mock_auth:
            mock_auth.return_value = False
            
            response = client.post("/auth/login", json={
                "username": "invalid_user",
                "password": "invalid_password"
            })
            
            assert response.status_code == 401
            data = response.json()
            assert "detail" in data
    
    def test_login_missing_credentials(self, client):
        """Test de connexion avec credentials manquants"""
        response = client.post("/auth/login", json={})
        assert response.status_code == 422  # Unprocessable Entity
        
        response = client.post("/auth/login", json={
            "username": "user_only"
        })
        assert response.status_code == 422

if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 