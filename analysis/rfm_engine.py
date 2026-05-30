"""
RFM分析引擎 - 计算Recency、Frequency、Monetary指标并评分

增强版:
- 10段细分 (regex分类替代8分类)
- rank(method='first') 解决频率并列问题
- IQR 去除极端值
- Log1p 变换用于聚类
- 双评分系统: 分位数(1-5) + 数值总和
"""
import sqlite3
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from config import DB_PATH, RFM_QUANTILES
from utils.timing import get_perf_logger, TimerContext


class RFMEngine:
    """RFM客户价值分析引擎（增强版）"""

    # 10段细分定义: 基于 R+F 两位数的 regex 映射（锚定全匹配）
    SEGMENT_MAP = {
        r"^[1-2][1-2]$": "hibernating",        # 休眠
        r"^[1-2][3-4]$": "at_risk",            # 风险
        r"^[1-2]5$":     "cant_loose",         # 不能流失
        r"^3[1-2]$":     "about_to_sleep",     # 即将休眠
        r"^33$":         "need_attention",      # 需关注
        r"^[3-4][4-5]$": "loyal_customers",     # 忠诚
        r"^41$":         "promising",          # 有希望
        r"^51$":         "new_customers",      # 新客户
        r"^[4-5][2-3]$": "potential_loyalists", # 潜力忠诚
        r"^5[4-5]$":     "champions",          # 冠军
    }

    # 中文标签映射
    SEGMENT_LABELS = {
        "hibernating": "休眠客户",
        "at_risk": "风险客户",
        "cant_loose": "不能流失",
        "about_to_sleep": "即将休眠",
        "need_attention": "需关注",
        "loyal_customers": "忠诚客户",
        "promising": "有希望客户",
        "new_customers": "新客户",
        "potential_loyalists": "潜力忠诚",
        "champions": "冠军客户",
    }

    # 营销策略建议
    STRATEGY_MAP = {
        "champions": "VIP维护，专属优惠，优先客服，增加忠诚度",
        "loyal_customers": "会员升级，专属活动，交叉销售",
        "potential_loyalists": "提升复购频率，个性化推荐，会员体系引导",
        "new_customers": "新客礼包，首购体验优化，积分激励",
        "promising": "培养消费习惯，限时优惠，品类推荐",
        "need_attention": "唤醒召回，限时优惠券，新品推送",
        "about_to_sleep": "定期触达，节日关怀，低频提醒",
        "at_risk": "重点挽留，大额优惠券，电话回访",
        "cant_loose": "紧急挽留，专属客服，大额回馈",
        "hibernating": "低成本维护，自动化邮件，最后尝试唤醒",
    }

    def __init__(self, db_path: str = None, reference_date: str = None):
        self.db_path = db_path or str(DB_PATH)
        self.reference_date = reference_date  # None = 动态计算
        self.perf = get_perf_logger()

    def _load_order_data(self) -> pd.DataFrame:
        """从数据库加载订单数据（使用customer_unique_id聚合真实客户）"""
        conn = sqlite3.connect(self.db_path)
        try:
            query = """
                SELECT
                    c.customer_unique_id AS customer_id,
                    o.order_id,
                    o.order_purchase_timestamp,
                    op.payment_value
                FROM orders o
                JOIN order_payments op ON o.order_id = op.order_id
                JOIN customers c ON o.customer_id = c.customer_id
                WHERE o.order_status = 'delivered'
                  AND o.order_purchase_timestamp IS NOT NULL
            """
            df = pd.read_sql_query(query, conn)
        finally:
            conn.close()

        df["order_purchase_timestamp"] = pd.to_datetime(df["order_purchase_timestamp"])
        df["payment_value"] = pd.to_numeric(df["payment_value"], errors="coerce").fillna(0)

        return df

    def _compute_reference_date(self, df: pd.DataFrame) -> pd.Timestamp:
        """动态计算参考日期: max(purchase_date) + 1天"""
        if self.reference_date:
            return pd.to_datetime(self.reference_date)
        return df["order_purchase_timestamp"].max() + timedelta(days=1)

    def _remove_outliers_iqr(self, rfm: pd.DataFrame) -> pd.DataFrame:
        """使用IQR方法去除monetary极端值"""
        Q1 = rfm["monetary"].quantile(0.25)
        Q3 = rfm["monetary"].quantile(0.75)
        IQR = Q3 - Q1
        lower = Q1 - 1.5 * IQR
        upper = Q3 + 1.5 * IQR
        before = len(rfm)
        rfm = rfm[(rfm["monetary"] >= lower) & (rfm["monetary"] <= upper)]
        removed = before - len(rfm)
        if removed > 0:
            print(f"  [INFO] IQR去噪: 移除 {removed} 个monetary极端值 ({before} -> {len(rfm)})")
        return rfm

    def calculate_rfm(self) -> pd.DataFrame:
        """
        计算RFM指标

        Returns:
            DataFrame: customer_id, recency, frequency, monetary
        """
        with TimerContext("rfm_calculate", self.perf):
            return self._calculate_rfm_impl()

    def _calculate_rfm_impl(self) -> pd.DataFrame:
        print("[CALC] 开始计算RFM指标...")
        df = self._load_order_data()

        if df.empty:
            raise ValueError("没有可用于RFM分析的订单数据")

        # 动态参考日期
        ref_date = self._compute_reference_date(df)
        print(f"  [INFO] 参考日期: {ref_date.strftime('%Y-%m-%d')}")

        # 按客户聚合
        rfm = df.groupby("customer_id").agg(
            recency=("order_purchase_timestamp", "max"),
            frequency=("order_id", "nunique"),
            monetary=("payment_value", "sum"),
        ).reset_index()

        # 计算Recency（距参考日期的天数）
        rfm["recency"] = (ref_date - rfm["recency"]).dt.days

        # 金额保留2位小数
        rfm["monetary"] = rfm["monetary"].round(2)

        # IQR去噪
        rfm = self._remove_outliers_iqr(rfm)

        print(f"  [OK] 计算完成: {len(rfm):,} 位客户")
        print(f"    Recency范围: {rfm['recency'].min()} ~ {rfm['recency'].max()} 天")
        print(f"    Frequency范围: {rfm['frequency'].min()} ~ {rfm['frequency'].max()} 次")
        print(f"    Monetary范围: R${rfm['monetary'].min():.2f} ~ R${rfm['monetary'].max():.2f}")

        return rfm

    def score_rfm(self, rfm: pd.DataFrame) -> pd.DataFrame:
        """
        对RFM进行评分（双评分系统）

        - 分位数评分 (1-5): 用于分类
        - 数值总和 (r_score + f_score + m_score): 用于连续分析
        - Log1p变换列: 用于聚类预处理

        Args:
            rfm: RFM原始数据

        Returns:
            DataFrame: 添加了评分和分组的RFM数据
        """
        print("[SCORE] 开始RFM评分...")
        df = rfm.copy()

        # Recency: 越小越好（反向评分），使用rank(method='first')解决并列
        df["r_score"] = pd.qcut(
            df["recency"].rank(method="first"),
            q=RFM_QUANTILES, labels=[5, 4, 3, 2, 1],
        ).astype(int)

        # Frequency: 越大越好，使用rank(method='first')解决并列
        df["f_score"] = pd.qcut(
            df["frequency"].rank(method="first"),
            q=RFM_QUANTILES, labels=[1, 2, 3, 4, 5],
        ).astype(int)

        # Monetary: 越大越好，使用rank(method='first')解决并列
        df["m_score"] = pd.qcut(
            df["monetary"].rank(method="first"),
            q=RFM_QUANTILES, labels=[1, 2, 3, 4, 5],
        ).astype(int)

        # 综合评分字符串 (用于10段分类)
        df["rfm_score"] = df["r_score"].astype(str) + df["f_score"].astype(str) + df["m_score"].astype(str)

        # 双评分: 数值总和
        df["rfm_score_numeric"] = df["r_score"] + df["f_score"] + df["m_score"]

        # 10段细分: 基于 R+F 两位数 regex
        df["rf_score"] = df["r_score"].astype(str) + df["f_score"].astype(str)
        df["segment"] = df["rf_score"].replace(self.SEGMENT_MAP, regex=True)

        # 添加中文标签
        df["segment_label"] = df["segment"].map(self.SEGMENT_LABELS).fillna("未分类")

        # Log1p 变换 (用于聚类)
        df["recency_log"] = np.log1p(df["recency"])
        df["frequency_log"] = np.log1p(df["frequency"])
        df["monetary_log"] = np.log1p(df["monetary"])

        # 打印分组统计
        print(f"  [OK] 评分完成")
        segment_counts = df["segment_label"].value_counts()
        print(f"  分组分布:")
        for seg, count in segment_counts.items():
            print(f"    {seg}: {count} ({count/len(df)*100:.1f}%)")

        return df

    def save_rfm_results(self, rfm_scored: pd.DataFrame) -> None:
        """将RFM结果保存到数据库"""
        print("[SAVE] 保存RFM结果到数据库...")
        conn = sqlite3.connect(self.db_path)
        try:
            # 准备数据
            save_cols = [
                "customer_id", "recency", "frequency", "monetary",
                "r_score", "f_score", "m_score", "rfm_score", "segment",
            ]
            save_df = rfm_scored[save_cols].copy()
            save_df["analysis_date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            save_df["cluster_label"] = -1  # 待聚类分析填充

            # 原子事务: DELETE + INSERT 要么全成功，要么全回滚
            with conn:
                conn.execute("DELETE FROM rfm_results")
                save_df.to_sql("rfm_results", conn, if_exists="append", index=False)
            print(f"  [OK] 保存完成: {len(save_df):,} 条记录")
        finally:
            conn.close()

    def run(self) -> pd.DataFrame:
        """执行完整RFM分析流程"""
        with TimerContext("rfm_total", self.perf):
            print("=" * 60)
            print("[START] RFM 分析引擎启动（增强版）")
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
