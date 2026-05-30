# 智能SQL查询助手 🤖

基于 LangChain + SiliconFlow LLM 的自然语言转SQL查询工具，支持中文问答、自动可视化。

用户输入自然语言问题 → AI自动生成SQL → 执行查询 → 返回结果 + Plotly图表

## ✨ 功能特性

- **自然语言转SQL**：用中文描述需求，自动生成SQL查询语句
- **智能可视化**：根据数据类型自动选择柱状图/折线图/饼图/表格
- **多表关联查询**：支持跨表JOIN、子查询等复杂SQL操作
- **对话式交互**：支持多轮对话，上下文记忆
- **数据库探索**：自动展示表结构，帮助理解数据
- **多模型支持**：支持Qwen、DeepSeek等多种LLM

## 🏗️ 技术架构

```
用户输入 (自然语言)
    │
    ▼
┌─────────────────────┐
│   Streamlit 前端     │
│   (app.py)          │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  LangChain Agent    │
│  ┌───────────────┐  │
│  │ Prompt 模板    │  │    ┌──────────────┐
│  │ (中文优化)     │──┼───▶│ SiliconFlow  │
│  └───────────────┘  │    │ LLM (Qwen3)  │
│  ┌───────────────┐  │    └──────────────┘
│  │ SQL 工具       │  │
│  │ 可视化工具     │  │
│  └───────────────┘  │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  SQLite / MySQL     │
│  (电商演示数据)      │
└─────────────────────┘
```

## 📊 演示数据库

内置电商数据集（运行 `setup_db.py` 自动生成）：

| 表名 | 说明 | 数据量 |
|------|------|--------|
| customers | 客户信息 | 500条 |
| categories | 商品类目 | 12个 |
| products | 商品信息 | 96个 |
| orders | 订单记录 | ~2500条 |
| order_items | 订单明细 | ~6000条 |
| reviews | 商品评价 | ~1000条 |

## 🚀 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/your-username/sql-assistant.git
cd sql-assistant
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置API Key

在 `.env` 文件中填入你的 SiliconFlow API Key：

```
SILICONFLOW_API_KEY=sk-xxxxxxxxxxxxxxxx
```

> 在 [SiliconFlow](https://cloud.siliconflow.cn) 免费注册获取 API Key

### 4. 生成演示数据库

```bash
python setup_db.py
```

### 5. 启动应用

```bash
streamlit run app.py
```

浏览器自动打开 http://localhost:8501

## 💬 示例问题

```
分析类
- 各类目的商品平均价格排名
- 各VIP等级客户的平均消费金额对比
- 男性和女性客户的消费差异

趋势类
- 每月订单数量趋势
- 最近30天的销售额变化

排名类
- 销量前10的商品及销售数量
- 评分最高的5个商品

探索类
- 哪个城市的客户最多
- 各支付方式的使用占比
```

## 📁 项目结构

```
sql-assistant/
├── app.py              # Streamlit 主界面
├── run_sql_agent.py    # 命令行版本
├── agent_tools.py      # 自定义可视化工具 (Plotly)
├── config.py           # 配置文件
├── setup_db.py         # 数据库初始化脚本
├── requirements.txt    # Python 依赖
├── .env                # API Key (不提交到Git)
├── .gitignore
├── README.md
└── data/
    └── ecommerce.db    # SQLite 数据库 (自动生成)
```

## 🔧 技术栈

| 组件 | 技术 |
|------|------|
| LLM | SiliconFlow (Qwen3-8B / DeepSeek-V3) |
| Agent框架 | LangChain |
| 前端 | Streamlit |
| 数据库 | SQLite / SQLAlchemy |
| 可视化 | Plotly |
| 语言 | Python 3.10+ |

## 📝 说明

- 本项目为数据科学与大数据技术专业课程项目
- 基于开源项目 [LangChain-SQL-Agent-for-dynamic-data-visualization](https://github.com/EliasK93/LangChain-SQL-Agent-for-dynamic-data-visualization) 改造
- 主要改进：接入国产LLM、中文界面、Streamlit Web化、电商数据集、新增饼图工具

## License

MIT
