"""
向量存储模块 - ChromaDB管理
"""
from pathlib import Path

from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_core.documents import Document

from config import CHROMA_DIR, siliconflow_api_key, llm_base_url, EMBEDDING_MODEL


class VectorStoreManager:
    """ChromaDB向量存储管理器"""

    def __init__(self, persist_dir: str = None):
        self.persist_dir = persist_dir or str(CHROMA_DIR)
        Path(self.persist_dir).mkdir(parents=True, exist_ok=True)

        # 使用SiliconFlow Embedding
        self.embeddings = OpenAIEmbeddings(
            model=EMBEDDING_MODEL,
            openai_api_base=llm_base_url,
            openai_api_key=siliconflow_api_key,
        )
        self._vectorstore = None

    @property
    def vectorstore(self) -> Chroma:
        """获取或创建向量存储"""
        if self._vectorstore is None:
            self._vectorstore = Chroma(
                persist_directory=self.persist_dir,
                embedding_function=self.embeddings,
                collection_name="ecommerce_reports"
            )
        return self._vectorstore

    def add_documents(self, documents: list) -> int:
        """
        添加文档到向量存储（分批处理，避免API批量限制）

        Args:
            documents: 切分后的文档块列表

        Returns:
            int: 添加的文档数量
        """
        if not documents:
            return 0

        # 分批添加，避免SiliconFlow API的批量限制
        batch_size = 10
        total = 0
        for i in range(0, len(documents), batch_size):
            batch = documents[i:i + batch_size]
            try:
                self.vectorstore.add_documents(batch)
                total += len(batch)
            except Exception as e:
                print(f"  [WARN] 批次 {i//batch_size + 1} 索引失败: {e}")
                # 尝试逐条添加
                for doc in batch:
                    try:
                        self.vectorstore.add_documents([doc])
                        total += 1
                    except Exception:
                        pass

        return total

    def similarity_search(self, query: str, k: int = 4) -> list:
        """
        相似度搜索

        Args:
            query: 查询文本
            k: 返回结果数量

        Returns:
            list: 相似文档列表
        """
        return self.vectorstore.similarity_search(query, k=k)

    def similarity_search_with_score(self, query: str, k: int = 4) -> list:
        """带分数的相似度搜索"""
        return self.vectorstore.similarity_search_with_score(query, k=k)

    def get_retriever(self, k: int = 4):
        """获取检索器"""
        return self.vectorstore.as_retriever(search_kwargs={"k": k})

    def clear(self) -> None:
        """清空向量存储（通过删除collection，避免Windows文件锁问题）"""
        try:
            # 通过删除collection来清空，而不是删除目录文件
            collection = self.vectorstore._collection
            # 获取所有文档ID并删除
            all_ids = collection.get()["ids"]
            if all_ids:
                collection.delete(ids=all_ids)
            self._vectorstore = None
        except Exception as e:
            print(f"清空向量存储失败: {e}")
            # 回退：重置vectorstore，下次访问时会重新创建
            self._vectorstore = None

    def get_document_count(self) -> int:
        """获取已索引的文档数量"""
        try:
            collection = self.vectorstore._collection
            return collection.count()
        except Exception:
            return 0
