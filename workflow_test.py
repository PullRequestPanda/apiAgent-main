import json
import sys
import os

# 确保项目根目录在sys.path中，以便导入模块
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from src.task_planner import TaskPlanner
from src.llm_factory import LLMFactory
from api_rag_agent import ApiRagAgent

def run_workflow_test(test_name: str, user_query: str, api_definitions: list):
    """
    执行一次完整的端到端工作流测试。
    """
    print("=" * 80)
    print(f"🚀 开始测试: {test_name}")
    print(f'   用户需求: "{user_query}"')
    print("=" * 80)

    # 1. 初始化所有组件
    llm = LLMFactory.create_llm(provider='dashscope')
    planner = TaskPlanner(llm)
    api_agent = ApiRagAgent()

    # 2. 调用 TaskPlanner 生成高层计划
    print("\n[Step 1/2] 正在调用 TaskPlanner 生成工作流计划...")
    plan = planner.plan(user_query, api_definitions)
    
    if "error" in plan or "workflow" not in plan:
        print("❌ 任务规划失败!")
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return

    print("✅ 计划生成成功:")
    print(json.dumps(plan, ensure_ascii=False, indent=2))

    # 3. 调用 ApiRagAgent 根据计划构建最终蓝图
    print("\n[Step 2/2] 正在调用 ApiRagAgent 构建最终蓝图...")
    blueprint = api_agent.build_workflow_blueprint(plan, user_query)

    print("\n🎉 测试完成! 最终生成的API工作流蓝图如下:")
    print("-" * 80)
    print(json.dumps(blueprint, ensure_ascii=False, indent=2))
    print("-" * 80)
    print("\n\n")

if __name__ == "__main__":
    # 加载API定义文件
    try:
        API_JSON_PATH = os.path.join(os.path.dirname(__file__), "data/api.json")
        with open(API_JSON_PATH, "r", encoding="utf-8") as f:
            api_json_definitions = json.load(f)
    except FileNotFoundError:
        print(f"错误：API定义文件未找到，请确保 {API_JSON_PATH} 存在。")
        api_json_definitions = []

    # --- 针对请假加班系统的新测试用例 ---
    test_cases = {
        "full_leave_process": {
            "description": "核心串行流程，模拟完整的请假申请",
            "query": "帮我提交一个从2025-08-01到2025-08-05的年假(ANNUAL_LEAVE)申请，原因是我要去度假。"
        }
    }

    # --- 执行测试 ---
    if api_json_definitions:
        for name, case in test_cases.items():
            run_workflow_test(name, case["query"], api_json_definitions)
    else:
        print("无法执行测试，因为API定义为空。")