"""
图表工厂 - 20+种Plotly图表类型
"""
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
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

    @staticmethod
    def sankey(labels: list, sources: list, targets: list, values: list,
               title: str = "") -> go.Figure:
        """桑基图 - 展示流量/流向关系"""
        # 为节点生成颜色
        n = len(labels)
        colors = (px.colors.qualitative.Set2 * ((n // len(px.colors.qualitative.Set2)) + 1))[:n]

        fig = go.Figure(data=[go.Sankey(
            node=dict(
                pad=15, thickness=20,
                line=dict(color="white", width=0.5),
                label=labels, color=colors,
            ),
            link=dict(
                source=sources, target=targets, value=values,
                color="rgba(200,200,200,0.3)",
            ),
        )])
        fig.update_layout(
            title=title, template="plotly_white",
            margin=dict(l=20, r=20, t=50, b=20),
        )
        return fig

    @staticmethod
    def sunburst(labels: list, parents: list, values: list,
                 title: str = "") -> go.Figure:
        """旭日图 - 展示层级结构"""
        fig = go.Figure(go.Sunburst(
            labels=labels, parents=parents, values=values,
            branchvalues="total",
            hovertemplate="<b>%{label}</b><br>数量: %{value}<br>占比: %{percentRoot:.1%}<extra></extra>",
            marker=dict(colorscale="Viridis"),
        ))
        fig.update_layout(
            title=title, template="plotly_white",
            margin=dict(l=20, r=20, t=50, b=20),
        )
        return fig

    @staticmethod
    def dual_axis(df: pd.DataFrame, x: str, y_bar: str, y_line: str,
                  title: str = "", bar_name: str = "柱状图",
                  line_name: str = "折线图",
                  y_bar_label: str = "", y_line_label: str = "") -> go.Figure:
        """双轴图 - 柱状图+折线图组合，左右Y轴独立缩放"""
        fig = make_subplots(specs=[[{"secondary_y": True}]])

        fig.add_trace(
            go.Bar(
                x=df[x], y=df[y_bar], name=bar_name,
                marker_color=ChartFactory.COLORS[0], opacity=0.7,
            ),
            secondary_y=False,
        )

        fig.add_trace(
            go.Scatter(
                x=df[x], y=df[y_line], name=line_name,
                mode="lines+markers",
                line=dict(color=ChartFactory.COLORS[1], width=3),
                marker=dict(size=7),
            ),
            secondary_y=True,
        )

        # 独立缩放：让两个轴各自占图表高度的80%，避免数值大的压扁数值小的
        bar_vals = df[y_bar].dropna()
        line_vals = df[y_line].dropna()
        if len(bar_vals) > 0 and bar_vals.max() > 0:
            bar_margin = (bar_vals.max() - bar_vals.min()) * 0.1
            fig.update_yaxes(
                title_text=y_bar_label or y_bar,
                secondary_y=False,
                range=[max(0, bar_vals.min() - bar_margin), bar_vals.max() + bar_margin],
            )
        else:
            fig.update_yaxes(title_text=y_bar_label or y_bar, secondary_y=False)

        if len(line_vals) > 0 and line_vals.max() > 0:
            line_margin = (line_vals.max() - line_vals.min()) * 0.1
            fig.update_yaxes(
                title_text=y_line_label or y_line,
                secondary_y=True,
                range=[max(0, line_vals.min() - line_margin), line_vals.max() + line_margin],
            )
        else:
            fig.update_yaxes(title_text=y_line_label or y_line, secondary_y=True)

        fig.update_layout(
            title=title, template="plotly_white",
            margin=dict(l=50, r=50, t=50, b=50),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        return fig

    @staticmethod
    def weekday_hour_heatmap(df: pd.DataFrame, title: str = "") -> go.Figure:
        """星期×小时热力图 - 展示订单活跃时段"""
        day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        day_labels = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

        # 确保有day_of_week和hour列
        if "day_of_week" not in df.columns or "hour" not in df.columns:
            raise ValueError("DataFrame必须包含day_of_week和hour列")

        pivot = df.pivot_table(index="day_of_week", columns="hour", values="count", aggfunc="sum").fillna(0)
        # 按星期排序
        available_days = [d for d in day_order if d in pivot.index]
        pivot = pivot.reindex(available_days)
        pivot.index = [day_labels[day_order.index(d)] for d in available_days]

        fig = go.Figure(data=go.Heatmap(
            z=pivot.values,
            x=[f"{h:02d}:00" for h in pivot.columns],
            y=pivot.index.tolist(),
            colorscale="YlOrRd",
            text=np.round(pivot.values, 0).astype(int),
            texttemplate="%{text}",
            textfont={"size": 10},
            hovertemplate="<b>%{y}</b> %{x}<br>订单数: %{z}<extra></extra>",
        ))
        fig.update_layout(
            title=title, template="plotly_white",
            margin=dict(l=60, r=30, t=50, b=50),
            xaxis_title="时段", yaxis_title="星期",
        )
        return fig
