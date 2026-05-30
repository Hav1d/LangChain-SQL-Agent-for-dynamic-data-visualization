"""
CSV数据采集模块 - 从Olist真实CSV文件读取电商数据
替代SimulatedDataCollector，使用Kaggle Brazilian E-Commerce真实数据集
"""
from pathlib import Path

import pandas as pd

from config import DATA_DIR


# CSV文件名映射：逻辑名 -> 实际文件名
_CSV_FILENAMES = {
    "customers": "customers_dataset.csv",
    "sellers": "sellers_dataset.csv",
    "products": "products_dataset.csv",
    "orders": "orders_dataset.csv",
    "order_items": "order_items_dataset.csv",
    "order_payments": "order_payments_dataset.csv",
    "order_reviews": "order_reviews_dataset.csv",
    "category_translation": "product_category_name_translation.csv",
    "geolocation": "geolocation_dataset.csv",
}


class CSVDataCollector:
    """从本地CSV文件读取Olist真实电商数据集"""

    def __init__(self, data_dir: str = None):
        """
        初始化CSV数据采集器

        Args:
            data_dir: CSV文件所在目录路径，默认为 config.DATA_DIR / "olist"
        """
        if data_dir is not None:
            self.data_dir = Path(data_dir)
        else:
            self.data_dir = DATA_DIR / "olist"

        if not self.data_dir.is_dir():
            raise FileNotFoundError(f"数据目录不存在: {self.data_dir}")

    # ──────────────────────────────────────────────
    # 公共接口
    # ──────────────────────────────────────────────

    def collect_all(self) -> dict:
        """
        读取所有CSV文件并返回结构化数据集

        Returns:
            dict: 包含以下键的DataFrame字典:
                - customers:          客户信息
                - sellers:            卖家信息
                - products:           商品信息
                - orders:             订单信息（含total_price, total_freight）
                - order_items:        订单明细
                - order_payments:     支付信息
                - order_reviews:      评价信息
                - category_translation: 类目翻译
        """
        print("[CSV] 开始读取Olist真实数据集...")

        customers = self._read_csv("customers")
        sellers = self._read_csv("sellers")
        products = self._read_csv("products")
        orders = self._read_csv("orders")
        order_items = self._read_csv("order_items")
        order_payments = self._read_csv("order_payments")
        order_reviews = self._read_csv("order_reviews")
        category_translation = self._read_csv("category_translation", handle_bom=True)

        # 将order_items的price和freight_value汇总到orders
        orders = self._attach_order_totals(orders, order_items)

        datasets = {
            "customers": customers,
            "sellers": sellers,
            "products": products,
            "orders": orders,
            "order_items": order_items,
            "order_payments": order_payments,
            "order_reviews": order_reviews,
            "category_translation": category_translation,
        }

        # 打印摘要
        print("\n[CSV] 数据读取完成！")
        for name, df in datasets.items():
            print(f"  {name}: {len(df):,} 条记录")

        return datasets

    # ──────────────────────────────────────────────
    # 内部方法
    # ──────────────────────────────────────────────

    def _resolve_path(self, key: str) -> Path:
        """
        解析CSV文件路径，自动处理双扩展名(.csv.csv)等异常情况

        Args:
            key: 逻辑文件名键（如 "customers"）

        Returns:
            Path: 解析后的文件路径

        Raises:
            FileNotFoundError: 找不到对应的CSV文件
        """
        expected_name = _CSV_FILENAMES[key]
        direct_path = self.data_dir / expected_name

        if direct_path.is_file():
            return direct_path

        # 处理双扩展名：有些来源会生成 customers_dataset.csv.csv
        double_ext = self.data_dir / (expected_name + ".csv")
        if double_ext.is_file():
            return double_ext

        # 兜底：按前缀模糊匹配
        stem = expected_name.replace(".csv", "")
        for candidate in self.data_dir.iterdir():
            if candidate.is_file() and candidate.name.startswith(stem) and candidate.suffix == ".csv":
                return candidate

        raise FileNotFoundError(
            f"找不到 {key} 对应的CSV文件: {self.data_dir / expected_name}"
        )

    def _read_csv(self, key: str, handle_bom: bool = False) -> pd.DataFrame:
        """
        读取单个CSV文件，自动处理编码和BOM

        Args:
            key: 逻辑文件名键
            handle_bom: 是否处理UTF-8 BOM字符

        Returns:
            pd.DataFrame: 读取的数据
        """
        path = self._resolve_path(key)
        expected_rows = self._expected_row_count(key)

        # 带BOM的文件使用utf-8-sig编码（自动剥离BOM）
        if handle_bom:
            encodings = ["utf-8-sig", "utf-8", "latin-1"]
        else:
            encodings = ["utf-8", "latin-1"]

        df = None
        last_error = None
        for encoding in encodings:
            try:
                df = pd.read_csv(path, encoding=encoding)
                break
            except UnicodeDecodeError as exc:
                last_error = exc
                continue

        if df is None:
            raise RuntimeError(
                f"无法以任何编码读取文件 {path}: {last_error}"
            )

        # 进度输出
        row_info = f"{len(df):,} rows"
        if expected_rows and abs(len(df) - expected_rows) > expected_rows * 0.01:
            row_info += f" (expected ~{expected_rows:,})"
        print(f"  [CSV] 读取 {path.name}... ({row_info})")

        return df

    def _attach_order_totals(self, orders: pd.DataFrame,
                             order_items: pd.DataFrame) -> pd.DataFrame:
        """
        将订单明细的price和freight_value汇总后挂载到orders上

        Args:
            orders: 订单DataFrame
            order_items: 订单明细DataFrame

        Returns:
            pd.DataFrame: 带有total_price和total_freight列的orders
        """
        totals = (
            order_items
            .groupby("order_id", as_index=False)
            .agg(
                total_price=("price", "sum"),
                total_freight=("freight_value", "sum"),
            )
        )

        orders = orders.merge(totals, on="order_id", how="left")
        orders["total_price"] = orders["total_price"].fillna(0.0)
        orders["total_freight"] = orders["total_freight"].fillna(0.0)

        print(f"  [CSV] 挂载订单总价: {len(totals):,} 个订单匹配成功")
        return orders

    @staticmethod
    def _expected_row_count(key: str) -> int | None:
        """返回各数据集的预期行数，用于进度输出校验"""
        counts = {
            "customers": 99_441,
            "sellers": 3_095,
            "products": 32_951,
            "orders": 99_441,
            "order_items": 112_650,
            "order_payments": 103_886,
            "order_reviews": 104_719,
            "category_translation": 70,
            "geolocation": 1_000_163,
        }
        return counts.get(key)
