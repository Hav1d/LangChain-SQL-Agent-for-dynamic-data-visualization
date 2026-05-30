"""
特征工程模块 - 为Olist电商数据添加衍生特征
"""
import pandas as pd
import numpy as np


class FeatureEngineer:
    """Olist数据特征工程器"""

    def _add_order_features(self, orders: pd.DataFrame) -> pd.DataFrame:
        """添加订单时间特征"""
        print("[FEATURE] 添加订单特征...")
        df = orders.copy()

        # 配送天数: 实际送达日期 - 审批日期
        df["delivery_time_days"] = (
            df["order_delivered_customer_date"] - df["order_approved_at"]
        ).dt.days

        # 延迟天数: 实际送达日期 - 预计送达日期 (负数表示提前送达)
        df["delay_vs_estimate"] = (
            df["order_delivered_customer_date"] - df["order_estimated_delivery_date"]
        ).dt.days

        # 运输时间: 预计送达日期 - 购买日期
        df["shipping_time"] = (
            df["order_estimated_delivery_date"] - df["order_purchase_timestamp"]
        ).dt.days

        return df

    def _add_order_item_features(self, order_items: pd.DataFrame) -> pd.DataFrame:
        """添加订单明细特征"""
        print("[FEATURE] 添加订单明细特征...")
        df = order_items.copy()

        # 每个订单的商品数量
        items_per_order = df.groupby("order_id")["order_item_id"].transform("count")
        df["items_per_order"] = items_per_order

        return df

    def _add_order_value_category(self, orders: pd.DataFrame, order_items: pd.DataFrame) -> pd.DataFrame:
        """添加订单价值分类"""
        df = orders.copy()

        # 如果total_price列不存在，从order_items计算
        if "total_price" not in df.columns:
            total_price = order_items.groupby("order_id")["price"].sum().rename("total_price")
            df = df.merge(total_price, left_on="order_id", right_index=True, how="left")
            df["total_price"] = df["total_price"].fillna(0)

        # 按价格分箱: Low (0-50), Medium (50-150), High (150+)
        df["order_value_category"] = pd.cut(
            df["total_price"],
            bins=[0, 50, 150, float("inf")],
            labels=["Low", "Medium", "High"],
            include_lowest=True,
        )

        return df

    def add_all_features(self, datasets: dict) -> dict:
        """为所有数据集添加衍生特征

        Args:
            datasets: 包含清洗后DataFrame的字典

        Returns:
            添加特征后的DataFrame字典
        """
        print("[FEATURE] 开始特征工程...")
        result = dict(datasets)

        # 订单特征
        if "orders" in result:
            result["orders"] = self._add_order_features(result["orders"])

        # 订单明细特征
        if "order_items" in result:
            result["order_items"] = self._add_order_item_features(result["order_items"])

        # 订单价值分类 (依赖 orders 和 order_items)
        if "orders" in result and "order_items" in result:
            result["orders"] = self._add_order_value_category(
                result["orders"], result["order_items"]
            )

        print("[OK] 特征工程完成！")
        return result
