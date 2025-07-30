import json
from typing import Dict, Any, List

class GroovyScriptGenerator:
    """根据API定义和已知数据，生成Groovy脚本。"""

    @staticmethod
    def generate(api_definition: Dict[str, Any], known_data: Dict[str, Any]) -> str:
        """
        生成Groovy脚本的核心方法。

        Args:
            api_definition: 单个API的完整定义，来自api.json。
            known_data: 用户提供的、已知的参数值。

        Returns:
            一段格式化好的、可直接使用的Groovy脚本字符串。
        """
        api_name = api_definition.get("name", "未知API")
        http_method = api_definition.get("method", "GET").upper()
        endpoint = api_definition.get("endpoint", "")
        
        # 从metadata中安全地解析params_json字符串
        try:
            api_params_str = api_definition.get("params_json", "[]")
            api_params = json.loads(api_params_str)
            if not isinstance(api_params, list):
                api_params = []
        except (json.JSONDecodeError, TypeError):
            api_params = []

        # 1. 构建请求体和缺失参数列表
        request_body = {}
        missing_params = []
        for param in api_params:
            param_name = param.get("name")
            if param_name in known_data:
                request_body[param_name] = known_data[param_name]
            elif param.get("required", False):
                missing_params.append(param_name)

        # 2. 生成Groovy脚本字符串
        script_template = f"""
import groovy.json.JsonOutput
import groovy.json.JsonSlurper

// 这是一个由智能助手生成的、用于调用“{api_name}”API的Groovy脚本。

// --- 1. API基础信息 ---
def apiUrl = "https://your-api-host.com{endpoint}" // TODO: 请将域名替换为实际地址
def httpMethod = "{http_method}"

// --- 2. 构建请求体 (Request Body) ---
'''
缺失的必要参数 (请在执行前补充):
{GroovyScriptGenerator._format_missing_params(missing_params)}
'''

def requestBody = {GroovyScriptGenerator._format_request_body(request_body)}

// --- 3. 发起HTTP请求 ---
try {{
    def connection = (HttpURLConnection) new URL(apiUrl).openConnection()
    connection.setRequestMethod(httpMethod)
    connection.setRequestProperty("Content-Type", "application/json")
    connection.setDoOutput(true)

    // 发送请求体
    def writer = new OutputStreamWriter(connection.outputStream)
    writer.write(JsonOutput.toJson(requestBody))
    writer.flush()
    writer.close()

    // --- 4. 处理响应 ---
    def responseCode = connection.getResponseCode()
    println "Response Code: ${{responseCode}}"

    if (responseCode == 200) {{
        def responseStream = connection.getInputStream()
        def responseText = responseStream.getText("UTF-8")
        def jsonResponse = new JsonSlurper().parseText(responseText)
        
        println "请求成功!"
        println "响应内容: ${{JsonOutput.prettyPrint(JsonOutput.toJson(jsonResponse))}}"
        
        // 成功后，可以将响应的关键信息更新回状态
        // this.some_variable = jsonResponse.some_field

    }} else {{
        def errorStream = connection.getErrorStream()
        def errorText = errorStream ? errorStream.getText("UTF-8") : "No error details available."
        println "请求失败!"
        println "错误详情: ${{errorText}}"
    }}

}} catch (Exception e) {{
    println "执行脚本时发生异常: ${{e.getMessage()}}"
    e.printStackTrace()
}}
"""
        return script_template

    @staticmethod
    def _format_missing_params(params: List[str]) -> str:
        if not params:
            return "无"
        return "\n".join([f"- {p}" for p in params])

    @staticmethod
    def _format_request_body(body: Dict[str, Any]) -> str:
        if not body:
            return "[:]";  # 空的Groovy Map
        
        # 将Python字典转换为Groovy的Map字面量字符串
        # 例如: {"name": "John", "age": 30} -> [name: "John", age: 30]
        items = []
        for key, value in body.items():
            # 对字符串值添加双引号，其他类型直接转换
            if isinstance(value, str):
                formatted_value = f'"""{value}"""' # 使用三引号以支持多行和特殊字符
            else:
                formatted_value = str(value)
            items.append(f"{key}: {formatted_value}")
        
        return f"[{', '.join(items)}]"