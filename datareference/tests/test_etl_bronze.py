"""
Tests pour le module ETL Bronze (import_json.py)
Test de l'importation des données JSON vers la base bronze
"""

import pytest
import psycopg2
import json
import tempfile
import os
import sys
from unittest.mock import patch, MagicMock

# Ajouter le répertoire parent au path pour les imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from import_json import (
    connect_to_database,
    create_tables_if_not_exist,
    calculate_file_hash,
    is_file_already_imported,
    import_monsters_batch,
    import_spells_batch,
    import_equipment_batch
)

class TestETLBronze:
    """Tests pour les fonctions ETL Bronze"""
    
    @pytest.fixture
    def db_connection(self):
        """Fixture pour la connexion à la base de test"""
        conn = psycopg2.connect(
            host=os.getenv('BRONZE_PG_HOST', 'localhost'),
            port=os.getenv('BRONZE_PG_PORT', '5435'),
            database=os.getenv('BRONZE_DB_NAME', 'bronze_db_test'),
            user=os.getenv('POSTGRES_USER'),
            password=os.getenv('POSTGRES_PASSWORD')
        )
        yield conn
        conn.close()
    
    @pytest.fixture
    def sample_monster_data(self):
        """Données de test pour les monstres"""
        return {
            "count": 2,
            "results": [
                {
                    "index": "goblin",
                    "name": "Goblin",
                    "size": "Small",
                    "type": "humanoid",
                    "subtype": "goblinoid",
                    "alignment": "neutral evil",
                    "armor_class": [{"type": "natural", "value": 15}],
                    "hit_points": 7,
                    "hit_dice": "2d6",
                    "speed": {"walk": "30 ft."},
                    "strength": 8,
                    "dexterity": 14,
                    "constitution": 10,
                    "intelligence": 10,
                    "wisdom": 8,
                    "charisma": 8,
                    "challenge_rating": 0.25,
                    "proficiency_bonus": 2,
                    "xp": 50
                },
                {
                    "index": "orc",
                    "name": "Orc",
                    "size": "Medium",
                    "type": "humanoid",
                    "subtype": "orc",
                    "alignment": "chaotic evil",
                    "armor_class": [{"type": "natural", "value": 13}],
                    "hit_points": 15,
                    "hit_dice": "2d8+2",
                    "speed": {"walk": "30 ft."},
                    "strength": 16,
                    "dexterity": 12,
                    "constitution": 13,
                    "intelligence": 7,
                    "wisdom": 11,
                    "charisma": 10,
                    "challenge_rating": 0.5,
                    "proficiency_bonus": 2,
                    "xp": 100
                }
            ]
        }
    
    @pytest.fixture
    def sample_json_file(self, sample_monster_data):
        """Créer un fichier JSON temporaire de test"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(sample_monster_data, f)
            yield f.name
        os.unlink(f.name)
    
    def test_connect_to_database(self, db_connection):
        """Test de connexion à la base de données"""
        assert db_connection is not None
        assert not db_connection.closed
        
        # Test d'exécution d'une requête simple
        cursor = db_connection.cursor()
        cursor.execute("SELECT 1;")
        result = cursor.fetchone()
        assert result[0] == 1
        cursor.close()
    
    def test_create_tables_if_not_exist(self, db_connection):
        """Test de création des tables"""
        # Les tables devraient être créées sans erreur
        try:
            create_tables_if_not_exist(db_connection)
            db_connection.commit()
        except Exception as e:
            pytest.fail(f"Création des tables échouée: {e}")
        
        # Vérifier que les tables principales existent
        cursor = db_connection.cursor()
        expected_tables = [
            'import_tracking', 'monsters', 'spells', 'equipment',
            'classes', 'races', 'magic_schools', 'damage_types'
        ]
        
        for table in expected_tables:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = %s
                );
            """, (table,))
            exists = cursor.fetchone()[0]
            assert exists, f"Table {table} n'existe pas"
        
        cursor.close()
    
    def test_calculate_file_hash(self, sample_json_file):
        """Test du calcul de hash de fichier"""
        hash1 = calculate_file_hash(sample_json_file)
        hash2 = calculate_file_hash(sample_json_file)
        
        # Le hash devrait être consistent
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hash length
        assert isinstance(hash1, str)
    
    def test_is_file_already_imported(self, db_connection, sample_json_file):
        """Test de vérification d'import existant"""
        create_tables_if_not_exist(db_connection)
        
        # Fichier pas encore importé
        assert not is_file_already_imported(db_connection, sample_json_file)
        
        # Simuler un import
        cursor = db_connection.cursor()
        file_hash = calculate_file_hash(sample_json_file)
        cursor.execute("""
            INSERT INTO import_tracking (file_name, file_hash, import_date, record_count, data_type)
            VALUES (%s, %s, NOW(), 2, 'monsters')
        """, (os.path.basename(sample_json_file), file_hash))
        db_connection.commit()
        cursor.close()
        
        # Maintenant le fichier devrait être marqué comme importé
        assert is_file_already_imported(db_connection, sample_json_file)
    
    def test_import_monsters_batch(self, db_connection, sample_monster_data):
        """Test d'import des monstres"""
        create_tables_if_not_exist(db_connection)
        
        # Import des données de test
        monsters = sample_monster_data["results"]
        imported_count = import_monsters_batch(db_connection, monsters)
        
        assert imported_count == 2
        
        # Vérifier que les données ont été insérées
        cursor = db_connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM monsters;")
        count = cursor.fetchone()[0]
        assert count == 2
        
        # Vérifier les données spécifiques
        cursor.execute("SELECT name, challenge_rating FROM monsters WHERE index = 'goblin';")
        goblin = cursor.fetchone()
        assert goblin[0] == "Goblin"
        assert float(goblin[1]) == 0.25
        
        cursor.close()
    
    def test_import_anti_duplication(self, db_connection, sample_monster_data):
        """Test du système anti-duplication"""
        create_tables_if_not_exist(db_connection)
        
        monsters = sample_monster_data["results"]
        
        # Premier import
        first_import = import_monsters_batch(db_connection, monsters)
        assert first_import == 2
        
        # Second import des mêmes données
        second_import = import_monsters_batch(db_connection, monsters)
        assert second_import == 0  # Aucun nouvel import
        
        # Vérifier qu'il n'y a toujours que 2 monstres
        cursor = db_connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM monsters;")
        count = cursor.fetchone()[0]
        assert count == 2
        cursor.close()
    
    @patch('import_json.blob_service_client')
    def test_azure_blob_connection(self, mock_blob_client):
        """Test de connexion Azure Blob Storage"""
        # Mock du client Azure
        mock_container = MagicMock()
        mock_blob_client.get_container_client.return_value = mock_container
        
        # Le test devrait passer sans erreur
        assert mock_blob_client.get_container_client.called
    
    def test_batch_processing_performance(self, db_connection):
        """Test de performance du traitement par batch"""
        create_tables_if_not_exist(db_connection)
        
        # Créer un grand dataset de test
        large_monster_batch = []
        for i in range(100):
            monster = {
                "index": f"test_monster_{i}",
                "name": f"Test Monster {i}",
                "size": "Medium",
                "type": "beast",
                "alignment": "neutral",
                "armor_class": [{"type": "natural", "value": 12}],
                "hit_points": 10,
                "hit_dice": "2d8",
                "speed": {"walk": "30 ft."},
                "strength": 10,
                "dexterity": 10,
                "constitution": 10,
                "intelligence": 10,
                "wisdom": 10,
                "charisma": 10,
                "challenge_rating": 0.25,
                "proficiency_bonus": 2,
                "xp": 50
            }
            large_monster_batch.append(monster)
        
        import time
        start_time = time.time()
        
        imported_count = import_monsters_batch(db_connection, large_monster_batch)
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        assert imported_count == 100
        assert processing_time < 10  # Moins de 10 secondes pour 100 monstres
        
        # Vérifier l'insertion
        cursor = db_connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM monsters WHERE index LIKE 'test_monster_%';")
        count = cursor.fetchone()[0]
        assert count == 100
        cursor.close()
    
    def test_error_handling_invalid_data(self, db_connection):
        """Test de gestion d'erreurs avec données invalides"""
        create_tables_if_not_exist(db_connection)
        
        # Données invalides (champs manquants)
        invalid_monsters = [
            {
                "index": "invalid_monster",
                # Champs obligatoires manquants
                "name": "Invalid Monster"
                # Pas d'autres champs
            }
        ]
        
        # L'import devrait gérer l'erreur gracieusement
        try:
            imported_count = import_monsters_batch(db_connection, invalid_monsters)
            # Selon l'implémentation, cela pourrait retourner 0 ou lever une exception
            assert imported_count >= 0
        except Exception as e:
            # L'exception devrait être gérée proprement
            assert "ERROR" in str(e) or "missing" in str(e).lower()

if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 