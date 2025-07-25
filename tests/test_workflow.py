import unittest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
import sys
import os

# 将项目根目录添加到sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 必须在sys.path设置后，才能导入main
from src.main import app

class TestApiRoutes(unittest.TestCase):

    def setUp(self):
        """在每个测试用例运行前执行"""
        self.client = TestClient(app)

    @patch('src.main.query_rewriter_chain')
    @patch('src.planning.task_planner.TaskPlanner.plan')
    def test_plan_endpoint_success(self, mock_plan, mock_rewriter):
        """测试 /plan 接口在成功情况下的表现"""
        print("\n--- 测试 /plan 接口成功场景 ---")
        
        # 1. 设定模拟对象的返回值
        mock_rewriter.ainvoke.return_value = "首先获取我的员工信息，然后并行为我提交请假和加班申请。"
        mock_plan.return_value = {
            "type": "sequential",
            "tasks": [
                {"api_name": "获取员工项目信息", "description": "获取员工的基础信息。"},
                {
                    "type": "parallel",
                    "tasks": [
                        {"api_name": "提交请假申请", "description": "提交请假申请。"},
                        {"api_name": "提交加班申请", "description": "提交加班申请。"}
                    ]
                }
            ]
        }

        # 2. 发起API请求
        response = self.client.post("/plan", json={"query": "帮我申请请假和加班"})

        # 3. 断言结果
        self.assertEqual(response.status_code, 200)
        response_json = response.json()
        self.assertEqual(response_json['type'], 'sequential')
        self.assertIn('tasks', response_json)
        print("✅ /plan 接口成功场景测试通过。")

    @patch('src.agent.api_rag_agent.ApiRagAgent.generate_api_call')
    def test_generate_api_call_success(self, mock_generate_call):
        """测试 /generate-api-call 接口在成功情况下的表现"""
        print("\n--- 测试 /generate-api-call 接口成功场景 ---")

        # 1. 设定模拟对象的返回值
        mock_generate_call.return_value = {
            "description": "通过邮箱地址解锁一个被锁定的用户账号。",
            "method": "POST",
            "url": "/api/v1/users/unlock",
            "missing": [
                {
                    "name": "email",
                    "description": "需要解锁的用户的邮箱地址",
                }
            ]
        }

        # 2. 发起API请求
        response = self.client.post("/generate-api-call", json={"query": "帮我解锁用户 a@b.com"})

        # 3. 断言结果
        self.assertEqual(response.status_code, 200)
        response_json = response.json()
        self.assertEqual(response_json['method'], 'POST')
        self.assertIn('missing', response_json)
        print("✅ /generate-api-call 接口成功场景测试通过。")

    @patch('src.main.query_rewriter_chain')
    def test_plan_endpoint_empty_query(self, mock_rewriter):
        """测试 /plan 接口在查询为空时的表现"""
        print("\n--- 测试 /plan 接口查询为空场景 ---")
        response = self.client.post("/plan", json={"query": ""})
        self.assertEqual(response.status_code, 400)
        print("✅ /plan 接口查询为空场景测试通过。")

if __name__ == '__main__':
    print("开始执行单元测试...")
    unittest.main()
