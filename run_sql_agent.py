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
                   agent_tools.output_table, agent_tools.output_pie_plot]
    prefix = """你是一个电商数据智能分析助手。你可以查询SQLite数据库中的电商数据，也可以用可视化工具生成图表。

规则：
- 如果用户的问题可以通过查询数据库回答，请先查询数据库再回答
- 如果用户问的是与数据库无关的通用问题（如"你是谁"、"你好"等），请直接回答，不需要查询数据库
- 如果用户要求可视化，请使用可视化工具（output_bar_plot、output_time_series_plot、output_pie_plot、output_table）生成图表
- 可视化工具接受JSON字符串或字典格式的数据，例如 {"月份": ["1月","2月"], "数量": [100, 200]}"""
    return create_sql_agent(
        llm, db=db, agent_type="tool-calling",
        max_iterations=agent_max_iterations,
        max_execution_time=agent_max_execution_time,
        extra_tools=extra_tools, verbose=True,
        prefix=prefix,
    )


if __name__ == '__main__':
    db = load_sql_database()
    print("数据库表:", db.get_usable_table_names())

    llm = load_llm()
    sql_agent = load_sql_agent(db, llm)

    # 测试查询
    test_queries = [
        "每个城市的客户数量是多少？用柱状图展示",
        "各类目的商品平均价格是多少？",
        "最近30天销量前10的商品是哪些？",
        "各VIP等级客户的平均消费金额对比",
    ]
    for query in test_queries:
        print(f"\n{'='*60}")
        print(f"问题: {query}")
        print(f"{'='*60}")
        answer = sql_agent.invoke({"input": query})["output"]
        print(answer)
