import psycopg2
from psycopg2.extras import RealDictCursor
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self, dbname="diploma_db", user="postgres", password="password", host="localhost"):
        self.conn_params = {
            "dbname": dbname,
            "user": user,
            "password": password,
            "host": host
        }
        
    def connect(self):
        """Установка соединения с БД"""
        try:
            self.connection = psycopg2.connect(**self.conn_params)
            logger.info("✅ Подключение к БД установлено")
            return self.connection
        except Exception as e:
            logger.error(f"❌ Ошибка подключения: {e}")
            raise
    
    def execute_query(self, query, params=None, fetch=False):
        """Выполнение SQL запроса"""
        with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query, params or ())
            if fetch:
                return cursor.fetchall()
            self.connection.commit()
    
    def create_test_tables(self):
        """Создание тестовых таблиц для исследования"""
        queries = [
            """
            DROP TABLE IF EXISTS orders_before_optimization;
            """,
            """
            DROP TABLE IF EXISTS orders_after_optimization;
            """,
            """
            CREATE TABLE orders_before_optimization (
                id BIGSERIAL PRIMARY KEY,
                customer_id INT NOT NULL,
                order_date DATE NOT NULL,
                status VARCHAR(20) NOT NULL,
                total_amount DECIMAL(10,2),
                product_id INT,
                region_id INT,
                created_at TIMESTAMP DEFAULT NOW()
            );
            """,
            """
            CREATE TABLE orders_after_optimization (
                id BIGSERIAL PRIMARY KEY,
                customer_id INT NOT NULL,
                order_date DATE NOT NULL,
                status VARCHAR(20) NOT NULL,
                total_amount DECIMAL(10,2),
                product_id INT,
                region_id INT,
                created_at TIMESTAMP DEFAULT NOW()
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS audit_log (
                id BIGSERIAL PRIMARY KEY,
                table_name VARCHAR(50),
                operation VARCHAR(20),
                rows_count INT,
                execution_time_ms FLOAT,
                timestamp TIMESTAMP DEFAULT NOW()
            );
            """
        ]
        
        for query in queries:
            self.execute_query(query)
        logger.info("✅ Тестовые таблицы созданы")
    
    def generate_test_data(self, num_records=1000000):
        """Генерация тестовых данных"""
        logger.info(f"Генерация {num_records} тестовых записей...")
        
        # Генерация для таблицы ДО оптимизации
        self.execute_query(f"""
            INSERT INTO orders_before_optimization 
            (customer_id, order_date, status, total_amount, product_id, region_id)
            SELECT 
                floor(random() * 10000 + 1)::int,
                CURRENT_DATE - (random() * 365)::int,
                CASE WHEN random() < 0.3 THEN 'pending' 
                     WHEN random() < 0.6 THEN 'completed' 
                     ELSE 'cancelled' END,
                round((random() * 1000 + 1)::numeric, 2),
                floor(random() * 100 + 1)::int,
                floor(random() * 10 + 1)::int
            FROM generate_series(1, {num_records});
        """)
        
        # Копирование тех же данных для таблицы ПОСЛЕ оптимизации
        self.execute_query(f"""
            INSERT INTO orders_after_optimization 
            SELECT * FROM orders_before_optimization;
        """)
        
        logger.info("✅ Тестовые данные сгенерированы")
    
    def get_table_stats(self, table_name):
        """Получение статистики по таблице"""
        stats = self.execute_query(f"""
            SELECT 
                schemaname,
                tablename,
                pg_size_pretty(pg_total_relation_size('{table_name}')) as total_size,
                pg_size_pretty(pg_relation_size('{table_name}')) as table_size,
                pg_size_pretty(pg_indexes_size('{table_name}')) as indexes_size,
                n_live_tup as row_count
            FROM pg_stat_user_tables 
            WHERE relname = '{table_name}';
        """, fetch=True)
        
        return stats[0] if stats else None