import time
import statistics
from tqdm import tqdm
import pandas as pd

class Benchmark:
    def __init__(self, db_manager):
        self.db = db_manager
        self.results = []
    
    def measure_query_time(self, query, params=None, iterations=10):
        """Измерение времени выполнения запроса"""
        times = []
        
        for i in range(iterations):
            start_time = time.perf_counter()
            self.db.execute_query(query, params)
            end_time = time.perf_counter()
            times.append((end_time - start_time) * 1000)  # в мс
        
        return {
            "avg": statistics.mean(times),
            "min": min(times),
            "max": max(times),
            "std": statistics.stdev(times) if len(times) > 1 else 0
        }
    
    def run_oltp_scenarios_before(self):
        """Запуск тестовых сценариев OLTP до оптимизации"""
        scenarios = []
        
        # 1. Точечный SELECT
        result = self.measure_query_time("""
            SELECT * FROM orders_before_optimization 
            WHERE id = %s;
        """, (500000,), 50)
        scenarios.append({"test": "SELECT по PK", "table": "before", **result})
        
        # 2. SELECT с фильтром по неуникальному полю
        result = self.measure_query_time("""
            SELECT * FROM orders_before_optimization 
            WHERE customer_id = %s AND status = 'completed';
        """, (1234,), 30)
        scenarios.append({"test": "SELECT по customer_id", "table": "before", **result})
        
        # 3. Агрегация по диапазону
        result = self.measure_query_time("""
            SELECT status, COUNT(*), SUM(total_amount)
            FROM orders_before_optimization 
            WHERE order_date BETWEEN '2023-01-01' AND '2023-12-31'
            GROUP BY status;
        """, iterations=20)
        scenarios.append({"test": "Агрегация с GROUP BY", "table": "before", **result})
        
        # 4. INSERT новой записи
        result = self.measure_query_time("""
            INSERT INTO orders_before_optimization 
            (customer_id, order_date, status, total_amount, product_id, region_id)
            VALUES (%s, CURRENT_DATE, 'pending', %s, %s, %s);
        """, (9999, 500.00, 50, 5), 100)
        scenarios.append({"test": "INSERT", "table": "before", **result})
        
        # 5. UPDATE по условию
        result = self.measure_query_time("""
            UPDATE orders_before_optimization 
            SET status = 'completed' 
            WHERE customer_id = %s AND status = 'pending';
        """, (9999,), 50)
        scenarios.append({"test": "UPDATE", "table": "before", **result})
        
        self.results.extend(scenarios)
        return scenarios
    
    def run_oltp_scenarios_after(self):
        """Запуск тестовых сценариев OLTP после оптимизации"""
        scenarios = []
        
        # Те же тесты для оптимизированной таблицы
        result = self.measure_query_time("""
            SELECT * FROM orders_after_optimization 
            WHERE id = %s;
        """, (500000,), 50)
        scenarios.append({"test": "SELECT по PK", "table": "after", **result})
        
        result = self.measure_query_time("""
            SELECT * FROM orders_after_optimization 
            WHERE customer_id = %s AND status = 'completed';
        """, (1234,), 30)
        scenarios.append({"test": "SELECT по customer_id", "table": "after", **result})
        
        result = self.measure_query_time("""
            SELECT status, COUNT(*), SUM(total_amount)
            FROM orders_after_optimization 
            WHERE order_date BETWEEN '2023-01-01' AND '2023-12-31'
            GROUP BY status;
        """, iterations=20)
        scenarios.append({"test": "Агрегация с GROUP BY", "table": "after", **result})
        
        result = self.measure_query_time("""
            INSERT INTO orders_after_optimization 
            (customer_id, order_date, status, total_amount, product_id, region_id)
            VALUES (%s, CURRENT_DATE, 'pending', %s, %s, %s);
        """, (9999, 500.00, 50, 5), 100)
        scenarios.append({"test": "INSERT", "table": "after", **result})
        
        result = self.measure_query_time("""
            UPDATE orders_after_optimization 
            SET status = 'completed' 
            WHERE customer_id = %s AND status = 'pending';
        """, (9999,), 50)
        scenarios.append({"test": "UPDATE", "table": "after", **result})
        
        self.results.extend(scenarios)
        return scenarios
    
    def run_concurrent_test(self, num_threads=10, operations_per_thread=100):
        """Тест конкурентного доступа"""
        import threading
        
        results_lock = threading.Lock()
        all_times = []
        
        def worker(worker_id):
            local_times = []
            db_local = type(self.db)(**self.db.conn_params)
            db_local.connect()
            
            for i in range(operations_per_thread):
                # Чередуем операции
                if i % 3 == 0:
                    # SELECT
                    start = time.perf_counter()
                    db_local.execute_query(
                        "SELECT * FROM orders_after_optimization WHERE customer_id = %s LIMIT 5;",
                        (worker_id % 1000,)
                    )
                    local_times.append(time.perf_counter() - start)
                elif i % 3 == 1:
                    # INSERT
                    start = time.perf_counter()
                    db_local.execute_query("""
                        INSERT INTO orders_after_optimization 
                        (customer_id, order_date, status, total_amount, product_id, region_id)
                        VALUES (%s, CURRENT_DATE, 'pending', %s, %s, %s);
                    """, (worker_id, 100.00, 1, 1))
                    local_times.append(time.perf_counter() - start)
                else:
                    # UPDATE
                    start = time.perf_counter()
                    db_local.execute_query("""
                        UPDATE orders_after_optimization 
                        SET total_amount = total_amount + 1 
                        WHERE id = (SELECT id FROM orders_after_optimization WHERE customer_id = %s LIMIT 1);
                    """, (worker_id % 1000,))
                    local_times.append(time.perf_counter() - start)
            
            with results_lock:
                all_times.extend(local_times)
        
        # Запуск потоков
        threads = []
        start_total = time.perf_counter()
        
        for i in range(num_threads):
            thread = threading.Thread(target=worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        total_time = time.perf_counter() - start_total
        
        return {
            "total_operations": num_threads * operations_per_thread,
            "total_time_sec": total_time,
            "ops_per_second": (num_threads * operations_per_thread) / total_time,
            "avg_op_time_ms": statistics.mean(all_times) * 1000 if all_times else 0
        }