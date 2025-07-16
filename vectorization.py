from langchain_core.documents import Document
import json
# from qwen_embeddings import QwenSentenceTransformerEmbeddings
from src.vector_stores import VectorStoreManager
from src.llm_factory import LLMFactory

with open("data/api.json", "r", encoding="utf-8") as f:
    api_docs = json.load(f)


docs = []
# 定义结构化的Markdown模板
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

for api in api_docs:
    # 格式化参数列表
    param_list = []
    for p in api.get("params", []):
        required_str = "必需" if p.get("required") else "可选"
        param_list.append(f"- **`{p.get('name')}`** (类型: {p.get('type')}, {required_str}): {p.get('description')}")
    param_str = "\n".join(param_list) if param_list else "无"

    # 格式化响应
    response_str = json.dumps(api.get("response", {}), ensure_ascii=False, indent=2)

    # 使用模板生成API文档内容
    content = markdown_template.format(
        name=api.get("name"),
        description=api.get("description"),
        method=api.get("method"),
        endpoint=api.get("endpoint"),
        params=param_str,
        response=response_str
    )

    # 构建 metadata，保留关键字段用于可能的精确过滤
    metadata = {
        "name": api.get("name"),
        "description": api.get("description"),
        "method": api.get("method"),
        "endpoint": api.get("endpoint"),
        "params_json": json.dumps(api.get("params", []), ensure_ascii=False)
    }

    docs.append(Document(page_content=content, metadata=metadata))
my_embeddings = LLMFactory.create_embeddings(provider='dashscope')

# 然后你可以继续使用：
vsm = VectorStoreManager(embeddings=my_embeddings)
vsm.create_vector_store(docs, collection_name='api_docs')



