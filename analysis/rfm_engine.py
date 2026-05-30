"""
RFM分析引擎 - 计算Recency、Frequency、Monetary指标并评分
"""
import sqlite3
from datetime import datetime

import numpy as np
import pandas as pd

from config import DB_PATH, RFM_REFERENCE_DATE, RFM_QUANTILES


class RFMEngine:
    """RFM客户价值分析引擎"""

    # 经典8分类定义
    SEGMENT_MAP = {
        (1, 1, 1): "重要保持客户",  # R低F高M高
        (1, 1, 0): "一般保持客户",  # R低F高M低
        (1, 0, 1): "重要挽留客户",  # R低F低M高
        (1, 0, 0): "一般挽留客户",  # R低F低M低
        (0, 1, 1): "重要价值客户",  # R高F高M高
        (0, 1, 0): "一般价值客户",  # R高F高M低
        (0, 0, 1): "重要发展客户",  # R高F低M高
        (0, 0, 0): "一般发展客户",  # R高F低M低
    }

    # 营销策略建议
    STRATEGY_MAP = {
        "重要价值客户": "VIP维护，专属优惠，优先客服，增加忠诚度",
        "重要发展客户": "提升复购频率，个性化推荐，会员体系引导",
        "重要保持客户": "唤醒召回，限时优惠券，新品推送",
        "重要挽留客户": "重点挽留，大额优惠券，电话回访",
        "一般价值客户": "提升客单价，交叉销售，满减活动",
        "一般发展客户": "培养消费习惯，新客礼包，积分激励",
        "一般保持客户": "定期触达，节日关怀，低频提醒",
        "一般挽留客户": "低成本维护，自动化邮件，最后尝试唤醒",
    }

    def __init__(self, db_path: str = None, reference_date: str = None):
        self.db_path = db_path or str(DB_PATH)
        self.reference_date = pd.to_datetime(reference_date or RFM_REFERENCE_DATE)

    def _load_order_data(self) -> pd.DataFrame:
        """从数据库加载订单数据"""
        conn = sqlite3.connect(self.db_path)

        query = """
            SELECT
                o.customer_id,
                o.order_id,
                o.order_purchase_timestamp,
                op.payment_value
            FROM orders o
            JOIN order_payments op ON o.order_id = op.order_id
            WHERE o.order_status = 'delivered'
              AND o.order_purchase_timestamp IS NOT NULL
        """
        df = pd.read_sql_query(query, conn)
        conn.close()

        df["order_purchase_timestamp"] = pd.to_datetime(df["order_purchase_timestamp"])
        df["payment_value"] = pd.to_numeric(df["payment_value"], errors="coerce").fillna(0)

        return df

    def calculate_rfm(self) -> pd.DataFrame:
        """
        计算RFM指标

        Returns:
            DataFrame: customer_id, recency, frequency, monetary
        """
        print("[CALC] 开始计算RFM指标...")
        df = self._load_order_data()

        if df.empty:
            raise ValueError("没有可用于RFM分析的订单数据")

        # 按客户聚合
        rfm = df.groupby("customer_id").agg(
            recency=("order_purchase_timestamp", "max"),
            frequency=("order_id", "nunique"),
            monetary=("payment_value", "sum"),
        ).reset_index()

        # 计算Recency（距参考日期的天数）
        rfm["recency"] = (self.reference_date - rfm["recency"]).dt.days

        # 金额保留2位小数
        rfm["monetary"] = rfm["monetary"].round(2)

        print(f"  [OK] 计算完成: {len(rfm):,} 位客户")
        print(f"    Recency范围: {rfm['recency'].min()} ~ {rfm['recency'].max()} 天")
        print(f"    Frequency范围: {rfm['frequency'].min()} ~ {rfm['frequency'].max()} 次")
        print(f"    Monetary范围: R${rfm['monetary'].min():.2f} ~ R${rfm['monetary'].max():.2f}")

        return rfm

    def score_rfm(self, rfm: pd.DataFrame) -> pd.DataFrame:
        """
        对RFM进行评分（1-5分，使用分位数法）

        Args:
            rfm: RFM原始数据

        Returns:
            DataFrame: 添加了评分和分组的RFM数据
        """
        print("🎯 开始RFM评分...")
        df = rfm.copy()

        # 使用分位数评分
        # Recency: 越小越好（反向评分）
        df["r_score"] = pd.qcut(
            df["recency"], q=RFM_QUANTILES, labels=[5, 4, 3, 2, 1],
            duplicates="drop"
        ).astype(int)

        # Frequency: 越大越好
        # 需要处理重复值
        try:
            df["f_score"] = pd.qcut(
                df["frequency"], q=RFM_QUANTILES, labels=[1, 2, 3, 4, 5],
                duplicates="drop"
            ).astype(int)
        except ValueError:
            # 如果分位数有重复值，使用rank方法
            df["f_score"] = pd.cut(
                df["frequency"].rank(method="first"),
                bins=RFM_QUANTILES, labels=[1, 2, 3, 4, 5]
            ).astype(int)

        # Monetary: 越大越好
        try:
            df["m_score"] = pd.qcut(
                df["monetary"], q=RFM_QUANTILES, labels=[1, 2, 3, 4, 5],
                duplicates="drop"
            ).astype(int)
        except ValueError:
            df["m_score"] = pd.cut(
                df["monetary"].rank(method="first"),
                bins=RFM_QUANTILES, labels=[1, 2, 3, 4, 5]
            ).astype(int)

        # 综合评分
        df["rfm_score"] = df["r_score"].astype(str) + df["f_score"].astype(str) + df["m_score"].astype(str)

        # 分组（使用中位数作为阈值）
        r_median = df["r_score"].median()
        f_median = df["f_score"].median()
        m_median = df["m_score"].median()

        def classify(row):
            r_high = 1 if row["r_score"] <= r_median else 0  # Recency低分=最近消费
            f_high = 1 if row["f_score"] >= f_median else 0
            m_high = 1 if row["m_score"] >= m_median else 0
            return self.SEGMENT_MAP.get((r_high, f_high, m_high), "未分类")

        df["segment"] = df.apply(classify, axis=1)

        # 打印分组统计
        print(f"  [OK] 评分完成")
        segment_counts = df["segment"].value_counts()
        print(f"  分组分布:")
        for seg, count in segment_counts.items():
            print(f"    {seg}: {count} ({count/len(df)*100:.1f}%)")

        return df

    def save_rfm_results(self, rfm_scored: pd.DataFrame) -> None:
        """将RFM结果保存到数据库"""
        print("[SAVE] 保存RFM结果到数据库...")
        conn = sqlite3.connect(self.db_path)

        # 清空旧数据
        conn.execute("DELETE FROM rfm_results")

        # 准备数据
        save_df = rfm_scored[[
            "customer_id", "recency", "frequency", "monetary",
            "r_score", "f_score", "m_score", "rfm_score", "segment"
        ]].copy()
        save_df["analysis_date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        save_df["cluster_label"] = -1  # 待聚类分析填充

        save_df.to_sql("rfm_results", conn, if_exists="append", index=False)
        conn.commit()
        conn.close()
        print(f"  [OK] 保存完成: {len(save_df):,} 条记录")

    def run(self) -> pd.DataFrame:
        """执行完整RFM分析流程"""
        print("=" * 60)
        print("[START] RFM 分析引擎启动")
        print("=" * 60)

        rfm = self.calculate_rfm()
        rfm_scored = self.score_rfm(rfm)
        self.save_rfm_results(rfm_scored)

        print(f"\n[OK] RFM分析完成！")
        return rfm_scored


if __name__ == "__main__":
    engine = RFMEngine()
    results = engine.run()
    print("\n前10条结果:")
    print(results.head(10).to_string())
