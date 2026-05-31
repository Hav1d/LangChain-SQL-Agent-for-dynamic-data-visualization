# E-Commerce Data Intelligence Platform

> [中文版本](#电商平台智能数据分析平台)

An end-to-end e-commerce analytics platform combining ETL pipelines, RFM customer segmentation, interactive dashboards, and RAG-powered Q&A — all driven by LangChain agents and SiliconFlow LLMs.

**Natural language in → SQL + Charts + Insights out.**

## Features

- **SQL Agent** — Ask questions in natural language, get auto-generated SQL queries and Plotly visualizations
- **ETL Pipeline** — Automated data collection, cleaning, feature engineering, and loading (supports Olist real dataset or synthetic data)
- **RFM Analysis** — Customer segmentation with KMeans clustering, 10-segment classification, and marketing strategy recommendations
- **Interactive Dashboard** — 4-tab Streamlit UI: data overview, RFM deep-dive, intelligent Q&A, and ETL management
- **RAG Knowledge Base** — Ask questions against generated analysis reports using RAG-Fusion with RRF ranking
- **Performance Instrumentation** — Full-chain timing logs and user action tracking for optimization

## Architecture

```
User Input (Natural Language)
    │
    ▼
┌──────────────────────────────────────────────┐
│              Streamlit Frontend              │
│  ┌──────────┬──────────┬──────────┬────────┐ │
│  │ Overview  │  RFM     │ Q&A     │ ETL    │ │
│  │ Dashboard │ Analysis │ (SQL/   │ Mgmt   │ │
│  │          │          │  RAG)   │        │ │
│  └──────────┴──────────┴──────────┴────────┘ │
└──────────────────┬───────────────────────────┘
                   │
    ┌──────────────┼──────────────┐
    ▼              ▼              ▼
┌─────────┐  ┌──────────┐  ┌──────────┐
│ SQL     │  │ RAG      │  │ ETL      │
│ Agent   │  │ Engine   │  │ Pipeline │
│ (7 tools)│  │ (Fusion) │  │ (5 steps)│
└────┬────┘  └─────┬────┘  └─────┬────┘
     │             │             │
     ▼             ▼             ▼
┌─────────┐  ┌──────────┐  ┌──────────┐
│ SQLite  │  │ ChromaDB │  │ Olist    │
│ (WAL)   │  │ Vectors  │  │ CSV Data │
└─────────┘  └──────────┘  └──────────┘
```

## Quick Start

### 1. Clone

```bash
git clone https://github.com/Hav1d/LangChain-SQL-Agent-for-dynamic-data-visualization.git
cd LangChain-SQL-Agent-for-dynamic-data-visualization
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure API Key

Create a `.env` file:

```
SILICONFLOW_API_KEY=sk-xxxxxxxxxxxxxxxx
```

> Get a free API key at [SiliconFlow](https://cloud.siliconflow.cn)

### 4. Run ETL Pipeline

The app will prompt you to run ETL on first launch. Or run manually:

```bash
python -c "from etl.pipeline import ETLPipeline; ETLPipeline().run()"
```

### 5. Launch

```bash
streamlit run app.py
```

Opens at http://localhost:8501

## Dashboard Tabs

| Tab | What it does |
|-----|-------------|
| **Data Overview** | KPIs, monthly revenue trends, category pie chart, heatmap, geo distribution, treemap |
| **RFM Analysis** | Customer segmentation, 3D scatter, sunburst, sankey flow, radar chart, marketing strategies |
| **Smart Q&A** | SQL Agent (preset queries or LLM-generated SQL) + RAG knowledge base Q&A |
| **ETL Management** | Pipeline execution, database stats, CSV export, performance log viewer |

## Example Questions

**SQL Agent mode:**
- "Monthly revenue trend"
- "Top 10 product categories by sales"
- "Customer distribution by city"
- "Repeat purchase frequency"
- "RFM customer segmentation overview"

**RAG mode:**
- "Which customers need retention?"
- "What are the characteristics of high-value users?"
- "How are sales distributed across categories?"

## Performance Optimizations

The platform includes several performance optimizations:

| Optimization | Impact |
|-------------|--------|
| `@st.cache_data` (5min TTL) | DB queries cached — repeat loads < 1s |
| `@st.fragment` tab lazy loading | Only active tab executes — saves ~12s per interaction |
| SQLite WAL mode + PRAGMAs | 20-40% query speedup |
| Database indexes (9 indexes) | JOIN queries drop from 2.3s to < 50ms |
| RFM column selection | Query reduced from 2.4s to ~1s |
| RAG-Fusion bypass for simple questions | Skips 2 LLM calls for short queries |
| Model select debounce | Eliminates 60% of unnecessary reruns |

## Project Structure

```
sql-assistant/
├── app.py                    # Streamlit main entry + tab orchestration
├── config.py                 # Environment config (.env based)
├── agent_tools.py            # 7 custom LangChain tools (charts, presets, auto-viz)
├── run_sql_agent.py          # CLI version
├── setup_db.py               # Legacy DB setup
│
├── dashboard/
│   ├── tabs.py               # Tab renderer (Overview, RFM, Q&A, ETL)
│   └── charts.py             # Plotly chart factory (12+ chart types)
│
├── etl/
│   ├── pipeline.py           # ETL orchestrator (5 steps: collect→clean→features→load→index)
│   ├── collector.py          # Synthetic data generator
│   ├── csv_collector.py      # Olist CSV data loader
│   ├── cleaner.py            # Data cleaning + outlier removal
│   ├── feature_engineering.py# Derived features (order value tiers, etc.)
│   └── loader.py             # SQLite loader
│
├── analysis/
│   ├── rfm_engine.py         # RFM scoring, 10-segment classification
│   ├── clustering.py         # KMeans clustering with silhouette scores
│   └── report_generator.py   # Markdown report generation
│
├── rag/
│   ├── rag_engine.py         # RAG-Fusion + RRF + hybrid retrieval
│   ├── document_processor.py # Report chunking for vectorization
│   └── vector_store.py       # ChromaDB vector store manager
│
├── utils/
│   └── timing.py             # Performance timers + user action logging
│
├── tests/
│   ├── test_timing.py        # Timing utility tests
│   ├── test_rfm.py           # RFM engine + clustering + report tests
│   ├── test_agent_tools.py   # Agent tools tests
│   └── test_etl.py           # ETL pipeline tests
│
└── data/                     # (gitignored) Generated at runtime
    ├── ecommerce.db          # SQLite database
    ├── performance.log       # Performance + user action logs
    └── chroma_db/            # ChromaDB vector store
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| LLM | SiliconFlow (Qwen3-8B / DeepSeek-V3 / DeepSeek-R1) |
| Agent Framework | LangChain (tool-calling agent) |
| Frontend | Streamlit |
| Database | SQLite (WAL mode) + SQLAlchemy |
| Vector Store | ChromaDB |
| Visualization | Plotly (12+ chart types) |
| Clustering | scikit-learn KMeans |
| Language | Python 3.10+ |

## Testing

```bash
python -m pytest tests/ -v
```

57 tests covering timing utilities, RFM engine, clustering, report generation, agent tools, and ETL pipeline.

## License

MIT

---

# 电商平台智能数据分析平台

> [English Version](#e-commerce-data-intelligence-platform)

端到端的电商数据分析平台，融合 ETL 数据管道、RFM 客户分群、交互式仪表盘和 RAG 知识库问答 —— 基于 LangChain Agent + SiliconFlow LLM 驱动。

**自然语言输入 → SQL + 图表 + 洞察输出。**

## 功能特性

- **SQL Agent** — 自然语言提问，自动生成 SQL 查询并返回 Plotly 可视化图表
- **ETL 管道** — 自动化数据采集、清洗、特征工程和加载（支持 Olist 真实数据集或模拟数据）
- **RFM 分析** — 客户分群，KMeans 聚类，10 段分类，营销策略建议
- **交互式仪表盘** — 4 标签页 Streamlit UI：数据概览、RFM 深度分析、智能问答、ETL 管理
- **RAG 知识库** — 基于生成的分析报告进行 RAG-Fusion + RRF 排序问答
- **性能计时体系** — 全链路耗时日志 + 用户行为追踪

## 系统架构

```
用户输入 (自然语言)
    │
    ▼
┌──────────────────────────────────────────────┐
│             Streamlit 前端                    │
│  ┌──────────┬──────────┬──────────┬────────┐ │
│  │ 数据概览  │ RFM分析  │ 智能问答  │ ETL管理 │ │
│  │ Dashboard │ Deep Dive│ SQL/RAG  │        │ │
│  └──────────┴──────────┴──────────┴────────┘ │
└──────────────────┬───────────────────────────┘
                   │
    ┌──────────────┼──────────────┐
    ▼              ▼              ▼
┌─────────┐  ┌──────────┐  ┌──────────┐
│ SQL     │  │ RAG      │  │ ETL      │
│ Agent   │  │ 引擎     │  │ 管道     │
│(7个工具) │  │(Fusion)  │  │(5个步骤) │
└────┬────┘  └─────┬────┘  └─────┬────┘
     │             │             │
     ▼             ▼             ▼
┌─────────┐  ┌──────────┐  ┌──────────┐
│ SQLite  │  │ ChromaDB │  │ Olist    │
│ (WAL)   │  │ 向量存储  │  │ CSV 数据 │
└─────────┘  └──────────┘  └──────────┘
```

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/Hav1d/LangChain-SQL-Agent-for-dynamic-data-visualization.git
cd LangChain-SQL-Agent-for-dynamic-data-visualization
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置 API Key

创建 `.env` 文件：

```
SILICONFLOW_API_KEY=sk-xxxxxxxxxxxxxxxx
```

> 在 [SiliconFlow](https://cloud.siliconflow.cn) 免费注册获取 API Key

### 4. 运行 ETL 管道

首次启动时应用会提示运行 ETL。也可手动执行：

```bash
python -c "from etl.pipeline import ETLPipeline; ETLPipeline().run()"
```

### 5. 启动应用

```bash
streamlit run app.py
```

浏览器自动打开 http://localhost:8501

## 仪表盘标签页

| 标签页 | 功能 |
|--------|------|
| **数据概览** | KPI 指标、月度收入趋势、类目饼图、热力图、地域分布、树状图 |
| **RFM 分析** | 客户分群、3D 散点图、旭日图、桑基图、雷达图、营销策略 |
| **智能问答** | SQL Agent（预置查询或 LLM 生成 SQL）+ RAG 知识库问答 |
| **ETL 管理** | 管道执行、数据库统计、CSV 导出、性能日志查看 |

## 示例问题

**SQL Agent 模式：**
- "月度收入趋势"
- "类目 TOP10 排名"
- "客户城市分布"
- "复购次数分布"
- "RFM 客户分群概览"

**RAG 模式：**
- "哪些用户需要挽留？"
- "高价值用户的特征是什么？"
- "各类目销售情况如何？"

## 性能优化

平台包含多项性能优化措施：

| 优化项 | 效果 |
|--------|------|
| `@st.cache_data`（5分钟TTL） | 数据库查询缓存 — 重复加载 < 1秒 |
| `@st.fragment` 标签页懒加载 | 仅活跃标签页执行 — 每次交互省 ~12秒 |
| SQLite WAL 模式 + PRAGMA | 查询提速 20-40% |
| 数据库索引（9个） | JOIN 查询从 2.3秒 降到 < 50毫秒 |
| RFM 列裁剪 | 查询从 2.4秒 降到 ~1秒 |
| RAG 简单问题跳过 Fusion | 短查询省 2 次 LLM 调用 |
| 模型选择防抖 | 减少 60% 不必要的页面重运行 |

## 项目结构

```
sql-assistant/
├── app.py                    # Streamlit 主入口 + 标签页编排
├── config.py                 # 环境配置（基于 .env）
├── agent_tools.py            # 7个自定义 LangChain 工具（图表、预置、自动可视化）
├── run_sql_agent.py          # 命令行版本
├── setup_db.py               # 旧版数据库初始化
│
├── dashboard/
│   ├── tabs.py               # 标签页渲染器（概览、RFM、问答、ETL）
│   └── charts.py             # Plotly 图表工厂（12+ 种图表类型）
│
├── etl/
│   ├── pipeline.py           # ETL 编排器（5步：采集→清洗→特征→加载→索引）
│   ├── collector.py          # 模拟数据生成器
│   ├── csv_collector.py      # Olist CSV 数据加载器
│   ├── cleaner.py            # 数据清洗 + 异常值处理
│   ├── feature_engineering.py# 衍生特征（订单价值层级等）
│   └── loader.py             # SQLite 加载器
│
├── analysis/
│   ├── rfm_engine.py         # RFM 评分、10段分类
│   ├── clustering.py         # KMeans 聚类 + 轮廓系数
│   └── report_generator.py   # Markdown 报告生成
│
├── rag/
│   ├── rag_engine.py         # RAG-Fusion + RRF + 混合检索
│   ├── document_processor.py # 报告分块向量化
│   └── vector_store.py       # ChromaDB 向量存储管理
│
├── utils/
│   └── timing.py             # 性能计时 + 用户行为日志
│
├── tests/
│   ├── test_timing.py        # 计时工具测试
│   ├── test_rfm.py           # RFM 引擎 + 聚类 + 报告测试
│   ├── test_agent_tools.py   # Agent 工具测试
│   └── test_etl.py           # ETL 管道测试
│
└── data/                     # (gitignore) 运行时生成
    ├── ecommerce.db          # SQLite 数据库
    ├── performance.log       # 性能 + 用户行为日志
    └── chroma_db/            # ChromaDB 向量存储
```

## 技术栈

| 组件 | 技术 |
|------|------|
| LLM | SiliconFlow (Qwen3-8B / DeepSeek-V3 / DeepSeek-R1) |
| Agent 框架 | LangChain (tool-calling agent) |
| 前端 | Streamlit |
| 数据库 | SQLite (WAL 模式) + SQLAlchemy |
| 向量存储 | ChromaDB |
| 可视化 | Plotly（12+ 种图表类型）|
| 聚类 | scikit-learn KMeans |
| 语言 | Python 3.10+ |

## 测试

```bash
python -m pytest tests/ -v
```

57 个测试，覆盖计时工具、RFM 引擎、聚类、报告生成、Agent 工具和 ETL 管道。

## 许可证

MIT
