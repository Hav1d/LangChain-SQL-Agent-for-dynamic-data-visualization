"""ETL模块测试"""
import os
import sys
import sqlite3
import tempfile

# 确保项目根目录在path中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import pandas as pd


@pytest.fixture
def temp_db(tmp_path):
    """创建临时数据库"""
    return str(tmp_path / "test.db")


class TestDataCollector:
    """测试数据采集器"""

    def test_generate_customers(self):
        from etl.collector import DataCollector
        collector = DataCollector(seed=42)
        datasets = collector.collect_all(n_customers=100, n_orders=200, n_products=50, n_sellers=20)

        assert "customers" in datasets
        assert len(datasets["customers"]) == 100
        assert "customer_id" in datasets["customers"].columns
        assert "customer_state" in datasets["customers"].columns

    def test_generate_orders(self):
        from etl.collector import DataCollector
        collector = DataCollector(seed=42)
        datasets = collector.collect_all(n_customers=100, n_orders=200, n_products=50, n_sellers=20)

        assert "orders" in datasets
        assert len(datasets["orders"]) > 0
        assert "order_id" in datasets["orders"].columns
        assert "customer_id" in datasets["orders"].columns

    def test_generate_order_items(self):
        from etl.collector import DataCollector
        collector = DataCollector(seed=42)
        datasets = collector.collect_all(n_customers=100, n_orders=200, n_products=50, n_sellers=20)

        assert "order_items" in datasets
        assert len(datasets["order_items"]) > 0
        assert "price" in datasets["order_items"].columns

    def test_all_datasets_present(self):
        from etl.collector import DataCollector
        collector = DataCollector(seed=42)
        datasets = collector.collect_all(n_customers=50, n_orders=100, n_products=30, n_sellers=10)

        expected = ["customers", "sellers", "products", "orders", "order_items",
                    "order_payments", "order_reviews", "category_translation"]
        for name in expected:
            assert name in datasets, f"缺少数据集: {name}"


class TestDataCleaner:
    """测试数据清洗器"""

    def test_clean_customers(self):
        from etl.cleaner import DataCleaner
        cleaner = DataCleaner()

        df = pd.DataFrame({
            "customer_id": ["c1", "c2", "c1"],  # 有重复
            "customer_city": [" Sao Paulo ", "rio", " sao paulo "],
            "customer_state": ["sp", "rj", "sp"],
            "customer_zip_code_prefix": [1000, 2000, 1000],
        })
        result = cleaner.clean_customers(df)
        assert len(result) == 2  # 去重后2条

    def test_clean_orders(self):
        from etl.cleaner import DataCleaner
        cleaner = DataCleaner()

        df = pd.DataFrame({
            "order_id": ["o1", "o2"],
            "customer_id": ["c1", "c2"],
            "order_purchase_timestamp": ["2018-01-01 10:00:00", "2018-06-15 12:00:00"],
            "order_status": ["delivered", "shipped"],
        })
        result = cleaner.clean_orders(df)
        assert len(result) == 2

    def test_clean_payments_negative(self):
        from etl.cleaner import DataCleaner
        cleaner = DataCleaner()

        df = pd.DataFrame({
            "order_id": ["o1"],
            "payment_value": [-10.0],
            "payment_installments": [0],
            "payment_type": ["credit_card"],
        })
        result = cleaner.clean_payments(df)
        assert result["payment_value"].iloc[0] > 0
        assert result["payment_installments"].iloc[0] >= 1


class TestETLPipeline:
    """测试完整ETL流程"""

    def test_pipeline_creates_database(self, temp_db):
        from etl.pipeline import ETLPipeline
        pipeline = ETLPipeline(db_path=temp_db, use_csv=False)
        pipeline.run(n_customers=50, n_orders=100, n_products=30, n_sellers=10)

        # 验证数据库存在
        assert os.path.exists(temp_db)

        # 验证表结构
        conn = sqlite3.connect(temp_db)
        tables = pd.read_sql_query(
            "SELECT name FROM sqlite_master WHERE type='table'", conn
        )["name"].tolist()
        conn.close()

        expected_tables = ["customers", "orders", "order_items", "order_payments",
                          "order_reviews", "products", "sellers",
                          "category_translation", "rfm_results", "analysis_reports"]
        for table in expected_tables:
            assert table in tables, f"缺少表: {table}"

    def test_pipeline_data_integrity(self, temp_db):
        from etl.pipeline import ETLPipeline
        pipeline = ETLPipeline(db_path=temp_db, use_csv=False)
        pipeline.run(n_customers=50, n_orders=100, n_products=30, n_sellers=10)

        conn = sqlite3.connect(temp_db)

        # 客户数
        count = pd.read_sql_query("SELECT COUNT(*) as cnt FROM customers", conn)["cnt"].iloc[0]
        assert count == 50

        # 订单数
        count = pd.read_sql_query("SELECT COUNT(*) as cnt FROM orders", conn)["cnt"].iloc[0]
        assert count > 0

        # 外键完整性
        orphan = pd.read_sql_query("""
            SELECT COUNT(*) as cnt FROM orders o
            LEFT JOIN customers c ON o.customer_id = c.customer_id
            WHERE c.customer_id IS NULL
        """, conn)["cnt"].iloc[0]
        assert orphan == 0, f"存在 {orphan} 条孤立订单"

        conn.close()
