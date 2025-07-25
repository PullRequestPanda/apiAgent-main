import json
import re
from typing import Dict, Any, List

from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.documents import Document
from loguru import logger

from src.vector_store.vector_stores import VectorStoreManager
from src.utils.llm_factory import LLMFactory
from src.retrieval.hybrid_retriever import ApiRetriever # Updated import

class ApiRagAgent:
    def __init__(self):
        self.embeddings = LLMFactory.create_embeddings(provider='dashscope')
        self.vsm = VectorStoreManager(embeddings=self.embeddings)
        self.vsm.load_vector_store(collection_name="api_docs")
        self.retriever = ApiRetriever(self.vsm) # Use the new ApiRetriever
        self.llm = LLMFactory.create_llm(provider='dashscope')
        self.param_fill_prompt = self._create_param_fill_prompt()
        self.api_chain = self.param_fill_prompt | self.llm | StrOutputParser()

    def _create_param_fill_prompt(self) -> ChatPromptTemplate:
        system_template = """
你是一个参数提取机器人。根据用户需求和API文档，为API的参数赋值。如果找不到值，就用`__MISSING__`作为值。
你的输出必须是只包含参数名和值的JSON。

**# API文档:**
{api_doc}
"""
        return ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(system_template),
            HumanMessagePromptTemplate.from_template("**# 用户需求:**\n{user_query}")
        ])

    def _get_api_doc_from_retrieval(self, query: str) -> Document | None:
        """使用ApiRetriever检索最相关的API文档"""
        logger.debug(f"使用ApiRetriever检索与查询 '{query}' 相关的API...")
        retrieved_results = self.retriever.search(query=query, final_k=1)
        if not retrieved_results:
            logger.warning("ApiRetriever未能检索到任何文档。")
            return None
        
        top_doc, score = retrieved_results[0]
        logger.info(f"检索到最相关的API: '{top_doc.metadata.get('name')}'，分数为: {score:.4f}")
        return top_doc

    def _fill_parameters(self, api_doc: Document, user_query: str) -> Dict[str, Any]:
        """根据API文档和用户查询，填充参数并构建最终的API调用信息。"""
        api_metadata = api_doc.metadata
        api_params_def = json.loads(api_metadata.get("params_json", "[]"))

        # 如果没有参数，直接返回组装好的结果
        if not api_params_def:
            return {
                "description": api_metadata.get("description"),
                "method": api_metadata.get("method"),
                "url": api_metadata.get("endpoint", "")
            }

        api_doc_for_prompt = json.dumps({
            "name": api_metadata["name"],
            "description": api_metadata["description"],
            "params": api_params_def
        }, ensure_ascii=False)

        chain_inputs = {
            "api_doc": api_doc_for_prompt,
            "user_query": user_query,
        }
        
        raw_text = self.api_chain.invoke(chain_inputs)
        match = re.search(r'\{.*\}', raw_text, re.DOTALL)
        llm_output = json.loads(match.group(0)) if match else {}

        final_body = {}
        missing_params = []
        final_url = api_metadata.get("endpoint", "")

        all_params = {p["name"]: p for p in api_params_def}

        # 填充路径和查询参数
        for name, value in llm_output.items():
            if f'{{{name}}}' in final_url:
                if value and value != "__MISSING__":
                    final_url = final_url.replace(f'{{{name}}}', str(value))
                else:
                    missing_params.append(all_params[name])
            else:
                if value and value != "__MISSING__":
                    final_body[name] = value
                else:
                    missing_params.append(all_params[name])

        final_task = {
            "description": api_metadata.get("description"),
            "method": api_metadata.get("method"),
            "url": final_url
        }
        if final_body:
            final_task["body"] = final_body
        if missing_params:
            final_task["missing"] = sorted(missing_params, key=lambda p: p['name'])

        return final_task

    def generate_api_call(self, user_query: str) -> Dict[str, Any]:
        """根据用户查询，生成单个API调用。"""
        # 1. 检索最相关的API文档
        api_doc = self._get_api_doc_from_retrieval(user_query)
        if not api_doc:
            return {"error": "无法找到与您的需求匹配的API。"}

        # 2. 填充参数
        return self._fill_parameters(api_doc, user_query)
