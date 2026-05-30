"""
数据加载模块 - 将清洗后的数据写入SQLite数据库
"""
import os
import sqlite3
from pathlib import Path

import pandas as pd

from config import DB_PATH, DATA_DIR


class DataLoader:
    """将数据加载到SQLite数据库"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(DB_PATH)

    def _create_tables(self, conn):
        """创建数据库表结构"""
        conn.executescript("""
            -- 删除旧表（按依赖顺序）
            DROP TABLE IF EXISTS order_payments;
            DROP TABLE IF EXISTS order_reviews;
            DROP TABLE IF EXISTS order_items;
            DROP TABLE IF EXISTS orders;
            DROP TABLE IF EXISTS products;
            DROP TABLE IF EXISTS sellers;
            DROP TABLE IF EXISTS customers;
            DROP TABLE IF EXISTS category_translation;
            DROP TABLE IF EXISTS rfm_results;
            DROP TABLE IF EXISTS analysis_reports;

            -- 客户表
            CREATE TABLE customers (
                customer_id TEXT PRIMARY KEY,
                customer_unique_id TEXT,
                customer_zip_code_prefix INTEGER,
                customer_city TEXT,
                customer_state TEXT
            );

            -- 卖家表
            CREATE TABLE sellers (
                seller_id TEXT PRIMARY KEY,
                seller_zip_code_prefix INTEGER,
                seller_city TEXT,
                seller_state TEXT
            );

            -- 商品表
            CREATE TABLE products (
                product_id TEXT PRIMARY KEY,
                product_category_name TEXT,
                product_name_lenght REAL,
                product_description_lenght REAL,
                product_photos_qty REAL,
                product_weight_g REAL,
                product_length_cm REAL,
                product_height_cm REAL,
                product_width_cm REAL
            );

            -- 订单表
            CREATE TABLE orders (
                order_id TEXT PRIMARY KEY,
                customer_id TEXT,
                order_status TEXT,
                order_purchase_timestamp TEXT,
                order_approved_at TEXT,
                order_delivered_carrier_date TEXT,
                order_delivered_customer_date TEXT,
                order_estimated_delivery_date TEXT,
                total_price REAL,
                total_freight REAL,
                delivery_time_days REAL,
                delay_vs_estimate REAL,
                shipping_time REAL,
                order_value_category TEXT,
                FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
            );

            -- 订单明细表
            CREATE TABLE order_items (
                order_id TEXT,
                order_item_id INTEGER,
                product_id TEXT,
                seller_id TEXT,
                shipping_limit_date TEXT,
                price REAL,
                freight_value REAL,
                items_per_order INTEGER,
                PRIMARY KEY (order_id, order_item_id),
                FOREIGN KEY (order_id) REFERENCES orders(order_id),
                FOREIGN KEY (product_id) REFERENCES products(product_id),
                FOREIGN KEY (seller_id) REFERENCES sellers(seller_id)
            );

            -- 支付表
            CREATE TABLE order_payments (
                order_id TEXT,
                payment_sequential INTEGER,
                payment_type TEXT,
                payment_installments INTEGER,
                payment_value REAL,
                PRIMARY KEY (order_id, payment_sequential),
                FOREIGN KEY (order_id) REFERENCES orders(order_id)
            );

            -- 评价表
            CREATE TABLE order_reviews (
                review_id TEXT PRIMARY KEY,
                order_id TEXT,
                review_score INTEGER,
                review_comment_title TEXT,
                review_comment_message TEXT,
                review_creation_date TEXT,
                review_answer_timestamp TEXT,
                FOREIGN KEY (order_id) REFERENCES orders(order_id)
            );

            -- 类目翻译表
            CREATE TABLE category_translation (
                product_category_name TEXT PRIMARY KEY,
                product_category_name_english TEXT
            );

            -- RFM分析结果表
            CREATE TABLE rfm_results (
                customer_id TEXT PRIMARY KEY,
                recency INTEGER,
                frequency INTEGER,
                monetary REAL,
                r_score INTEGER,
                f_score INTEGER,
                m_score INTEGER,
                rfm_score TEXT,
                segment TEXT,
                cluster_label INTEGER,
                analysis_date TEXT
            );

            -- 分析报告表（供RAG使用）
            CREATE TABLE analysis_reports (
                report_id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_type TEXT,
                title TEXT,
                content TEXT,
                created_at TEXT
            );
        """)

    def _create_indexes(self, conn):
        """创建索引以加速查询"""
        conn.executescript("""
            CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_id);
            CREATE INDEX IF NOT EXISTS idx_orders_date ON orders(order_purchase_timestamp);
            CREATE INDEX IF NOT EXISTS idx_order_items_order ON order_items(order_id);
            CREATE INDEX IF NOT EXISTS idx_order_items_product ON order_items(product_id);
            CREATE INDEX IF NOT EXISTS idx_payments_order ON order_payments(order_id);
            CREATE INDEX IF NOT EXISTS idx_reviews_order ON order_reviews(order_id);
            CREATE INDEX IF NOT EXISTS idx_products_category ON products(product_category_name);
            CREATE INDEX IF NOT EXISTS idx_rfm_segment ON rfm_results(segment);
        """)

    def load_all(self, datasets: dict) -> None:
        """将所有数据集写入数据库"""
        print("[LOAD] 开始加载数据到数据库...")

        # 确保data目录存在
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        conn = sqlite3.connect(self.db_path)

        try:
            # 创建表
            self._create_tables(conn)
            print("  [OK] 表结构创建完成")

            # 写入数据
            table_order = [
                "customers", "sellers", "products", "category_translation",
                "orders", "order_items", "order_payments", "order_reviews"
            ]

            for table_name in table_order:
                if table_name in datasets:
                    df = datasets[table_name]
                    # 处理NaT值
                    for col in df.select_dtypes(include=["datetime64"]).columns:
                        df[col] = df[col].astype(str).replace("NaT", None)
                    df.to_sql(table_name, conn, if_exists="append", index=False)
                    print(f"  [OK] {table_name}: {len(df):,} 条记录写入成功")

            # 创建索引
            self._create_indexes(conn)
            print("  [OK] 索引创建完成")

            conn.commit()
            print(f"\n[OK] 数据库加载完成: {self.db_path}")

            # 打印数据库大小
            db_size = os.path.getsize(self.db_path) / (1024 * 1024)
            print(f"   数据库大小: {db_size:.1f} MB")

        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
