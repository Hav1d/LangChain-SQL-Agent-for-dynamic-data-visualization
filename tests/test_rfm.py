"""RFM分析模块测试"""
import os
import sys
import sqlite3

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import pandas as pd

from etl.pipeline import ETLPipeline
from analysis.rfm_engine import RFMEngine
from analysis.clustering import RFMClustering
from analysis.report_generator import ReportGenerator


@pytest.fixture
def populated_db(tmp_path):
    """创建并填充测试数据库"""
    db_path = str(tmp_path / "test.db")
    pipeline = ETLPipeline(db_path=db_path)
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
