"""
Tests pour le système d'authentification JWT
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import os
import sys

# Add the parent directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app import app
from auth import JWTAuth

class TestJWTAuthentication:
    """Tests pour l'authentification JWT"""
    
    @pytest.fixture
    def client(self):
        """Client de test FastAPI"""
        return TestClient(app)
    
    @pytest.fixture
    def mock_user(self):
        """Utilisateur fictif pour les tests"""
        return {
            "id": "test-user-id",
            "email": "test@example.com",
            "username": "testuser"
        }
    
    def test_create_jwt_token(self, mock_user):
        """Test de création d'un token JWT"""
        token = JWTAuth.create_access_token(mock_user)
        
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0
    
    def test_verify_valid_jwt_token(self, mock_user):
        """Test de vérification d'un token JWT valide"""
        token = JWTAuth.create_access_token(mock_user)
        payload = JWTAuth.verify_token(token)
        
        assert payload["user_id"] == mock_user["id"]
        assert payload["email"] == mock_user["email"]
        assert payload["username"] == mock_user["username"]
    
    def test_verify_invalid_jwt_token(self):
        """Test de vérification d'un token JWT invalide"""
        with pytest.raises(Exception):  # HTTPException attendue
            JWTAuth.verify_token("invalid-token")
    
    def test_verify_expired_token(self, mock_user):
        """Test de vérification d'un token expiré"""
        # Mock datetime pour simuler un token expiré
        with patch('auth.datetime') as mock_datetime:
            from datetime import datetime, timedelta
            
            # Créer un token avec une expiration dans le passé
            past_time = datetime.utcnow() - timedelta(hours=25)
            mock_datetime.utcnow.return_value = past_time
            
            token = JWTAuth.create_access_token(mock_user)
            
            # Restaurer le temps réel pour la vérification
            mock_datetime.utcnow.return_value = datetime.utcnow()
            
            with pytest.raises(Exception):  # HTTPException attendue
                JWTAuth.verify_token(token)
    
    @patch('auth.psycopg2.connect')
    def test_get_user_from_db_success(self, mock_connect, mock_user):
        """Test de récupération utilisateur depuis la DB avec succès"""
        # Mock de la connexion DB
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        
        # Mock du résultat de la requête
        mock_cursor.fetchone.return_value = {
            "Id": mock_user["id"],
            "Email": mock_user["email"],
            "UserName": mock_user["username"],
            "EmailConfirmed": True
        }
        
        result = JWTAuth.get_user_from_db(mock_user["id"])
        
        assert result is not None
        assert result["id"] == mock_user["id"]
        assert result["email"] == mock_user["email"]
        assert result["email_confirmed"] is True
    
    @patch('auth.psycopg2.connect')
    def test_get_user_from_db_not_found(self, mock_connect):
        """Test de récupération utilisateur non trouvé en DB"""
        # Mock de la connexion DB
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        
        # Mock d'un résultat vide
        mock_cursor.fetchone.return_value = None
        
        result = JWTAuth.get_user_from_db("non-existent-user")
        
        assert result is None
    
    @patch('auth.psycopg2.connect')
    def test_validate_campaign_access_owner(self, mock_connect, mock_user):
        """Test de validation d'accès pour le propriétaire d'une campagne"""
        from auth import validate_campaign_access
        
        # Mock de la connexion DB
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        
        # Mock : utilisateur est propriétaire de la campagne
        mock_cursor.fetchone.side_effect = [
            {"Id": 1},  # Première requête : campagne trouvée
            None        # Deuxième requête : pas besoin de vérifier les personnages
        ]
        
        import asyncio
        result = asyncio.run(validate_campaign_access(mock_user, 1))
        
        assert result is True
    
    @patch('auth.psycopg2.connect')
    def test_validate_campaign_access_player(self, mock_connect, mock_user):
        """Test de validation d'accès pour un joueur de la campagne"""
        from auth import validate_campaign_access
        
        # Mock de la connexion DB
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        
        # Mock : utilisateur n'est pas propriétaire mais a un personnage
        mock_cursor.fetchone.side_effect = [
            None,       # Première requête : pas propriétaire
            {"Id": 1}   # Deuxième requête : a un personnage
        ]
        
        import asyncio
        result = asyncio.run(validate_campaign_access(mock_user, 1))
        
        assert result is True
    
    @patch('auth.psycopg2.connect')
    def test_validate_campaign_access_denied(self, mock_connect, mock_user):
        """Test de validation d'accès refusé"""
        from auth import validate_campaign_access
        
        # Mock de la connexion DB
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        
        # Mock : utilisateur n'a aucun accès
        mock_cursor.fetchone.return_value = None
        
        import asyncio
        result = asyncio.run(validate_campaign_access(mock_user, 1))
        
        assert result is False


class TestAuthenticationRoutes:
    """Tests pour les routes d'authentification"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    @patch('auth_routes.psycopg2.connect')
    def test_login_success(self, mock_connect, client):
        """Test de connexion réussie"""
        # Mock de la connexion DB
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        
        # Mock d'un utilisateur valide
        mock_cursor.fetchone.return_value = {
            "Id": "test-user-id",
            "UserName": "testuser",
            "Email": "test@example.com",
            "PasswordHash": "hashed-password",
            "EmailConfirmed": True,
            "LockoutEnd": None
        }
        
        # Mock de la vérification du mot de passe
        with patch('auth_routes.verify_aspnet_password', return_value=True):
            response = client.post("/auth/login", json={
                "email": "test@example.com",
                "password": "testpassword"
            })
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert "user" in data
    
    @patch('auth_routes.psycopg2.connect')
    def test_login_invalid_credentials(self, mock_connect, client):
        """Test de connexion avec identifiants invalides"""
        # Mock de la connexion DB
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        
        # Mock d'un utilisateur non trouvé
        mock_cursor.fetchone.return_value = None
        
        response = client.post("/auth/login", json={
            "email": "nonexistent@example.com",
            "password": "testpassword"
        })
        
        assert response.status_code == 401
        assert "Invalid email or password" in response.json()["detail"]
    
    def test_verify_token_without_auth(self, client):
        """Test de vérification de token sans authentification"""
        response = client.post("/auth/verify-token")
        
        assert response.status_code == 401


class TestProtectedRoutes:
    """Tests pour les routes protégées"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    @pytest.fixture 
    def valid_token(self):
        """Token JWT valide pour les tests"""
        user_data = {
            "id": "test-user-id",
            "email": "test@example.com",
            "username": "testuser"
        }
        return JWTAuth.create_access_token(user_data)
    
    def test_protected_route_without_token(self, client):
        """Test d'accès à une route protégée sans token"""
        # Activer l'authentification pour ce test
        with patch.dict(os.environ, {"ENABLE_AUTH": "true"}):
            response = client.get("/api/gamemaster/campaign/1/elements")
            assert response.status_code == 401
    
    @patch('app.validate_campaign_access')
    @patch('app.db_service.get_campaign_npcs')
    @patch('app.db_service.get_campaign_locations') 
    @patch('app.db_service.get_campaign_quests')
    def test_protected_route_with_valid_token(self, mock_quests, mock_locations, mock_npcs, mock_access, client, valid_token):
        """Test d'accès à une route protégée avec token valide"""
        # Mock des réponses
        mock_access.return_value = True
        mock_npcs.return_value = []
        mock_locations.return_value = []
        mock_quests.return_value = []
        
        with patch.dict(os.environ, {"ENABLE_AUTH": "true"}):
            headers = {"Authorization": f"Bearer {valid_token}"}
            response = client.get("/api/gamemaster/campaign/1/elements", headers=headers)
            
            assert response.status_code == 200
            data = response.json()
            assert "success" in data
            assert data["success"] is True
    
    @patch('app.validate_campaign_access')
    def test_protected_route_access_denied(self, mock_access, client, valid_token):
        """Test d'accès refusé à une campagne"""
        # Mock : accès refusé
        mock_access.return_value = False
        
        with patch.dict(os.environ, {"ENABLE_AUTH": "true"}):
            headers = {"Authorization": f"Bearer {valid_token}"}
            response = client.get("/api/gamemaster/campaign/1/elements", headers=headers)
            
            assert response.status_code == 403
            assert "don't have access" in response.json()["detail"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
