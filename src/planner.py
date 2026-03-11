# src/planner.py
from langchain_core.prompts import PromptTemplate
import json
import re

class Planner:
    """
    规划器 - 将复杂需求拆解为可执行的任务列表
    """

    def __init__(self, llm, knowledge_retriever=None):
        """
        初始化规划器

        Args:
            llm: 语言模型实例
            knowledge_retriever: 知识库检索器实例（可选）
        """
        self.llm = llm
        self.knowledge_retriever = knowledge_retriever
        self.prompt_template = """
你是一个生信数据分析任务规划专家。

【任务】:
将用户的复杂需求拆解为一系列可执行的子任务。

【当前数据状态 (Context)】:
{data_context}

【Notebook 历史上下文】:
{notebook_history}

【已完成的任务列表】:
{completed_tasks}

【知识库检索结果】:
{knowledge_base}

【拆解原则】:
1. **上下文感知**：仔细阅读当前数据状态和历史记录，确保任务合理
2. **独立清晰**：每个任务应该是独立、清晰、可执行的分析步骤
3. **逻辑顺序**：按照数据分析的逻辑顺序排列（如：加载→质控→标准化→降维→聚类→可视化）
4. **避免重复**：如果某些步骤已在历史记录中完成，不要重复包含
5. **具体明确**：每个任务只包含一个明确的分析目标，避免过于笼统
6. **知识库参考**：如果知识库中有相关的标准流程或最佳实践，请参考这些内容制定规划

【智能拆解规则】:
1. **数据为空**：如果当前无数据上下文，首先添加数据加载任务
2. **步骤衔接**：根据已完成的任务，判断下一个应该执行的步骤
3. **参数推断**：根据数据状态（细胞数、基因数等）推断合适的参数范围
4. **跳过已完成**：如果历史记录显示某些分析已完成（如PCA、聚类），跳过这些步骤
5. **知识库参数**：如果知识库提供了推荐的参数或标准流程，使用这些信息

【常见生信分析流程参考】:
- **单细胞RNA-seq**:
  * 初级：读取数据→质量控制→细胞过滤→标准化→特征基因选择
  * 高级：降维(PCA)→聚类→UMAP/tSNE可视化→差异分析→细胞类型注释
  * 可选：批次效应校正→轨迹分析→拟时序分析
- **常规转录组**:
  * 读取数据→质量控制→标准化→差异表达分析→富集分析→可视化
- **蛋白质组学**:
  * 读取数据→质量控制→标准化→差异分析→功能富集→网络分析

【输出格式】:
```json
{{
  "tasks": [
    {{"id": 1, "task": "读取单细胞数据文件并创建Seurat对象"}},
    {{"id": 2, "task": "进行质量控制，统计细胞和基因数量"}},
    {{"id": 3, "task": "标准化数据并识别高变基因"}},
    {{"id": 4, "task": "执行PCA降维分析，选择合适的PC数量"}},
    {{"id": 5, "task": "进行细胞聚类分析（分辨率0.5）"}},
    {{"id": 6, "task": "生成UMAP降维可视化"}}
  ]
}}
```

【示例场景 1 - 数据为空】:
用户需求："帮我完成单细胞数据的预处理和聚类分析"
数据状态：当前无数据上下文
规划结果：
1. 读取单细胞数据文件（readRDS或创建Seurat对象）
2. 进行质量控制和细胞过滤
3. 标准化数据并识别高变基因
4. 执行PCA降维分析
5. 进行细胞聚类
6. 生成UMAP可视化

【示例场景 2 - 已有部分数据】:
用户需求："帮我完成聚类分析和可视化"
数据状态：sc_obj（Seurat对象，3000细胞，已完成质控和标准化）
规划结果：
1. 执行PCA降维分析（如已完成则跳过）
2. 进行细胞聚类分析
3. 生成UMAP可视化
4. 绘制各cluster的marker基因小提琴图

【用户需求】: {user_input}

请生成任务规划:
"""

    def create_plan(self, user_input, data_context="", notebook_history="", completed_tasks=""):
        """
        创建任务规划
        :param user_input: 用户的原始需求
        :param data_context: 当前数据上下文信息
        :param notebook_history: Notebook 历史上下文
        :param completed_tasks: 已完成的任务列表
        :return: 任务列表
        """
        # 检索知识库
        knowledge_base_content = ""
        if self.knowledge_retriever:
            print("    [规划器] 正在检索知识库...")
            knowledge_base_content = self.knowledge_retriever.retrieve(user_input)
            if knowledge_base_content:
                print("    [规划器] 已检索到相关知识")
            else:
                print("    [规划器] 未检索到相关知识")

        prompt = PromptTemplate(
            input_variables=["user_input", "data_context", "notebook_history", "completed_tasks", "knowledge_base"],
            template=self.prompt_template
        )

        if not data_context:
            data_context = "当前无数据上下文。"
        if not notebook_history:
            notebook_history = "暂无历史代码。"
        if not completed_tasks:
            completed_tasks = "暂无已完成任务。"

        formatted = prompt.format(
            user_input=user_input,
            data_context=data_context,
            notebook_history=notebook_history,
            completed_tasks=completed_tasks,
            knowledge_base=knowledge_base_content if knowledge_base_content else "（未检索到相关知识）"
        )

        response = self.llm.invoke(formatted)
        text = response.content if hasattr(response, 'content') else str(response)

        try:
            # 提取 JSON
            pattern = r"```json(.*?)```"
            match = re.search(pattern, text, re.DOTALL)
            json_str = match.group(1).strip() if match else text.strip()
            plan_data = json.loads(json_str)

            tasks = plan_data.get('tasks', [])

            if not tasks:
                print("    [警告] 规划器未生成有效任务列表")
                return []

            print(f"\n{'='*50}")
            print(f">>> [规划器] 已生成 {len(tasks)} 个子任务:")
            for task in tasks:
                print(f"    {task['id']}. {task['task']}")
            print(f"{'='*50}\n")

            return tasks

        except Exception as e:
            print(f"    [错误] 规划生成失败: {e}")
            print(f"    原始返回: {text[:200]}...")
            return []

    def is_complex_task(self, user_input):
        """
        判断是否需要拆解为规划（简单判断）
        :param user_input: 用户输入
        :return: 是否需要规划
        """
        # 简单任务的关键词（这些通常不需要拆解）
        simple_keywords = [
            "画", "显示", "查看", "修改", "删除", "添加",
            "运行", "执行", "继续", "下一个", "查看规划",
            "解释", "说明", "为什么", "怎么样"
        ]

        txt = user_input.strip()
        for keyword in simple_keywords:
            if txt.startswith(keyword):
                return False

        # 复杂任务的关键词（这些通常需要拆解）
        complex_keywords = [
            "完成", "进行", "帮我做", "分析", "处理", "构建",
            "流程", "完整", "全部", "从头"
        ]

        for keyword in complex_keywords:
            if keyword in txt:
                return True

        # 默认情况下，如果输入长度超过20个字，倾向于需要规划
        return len(txt) > 20
