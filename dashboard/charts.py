"""
图表工厂 - 15+种Plotly图表类型
"""
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np


class ChartFactory:
    """图表工厂类，提供各种Plotly图表"""

    # 统一配色方案
    COLORS = px.colors.qualitative.Set2
    SEQUENTIAL = "Viridis"
    DIVERGING = "RdYlGn"

    @staticmethod
    def bar(df: pd.DataFrame, x: str, y: str, title: str = "",
            color: str = None, horizontal: bool = False) -> go.Figure:
        """柱状图"""
        if horizontal:
            fig = px.bar(df, y=x, x=y, title=title, color=color,
                        color_discrete_sequence=ChartFactory.COLORS,
                        orientation="h")
        else:
            fig = px.bar(df, x=x, y=y, title=title, color=color,
                        color_discrete_sequence=ChartFactory.COLORS)
        fig.update_layout(template="plotly_white", margin=dict(l=50, r=30, t=50, b=50))
        return fig

    @staticmethod
    def line(df: pd.DataFrame, x: str, y: str, title: str = "",
             color: str = None) -> go.Figure:
        """折线图"""
        fig = px.line(df, x=x, y=y, title=title, color=color,
                     markers=True, color_discrete_sequence=ChartFactory.COLORS)
        fig.update_layout(template="plotly_white", margin=dict(l=50, r=30, t=50, b=50))
        return fig

    @staticmethod
    def pie(df: pd.DataFrame, names: str, values: str, title: str = "") -> go.Figure:
        """饼图"""
        fig = px.pie(df, names=names, values=values, title=title,
                    hole=0.3, color_discrete_sequence=ChartFactory.COLORS)
        fig.update_layout(template="plotly_white", margin=dict(l=30, r=30, t=50, b=30))
        return fig

    @staticmethod
    def scatter_3d(df: pd.DataFrame, x: str, y: str, z: str,
                   color: str = None, title: str = "") -> go.Figure:
        """3D散点图"""
        fig = px.scatter_3d(df, x=x, y=y, z=z, color=color, title=title,
                           color_discrete_sequence=ChartFactory.COLORS,
                           opacity=0.7)
        fig.update_layout(
            template="plotly_white",
            scene=dict(
                xaxis_title=x, yaxis_title=y, zaxis_title=z
            ),
            margin=dict(l=0, r=0, t=50, b=0)
        )
        return fig

    @staticmethod
    def radar(categories: list, values: list, title: str = "",
              reference_values: list = None) -> go.Figure:
        """雷达图"""
        fig = go.Figure()
        fig.add_trace(go.Scatterpolar(
            r=values + [values[0]],
            theta=categories + [categories[0]],
            fill="toself",
            name="当前群体",
            line_color=ChartFactory.COLORS[0],
            opacity=0.7
        ))
        if reference_values:
            fig.add_trace(go.Scatterpolar(
                r=reference_values + [reference_values[0]],
                theta=categories + [categories[0]],
                fill="toself",
                name="整体平均",
                line_color=ChartFactory.COLORS[1],
                opacity=0.5
            ))
        fig.update_layout(
            polar=dict(radialaxis=dict(visible=True)),
            showlegend=True, title=title,
            template="plotly_white",
            margin=dict(l=80, r=80, t=50, b=50)
        )
        return fig

    @staticmethod
    def funnel(names: list, values: list, title: str = "") -> go.Figure:
        """漏斗图"""
        fig = go.Figure(go.Funnel(
            y=names, x=values,
            marker_color=px.colors.sequential.Viridis[:len(names)],
            textinfo="value+percent initial"
        ))
        fig.update_layout(
            title=title, template="plotly_white",
            margin=dict(l=50, r=30, t=50, b=30)
        )
        return fig

    @staticmethod
    def heatmap(df: pd.DataFrame, x: str, y: str, z: str,
                title: str = "") -> go.Figure:
        """热力图"""
        pivot = df.pivot_table(index=y, columns=x, values=z, aggfunc="mean")
        fig = go.Figure(data=go.Heatmap(
            z=pivot.values,
            x=pivot.columns.tolist(),
            y=pivot.index.tolist(),
            colorscale="YlOrRd",
            text=np.round(pivot.values, 1),
            texttemplate="%{text}",
            textfont={"size": 10}
        ))
        fig.update_layout(
            title=title, template="plotly_white",
            margin=dict(l=50, r=30, t=50, b=50)
        )
        return fig

    @staticmethod
    def box(df: pd.DataFrame, x: str, y: str, title: str = "",
            color: str = None) -> go.Figure:
        """箱线图"""
        fig = px.box(df, x=x, y=y, title=title, color=color,
                    color_discrete_sequence=ChartFactory.COLORS)
        fig.update_layout(template="plotly_white", margin=dict(l=50, r=30, t=50, b=50))
        return fig

    @staticmethod
    def histogram(df: pd.DataFrame, x: str, title: str = "",
                  nbins: int = 30, color: str = None) -> go.Figure:
        """直方图"""
        fig = px.histogram(df, x=x, title=title, nbins=nbins, color=color,
                          color_discrete_sequence=ChartFactory.COLORS)
        fig.update_layout(template="plotly_white", margin=dict(l=50, r=30, t=50, b=50))
        return fig

    @staticmethod
    def treemap(df: pd.DataFrame, path: list, values: str,
                title: str = "") -> go.Figure:
        """矩形树图"""
        fig = px.treemap(df, path=path, values=values, title=title,
                        color_discrete_sequence=ChartFactory.COLORS)
        fig.update_layout(template="plotly_white", margin=dict(l=20, r=20, t=50, b=20))
        return fig

    @staticmethod
    def scatter(df: pd.DataFrame, x: str, y: str, title: str = "",
                color: str = None, size: str = None) -> go.Figure:
        """散点图"""
        fig = px.scatter(df, x=x, y=y, title=title, color=color, size=size,
                        color_discrete_sequence=ChartFactory.COLORS,
                        opacity=0.7)
        fig.update_layout(template="plotly_white", margin=dict(l=50, r=30, t=50, b=50))
        return fig

    @staticmethod
    def kpi_card(label: str, value: str, delta: str = None,
                 delta_color: str = "normal") -> None:
        """KPI指标卡（使用Streamlit metric）"""
        # 这个方法返回数据，由Streamlit渲染
        return {"label": label, "value": value, "delta": delta, "delta_color": delta_color}

    @staticmethod
    def donut(df: pd.DataFrame, names: str, values: str,
              title: str = "") -> go.Figure:
        """环形图"""
        fig = go.Figure(data=[go.Pie(
            labels=df[names], values=df[values],
            hole=0.5, textinfo="label+percent",
            marker_colors=ChartFactory.COLORS
        )])
        fig.update_layout(
            title=title, template="plotly_white",
            margin=dict(l=30, r=30, t=50, b=30)
        )
        return fig

    @staticmethod
    def area(df: pd.DataFrame, x: str, y: str, title: str = "",
             color: str = None) -> go.Figure:
        """面积图"""
        fig = px.area(df, x=x, y=y, title=title, color=color,
                     color_discrete_sequence=ChartFactory.COLORS)
        fig.update_layout(template="plotly_white", margin=dict(l=50, r=30, t=50, b=50))
        return fig

    @staticmethod
    def violin(df: pd.DataFrame, x: str, y: str, title: str = "",
               color: str = None) -> go.Figure:
        """小提琴图"""
        fig = px.violin(df, x=x, y=y, title=title, color=color,
                       box=True, color_discrete_sequence=ChartFactory.COLORS)
        fig.update_layout(template="plotly_white", margin=dict(l=50, r=30, t=50, b=50))
        return fig

    @staticmethod
    def table(df: pd.DataFrame, title: str = "") -> go.Figure:
        """数据表格"""
        fig = go.Figure(data=[go.Table(
            header=dict(
                values=list(df.columns),
                fill_color="#4A90D9",
                font=dict(color="white", size=12),
                align="left"
            ),
            cells=dict(
                values=[df[col] for col in df.columns],
                fill_color="#F0F4FA",
                align="left",
                font=dict(size=11)
            )
        )])
        fig.update_layout(
            title=title,
            margin=dict(l=20, r=20, t=50, b=20),
            height=min(600, max(300, len(df) * 35 + 80))
        )
        return fig
