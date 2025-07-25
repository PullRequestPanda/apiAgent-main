from langchain_core.documents import Document
import json
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.vector_store.vector_stores import VectorStoreManager
from src.utils.llm_factory import LLMFactory

def vectorize_apis(vsm: VectorStoreManager):
    """读取api.json，向量化并存储单个API的信息"""
    print("正在处理单个API的向量化...")
    with open("data/api.json", "r", encoding="utf-8") as f:
        api_docs_data = json.load(f)

    docs = []
    markdown_template = """
### API名称: {name}

**功能描述:**
{description}

**请求详情:**
- **方法:** `{method}`
- **路径:** `{endpoint}`

**参数列表:**
{params}

**预期响应:**
{response}
"""

    for api in api_docs_data:
        param_list = [f"- **`{p.get('name')}`** (类型: {p.get('type')}, {'必需' if p.get('required') else '可选'}): {p.get('description')}" for p in api.get("params", [])]
        param_str = "\n".join(param_list) if param_list else "无"
        response_str = json.dumps(api.get("response", {}), ensure_ascii=False, indent=2)

        content = markdown_template.format(
            name=api.get("name"),
            description=api.get("description"),
            method=api.get("method"),
            endpoint=api.get("endpoint"),
            params=param_str,
            response=response_str
        )
        metadata = {
            "name": api.get("name"),
            "description": api.get("description"),
            "method": api.get("method"),
            "endpoint": api.get("endpoint"),
            "params_json": json.dumps(api.get("params", []), ensure_ascii=False)
        }
        docs.append(Document(page_content=content, metadata=metadata))
    
    vsm.create_vector_store(docs, collection_name='api_docs')
    print("单个API向量库[api_docs]创建/更新成功。")

if __name__ == "__main__":
    # 初始化向量存储管理器
    embeddings = LLMFactory.create_embeddings(provider='dashscope')
    vsm = VectorStoreManager(embeddings=embeddings)

    # 执行API向量化流程
    vectorize_apis(vsm)

    print("\n所有向量化任务完成。")