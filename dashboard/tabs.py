"""
标签页渲染器 - 仪表盘各标签页内容
"""
import sqlite3
from datetime import datetime

import pandas as pd
import streamlit as st

from .charts import ChartFactory
from config import DB_PATH
from utils.timing import get_perf_logger, TimerContext, read_recent_logs, log_user_action


class TabRenderer:
    """仪表盘标签页渲染器"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(DB_PATH)
        self.charts = ChartFactory()
        self.perf = get_perf_logger()

    def _query(self, sql: str, params=None) -> pd.DataFrame:
        """执行SQL查询"""
        with TimerContext("db_query", self.perf):
            conn = sqlite3.connect(self.db_path)
            df = pd.read_sql_query(sql, conn, params=params)
            conn.close()
            return df

    def render_overview(self):
        """Tab1 - 数据概览"""
        with TimerContext("render_overview", self.perf):
            self._render_overview_impl()

    def _render_overview_impl(self):
        st.header("📊 数据概览")

        # 日期范围筛选
        col_date1, col_date2 = st.columns(2)
        with col_date1:
            date_range = self._query("SELECT MIN(order_purchase_timestamp) as min_d, MAX(order_purchase_timestamp) as max_d FROM orders")
            min_date = pd.to_datetime(date_range["min_d"].iloc[0]).date() if not date_range.empty else None
            max_date = pd.to_datetime(date_range["max_d"].iloc[0]).date() if not date_range.empty else None
            start_date = st.date_input("开始日期", value=min_date, key="overview_start")
        with col_date2:
            end_date = st.date_input("结束日期", value=max_date, key="overview_end")

        log_user_action("date_filter", f"start={start_date}, end={end_date}")

        date_filter = ""
        if start_date and end_date:
            date_filter = f"AND order_purchase_timestamp >= '{start_date}' AND order_purchase_timestamp <= '{end_date} 23:59:59'"

        # KPI指标（带日期筛选）
        kpis = self._get_kpis_filtered(date_filter)
        cols = st.columns(4)
        for i, (label, value, delta) in enumerate(kpis):
            with cols[i]:
                st.metric(label=label, value=value, delta=delta)

        st.divider()

        # ── 第一行: 双轴图 (收入+订单数) + 类目饼图 ──
        col1, col2 = st.columns(2)

        with col1:
            with TimerContext("overview_monthly_chart", self.perf):
                monthly = self._query(f"""
                    SELECT
                        strftime('%Y-%m', order_purchase_timestamp) as month,
                        COUNT(DISTINCT order_id) as order_count,
                        SUM(total_price) as revenue
                    FROM orders
                    WHERE order_status = 'delivered' {date_filter}
                    GROUP BY month
                    ORDER BY month
                """)
                if not monthly.empty:
                    fig = self.charts.dual_axis(
                        monthly, "month", "revenue", "order_count",
                        "月度收入与订单趋势",
                        bar_name="收入 (R$)", line_name="订单数",
                        y_bar_label="收入 (R$)", y_line_label="订单数",
                    )
                    st.plotly_chart(fig, width="stretch")
                st.download_button("下载月度数据 CSV", monthly.to_csv(index=False).encode("utf-8-sig"),
                                   "monthly_sales.csv", "text/csv", key="dl_monthly")

        with col2:
            with TimerContext("overview_category_pie", self.perf):
                categories = self._query(f"""
                    SELECT
                        COALESCE(ct.product_category_name_english, p.product_category_name) as category,
                        SUM(oi.price) as revenue
                    FROM order_items oi
                    JOIN products p ON oi.product_id = p.product_id
                    JOIN orders o ON oi.order_id = o.order_id
                    LEFT JOIN category_translation ct ON p.product_category_name = ct.product_category_name
                    WHERE o.order_status = 'delivered' {date_filter}
                    GROUP BY category
                    ORDER BY revenue DESC
                    LIMIT 10
                """)
                if not categories.empty:
                    fig = self.charts.pie(categories, "category", "revenue", "类目销售占比 TOP10")
                    st.plotly_chart(fig, width="stretch")
                    st.download_button("下载类目数据 CSV", categories.to_csv(index=False).encode("utf-8-sig"),
                                       "category_sales.csv", "text/csv", key="dl_cat")

        # ── 第二行: 星期×小时热力图 + 地域分布 ──
        col3, col4 = st.columns(2)

        with col3:
            with TimerContext("overview_heatmap", self.perf):
                hourly = self._query(f"""
                    SELECT
                        CASE CAST(strftime('%w', order_purchase_timestamp) AS INTEGER)
                            WHEN 0 THEN 'Sunday' WHEN 1 THEN 'Monday'
                            WHEN 2 THEN 'Tuesday' WHEN 3 THEN 'Wednesday'
                            WHEN 4 THEN 'Thursday' WHEN 5 THEN 'Friday'
                            WHEN 6 THEN 'Saturday'
                        END as day_of_week,
                        CAST(strftime('%H', order_purchase_timestamp) AS INTEGER) as hour,
                        COUNT(*) as count
                    FROM orders
                    WHERE order_status = 'delivered' {date_filter}
                    GROUP BY day_of_week, hour
                """)
                if not hourly.empty:
                    fig = self.charts.weekday_hour_heatmap(hourly, "订单活跃时段分布")
                    st.plotly_chart(fig, width="stretch")

        with col4:
            with TimerContext("overview_geo", self.perf):
                geo = self._query("""
                    SELECT customer_state, COUNT(*) as count
                    FROM customers GROUP BY customer_state
                    ORDER BY count DESC LIMIT 10
                """)
                if not geo.empty:
                    fig = self.charts.bar(geo, "customer_state", "count", "客户地域分布 TOP10")
                    st.plotly_chart(fig, width="stretch")

        # ── 第三行: 类目树状图 + 支付方式 ──
        col5, col6 = st.columns(2)

        with col5:
            with TimerContext("overview_treemap", self.perf):
                treemap_data = self._query(f"""
                    SELECT
                        COALESCE(ct.product_category_name_english, p.product_category_name) as category,
                        o.order_value_category as value_tier,
                        SUM(oi.price) as revenue
                    FROM order_items oi
                    JOIN products p ON oi.product_id = p.product_id
                    JOIN orders o ON oi.order_id = o.order_id
                    LEFT JOIN category_translation ct ON p.product_category_name = ct.product_category_name
                    WHERE o.order_status = 'delivered' {date_filter}
                      AND o.order_value_category IS NOT NULL
                    GROUP BY category, value_tier
                    ORDER BY revenue DESC
                    LIMIT 50
                """)
                if not treemap_data.empty:
                    fig = self.charts.treemap(
                        treemap_data, path=["category", "value_tier"], values="revenue",
                        title="类目×订单价值层级",
                    )
                    st.plotly_chart(fig, width="stretch")

        with col6:
            payments = self._query("""
                SELECT payment_type, COUNT(*) as count
                FROM order_payments GROUP BY payment_type
                ORDER BY count DESC
            """)
            if not payments.empty:
                fig = self.charts.donut(payments, "payment_type", "count", "支付方式分布")
                st.plotly_chart(fig, width="stretch")

    def render_rfm(self):
        """Tab2 - RFM分析"""
        with TimerContext("render_rfm", self.perf):
            self._render_rfm_impl()

    def _render_rfm_impl(self):
        st.header("🔬 RFM客户分析")

        rfm = self._query("SELECT * FROM rfm_results")
        if rfm.empty:
            st.warning("暂无RFM数据，请先运行ETL和RFM分析。")
            return

        # 中文标签映射
        from analysis.rfm_engine import RFMEngine
        segment_labels = RFMEngine.SEGMENT_LABELS
        rfm["segment_label"] = rfm["segment"].map(segment_labels).fillna(rfm["segment"])

        # 概览指标
        cols = st.columns(4)
        with cols[0]:
            st.metric("分析客户数", f"{len(rfm):,}")
        with cols[1]:
            st.metric("平均Recency", f"{rfm['recency'].mean():.0f} 天")
        with cols[2]:
            st.metric("平均Frequency", f"{rfm['frequency'].mean():.1f} 次")
        with cols[3]:
            st.metric("平均Monetary", f"R${rfm['monetary'].mean():.2f}")

        st.divider()

        # ── 第一行: 旭日图 + 饼图 ──
        col1, col2 = st.columns(2)

        with col1:
            # 旭日图: 分群 → 聚类层级
            seg_cluster = rfm.groupby(["segment_label", "cluster_label"]).size().reset_index(name="count")
            if not seg_cluster.empty:
                labels = ["全部客户"]
                parents = [""]
                values = [len(rfm)]

                for seg in seg_cluster["segment_label"].unique():
                    seg_count = seg_cluster[seg_cluster["segment_label"] == seg]["count"].sum()
                    labels.append(seg)
                    parents.append("全部客户")
                    values.append(seg_count)

                    clusters = seg_cluster[seg_cluster["segment_label"] == seg]
                    for _, row in clusters.iterrows():
                        cluster_name = f"{seg}-群体{int(row['cluster_label'])}"
                        labels.append(cluster_name)
                        parents.append(seg)
                        values.append(int(row["count"]))

                fig = self.charts.sunburst(labels, parents, values, "客户分群层级结构")
                st.plotly_chart(fig, width="stretch")

        with col2:
            segment_counts = rfm["segment_label"].value_counts().reset_index()
            segment_counts.columns = ["segment_label", "count"]
            fig = self.charts.pie(segment_counts, "segment_label", "count", "客户分群占比")
            st.plotly_chart(fig, width="stretch")

        # ── 第二行: 3D散点图 + 箱线图 ──
        col3, col4 = st.columns(2)

        with col3:
            fig = self.charts.scatter_3d(
                rfm, "recency", "frequency", "monetary",
                color="segment_label", title="RFM 3D散点图"
            )
            st.plotly_chart(fig, width="stretch")

        with col4:
            fig = self.charts.box(rfm, "segment_label", "monetary", "各群体消费分布")
            st.plotly_chart(fig, width="stretch")

        # ── 第三行: 桑基图 (分群→支付方式) + 雷达图 ──
        col5, col6 = st.columns(2)

        with col5:
            sankey_data = self._query("""
                SELECT r.segment, op.payment_type, COUNT(*) as cnt
                FROM rfm_results r
                JOIN customers c ON r.customer_id = c.customer_unique_id
                JOIN orders o ON c.customer_id = o.customer_id
                JOIN order_payments op ON o.order_id = op.order_id
                GROUP BY r.segment, op.payment_type
                HAVING cnt > 100
            """)
            if not sankey_data.empty:
                sankey_data["segment_label"] = sankey_data["segment"].map(segment_labels).fillna(sankey_data["segment"])
                # 构建桑基图数据
                all_nodes = list(sankey_data["segment_label"].unique()) + list(sankey_data["payment_type"].unique())
                node_dict = {name: idx for idx, name in enumerate(all_nodes)}

                sources = [node_dict[row["segment_label"]] for _, row in sankey_data.iterrows()]
                targets = [node_dict[row["payment_type"]] for _, row in sankey_data.iterrows()]
                values = sankey_data["cnt"].tolist()

                fig = self.charts.sankey(all_nodes, sources, targets, values, "客户分群 → 支付方式流向")
                st.plotly_chart(fig, width="stretch")

        with col6:
            # 雷达图 - 各群体RFM均值
            segments = rfm["segment_label"].unique()
            if len(segments) > 0:
                selected = st.selectbox("选择群体查看雷达图", segments, key="radar_seg")
                seg_data = rfm[rfm["segment_label"] == selected]
                categories = ["Recency(反向)", "Frequency", "Monetary"]
                # 归一化到0-1 (防除零)
                r_max = rfm["recency"].max() or 1
                f_max = rfm["frequency"].max() or 1
                m_max = rfm["monetary"].max() or 1
                r_norm = 1 - (seg_data["recency"].mean() / r_max)
                f_norm = seg_data["frequency"].mean() / f_max
                m_norm = seg_data["monetary"].mean() / m_max
                values = [r_norm * 100, f_norm * 100, m_norm * 100]

                r_all = 1 - (rfm["recency"].mean() / r_max)
                f_all = rfm["frequency"].mean() / f_max
                m_all = rfm["monetary"].mean() / m_max
                ref_values = [r_all * 100, f_all * 100, m_all * 100]

                fig = self.charts.radar(categories, values,
                                       f"{selected} vs 整体平均", ref_values)
                st.plotly_chart(fig, width="stretch")

        # ── 营销策略建议 ──
        st.divider()
        st.subheader("📋 营销策略建议")
        strategy_data = []
        from analysis.rfm_engine import RFMEngine as RE
        for segment in rfm["segment"].unique():
            seg_df = rfm[rfm["segment"] == segment]
            label = segment_labels.get(segment, segment)
            strategy = RE.STRATEGY_MAP.get(segment, "")
            strategy_data.append({
                "分群": label,
                "人数": len(seg_df),
                "占比": f"{len(seg_df)/len(rfm)*100:.1f}%",
                "平均Recency": f"{seg_df['recency'].mean():.0f}天",
                "平均Frequency": f"{seg_df['frequency'].mean():.1f}次",
                "平均Monetary": f"R${seg_df['monetary'].mean():.2f}",
                "营销策略": strategy,
            })
        st.dataframe(pd.DataFrame(strategy_data), width="stretch")

        # 导出RFM完整数据
        st.divider()
        st.subheader("📥 数据导出")
        csv_data = rfm.to_csv(index=False).encode("utf-8-sig")
        st.download_button("下载RFM完整数据 CSV", csv_data, "rfm_results.csv", "text/csv",
                           use_container_width=True, key="dl_rfm")

    def render_qa(self):
        """Tab3 - 智能问答"""
        st.header("💬 智能问答")

        # 模式切换
        mode = st.radio(
            "选择问答模式",
            ["SQL Agent (自然语言查询)", "RAG知识库问答"],
            horizontal=True, key="qa_mode"
        )
        log_user_action("switch_qa_mode", mode)

        if mode == "SQL Agent (自然语言查询)":
            self._render_sql_agent()
        else:
            self._render_rag_qa()

    def _render_sql_agent(self):
        """SQL Agent模式"""
        st.subheader("🔍 SQL Agent")
        st.caption("用自然语言描述你想查询的数据，AI会自动生成SQL并返回结果")

        if "sql_agent_messages" not in st.session_state:
            st.session_state.sql_agent_messages = []

        # 清除聊天按钮
        col_header1, col_header2 = st.columns([5, 1])
        with col_header2:
            if st.button("清除对话", key="clear_sql_chat"):
                log_user_action("click", "清除对话(SQL)")
                st.session_state.sql_agent_messages = []
                st.rerun()

        # 快速预置查询模式：关键词匹配直接调用，无需LLM
        PRESET_KEYWORD_MAP = {
            "月度收入": "monthly_revenue", "收入趋势": "monthly_revenue",
            "月度趋势": "monthly_revenue", "每月收入": "monthly_revenue",
            "类目top": "category_top10", "商品类目": "category_top10",
            "类目排名": "category_top10", "热销类目": "category_top10",
            "类目销售": "category_top10",
            "城市分布": "city_distribution", "客户城市": "city_distribution",
            "支付方式": "payment_analysis", "支付分析": "payment_analysis",
            "配送绩效": "delivery_performance", "配送时间": "delivery_performance",
            "延迟率": "delivery_performance",
            "评分": "review_correlation", "评价": "review_correlation",
            "卖家top": "seller_top10", "卖家排名": "seller_top10",
            "复购": "repeat_purchase", "购买次数": "repeat_purchase",
            "消费频率": "repeat_purchase", "消费次数": "repeat_purchase",
            "购买频率": "repeat_purchase", "频次": "repeat_purchase",
            "消费分布": "repeat_purchase", "购买分布": "repeat_purchase",
            "rfm": "rfm_summary", "分群": "rfm_summary", "客户分群": "rfm_summary",
            "订单状态": "order_status",
            "运费": "freight_analysis", "运费分析": "freight_analysis",
            "分期": "installment_analysis", "分期分析": "installment_analysis",
            "星期": "weekday_orders", "周几": "weekday_orders",
            "各州": "state_revenue", "州销售": "state_revenue",
            "生命周期": "customer_lifetime", "客户价值": "customer_lifetime",
        }

        def _try_fast_preset(query: str):
            """尝试快速预置查询，返回(query_name, chart_json)或None"""
            import json as _json
            import agent_tools as _at
            q_lower = query.lower()
            for keyword, preset_name in PRESET_KEYWORD_MAP.items():
                if keyword.lower() in q_lower:
                    try:
                        result = _at.query_and_visualize.invoke({"query_name": preset_name})
                        data = _json.loads(result)
                        if "data" in data and "layout" in data:
                            return preset_name, result
                        elif "data" in data:
                            # 有数据但没图表，用auto_visualize生成
                            auto_fig = _at.auto_visualize.invoke({
                                "data": _json.dumps(data["data"]),
                                "title": data.get("description", "")
                            })
                            auto_data = _json.loads(auto_fig)
                            if "data" in auto_data and "layout" in auto_data:
                                return preset_name, auto_fig
                    except Exception:
                        pass
            return None

        # 处理查询的辅助函数
        def _generate_data_summary(preset_name: str, chart_json: str) -> str:
            """从图表JSON中提取关键数据，生成有具体数字的回答"""
            import json as _json
            from agent_tools import PRESET_QUERIES as _PQ
            try:
                fig_data = _json.loads(chart_json)
                traces = fig_data.get("data", [])
                if not traces:
                    return f"📊 {_PQ.get(preset_name, {}).get('description', preset_name)}"

                first_trace = traces[0]
                x_vals = first_trace.get("x", [])
                y_vals = first_trace.get("y", [])
                labels = first_trace.get("labels", [])
                values = first_trace.get("values", [])
                header_vals = first_trace.get("header", {}).get("values", [])

                # 柱状图/折线图: 提取TOP项和总量
                if x_vals and y_vals:
                    # 过滤掉None
                    pairs = [(x, y) for x, y in zip(x_vals, y_vals) if y is not None]
                    if not pairs:
                        return f"📊 {_PQ.get(preset_name, {}).get('description', preset_name)}"

                    # 尝试转数值
                    numeric_pairs = []
                    for x, y in pairs:
                        try:
                            numeric_pairs.append((x, float(y)))
                        except (ValueError, TypeError):
                            numeric_pairs.append((x, y))

                    # 检查是否全是数值
                    all_numeric = all(isinstance(y, (int, float)) for _, y in numeric_pairs)

                    desc = _PQ.get(preset_name, {}).get("description", preset_name)
                    lines = [f"📊 **{desc}**\n"]

                    if all_numeric and numeric_pairs:
                        total = sum(y for _, y in numeric_pairs)
                        max_item = max(numeric_pairs, key=lambda p: p[1])
                        min_item = min(numeric_pairs, key=lambda p: p[1])
                        lines.append(f"- 共 **{len(numeric_pairs)}** 项，总计 **{total:,.2f}**")
                        lines.append(f"- 最高: **{max_item[0]}** = {max_item[1]:,.2f}")
                        if len(numeric_pairs) > 1:
                            lines.append(f"- 最低: **{min_item[0]}** = {min_item[1]:,.2f}")
                        # TOP3
                        top3 = sorted(numeric_pairs, key=lambda p: p[1], reverse=True)[:3]
                        lines.append(f"- TOP3: " + ", ".join(f"{x}({y:,.1f})" for x, y in top3))
                    else:
                        lines.append(f"- 共 {len(pairs)} 条记录")

                    return "\n".join(lines)

                # 饼图: 提取占比
                if labels and values:
                    desc = _PQ.get(preset_name, {}).get("description", preset_name)
                    total = sum(float(v) for v in values if v is not None)
                    lines = [f"📊 **{desc}**\n"]
                    for lbl, val in zip(labels[:5], values[:5]):
                        try:
                            pct = float(val) / total * 100 if total > 0 else 0
                            lines.append(f"- {lbl}: {float(val):,.0f} ({pct:.1f}%)")
                        except (ValueError, TypeError):
                            lines.append(f"- {lbl}: {val}")
                    if len(labels) > 5:
                        lines.append(f"- ...及其他 {len(labels)-5} 项")
                    return "\n".join(lines)

                # 表格: 提取行列数
                if header_vals:
                    desc = _PQ.get(preset_name, {}).get("description", preset_name)
                    n_rows = len(header_vals[0]) if header_vals else 0
                    return f"📊 **{desc}**\n- 共 {n_rows} 行数据，{len(header_vals)} 列"

                return f"📊 {_PQ.get(preset_name, {}).get('description', preset_name)}"
            except Exception:
                return f"📊 {_PQ.get(preset_name, {}).get('description', preset_name)}"

        def process_sql_query(query: str):
            import json as _json
            import re as _re
            import plotly.io as _pio
            with TimerContext(f"sql_query_total", self.perf):
                return _process_sql_query_impl(query)

        def _process_sql_query_impl(query: str):
            import json as _json
            import re as _re
            import plotly.io as _pio
            st.session_state.sql_agent_messages.append({"role": "user", "content": query})

            # 尝试快速预置查询模式（无需LLM，秒级响应）
            with TimerContext("sql_fast_preset_match", self.perf):
                fast_result = _try_fast_preset(query)
            if fast_result:
                preset_name, chart_json = fast_result
                from agent_tools import PRESET_QUERIES
                desc = PRESET_QUERIES.get(preset_name, {}).get("description", preset_name)
                # 从图表JSON中提取数据摘要
                summary = _generate_data_summary(preset_name, chart_json)
                st.session_state.sql_agent_messages.append({
                    "role": "assistant",
                    "content": summary,
                    "charts": [chart_json]
                })
                return

            # 拦截通用问题（不查数据库，直接回答）
            _GENERAL_PATTERNS = [
                r"你是谁", r"你是什么", r"自我介绍", r"你能做什么", r"你的功能",
                r"你好", r"hello", r"hi\b", r"hey\b", r"早上好", r"下午好", r"晚上好",
                r"谢谢", r"感谢", r"thank", r"拜拜", r"再见",
                r"帮助", r"怎么用", r"使用方法", r"help",
            ]
            q_lower = query.lower().strip()
            is_general = any(_re.search(p, q_lower) for p in _GENERAL_PATTERNS)
            # 如果问题很短（<10字符）且不含数据关键词，也视为通用
            data_keywords = ["收入", "订单", "客户", "销售", "类目", "支付", "配送", "卖家",
                             "复购", "rfm", "分群", "运费", "分期", "星期", "州", "生命周期",
                             "查询", "统计", "分析", "图表", "趋势", "排名", "top", "多少"]
            has_data_kw = any(kw in q_lower for kw in data_keywords)
            if is_general and not has_data_kw:
                general_answer = (
                    "我是电商数据分析助手，可以帮你：\n\n"
                    "- 📊 查询销售数据（月度收入、类目排名、城市分布等）\n"
                    "- 🔬 分析客户群体（RFM分群、复购分析、生命周期价值）\n"
                    "- 📈 生成可视化图表（柱状图、折线图、饼图等）\n"
                    "- 💬 回答数据分析相关问题\n\n"
                    "直接输入你想了解的数据问题即可，例如「月度收入趋势」「复购次数分布」。"
                )
                st.session_state.sql_agent_messages.append({
                    "role": "assistant", "content": general_answer
                })
                return

            # LLM Agent模式
            agent = st.session_state.get("sql_agent")
            if agent is None:
                st.session_state.sql_agent_messages.append({
                    "role": "assistant",
                    "content": "⚠️ SQL Agent未初始化。请检查侧边栏的API Key配置是否正确，以及数据库是否已初始化。"
                })
                return

            try:
                with st.spinner("AI正在分析你的问题..."):
                    with TimerContext("sql_llm_agent_invoke", self.perf):
                        response = agent.invoke({"input": query})
                    # 兼容不同返回格式
                    if isinstance(response, dict):
                        output = response.get("output", "")
                        if not output:
                            output = response.get("result", str(response))
                        # 从中间步骤提取Plotly图表数据 (鲁棒提取)
                        charts = []
                        preset_data = None
                        for step in response.get("intermediate_steps", []):
                            if len(step) >= 2:
                                action = step[0]
                                tool_output = step[1]
                                if isinstance(tool_output, str):
                                    try:
                                        fig_dict = _json.loads(tool_output)
                                        if "data" in fig_dict and "layout" in fig_dict:
                                            charts.append(tool_output)
                                        elif "data" in fig_dict and "description" in fig_dict:
                                            # preset_query返回的数据，保存用于后备可视化
                                            preset_data = fig_dict
                                    except (_json.JSONDecodeError, TypeError):
                                        pass
                    else:
                        output = str(response)
                        charts = []
                        preset_data = None

                    # 从output文本中提取可能嵌入的plotly JSON
                    if output:
                        json_pattern = _re.compile(r'\{"data"\s*:\s*\[.*?\]\s*,\s*"layout"\s*:\s*\{.*?\}\s*\}', _re.DOTALL)
                        for match in json_pattern.finditer(output):
                            try:
                                fig_dict = _json.loads(match.group())
                                if "data" in fig_dict and "layout" in fig_dict:
                                    charts.append(match.group())
                                    output = output[:match.start()].strip()
                            except (_json.JSONDecodeError, TypeError):
                                pass

                    # 后备：如果agent调用了preset_query但没有生成图表，自动可视化
                    if not charts and preset_data and "data" in preset_data:
                        try:
                            import agent_tools as _at
                            auto_fig = _at.auto_visualize.invoke(
                                {"data": _json.dumps(preset_data["data"]), "title": preset_data.get("description", "")}
                            )
                            auto_dict = _json.loads(auto_fig)
                            if "data" in auto_dict and "layout" in auto_dict:
                                charts.append(auto_fig)
                        except Exception as viz_err:
                            print(f"[WARN] 后备可视化失败: {viz_err}")

                    # 最终后备：如果agent返回了数据但没有图表，尝试从输出中提取数据并可视化
                    if not charts and output:
                        try:
                            import agent_tools as _at
                            # 尝试从output中提取JSON数据
                            data_pattern = _re.compile(r'\{[^{}]*"data"\s*:\s*\{[^{}]+\}\s*\}')
                            for match in data_pattern.finditer(output):
                                try:
                                    data_dict = _json.loads(match.group())
                                    if "data" in data_dict:
                                        auto_fig = _at.auto_visualize.invoke({
                                            "data": _json.dumps(data_dict["data"]),
                                            "title": data_dict.get("description", "")
                                        })
                                        auto_data = _json.loads(auto_fig)
                                        if "data" in auto_data and "layout" in auto_data:
                                            charts.append(auto_fig)
                                            break
                                except Exception:
                                    pass
                        except Exception:
                            pass

                    if not output or output.strip() == "":
                        output = "查询完成，已生成可视化图表。" if charts else "查询完成。"

                    st.session_state.sql_agent_messages.append({
                        "role": "assistant", "content": output, "charts": charts
                    })
            except Exception as e:
                err_str = str(e)
                if "rate" in err_str.lower() or "429" in err_str:
                    error_msg = "API请求频率超限，请稍后再试。"
                elif "auth" in err_str.lower() or "401" in err_str:
                    error_msg = "API Key无效或已过期，请检查侧边栏配置。"
                elif "timeout" in err_str.lower():
                    error_msg = "请求超时，查询可能过于复杂，请简化问题重试。"
                else:
                    error_msg = f"查询出错: {type(e).__name__}: {err_str[:200]}"
                st.session_state.sql_agent_messages.append({"role": "assistant", "content": f"[ERROR] {error_msg}"})

        # 示例查询按钮
        examples = [
            "月度收入趋势",
            "类目TOP10排名",
            "RFM客户分群概览",
            "配送绩效和延迟率",
        ]
        cols = st.columns(2)
        for i, ex in enumerate(examples):
            with cols[i % 2]:
                if st.button(ex, key=f"sql_ex_{i}", use_container_width=True):
                    log_user_action("click_example", f"SQL示例: {ex}")
                    process_sql_query(ex)
                    st.rerun()

        # 显示历史消息
        for msg in st.session_state.sql_agent_messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
                # 渲染Plotly图表
                for chart_json in msg.get("charts", []):
                    with TimerContext("sql_chart_render", self.perf):
                        try:
                            import plotly.io as pio
                            fig = pio.from_json(chart_json)
                            st.plotly_chart(fig, width="stretch")
                        except Exception as chart_err:
                            st.warning(f"图表渲染失败: {chart_err}")
                            try:
                                import json as _json
                                data = _json.loads(chart_json)
                                if "data" in data:
                                    st.json(data)
                            except Exception:
                                st.code(chart_json[:500])

        # 聊天输入
        if query := st.chat_input("用自然语言描述你想查询的数据...", key="sql_input"):
            log_user_action("sql_query", query)
            process_sql_query(query)
            st.rerun()

    def _render_rag_qa(self):
        """RAG知识库问答模式"""
        st.subheader("📚 RAG知识库问答")
        st.caption("基于分析报告的智能问答，支持自然语言查询分析结论")

        try:
            from rag.rag_engine import RAGEngine

            if "rag_engine" not in st.session_state:
                with st.spinner("正在初始化RAG引擎..."):
                    with TimerContext("rag_engine_init", self.perf):
                        st.session_state.rag_engine = RAGEngine()

            rag = st.session_state.rag_engine

            # 显示知识库状态
            status = rag.get_status()
            doc_count = status['document_count']

            # 自动索引：如果知识库为空但有报告文件，自动索引
            if doc_count == 0:
                from config import REPORTS_DIR
                report_files = list(REPORTS_DIR.glob("*.md")) if REPORTS_DIR.exists() else []
                if report_files:
                    with st.spinner("⏳ 首次使用，正在自动索引知识库..."):
                        count = rag.index_documents()
                        if count > 0:
                            st.success(f"✅ 知识库已自动索引 {count} 个文档块。")
                            doc_count = count
                            st.rerun()
                        else:
                            st.warning("索引失败，请手动点击下方按钮重试。")
                else:
                    st.warning("知识库为空！请先切换到 **ETL管理** 标签页执行ETL Pipeline。")
            else:
                st.info(f"📚 知识库状态: {doc_count} 篇文档已索引")

            # 索引按钮
            col_idx1, col_idx2 = st.columns([3, 1])
            with col_idx2:
                if st.button("🔄 重建索引", key="reindex_rag"):
                    log_user_action("click", "重建RAG索引")
                    with st.spinner("正在重新索引文档..."):
                        count = rag.index_documents()
                        if count > 0:
                            st.success(f"✅ 索引更新完成！已索引 {count} 个文档块。")
                        else:
                            st.warning("没有找到可索引的文档。请先执行ETL Pipeline生成分析报告。")
                        st.rerun()

            # 处理RAG查询的辅助函数
            def process_rag_query(query: str):
                if "rag_messages" not in st.session_state:
                    st.session_state.rag_messages = []
                st.session_state.rag_messages.append({"role": "user", "content": query})

                # 刷新知识库状态
                current_status = rag.get_status()
                current_doc_count = current_status['document_count']

                if current_doc_count == 0:
                    st.session_state.rag_messages.append({
                        "role": "assistant",
                        "content": "⚠️ 知识库为空。请先切换到 **ETL管理** 标签页执行ETL Pipeline，然后回到此页面重试。"
                    })
                    return

                try:
                    with st.spinner("🔍 正在检索知识库并生成回答..."):
                        with TimerContext("rag_query_total", self.perf):
                            answer = rag.query(query)
                        st.session_state.rag_messages.append({"role": "assistant", "content": answer})
                except Exception as e:
                    err_str = str(e)
                    if "rate" in err_str.lower() or "429" in err_str:
                        error_msg = "API请求频率超限，请稍后再试。"
                    elif "auth" in err_str.lower() or "401" in err_str:
                        error_msg = "API Key无效或已过期，请检查侧边栏配置。"
                    elif "timeout" in err_str.lower():
                        error_msg = "请求超时，请稍后重试。"
                    else:
                        error_msg = f"RAG查询出错: {type(e).__name__}: {err_str[:200]}"
                    st.session_state.rag_messages.append({"role": "assistant", "content": f"❌ {error_msg}"})

            # 示例问题按钮
            examples = [
                "哪些用户需要挽留？",
                "高价值用户的特征是什么？",
                "各类目销售情况如何？",
                "客户的购买频率分布是怎样的？",
            ]
            cols = st.columns(2)
            for i, ex in enumerate(examples):
                with cols[i % 2]:
                    if st.button(ex, key=f"rag_ex_{i}", use_container_width=True):
                        log_user_action("click_example", f"RAG示例: {ex}")
                        process_rag_query(ex)
                        st.rerun()

            # 聊天
            if "rag_messages" not in st.session_state:
                st.session_state.rag_messages = []

            # 清除聊天按钮
            if st.session_state.rag_messages:
                if st.button("清除对话", key="clear_rag_chat"):
                    log_user_action("click", "清除对话(RAG)")
                    st.session_state.rag_messages = []
                    st.rerun()

            for msg in st.session_state.rag_messages:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])

            if query := st.chat_input("基于分析报告提问...", key="rag_input"):
                log_user_action("rag_query", query)
                process_rag_query(query)
                st.rerun()

        except ImportError as e:
            st.error(f"RAG模块加载失败: {e}")
            st.info("请确保已安装所有依赖: pip install chromadb langchain-chroma")
        except Exception as e:
            st.error(f"RAG引擎初始化失败: {type(e).__name__}: {str(e)}")
            st.info("请检查API Key配置和网络连接。")

    def render_etl(self):
        """Tab4 - ETL管理"""
        st.header("⚙️ ETL管理")

        # 数据库状态
        st.subheader("📊 数据库状态")
        try:
            tables = self._query("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            stats = []
            for _, row in tables.iterrows():
                table_name = row["name"]
                count = self._query(f"SELECT COUNT(*) as cnt FROM {table_name}")
                stats.append({"表名": table_name, "记录数": f"{count['cnt'].iloc[0]:,}"})
            st.dataframe(pd.DataFrame(stats), width="stretch")

            # 数据导出
            st.subheader("📥 快速导出")
            export_table = st.selectbox("选择要导出的表", tables["name"].tolist(), key="export_table")
            if st.button("导出为CSV", key="btn_export_csv"):
                log_user_action("click", f"导出CSV: {export_table}")
                export_df = self._query(f"SELECT * FROM {export_table}")
                csv_bytes = export_df.to_csv(index=False).encode("utf-8-sig")
                st.download_button(f"下载 {export_table}.csv", csv_bytes,
                                   f"{export_table}.csv", "text/csv", key="dl_etl_export")
                st.success(f"已准备 {len(export_df):,} 条记录")

        except Exception as e:
            st.error(f"无法读取数据库: {e}")

        st.divider()

        # 数据刷新
        st.subheader("🔄 数据刷新")

        # 检查是否使用CSV数据
        from config import USE_CSV_DATA
        if USE_CSV_DATA:
            st.info("📊 当前使用 **Olist真实数据集** (99K客户, 98K订单)")
        else:
            st.info("📊 当前使用 **模拟数据**")
            col1, col2 = st.columns(2)
            with col1:
                n_customers = st.number_input("客户数量", min_value=100, max_value=50000, value=5000)
                n_orders = st.number_input("订单数量", min_value=100, max_value=100000, value=12000)
            with col2:
                n_products = st.number_input("商品数量", min_value=50, max_value=10000, value=2000)
                n_sellers = st.number_input("卖家数量", min_value=50, max_value=5000, value=500)

        if st.button("🚀 执行ETL Pipeline", type="primary", use_container_width=True):
            log_user_action("click", "执行ETL Pipeline")
            try:
                from etl.pipeline import ETLPipeline

                # Step 1: ETL
                with st.spinner("⏳ [1/4] 正在执行ETL数据管道..."):
                    with TimerContext("etl_pipeline", self.perf):
                        pipeline = ETLPipeline()
                        if USE_CSV_DATA:
                            pipeline.run()
                        else:
                            pipeline.run(
                                n_customers=n_customers,
                                n_orders=n_orders,
                                n_products=n_products,
                                n_sellers=n_sellers,
                            )
                st.success("✅ ETL执行完成！")

                # Step 2: RFM分析
                with st.spinner("⏳ [2/4] 正在运行RFM客户分析..."):
                    with TimerContext("etl_rfm_analysis", self.perf):
                        from analysis.rfm_engine import RFMEngine
                        rfm_engine = RFMEngine()
                        rfm_engine.run()
                st.success("✅ RFM分析完成！")

                # Step 3: 聚类分析
                with st.spinner("⏳ [3/4] 正在运行KMeans聚类..."):
                    with TimerContext("etl_clustering", self.perf):
                        from analysis.clustering import RFMClustering
                        clustering = RFMClustering()
                        clustering.cluster()
                st.success("✅ 聚类分析完成！")

                # Step 4: 报告生成
                with st.spinner("⏳ [4/4] 正在生成分析报告..."):
                    with TimerContext("etl_report_generation", self.perf):
                        from analysis.report_generator import ReportGenerator
                        generator = ReportGenerator()
                        generator.generate_all_reports()
                st.success("✅ 报告生成完成！")

                # 自动触发RAG索引
                with st.spinner("⏳ 正在更新RAG知识库索引..."):
                    try:
                        with TimerContext("etl_rag_indexing", self.perf):
                            from rag.rag_engine import RAGEngine
                            rag = RAGEngine()
                            count = rag.index_documents()
                        if count > 0:
                            st.success(f"✅ RAG知识库已更新，索引了 {count} 个文档块。")
                        # 清除缓存的RAG引擎，下次使用时会重新初始化
                        if "rag_engine" in st.session_state:
                            del st.session_state["rag_engine"]
                    except Exception as rag_e:
                        st.warning(f"⚠️ RAG索引更新失败（不影响数据使用）: {rag_e}")

                st.balloons()
                st.info("🔄 请刷新页面查看最新数据。")
            except Exception as e:
                st.error(f"❌ ETL执行失败: {e}")
                import traceback
                st.code(traceback.format_exc())

        st.divider()

        # 执行日志
        st.subheader("📝 最近的分析报告")
        try:
            reports = self._query("""
                SELECT report_type, title, created_at
                FROM analysis_reports
                ORDER BY created_at DESC
                LIMIT 10
            """)
            if not reports.empty:
                st.dataframe(reports, width="stretch")
            else:
                st.info("暂无报告")
        except Exception:
            st.info("暂无报告")

        # 性能日志查看器
        st.divider()
        st.subheader("⏱️ Performance Log")
        log_lines = read_recent_logs(n=50)
        if log_lines:
            log_text = "\n".join(log_lines)
            st.code(log_text, language=None)
        else:
            st.info("暂无性能日志。执行ETL或查询操作后将自动记录。")

    def _get_kpis(self) -> list:
        """获取KPI指标"""
        return self._get_kpis_filtered("")

    def _get_kpis_filtered(self, date_filter: str) -> list:
        """获取KPI指标（带日期筛选）"""
        kpis = []
        try:
            # 总客户数（不受日期筛选影响）
            r = self._query("SELECT COUNT(DISTINCT customer_id) as cnt FROM customers")
            kpis.append(("总客户数", f"{r['cnt'].iloc[0]:,}", None))

            # 完成订单数
            r = self._query(f"SELECT COUNT(*) as cnt FROM orders WHERE order_status='delivered' {date_filter}")
            kpis.append(("完成订单数", f"{r['cnt'].iloc[0]:,}", None))

            # 总销售额
            r = self._query(f"""
                SELECT SUM(op.payment_value) as total
                FROM order_payments op
                JOIN orders o ON op.order_id = o.order_id
                WHERE o.order_status = 'delivered' {date_filter}
            """)
            total = r['total'].iloc[0] or 0
            kpis.append(("总销售额 (R$)", f"{total:,.2f}", None))

            # 平均客单价
            r = self._query(f"""
                SELECT AVG(total) as avg_val FROM (
                    SELECT SUM(op.payment_value) as total
                    FROM order_payments op
                    JOIN orders o ON op.order_id = o.order_id
                    WHERE o.order_status = 'delivered' {date_filter}
                    GROUP BY o.customer_id
                )
            """)
            avg = r['avg_val'].iloc[0] or 0
            kpis.append(("平均客单价 (R$)", f"{avg:,.2f}", None))

        except Exception:
            kpis = [
                ("总客户数", "N/A", None),
                ("完成订单数", "N/A", None),
                ("总销售额 (R$)", "N/A", None),
                ("平均客单价 (R$)", "N/A", None),
            ]

        return kpis
