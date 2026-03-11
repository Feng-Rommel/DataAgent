# src/code_programmer.py

from langchain_core.prompts import PromptTemplate
import json
import re

class CodeProgrammer:
    def __init__(self, llm, knowledge_retriever=None):
        """
        初始化代码生成器

        Args:
            llm: 语言模型实例
            knowledge_retriever: 知识库检索器实例（可选）
        """
        self.llm = llm
        self.knowledge_retriever = knowledge_retriever
        # 上下文提取器的 prompt
        self.context_extraction_prompt = """你是一个智能上下文分析助手。
从完整的 Notebook 历史中，筛选出与当前任务最相关的代码单元（Cells）。

【当前任务】:
{current_task}

【完整的历史记录】:
{full_history}

【任务要求】:
1. 最多选择 {max_cells} 个最相关的 cell
2. 优先保留：数据加载、变量定义、前置步骤、类似功能代码
3. 过滤掉：无关的探索性代码、失败的尝试、调试代码
4. 确保筛选后的代码可以独立运行

【JSON 输出格式】:
返回一个包含相关 cell 的 JSON 数组：
```json
{{
  "relevant_cells": [
    {{
      "id": 1,
      "code": "...",
      "output": "...",
      "relevance_score": 0.95,
      "reason": "加载了当前任务需要的数据对象"
    }}
  ],
  "summary": "从 X 个历史 cell 中筛选出 Y 个最相关的"
}}
```

如果没有相关的历史记录，返回空数组。"""

        # 优化后的 Prompt
        self.prompt_template = """你是一个 R 语言单细胞分析专家。
请根据用户需求，生成一组 Jupyter Notebook 代码块 (Cells)，仅满足客户的需求就行，不要自作聪明多写代码，如果客户只是让你查看目录下文件，就不要把读取的代码也写了。

【当前数据状态】:
{data_context}

【Notebook 历史上下文】:
{notebook_history}

【已完成的任务列表】:
{completed_tasks}

【知识库检索结果，一定要好好参考，最好用知识库里的方法，不要自己乱写,还有里面用到的R包一定要加载,但是知识库里的东西你也不能照抄,要根据实际情况修改,特别是细胞注释这部分,必须根据上下文实际情况挑选基因和进行注释】:
{knowledge_base}

【任务要求】：
1. **上下文感知**：仔细阅读当前数据状态和历史记录，确保代码能正确衔接。
2. **批量生成**：一次性生成完成该任务所需的所有代码步骤。
3. **逻辑分块**：请按照 Jupyter Notebook 的最佳实践，将代码拆分为多个 Cell：
   - **数据加载**（如 readRDS, CreateSeuratObject）单独放一个 Cell
   - **变量定义**（如参数设置、阈值设定）单独放一个 Cell
   - **耗时计算**（如 RunPCA, FindClusters, FindMarkers）单独放一个 Cell
   - **绘图展示**（如 DimPlot, VlnPlot, FeaturePlot）单独放一个 Cell
   - **结果检查**（如 head(), str(), print()）单独放一个 Cell
4. **简洁输出**：只返回包含注释的代码列表，不要 id 和 description 字段。
5. **知识库参考**：如果知识库中有相关的参数设置、流程说明或代码示例，请优先参考这些信息，确保代码的正确性和最佳实践,但是个性化的东西不能照抄,要根据上下文进行修改,特别是细胞注释部分。

【编码规范】：
1. **变量引用**：如果数据状态中已有 Seurat 对象，直接使用该对象名（如 sc_obj）
2. **参数设置**：根据数据状态中的元数据列名正确设置参数
3. **代码注释**：在关键步骤添加中文注释说明
4. **错误处理**：对于可能失败的操作，添加简单的检查逻辑
5. **引号使用**：R 代码字符串**必须使用单引号**（用 ' 包裹），绝对不要用双引号

【JSON 输出示例，仅示例，让你知道输出格式是什么样的，别照抄】：
```json
[
  "# 读取预处理后的单细胞数据\\nsc_obj <- readRDS('filtered_seurat.rds')\\n# 查看数据基本信息\\nprint(sc_obj)",
  "# 标准化数据（LogNormalize）\\nsc_obj <- NormalizeData(sc_obj, normalization.method = 'LogNormalize', scale.factor = 10000)",
  "# 识别高变基因（默认2000个）\\nsc_obj <- FindVariableFeatures(sc_obj, selection.method = 'vst', nfeatures = 2000)\\n# 查看高变基因\\nVariableFeatures(sc_obj)[1:10]",
  "# 执行 PCA 降维\\nsc_obj <- RunPCA(sc_obj, features = VariableFeatures(object = sc_obj), npcs = 30)\\n# 查看降维结果\\nprint(sc_obj[['pca']])",
  "# 绘制 PCA 肘部图，选择合适的 PC 数量\\nElbowPlot(sc_obj, ndims=30)"
]
```

【重要提示】：
1. 输出必须包裹在 ```json ... ``` 代码块中
2. 返回简单的字符串数组，每个元素是一个完整的代码块（包含注释）
3. 确保 JSON 格式完全正确，每个字符串都用双引号，不要遗漏逗号
4. **R 代码中的字符串全部使用单引号**，不要用双引号

【特殊情况处理】：
1. **数据为空**：如果数据状态为"当前无数据上下文"，首先生成加载数据的代码
2. **变量不存在**：不要引用数据状态中不存在的变量
3. **步骤已完成**：如果历史记录中显示某些步骤已完成（如 PCA），跳过这些步骤
4. **参数调整**：根据数据状态中的细胞数、基因数等信息调整参数
5. **知识库参数**：如果知识库提供了推荐的参数值或阈值，请使用这些值

用户任务：{user_requirements}
"""

    def _extract_relevant_context(self, current_task, full_history, max_cells=100):
        """
        内部方法：提取与当前任务相关的上下文

        Args:
            current_task: 当前任务描述
            full_history: 完整的历史记录（JSON 格式）
            max_cells: 最多保留多少个相关 cell

        Returns:
            str: 筛选后的上下文字符串
        """
        # 如果历史为空或已经是简短的，直接返回
        if not full_history or full_history in ["[]", "暂无历史代码。", "当前无数据上下文。"]:
            return full_history

        try:
            # 解析历史记录
            history_data = json.loads(full_history)
            if not isinstance(history_data, list):
                return full_history

            # 如果历史数量小于等于 max_cells，直接返回
            if len(history_data) <= max_cells:
                return full_history

            # 使用 LLM 进行智能筛选
            print(f"    [上下文提取] 正在分析 {len(history_data)} 个历史 cell...")

            prompt = PromptTemplate(
                input_variables=["current_task", "full_history", "max_cells"],
                template=self.context_extraction_prompt
            )

            formatted = prompt.format(
                current_task=current_task,
                full_history=full_history,
                max_cells=max_cells
            )

            response = self.llm.invoke(formatted)
            text = response.content if hasattr(response, 'content') else str(response)

            # 解析 LLM 返回的 JSON
            try:
                pattern = r"```json(.*?)```"
                match = re.search(pattern, text, re.DOTALL)
                json_str = match.group(1).strip() if match else text.strip()

                result = json.loads(json_str)
                relevant_cells = result.get("relevant_cells", [])
                summary = result.get("summary", f"智能筛选完成")

                # 格式化为 JSON 字符串
                extracted_context = json.dumps(relevant_cells, ensure_ascii=False, indent=2)


                print(f"    [上下文提取] {extracted_context}")
                return extracted_context

            except json.JSONDecodeError as e:
                print(f"    [上下文提取] JSON 解析失败，使用降级策略: {e}")
                # 降级：返回最近的 N 个 cell
                return json.dumps(history_data[-max_cells:], ensure_ascii=False, indent=2)

        except json.JSONDecodeError:
            # 如果原始历史不是有效 JSON，直接返回
            return full_history
        except Exception as e:
            print(f"    [上下文提取] 发生错误: {e}，返回原始历史")
            return full_history

    def generate_code(self, user_requirements, data_context="", notebook_history="", completed_tasks=""):
        """
        生成代码块列表

        Args:
            user_requirements: 用户需求
            data_context: 当前数据状态
            notebook_history: Notebook 历史上下文
            completed_tasks: 已完成的任务列表

        Returns:
            list: 代码字符串列表，每个元素是一个完整的代码块
        """
        if not data_context:
            data_context = "当前无数据上下文。"
        if not notebook_history:
            notebook_history = "暂无历史代码。"
        if not completed_tasks:
            completed_tasks = "暂无已完成任务。"

        # 智能筛选历史上下文（只在需要时调用）
        if notebook_history and notebook_history != "暂无历史代码。":
            notebook_history = self._extract_relevant_context(
                current_task=user_requirements,
                full_history=notebook_history,
                max_cells=5  # 最多保留 5 个最相关的 cell
            )

        print(f"    [代码生成器] 已筛选出相关cell: {notebook_history}")

        # 检索知识库
        knowledge_base_content = ""
        if self.knowledge_retriever:
            print("    [代码生成器] 正在检索知识库...")
            knowledge_base_content = self.knowledge_retriever.retrieve(user_requirements)
            if knowledge_base_content:
                print(f"    [代码生成器] 已检索到相关知识: {knowledge_base_content}")
            else:
                print("    [代码生成器] 未检索到相关知识")

        prompt = PromptTemplate(
            input_variables=["user_requirements", "data_context", "notebook_history", "completed_tasks", "knowledge_base"],
            template=self.prompt_template
        )

        formatted = prompt.format(
            user_requirements=user_requirements,
            data_context=data_context,
            notebook_history=notebook_history,
            completed_tasks=completed_tasks,
            knowledge_base=knowledge_base_content if knowledge_base_content else "（未检索到相关知识）"
        )

        response = self.llm.invoke(formatted)
        text = response.content if hasattr(response, 'content') else str(response)
        print(f"    [代码生成器] 生成代码: {text}")

        json_str = None

        try:
            # 1. 首先尝试直接解析（如果返回的就是纯JSON）
            try:
                stripped_text = text.strip()
                steps = json.loads(stripped_text)
                if isinstance(steps, list):
                    print(f"    [解析成功] 直接解析JSON数组成功，{len(steps)}个代码块")
                    return steps
            except json.JSONDecodeError:
                pass

            # 2. 尝试提取 markdown 代码块中的 JSON
            pattern = r"```json(.*?)```"
            match = re.search(pattern, text, re.DOTALL)
            if match:
                json_str = match.group(1).strip()
                print(f"    [调试] 正则匹配成功，提取长度: {len(json_str)}")
            else:
                # 3. 尝试查找 JSON 数组（从 [ 开始到 ] 结束）
                array_match = re.search(r'(\[[^\]]*(?:\[[^\]]*\][^\]]*)*\])', text, re.DOTALL)
                if array_match:
                    json_str = array_match.group(1).strip()
                    print(f"    [调试] 数组匹配成功，提取长度: {len(json_str)}")
                else:
                    print(f"    [调试] 未能匹配到JSON，使用完整文本")
                    json_str = text.strip()

            # 预处理：修复JSON字符串中的引号问题
            json_str = self._preprocess_json_quotes(json_str)

            # 解析 JSON 字符串数组
            steps = json.loads(json_str)

            if isinstance(steps, list):
                return steps
            return []
        except json.JSONDecodeError as e:
            # 尝试从错误中恢复
            print(f"    [CodeProgrammer] JSON 解析失败: {e}")
            print(f"    [调试] 解析的字符串长度: {len(json_str)}, 前200字符: {json_str[:200] if json_str else 'None'}")

            # 智能修复 JSON 字符串
            fixed_json = self._fix_json_string(json_str)

            if fixed_json:
                try:
                    steps = json.loads(fixed_json)
                    if isinstance(steps, list):
                        print(f"    [恢复] 修复 JSON 成功，提取到 {len(steps)} 个代码块")
                        return steps
                except json.JSONDecodeError:
                    pass

            # 如果还是失败，输出原始返回以便调试
            print(f"    [CodeProgrammer Error] 最终解析失败: {e}")
            print(f"    原始返回前500字符:\n{text[:500]}")
            return []
        except Exception as e:
            print(f"    [CodeProgrammer Error] 意外错误: {e}")
            return []

    def _fix_json_string(self, json_str: str) -> str:
        """
        智能修复 JSON 字符串中的常见问题
        """
        try:
            # 1. 尝试直接解析（可能是 JSON 格式问题，如尾随逗号）
            json_str = json_str.strip()
            # 移除尾随逗号
            if json_str.endswith(','):
                json_str = json_str[:-1].rstrip()

            try:
                json.loads(json_str)
                return json_str
            except:
                pass

            # 2. 智能分割 JSON 数组元素（不使用正则表达式）
            if json_str.startswith('[') and json_str.endswith(']'):
                content = json_str[1:-1]  # 去掉外层括号
                # 按逗号分割元素
                elements = []
                current = []
                in_string = False
                escape = False
                bracket_depth = 0  # 跟踪括号深度，处理嵌套括号

                for char in content:
                    if escape:
                        current.append(char)
                        escape = False
                        continue

                    if char == '\\':
                        escape = True
                        current.append(char)
                    elif char == '"' and not escape:
                        in_string = not in_string
                        current.append(char)
                    elif char == ',' and not in_string and not escape and bracket_depth == 0:
                        elements.append(''.join(current))
                        current = []
                    else:
                        # 跟踪括号深度
                        if char == '[':
                            bracket_depth += 1
                        elif char == ']':
                            bracket_depth -= 1
                        current.append(char)

                if current:
                    elements.append(''.join(current))

                # 过滤出有效的代码元素
                valid_elements = []
                for elem in elements:
                    elem = elem.strip().strip('"')
                    # 移除转义字符
                    elem = elem.replace('\\n', '\n').replace('\\"', '"').replace('\\t', '\t')
                    # 检查是否看起来像代码
                    if any(keyword in elem for keyword in ['<-', 'library(', 'sc_obj', '#', '(', ')', '=']):
                        # 重新包裹引号
                        valid_elements.append(f'"{elem}"')

                if valid_elements:
                    return '[' + ','.join(valid_elements) + ']'

            return None
        except Exception as e:
            print(f"    [JSON修复] 修复过程中出错: {e}")
            return None

    def _preprocess_json_quotes(self, json_str: str) -> str:
        """
        预处理JSON字符串，修复R代码中的双引号问题
        将JSON字符串内部的未转义双引号替换为单引号
        """
        try:
            # 使用一个状态机来准确识别JSON字符串边界
            result = []
            in_string = False  # 是否在JSON字符串值内部（不包括引号本身）
            escape = False  # 是否在转义状态
            i = 0

            while i < len(json_str):
                char = json_str[i]

                # 处理转义字符
                if escape:
                    result.append(char)
                    escape = False
                    i += 1
                    continue

                if char == '\\':
                    escape = True
                    result.append(char)
                    i += 1
                    continue

                # 处理引号
                if char == '"':
                    if not in_string:
                        # 进入字符串
                        in_string = True
                        result.append('"')
                    else:
                        # 遇到引号，判断是字符串结束还是内部引号
                        # 向前看，如果是 `, } ] ` 或者是字符串末尾，那就是结束
                        j = i + 1
                        # 跳过空白字符
                        while j < len(json_str) and json_str[j] in ' \t\n\r':
                            j += 1

                        if j >= len(json_str) or json_str[j] in ',}]':
                            # 这是字符串结束
                            in_string = False
                            result.append('"')
                        else:
                            # 这是内部引号，替换为单引号
                            result.append("'")
                    i += 1
                    continue

                # 其他字符直接添加
                result.append(char)
                i += 1

            return ''.join(result)
        except Exception as e:
            print(f"    [JSON预处理] 预处理出错: {e}")
            return json_str
