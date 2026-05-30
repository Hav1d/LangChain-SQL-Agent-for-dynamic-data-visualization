"""RFM分析模块测试"""
import os
import sys
import sqlite3

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import pandas as pd
import numpy as np

from etl.pipeline import ETLPipeline
from analysis.rfm_engine import RFMEngine
from analysis.clustering import RFMClustering
from analysis.report_generator import ReportGenerator


@pytest.fixture
def populated_db(tmp_path):
    """创建并填充测试数据库（使用模拟数据）"""
    db_path = str(tmp_path / "test.db")
    pipeline = ETLPipeline(db_path=db_path, use_csv=False)
    pipeline.run(n_customers=100, n_orders=300, n_products=50, n_sellers=20)
    return db_path


class TestRFMEngine:
    """测试RFM分析引擎"""

    def test_calculate_rfm(self, populated_db):
        engine = RFMEngine(db_path=populated_db)
        rfm = engine.calculate_rfm()

        assert len(rfm) > 0
        assert "customer_id" in rfm.columns
        assert "recency" in rfm.columns
        assert "frequency" in rfm.columns
        assert "monetary" in rfm.columns

        # Recency应为正数
        assert (rfm["recency"] >= 0).all()
        # Frequency应为正数
        assert (rfm["frequency"] >= 1).all()
        # Monetary应为正数
        assert (rfm["monetary"] > 0).all()

    def test_dynamic_reference_date(self, populated_db):
        """测试动态参考日期: max(date) + 1天"""
        engine = RFMEngine(db_path=populated_db)
        rfm = engine.calculate_rfm()

        # 加载原始数据验证
        conn = sqlite3.connect(populated_db)
        max_date = pd.read_sql_query(
            "SELECT MAX(order_purchase_timestamp) as max_date FROM orders WHERE order_status='delivered'",
            conn
        )["max_date"].iloc[0]
        conn.close()

        max_date = pd.to_datetime(max_date)
        expected_ref = max_date + pd.Timedelta(days=1)

        # 最小recency应为0（参考日期 - 最大购买日期 = 1天）
        assert rfm["recency"].min() >= 0
        assert rfm["recency"].min() <= 1  # 允许1天误差

    def test_iqr_outlier_removal(self, populated_db):
        """测试IQR去噪移除极端值"""
        engine = RFMEngine(db_path=populated_db)
        rfm = engine.calculate_rfm()

        # IQR去噪后，monetary应在一个合理范围内
        Q1 = rfm["monetary"].quantile(0.25)
        Q3 = rfm["monetary"].quantile(0.75)
        IQR = Q3 - Q1

        # 所有值应在 [Q1 - 1.5*IQR, Q3 + 1.5*IQR] 范围内
        assert (rfm["monetary"] >= Q1 - 1.5 * IQR).all()
        assert (rfm["monetary"] <= Q3 + 1.5 * IQR).all()

    def test_score_rfm(self, populated_db):
        engine = RFMEngine(db_path=populated_db)
        rfm = engine.calculate_rfm()
        scored = engine.score_rfm(rfm)

        assert "r_score" in scored.columns
        assert "f_score" in scored.columns
        assert "m_score" in scored.columns
        assert "rfm_score" in scored.columns
        assert "segment" in scored.columns

        # 评分范围1-5
        assert scored["r_score"].between(1, 5).all()
        assert scored["f_score"].between(1, 5).all()
        assert scored["m_score"].between(1, 5).all()

    def test_dual_scoring(self, populated_db):
        """测试双评分系统: 分位数 + 数值总和"""
        engine = RFMEngine(db_path=populated_db)
        rfm = engine.calculate_rfm()
        scored = engine.score_rfm(rfm)

        assert "rfm_score_numeric" in scored.columns
        # 数值总和 = r_score + f_score + m_score
        expected = scored["r_score"] + scored["f_score"] + scored["m_score"]
        assert (scored["rfm_score_numeric"] == expected).all()
        # 范围应在 3-15 之间
        assert scored["rfm_score_numeric"].between(3, 15).all()

    def test_10_segment_classification(self, populated_db):
        """测试10段细分分类"""
        engine = RFMEngine(db_path=populated_db)
        rfm = engine.calculate_rfm()
        scored = engine.score_rfm(rfm)

        # 应有segment和segment_label列
        assert "segment" in scored.columns
        assert "segment_label" in scored.columns

        # 所有segment应属于10个预定义类别
        valid_segments = set(RFMEngine.SEGMENT_LABELS.keys())
        actual_segments = set(scored["segment"].unique())
        assert actual_segments.issubset(valid_segments), \
            f"未知分段: {actual_segments - valid_segments}"

        # 应有中文标签
        assert scored["segment_label"].notna().all()
        # 中文标签不应包含英文原名
        assert not scored["segment_label"].str.contains("_").any()

    def test_log1p_transform(self, populated_db):
        """测试Log1p变换列"""
        engine = RFMEngine(db_path=populated_db)
        rfm = engine.calculate_rfm()
        scored = engine.score_rfm(rfm)

        assert "recency_log" in scored.columns
        assert "frequency_log" in scored.columns
        assert "monetary_log" in scored.columns

        # 验证 log1p 变换正确性
        np.testing.assert_allclose(
            scored["recency_log"], np.log1p(scored["recency"]), rtol=1e-10
        )
        np.testing.assert_allclose(
            scored["frequency_log"], np.log1p(scored["frequency"]), rtol=1e-10
        )
        np.testing.assert_allclose(
            scored["monetary_log"], np.log1p(scored["monetary"]), rtol=1e-10
        )

    def test_rank_based_scoring(self, populated_db):
        """测试rank(method='first')解决并列问题"""
        engine = RFMEngine(db_path=populated_db)
        rfm = engine.calculate_rfm()
        scored = engine.score_rfm(rfm)

        # 每个评分维度应有5个分值
        assert scored["r_score"].nunique() <= 5
        assert scored["f_score"].nunique() <= 5
        assert scored["m_score"].nunique() <= 5

        # 每个分值应有数据
        for score_col in ["r_score", "f_score", "m_score"]:
            assert scored[score_col].between(1, 5).all()

    def test_save_rfm_results(self, populated_db):
        engine = RFMEngine(db_path=populated_db)
        rfm = engine.calculate_rfm()
        scored = engine.score_rfm(rfm)
        engine.save_rfm_results(scored)

        # 验证数据库中有数据
        conn = sqlite3.connect(populated_db)
        count = pd.read_sql_query("SELECT COUNT(*) as cnt FROM rfm_results", conn)["cnt"].iloc[0]
        conn.close()
        assert count > 0

    def test_full_rfm_pipeline(self, populated_db):
        engine = RFMEngine(db_path=populated_db)
        results = engine.run()

        assert len(results) > 0
        assert "segment" in results.columns
        assert "rfm_score_numeric" in results.columns
        assert "segment_label" in results.columns

        # 验证有多个分群
        segments = results["segment"].nunique()
        assert segments >= 2


class TestRFMClustering:
    """测试KMeans聚类"""

    def test_cluster(self, populated_db):
        # 先运行RFM分析
        engine = RFMEngine(db_path=populated_db)
        engine.run()

        # 运行聚类
        clustering = RFMClustering(db_path=populated_db)
        results = clustering.cluster()

        assert "cluster_label" in results.columns
        assert results["cluster_label"].nunique() >= 2

    def test_cluster_centers(self, populated_db):
        engine = RFMEngine(db_path=populated_db)
        engine.run()

        clustering = RFMClustering(db_path=populated_db)
        clustering.cluster()
        centers = clustering.get_cluster_centers()

        assert len(centers) > 0
        assert "recency" in centers.columns
        assert "frequency" in centers.columns
        assert "monetary" in centers.columns

        # 聚类中心应为正值（经过expm1逆变换）
        assert (centers["recency"] >= 0).all()
        assert (centers["frequency"] >= 0).all()
        assert (centers["monetary"] >= 0).all()

    def test_silhouette_scores(self, populated_db):
        """测试轮廓系数计算"""
        engine = RFMEngine(db_path=populated_db)
        engine.run()

        clustering = RFMClustering(db_path=populated_db)
        clustering.cluster()

        metrics = clustering.get_selection_metrics()
        assert "k_range" in metrics
        assert "inertias" in metrics
        assert "silhouettes" in metrics
        assert len(metrics["inertias"]) == len(metrics["silhouettes"])
        assert len(metrics["inertias"]) > 0

        # 轮廓系数应在 -1 到 1 之间
        for s in metrics["silhouettes"]:
            assert -1 <= s <= 1

    def test_log1p_transform_in_clustering(self, populated_db):
        """测试聚类使用log1p变换"""
        engine = RFMEngine(db_path=populated_db)
        engine.run()

        clustering = RFMClustering(db_path=populated_db)
        results = clustering.cluster()

        # 聚类应该能正常执行，不会因为log1p变换而出错
        assert results["cluster_label"].nunique() >= 2
        assert (results["cluster_label"] >= 0).all()


class TestReportGenerator:
    """测试报告生成器"""

    def test_generate_rfm_report(self, populated_db):
        engine = RFMEngine(db_path=populated_db)
        engine.run()

        generator = ReportGenerator(db_path=populated_db)
        report = generator.generate_rfm_report()

        assert len(report) > 100
        assert "RFM" in report
        assert "客户" in report

    def test_generate_sales_report(self, populated_db):
        generator = ReportGenerator(db_path=populated_db)
        report = generator.generate_sales_report()

        assert len(report) > 100
        assert "销售" in report

    def test_save_report(self, populated_db, tmp_path):
        generator = ReportGenerator(db_path=populated_db)
        report = generator.generate_rfm_report()
        path = generator.save_report(report, "test", "测试报告")

        assert os.path.exists(path)

        # 验证数据库中有记录
        conn = sqlite3.connect(populated_db)
        count = pd.read_sql_query(
            "SELECT COUNT(*) as cnt FROM analysis_reports", conn
        )["cnt"].iloc[0]
        conn.close()
        assert count > 0
