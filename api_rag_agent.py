import json
import re
from typing import Dict, Any, List

from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain_core.output_parsers import StrOutputParser

from src.vector_stores import VectorStoreManager
from src.llm_factory import LLMFactory

class ApiRagAgent:
    """
    API RAG Agent: 接收一个结构化的工作流计划，并构建一个可执行的API调用蓝图。
    """
    def __init__(self):
        self.embeddings = LLMFactory.create_embeddings(provider='dashscope')
        self.vsm = VectorStoreManager(embeddings=self.embeddings)
        self.vsm.load_vector_store(collection_name="api_docs")
        self.llm = LLMFactory.create_llm(provider='dashscope')
        self.param_fill_prompt = self._create_param_fill_prompt()
        self.api_chain = self.param_fill_prompt | self.llm | StrOutputParser()

    def _create_param_fill_prompt(self) -> ChatPromptTemplate:
        """创建一个极其简化的Prompt，让LLM只负责从用户原始需求中提取参数值"""
        system_template = """
你是一个参数提取机器人。根据用户需求，为下面JSON中列出的参数寻找并提供对应的值。如果找不到某个参数的值，就使用字符串 `__MISSING__` 作为它的值。
你的输出必须是一个严格的JSON对象，只包含参数名和提取到的参数值。

**# 需要寻找值的参数列表:**
{param_list_str}
"""
        return ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(system_template),
            HumanMessagePromptTemplate.from_template("**# 用户原始需求:**\n{user_query}")
        ])

    def _fill_task_parameters(self, task: Dict[str, Any], user_query: str) -> Dict[str, Any]:
        """为一个任务填充参数，严格区分上下文依赖和用户输入"""
        api_name = task.get("api_name")
        retrieved_docs = self.vsm.similarity_search(query=api_name, k=1)
        if not retrieved_docs:
            return {"error": f"无法找到API '{api_name}' 的文档"}
        
        api_metadata = retrieved_docs[0].metadata
        api_params_def = json.loads(api_metadata.get("params_json", "[]"))

        final_body = {}
        missing_params = []
        params_to_find_from_user = []

        # 1. 首先处理所有参数，区分来源
        for param_def in api_params_def:
            param_name = param_def["name"]
            input_source = task.get("inputs", {}).get(param_name)

            if input_source and input_source.startswith("ref:"):
                # 参数来源于上游任务，直接标记为missing
                missing_params.append({
                    "name": param_name,
                    "type": param_def.get("type"),
                    "description": param_def.get("description"),
                    "required": param_def.get("required", False),
                    "source": input_source
                })
            else:
                # 参数需要从用户输入中寻找
                params_to_find_from_user.append(param_def)

        # 2. 如果有需要从用户输入中寻找的参数，则调用LLM
        if params_to_find_from_user:
            chain_inputs = {
                "param_list_str": json.dumps(params_to_find_from_user, ensure_ascii=False),
                "user_query": user_query,
            }
            raw_text = self.api_chain.invoke(chain_inputs)
            match = re.search(r'\{.*\}', raw_text, re.DOTALL)
            llm_output = json.loads(match.group(0)) if match else {}

            # 处理LLM的输出
            for param_def in params_to_find_from_user:
                param_name = param_def["name"]
                value = llm_output.get(param_name)

                if value and value != "__MISSING__":
                    final_body[param_name] = value
                else:
                    missing_params.append({
                        "name": param_name,
                        "type": param_def.get("type"),
                        "description": param_def.get("description"),
                        "required": param_def.get("required", False),
                        "source": "user_input"
                    })
        
        # 3. 组装最终结果
        final_task = {
            "description": api_metadata.get("description"),
            "method": api_metadata.get("method"),
            "url": api_metadata.get("endpoint", "")
        }
        if final_body:
            final_task["body"] = final_body
        if missing_params:
            final_task["missing"] = sorted(missing_params, key=lambda p: p['name']) # 排序以保证输出稳定

        return final_task

    def build_workflow_blueprint(self, plan: Dict[str, Any], user_query: str) -> Dict[str, Any]:
        """构建API工作流蓝图的主方法"""
        if "workflow" not in plan:
            return {"error": "无效的计划格式，缺少'workflow'键"}

        final_workflow = {"type": "sequential", "tasks": []}

        for stage in sorted(plan["workflow"], key=lambda s: s.get("stage", 0)):
            stage_tasks = stage.get("tasks", [])
            filled_stage_tasks = []
            for task in stage_tasks:
                filled_task = self._fill_task_parameters(task, user_query)
                filled_stage_tasks.append(filled_task)

            if len(filled_stage_tasks) > 1:
                final_workflow["tasks"].append({"type": "parallel", "tasks": filled_stage_tasks})
            elif len(filled_stage_tasks) == 1:
                final_workflow["tasks"].append(filled_stage_tasks[0])

        return {"workflow": final_workflow}