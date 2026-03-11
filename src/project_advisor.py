# src/project_advisor.py
from langchain_core.prompts import PromptTemplate

class ProjectAdvisor:
    def __init__(self, llm, knowledge_retriever=None):
        """
        初始化项目顾问
        
        Args:
            llm: 语言模型实例
            knowledge_retriever: 知识库检索器实例（可选）
        """
        self.llm = llm
        self.knowledge_retriever = knowledge_retriever
        
        self.prompt_template = """
你是一个生物信息学高级顾问。
你拥有当前项目的**完整执行历史**和**最新数据状态**。
请基于这些上下文，回答用户的问题。

【1. 全局数据状态 (Memory)】:
{global_context}

【2. Notebook 执行历史 (History)】:
(这是用户已经执行过的操作序列，包含代码和关键输出)
{notebook_history}

【3. 知识库检索结果】:
{knowledge_base}

【4. 用户问题】:
{question}

【回答原则】:
1. **上下文关联**：如果用户问"这一步"或"上一步"，请根据 History 推断。如果用户问"第5步"，请查找 id=5 的记录。
2. **代码解释**：如果涉及代码，请解释算法原理。
3. **生物学意义**：如果涉及图表或数据结果，请尝试解读其生物学含义（如细胞群分布、基因表达差异）。
4. **建议引导**：如果用户迷茫，请根据当前数据状态推荐下一步分析（如 QC 后推荐降维）。
5. **知识库利用**：如果知识库中有相关信息，请优先参考知识库内容，确保回答准确性和权威性。

请直接给出回答：
"""

    def ask(self, user_question, global_context, notebook_history_json):
        """
        :param user_question: 用户的提问
        :param global_context: DataSummarizer 维护的当前状态文本
        :param notebook_history_json: NotebookManager 导出的完整历史 JSON 字符串
        """
        # 检索知识库
        knowledge_base_content = ""
        if self.knowledge_retriever:
            print("    [顾问] 正在检索知识库...")
            knowledge_base_content = self.knowledge_retriever.retrieve(user_question)
            if knowledge_base_content:
                print("    [顾问] 已检索到相关知识")
            else:
                print("    [顾问] 未检索到相关知识")
        
        prompt = PromptTemplate(
            input_variables=["global_context", "notebook_history", "question", "knowledge_base"],
            template=self.prompt_template
        )
        
        # 简单防爆处理：如果历史太长，保留最近的 N 步和最开始的几步
        # 或者直接依赖长上下文模型的能力 (Qwen 32B 支持 128k，通常够用了)
        # 这里直接传，如果太慢可以后续优化截断逻辑
        
        formatted = prompt.format(
            global_context=global_context,
            notebook_history=notebook_history_json,
            question=user_question,
            knowledge_base=knowledge_base_content if knowledge_base_content else "（未检索到相关知识）"
        )
        
        print("    [顾问] 正在阅读项目历史并思考...")
        response = self.llm.invoke(formatted)
        return (response.content if hasattr(response, 'content') else str(response)).strip()




