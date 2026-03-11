# src/chat_router.py
from langchain_core.prompts import PromptTemplate
import json
import re

class ChatRouter:
    def __init__(self, llm):
        self.llm = llm
        self.prompt_template = """
你是一个交互式生信系统的**指令编排引擎**。
请分析用户输入，拆解为**按顺序执行的动作列表**。

【最高原则】:
- 动作必须原子化。先跳转，再插入结构，最后生成内容。
- 如果涉及代码生成，**严禁**在动作链末尾自动添加 "RUN"。
- **重要**：动作链中最多只能包含一个 FOLLOW_PLAN 或 NEXT_TASK 动作，严禁重复执行。
- **重要**：CREATE_PLAN 动作后严禁立即添加 FOLLOW_PLAN，应让用户手动确认。

【可用动作 (Action Types)】:
1. "JUMP": 跳转光标。参数: target (整数 或 "last").
2. "INSERT_CELL": 在当前光标位置插入一个空白代码 Cell。参数: position ("BEFORE" | "AFTER"). 默认 "AFTER"。
3. "DELETE_CELL": 删除当前 Cell。无参数。
4. "AI_GEN": AI 生成代码填充当前 Cell。参数: content (需求描述). **仅用于简单的单步任务**,把客户的需求直接原封不动地当作参数,不要自作聪明地删改。
5. "MODIFY_CODE": **修改当前 Cell 的代码**。参数: content (修改需求),把客户的需求直接原封不动地放进content,不要自作聪明地删改。
   - 用于: "修改这一步"、"把参数改为X"、"修复这个错误"、"代码报错,修复代码"
   - 特点: 只修改当前 Cell，不生成新 Cell
6. "DIRECT_CODE": 直接填入用户提供的代码到当前 Cell。参数: content (代码)。
7. "RUN": 运行当前 Cell。
8. "DATA_SUMMARIZE": 运行数据总结/探针。当用户说"总结一下数据"、"查看变量状态"、"更新记忆"时使用。无参数。
9. "QA": 用户正在**提问、寻求解释、咨询建议**，或者只是在闲聊,你不要把什么都分析成QA,我都说了写代码进行单细胞注释,你判断成QA,你脑子是不是有问题啊。
   - 参数 `content`: 用户的原始问题/话语。
10. "CREATE_PLAN": **创建任务规划**。当用户提出复杂需求（如"完成单细胞数据分析"）时使用。
    - 参数 `content`: 用户的原始需求描述
    - 特点: 会调用规划器拆解任务，创建新的规划
11. "FOLLOW_PLAN": **按计划执行**。当用户明确表示"按计划进行"或"开始执行规划"时使用。
    - 参数 `content`: 无（或留空）
    - 特点: 从计划中取第一个任务开始执行
12. "EXIT": 退出。

【重要判断规则】:
- 如果用户提出**复杂、多步骤的需求**（如"帮我完成单细胞数据分析"），使用 **CREATE_PLAN** 动作。
- 如果用户说"按计划进行"或"开始执行规划"，使用 **FOLLOW_PLAN** 动作。
- 如果输入以 **"[规划任务]:"** 开头（由 FOLLOW_PLAN 调用传入），这是来自规划的子任务，直接使用 **AI_GEN** 动作。
- 如果用户要**修改当前 Cell**（如"修改这一步"、"把参数改为0.5"、"修复错误"），使用 **MODIFY_CODE** 动作。
- 如果用户需求**简单明确且需要新代码**（如"画个UMAP图"），使用 **AI_GEN** 动作。
- 如果用户在**提问或咨询**，使用 **QA** 动作。
- 在AI_GEN和MODIFY_CODE中一定要把用户提供的有效信息完整地作为参数,不要自作聪明地删改，比如用户提供了数据路径，那么一定要把数据路径提取出来，以便代码生成器生成代码

【示例】:
- 用户: "帮我完成单细胞数据的预处理和聚类分析"
  输出: [
    {{"type": "CREATE_PLAN", "content": "帮我完成单细胞数据的预处理和聚类分析"}}
  ]

- 用户: "按计划进行" 或 "开始执行规划"
  输出: [
    {{"type": "FOLLOW_PLAN"}}
  ]

- 用户: "[代码生成]: 读取单细胞数据文件并创建Seurat对象，数据在..."
  输出: [
    {{"type": "AI_GEN", "content": 直接传入用户需求，无需修改}}
  ]

- 用户: "[代码生成]: 进行质量控制，过滤低质量细胞"
  输出: [
    {{"type": "AI_GEN", "content": 直接传入用户需求，无需修改}}
  ]

- 用户: "在第6步前面加一个去线粒体的步骤"
  输出: [
    {{"type": "JUMP", "target": 6}},
    {{"type": "INSERT_CELL", "position": "BEFORE"}},
    {{"type": "AI_GEN", "content": "过滤线粒体比例 > 5 的细胞"}}
  ]

- 用户: "修改这一步，把分辨率改0.5"
  输出: [
    {{"type": "MODIFY_CODE", "content": "把分辨率改0.5"}}
  ]

- 用户: "解释一下第5步的图"
  输出：[
    {{"type": "QA", "content": "解释一下第5步的图"}}
  ]

- 用户: "画个 UMAP 图"
  输出: [
    {{"type": "AI_GEN", "content": "画个 UMAP 图"}}
  ]

【用户输入】: {user_input}
"""

    def parse(self, user_input, current_index, total_cells):
        # 1. 快速处理简单指令 (省钱省时间)
        txt = user_input.strip().lower()
        if txt in ["q", "quit", "exit"]: return [{"type": "EXIT"}]
        if txt in ["run", "ok", "y", "yes"]: return [{"type": "RUN"}]
        if txt in ["继续", "下一个", "next", "continue"]: return [{"type": "NEXT_TASK"}]
        if txt in ["查看规划", "显示计划", "show plan", "plan"]: return [{"type": "SHOW_PLAN"}]

        # 1.1 快速处理来自规划的任务 (无需调用 LLM)
        if user_input.startswith("[规划任务]:"):
            # 提取任务描述
            task_description = user_input.replace("[规划任务]:", "").strip()
            return [{"type": "AI_GEN", "content": task_description}]

        # 2. 复杂指令交给 LLM
        prompt = PromptTemplate(
            input_variables=["user_input", "current_index", "total_cells"],
            template=self.prompt_template
        )
        formatted = prompt.format(
            user_input=user_input,
            current_index=current_index + 1,
            total_cells=total_cells
        )

        response = self.llm.invoke(formatted)
        text = response.content if hasattr(response, 'content') else str(response)

        try:
            # 提取 JSON
            pattern = r"```json(.*?)```"
            match = re.search(pattern, text, re.DOTALL)
            json_str = match.group(1).strip() if match else text.strip()
            actions = json.loads(json_str)

            if isinstance(actions, list):
                # 对AI_GEN和MODIFY_CODE动作，直接使用用户原始输入
                for action in actions:
                    if action.get("type") in ["AI_GEN", "MODIFY_CODE"]:
                        action["content"] = user_input
                return actions
            return []
        except:
            print(f"[Router Error] 解析失败，回退到默认模式。原始返回: {text[:100]}...")
            # 兜底：当作新需求追加
            return [{"type": "AI_GEN", "operation": "APPEND", "content": user_input}]
            
