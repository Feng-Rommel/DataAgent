import nbformat
from nbformat.v4 import new_notebook, new_code_cell, new_markdown_cell

class NotebookManager:
    def __init__(self, filename="analysis.ipynb"):
        self.filename = filename
        try:
            # 尝试读取已有文件，支持断点续传
            with open(self.filename, 'r', encoding='utf-8') as f:
                self.nb = nbformat.read(f, as_version=4)
        except FileNotFoundError:
            self.nb = new_notebook()
            self.nb.metadata.kernelspec = {"display_name": "R", "language": "R", "name": "r_global"}
        
        # 游标设计：
        # 如果文件为空，cursor = -1 (等待插入)
        # 如果有内容，默认指向最后一个，方便继续追加
        self.cursor = len(self.nb.cells) - 1 if self.nb.cells else -1
        self.save()

    def save(self):
        with open(self.filename, 'w', encoding='utf-8') as f:
            nbformat.write(self.nb, f)

    # ==========================================
    #           1. 游标与导航 (Navigation)
    # ==========================================
    def jump_to(self, index):
        """
        修改当前游标位置 (支持 0-based 索引)
        """
        if not self.nb.cells:
            self.cursor = -1
            print(">>> [系统] Notebook 为空。")
            return

        # 边界限制
        if index < 0: index = 0
        if index >= len(self.nb.cells): index = len(self.nb.cells) - 1
        
        self.cursor = index
        print(f">>> [系统] 光标已跳转至 Cell {self.cursor + 1}")

    def get_current_cell_content(self):
        if 0 <= self.cursor < len(self.nb.cells):
            return self.nb.cells[self.cursor].source
        return None

    # ==========================================
    #           2. 编辑操作 (Editing)
    # ==========================================
    def insert_cell(self, code, position="AFTER", cell_type="code"):
        """
        插入 Cell 并移动光标。
        """
        if cell_type == "code":
            cell = new_code_cell(source=code)
        else:
            cell = new_markdown_cell(source=code)

        # 逻辑：
        # 如果 Notebook 为空，初始化
        if not self.nb.cells:
            self.nb.cells.append(cell)
            self.cursor = 0
        
        # 如果在当前位置之后插入
        elif position == "AFTER":
            # 插入到 cursor + 1
            insert_idx = self.cursor + 1
            self.nb.cells.insert(insert_idx, cell)
            self.cursor = insert_idx # 光标自动跟进到新 Cell
            
        # 如果在当前位置之前插入
        elif position == "BEFORE":
            # 插入到 cursor
            insert_idx = max(0, self.cursor)
            self.nb.cells.insert(insert_idx, cell)
            # 光标停留在新插入的 Cell 上 (索引不变，但内容变了)
            self.cursor = insert_idx

        self.save()
        return self.cursor

    def set_current_cell_code(self, code):
        """修改当前 Cell 的代码"""
        if 0 <= self.cursor < len(self.nb.cells):
            self.nb.cells[self.cursor].source = code
            self.save()
            return True
        return False

    def delete_current_cell(self):
        if 0 <= self.cursor < len(self.nb.cells):
            del self.nb.cells[self.cursor]
            self.save()
            # 删除后光标逻辑：如果删的是最后一个，光标前移
            if self.cursor >= len(self.nb.cells):
                self.cursor = max(0, len(self.nb.cells) - 1)
            # 如果删空了
            if not self.nb.cells:
                self.cursor = -1

    # ==========================================
    #           3. 执行操作 (Execution)
    # ==========================================
    def execute_current_cell(self, kernel_session, auto_advance=True):
        """
        执行当前 Cell，保存结果，并自动步进。

        Args:
            kernel_session: 内核会话对象
            auto_advance: 是否自动移动到下一个 Cell（默认 True）

        Returns:
            tuple: (success, outputs, is_last_cell)
            - is_last_cell: 这是一个标记，告诉主程序是否跑到了尽头(适合触发总结)
        """
        if self.cursor < 0 or self.cursor >= len(self.nb.cells):
            return False, [], False

        print(f">>> [执行] 正在运行 Cell {self.cursor + 1} ...")

        # 1. 运行
        code = self.nb.cells[self.cursor].source
        outputs, error_occurred = kernel_session.run(code)

        print(f">>> [执行] 执行完成，共收集 {len(outputs)} 个输出，error={error_occurred}")

        # 2. 保存输出
        self.nb.cells[self.cursor].outputs = outputs
        self.save()
        print(f">>> [执行] 已保存输出到磁盘")

        # 3. 判断是否是最后一个 Cell (用于触发总结)
        # 注意：这里判断的是【运行前】的位置是不是最后
        was_last_cell = (self.cursor == len(self.nb.cells) - 1)

        # 4. 游标自动步进 (Auto-Advance)
        if auto_advance and not error_occurred:
            # 如果不是最后一个，自动跳到下一个准备运行
            if not was_last_cell:
                self.cursor += 1
                # print(f">>> [系统] 自动跳转至下一个 Cell {self.cursor + 1}")
            else:
                # 如果是最后一个，光标不动，或者你可以选择自动新建一个空 Cell
                pass

        print(f">>> [执行] 返回: success={not error_occurred}, was_last_cell={was_last_cell}")
        return not error_occurred, outputs, was_last_cell

    @staticmethod
    def categorize_outputs(outputs):
        """
        【清洗工具】将全量输出分拣为 AI 易读的格式。
        不会修改 Notebook 文件本身，只返回处理后的数据。

        Returns:
            dict: {
                "ai_text": str,   # 干净的文本 (stdout + result)，给总结器用
                "logs": str,      # 噪音文本 (stderr)，可丢弃
                "images": int,    # 图片数量
                "error": str      # 报错信息
            }
        """
        result = {
            "ai_text": "",
            "logs": "",
            "images": 0,
            "error": None
        }

        for out in outputs:
            # 1. 标准输出 (stdout) -> AI 要看
            if out.output_type == 'stream' and out.name == 'stdout':
                result['ai_text'] += out.text

            # 2. 标准错误 (stderr) -> 视为日志/噪音
            elif out.output_type == 'stream' and out.name == 'stderr':
                result['logs'] += out.text

            # 3. 执行结果 (execute_result) -> AI 要看
            elif out.output_type == 'execute_result':
                text = out.data.get('text/plain', '')
                result['ai_text'] += f"\n[Result]:\n{text}\n"

            # 4. display_data -> 可能是图片也可能是文本
            elif out.output_type == 'display_data':
                # 检查是否是图片
                if 'image/png' in out.data or 'image/jpeg' in out.data:
                    result['images'] += 1
                # 提取文本内容
                else:
                    # 优先提取 text/plain
                    if 'text/plain' in out.data:
                        text = out.data['text/plain']
                        if isinstance(text, list):
                            text = ''.join(text)
                        result['ai_text'] += text
                    # 其次提取 text/html
                    elif 'text/html' in out.data:
                        html = out.data['text/html']
                        if isinstance(html, list):
                            html = ''.join(html)
                        # 从 HTML 中提取纯文本（简单去除标签）
                        import re
                        text = re.sub(r'<[^>]+>', '', html)
                        result['ai_text'] += text
                    # 再次提取 text/markdown
                    elif 'text/markdown' in out.data:
                        md = out.data['text/markdown']
                        if isinstance(md, list):
                            md = ''.join(md)
                        result['ai_text'] += md

            # 5. 错误 (error) -> 既是日志，也是关键状态
            elif out.output_type == 'error':
                err_msg = f"{out.ename}: {out.evalue}"
                result['error'] = err_msg
                result['logs'] += f"\n[ERROR]: {err_msg}\n"

        return result

    def get_cell_context(self, index=None):
        """
        获取指定 Cell (默认当前光标) 的【代码 + 清洗后的输出】组合。
        这是专门喂给 DataSummarizer 的"营养餐"。
        """
        if index is None:
            index = self.cursor
            
        if index < 0 or index >= len(self.nb.cells):
            return ""
            
        cell = self.nb.cells[index]
        
        # 1. 获取代码
        code = cell.source
        
        # 2. 获取并清洗输出 (复用之前的静态方法)
        parsed_out = self.categorize_outputs(cell.outputs)
        clean_output = parsed_out['ai_text']
        
        # 3. 组合成 AI 易读的格式
        context_str = (
            f"【执行的代码】:\n{code}\n\n"
            f"【产生的清洗后输出】:\n{clean_output}"
        )
        
        return context_str
    
    # ==========================================
    #           4. 历史导出 (History Export)
    # ==========================================
    def export_history_json(self):
        """
        导出 Notebook 执行历史为 JSON 字符串，供 ProjectAdvisor 使用。
        
        Returns:
            str: JSON 格式的历史记录
        """
        import json
        
        history = []
        for i, cell in enumerate(self.nb.cells):
            if cell.cell_type == 'code':
                parsed = self.categorize_outputs(cell.outputs)
                
                # 只导出有输出的 Cell（已执行过的）
                if parsed['ai_text'] or parsed['error'] or parsed['images'] > 0:
                    history.append({
                        "id": i + 1,
                        "code": cell.source,
                        "output": parsed['ai_text'],
                        "has_image": parsed['images'] > 0,
                        "error": parsed['error']
                    })
        
        return json.dumps(history, ensure_ascii=False, indent=2)
    
    def export_history_summary(self, max_cells=10):
        """
        导出简化的历史摘要（用于长上下文优化）
        
        Args:
            max_cells: 最多保留多少个 Cell 的历史
            
        Returns:
            str: 简化的历史摘要
        """
        import json
        
        history = []
        cells_with_output = []
        
        # 收集所有有输出的 Cell
        for i, cell in enumerate(self.nb.cells):
            if cell.cell_type == 'code':
                parsed = self.categorize_outputs(cell.outputs)
                if parsed['ai_text'] or parsed['error'] or parsed['images'] > 0:
                    cells_with_output.append((i, cell, parsed))
        
        # 如果超过限制，保留最近的 N 个
        if len(cells_with_output) > max_cells:
            cells_with_output = cells_with_output[-max_cells:]
        
        # 构建历史
        for i, cell, parsed in cells_with_output:
            # 截断过长的输出
            output_text = parsed['ai_text']
            if len(output_text) > 500:
                output_text = output_text[:500] + "\n...(输出过长，已截断)"
            
            history.append({
                "id": i + 1,
                "code": cell.source[:200] + ("..." if len(cell.source) > 200 else ""),
                "output": output_text,
                "has_image": parsed['images'] > 0,
                "error": parsed['error']
            })
        
        return json.dumps(history, ensure_ascii=False, indent=2)
        








