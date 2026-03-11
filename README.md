# 数据分析 Agentic Workflow

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://www.python.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Production%20Ready-brightgreen.svg)]()

基于 AI 的交互式数据分析系统，专为生物信息学设计。

## ✨ 核心特性

- 🎯 **智能规划**: 复杂任务自动拆解为可管理的子任务
- 💬 **智能问答**: 基于上下文的代码解释和分析建议
- 🎮 **用户控制**: 每步都需确认，保持完全主导权
- 📊 **可视化**: 所有内容在 Jupyter Notebook 中展示

## 🚀 快速开始

### 前提条件
- 已完成 [环境配置](#-环境配置)
- Ollama 服务已运行（或配置了其他 LLM API）

### 1. 启动系统
```bash
# 激活环境
conda activate cellagent

# 启动分析系统
python main.py
```

### 2. 创建规划（复杂任务）
```
帮我完成单细胞数据的预处理和聚类分析
```

### 3. 执行任务
```
继续
```

### 4. 运行代码
```
[回车]
```

### 5. 提问
```
这个结果是什么意思？
```

## 📝 命令速查

| 命令 | 功能 |
|------|------|
| `帮我完成单细胞数据的预处理和聚类分析` | 创建任务规划（自动拆解复杂任务）|
| `按计划进行` / `开始执行规划` | 按计划执行第一个任务 |
| `继续` / `下一个` | 执行下一个任务 |
| `查看规划` | 显示当前进度 |
| `画个 UMAP 图` | 直接生成代码 |
| `修改这一步，把参数改为0.5` | 修改当前 Cell |
| `修复这个错误` | 修复当前 Cell |
| `解释一下第5步` | 咨询顾问 |
| `[回车]` | 运行代码 |
| `q` / `exit` | 退出 |

## 📚 文档

### 快速参考
- [规划器快速参考](PLANNER_QUICK_REFERENCE.md) - 任务规划命令速查
- [QA 快速参考](QA_QUICK_REFERENCE.md) - 智能问答命令速查

### 详细指南
- [规划器使用指南](PLANNER_USAGE_GUIDE.md) - 完整规划器教程
- [QA 使用指南](QA_USAGE_GUIDE.md) - 顾问功能完整教程
- [功能总结](FEATURE_SUMMARY.md) - 所有功能特性说明

### 技术文档
- [架构优化建议](ARCHITECTURE_OPTIMIZATION.md) - 系统架构设计
- [Bug 修复总结](BUG_FIXES_SUMMARY.md) - 已修复问题记录
- [最终验收清单](FINAL_CHECKLIST.md) - 功能验收标准
- [设计理念](设计理念.md) - 系统设计思路
- [知识库集成说明](知识库集成说明.md) - 知识库使用指南

## 🎯 使用场景

### 场景 1: 完整分析流程
```
用户: 帮我完成单细胞数据的预处理和聚类分析
系统: [规划器自动拆解为 6 个子任务]

用户: 按计划进行
系统: [执行任务 1，生成代码]

用户: [回车运行代码]

用户: 这个质控结果怎么样？
系统: [顾问解释结果并提供建议]

用户: 继续
系统: [执行任务 2]
```

### 场景 2: 快速单步操作
```
用户: 画个 UMAP 图
系统: [直接生成代码]

用户: [回车]
系统: [图形] 图片已生成

用户: 这个图显示了什么？
系统: [顾问解读图表]
```

## 🏗️ 架构

```
用户输入
    ↓
ChatRouter (指令路由)
    ↓
    ├─→ 复杂需求 → Planner (新建规划) → PlanManager
    ├─→ 按计划进行 → PlanManager (获取任务) → ChatRouter (重新识别) → CodeProgrammer → 代码生成
    ├─→ [规划任务] → 快速识别 → CodeProgrammer → 代码生成
    ├─→ 简单需求 → CodeProgrammer → 代码生成
    ├─→ 提问 → ProjectAdvisor → 智能回答
    ├─→ 运行 → UnifiedKernelSession → 执行代码
    └─→ Cell 操作 → NotebookManager
```

## 📁 项目结构

```
.
├── main.py                      # 主程序入口
├── ui_app.py                    # UI 界面（可选）
├── llm_config.json              # LLM 配置文件
├── current_plan.json            # 当前规划存储
├── requirements_all.txt         # 完整依赖列表
├── requirements_ui.txt          # UI 依赖列表
├── src/                         # 源代码目录
│   ├── llm_factory.py          # LLM 工厂（支持多种后端）
│   ├── chat_router.py          # 指令路由器
│   ├── planner.py              # 任务规划器
│   ├── plan_manager.py         # 规划管理器
│   ├── code_programmer.py      # 代码生成器
│   ├── code_modifier.py        # 代码修改器
│   ├── project_advisor.py      # 项目顾问
│   ├── knowledge_retriever.py  # 知识库检索器
│   ├── data_summarizer.py      # 数据总结器
│   ├── nbManager.py            # Notebook 管理器
│   └── kernel_session.py       # 内核会话管理
├── 知识库/                      # 生物信息学知识库
│   ├── Seurat/                 # Seurat 相关文档
│   ├── scanpy/                 # Scanpy 相关文档
│   └── ...                     # 其他主题文档
├── test_data/                  # 测试数据
├── analysis_result.ipynb       # 分析结果 Notebook
├── test_llm.py                 # LLM 测试脚本
├── test_knowledge_retrieval.py # 知识库测试脚本
└── docs/                       # 详细文档（如有的话）
```

## 📦 核心组件

- **Planner**: 智能规划器，将复杂需求自动拆解为可执行的子任务列表
- **PlanManager**: 规划管理器，存储任务规划并追踪执行进度
- **ChatRouter**: 指令路由器，识别用户意图并分发到对应组件
- **ProjectAdvisor**: 项目顾问，智能问答
- **CodeProgrammer**: 代码生成器
- **CodeModifier**: 代码修改器，精准修改单个 Cell
- **DataSummarizer**: 数据总结器
- **NotebookManager**: Notebook 管理
- **UnifiedKernelSession**: 内核管理

## ✅ 测试状态

```
✓ Bug 修复测试: 4/4 通过
✓ 规划器测试: 4/4 通过
✓ QA 功能测试: 5/5 通过
总计: 13/13 通过
```

## 🔧 环境配置

### 系统要求

- **操作系统**: Windows / macOS / Linux
- **Python**: 3.8 或更高版本
- **R**: 4.0 或更高版本（用于生物信息学数据分析）
- **内存**: 建议 16GB 以上（运行大型 LLM 模型）

### 1. Python 环境安装

#### 创建 Conda 环境（推荐）

```bash
# 创建新的 Conda 环境
conda create -n cellagent python=3.10 -y

# 激活环境
conda activate cellagent
```

#### 安装 Python 依赖

```bash
# 安装基础依赖
pip install -r requirements_ui.txt

# 或安装完整依赖（包含所有 LLM 支持）
pip install -r requirements_all.txt
```

### 2. R 环境配置

#### 安装 R 和 R 包

系统需要先安装 R 环境，然后安装以下关键包：

```r
# 在 R 中执行
install.packages("remotes")
remotes::install_github("satijalab/seurat")
install.packages("dplyr")
install.packages("ggplot2")
```

#### 配置 Jupyter 内核支持 R

```bash
# 安装 IRkernel
conda install -c r r-irkernel

# 注册 R 内核
R -e "IRkernel::installspec()"
```

### 3. LLM 配置

系统支持多种 LLM 后端，推荐使用 **Ollama** 进行本地部署。

#### 方案 A: 使用 Ollama（推荐，免费本地运行）

1. **安装 Ollama**

   - Windows: 下载 [Ollama 安装包](https://ollama.ai/download)
   - macOS: `brew install ollama`
   - Linux: `curl -fsSL https://ollama.ai/install.sh | sh`

2. **下载模型**

   ```bash
   # 下载推荐的模型
   ollama pull qwen2.5-coder:14b

   # 或其他模型（根据机器配置选择）
   # ollama pull llama3.1:8b
   # ollama pull deepseek-coder:6.7b
   ```

3. **启动 Ollama 服务**

   ```bash
   # Ollama 安装后会自动启动服务
   # 确认服务状态
   ollama list
   ```

4. **配置 LLM**

   编辑 `llm_config.json` 文件：

   ```json
   {
     "llm_type": "ollama",
     "model": "qwen2.5-coder:14b",
     "base_url": "http://localhost:11434",
     "api_key": "sk-dummy",  // Ollama 不需要真实 API Key
     "temperature": 0.1,
     "max_tokens": null
   }
   ```

#### 方案 B: 使用 OpenAI API

1. 获取 API Key: [OpenAI Platform](https://platform.openai.com/api-keys)

2. 配置 `llm_config.json`:

   ```json
   {
     "llm_type": "openai",
     "model": "gpt-4",
     "api_key": "your-api-key-here",
     "base_url": "https://api.openai.com/v1",
     "temperature": 0.1,
     "max_tokens": 4096
   }
   ```

#### 方案 C: 使用其他兼容 OpenAI 的 API

系统支持任何兼容 OpenAI API 格式的服务（如 Azure、通义千问等）：

```json
{
  "llm_type": "openai",
  "model": "qwen-plus",
  "api_key": "your-api-key",
  "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
  "temperature": 0.1
}
```

### 4. 知识库配置（可选）

系统内置了生物信息学知识库，无需额外配置。如需自定义知识库：

1. 将文档放入 `知识库/` 目录
2. 系统会自动索引并检索

### 5. 验证安装

```bash
# 测试 LLM 连接
python test_llm.py

# 测试知识库检索
python test_knowledge_retrieval.py
```

## 📊 功能对比

| 功能 | 传统方式 | 本系统 |
|------|---------|--------|
| 任务规划 | 手动规划 | ✅ 自动拆解 |
| 代码生成 | 手动编写 | ✅ AI 生成 |
| 代码解释 | 查文档 | ✅ 即时问答 |
| 错误诊断 | 自己调试 | ✅ 顾问建议 |
| 进度追踪 | 手动记录 | ✅ 自动追踪 |
| 断点续传 | 不支持 | ✅ 自动恢复 |

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

---

**版本**: 2.0
**状态**: ✅ 生产就绪
**最后更新**: 2026-03-11

---

## 🌟 Star History

如果这个项目对你有帮助，请给一个 Star ⭐️

[![Star History Chart](https://api.star-history.com/svg?repos=yourusername/data-analysis-agent&type=Date)](https://star-history.com/#yourusername/data-analysis-agent&Date)
