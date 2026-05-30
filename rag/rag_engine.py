"""
RAG问答引擎 - 整合文档处理、向量存储和LLM问答

增强版:
- RAG-Fusion: LLM生成多查询变体
- RRF (Reciprocal Rank Fusion): 多路结果融合排序
- LCEL链式调用
- 混合检索: 语义搜索 + 关键词补充
"""
import logging
import re

from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_openai import ChatOpenAI

from .document_processor import DocumentProcessor
from .vector_store import VectorStoreManager
from config import (
    DB_PATH, REPORTS_DIR, siliconflow_api_key, llm_base_url,
    llm_model_id, llm_temperature, RAG_TOP_K
)
from utils.timing import get_perf_logger, TimerContext

logger = logging.getLogger(__name__)


RAG_PROMPT_TEMPLATE = """你是一个电商数据分析助手。根据以下检索到的分析报告内容，回答用户的问题。

要求：
1. 直接回答问题，引用报告中的具体数据（数字、百分比、金额等）
2. 如果报告中有多个相关的分群或分类，必须逐一列出所有相关群体的数据，不要遗漏
3. 给出基于数据的可操作建议
4. 如果报告中完全没有相关信息，如实说明

检索到的报告内容：
{context}

用户问题：{question}

请用中文回答，保持专业和准确。注意：如果报告中提到了多个客户群体（如重要挽留客户、一般挽留客户等），请全部列出，不要只提其中一个："""

MULTI_QUERY_PROMPT = """你是一个搜索查询生成专家。给定以下用户问题，请生成 {n} 个不同措辞的搜索查询，用于检索相关文档。

要求：
- 每个查询用不同的角度或措辞
- 保持查询的核心意图不变
- 适合向量相似度搜索
- 每行一个查询，不要编号

用户问题：{question}

生成的搜索查询："""


class RAGEngine:
    """RAG问答引擎（增强版）"""

    def __init__(self) -> None:
        self.doc_processor = DocumentProcessor()
        self.vector_store = VectorStoreManager()
        self._llm: ChatOpenAI = None

    def _get_llm(self) -> ChatOpenAI:
        if self._llm is None:
            extra_kwargs = {}
            if "Qwen3" in llm_model_id:
                extra_kwargs["extra_body"] = {"enable_thinking": False}
            self._llm = ChatOpenAI(
                model=llm_model_id,
                temperature=llm_temperature,
                openai_api_base=llm_base_url,
                openai_api_key=siliconflow_api_key,
                **extra_kwargs,
            )
        return self._llm

    def index_documents(self) -> int:
        """索引所有文档到向量存储"""
        logger.info("开始索引文档到向量存储...")
        self.vector_store.clear()

        chunks = self.doc_processor.process(
            db_path=str(DB_PATH),
            report_dir=str(REPORTS_DIR)
        )
        if not chunks:
            logger.warning("没有文档可索引")
            return 0

        count = self.vector_store.add_documents(chunks)
        logger.info("已索引 %d 个文档块", count)
        return count

    def generate_multi_queries(self, question: str, n: int = 2) -> list[str]:
        """使用LLM生成多个查询变体（RAG-Fusion）

        Args:
            question: 原始用户问题
            n: 生成的查询数量

        Returns:
            list[str]: 查询变体列表（包含原始问题）
        """
        llm = self._get_llm()
        prompt = ChatPromptTemplate.from_template(MULTI_QUERY_PROMPT)
        chain = prompt | llm | StrOutputParser()

        try:
            response = chain.invoke({"question": question, "n": n})
            queries = [q.strip() for q in response.strip().split("\n") if q.strip()]
            # 过滤掉编号前缀 (1. 2. 等)
            queries = [re.sub(r"^\d+[\.\)、]\s*", "", q) for q in queries]
            # 去重并加入原始问题
            seen: set[str] = set()
            result: list[str] = []
            for q in [question] + queries:
                if q and q not in seen:
                    seen.add(q)
                    result.append(q)
            return result
        except Exception as e:
            logger.warning("多查询生成失败，回退到单查询: %s", e)
            return [question]

    @staticmethod
    def reciprocal_rank_fusion(results_list: list[list[Document]], k: int = 60) -> list[Document]:
        """倒数排名融合 (RRF)

        对多路检索结果进行融合排序:
        score(doc) = sum(1 / (rank + k)) across all result lists

        Args:
            results_list: 多路检索结果，每路是一个Document列表
            k: 平滑参数，默认60

        Returns:
            list[Document]: 按RRF分数排序的Document列表
        """
        fused_scores = {}
        doc_map = {}

        for results in results_list:
            for rank, doc in enumerate(results):
                # 用内容前200字符作为去重key
                doc_key = doc.page_content[:200]
                if doc_key not in fused_scores:
                    fused_scores[doc_key] = 0
                    doc_map[doc_key] = doc
                fused_scores[doc_key] += 1.0 / (rank + k)

        # 按融合分数排序
        sorted_items = sorted(fused_scores.items(), key=lambda x: x[1], reverse=True)
        return [doc_map[key] for key, _ in sorted_items]

    def _hybrid_retrieve(self, question: str, k: int = 6) -> list[Document]:
        """混合检索：语义搜索 + 关键词补充"""
        # 语义搜索
        docs = self.vector_store.similarity_search(question, k=k)
        seen_contents: set[str] = {d.page_content for d in docs}

        # 关键词补充：从问题中提取关键词，搜索包含关键词的文档
        keywords = []
        for kw in ["挽留", "保持", "价值", "发展", "分群", "聚类", "RFM", "策略", "营销"]:
            if kw in question:
                keywords.append(kw)
        if keywords:
            all_docs = self.vector_store.vectorstore.get()["documents"]
            for doc_text in all_docs:
                if any(kw in doc_text for kw in keywords) and doc_text not in seen_contents:
                    docs.append(Document(page_content=doc_text, metadata={"source": "keyword_match"}))
                    seen_contents.add(doc_text)
                    if len(docs) >= k * 2:
                        break
        return docs[:k * 2]

    def _rag_fusion_retrieve(self, question: str, k: int = 6) -> list[Document]:
        """RAG-Fusion检索: 多查询 + RRF融合

        1. LLM生成多个查询变体
        2. 每个查询独立检索
        3. RRF融合多路结果
        """
        queries = self.generate_multi_queries(question)
        logger.info("生成 %d 个查询变体", len(queries))

        # 多路检索
        all_results = []
        for q in queries:
            docs = self.vector_store.similarity_search(q, k=k)
            all_results.append(docs)

        # RRF融合
        fused = self.reciprocal_rank_fusion(all_results)
        return fused[:k * 2]

    def query(self, question: str, use_fusion: bool = True) -> str:
        """执行RAG问答

        Args:
            question: 用户问题
            use_fusion: 是否使用RAG-Fusion（默认True）
        """
        perf = get_perf_logger()
        with TimerContext("rag_query_total", perf):
            return self._query_impl(question, use_fusion)

    def _query_impl(self, question: str, use_fusion: bool = True) -> str:
        if self.vector_store.get_document_count() == 0:
            return "知识库为空，请先点击「更新知识库索引」按钮。"

        # 检索
        if use_fusion:
            docs = self._rag_fusion_retrieve(question)
        else:
            docs = self._hybrid_retrieve(question)

        context = "\n\n".join(d.page_content for d in docs)

        # 用LLM生成回答
        llm = self._get_llm()
        prompt = ChatPromptTemplate.from_template(RAG_PROMPT_TEMPLATE)
        chain = prompt | llm | StrOutputParser()
        try:
            answer = chain.invoke({"context": context, "question": question})

            # 来源信息
            if docs:
                source_info = "\n\n---\n**参考来源:**\n"
                seen = set()
                for doc in docs:
                    source = doc.metadata.get("source", "未知")
                    if source not in seen:
                        seen.add(source)
                        title = doc.metadata.get("title", doc.metadata.get("filename", source))
                        source_info += f"- {title}\n"
                answer += source_info

            return answer
        except Exception as e:
            logger.error("RAG查询失败: %s", e, exc_info=True)
            return f"查询出错: {str(e)}\n\n请检查网络连接和API Key配置。"

    def get_status(self) -> dict:
        """获取RAG系统状态"""
        doc_count = self.vector_store.get_document_count()
        return {"document_count": doc_count, "index_ready": doc_count > 0}
