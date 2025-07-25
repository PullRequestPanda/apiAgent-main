import json
import sys
import os
import requests

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def run_service_test(test_name: str, user_query: str):
    print("=" * 80)
    print(f"🚀 开始测试: {test_name}")
    print(f'   用户需求: "{user_query}')
    print("=" * 80)

    url = "http://localhost:8000/v8/workflow"
    headers = {"Content-Type": "application/json"}
    data = {"query": user_query}

    try:
        response = requests.post(url, headers=headers, data=json.dumps(data))
        response.raise_for_status()
        print("✅ 服务响应成功:")
        response_json = response.json()
        print(json.dumps(response_json, ensure_ascii=False, indent=2))
        print(f"\n>> 计划来源: {response_json.get('plan_source')}")
    except requests.exceptions.RequestException as e:
        print(f"❌ 服务调用失败: {e}")
        if e.response is not None:
            try:
                print("   错误详情:", e.response.json())
            except json.JSONDecodeError:
                print("   无法解析错误响应.")
    print("-" * 80)

if __name__ == "__main__":
    # --- 定义最终架构的、更多样化的测试用例 ---
    test_cases = {
        "action_match_synonym": {
            "description": "测试近义词能否成功匹配到‘请假’动作",
            "query": "老板，我身体不舒服，想明天休假一天，调整下身体。"
        },
        "action_match_long_sentence": {
            "description": "测试在长句和噪声中能否匹配到‘加班’动作",
            "query": "哎，昨晚系统出bug了，我和小明从晚上8点一直搞到11点才修复，我得提交一下加班申请，不然亏大了。"
        },
        "planner_fallback_specific_query": {
            "description": "测试一个清晰但未定义的动作，能否正确回退并规划出单个API",
            "query": "帮我查一下ID是p_123的项目的详细情况。"
        },
        "action_match_with_missing_info": {
            "description": "测试匹配到动作，但缺少大量信息的情况",
            "query": "我要申请加班，就是今天晚上。"
        },
        "intent_conflict_test": {
            "description": "意图混淆边界测试，一句话中包含多个动作的关键词",
            "query": "我昨天加班到很晚，所以今天想请假休息一下。"
        },
        "implicit_intent_query": {
            "description": "隐式意图测试，没有明确的动作词",
            "query": "我的ID是s_999，我想知道我的项目经理是谁。"
        },
        "multi_entity_extraction": {
            "description": "多实体提取测试，一句话提供多个参数",
            "query": "给ID是s_007的员工报一下加班，项目是p_top_secret，就今天，从晚上7点到10点，补偿方式是调休(SHIFT_LEAVE)，原因：上线前准备。"
        },
        "irrelevant_input_test": {
            "description": "无关输入测试，测试系统的兜底能力",
            "query": "今天天气怎么样？"
        }
    }

    print("请确保 `src/main.py` 服务正在另一个终端中运行...")
    print("等待3秒后开始测试...")
    import time
    time.sleep(3)

    # --- 执行测试 ---
    for name, case in test_cases.items():
        run_service_test(name, case["query"])
