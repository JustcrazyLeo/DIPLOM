class TableOptimizer:
    def __init__(self, db_manager):
        self.db = db_manager
    
    def apply_basic_indexes(self):
        """Применение базовых оптимизаций индексов"""
        optimizations = []
        
        # 1. Создание индекса на часто используемом поле customer_id
        self.db.execute_query("""
            CREATE INDEX idx_customer_id ON orders_after_optimization(customer_id);
        """)
        optimizations.append("✅ Индекс на customer_id создан")
        
        # 2. Составной индекс для часто используемых условий
        self.db.execute_query("""
            CREATE INDEX idx_status_date ON orders_after_optimization(status, order_date);
        """)
        optimizations.append("✅ Составной индекс на (status, order_date) создан")
        
        # 3. Частичный индекс для активных заказов
        self.db.execute_query("""
            CREATE INDEX idx_active_orders ON orders_after_optimization(customer_id) 
            WHERE status = 'pending';
        """)
        optimizations.append("✅ Частичный индекс для pending заказов создан")
        
        # 4. Индекс для покрывающего запроса (covering index)
        self.db.execute_query("""
            CREATE INDEX idx_covering_customer ON orders_after_optimization(customer_id, status, total_amount);
        """)
        optimizations.append("✅ Покрывающий индекс создан")
        
        # 5. Индекс на поле для сортировки
        self.db.execute_query("""
            CREATE INDEX idx_order_date_desc ON orders_after_optimization(order_date DESC);
        """)
        optimizations.append("✅ Индекс для сортировки по дате создан")
        
        return optimizations
    
    def apply_table_optimizations(self):
        """Оптимизация структуры таблицы"""
        optimizations = []
        
        # 1. Изменение типа данных для status (если бы были ENUM)
        try:
            self.db.execute_query("""
                ALTER TABLE orders_after_optimization 
                ALTER COLUMN status TYPE VARCHAR(10);
            """)
            optimizations.append("✅ Оптимизирован тип данных для status")
        except:
            pass
        
        # 2. Создание секционирования по дате (для PostgreSQL 10+)
        try:
            self.db.execute_query("""
                CREATE TABLE orders_partitioned (
                    LIKE orders_after_optimization INCLUDING ALL
                ) PARTITION BY RANGE (order_date);
                
                CREATE TABLE orders_2023 PARTITION OF orders_partitioned
                FOR VALUES FROM ('2023-01-01') TO ('2024-01-01');
                
                CREATE TABLE orders_2024 PARTITION OF orders_partitioned
                FOR VALUES FROM ('2024-01-01') TO ('2025-01-01');
            """)
            optimizations.append("✅ Секционирование по дате создано")
        except:
            optimizations.append("⚠️ Секционирование не поддерживается")
        
        # 3. Включение параллельных запросов
        self.db.execute_query("""
            ALTER TABLE orders_after_optimization 
            SET (parallel_workers = 4);
        """)
        optimizations.append("✅ Параллельные запросы включены")
        
        # 4. Оптимизация параметров таблицы
        self.db.execute_query("""
            ALTER TABLE orders_after_optimization 
            SET (fillfactor = 90);
        """)
        optimizations.append("✅ Fillfactor установлен в 90%")
        
        return optimizations
    
    def analyze_tables(self):
        """Сбор статистики для оптимизатора"""
        self.db.execute_query("ANALYZE orders_before_optimization;")
        self.db.execute_query("ANALYZE orders_after_optimization;")
        
        # Получение информации об индексах
        indexes = self.db.execute_query("""
            SELECT 
                tablename,
                indexname,
                indexdef
            FROM pg_indexes 
            WHERE tablename LIKE 'orders_%'
            ORDER BY tablename, indexname;
        """, fetch=True)
        
        return indexes
    
    def get_query_plans(self):
        """Получение планов выполнения запросов"""
        plans = []
        
        queries = [
            ("SELECT до оптимизации", """
                EXPLAIN (ANALYZE, BUFFERS) 
                SELECT * FROM orders_before_optimization 
                WHERE customer_id = 1234 AND status = 'completed';
            """),
            ("SELECT после оптимизации", """
                EXPLAIN (ANALYZE, BUFFERS) 
                SELECT * FROM orders_after_optimization 
                WHERE customer_id = 1234 AND status = 'completed';
            """),
            ("INSERT до оптимизации", """
                EXPLAIN (ANALYZE) 
                INSERT INTO orders_before_optimization 
                (customer_id, order_date, status, total_amount, product_id, region_id)
                VALUES (9999, CURRENT_DATE, 'pending', 500.00, 50, 5);
            """),
            ("INSERT после оптимизации", """
                EXPLAIN (ANALYZE) 
                INSERT INTO orders_after_optimization 
                (customer_id, order_date, status, total_amount, product_id, region_id)
                VALUES (9999, CURRENT_DATE, 'pending', 500.00, 50, 5);
            """)
        ]
        
        for name, query in queries:
            result = self.db.execute_query(query, fetch=True)
            plan_text = "\n".join([str(row) for row in result])
            plans.append({"query": name, "plan": plan_text[:500] + "..."})
        
        return plans