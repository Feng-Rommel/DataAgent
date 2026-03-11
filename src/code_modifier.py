# src/code_modifier.py
from langchain_core.prompts import PromptTemplate
import json
import re

class CodeModifier:
    """
    代码修改器 - 专门用于修改单个 Cell 的代码
    与 CodeProgrammer 的区别：
    - CodeProgrammer: 生成新代码，可能生成多个 Cell
    - CodeModifier: 修改现有代码，只修改当前 Cell
    """
    
    def __init__(self, llm):
        self.llm = llm
        
        self.prompt_template = """你是一个 R 语言代码修改专家。
你的任务是根据用户的修改需求或当前报错，修改当前 Cell 的代码。

【重要原则】:
1. **只修改当前 Cell**: 不要生成新的 Cell，只返回修改后的代码
2. **保持功能完整**: 修改后的代码应该是完整可运行的
3. **针对性修改**: 只修改用户要求的部分，其他部分保持不变
4. **错误修复**: 如果有报错信息，优先修复错误

【当前 Cell 信息】:
```r
{current_code}
```

【运行输出】:
{execution_output}

【用户修改需求】:
{user_request}

【任务要求】:
1. 分析当前代码和运行结果（如果有）
2. 理解用户的修改需求
3. 生成修改后的完整代码
4. 如果有错误，修复错误

【输出格式】:
直接输出修改后的代码，用 ```r ... ``` 包裹

【注意事项】:
1. 代码必须是完整的、可直接运行的
2. 不要添加额外的注释（除非用户要求）
3. 保持代码风格一致
4. 如果当前代码有错误，优先修复错误
"""

    def modify_code(self, current_code, user_request, execution_output=""):
        """
        修改当前 Cell 的代码

        Args:
            current_code: 当前 Cell 的代码
            user_request: 用户的修改需求
            execution_output: 运行输出（可选，如果有报错会很有用）

        Returns:
            str: 修改后的代码
        """
        # 处理空输出
        if not execution_output or execution_output.strip() == "":
            execution_output = "（当前 Cell 尚未运行或无输出）"

        print(f"代码修改器:当前输出为{execution_output}")
        prompt = PromptTemplate(
            input_variables=["current_code", "user_request", "execution_output"],
            template=self.prompt_template
        )

        formatted = prompt.format(
            current_code=current_code,
            user_request=user_request,
            execution_output=execution_output
        )

        response = self.llm.invoke(formatted)
        text = response.content if hasattr(response, 'content') else str(response)

        try:
            # 提取代码块
            pattern = r"```r(.*?)```"
            match = re.search(pattern, text, re.DOTALL)
            code = match.group(1).strip() if match else None

            if code:
                print(f"    [CodeModifier] 修改后的代码: {code}")
                return code

            # 如果没有找到代码块，尝试直接使用返回内容
            if "```" in text:
                # 尝试提取没有语言标识的代码块
                pattern2 = r"```(.*?)```"
                match2 = re.search(pattern2, text, re.DOTALL)
                if match2:
                    return match2.group(1).strip()

            # 如果都没有，返回原代码
            print(f"    [CodeModifier Warning] 无法提取修改后的代码，保持原代码不变")
            return current_code

        except Exception as e:
            print(f"    [CodeModifier Error] 解析失败: {e}")
            print(f"    原始返回: {text[:200]}...")
            return current_code
