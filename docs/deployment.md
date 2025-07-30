# 智能API规划与调用系统 - 部署手册

本手册将指导您如何从零开始，在您的本地环境中成功部署并运行本系统。

## 1. 系统要求

- **Python**: 3.8 或更高版本
- **Git**: 用于克隆代码库
- **网络连接**: 用于下载依赖库和与大模型API进行交互

## 2. 部署步骤

### 第1步：克隆代码库

打开您的终端，将本项目的代码库克隆到您的本地机器上。

```bash
git clone <your-repository-url>
cd <repository-name>
```

### 第2步：安装依赖

我们使用`requirements.txt`文件来管理项目的所有Python依赖。运行以下命令来安装它们。建议在一个虚拟环境中进行此操作。

```bash
# 可选，但推荐：创建一个虚拟环境
python -m venv venv
source venv/bin/activate  # 在Windows上，使用 `venv\Scripts\activate`

# 安装所有依赖
pip install -r requirements.txt
```

### 第3步：配置环境变量

API密钥等敏感信息必须通过环境变量进行配置。在项目的根目录下，创建一个名为`.env`的新文件。

```bash
touch .env
```

然后，打开`.env`文件，并根据您选择的大模型服务商，填入您自己的API密钥。这是一个示例：

```dotenv
# .env (这是一个示例，请务必填入你自己的有效密钥)

# 如果你使用阿里云通义千问 (推荐)
DASHSCOPE_API_KEY="sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

# 如果你使用OpenAI
# OPENAI_API_KEY="sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
# OPENAI_BASE_URL="https://api.openai.com/v1" # 如果需要代理，请修改此项
```

**重要**: 
- 您可以在`config/settings.py`文件中，修改`llm_provider`的默认值来切换使用`'dashscope'`或`'openai'`。
- `.env`文件已被项目的`.gitignore`文件忽略，它不会被提交到版本库中，请放心填写。

### 第4步：生成向量数据库

在第一次启动服务前，您必须为`data/api.json`中的API文档生成本地的向量索引。运行以下命令：

```bash
python scripts/vectorization.py
```

该脚本会读取API定义，并在项目的根目录下创建一个`vector_store/`目录，其中包含了ChromaDB的数据库文件。这个目录同样被`.gitignore`忽略。

### 第5步：启动服务

一切准备就绪！运行以下命令来启动FastAPI应用：

```bash
python src/main.py
```

如果一切顺利，您将在终端看到类似以下的输出，表明服务已成功启动：

```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

## 3. 验证部署

### 3.1. 访问API文档

服务启动后，打开您的浏览器，访问 `http://127.0.0.1:8000/docs`。

您应该能看到FastAPI自动生成的交互式API文档页面。您可以在这个页面上，直接测试我们提供的所有接口（`/plan`, `/generate-api-call`, `/generate-groovy-script`）。

### 3.2. 查看日志

系统运行过程中产生的所有日志，都会被记录在根目录下的`logs/app.log`文件中。如果您遇到任何问题，检查这个文件是排查错误的第一步。

### 3.3. 运行单元测试

为了确保所有核心功能都按预期工作，您可以随时运行项目自带的单元测试。这不需要启动主服务。

```bash
python tests/test_workflow.py
```

如果所有测试都通过，说明您的部署环境和代码都是健康、正确的。
