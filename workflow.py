import json
import sys
import os
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# 确保项目根目录在sys.path中，以便导入模块
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from src.task_planner import TaskPlanner
from src.llm_factory import LLMFactory
from api_rag_agent import ApiRagAgent

# --- 1. 全局对象初始化 ---
# 在服务启动时加载一次，避免每次请求都重新加载
print("正在初始化服务，加载模型和数据...")

llm = LLMFactory.create_llm(provider='dashscope')
planner = TaskPlanner(llm)
api_agent = ApiRagAgent()

# 加载API定义文件
try:
    API_JSON_PATH = os.path.join(os.path.dirname(__file__), "data/api.json")
    with open(API_JSON_PATH, "r", encoding="utf-8") as f:
        api_json_definitions = json.load(f)
except FileNotFoundError:
    print(f"错误：API定义文件未找到，请确保 {API_JSON_PATH} 存在。")
    # 在生产环境中，如果关键数据文件缺失，服务应该启动失败
    sys.exit(1)

print("服务初始化完成。")

# --- 2. FastAPI应用定义 ---
app = FastAPI(
    title="API智能编排与参数补全服务",
    description="接收自然语言需求，并将其编译成一个结构化的API工作流蓝图。",
    version="1.0.0"
)

class WorkflowRequest(BaseModel):
    query: str

@app.post("/v1/workflow", summary="生成API工作流蓝图")
async def create_workflow_blueprint(request: WorkflowRequest):
    """
    接收用户的自然语言查询，并执行以下两步操作：
    1.  **规划(Plan)**: 调用`TaskPlanner`生成一个结构化的工作流计划。
    2.  **构建(Build)**: 调用`ApiRagAgent`根据该计划，填充参数并构建最终的API工作流蓝图。
    
    返回的蓝图是一个可被其他服务直接解析和执行的JSON对象。
    """
    user_query = request.query
    if not user_query:
        raise HTTPException(status_code=400, detail="Query不能为空")

    # --- 执行核心逻辑 ---
    # 1. 调用 TaskPlanner 生成高层计划
    plan = planner.plan(user_query, api_json_definitions)
    if "error" in plan or "workflow" not in plan:
        raise HTTPException(status_code=500, detail={"error": "任务规划失败", "details": plan})

    # 2. 调用 ApiRagAgent 根据计划构建最终蓝图
    blueprint = api_agent.build_workflow_blueprint(plan, user_query)
    if "error" in blueprint:
        raise HTTPException(status_code=500, detail={"error": "工作流蓝图构建失败", "details": blueprint})

    return blueprint

# --- 3. 服务启动入口 ---
if __name__ == "__main__":
    # 使用uvicorn启动服务，建议在生产环境中使用Gunicorn等多进程管理器
    uvicorn.run(app, host="0.0.0.0", port=8000)
