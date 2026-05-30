"""
ETL Pipeline - 编排整个数据流程
支持两种数据源: 真实Olist CSV数据 / 模拟数据
"""
import time

from .collector import DataCollector
from .csv_collector import CSVDataCollector
from .cleaner import DataCleaner, OlistDataCleaner
from .loader import DataLoader
from .feature_engineering import FeatureEngineer
from utils.timing import get_perf_logger, TimerContext

_perf = get_perf_logger()


class ETLPipeline:
    """ETL数据管道：采集 → 清洗 → 特征工程 → 加载

    Args:
        db_path: 数据库文件路径
        use_csv: True=使用真实Olist CSV数据, False=使用模拟数据
    """

    def __init__(self, db_path: str = None, use_csv: bool = True):
        self.use_csv = use_csv
        self.loader = DataLoader(db_path)
        self.feature_engineer = FeatureEngineer()

        if use_csv:
            self.collector = CSVDataCollector()
            self.cleaner = OlistDataCleaner()
        else:
            self.collector = DataCollector(seed=42)
            self.cleaner = DataCleaner()

    def run(self, n_customers: int = 5000, n_orders: int = 12000,
            n_products: int = 2000, n_sellers: int = 500) -> dict:
        """
        执行完整ETL流程

        Args:
            n_customers: 客户数量（仅模拟模式）
            n_orders: 订单数量（仅模拟模式）
            n_products: 商品数量（仅模拟模式）
            n_sellers: 卖家数量（仅模拟模式）

        Returns:
            dict: 数据集字典
        """
        start_time = time.time()
        source = "Olist CSV真实数据" if self.use_csv else "模拟数据"

        print("=" * 60)
        print(f"[START] ETL Pipeline 启动 (数据源: {source})")
        print("=" * 60)

        # Step 1: 采集
        print(f"\n[1/4] 数据采集")
        with TimerContext("etl_step1_collect", _perf):
            if self.use_csv:
                datasets = self.collector.collect_all()
            else:
                datasets = self.collector.collect_all(
                    n_customers=n_customers,
                    n_orders=n_orders,
                    n_products=n_products,
                    n_sellers=n_sellers,
                )

        # Step 2: 清洗
        print(f"\n[2/4] 数据清洗")
        with TimerContext("etl_step2_clean", _perf):
            cleaned = self.cleaner.clean_all(datasets)

        # Step 3: 特征工程
        print(f"\n[3/4] 特征工程")
        with TimerContext("etl_step3_features", _perf):
            featured = self.feature_engineer.add_all_features(cleaned)

        # Step 4: 加载
        print(f"\n[4/4] 数据加载")
        with TimerContext("etl_step4_load", _perf):
            self.loader.load_all(featured)

        elapsed = time.time() - start_time
        print(f"\n{'=' * 60}")
        print(f"[OK] ETL Pipeline 完成！耗时: {elapsed:.1f}秒")
        print(f"{'=' * 60}")

        return featured


if __name__ == "__main__":
    pipeline = ETLPipeline(use_csv=True)
    pipeline.run()
