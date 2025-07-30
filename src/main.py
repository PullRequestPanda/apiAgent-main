import json
import sys
import os
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Any
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from loguru import logger

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.planning.task_planner import TaskPlanner
from src.agent.api_rag_agent import ApiRagAgent
from src.utils.llm_factory import LLMFactory
from src.utils.groovy_script_generator import GroovyScriptGenerator
from config.settings import settings

def setup_logging():
    """根据配置设置Loguru日志记录器。"""
    logger.remove()  # 移除默认的处理器
    logger.add(
        sys.stderr,
        level=settings.log_level.upper(),
        format=settings.log_format,
        colorize=True
    )
    logger.add(
        settings.log_file,
        level=settings.log_level.upper(),
        format=settings.log_format,
        rotation=settings.log_rotation,
        retention=settings.log_retention,
        encoding="utf-8",
        enqueue=True,  # 使日志写入成为非阻塞
        backtrace=True, # 记录完整的堆栈跟踪
        diagnose=True   # 添加异常诊断信息
    )
    logger.info("日志系统初始化完成。")

# --- 全局变量初始化 ---
api_agent = None
planner = None
api_json_definitions = None
llm = None
query_rewriter_chain = None

app = FastAPI(
    title="智能API路由与调用服务",
    description="提供任务规划、API参数填充和Groovy脚本生成三大功能。",
    version="13.0.0"
)

@app.on_event("startup")
async def startup_event():
    """应用启动时执行的事件"""
    global api_agent, planner, api_json_definitions, llm, query_rewriter_chain
    setup_logging()
    logger.info("正在初始化服务，加载模型和数据...")
    try:
        llm = LLMFactory.create_llm(provider='dashscope')
        api_agent = ApiRagAgent()
        planner = TaskPlanner(llm)
        with open("data/api.json", "r", encoding="utf-8") as f:
            api_json_definitions = json.load(f)

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

        logger.info("服务初始化完成。")
    except Exception as e:
        logger.exception(f"服务初始化过程中发生严重错误: {e}")
        raise

class PlanRequestBody(BaseModel):
    query: str

class ApiCallRequestBody(BaseModel):
    query: str

class GroovyRequestBody(BaseModel):
    query: str
    known_data: Dict[str, Any] = Field(default_factory=dict, description="调用端已知的参数键值对")

@app.post("/plan", summary="生成任务规划")
async def create_plan(request: PlanRequestBody):
    user_query = request.query
    if not user_query:
        raise HTTPException(status_code=400, detail="Query不能为空")

    try:
        logger.info(f"接收到原始请求: '{user_query}'，正在进行查询改写...")
        rewritten_query = query_rewriter_chain.invoke({"user_query": user_query})
        logger.info(f"改写后的查询: '{rewritten_query}'")

        logger.info(f"调用TaskPlanner...")
        plan = planner.plan(rewritten_query, api_json_definitions)
        
        if not plan or "error" in plan or not plan.get("tasks"):
            error_detail = {"error": "无法为您的需求生成有效的执行计划。", "planner_details": plan}
            logger.warning(f"TaskPlanner处理失败: {error_detail}")
            raise HTTPException(status_code=404, detail=error_detail)
        
        logger.info(f"成功生成任务规划: {plan}")
        return plan

    except Exception as e:
        logger.exception(f"处理规划请求时发生未知错误: {e}")
        raise HTTPException(status_code=500, detail={"error": "处理请求时发生内部错误。"})

@app.post("/generate-api-call", summary="生成单次API调用")
async def generate_api_call(request: ApiCallRequestBody):
    user_query = request.query
    if not user_query:
        raise HTTPException(status_code=400, detail="Query不能为空")

    try:
        logger.info(f"接收到API调用生成请求: '{user_query}'，调用ApiRagAgent...")
        result = api_agent.generate_api_call(user_query)
        
        if "error" in result:
            logger.warning(f"Agent处理失败: {result['error']}")
            raise HTTPException(status_code=404, detail=result)
        
        logger.info(f"成功生成API调用信息: {result}")
        return result

    except Exception as e:
        logger.exception(f"处理API调用生成请求时发生未知错误: {e}")
        raise HTTPException(status_code=500, detail={"error": "处理请求时发生内部错误。"})

@app.post("/generate-groovy-script", summary="生成Groovy脚本")
async def generate_groovy_script(request: GroovyRequestBody):
    user_query = request.query
    known_data = request.known_data
    if not user_query:
        raise HTTPException(status_code=400, detail="Query不能为空")

    try:
        logger.info(f"接收到Groovy脚本生成请求: '{user_query}'，已知数据: {known_data}")
        
        # 1. 找到对应的API定义
        api_doc = api_agent._get_api_doc_from_retrieval(user_query)
        if not api_doc:
            raise HTTPException(status_code=404, detail={"error": "无法找到与您的需求匹配的API。"})
        api_definition = api_doc.metadata

        # 2. 生成Groovy脚本
        script = GroovyScriptGenerator.generate(api_definition, known_data)
        
        logger.info(f"成功为API '{api_definition.get('name')}' 生成Groovy脚本。")
        return {"groovy_script": script}

    except Exception as e:
        logger.exception(f"处理Groovy脚本生成请求时发生未知错误: {e}")
        raise HTTPException(status_code=500, detail={"error": "处理请求时发生内部错误。"})

if __name__ == "__main__":
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)
