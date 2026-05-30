"""Agent工具模块测试"""
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import pandas as pd
import numpy as np

from etl.pipeline import ETLPipeline
from analysis.rfm_engine import RFMEngine


@pytest.fixture
def populated_db(tmp_path):
    """创建并填充测试数据库"""
    db_path = str(tmp_path / "test.db")
    pipeline = ETLPipeline(db_path=db_path, use_csv=False)
    pipeline.run(n_customers=100, n_orders=300, n_products=50, n_sellers=20)
    # 运行RFM生成rfm_results表
    engine = RFMEngine(db_path=db_path)
    engine.run()
    return db_path


class TestPresetQueries:
    """测试预置查询模板"""

    def test_all_preset_queries_execute(self, populated_db):
        """所有预置查询都能成功执行"""
        import agent_tools
        from config import DB_PATH

        # 临时替换DB_PATH
        original = agent_tools.DB_PATH
        agent_tools.DB_PATH = populated_db

        try:
            for name in agent_tools.PRESET_QUERIES:
                result = agent_tools.preset_query.invoke(name)
                parsed = json.loads(result)
                assert "error" not in parsed, f"查询 '{name}' 出错: {parsed.get('error')}"
                assert "data" in parsed, f"查询 '{name}' 缺少data字段"
        finally:
            agent_tools.DB_PATH = original

    def test_preset_query_invalid_name(self, populated_db):
        """无效查询名返回错误"""
        import agent_tools
        original = agent_tools.DB_PATH
        agent_tools.DB_PATH = populated_db

        try:
            result = agent_tools.preset_query.invoke("nonexistent_query")
            parsed = json.loads(result)
            assert "error" in parsed
            assert "可用" in parsed["error"]
        finally:
            agent_tools.DB_PATH = original

    def test_preset_query_monthly_revenue_schema(self, populated_db):
        """monthly_revenue 返回正确列"""
        import agent_tools
        original = agent_tools.DB_PATH
        agent_tools.DB_PATH = populated_db

        try:
            result = agent_tools.preset_query.invoke("monthly_revenue")
            parsed = json.loads(result)
            data = parsed["data"]
            assert "month" in data
            assert "orders" in data
            assert "revenue" in data
            assert len(data["month"]) > 0
        finally:
            agent_tools.DB_PATH = original

    def test_preset_query_rfm_summary_schema(self, populated_db):
        """rfm_summary 返回正确列"""
        import agent_tools
        original = agent_tools.DB_PATH
        agent_tools.DB_PATH = populated_db

        try:
            result = agent_tools.preset_query.invoke("rfm_summary")
            parsed = json.loads(result)
            data = parsed["data"]
            assert "segment" in data
            assert "customers" in data
            assert "avg_recency" in data
            assert "avg_frequency" in data
            assert "avg_monetary" in data
        finally:
            agent_tools.DB_PATH = original

    def test_preset_query_descriptions(self):
        """所有预置查询都有描述和图表类型"""
        import agent_tools
        for name, preset in agent_tools.PRESET_QUERIES.items():
            assert "description" in preset, f"'{name}' 缺少description"
            assert "chart" in preset, f"'{name}' 缺少chart"
            assert preset["chart"] in ("time_series", "bar", "pie", "table"), \
                f"'{name}' 无效chart类型: {preset['chart']}"


class TestQueryAndVisualize:
    """测试查询并可视化一步完成工具"""

    def test_query_and_visualize_time_series(self, populated_db):
        """monthly_revenue应生成折线图"""
        import agent_tools
        original = agent_tools.DB_PATH
        agent_tools.DB_PATH = populated_db
        try:
            result = agent_tools.query_and_visualize.invoke({"query_name": "monthly_revenue"})
            fig_dict = json.loads(result)
            assert "data" in fig_dict
            assert fig_dict["data"][0]["type"] == "scatter"
        finally:
            agent_tools.DB_PATH = original

    def test_query_and_visualize_pie(self, populated_db):
        """payment_analysis应生成饼图"""
        import agent_tools
        original = agent_tools.DB_PATH
        agent_tools.DB_PATH = populated_db
        try:
            result = agent_tools.query_and_visualize.invoke({"query_name": "payment_analysis"})
            fig_dict = json.loads(result)
            assert "data" in fig_dict
            assert fig_dict["data"][0]["type"] == "pie"
        finally:
            agent_tools.DB_PATH = original

    def test_query_and_visualize_bar(self, populated_db):
        """category_top10应生成柱状图"""
        import agent_tools
        original = agent_tools.DB_PATH
        agent_tools.DB_PATH = populated_db
        try:
            result = agent_tools.query_and_visualize.invoke({"query_name": "category_top10"})
            fig_dict = json.loads(result)
            assert "data" in fig_dict
            assert fig_dict["data"][0]["type"] == "bar"
        finally:
            agent_tools.DB_PATH = original

    def test_query_and_visualize_table(self, populated_db):
        """delivery_performance应生成表格"""
        import agent_tools
        original = agent_tools.DB_PATH
        agent_tools.DB_PATH = populated_db
        try:
            result = agent_tools.query_and_visualize.invoke({"query_name": "delivery_performance"})
            fig_dict = json.loads(result)
            assert "data" in fig_dict
            assert fig_dict["data"][0]["type"] == "table"
        finally:
            agent_tools.DB_PATH = original

    def test_query_and_visualize_invalid(self, populated_db):
        """无效查询名返回错误"""
        import agent_tools
        original = agent_tools.DB_PATH
        agent_tools.DB_PATH = populated_db
        try:
            result = agent_tools.query_and_visualize.invoke({"query_name": "nonexistent"})
            parsed = json.loads(result)
            assert "error" in parsed
        finally:
            agent_tools.DB_PATH = original

    def test_query_and_visualize_custom_title(self, populated_db):
        """自定义标题应生效"""
        import agent_tools
        original = agent_tools.DB_PATH
        agent_tools.DB_PATH = populated_db
        try:
            result = agent_tools.query_and_visualize.invoke({"query_name": "monthly_revenue", "title": "自定义标题"})
            fig_dict = json.loads(result)
            assert fig_dict.get("layout", {}).get("title", {}).get("text") == "自定义标题"
        finally:
            agent_tools.DB_PATH = original


class TestAutoVisualize:
    """测试自动可视化"""

    def test_time_series_detection(self):
        """时间序列数据应生成折线图"""
        import agent_tools
        data = json.dumps({
            "month": ["2018-01", "2018-02", "2018-03"],
            "revenue": [1000, 1500, 2000],
        })
        result = agent_tools.auto_visualize.invoke(data)
        fig_dict = json.loads(result)
        assert "data" in fig_dict
        # 时间序列应该用Scatter (折线)
        assert fig_dict["data"][0]["type"] == "scatter"

    def test_categorical_pie_detection(self):
        """少量类别数据应生成饼图"""
        import agent_tools
        data = json.dumps({
            "payment_type": ["credit_card", "boleto", "voucher"],
            "count": [500, 300, 100],
        })
        result = agent_tools.auto_visualize.invoke(data)
        fig_dict = json.loads(result)
        assert "data" in fig_dict
        assert fig_dict["data"][0]["type"] == "pie"

    def test_categorical_bar_detection(self):
        """多类别数据应生成柱状图"""
        import agent_tools
        data = json.dumps({
            "city": [f"city_{i}" for i in range(15)],
            "count": [100 - i for i in range(15)],
        })
        result = agent_tools.auto_visualize.invoke(data)
        fig_dict = json.loads(result)
        assert "data" in fig_dict
        assert fig_dict["data"][0]["type"] == "bar"

    def test_tuple_input_format(self):
        """接受SQL查询结果的tuple格式"""
        import agent_tools
        data = [
            ("2018-01", 1000),
            ("2018-02", 1500),
            ("2018-03", 2000),
        ]
        result = agent_tools.auto_visualize.invoke({"data": data})
        fig_dict = json.loads(result)
        assert "data" in fig_dict

    def test_invalid_data(self):
        """无效数据应返回错误"""
        import agent_tools
        result = agent_tools.auto_visualize.invoke("{}")
        parsed = json.loads(result)
        assert "error" in parsed

    def test_single_column_error(self):
        """单列数据应返回错误"""
        import agent_tools
        data = json.dumps({"col1": [1, 2, 3]})
        result = agent_tools.auto_visualize.invoke(data)
        parsed = json.loads(result)
        assert "error" in parsed

    def test_title_applied(self):
        """标题应正确应用到图表"""
        import agent_tools
        data = json.dumps({
            "category": ["A", "B", "C"],
            "value": [10, 20, 30],
        })
        result = agent_tools.auto_visualize.invoke({"data": data, "title": "测试标题"})
        fig_dict = json.loads(result)
        assert fig_dict.get("layout", {}).get("title", {}).get("text") == "测试标题"
