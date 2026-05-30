import json
from typing import Any

import pandas as pd
import plotly.graph_objects as go
from langchain.tools import tool


def _parse_data(data: Any) -> dict:
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
            # 转为dict格式: 第一列作key，其余列作values
            result = {}
            for row in data:
                if len(row) == 2:
                    k, v = str(row[0]), row[1]
                    if k not in result:
                        result[k] = []
                    result[k].append(v)
                else:
                    for i, val in enumerate(row):
                        col_name = f"col_{i}" if i > 0 else "x"
                        if col_name not in result:
                            result[col_name] = []
                        result[col_name].append(val)
            return result if result else None
    return None


@tool
def output_table(data: Any) -> str:
    """
    输出漂亮的表格 (Plotly Table)。
    data: JSON字符串或字典，格式 {"列名1": [值...], "列名2": [值...]}
    也接受SQL查询结果格式如 [(值1, 值2), ...]
    """
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
