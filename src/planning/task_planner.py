import json
import re

class TaskPlanner:
    def __init__(self, llm):
        self.llm = llm

    def plan(self, user_query: str, api_json: list) -> dict:
        """
        调用大模型，根据用户意图，动态规划出一个包含多步骤、串并行关系、且每个任务都包含api_name的workflow。
        """
        api_signatures = [
            {"name": api.get("name"), "description": api.get("description")}
            for api in api_json
        ]

        prompt = f"""
# 角色
你是一个顶级的API任务规划专家，同时深刻理解业务流程。你的任务是根据用户的自然语言需求和下述的核心业务规则，设计出一个逻辑严谨、步骤最优的API执行计划。

# 核心业务规则
- **前置依赖规则**: 在执行任何与员工相关的具体操作（如提交请假、加班申请）之前，必须首先调用`获取员工项目信息`来获取该员工的基础信息。这是一个必须遵守的前置步骤。

# 指令
请严格遵循以下思考链（Chain-of-Thought）来构建你的计划：
1.  **规则检查**: 首先，检查用户的需求是否触发了任何“核心业务规则”。
2.  **核心意图分析**: 接着，分析用户的核心业务目标是什么。
3.  **原子能力筛选**: 根据意图，从“可用API列表”中筛选出所有完成任务所需要的API。
4.  **依赖关系分析**: 结合业务规则和API的输入输出，分析它们之间的依赖关系，判断是串行还是并行。
5.  **构建执行计划**: 最后，构建一个包含`type`和`tasks`数组的JSON工作流。`tasks`数组中的每一个任务对象，都必须包含一个`api_name`字段，其值必须严格等于“可用API列表”中对应API的`name`字段。

# 可用API列表 (你的工具箱)
{json.dumps(api_signatures, ensure_ascii=False, indent=2)}

# 用户的需求
{user_query}

# 输出要求
- 如果你能构建一个有意义的计划，请严格按照下面的JSON格式返回，不要包含任何额外的解释或注释。
- **如果用户的需求与所有可用的API都完全不相关，请只返回一个空的JSON对象: `{{}}`**

```json
{{
  "type": "sequential",
  "tasks": [
    {{
      "api_name": "获取员工项目信息",
      "description": "获取员工的基础信息，如项目和汇报对象。"
    }},
    {{
      "type": "parallel",
      "tasks": [
        {{
          "api_name": "提交请假申请",
          "description": "提交员工的请假申请。"
        }},
        {{
          "api_name": "提交加班申请",
          "description": "提交员工的加班申请。"
        }}
      ]
    }}
  ]
}}
```
"""
        response = self.llm.invoke(prompt)
        raw_text = str(response.content) if hasattr(response, 'content') else str(response)
        
        match = re.search(r"```json\n(\{.*?\})\n```", raw_text, re.DOTALL)
        if not match:
            match = re.search(r'\{.*\}', raw_text, re.DOTALL)

        if match:
            try:
                json_str = match.group(1) if "```" in match.group(0) else match.group(0)
                return json.loads(json_str)
            except json.JSONDecodeError:
                return {"error": "无法从TaskPlanner输出中解析JSON", "raw": match.group(0)}

        return {"error": "无法从TaskPlanner输出中找到JSON对象", "raw": raw_text}
