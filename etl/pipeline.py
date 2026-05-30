"""
ETL Pipeline - 编排整个数据流程
"""
import time

from .collector import DataCollector
from .cleaner import DataCleaner
from .loader import DataLoader


class ETLPipeline:
    """ETL数据管道：采集 → 清洗 → 加载"""

    def __init__(self, db_path: str = None):
        self.collector = DataCollector(seed=42)
        self.cleaner = DataCleaner()
        self.loader = DataLoader(db_path)

    def run(self, n_customers: int = 5000, n_orders: int = 12000,
            n_products: int = 2000, n_sellers: int = 500) -> dict:
        """
        执行完整ETL流程

        Args:
            n_customers: 客户数量
            n_orders: 订单数量
            n_products: 商品数量
            n_sellers: 卖家数量

        Returns:
            dict: 数据集字典
        """
        start_time = time.time()

        print("=" * 60)
        print("[START] ETL Pipeline 启动")
        print("=" * 60)

        # Step 1: 采集
        print("\n[1/3] 数据采集")
        datasets = self.collector.collect_all(
            n_customers=n_customers,
            n_orders=n_orders,
            n_products=n_products,
            n_sellers=n_sellers,
        )

        # Step 2: 清洗
        print("\n[2/3] 数据清洗")
        cleaned = self.cleaner.clean_all(datasets)

        # Step 3: 加载
        print("\n[3/3] 数据加载")
        self.loader.load_all(cleaned)

        elapsed = time.time() - start_time
        print(f"\n{'=' * 60}")
        print(f"[OK] ETL Pipeline 完成！耗时: {elapsed:.1f}秒")
        print(f"{'=' * 60}")

        return cleaned


if __name__ == "__main__":
    pipeline = ETLPipeline()
    pipeline.run()
