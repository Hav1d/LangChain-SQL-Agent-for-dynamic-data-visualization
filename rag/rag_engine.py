"""
RAG问答引擎 - 整合文档处理、向量存储和LLM问答
使用LCEL (LangChain Expression Language) 构建检索链
"""
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

from .document_processor import DocumentProcessor
from .vector_store import VectorStoreManager
from config import (
    DB_PATH, REPORTS_DIR, siliconflow_api_key, llm_base_url,
    llm_model_id, llm_temperature, RAG_TOP_K
)


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


class RAGEngine:
    """RAG问答引擎（基于LCEL）"""

    def __init__(self):
        self.doc_processor = DocumentProcessor()
        self.vector_store = VectorStoreManager()
        self._chain = None

    def _get_llm(self) -> ChatOpenAI:
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

    def _get_chain(self):
        if self._chain is None:
            llm = self._get_llm()
            retriever = self.vector_store.get_retriever(k=RAG_TOP_K)
            prompt = ChatPromptTemplate.from_template(RAG_PROMPT_TEMPLATE)

            def format_docs(docs):
                return "\n\n".join(doc.page_content for doc in docs)

            self._chain = (
                {"context": retriever | format_docs, "question": RunnablePassthrough()}
                | prompt
                | llm
                | StrOutputParser()
            )
        return self._chain

    def index_documents(self) -> int:
        """索引所有文档到向量存储"""
        print("开始索引文档到向量存储...")
        self.vector_store.clear()
        self._chain = None

        chunks = self.doc_processor.process(
            db_path=str(DB_PATH),
            report_dir=str(REPORTS_DIR)
        )
        if not chunks:
            print("  没有文档可索引")
            return 0

        count = self.vector_store.add_documents(chunks)
        print(f"  已索引 {count} 个文档块")
        return count

    def _hybrid_retrieve(self, question: str, k: int = 6) -> list:
        """混合检索：语义搜索 + 关键词补充"""
        # 语义搜索
        docs = self.vector_store.similarity_search(question, k=k)
        seen_contents = {d.page_content for d in docs}

        # 关键词补充：从问题中提取关键词，搜索包含关键词的文档
        keywords = []
        for kw in ["挽留", "保持", "价值", "发展", "分群", "聚类", "RFM", "策略", "营销"]:
            if kw in question:
                keywords.append(kw)
        if keywords:
            all_docs = self.vector_store.vectorstore.get()["documents"]
            for doc_text in all_docs:
                if any(kw in doc_text for kw in keywords) and doc_text not in seen_contents:
                    from langchain_core.documents import Document
                    docs.append(Document(page_content=doc_text, metadata={"source": "keyword_match"}))
                    seen_contents.add(doc_text)
                    if len(docs) >= k * 2:
                        break
        return docs[:k * 2]

    def query(self, question: str) -> str:
        """执行RAG问答"""
        if self.vector_store.get_document_count() == 0:
            return "知识库为空，请先点击「更新知识库索引」按钮。"

        # 混合检索获取上下文
        docs = self._hybrid_retrieve(question)
        context = "\n\n".join(d.page_content for d in docs)

        # 直接用LLM生成回答（不走chain，使用自定义context）
        from langchain_openai import ChatOpenAI
        from config import llm_model_id, llm_temperature, llm_base_url, siliconflow_api_key
        extra_kwargs = {}
        if "Qwen3" in llm_model_id:
            extra_kwargs["extra_body"] = {"enable_thinking": False}
        llm = ChatOpenAI(
            model=llm_model_id, temperature=llm_temperature,
            openai_api_base=llm_base_url, openai_api_key=siliconflow_api_key,
            **extra_kwargs,
        )
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
            return f"查询出错: {str(e)}\n\n请检查网络连接和API Key配置。"

    def get_status(self) -> dict:
        """获取RAG系统状态"""
        doc_count = self.vector_store.get_document_count()
        return {"document_count": doc_count, "index_ready": doc_count > 0}
