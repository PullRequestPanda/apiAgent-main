# src/retrieval/hybrid_retriever.py

import json
from typing import List, Tuple
from langchain_core.documents import Document
from loguru import logger

from src.vectorize.vectorizer import VectorStoreManager
from src.rerank.reranker import RerankerManager
from config.settings import settings

class ApiRetriever:
    """
    一个专门用于API检索的检索器，流程为：向量检索 -> Reranker精排。
    """

    def __init__(self, vector_store_manager: VectorStoreManager):
        """
        初始化API检索器。
        Args:
            vector_store_manager: 一个已经加载了'api_docs'集合的向量存储管理器。
        """
        self.vsm = vector_store_manager
        self.reranker = RerankerManager()
        # 确保向量存储已经加载
        if not self.vsm.vector_store:
            logger.warning("传入的VectorStoreManager未加载任何向量存储，请在使用前调用load_vector_store。")
        logger.info(f"ApiRetriever初始化成功。")

    def search(
        self, 
        query: str, 
        vector_k: int = 10, 
        final_k: int = 3
    ) -> List[Tuple[Document, float]]:
        """
        执行API检索。

        Args:
            query (str): 用户的自然语言查询。
            vector_k (int): 向量检索阶段召回的文档数量。
            final_k (int): 经过Reranker精排后最终返回的文档数量。

        Returns:
            List[Tuple[Document, float]]: 返回一个元组列表，每个元组包含一个文档和其相关性分数。
        """
        logger.debug(f"开始API检索，查询: '{query}'")

        # --- 1. 向量召回 ---
        try:
            # 使用带分数的搜索，虽然reranker目前不使用原始分数，但保留以备将来之用
            recalled_results = self.vsm.similarity_search_with_score(query, k=vector_k)
            recalled_docs = [doc for doc, score in recalled_results]
            logger.debug(f"向量检索召回 {len(recalled_docs)} 个结果。")
        except Exception as e:
            logger.error(f"向量检索失败: {e}")
            return []

        if not recalled_docs:
            return []

        # --- 2. Reranker精排 ---
        if self.reranker.enabled and settings.enable_reranking:
            logger.debug(f"开始使用Reranker对 {len(recalled_docs)} 个文档进行精排...")
            try:
                reranked_results = self.reranker.rerank_documents(
                    query=query,
                    documents=recalled_docs,
                    top_k=final_k
                )
                logger.debug(f"Reranker返回 {len(reranked_results)} 个结果。")
                return reranked_results
            except Exception as e:
                logger.error(f"Reranker精排失败: {e}。")
                return []
        else:
            # 如果禁用Reranker，直接返回向量检索的结果
            logger.warning("Reranker未启用或被禁用，将直接返回向量检索结果。")
            # ChromaDB返回的是距离，分数越小越好。reranker返回的是相关性，分数越高越好。
            # 这里我们做一个简单的转换，并截取top_k
            final_results = []
            for doc, score in recalled_results[:final_k]:
                relevance_score = 1.0 - score  # 简单地将距离转换为相关性
                final_results.append((doc, relevance_score))
            return final_results