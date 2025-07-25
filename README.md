# API智能编排与参数补全系统需求


## 一、系统定位

本系统是一个**无状态的API智能编排与参数补全服务**。它接收用户的自然语言需求，并将其**编译**成一个结构化的、可直接被其他服务执行的**API工作流蓝图**。系统本身不执行任何API调用，而是为调用方提供一个包含清晰调用顺序（串行/并行）和已填充参数的完整方案。

核心特性：
- **智能编排**: 自动分析API依赖，规划多步调用的串并联关系。
- **参数补全**: 从用户输入中自动提取并填充API所需参数。
- **缺失提示**: 当参数无法从当前上下文补全时，在返回的蓝图中明确标记`missing`字段，提示调用方需要补充哪些信息。

---

## 二、核心组件与职责

### 1. 数据层：API知识库构建

- **`data/api_dependencies.json`**: 定义了企业所有API的结构化信息（name, description, method, endpoint, params, response等）。是整个系统的事实来源。
- **`vectorization.py`**:
  - **API文档结构化**: 解析`api_dependencies.json`，并使用结构化的Markdown模板为每个API生成一份语义丰富的“API文档”，用于后续的精确检索。
  - **向量化与存储**: 将生成的Markdown文档进行向量化，存入向量数据库（如Chroma），为`api_rag_agent`提供快速检索能力。

### 2. 规划与构建层

- **`src/task_planner.py` (高层架构师)**:
  - **职责**: 制定高层执行计划。
  - **输入**: 用户的自然语言需求 和 `api_dependencies.json`。
  - **处理**: 利用大模型分析API间的输入输出依赖，生成一个**内部使用**的、定义了API调用顺序和串并联关系的抽象执行计划。

- **`api_rag_agent.py` (蓝图构建工程师)**:
  - **职责**: 将抽象计划细化并填充，构建最终的API工作流蓝图。
  - **处理**: 遍历`task_planner`生成的计划，对其中的每一步：
    1.  **检索(Retrieve)**: 使用任务描述，通过`src/vector_stores.py`从向量库中检索出最匹配的API详细文档。
    2.  **打包上下文(Package)**: 整合用户的原始请求、检索到的API文档以及上游步骤的输出。
    3.  **填充(Fill)**: 调用大模型，对当前API进行参数填充。如果信息充足，则填充`body`/`params`；否则，将缺失的参数记录在`missing`字段中。
    4.  **组装(Assemble)**: 将所有处理完成的API任务块，按照计划的结构，组装成最终的嵌套JSON。

- **`src/vector_stores.py`**:
  - **职责**: 为`api_rag_agent`提供精确、快速的API文档检索能力。

### 3. 服务层

- **`workflow.py`**:
  - **职责**: 作为FastAPI服务入口，接收用户请求，完整地协调`task_planner`和`api_rag_agent`的工作，并最终返回构建好的API工作流蓝图。
- **`workflow_test.py`**:
  - **职责**: 提供对整个工作流的端到端测试，覆盖串行、并行、参数缺失等多种场景。

---

## 三、典型流程示意

1.  **用户输入自然语言需求** (包含意图和部分数据)
    ↓
2.  **`workflow.py`** 接收请求，开始处理
    ↓
3.  **`task_planner.py`** 分析全局API，输出**内部执行计划**
    ↓
4.  **`api_rag_agent.py`** 按计划逐步执行：
    - 对计划中的**每一个**API:
        - `vector_stores.py` **检索**API详情
        - 大模型根据(用户输入+API详情+上文) **填充参数**或**标记missing**
    - 将所有结果**组装**成最终的嵌套JSON
    ↓
5.  **`workflow.py`** 返回完整的**API工作流蓝图** (包含调用顺序、URL、已填充参数和`missing`提示)

---
