# 智能API规划与调用系统

## 一、系统定位

本系统是一个**智能API规划与调用服务**，它提供两大核心能力，旨在将用户的自然语言需求，高效、准确地转化为机器可执行的指令。

- **`/plan` (任务规划接口)**: 接收一个复杂的、可能包含多个步骤的自然语言需求，并将其**编译**成一个结构化的、定义了清晰执行顺序（串行/并行）的**任务计划**。
- **`/generate-api-call` (API调用生成接口)**: 接收一个相对直接的自然语言需求，通过“检索-精排”的两阶段流程找到最匹配的API，并利用大模型自动填充参数，最终生成一个可直接被其他服务执行的**API调用详情**。

## 二、核心组件与职责

### 1. 数据层：API知识库

- **`data/api.json`**: 定义了企业所有API的结构化信息（name, description, method, endpoint, params, response等）。是整个系统进行规划和检索的唯一事实来源。
- **`scripts/vectorization.py`**: 负责读取`api.json`，将每个API的描述信息进行向量化，并构建一个用于快速语义检索的向量数据库（ChromaDB）。

### 2. 服务层 (src/main.py)

- **职责**: 作为FastAPI的服务入口，统一协调以下所有组件，并对外提供`/plan`和`/generate-api-call`两个核心接口。

- **查询改写 (Query Rewriting)**: 在处理`/plan`请求时，会先调用一个大模型，将用户模糊的、口语化的请求，改写成一个逻辑更清晰、信息更丰富的指令，为后续的精准规划做准备。

### 3. 规划与生成层

- **`src/planning/task_planner.py` (任务规划师)**:
  - **职责**: 制定高层执行计划。
  - **输入**: 经过改写的、清晰的用户指令 和 `api.json`中的完整API定义。
  - **处理**: 利用大模型分析API间的**数据流依赖关系**（一个API的输出是否能作为另一个API的输入），生成一个定义了API调用顺序和串并联关系的结构化任务计划。

- **`src/agent/api_rag_agent.py` (API调用生成器)**:
  - **职责**: 处理单个API的调用生成请求。
  - **处理流程**: 
    1.  **检索(Retrieve)**: 使用`ApiRetriever`，通过“向量检索+Reranker精排”的两阶段流程，从向量库中精准地找出与用户需求最匹配的API。
    2.  **填充(Fill)**: 调用大模型，根据用户需求和API定义，自动填充API所需的参数。
    3.  **组装(Assemble)**: 将所有信息（包括方法、URL、已填充参数、缺失参数等）组装成一个完整的API调用详情JSON。

- **`src/retrieval/api_retriever.py` (API检索器)**:
  - **职责**: 为`ApiRagAgent`提供精确、高效的API检索能力。

### 4. 测试

- **`tests/test_workflow.py`**: 提供对两大核心接口的单元测试，使用`unittest.mock`模拟大模型行为，确保核心逻辑的稳定与正确。

## 三、典型流程示意

### 流程一：任务规划 (`/plan`)

1.  **用户输入复杂需求**: `"帮我申请请假和加班"`
    ↓
2.  **`main.py` -> 查询改写**: 改写为 `"首先获取我的员工信息，然后并行为我提交请假和加班申请。"`
    ↓
3.  **`task_planner.py`** 分析改写后的指令和API定义，输出**任务计划JSON**

### 流程二：API调用生成 (`/generate-api-call`)

1.  **用户输入直接需求**: `"我要请假"`
    ↓
2.  **`api_rag_agent.py`** 开始处理:
    - `api_retriever.py` **检索并精排**出`提交请假申请`这个API。
    - 大模型**填充参数**，并找出需要用户补充的`missing`字段。
    ↓
3.  返回**API调用详情JSON**

---

## 四、环境配置与启动

### 1. 安装依赖

确保你已经安装了Python 3.8+。然后，在项目根目录下运行以下命令，安装所有必需的库：

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

项目需要API密钥才能与大模型服务进行交互。请在项目根目录下创建一个名为`.env`的文件，并根据你选择的服务商，在其中**提供你自己的API密钥**：

```dotenv
# .env (这是一个示例，请填入你自己的有效密钥)

# 如果你使用阿里云通义千问 (推荐)
DASHSCOPE_API_KEY="sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

# 如果你使用OpenAI
# OPENAI_API_KEY="sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
# OPENAI_BASE_URL="https://api.openai.com/v1" # 如果需要代理，请修改此项
```

**重要**: `.env`文件已被添加到`.gitignore`中，它不会、也不应该被提交到版本库中。

同时，你可以在`config/settings.py`文件中，修改`llm_provider`的默认值来切换使用`'dashscope'`或`'openai'`。

### 3. 生成向量数据

在第一次启动服务前，你需要为`data/api.json`中的API文档生成向量索引。运行以下命令：

```bash
python scripts/vectorization.py
```

该脚本会读取API定义，在`vector_store`目录下创建本地的向量数据库。

### 4. 启动服务

一切准备就绪后，运行以下命令来启动FastAPI应用：

```bash
python src/main.py
```

服务启动后，你可以在浏览器中访问 `http://127.0.0.1:8000/docs` 来查看和测试API接口。

### 5. 运行测试

为了确保所有核心功能都按预期工作，你可以随时运行项目自带的单元测试：

```bash
python tests/test_workflow.py
```