"""
标签页渲染器 - 仪表盘各标签页内容
"""
import sqlite3
from datetime import datetime

import pandas as pd
import streamlit as st

from .charts import ChartFactory
from config import DB_PATH


class TabRenderer:
    """仪表盘标签页渲染器"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(DB_PATH)
        self.charts = ChartFactory()

    def _query(self, sql: str, params=None) -> pd.DataFrame:
        """执行SQL查询"""
        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql_query(sql, conn, params=params)
        conn.close()
        return df

    def render_overview(self):
        """Tab1 - 数据概览"""
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

        # 销售趋势
        col1, col2 = st.columns(2)

        with col1:
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
                fig = self.charts.line(monthly, "month", "revenue", "月度销售趋势 (R$)")
                st.plotly_chart(fig, width="stretch")
                st.download_button("下载月度数据 CSV", monthly.to_csv(index=False).encode("utf-8-sig"),
                                   "monthly_sales.csv", "text/csv", key="dl_monthly")

        with col2:
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
                fig = self.charts.pie(categories, "category", "revenue", "类目销售占比")
                st.plotly_chart(fig, width="stretch")
                st.download_button("下载类目数据 CSV", categories.to_csv(index=False).encode("utf-8-sig"),
                                   "category_sales.csv", "text/csv", key="dl_cat")

        # 地域分布和支付方式
        col3, col4 = st.columns(2)

        with col3:
            geo = self._query("""
                SELECT customer_state, COUNT(*) as count
                FROM customers GROUP BY customer_state
                ORDER BY count DESC LIMIT 10
            """)
            if not geo.empty:
                fig = self.charts.bar(geo, "customer_state", "count", "客户地域分布 TOP10")
                st.plotly_chart(fig, width="stretch")

        with col4:
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
        st.header("🔬 RFM客户分析")

        rfm = self._query("SELECT * FROM rfm_results")
        if rfm.empty:
            st.warning("暂无RFM数据，请先运行ETL和RFM分析。")
            return

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

        # 3D散点图
        col1, col2 = st.columns(2)

        with col1:
            fig = self.charts.scatter_3d(
                rfm, "recency", "frequency", "monetary",
                color="segment", title="RFM 3D散点图"
            )
            st.plotly_chart(fig, width="stretch")

        with col2:
            segment_counts = rfm["segment"].value_counts().reset_index()
            segment_counts.columns = ["segment", "count"]
            fig = self.charts.pie(segment_counts, "segment", "count", "客户分群占比")
            st.plotly_chart(fig, width="stretch")

        # 箱线图和雷达图
        col3, col4 = st.columns(2)

        with col3:
            fig = self.charts.box(rfm, "segment", "monetary", "各群体消费分布")
            st.plotly_chart(fig, width="stretch")

        with col4:
            # 雷达图 - 各群体RFM均值
            segments = rfm["segment"].unique()
            if len(segments) > 0:
                selected = st.selectbox("选择群体查看雷达图", segments, key="radar_seg")
                seg_data = rfm[rfm["segment"] == selected]
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

        # 营销策略建议
        st.subheader("📋 营销策略建议")
        strategy_data = []
        for segment in rfm["segment"].unique():
            seg_df = rfm[rfm["segment"] == segment]
            strategy_data.append({
                "分群": segment,
                "人数": len(seg_df),
                "占比": f"{len(seg_df)/len(rfm)*100:.1f}%",
                "平均Recency": f"{seg_df['recency'].mean():.0f}天",
                "平均Frequency": f"{seg_df['frequency'].mean():.1f}次",
                "平均Monetary": f"R${seg_df['monetary'].mean():.2f}",
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
                st.session_state.sql_agent_messages = []
                st.rerun()

        # 处理查询的辅助函数
        def process_sql_query(query: str):
            import json as _json
            agent = st.session_state.get("sql_agent")
            st.session_state.sql_agent_messages.append({"role": "user", "content": query})

            if agent is None:
                st.session_state.sql_agent_messages.append({
                    "role": "assistant",
                    "content": "⚠️ SQL Agent未初始化。请检查侧边栏的API Key配置是否正确，以及数据库是否已初始化。"
                })
                return

            try:
                with st.spinner("AI正在分析你的问题，生成SQL查询..."):
                    response = agent.invoke({"input": query})
                    # 兼容不同返回格式
                    if isinstance(response, dict):
                        output = response.get("output", "")
                        if not output:
                            output = response.get("result", str(response))
                        # 从中间步骤提取Plotly图表数据
                        charts = []
                        for step in response.get("intermediate_steps", []):
                            if len(step) >= 2:
                                tool_output = step[1]
                                if isinstance(tool_output, str) and tool_output.startswith('{"data"'):
                                    try:
                                        fig_dict = _json.loads(tool_output)
                                        if "data" in fig_dict:
                                            charts.append(tool_output)
                                    except (_json.JSONDecodeError, TypeError):
                                        pass
                    else:
                        output = str(response)
                        charts = []

                    if not output or output.strip() == "":
                        output = "⚠️ Agent返回了空结果。可能是模型不支持工具调用，请尝试更换模型。"

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
            "每个城市的客户数量是多少？",
            "各类目的商品平均价格排名",
            "月度订单数量趋势",
            "评分最高的5个商品",
        ]
        cols = st.columns(2)
        for i, ex in enumerate(examples):
            with cols[i % 2]:
                if st.button(ex, key=f"sql_ex_{i}", use_container_width=True):
                    process_sql_query(ex)
                    st.rerun()

        # 显示历史消息
        for msg in st.session_state.sql_agent_messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
                # 渲染Plotly图表
                for chart_json in msg.get("charts", []):
                    try:
                        import plotly.io as pio
                        fig = pio.from_json(chart_json)
                        st.plotly_chart(fig, width="stretch")
                    except Exception:
                        pass

        # 聊天输入
        if query := st.chat_input("用自然语言描述你想查询的数据...", key="sql_input"):
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
                    st.session_state.rag_engine = RAGEngine()

            rag = st.session_state.rag_engine

            # 显示知识库状态
            status = rag.get_status()
            doc_count = status['document_count']

            if doc_count == 0:
                st.warning("知识库为空！请先执行以下步骤：")
                st.markdown("""
                1. 切换到 **ETL管理** 标签页
                2. 点击 **执行ETL Pipeline** 按钮
                3. 等待ETL和报告生成完成
                4. 回到此页面，点击下方 **更新知识库索引** 按钮
                """)
            else:
                st.info(f"知识库状态: {doc_count} 篇文档已索引")

            # 索引按钮
            if st.button("更新知识库索引", key="reindex_rag"):
                with st.spinner("正在重新索引文档..."):
                    count = rag.index_documents()
                    if count > 0:
                        st.success(f"索引更新完成！已索引 {count} 个文档块。")
                    else:
                        st.warning("没有找到可索引的文档。请先执行ETL Pipeline生成分析报告。")
                    st.rerun()

            # 处理RAG查询的辅助函数
            def process_rag_query(query: str):
                if "rag_messages" not in st.session_state:
                    st.session_state.rag_messages = []
                st.session_state.rag_messages.append({"role": "user", "content": query})

                if doc_count == 0:
                    st.session_state.rag_messages.append({
                        "role": "assistant",
                        "content": "知识库为空，请先执行ETL Pipeline生成分析报告，然后点击「更新知识库索引」按钮。"
                    })
                    return

                try:
                    with st.spinner("正在检索知识库并生成回答..."):
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
                    st.session_state.rag_messages.append({"role": "assistant", "content": f"[ERROR] {error_msg}"})

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
                        process_rag_query(ex)
                        st.rerun()

            # 聊天
            if "rag_messages" not in st.session_state:
                st.session_state.rag_messages = []

            # 清除聊天按钮
            if st.session_state.rag_messages:
                if st.button("清除对话", key="clear_rag_chat"):
                    st.session_state.rag_messages = []
                    st.rerun()

            for msg in st.session_state.rag_messages:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])

            if query := st.chat_input("基于分析报告提问...", key="rag_input"):
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
        col1, col2 = st.columns(2)

        with col1:
            n_customers = st.number_input("客户数量", min_value=100, max_value=50000, value=5000)
            n_orders = st.number_input("订单数量", min_value=100, max_value=100000, value=12000)

        with col2:
            n_products = st.number_input("商品数量", min_value=50, max_value=10000, value=2000)
            n_sellers = st.number_input("卖家数量", min_value=50, max_value=5000, value=500)

        if st.button("🚀 执行ETL Pipeline", type="primary", use_container_width=True):
            with st.spinner("正在执行ETL..."):
                try:
                    from etl.pipeline import ETLPipeline
                    pipeline = ETLPipeline()
                    pipeline.run(
                        n_customers=n_customers,
                        n_orders=n_orders,
                        n_products=n_products,
                        n_sellers=n_sellers,
                    )
                    st.success("ETL执行完成！")

                    # 自动运行RFM分析
                    with st.spinner("正在运行RFM分析..."):
                        from analysis.rfm_engine import RFMEngine
                        from analysis.clustering import RFMClustering
                        from analysis.report_generator import ReportGenerator

                        rfm_engine = RFMEngine()
                        rfm_engine.run()

                        clustering = RFMClustering()
                        clustering.cluster()

                        generator = ReportGenerator()
                        generator.generate_all_reports()

                    st.success("RFM分析和报告生成完成！")

                    # 自动触发RAG索引
                    with st.spinner("正在更新RAG知识库索引..."):
                        try:
                            from rag.rag_engine import RAGEngine
                            rag = RAGEngine()
                            count = rag.index_documents()
                            if count > 0:
                                st.success(f"RAG知识库已更新，索引了 {count} 个文档块。")
                            # 清除缓存的RAG引擎，下次使用时会重新初始化
                            if "rag_engine" in st.session_state:
                                del st.session_state["rag_engine"]
                        except Exception as rag_e:
                            st.warning(f"RAG索引更新失败（不影响数据使用）: {rag_e}")

                    st.info("请刷新页面查看最新数据。")
                except Exception as e:
                    st.error(f"ETL执行失败: {e}")
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
