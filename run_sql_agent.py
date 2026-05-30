import os
from langchain_community.utilities import SQLDatabase
from langchain_openai import ChatOpenAI
from langchain_community.agent_toolkits import create_sql_agent
from sqlalchemy import create_engine
import agent_tools
from config import (
    siliconflow_api_key, llm_base_url, llm_model_id, llm_temperature,
    agent_max_execution_time, agent_max_iterations, database_url
)
from utils.timing import get_perf_logger, TimerContext

perf = get_perf_logger()


def load_sql_database() -> SQLDatabase:
    """加载 SQLite 电商数据库"""
    engine = create_engine(database_url)
    return SQLDatabase(engine=engine)


def load_llm() -> ChatOpenAI:
    """加载 SiliconFlow LLM (OpenAI 兼容接口)"""
    extra_kwargs = {}
    if "Qwen3" in llm_model_id:
        extra_kwargs["extra_body"] = {"enable_thinking": False}
    return ChatOpenAI(
        model=llm_model_id,
        temperature=llm_temperature,
        openai_api_base=llm_base_url,
        openai_api_key=siliconflow_api_key,
        **extra_kwargs,
    )


def load_sql_agent(db: SQLDatabase, llm: ChatOpenAI):
    """创建 LangChain SQL Agent"""
    extra_tools = [agent_tools.output_bar_plot, agent_tools.output_time_series_plot,
                   agent_tools.output_table, agent_tools.output_pie_plot,
                   agent_tools.preset_query, agent_tools.auto_visualize,
                   agent_tools.query_and_visualize]
    prefix = """你是电商数据分析助手。

【严格规则】
- 通用问题（自我介绍、闲聊、问候、能力说明）：直接用文字回答，禁止调用任何工具
- 数据分析问题（涉及具体数据查询、图表生成）：才调用工具

数据查询可用: monthly_revenue, category_top10, city_distribution, payment_analysis, delivery_performance, review_correlation, seller_top10, repeat_purchase, rfm_summary, order_status, freight_analysis, installment_analysis, weekday_orders, state_revenue, customer_lifetime
消费频率/购买次数/复购 → repeat_purchase
如果没有匹配的预置查询，用SQL+auto_visualize
回答必须包含具体数字，不能只给定性描述"""
    return create_sql_agent(
        llm, db=db, agent_type="tool-calling",
        max_iterations=agent_max_iterations,
        max_execution_time=agent_max_execution_time,
        extra_tools=extra_tools, verbose=True,
        prefix=prefix,
    )


if __name__ == '__main__':
    with TimerContext("cli_load_db", perf):
        db = load_sql_database()
    print("数据库表:", db.get_usable_table_names())

    with TimerContext("cli_load_llm", perf):
        llm = load_llm()

    with TimerContext("cli_load_agent", perf):
        sql_agent = load_sql_agent(db, llm)

    # 测试查询
    test_queries = [
        "每个城市的客户数量是多少？用柱状图展示",
        "各类目的商品平均价格是多少？",
        "用preset_query查看月度收入趋势",
        "用preset_query查看RFM分群概览",
    ]
    for i, query in enumerate(test_queries):
        print(f"\n{'='*60}")
        print(f"问题: {query}")
        print(f"{'='*60}")
        with TimerContext(f"cli_query_{i}", perf):
            answer = sql_agent.invoke({"input": query})["output"]
        print(answer)
