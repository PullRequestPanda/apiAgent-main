import json
import sys
import os
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.planning.task_planner import TaskPlanner
from src.agent.api_rag_agent import ApiRagAgent
from src.utils.llm_factory import LLMFactory

print("正在初始化服务，加载模型和数据...")

# --- 全局变量初始化 ---
api_agent = None
planner = None
api_json_definitions = None
llm = None
query_rewriter_chain = None

try:
    # 初始化LLM
    llm = LLMFactory.create_llm(provider='dashscope')
    
    # 初始化ApiRagAgent，用于第二个接口
    api_agent = ApiRagAgent()
    
    # 初始化TaskPlanner，用于第一个接口
    planner = TaskPlanner(llm)
    
    # 加载API定义文件，供TaskPlanner使用
    with open("data/api.json", "r", encoding="utf-8") as f:
        api_json_definitions = json.load(f)

    # 创建查询改写链
    rewrite_prompt = ChatPromptTemplate.from_template(
        """# 角色
你是一个专业的业务需求分析师。你的任务是将用户模糊的、口语化的请求，改写成一个清晰、明确、包含必要业务逻辑步骤的指令。"

        "# 核心业务规则
        - 在执行任何与员工相关的具体操作（如请假、加班）之前，必须首先获取该员工的基础信息。这是一个必须遵守的前置步骤。"

        "# 改写示例
        - 原始请求: "帮我申请请假和加班"
        - 改写后: "首先获取我的员工信息，然后并行为我提交请假和加班申请。"
        - 原始请求: "我的项目经理是谁？"
        - 改写后: "获取我的员工项目信息，并告诉我项目经理是谁。"
        - 原始请求: "我要请假"
        - 改写后: "帮我提交一个请假申请。"

        "# 你的任务
        请根据以上规则和示例，改写下面的用户原始请求。只返回改写后的指令，不要添加任何解释。"

        "用户原始请求: {user_query}"""
    )
    query_rewriter_chain = rewrite_prompt | llm | StrOutputParser()

    print("服务初始化完成。")
except Exception as e:
    print(f"服务初始化过程中发生严重错误: {e}")
    sys.exit(1)

app = FastAPI(
    title="智能API路由与调用服务",
    description="提供任务规划和API参数自动填充两大功能。",
    version="11.0.0"
)

class RequestBody(BaseModel):
    query: str

@app.post("/plan", summary="生成任务规划")
async def create_plan(request: RequestBody):
    """
    接收用户的自然语言，先进行查询改写，然后生成结构化的任务计划。
    """
    user_query = request.query
    if not user_query:
        raise HTTPException(status_code=400, detail="Query不能为空")

    try:
        # 1. 查询改写
        print(f"接收到原始请求: '{user_query}'，正在进行查询改写...")
        rewritten_query = query_rewriter_chain.invoke({"user_query": user_query})
        print(f"改写后的查询: '{rewritten_query}'")

        # 2. 调用TaskPlanner
        print(f"调用TaskPlanner...")
        plan = planner.plan(rewritten_query, api_json_definitions)
        
        if not plan or "error" in plan or not plan.get("tasks"):
            error_detail = {"error": "无法为您的需求生成有效的执行计划。", "planner_details": plan}
            print(f"TaskPlanner处理失败: {error_detail}")
            raise HTTPException(status_code=404, detail=error_detail)
        
        print(f"成功生成任务规划: {plan}")
        return plan

    except Exception as e:
        print(f"处理规划请求时发生未知错误: {e}")
        raise HTTPException(status_code=500, detail={"error": "处理请求时发生内部错误。"})

@app.post("/generate-api-call", summary="生成单次API调用")
async def generate_api_call(request: RequestBody):
    """
    接收用户的自然语言，检索最匹配的API，并自动填充参数。
    """
    user_query = request.query
    if not user_query:
        raise HTTPException(status_code=400, detail="Query不能为空")

    try:
        print(f"接收到API调用生成请求: '{user_query}'，调用ApiRagAgent...")
        result = api_agent.generate_api_call(user_query)
        
        if "error" in result:
            print(f"Agent处理失败: {result['error']}")
            raise HTTPException(status_code=404, detail=result)
        
        print(f"成功生成API调用信息: {result}")
        return result

    except Exception as e:
        print(f"处理API调用生成请求时发生未知错误: {e}")
        raise HTTPException(status_code=500, detail={"error": "处理请求时发生内部错误。"})

if __name__ == "__main__":
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)
