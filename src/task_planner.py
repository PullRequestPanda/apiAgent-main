import json
import sys
import os
import re
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 调试：检查配置
from config.settings import settings
print(f"DashScope API Key: {settings.dashscope_api_key}")
print(f"API Key 长度: {len(settings.dashscope_api_key) if settings.dashscope_api_key else 0}")

class TaskPlanner:
    def __init__(self, llm):
        self.llm = llm

    def plan(self, user_query: str, api_json: list) -> dict:
        """
        调用大模型进行意图分解和任务编排。
        输入：用户需求、全部接口json。
        输出：一个结构化的、包含阶段和任务依赖的工作流计划。
        """
        prompt = f"""
你是一个非常出色的API任务规划专家。请根据用户的自然语言需求和所有可用的API定义，为我生成一个结构化的API工作流计划。这个计划将被用于后续的参数填充和执行。

**# 指令:**
1.  **分析依赖**: 仔细分析API列表中的`params`和`response`，理解API之间的依赖关系（例如，一个API的输入可能依赖于另一个API的输出）。
2.  **分阶段规划**: 将整个工作流分解为多个按顺序执行的**阶段(Stage)**。只有在前一个stage的所有任务都完成后，才能进入下一个stage。
3.  **并行处理**: 在同一个stage内，列出所有可以**并行(parallel)**执行的任务(task)。
4.  **结构化输出**: 必须严格按照下面的JSON格式输出你的计划，不要添加任何额外的解释或注释。

**# JSON输出格式:**
```json
{{
  "workflow": [
    {{
      "stage": 1,
      "description": "描述第一个阶段的总体目标",
      "tasks": [
        {{
          "task_id": "unique_task_id_1",
          "api_name": "要调用的API的名称",
          "description": "描述这个具体任务的目标",
          "inputs": {{
            "param_name_1": "ref:source_task_id.outputs.source_field", // 引用上游任务的输出
            "param_name_2": "from_user_input" // 表示需要从用户原始输入中提取
          }},
          "outputs": {{
            "output_field_1": "a_clear_placeholder_name" // 为此任务的输出字段定义一个清晰的占位符
          }}
        }}
      ]
    }}
    // ... more stages
  ]
}}
```

**# 关键要求:**
- **`task_id`**: 必须为每个任务创建一个简短、清晰、唯一的ID。
- **`api_name`**: 必须准确地从API定义中选择对应的`name`。
- **`inputs`**: 
    - 如果参数值需要从上一个步骤的输出中获取，请使用 `"ref:source_task_id.outputs.output_field_name"` 的格式。
    - 如果参数值可以直接从用户的原始请求中找到，请使用 `"from_user_input"` 作为占位符。
- **`outputs`**: 为每个API的响应字段定义一个清晰、易于引用的占位符名称。

**# 用户需求:**
{user_query}

**# 所有可用的API定义:**
{json.dumps(api_json, ensure_ascii=False)}

请立即生成JSON格式的工作流计划。
"""
        response = self.llm.invoke(prompt)
        try:
            # 检查 response 的类型
            if isinstance(response, str):
                raw_text = response
            elif isinstance(response, dict) and "text" in response:
                raw_text = response["text"]
            else:
                raw_text = str(response.content) if hasattr(response, 'content') else str(response)
            # 移除JSON中的行内注释 // ...
            raw_text = re.sub(r"//.*", "", raw_text)
            # 更鲁棒地去除 markdown 代码块
            raw_text = re.sub(r"^```[a-zA-Z]*\s*", "", raw_text)
            raw_text = re.sub(r"\s*```$", "", raw_text)
            raw_text = raw_text.strip()
            return json.loads(raw_text)
        except Exception as e:
            print(f"[DEBUG] raw_text for JSON decode error:\n{raw_text}")
            return {"status": "error", "message": f"解析任务编排失败: {str(e)}", "raw": raw_text if 'raw_text' in locals() else str(response)}

# 使用示例
if __name__ == "__main__":
    from src.llm_factory import LLMFactory
    llm = LLMFactory.create_llm(provider='dashscope')
    planner = TaskPlanner(llm)
    with open("data/api_dependencies.json", "r", encoding="utf-8") as f:
        api_json = json.load(f)
    # user_query = "帮我注册一个新用户，用户名是alice，密码是123456，邮箱是alice@example.com，部门是技术部，查询该用户的权限"
    user_query = "请用用户名zhangsan，密码abc123登录系统，登录后查询该用户的详细信息和他所在部门的所有项目"
    plan = planner.plan(user_query, api_json)
    print(json.dumps(plan, ensure_ascii=False, indent=2))