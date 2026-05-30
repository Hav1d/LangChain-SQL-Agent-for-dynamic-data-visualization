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


class OlistDataCleaner(DataCleaner):
    """针对真实Olist CSV数据的增强清洗器

    继承DataCleaner，覆盖orders/products/reviews方法以处理真实数据中的
    缺失值、时间戳顺序、拼写错误列名等问题，并新增geolocation清洗。
    """

    def clean_orders(self, df: pd.DataFrame) -> pd.DataFrame:
        """清洗订单数据（增强版）

        - 所有日期列转pd.to_datetime(errors='coerce')
        - 已完成(delivered)订单缺失三个关键日期字段之一则丢弃
        - 强制时间戳顺序: purchase <= approved <= carrier_date <= customer_date
        """
        df = df.copy()

        # 转换时间列
        time_cols = [
            "order_purchase_timestamp", "order_approved_at",
            "order_delivered_carrier_date", "order_delivered_customer_date",
            "order_estimated_delivery_date",
        ]
        for col in time_cols:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce")

        # 去除无效订单（无购买时间）
        df = df.dropna(subset=["order_purchase_timestamp"])

        # 过滤异常日期范围
        df = df[df["order_purchase_timestamp"] >= "2016-01-01"]
        df = df[df["order_purchase_timestamp"] <= "2018-12-31"]

        # 已完成订单必须有三个关键日期
        required_date_cols = [
            "order_approved_at",
            "order_delivered_carrier_date",
            "order_delivered_customer_date",
        ]
        for col in required_date_cols:
            if col in df.columns:
                delivered_missing = (df["order_status"] == "delivered") & df[col].isna()
                df = df[~delivered_missing]

        # 强制时间戳顺序: purchase <= approved <= carrier <= customer
        order_pairs = [
            ("order_purchase_timestamp", "order_approved_at"),
            ("order_approved_at", "order_delivered_carrier_date"),
            ("order_delivered_carrier_date", "order_delivered_customer_date"),
        ]
        for early_col, late_col in order_pairs:
            if early_col in df.columns and late_col in df.columns:
                # 只在两列都有值时比较
                both_present = df[early_col].notna() & df[late_col].notna()
                violation = both_present & (df[early_col] > df[late_col])
                df = df[~violation]

        return df

    def clean_products(self, df: pd.DataFrame) -> pd.DataFrame:
        """清洗商品数据（增强版）

        - 保留product_name_lenght拼写（DB schema使用此拼写）
        - 数值列用中位数填充: product_name_lenght, product_description_lenght,
          product_photos_qty, product_weight_g, product_length_cm,
          product_height_cm, product_width_cm
        - product_category_name用众数填充
        """
        df = df.copy()

        # 数值列：转numeric后用中位数填充
        median_fill_cols = [
            "product_name_lenght",
            "product_description_lenght",
            "product_photos_qty",
            "product_weight_g",
            "product_length_cm",
            "product_height_cm",
            "product_width_cm",
        ]
        for col in median_fill_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
                median_val = df[col].median()
                df[col] = df[col].fillna(median_val)

        # 分类列：用众数填充
        if "product_category_name" in df.columns:
            mode_val = df["product_category_name"].mode()
            if len(mode_val) > 0:
                df["product_category_name"] = df["product_category_name"].fillna(mode_val.iloc[0])

        # 重量/尺寸不能为负（保留DataCleaner的逻辑）
        for col in ["product_weight_g", "product_length_cm", "product_height_cm", "product_width_cm"]:
            if col in df.columns:
                df[col] = df[col].clip(lower=0)

        return df

    def clean_reviews(self, df: pd.DataFrame) -> pd.DataFrame:
        """清洗评价数据（增强版）

        - review_comment_title和review_comment_message的NaN填充为"No comment"
        - review_score裁剪到1-5
        - 按review_id去重（保留第一条）
        """
        df = df.copy()

        # 按review_id去重（Olist真实数据有重复review_id）
        if "review_id" in df.columns:
            df = df.drop_duplicates(subset=["review_id"], keep="first")

        # 填充评论缺失值
        for col in ["review_comment_title", "review_comment_message"]:
            if col in df.columns:
                df[col] = df[col].fillna("No comment")

        # 评分范围1-5
        if "review_score" in df.columns:
            df["review_score"] = pd.to_numeric(df["review_score"], errors="coerce")
            df["review_score"] = df["review_score"].clip(lower=1, upper=5)

        # 转换时间
        time_cols = ["review_creation_date", "review_answer_timestamp"]
        for col in time_cols:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce")

        return df

    def clean_geolocation(self, df: pd.DataFrame) -> pd.DataFrame:
        """清洗地理定位数据（新增）

        - 按geolocation_zip_code_prefix去重
        - 分组后对lat/lng取均值，city/state取第一个值
        - 将约100万行缩减为约2万行（每个邮编一行）
        """
        df = df.copy()

        zip_col = "geolocation_zip_code_prefix"
        if zip_col not in df.columns:
            return df

        # 数值列转numeric
        for col in ["geolocation_lat", "geolocation_lng"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        # 标准化城市名
        if "geolocation_city" in df.columns:
            df["geolocation_city"] = df["geolocation_city"].str.strip().str.lower()

        # 按邮编分组：lat/lng取均值，city/state取第一个
        agg_dict = {}
        if "geolocation_lat" in df.columns:
            agg_dict["geolocation_lat"] = "mean"
        if "geolocation_lng" in df.columns:
            agg_dict["geolocation_lng"] = "mean"
        if "geolocation_city" in df.columns:
            agg_dict["geolocation_city"] = "first"
        if "geolocation_state" in df.columns:
            agg_dict["geolocation_state"] = "first"

        if agg_dict:
            df = df.groupby(zip_col, as_index=False).agg(agg_dict)

        return df

    def clean_all(self, datasets: dict) -> dict:
        """清洗所有数据集（增强版，包含geolocation）"""
        print("[CLEAN] 开始数据清洗（OlistDataCleaner增强模式）...")
        cleaned = {}

        cleaners = {
            "customers": self.clean_customers,
            "orders": self.clean_orders,
            "order_items": self.clean_order_items,
            "order_payments": self.clean_payments,
            "order_reviews": self.clean_reviews,
            "products": self.clean_products,
            "geolocation": self.clean_geolocation,
        }

        for name, df in datasets.items():
            original_count = len(df)
            if name in cleaners:
                cleaned[name] = cleaners[name](df)
                new_count = len(cleaned[name])
                diff = original_count - new_count
                if diff > 0:
                    print(f"  {name}: 清洗掉 {diff} 条异常数据 ({original_count} -> {new_count})")
                else:
                    print(f"  {name}: {new_count} 条 (无异常)")
            else:
                cleaned[name] = df
                print(f"  {name}: {len(df)} 条 (无需清洗)")

        print("[OK] 数据清洗完成！")
        return cleaned
