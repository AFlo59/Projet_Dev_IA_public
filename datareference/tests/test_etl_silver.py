"""
Tests pour le module ETL Silver (bronze_to_silver.py)
Test de la transformation des données Bronze vers Silver
"""

import pytest
import psycopg2
import os
import sys
from unittest.mock import patch, MagicMock

# Ajouter le répertoire parent au path pour les imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bronze_to_silver import (
    connect_to_databases,
    create_silver_schema,
    calculate_source_hash,
    is_transformation_needed,
    transform_monsters,
    transform_spells,
    transform_equipment,
    create_indexes_and_constraints
)

class TestETLSilver:
    """Tests pour les fonctions ETL Silver"""
    
    @pytest.fixture
    def bronze_connection(self):
        """Fixture pour la connexion à la base bronze de test"""
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
    def silver_connection(self):
        """Fixture pour la connexion à la base silver de test"""
        conn = psycopg2.connect(
            host=os.getenv('SILVER_PG_HOST', 'localhost'),
            port=os.getenv('SILVER_PG_PORT', '5436'),
            database=os.getenv('SILVER_DB_NAME', 'silver_db_test'),
            user=os.getenv('POSTGRES_USER'),
            password=os.getenv('POSTGRES_PASSWORD')
        )
        yield conn
        conn.close()
    
    @pytest.fixture
    def sample_bronze_data(self, bronze_connection):
        """Insérer des données de test dans la base bronze"""
        cursor = bronze_connection.cursor()
        
        # Créer les tables bronze si nécessaire
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS monsters (
                id SERIAL PRIMARY KEY,
                index VARCHAR(50) UNIQUE,
                name VARCHAR(100),
                size VARCHAR(20),
                type VARCHAR(50),
                subtype VARCHAR(50),
                alignment VARCHAR(50),
                armor_class JSONB,
                hit_points INTEGER,
                hit_dice VARCHAR(20),
                speed JSONB,
                strength INTEGER,
                dexterity INTEGER,
                constitution INTEGER,
                intelligence INTEGER,
                wisdom INTEGER,
                charisma INTEGER,
                challenge_rating DECIMAL,
                proficiency_bonus INTEGER,
                xp INTEGER,
                created_at TIMESTAMP DEFAULT NOW()
            );
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transformation_tracking (
                id SERIAL PRIMARY KEY,
                source_hash VARCHAR(64),
                transformation_date TIMESTAMP DEFAULT NOW(),
                records_processed INTEGER
            );
        """)
        
        # Insérer des données de test
        cursor.execute("""
            INSERT INTO monsters (index, name, size, type, alignment, armor_class, 
                                hit_points, hit_dice, speed, strength, dexterity, 
                                constitution, intelligence, wisdom, charisma, 
                                challenge_rating, proficiency_bonus, xp)
            VALUES 
                ('goblin', 'Goblin', 'Small', 'humanoid', 'neutral evil', 
                 '[{"type": "natural", "value": 15}]', 7, '2d6', 
                 '{"walk": "30 ft."}', 8, 14, 10, 10, 8, 8, 0.25, 2, 50),
                ('orc', 'Orc', 'Medium', 'humanoid', 'chaotic evil',
                 '[{"type": "natural", "value": 13}]', 15, '2d8+2',
                 '{"walk": "30 ft."}', 16, 12, 13, 7, 11, 10, 0.5, 2, 100),
                ('dragon', 'Ancient Red Dragon', 'Gargantuan', 'dragon', 'chaotic evil',
                 '[{"type": "natural", "value": 22}]', 546, '28d20+252',
                 '{"walk": "40 ft.", "climb": "40 ft.", "fly": "80 ft."}', 
                 30, 10, 29, 18, 15, 23, 24, 7, 62000)
            ON CONFLICT (index) DO NOTHING;
        """)
        
        bronze_connection.commit()
        cursor.close()
        
        yield "bronze_data_ready"
        
        # Cleanup
        cursor = bronze_connection.cursor()
        cursor.execute("TRUNCATE TABLE monsters CASCADE;")
        cursor.execute("TRUNCATE TABLE transformation_tracking CASCADE;")
        bronze_connection.commit()
        cursor.close()
    
    def test_connect_to_databases(self):
        """Test de connexion aux deux bases de données"""
        bronze_conn, silver_conn = connect_to_databases()
        
        assert bronze_conn is not None
        assert silver_conn is not None
        assert not bronze_conn.closed
        assert not silver_conn.closed
        
        bronze_conn.close()
        silver_conn.close()
    
    def test_create_silver_schema(self, silver_connection):
        """Test de création du schéma Silver"""
        try:
            create_silver_schema(silver_connection)
            silver_connection.commit()
        except Exception as e:
            pytest.fail(f"Création du schéma Silver échouée: {e}")
        
        # Vérifier que les tables Silver existent
        cursor = silver_connection.cursor()
        expected_tables = [
            'dim_monsters', 'dim_spells', 'dim_equipment', 
            'dim_classes', 'dim_races', 'fact_combat_stats'
        ]
        
        for table in expected_tables:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = %s
                );
            """, (table,))
            exists = cursor.fetchone()[0]
            assert exists, f"Table Silver {table} n'existe pas"
        
        cursor.close()
    
    def test_calculate_source_hash(self, bronze_connection, sample_bronze_data):
        """Test du calcul de hash des données source"""
        hash1 = calculate_source_hash(bronze_connection)
        hash2 = calculate_source_hash(bronze_connection)
        
        # Le hash devrait être consistent pour les mêmes données
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hash length
        assert isinstance(hash1, str)
    
    def test_is_transformation_needed(self, bronze_connection, silver_connection, sample_bronze_data):
        """Test de vérification de nécessité de transformation"""
        create_silver_schema(silver_connection)
        
        # Première transformation nécessaire
        assert is_transformation_needed(bronze_connection, silver_connection)
        
        # Simuler une transformation déjà effectuée
        current_hash = calculate_source_hash(bronze_connection)
        cursor = silver_connection.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transformation_tracking (
                id SERIAL PRIMARY KEY,
                source_hash VARCHAR(64),
                transformation_date TIMESTAMP DEFAULT NOW(),
                records_processed INTEGER
            );
        """)
        cursor.execute("""
            INSERT INTO transformation_tracking (source_hash, records_processed)
            VALUES (%s, 3)
        """, (current_hash,))
        silver_connection.commit()
        cursor.close()
        
        # Maintenant la transformation ne devrait plus être nécessaire
        assert not is_transformation_needed(bronze_connection, silver_connection)
    
    def test_transform_monsters(self, bronze_connection, silver_connection, sample_bronze_data):
        """Test de transformation des monstres Bronze vers Silver"""
        create_silver_schema(silver_connection)
        
        transformed_count = transform_monsters(bronze_connection, silver_connection)
        
        assert transformed_count == 3  # 3 monstres dans les données de test
        
        # Vérifier les données transformées
        cursor = silver_connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM dim_monsters;")
        count = cursor.fetchone()[0]
        assert count == 3
        
        # Vérifier la transformation de données spécifiques
        cursor.execute("""
            SELECT name, cr_numeric, creature_tier, armor_class_value 
            FROM dim_monsters WHERE monster_index = 'goblin';
        """)
        goblin = cursor.fetchone()
        assert goblin[0] == "Goblin"
        assert float(goblin[1]) == 0.25
        assert goblin[2] == "Low"  # Tier basé sur CR
        assert goblin[3] == 15
        
        # Vérifier le dragon (haut niveau)
        cursor.execute("""
            SELECT creature_tier, hit_points_category
            FROM dim_monsters WHERE monster_index = 'dragon';
        """)
        dragon = cursor.fetchone()
        assert dragon[0] == "Legendary"  # Tier basé sur CR 24
        assert dragon[1] == "Very High"  # HP > 500
        
        cursor.close()
    
    def test_transform_monsters_performance(self, bronze_connection, silver_connection):
        """Test de performance de transformation des monstres"""
        create_silver_schema(silver_connection)
        
        # Insérer un grand nombre de monstres dans bronze
        cursor = bronze_connection.cursor()
        monsters_data = []
        for i in range(1000):
            monsters_data.append((
                f'test_monster_{i}', f'Test Monster {i}', 'Medium', 'beast', 'neutral',
                '[{"type": "natural", "value": 12}]', 10, '2d8',
                '{"walk": "30 ft."}', 10, 10, 10, 10, 10, 10, 0.25, 2, 50
            ))
        
        cursor.executemany("""
            INSERT INTO monsters (index, name, size, type, alignment, armor_class, 
                                hit_points, hit_dice, speed, strength, dexterity, 
                                constitution, intelligence, wisdom, charisma, 
                                challenge_rating, proficiency_bonus, xp)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, monsters_data)
        bronze_connection.commit()
        cursor.close()
        
        import time
        start_time = time.time()
        
        transformed_count = transform_monsters(bronze_connection, silver_connection)
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        assert transformed_count == 1000
        assert processing_time < 30  # Moins de 30 secondes pour 1000 monstres
        
        # Cleanup
        cursor = bronze_connection.cursor()
        cursor.execute("DELETE FROM monsters WHERE index LIKE 'test_monster_%';")
        bronze_connection.commit()
        cursor.close()
    
    def test_create_indexes_and_constraints(self, silver_connection):
        """Test de création des index et contraintes"""
        create_silver_schema(silver_connection)
        
        try:
            create_indexes_and_constraints(silver_connection)
            silver_connection.commit()
        except Exception as e:
            pytest.fail(f"Création des index échouée: {e}")
        
        # Vérifier que les index existent
        cursor = silver_connection.cursor()
        cursor.execute("""
            SELECT indexname FROM pg_indexes 
            WHERE tablename IN ('dim_monsters', 'dim_spells', 'dim_equipment')
            AND schemaname = 'public';
        """)
        indexes = cursor.fetchall()
        
        # Il devrait y avoir au moins quelques index
        assert len(indexes) > 0
        
        # Vérifier des index spécifiques
        index_names = [idx[0] for idx in indexes]
        expected_indexes = ['idx_monsters_cr', 'idx_monsters_type', 'idx_spells_level']
        
        for expected_idx in expected_indexes:
            assert any(expected_idx in idx_name for idx_name in index_names), \
                f"Index {expected_idx} non trouvé"
        
        cursor.close()
    
    def test_full_transformation_pipeline(self, bronze_connection, silver_connection, sample_bronze_data):
        """Test du pipeline de transformation complet"""
        # 1. Créer le schéma Silver
        create_silver_schema(silver_connection)
        
        # 2. Vérifier que la transformation est nécessaire
        assert is_transformation_needed(bronze_connection, silver_connection)
        
        # 3. Effectuer toutes les transformations
        monsters_count = transform_monsters(bronze_connection, silver_connection)
        
        # 4. Créer les index
        create_indexes_and_constraints(silver_connection)
        
        # 5. Marquer la transformation comme effectuée
        current_hash = calculate_source_hash(bronze_connection)
        cursor = silver_connection.cursor()
        cursor.execute("""
            INSERT INTO transformation_tracking (source_hash, records_processed)
            VALUES (%s, %s)
        """, (current_hash, monsters_count))
        silver_connection.commit()
        cursor.close()
        
        # 6. Vérifier que la transformation n'est plus nécessaire
        assert not is_transformation_needed(bronze_connection, silver_connection)
        
        # 7. Vérifier les résultats finaux
        cursor = silver_connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM dim_monsters;")
        final_count = cursor.fetchone()[0]
        assert final_count == monsters_count
        cursor.close()
    
    def test_data_quality_validation(self, bronze_connection, silver_connection, sample_bronze_data):
        """Test de validation de la qualité des données"""
        create_silver_schema(silver_connection)
        transform_monsters(bronze_connection, silver_connection)
        
        cursor = silver_connection.cursor()
        
        # Vérifier qu'il n'y a pas de doublons
        cursor.execute("""
            SELECT monster_index, COUNT(*)
            FROM dim_monsters
            GROUP BY monster_index
            HAVING COUNT(*) > 1;
        """)
        duplicates = cursor.fetchall()
        assert len(duplicates) == 0, f"Doublons trouvés: {duplicates}"
        
        # Vérifier que tous les champs obligatoires sont remplis
        cursor.execute("""
            SELECT COUNT(*) FROM dim_monsters
            WHERE name IS NULL OR monster_index IS NULL OR creature_type IS NULL;
        """)
        null_required_fields = cursor.fetchone()[0]
        assert null_required_fields == 0, "Champs obligatoires manquants"
        
        # Vérifier la cohérence des données (CR vs Tier)
        cursor.execute("""
            SELECT COUNT(*) FROM dim_monsters
            WHERE cr_numeric >= 17 AND creature_tier != 'Legendary';
        """)
        inconsistent_tiers = cursor.fetchone()[0]
        assert inconsistent_tiers == 0, "Incohérence dans les tiers de créatures"
        
        cursor.close()
    
    def test_incremental_transformation(self, bronze_connection, silver_connection, sample_bronze_data):
        """Test de transformation incrémentale"""
        create_silver_schema(silver_connection)
        
        # Première transformation
        transform_monsters(bronze_connection, silver_connection)
        
        # Ajouter de nouvelles données dans bronze
        cursor = bronze_connection.cursor()
        cursor.execute("""
            INSERT INTO monsters (index, name, size, type, alignment, armor_class, 
                                hit_points, hit_dice, speed, strength, dexterity, 
                                constitution, intelligence, wisdom, charisma, 
                                challenge_rating, proficiency_bonus, xp)
            VALUES ('new_monster', 'New Monster', 'Large', 'beast', 'neutral',
                   '[{"type": "natural", "value": 14}]', 25, '4d10+4',
                   '{"walk": "40 ft."}', 15, 12, 14, 3, 12, 6, 2, 2, 450)
        """)
        bronze_connection.commit()
        cursor.close()
        
        # La transformation devrait maintenant être nécessaire
        assert is_transformation_needed(bronze_connection, silver_connection)
        
        # Seconde transformation (incrémentale)
        new_count = transform_monsters(bronze_connection, silver_connection)
        
        # Vérifier que le nouveau monstre a été ajouté
        cursor = silver_connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM dim_monsters WHERE monster_index = 'new_monster';")
        new_monster_count = cursor.fetchone()[0]
        assert new_monster_count == 1
        
        # Vérifier le total
        cursor.execute("SELECT COUNT(*) FROM dim_monsters;")
        total_count = cursor.fetchone()[0]
        assert total_count == 4  # 3 originaux + 1 nouveau
        
        cursor.close()

if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 