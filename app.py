"""
电商数据智能分析平台 - 主入口
融合ETL、RFM分析、交互式仪表盘、RAG问答四大模块
"""
import os
import sys
import json
import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st
import plotly.graph_objects as go

# 确保项目根目录在path中
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import (
    siliconflow_api_key, llm_base_url, llm_model_id, llm_temperature,
    agent_max_execution_time, agent_max_iterations, database_url, DB_PATH
)

# ──────────────────────────────────────────────
# 页面配置
# ──────────────────────────────────────────────
st.set_page_config(
    page_title="电商数据智能分析平台",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定义CSS
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        padding: 1rem 2rem;
        border-radius: 10px;
        margin-bottom: 1rem;
    }
    .main-header h1 {
        color: white;
        margin: 0;
        font-size: 1.8rem;
    }
    .main-header p {
        color: rgba(255,255,255,0.8);
        margin: 0;
        font-size: 0.9rem;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 10px 20px;
        border-radius: 5px;
    }
</style>
""", unsafe_allow_html=True)


# ──────────────────────────────────────────────
# 侧边栏
# ──────────────────────────────────────────────
def render_sidebar():
    with st.sidebar:
        st.header("⚙️ 系统配置")

        api_key = st.text_input(
            "SiliconFlow API Key",
            value=siliconflow_api_key,
            type="password",
            help="在 https://cloud.siliconflow.cn 获取"
        )

        model = st.selectbox(
            "选择模型",
            ["Qwen/Qwen3-8B", "Qwen/Qwen2.5-7B-Instruct",
             "deepseek-ai/DeepSeek-V3", "Qwen/Qwen3-32B",
             "Pro/deepseek-ai/DeepSeek-R1"],
            index=0
        )

        st.divider()

        # 数据库信息
        st.header("📊 数据库信息")
        db_path = str(DB_PATH)
        if os.path.exists(db_path):
            db_size = os.path.getsize(db_path) / (1024 * 1024)
            st.metric("数据库大小", f"{db_size:.1f} MB")

            try:
                conn = sqlite3.connect(db_path)
                tables = pd.read_sql_query(
                    "SELECT name FROM sqlite_master WHERE type='table'", conn
                )
                conn.close()
                st.write(f"**数据表:** {len(tables)} 个")
            except Exception:
                pass
        else:
            st.warning("数据库未初始化")
            st.info("请在ETL管理标签页执行数据刷新")

        st.divider()

        # 系统状态
        st.header("🔧 系统状态")
        st.write(f"**LLM模型:** {model}")
        st.write(f"**数据库:** {'✅ 就绪' if os.path.exists(db_path) else '❌ 未初始化'}")

        # 检查RFM数据
        try:
            conn = sqlite3.connect(db_path)
            rfm_count = pd.read_sql_query(
                "SELECT COUNT(*) as cnt FROM rfm_results", conn
            )['cnt'].iloc[0]
            conn.close()
            st.write(f"**RFM分析:** {'✅ ' + str(rfm_count) + ' 条' if rfm_count > 0 else '❌ 未运行'}")
        except Exception:
            st.write("**RFM分析:** ❌ 未运行")

        return api_key, model


# ──────────────────────────────────────────────
# 初始化SQL Agent (带缓存)
# ──────────────────────────────────────────────
@st.cache_resource
def init_db(db_url):
    from langchain_community.utilities import SQLDatabase
    from sqlalchemy import create_engine
    engine = create_engine(db_url)
    return SQLDatabase(engine=engine)


@st.cache_resource
def init_llm(key, model_id):
    from langchain_openai import ChatOpenAI
    # Qwen3模型需要关闭thinking模式，否则openai-tools agent返回空结果
    extra_kwargs = {}
    if "Qwen3" in model_id:
        extra_kwargs["extra_body"] = {"enable_thinking": False}
    return ChatOpenAI(
        model=model_id,
        temperature=llm_temperature,
        openai_api_base=llm_base_url,
        openai_api_key=key,
        **extra_kwargs,
    )


@st.cache_resource
def init_sql_agent(_db, _llm):
    import agent_tools
    from langchain_community.agent_toolkits import create_sql_agent

    extra_tools = [
        agent_tools.output_bar_plot,
        agent_tools.output_time_series_plot,
        agent_tools.output_table,
        agent_tools.output_pie_plot,
    ]
    prefix = """你是一个电商数据智能分析助手。你可以查询SQLite数据库中的电商数据，也可以用可视化工具生成图表。

规则：
- 如果用户的问题可以通过查询数据库回答，请先查询数据库再回答
- 如果用户问的是与数据库无关的通用问题（如"你是谁"、"你好"等），请直接回答，不需要查询数据库
- 如果用户要求可视化，请使用可视化工具（output_bar_plot、output_time_series_plot、output_pie_plot、output_table）生成图表
- 可视化工具接受JSON字符串或字典格式的数据，例如 {{"月份": ["1月","2月"], "数量": [100, 200]}}"""
    return create_sql_agent(
        _llm, db=_db, agent_type="tool-calling",
        max_iterations=agent_max_iterations,
        max_execution_time=agent_max_execution_time,
        extra_tools=extra_tools, verbose=True,
        prefix=prefix,
    )


# ──────────────────────────────────────────────
# 主页面
# ──────────────────────────────────────────────
def main():
    # 标题
    st.markdown("""
    <div class="main-header">
        <h1>📊 电商数据智能分析平台</h1>
        <p>融合 ETL管道 + RFM分析 + 数据仪表盘 + RAG知识库问答 | 基于 LangChain + SiliconFlow LLM</p>
    </div>
    """, unsafe_allow_html=True)

    # 侧边栏
    api_key, model = render_sidebar()

    # 初始化SQL Agent
    sql_agent = None
    if api_key and os.path.exists(str(DB_PATH)):
        try:
            db = init_db(database_url)
            llm = init_llm(api_key, model)
            sql_agent = init_sql_agent(db, llm)
            st.session_state["sql_agent"] = sql_agent
        except Exception as e:
            st.sidebar.error(f"Agent初始化失败: {e}")

    # 检查数据库是否初始化
    if not os.path.exists(str(DB_PATH)):
        st.warning("⚠️ 数据库未初始化，请先执行ETL Pipeline生成数据。")
        st.info("👉 点击上方 **ETL管理** 标签页，然后点击 **执行ETL Pipeline** 按钮。")

    # 四个标签页
    from dashboard.tabs import TabRenderer
    renderer = TabRenderer()

    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 数据概览", "🔬 RFM分析", "💬 智能问答", "⚙️ ETL管理"
    ])

    with tab1:
        renderer.render_overview()

    with tab2:
        renderer.render_rfm()

    with tab3:
        renderer.render_qa()

    with tab4:
        renderer.render_etl()

    # 页脚
    st.divider()
    st.caption("💡 电商数据智能分析平台 | ETL + RFM + Dashboard + RAG | Powered by LangChain + SiliconFlow")


if __name__ == "__main__":
    main()
