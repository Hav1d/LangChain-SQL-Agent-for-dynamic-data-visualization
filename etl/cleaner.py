"""
数据清洗模块 - 清洗和标准化Olist数据
"""
import pandas as pd
import numpy as np


class DataCleaner:
    """Olist数据清洗器"""

    def clean_customers(self, df: pd.DataFrame) -> pd.DataFrame:
        """清洗客户数据"""
        df = df.copy()
        # 去重
        df = df.drop_duplicates(subset=["customer_id"])
        # 标准化城市名
        df["customer_city"] = df["customer_city"].str.strip().str.lower()
        # 验证州代码
        valid_states = ["AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO",
                        "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI",
                        "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO"]
        df["customer_state"] = df["customer_state"].str.upper()
        df = df[df["customer_state"].isin(valid_states)]
        # 验证邮编
        df["customer_zip_code_prefix"] = pd.to_numeric(
            df["customer_zip_code_prefix"], errors="coerce"
        ).fillna(0).astype(int)
        return df

    def clean_orders(self, df: pd.DataFrame) -> pd.DataFrame:
        """清洗订单数据"""
        df = df.copy()
        # 转换时间列
        time_cols = [
            "order_purchase_timestamp", "order_approved_at",
            "order_delivered_carrier_date", "order_delivered_customer_date",
            "order_estimated_delivery_date"
        ]
        for col in time_cols:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce")

        # 去除无效订单（无购买时间）
        df = df.dropna(subset=["order_purchase_timestamp"])

        # 过滤异常日期
        df = df[df["order_purchase_timestamp"] >= "2016-01-01"]
        df = df[df["order_purchase_timestamp"] <= "2018-12-31"]

        return df

    def clean_order_items(self, df: pd.DataFrame) -> pd.DataFrame:
        """清洗订单明细"""
        df = df.copy()
        # 价格和运费不能为负
        df["price"] = df["price"].clip(lower=0.01)
        df["freight_value"] = df["freight_value"].clip(lower=0)
        # 数量至少为1
        if "order_item_id" in df.columns:
            df["order_item_id"] = df["order_item_id"].clip(lower=1)
        return df

    def clean_payments(self, df: pd.DataFrame) -> pd.DataFrame:
        """清洗支付数据"""
        df = df.copy()
        # 金额不能为负
        df["payment_value"] = df["payment_value"].clip(lower=0.01)
        # 分期数至少为1
        df["payment_installments"] = df["payment_installments"].clip(lower=1)
        # 标准化支付方式
        valid_methods = ["credit_card", "boleto", "voucher", "debit_card"]
        df.loc[~df["payment_type"].isin(valid_methods), "payment_type"] = "other"
        return df

    def clean_reviews(self, df: pd.DataFrame) -> pd.DataFrame:
        """清洗评价数据"""
        df = df.copy()
        # 评分范围1-5
        df["review_score"] = df["review_score"].clip(lower=1, upper=5)
        # 转换时间
        time_cols = ["review_creation_date", "review_answer_timestamp"]
        for col in time_cols:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce")
        return df

    def clean_products(self, df: pd.DataFrame) -> pd.DataFrame:
        """清洗商品数据"""
        df = df.copy()
        # 重量不能为负
        for col in ["product_weight_g", "product_length_cm", "product_height_cm", "product_width_cm"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).clip(lower=0)
        return df

    def clean_all(self, datasets: dict) -> dict:
        """清洗所有数据集"""
        print("[CLEAN] 开始数据清洗...")
        cleaned = {}

        cleaners = {
            "customers": self.clean_customers,
            "orders": self.clean_orders,
            "order_items": self.clean_order_items,
            "order_payments": self.clean_payments,
            "order_reviews": self.clean_reviews,
            "products": self.clean_products,
        }

        for name, df in datasets.items():
            original_count = len(df)
            if name in cleaners:
                cleaned[name] = cleaners[name](df)
                new_count = len(cleaned[name])
                diff = original_count - new_count
                if diff > 0:
                    print(f"  {name}: 清洗掉 {diff} 条异常数据 ({original_count} → {new_count})")
                else:
                    print(f"  {name}: {new_count} 条 (无异常)")
            else:
                cleaned[name] = df
                print(f"  {name}: {len(df)} 条 (无需清洗)")

        print("[OK] 数据清洗完成！")
        return cleaned
