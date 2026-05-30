import json
import re
import sqlite3
from typing import Any, Optional

import pandas as pd
import plotly.graph_objects as go
from langchain.tools import tool

from config import DB_PATH
from utils.timing import get_perf_logger, TimerContext

_perf = get_perf_logger()


# ──────────────────────────────────────────────
# 预置业务查询模板
# ──────────────────────────────────────────────
PRESET_QUERIES = {
    "monthly_revenue": {
        "sql": """
            SELECT strftime('%Y-%m', order_purchase_timestamp) AS month,
                   COUNT(DISTINCT o.order_id) AS orders,
                   ROUND(SUM(op.payment_value), 2) AS revenue
            FROM orders o
            JOIN order_payments op ON o.order_id = op.order_id
            WHERE o.order_status = 'delivered'
            GROUP BY month ORDER BY month
        """,
        "description": "月度收入与订单趋势",
        "chart": "time_series",
    },
    "category_top10": {
        "sql": """
            SELECT COALESCE(ct.product_category_name_english, p.product_category_name) AS category,
                   ROUND(SUM(oi.price), 2) AS revenue,
                   COUNT(DISTINCT oi.order_id) AS orders
            FROM order_items oi
            JOIN products p ON oi.product_id = p.product_id
            JOIN orders o ON oi.order_id = o.order_id
            LEFT JOIN category_translation ct ON p.product_category_name = ct.product_category_name
            WHERE o.order_status = 'delivered'
            GROUP BY category
            ORDER BY revenue DESC LIMIT 10
        """,
        "description": "销售额TOP10商品类目",
        "chart": "bar",
    },
    "city_distribution": {
        "sql": """
            SELECT customer_city, COUNT(*) AS customer_count
            FROM customers
            GROUP BY customer_city
            ORDER BY customer_count DESC LIMIT 15
        """,
        "description": "客户城市分布TOP15",
        "chart": "bar",
    },
    "payment_analysis": {
        "sql": """
            SELECT payment_type,
                   COUNT(*) AS count,
                   ROUND(SUM(payment_value), 2) AS total_value,
                   ROUND(AVG(payment_value), 2) AS avg_value,
                   ROUND(AVG(payment_installments), 1) AS avg_installments
            FROM order_payments
            GROUP BY payment_type
            ORDER BY count DESC
        """,
        "description": "支付方式分布与统计",
        "chart": "pie",
    },
    "delivery_performance": {
        "sql": """
            SELECT
                ROUND(AVG(delivery_time_days), 1) AS avg_delivery_days,
                ROUND(AVG(delay_vs_estimate), 1) AS avg_delay_days,
                SUM(CASE WHEN delay_vs_estimate > 0 THEN 1 ELSE 0 END) AS late_orders,
                COUNT(*) AS total_orders,
                ROUND(100.0 * SUM(CASE WHEN delay_vs_estimate > 0 THEN 1 ELSE 0 END) / COUNT(*), 1) AS late_rate_pct
            FROM orders
            WHERE order_status = 'delivered'
              AND delivery_time_days IS NOT NULL
        """,
        "description": "配送绩效总览（平均天数、延迟率）",
        "chart": "table",
    },
    "review_correlation": {
        "sql": """
            SELECT r.review_score,
                   COUNT(*) AS count,
                   ROUND(AVG(o.delivery_time_days), 1) AS avg_delivery_days,
                   ROUND(AVG(o.delay_vs_estimate), 1) AS avg_delay
            FROM order_reviews r
            JOIN orders o ON r.order_id = o.order_id
            WHERE o.order_status = 'delivered'
              AND o.delivery_time_days IS NOT NULL
            GROUP BY r.review_score
            ORDER BY r.review_score
        """,
        "description": "评分与配送时间相关性",
        "chart": "bar",
    },
    "seller_top10": {
        "sql": """
            SELECT s.seller_id,
                   MIN(s.seller_city) AS seller_city,
                   MIN(s.seller_state) AS seller_state,
                   COUNT(DISTINCT oi.order_id) AS orders,
                   ROUND(SUM(oi.price), 2) AS revenue
            FROM order_items oi
            JOIN sellers s ON oi.seller_id = s.seller_id
            JOIN orders o ON oi.order_id = o.order_id
            WHERE o.order_status = 'delivered'
            GROUP BY s.seller_id
            ORDER BY revenue DESC LIMIT 10
        """,
        "description": "销售额TOP10卖家",
        "chart": "bar",
    },
    "repeat_purchase": {
        "sql": """
            SELECT purchase_count, COUNT(*) AS customer_count
            FROM (
                SELECT c.customer_unique_id, COUNT(*) AS purchase_count
                FROM orders o
                JOIN customers c ON o.customer_id = c.customer_id
                WHERE o.order_status = 'delivered'
                GROUP BY c.customer_unique_id
            ) AS purchase_stats
            GROUP BY purchase_count
            ORDER BY purchase_count
        """,
        "description": "复购次数分布",
        "chart": "bar",
    },
    "rfm_summary": {
        "sql": """
            SELECT segment,
                   COUNT(*) AS customers,
                   ROUND(AVG(recency), 0) AS avg_recency,
                   ROUND(AVG(frequency), 1) AS avg_frequency,
                   ROUND(AVG(monetary), 2) AS avg_monetary
            FROM rfm_results
            GROUP BY segment
            ORDER BY avg_monetary DESC
        """,
        "description": "RFM分群概览",
        "chart": "table",
    },
    "order_status": {
        "sql": """
            SELECT order_status, COUNT(*) AS count
            FROM orders
            GROUP BY order_status
            ORDER BY count DESC
        """,
        "description": "订单状态分布",
        "chart": "pie",
    },
    "freight_analysis": {
        "sql": """
            SELECT
                COALESCE(ct.product_category_name_english, p.product_category_name) AS category,
                ROUND(AVG(oi.freight_value), 2) AS avg_freight,
                ROUND(AVG(oi.freight_value) * 100.0 / AVG(oi.price), 1) AS freight_pct
            FROM order_items oi
            JOIN products p ON oi.product_id = p.product_id
            LEFT JOIN category_translation ct ON p.product_category_name = ct.product_category_name
            JOIN orders o ON oi.order_id = o.order_id
            WHERE o.order_status = 'delivered' AND oi.price > 0
            GROUP BY category
            ORDER BY avg_freight DESC LIMIT 10
        """,
        "description": "各类目运费占比TOP10",
        "chart": "bar",
    },
    "installment_analysis": {
        "sql": """
            SELECT payment_installments,
                   COUNT(*) AS count,
                   ROUND(AVG(payment_value), 2) AS avg_value,
                   ROUND(SUM(payment_value), 2) AS total_value
            FROM order_payments
            WHERE payment_type = 'credit_card'
            GROUP BY payment_installments
            ORDER BY payment_installments
        """,
        "description": "信用卡分期分析",
        "chart": "bar",
    },
    "weekday_orders": {
        "sql": """
            SELECT CASE CAST(strftime('%w', order_purchase_timestamp) AS INTEGER)
                       WHEN 0 THEN '周日' WHEN 1 THEN '周一' WHEN 2 THEN '周二'
                       WHEN 3 THEN '周三' WHEN 4 THEN '周四' WHEN 5 THEN '周五'
                       WHEN 6 THEN '周六' END AS weekday,
                   COUNT(*) AS orders,
                   ROUND(SUM(total_price), 2) AS revenue
            FROM orders
            WHERE order_status = 'delivered'
            GROUP BY weekday
            ORDER BY CAST(strftime('%w', order_purchase_timestamp) AS INTEGER)
        """,
        "description": "星期维度订单分布",
        "chart": "bar",
    },
    "state_revenue": {
        "sql": """
            SELECT c.customer_state,
                   COUNT(DISTINCT o.order_id) AS orders,
                   ROUND(SUM(op.payment_value), 2) AS revenue,
                   ROUND(AVG(op.payment_value), 2) AS avg_order_value
            FROM orders o
            JOIN customers c ON o.customer_id = c.customer_id
            JOIN order_payments op ON o.order_id = op.order_id
            WHERE o.order_status = 'delivered'
            GROUP BY c.customer_state
            ORDER BY revenue DESC LIMIT 10
        """,
        "description": "各州销售额TOP10",
        "chart": "bar",
    },
    "customer_lifetime": {
        "sql": """
            SELECT
                CASE
                    WHEN order_count = 1 THEN '单次购买'
                    WHEN order_count BETWEEN 2 AND 3 THEN '2-3次'
                    WHEN order_count BETWEEN 4 AND 6 THEN '4-6次'
                    ELSE '7次以上'
                END AS lifetime_group,
                COUNT(*) AS customers,
                ROUND(AVG(total_spent), 2) AS avg_spent
            FROM (
                SELECT c.customer_unique_id,
                       COUNT(*) AS order_count,
                       SUM(o.total_price) AS total_spent
                FROM orders o
                JOIN customers c ON o.customer_id = c.customer_id
                WHERE o.order_status = 'delivered'
                GROUP BY c.customer_unique_id
            ) AS lifetime_stats
            GROUP BY lifetime_group
            ORDER BY avg_spent DESC
        """,
        "description": "客户生命周期价值分组",
        "chart": "pie",
    },
}


def _parse_data(data: Any) -> Optional[dict]:
    """解析数据，处理各种输入格式（str/dict/list of tuples）"""
    # 直接是dict
    if isinstance(data, dict):
        if data:
            return data
        return None
    # 字符串
    if isinstance(data, str):
        data = data.strip()
        if not data or data == "{}":
            return None
        try:
            parsed = json.loads(data)
            if isinstance(parsed, dict) and parsed:
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass
        return None
    # list of tuples (SQL查询结果格式)
    if isinstance(data, list) and len(data) > 0:
        if isinstance(data[0], (list, tuple)) and len(data[0]) >= 2:
            # 转为column-oriented dict格式
            n_cols = len(data[0])
            result = {}
            for i in range(n_cols):
                col_name = f"col_{i}" if i > 0 else "x"
                result[col_name] = [row[i] for row in data]
            return result if result else None
    return None


@tool
def output_table(data: Any) -> str:
    """
    输出漂亮的表格 (Plotly Table)。
    data: JSON字符串或字典，格式 {"列名1": [值...], "列名2": [值...]}
    也接受SQL查询结果格式如 [(值1, 值2), ...]
    """
    with TimerContext("tool.output_table", _perf):
        data = _parse_data(data)
        if not data or len(data) < 1:
            return json.dumps({"error": "数据格式错误，需要至少1列数据"})
        df = pd.DataFrame(data)
        fig = go.Figure(data=[go.Table(
            header={'values': list(df.columns), 'fill_color': '#4A90D9', 'font': {'color': 'white', 'size': 13}, 'align': 'left'},
            cells={'values': [df[col] for col in df.columns], 'fill_color': '#F0F4FA', 'align': 'left', 'font': {'size': 12}}
        )])
        fig.update_layout(margin=dict(l=20, r=20, t=30, b=20), height=max(300, len(df) * 35 + 80))
        return fig.to_json()


@tool
def output_bar_plot(data: Any, title: str = "") -> str:
    """
    输出柱状图。
    data: JSON字符串或字典，格式 {"x轴": [...], "y轴": [...]}
    也接受SQL查询结果格式如 [(x值, y值), ...]
    title: 图表标题（可选）
    """
    with TimerContext("tool.output_bar_plot", _perf):
        data = _parse_data(data)
        if not data or len(data) < 2:
            return json.dumps({"error": "数据格式错误，需要至少2列数据 (x轴, y轴)"})
        keys = list(data.keys())
        x_key, y_key = keys[0], keys[1]
        fig = go.Figure(data=[go.Bar(
            x=data[x_key], y=data[y_key],
            marker_color='#4A90D9', marker_line_color='#2E6BAC', marker_line_width=1
        )])
        fig.update_layout(
            title=title or f"{y_key} by {x_key}",
            xaxis_title=x_key, yaxis_title=y_key,
            template="plotly_white", margin=dict(l=50, r=30, t=50, b=50)
        )
        return fig.to_json()


@tool
def output_time_series_plot(data: Any, title: str = "") -> str:
    """
    输出折线图（时间序列趋势）。
    data: JSON字符串或字典，格式 {"x轴": [...], "系列1": [...], "系列2": [...]}
    也接受SQL查询结果格式如 [(x值, y值), ...]
    title: 图表标题（可选）
    """
    with TimerContext("tool.output_time_series_plot", _perf):
        data = _parse_data(data)
        if not data or len(data) < 2:
            return json.dumps({"error": "数据格式错误，需要至少2列数据"})
        keys = list(data.keys())
        x_key = keys[0]
        x_vals = data[x_key]
        color_palette = ['#4A90D9', '#E74C3C', '#2ECC71', '#F39C12', '#9B59B6', '#1ABC9C', '#E67E22', '#34495E']
        fig = go.Figure()
        for i, y_key in enumerate(keys[1:]):
            fig.add_trace(go.Scatter(
                x=x_vals, y=data[y_key], mode='markers+lines',
                name=y_key, line=dict(color=color_palette[i % len(color_palette)], width=2),
                marker=dict(size=6)
            ))
        fig.update_layout(
            title=title or "趋势图",
            xaxis_title=x_key, yaxis_title="数值",
            template="plotly_white",
            xaxis={"tickmode": "array", "tickvals": x_vals},
            margin=dict(l=50, r=30, t=50, b=50)
        )
        return fig.to_json()


@tool
def output_pie_plot(data: Any, title: str = "") -> str:
    """
    输出饼图（占比分析）。
    data: JSON字符串或字典，格式 {"标签": [...], "数值": [...]}
    也接受SQL查询结果格式如 [(标签, 值), ...]
    title: 图表标题（可选）
    """
    with TimerContext("tool.output_pie_plot", _perf):
        data = _parse_data(data)
        if not data or len(data) < 2:
            return json.dumps({"error": "数据格式错误，需要至少2列数据 (标签, 数值)"})
        keys = list(data.keys())
        fig = go.Figure(data=[go.Pie(
            labels=data[keys[0]], values=data[keys[1]],
            hole=0.3, textinfo='label+percent'
        )])
        fig.update_layout(
            title=title or "占比图",
            template="plotly_white",
            margin=dict(l=30, r=30, t=50, b=30)
        )
        return fig.to_json()


@tool
def preset_query(query_name: str) -> str:
    """
    执行预置业务分析查询。可用的查询名称:
    monthly_revenue (月度收入趋势), category_top10 (类目TOP10),
    city_distribution (城市分布), payment_analysis (支付方式分析),
    delivery_performance (配送绩效), review_correlation (评分与配送相关性),
    seller_top10 (卖家TOP10), repeat_purchase (复购分布),
    rfm_summary (RFM分群概览), order_status (订单状态),
    freight_analysis (运费分析), installment_analysis (分期分析),
    weekday_orders (星期订单分布), state_revenue (各州销售),
    customer_lifetime (客户生命周期)
    """
    with TimerContext(f"tool.preset_query({query_name})", _perf):
        if query_name not in PRESET_QUERIES:
            available = ", ".join(PRESET_QUERIES.keys())
            return json.dumps({"error": f"未知查询 '{query_name}'。可用: {available}"})

        preset = PRESET_QUERIES[query_name]
        conn = sqlite3.connect(str(DB_PATH))
        try:
            df = pd.read_sql_query(preset["sql"], conn)
        except sqlite3.Error as e:
            return json.dumps({"error": f"查询执行失败: {str(e)}"})
        finally:
            conn.close()

        if df.empty:
            return json.dumps({"message": "查询结果为空", "data": {}})

        result = {"description": preset["description"], "data": df.to_dict(orient="list")}
        return json.dumps(result, ensure_ascii=False)


@tool
def auto_visualize(data: Any, title: str = "") -> str:
    """
    自动检测数据类型并生成最合适的图表。
    data: JSON字符串或字典，格式 {"列名1": [值...], "列名2": [值...]}
    也接受SQL查询结果格式如 [(值1, 值2), ...]
    title: 图表标题（可选）
    自动判断: 时间序列→折线图, 分类+少量类别→饼图, 分类+多类别→柱状图
    """
    with TimerContext("tool.auto_visualize", _perf):
        return _auto_visualize_impl(data, title)


def _auto_visualize_impl(data: Any, title: str = "") -> str:
    data = _parse_data(data)
    if not data or len(data) < 2:
        return json.dumps({"error": "数据格式错误，需要至少2列数据"})

    keys = list(data.keys())
    x_key, y_key = keys[0], keys[1]
    x_vals = data[x_key]
    n = len(x_vals)

    # 检测时间序列: 采样前5个值，多数匹配日期模式
    is_time = False
    if n > 0:
        sample_count = min(5, n)
        date_pattern = re.compile(r"^\d{4}-(0[1-9]|1[0-2])")
        matches = sum(1 for i in range(sample_count) if date_pattern.match(str(x_vals[i])))
        is_time = matches > sample_count // 2

    color_palette = ['#4A90D9', '#E74C3C', '#2ECC71', '#F39C12', '#9B59B6']

    if is_time:
        fig = go.Figure()
        for i, y_k in enumerate(keys[1:]):
            fig.add_trace(go.Scatter(
                x=x_vals, y=data[y_k], mode="markers+lines",
                name=y_k, line=dict(color=color_palette[i % len(color_palette)], width=2),
            ))
        fig.update_layout(
            title=title or "趋势图", xaxis_title=x_key, yaxis_title="数值",
            template="plotly_white", margin=dict(l=50, r=30, t=50, b=50),
        )
        return fig.to_json()

    # 检测分类数据: 少量类别 → 饼图，多类别 → 柱状图
    if n <= 8:
        fig = go.Figure(data=[go.Pie(
            labels=x_vals, values=data[y_key],
            hole=0.3, textinfo="label+percent",
        )])
        fig.update_layout(
            title=title or "占比图", template="plotly_white",
            margin=dict(l=30, r=30, t=50, b=30),
        )
    else:
        fig = go.Figure()
        for i, y_k in enumerate(keys[1:]):
            fig.add_trace(go.Bar(
                x=x_vals, y=data[y_k], name=y_k,
                marker_color=color_palette[i % len(color_palette)],
                marker_line_color="#2E6BAC", marker_line_width=1,
            ))
        fig.update_layout(
            title=title or f"对比图",
            xaxis_title=x_key, yaxis_title="数值",
            barmode="group",
            template="plotly_white", margin=dict(l=50, r=30, t=50, b=50),
        )
    return fig.to_json()


@tool
def query_and_visualize(query_name: str, title: str = "") -> str:
    """
    执行预置查询并自动生成可视化图表（一步完成，无需分两步调用）。
    query_name: 预置查询名称，如 monthly_revenue, category_top10, city_distribution 等
    title: 图表标题（可选，默认使用查询的描述）
    返回plotly图表JSON，可直接用于渲染。
    """
    with TimerContext(f"tool.query_and_visualize({query_name})", _perf):
        return _query_and_visualize_impl(query_name, title)


def _query_and_visualize_impl(query_name: str, title: str = "") -> str:
    if query_name not in PRESET_QUERIES:
        available = ", ".join(PRESET_QUERIES.keys())
        return json.dumps({"error": f"未知查询 '{query_name}'。可用: {available}"})

    preset = PRESET_QUERIES[query_name]
    conn = sqlite3.connect(str(DB_PATH))
    try:
        df = pd.read_sql_query(preset["sql"], conn)
    except sqlite3.Error as e:
        return json.dumps({"error": f"查询执行失败: {str(e)}"})
    finally:
        conn.close()

    if df.empty:
        return json.dumps({"message": "查询结果为空", "data": {}})

    data = df.to_dict(orient="list")
    chart_title = title or preset["description"]

    # 根据预设图表类型生成图表
    chart_type = preset["chart"]
    keys = list(data.keys())
    x_vals = data[keys[0]]
    color_palette = ['#4A90D9', '#E74C3C', '#2ECC71', '#F39C12', '#9B59B6']

    fig = None
    if chart_type == "time_series":
        fig = go.Figure()
        for i, y_k in enumerate(keys[1:]):
            fig.add_trace(go.Scatter(
                x=x_vals, y=data[y_k], mode="markers+lines",
                name=y_k, line=dict(color=color_palette[i % len(color_palette)], width=2),
            ))
        fig.update_layout(
            title=chart_title, xaxis_title=keys[0], yaxis_title="数值",
            template="plotly_white", margin=dict(l=50, r=30, t=50, b=50),
        )
    elif chart_type == "pie":
        fig = go.Figure(data=[go.Pie(
            labels=x_vals, values=data[keys[1]],
            hole=0.3, textinfo="label+percent",
        )])
        fig.update_layout(
            title=chart_title, template="plotly_white",
            margin=dict(l=30, r=30, t=50, b=30),
        )
    elif chart_type == "bar":
        fig = go.Figure()
        for i, y_k in enumerate(keys[1:]):
            fig.add_trace(go.Bar(
                x=x_vals, y=data[y_k], name=y_k,
                marker_color=color_palette[i % len(color_palette)],
                marker_line_color="#2E6BAC", marker_line_width=1,
            ))
        fig.update_layout(
            title=chart_title, xaxis_title=keys[0], yaxis_title="数值",
            barmode="group", template="plotly_white",
            margin=dict(l=50, r=30, t=50, b=50),
        )
    elif chart_type == "table":
        fig = go.Figure(data=[go.Table(
            header={'values': list(df.columns), 'fill_color': '#4A90D9',
                    'font': {'color': 'white', 'size': 13}, 'align': 'left'},
            cells={'values': [df[col] for col in df.columns],
                   'fill_color': '#F0F4FA', 'align': 'left', 'font': {'size': 12}},
        )])
        fig.update_layout(
            title=chart_title,
            margin=dict(l=20, r=20, t=30, b=20),
            height=max(300, len(df) * 35 + 80),
        )

    if fig is not None:
        return fig.to_json()
    else:
        return json.dumps({"description": preset["description"], "data": data}, ensure_ascii=False)
