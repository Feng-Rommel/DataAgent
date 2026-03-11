# src/knowledge_retriever.py
import os
from typing import List
from langchain_core.prompts import PromptTemplate

class KnowledgeRetriever:
    """知识库检索器 - 从知识库中检索相关信息并提供给其他 agent"""
    
    def __init__(self, llm, knowledge_base_path: str = "./知识库测试"):
        """
        初始化知识库检索器

        Args:
            llm: 语言模型实例
            knowledge_base_path: 知识库根目录路径
        """
        self.llm = llm
        self.knowledge_base_path = knowledge_base_path
        self.knowledge_index = {}
        self.knowledge_categories = []
        # 存储带标题的文件信息：{category: [{'path': path, 'title': title, 'filename': filename}, ...]}
        self._category_files_dict = {}

        # 初始化知识库索引
        self._build_knowledge_index()
    
    def _build_knowledge_index(self):
        """构建知识库索引（包含文件标题）"""
        if not os.path.exists(self.knowledge_base_path):
            print(f"    [知识库] 警告: 知识库路径不存在: {self.knowledge_base_path}")
            return

        print(f"    [知识库] 正在索引知识库: {self.knowledge_base_path}")

        # 遍历知识库目录
        for category in os.listdir(self.knowledge_base_path):
            category_path = os.path.join(self.knowledge_base_path, category)

            # 只处理目录（跳过文件）
            if not os.path.isdir(category_path):
                continue

            # 收集该分类下的所有 markdown 文件及其标题
            category_files = []
            for root, dirs, files in os.walk(category_path):
                for file in files:
                    if file.endswith('.md'):
                        file_path = os.path.join(root, file)
                        relative_path = os.path.relpath(file_path, self.knowledge_base_path)
                        # 读取文件标题（第一行）
                        title = self._extract_file_title(file_path)
                        category_files.append({
                            'path': relative_path,
                            'title': title,
                            'filename': file
                        })

            if category_files:
                self.knowledge_categories.append(category)
                self.knowledge_index[category] = [f['path'] for f in category_files]
                self._category_files_dict[category] = category_files  # 保存带标题的文件信息
                print(f"    [知识库] 索引分类 '{category}': {len(category_files)} 个文件")

        print(f"    [知识库] 索引完成，共 {len(self.knowledge_categories)} 个分类")

    def _extract_file_title(self, file_path: str) -> str:
        """提取文件标题（第一行）"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                first_line = f.readline().strip()
                # 移除 markdown 标题符号
                if first_line.startswith('#'):
                    first_line = first_line.lstrip('#').strip()
                return first_line if first_line else os.path.basename(file_path)
        except Exception as e:
            print(f"    [知识库] 读取标题失败 {file_path}: {e}")
            return os.path.basename(file_path)
    
    def _read_file_content(self, file_path: str) -> str:
        """读取文件内容"""
        full_path = os.path.join(self.knowledge_base_path, file_path)
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            print(f"    [知识库] 读取文件失败 {file_path}: {e}")
            return ""

    def _select_relevant_files(self, user_query: str, category: str, max_files: int = 2) -> List[str]:
        """
        使用 LLM 从指定分类中选择最相关的文件（基于文件名和标题）

        Args:
            user_query: 用户查询
            category: 知识库分类
            max_files: 最多返回的文件数

        Returns:
            相关文件的路径列表
        """

        # 获取该分类下的文件列表（带标题）
        category_files = self._category_files_dict.get(category, [])
        print(f"    [知识库] 分类 '{category}' 下有 {category_files}")
        if not category_files:
            print(f"    [知识库] 分类 '{category}' 下没有文件")
            return []

        # 构建文件列表供 LLM 选择
        files_info = []
        for i, file_info in enumerate(category_files, 1):
            files_info.append(
                f"{i}. 文件名: {file_info['filename']}\n"
                f"   标题: {file_info['title']}\n"
                f"   路径: {file_info['path']}"
            )
        files_list_str = "\n".join(files_info)
        print(f"    [知识库] 文件列表:\n{files_list_str}")

        prompt_template = """
你是知识库文件选择专家。请根据用户查询，从以下文件列表中选择最相关的 1-2 个文件。

【可用文件列表】:
{files_list}

【用户查询】:
{query}

【选择原则,下面列举的仅是示例,你要自己判断】:
1. 根据文件名和标题判断相关性
2. 选择最直接相关的 1-2 个文件
3. 如果涉及"质量控制"、"QC"、"过滤"，选择相关文件
4. 如果涉及"预处理"、"标准化"、"归一化"，选择相关文件
5. 如果涉及"数据读取"、"加载"，选择相关文件
6. 优先选择标题中包含关键词的文件

【输出格式】:
只输出文件编号列表，用逗号分隔。例如: 1,3
或者: 2
如果没有相关文件，输出: 无
"""

        prompt = PromptTemplate(
            input_variables=["files_list", "query"],
            template=prompt_template
        )

        formatted = prompt.format(files_list=files_list_str, query=user_query)

        try:
            response = self.llm.invoke(formatted)
            result = (response.content if hasattr(response, 'content') else str(response)).strip()

            if result == "无" or "无相关" in result:
                print(f"    [知识库] 未找到相关文件")
                return []

            # 解析选择的文件编号
            selected_files = []
            for part in result.split(','):
                part = part.strip()
                if part.isdigit():
                    idx = int(part) - 1  # 转换为 0-based 索引
                    if 0 <= idx < len(category_files):
                        selected_files.append(category_files[idx]['path'])
                        print(f"    [知识库] 选择文件: {category_files[idx]['filename']} - {category_files[idx]['title']}")

            # 限制返回数量
            return selected_files[:max_files]

        except Exception as e:
            print(f"    [知识库] 文件选择失败: {e}")
            # 降级：返回前两个文件
            return [f['path'] for f in category_files[:max_files]]

    def _read_category_files(self, category: str, max_files: int = 5) -> List[str]:
        """读取指定分类下的文件内容"""
        if category not in self.knowledge_index:
            return []

        files = self.knowledge_index[category][:max_files]
        contents = []
        for file_path in files:
            content = self._read_file_content(file_path)
            if content:
                contents.append(f"# {file_path}\n{content}")

        return contents
    
    def _select_categories(self, user_query: str, max_categories: int = 2) -> List[str]:
        """使用 LLM 选择相关的知识库分类

        Args:
            user_query: 用户查询
            max_categories: 最多返回的分类数

        Returns:
            相关分类列表
        """

        if not self.knowledge_categories:
            return []

        categories_str = "\n".join([f"- {cat}" for cat in self.knowledge_categories])

        prompt_template = f"""
你是知识库检索专家。请根据用户查询，从以下知识库分类中选择最相关的分类（最多选择 {max_categories} 个）。

【可用知识库分类】:
{{categories}}

【用户查询】:
{{query}}

【选择原则】:
- 如果查询涉及"单细胞"、"scRNA"、"细胞类型"、"聚类"等，选择 scRNA 分类
- 如果查询涉及"批量"、"bulk"、"差异表达"、"富集分析"等，选择 bulkRNA 分类
- 如果查询涉及"空间"、"spatial"、"反卷积"等，选择 spatialRNA 分类
- 如果查询涉及"数据集"、"数据库"等，选择 datasets 分类
- 优先选择最直接相关的 1-2 个分类，避免选择太多

【输出格式】:
只输出分类名称列表，用逗号分隔。例如: scRNA,datasets
如果没有相关分类，输出: 无
如果问题很简单，比如就是看一下有什么文件或者数据框有哪些列，则输出：无需参考知识库
"""

        prompt = PromptTemplate(
            input_variables=["categories", "query"],
            template=prompt_template
        )

        formatted = prompt.format(categories=categories_str, query=user_query)

        try:
            response = self.llm.invoke(formatted)
            result = (response.content if hasattr(response, 'content') else str(response)).strip()

            if result == "无" or "无相关" in result or "无需参考" in result:
                return []

            # 解析分类列表
            selected = []
            for cat in self.knowledge_categories:
                if cat.lower() in result.lower():
                    selected.append(cat)

            return selected[:max_categories]  # 最多返回 max_categories 个分类
        except Exception as e:
            print(f"    [知识库] 分类选择失败: {e}")
            return []
    
    def _extract_relevant_knowledge(self, user_query: str, category_contents: List[str]) -> str:
        """使用 LLM 从内容中提取最相关的知识片段"""
        
        if not category_contents:
            return ""
        
        # 合并所有内容（限制长度避免上下文过大）
        combined_content = "\n\n".join(category_contents)
        print(f"    [知识库] 合并内容长度: {len(combined_content)}")
        if len(combined_content) > 128000:
            # 简单截断，保留前面的内容
            combined_content = combined_content[:128000]
        
        prompt_template = """
你是知识提取专家。请从以下知识库内容中提取与用户查询最相关的知识片段。

【知识库内容】:
{knowledge_content}

【用户查询】:
{query}

【提取原则】:
1. 提取直接相关的定义、流程、参数说明、代码示例
2. 保留关键参数、阈值、注意事项等重要信息
3. 如果内容很长，只提取最核心的部分
4. 保持原文的技术准确性
5. 使用 markdown 格式输出，包含标题和代码块
6. 参考知识库的代码块一定要完整地提取出来,不要自作主张地删改,特别是一些R包地加载,你总是自作聪明地删除一些R包地加载

【输出格式】:
直接输出提取的知识片段，不要添加任何解释或说明。
如果找不到相关内容，输出: 未找到相关知识
"""
        print(f"    [知识库] 初步提取的内容: {combined_content}")
        print(f"    [知识库] 用户查询: {user_query}")
        prompt = PromptTemplate(
            input_variables=["knowledge_content", "query"],
            template=prompt_template
        )
        
        formatted = prompt.format(knowledge_content=combined_content, query=user_query)
        
        try:
            response = self.llm.invoke(formatted)
            result = (response.content if hasattr(response, 'content') else str(response)).strip()
            
            if "未找到相关" in result:
                return ""
            
            return result
        except Exception as e:
            print(f"    [知识库] 知识提取失败: {e}")
            return ""
    
    def retrieve(self, user_query: str) -> str:
        """
        根据用户查询检索知识库（改进版：先选择文件，再读取内容）

        Args:
            user_query: 用户查询或任务描述

        Returns:
            str: 检索到的相关知识，如果没有则返回空字符串
        """
        if not self.knowledge_index:
            return ""

        try:
            # 1. 选择相关的分类（限制为最多 2 个分类，避免选择太多）
            selected_categories = self._select_categories(user_query, max_categories=2)

            if not selected_categories:
                print(f"    [知识库] 未找到相关分类")
                return ""

            print(f"    [知识库] 选择相关分类: {', '.join(selected_categories)}")

            # 2. 对每个分类，选择最相关的 1-2 个文件
            all_selected_files = []
            for category in selected_categories:
                selected_files = self._select_relevant_files(user_query, category, max_files=2)
                all_selected_files.extend(selected_files)

            if not all_selected_files:
                print(f"    [知识库] 未找到相关文件")
                return ""

            print(f"    [知识库] 共选择了 {len(all_selected_files)} 个文件")

            # 3. 只读取这些选定的文件内容
            all_contents = []
            for file_path in all_selected_files:
                content = self._read_file_content(file_path)
                if content:
                    all_contents.append(f"# {file_path}\n{content}")
                    print(f"    [知识库] 读取文件: {file_path} ({len(content)} 字符)")

            if not all_contents:
                print(f"    [知识库] 文件无内容")
                return ""

            # 4. 提取最相关的知识片段（简化版，因为文件已经过筛选）
            relevant_knowledge = self._extract_relevant_knowledge(user_query, all_contents)

            if relevant_knowledge:
                print(f"    [知识库] 检索到相关知识 ({len(relevant_knowledge)} 字符)")

            return relevant_knowledge

        except Exception as e:
            print(f"    [知识库] 检索失败: {e}")
            return ""
    
    def get_knowledge_summary(self) -> str:
        """获取知识库摘要信息"""
        if not self.knowledge_index:
            return "知识库为空或未正确初始化"
        
        summary = "【知识库分类】\n"
        for category, files in self.knowledge_index.items():
            summary += f"- {category}: {len(files)} 个文件\n"
        
        return summary
