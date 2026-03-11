import sys
import json
# 引入我们封装好的类
from src.kernel_session import UnifiedKernelSession
from src.nbManager import NotebookManager
from src.chat_router import ChatRouter
from src.code_programmer import CodeProgrammer
from src.code_modifier import CodeModifier
from src.data_summarizer import DataSummarizer
from src.plan_manager import PlanManager
from src.planner import Planner
from src.project_advisor import ProjectAdvisor
from src.knowledge_retriever import KnowledgeRetriever
from src.llm_factory import LLMFactory, create_default_llm

# ================= 配置 =================
NOTEBOOK_FILE = "analysis_result.ipynb"

# ================= 初始化组件 =================
print(">>> [系统] 正在初始化 Agent 组件...")
print(">>> [系统] 正在初始化大模型...")

# 使用 LLM 工厂创建模型实例
llm = create_default_llm()

print(f">>> [系统] 大模型初始化完成")

# 1. 启动内核 (现在清理逻辑封装在里面了)
kernel = UnifiedKernelSession("r_global")

# 2. 初始化知识库检索器
print(">>> [系统] 正在初始化知识库检索器...")
knowledge_retriever = KnowledgeRetriever(llm, knowledge_base_path="./知识库")

# 3. 初始化其他组件
nb_manager = NotebookManager(NOTEBOOK_FILE)
router = ChatRouter(llm)
code_programmer = CodeProgrammer(llm, knowledge_retriever=knowledge_retriever)
code_modifier = CodeModifier(llm)
data_summarizer = DataSummarizer(llm)
plan_manager = PlanManager()
planner = Planner(llm, knowledge_retriever=knowledge_retriever)
advisor = ProjectAdvisor(llm, knowledge_retriever=knowledge_retriever)

# 全局数据上下文
# 初始化全局记忆字典
global_memory = {}

def get_memory_context_str():
    """获取全局数据上下文字符串"""
    if not global_memory: return "当前内存为空。"
    return json.dumps(global_memory, indent=2, ensure_ascii=False)

def get_notebook_history():
    """获取 Notebook 历史摘要"""
    try:
        # 使用简化版历史（避免上下文过长）
        history = nb_manager.export_history_summary(max_cells=15)
        if history == "[]":
            return "暂无历史代码。"
        return history
    except Exception as e:
        return "历史记录不可用。"

def get_completed_tasks():
    """获取已完成的任务列表"""
    if plan_manager.has_active_plan():
        completed = [task for task in plan_manager.plan if task['status'] == 'completed']
        if completed:
            return "\n".join([f"- {task['task']}" for task in completed])
    return "暂无已完成任务。"

# ================= 主循环 =================

def main_loop():
    # 初始化全局变量
    current_data_context = "当前无数据上下文。"
    last_run_context = None
    
    # 启动时检查是否有未完成的规划
    if plan_manager.has_active_plan() and not plan_manager.is_plan_completed():
        print("\n" + "="*50)
        print(">>> [系统] 检测到未完成的规划:")
        print(plan_manager.get_plan_summary())
        print("="*50)
        print("提示: 输入 '继续' 执行下一个任务，或输入新需求创建新规划。\n")
    
    while True:
        # 显示状态
        cursor_display = nb_manager.cursor + 1
        total_cells = len(nb_manager.nb.cells)
        print(f'当前cell:{cursor_display}')
        # 获取输入
        try:
            user_input = input(f"\n[Cell {cursor_display}/{total_cells}] >>> (输入指令/代码/q): ")
        except KeyboardInterrupt:
            # 支持 Ctrl+C 退出
            print("\n>>> 检测到中断信号，准备退出...")
            break

        # 特殊处理：空输入（直接回车）= 运行当前 Cell
        if user_input.strip() == "":
            actions = [{"type": "RUN"}]
        else:
            # 准备上下文给代码生成器
            context_str = get_memory_context_str()
            # 1. 解析动作链
            actions = router.parse(user_input, nb_manager.cursor, total_cells)
        
        # ==========================================
        # 1. 初始化本轮执行缓冲区
        # ==========================================
        batch_log_buffer = "" 
        has_execution = False
        code_modified = False  # 标记本轮是否修改了代码
        
        # 2. 遍历执行动作
        should_exit = False
        print(actions)
        for action in actions:
            print(action)
            action_type = action.get("type")
            content = action.get("content")
            target = action.get("target")
            position = action.get("position", "AFTER")
            
            # --- 分支: 退出 ---
            if action_type == "EXIT":
                should_exit = True
                break
            
            # --- 分支: 导航与结构 ---
            elif action_type == "JUMP":
                if target == "last": target_idx = len(nb_manager.nb.cells) - 1
                else: target_idx = int(target) - 1
                nb_manager.jump_to(target_idx)

            elif action_type == "INSERT_CELL":
                nb_manager.insert_cell("", position=position)

            elif action_type == "DELETE_CELL":
                nb_manager.delete_current_cell()

            # --- 分支: 内容生成 ---
            elif action_type == "DIRECT_CODE":
                code_to_write = ""
                code_to_write = content
                if code_to_write:
                    nb_manager.set_current_cell_code(code_to_write)
                    code_modified = True
            
            # --- 分支: 修改代码 (MODIFY_CODE) ---
            elif action_type == "MODIFY_CODE":
                print(f"    [代码修改器] 正在分析并修改当前 Cell...")
                
                # 1. 获取当前 Cell 的代码
                current_code = nb_manager.get_current_cell_content()
                
                if not current_code or current_code.strip() == "":
                    print("    [警告] 当前 Cell 为空，无法修改。")
                    continue
                
                # 2. 获取当前 Cell 的运行输出（如果有）
                if 0 <= nb_manager.cursor < len(nb_manager.nb.cells):
                    cell = nb_manager.nb.cells[nb_manager.cursor]
                    parsed_output = nb_manager.categorize_outputs(cell.outputs)
                    
                    # 组合输出信息
                    execution_output = ""
                    if parsed_output['ai_text']:
                        execution_output += f"输出:\n{parsed_output['ai_text']}\n"
                    if parsed_output['error']:
                        execution_output += f"错误:\n{parsed_output['error']}\n"
                    if parsed_output['images'] > 0:
                        execution_output += f"生成了 {parsed_output['images']} 张图片\n"
                    
                    if not execution_output:
                        execution_output = "（当前 Cell 尚未运行）"
                else:
                    execution_output = ""
                
                # 3. 调用 CodeModifier 修改代码
                try:
                    modified_code = code_modifier.modify_code(
                        current_code=current_code,
                        user_request=content,
                        execution_output=execution_output
                    )

                    # 4. 更新 Cell 代码
                    if modified_code and modified_code != current_code:
                        nb_manager.set_current_cell_code(modified_code)
                        print(f"    [完成] 代码已修改。")
                        code_modified = True
                    else:
                        print("    [提示] 代码未发生变化。")

                except Exception as e:
                    print(f"    [错误] 代码修改失败: {e}")
                    print(f"    提示: 请检查修改需求是否明确。")

            elif action_type == "AI_GEN":
                print(f"    [AI] 正在规划并生成代码块: {content}")

                # 准备额外的上下文
                notebook_history = get_notebook_history()
                completed_tasks = get_completed_tasks()

                # 1. 一次性生成所有步骤
                steps = code_programmer.generate_code(
                    content,
                    data_context=current_data_context,
                    notebook_history=notebook_history,
                    completed_tasks=completed_tasks
                )
            
                if not steps:
                    print("    [警告] 未生成有效代码。")
                    continue

                print(f"    [系统] AI 生成了 {len(steps)} 个代码块，正在写入 Notebook...")
            
                # 2. 确定插入位置
                # 如果 Router 说 INSERT，就插在当前光标后；如果是 APPEND，也是插在最后
                # 无论哪种，我们都以当前光标为基准，向后连续插入
            
                # 记录这批新代码的起始索引
                first_new_cell_idx = -1
            
                # 3. 批量插入循环
                for i, code in enumerate(steps):
                    # 插入空白 Cell (这会自动更新 nb_manager.cursor)
                    # position="AFTER" 保证了顺序：
                    # 当前光标 5 -> 插入后变成 6 -> 光标移到 6
                    # 下一次循环 -> 插入到 6 后面变成 7 -> 光标移到 7
                    nb_manager.insert_cell("", position="AFTER")

                    # 填入代码（代码已包含注释）
                    nb_manager.set_current_cell_code(code)

                    # 记录第一块的位置
                    if i == 0:
                        first_new_cell_idx = nb_manager.cursor

                # 4. 体验优化：光标回跳
                # 写入完了，光标现在在最后一个新 Cell 上
                # 我们把它移回这批代码的第一个，方便用户开始 Review 和运行
                if first_new_cell_idx != -1:
                    nb_manager.jump_to(first_new_cell_idx)
                    print(f"    [完成] 代码已批量写入。光标已移回 Cell {first_new_cell_idx + 1}。")
                    print(f"    >>> 请按 [回车] 逐个运行新生成的代码块。")
                    code_modified = True

            # --- 分支: 运行 ---
            # === 动作: 运行 (RUN) ===
            elif action_type == "RUN":
                print(f">>> 正在运行 Cell {nb_manager.cursor + 1} ...")
                success, outputs, _ = nb_manager.execute_current_cell(kernel)
            
                # --- 用户反馈 (保持不变) ---
                parsed = nb_manager.categorize_outputs(outputs)
                if success:
                    if parsed['images'] > 0: print("    [图形] 图片已生成。")
                
                    # --- 【关键修改】获取完整的 Cell 上下文 ---
                    # 直接调用 NotebookManager 的新方法
                    last_run_context = nb_manager.get_cell_context(nb_manager.cursor - 1 if nb_manager.cursor > 0 else 0)
                
                    print("    [系统] 运行成功，上下文已缓存。")
                else:
                    print(f"    [报错] {parsed['error']}")

            # === 动作: 总结 (SUMMARIZE) ===
            elif action_type == "SUMMARIZE" or action_type == "DATA_SUMMARIZE":
                if last_run_context:
                    print(">>> [系统] 正在基于【代码+结果】更新记忆...")
                
                    # 直接把组合好的字符串扔给 AI，传入全局上下文
                    new_summary = data_summarizer.generate_update_patch(
                        last_run_context,
                        global_context=get_memory_context_str()
                    )
                    # 更新全局记忆
                    if new_summary:
                        global_memory.update(new_summary)
                        current_data_context = json.dumps(global_memory, indent=2, ensure_ascii=False)
                        print(f"    [记忆更新]: {current_data_context}")
                    else:
                        print("    [系统] 无新的状态变化。")
                else:
                    print("    [警告] 没有可总结的运行上下文。")
            
            # === 动作: 执行下一个任务 (NEXT_TASK) ===
            elif action_type == "NEXT_TASK":
                if not plan_manager.has_active_plan():
                    print("    [提示] 当前没有活跃的规划。请先描述您的需求。")
                    continue
                
                if plan_manager.is_plan_completed():
                    print("    [完成] 所有规划任务已执行完毕！")
                    plan_manager.clear_plan()
                    continue
                
                # 获取当前任务
                current_task = plan_manager.get_current_task()
                if not current_task:
                    print("    [错误] 无法获取当前任务。")
                    continue
                
                print(f"\n{'='*50}")
                print(f">>> [执行任务 {current_task['id']}]: {current_task['task']}")
                print(f"{'='*50}\n")
                
                # 标记任务为进行中
                current_task['status'] = 'in_progress'
                plan_manager.save_plan()
                
                # 使用 CodeProgrammer 生成代码
                print(f"    [AI] 正在生成代码...")

                # 准备额外的上下文
                notebook_history = get_notebook_history()
                completed_tasks = get_completed_tasks()

                steps = code_programmer.generate_code(
                    current_task['task'],
                    data_context=current_data_context,
                    notebook_history=notebook_history,
                    completed_tasks=completed_tasks
                )
                
                if not steps:
                    print("    [警告] 未生成有效代码。")
                    continue
                
                print(f"    [系统] AI 生成了 {len(steps)} 个代码块，正在写入 Notebook...")
                
                # 记录这批新代码的起始索引
                first_new_cell_idx = -1
                
                # 批量插入代码
                for i, code in enumerate(steps):
                    # 插入空白 Cell
                    nb_manager.insert_cell("", position="AFTER")

                    # 填入代码（代码已包含注释）
                    nb_manager.set_current_cell_code(code)

                    # 记录第一块的位置
                    if i == 0:
                        first_new_cell_idx = nb_manager.cursor
                
                # 光标回跳到第一个新 Cell
                if first_new_cell_idx != -1:
                    nb_manager.jump_to(first_new_cell_idx)
                    print(f"    [完成] 代码已写入。光标已移至 Cell {first_new_cell_idx + 1}。")
                    print(f"\n>>> 请按 [回车] 逐个运行代码块。")
                    print(f">>> 运行完成后，输入 '继续' 执行下一个任务。\n")
                    
                    # 标记当前任务为已完成
                    plan_manager.mark_current_completed()
                    
                    # 显示进度
                    progress = plan_manager.get_progress()
                    print(f"[进度] {progress['completed']}/{progress['total']} 任务已完成 ({progress['percentage']}%)")
                    
                    code_modified = True
            
            # === 动作: 显示规划 (SHOW_PLAN) ===
            elif action_type == "SHOW_PLAN":
                if plan_manager.has_active_plan():
                    print(f"\n{'='*50}")
                    print(plan_manager.get_plan_summary())
                    print(f"{'='*50}\n")
                else:
                    print("    [提示] 当前没有活跃的规划。")

            # === 动作: 创建规划 (CREATE_PLAN) ===
            elif action_type == "CREATE_PLAN":
                print(f"\n{'='*50}")
                print(">>> [系统] 检测到复杂需求，正在生成规划...")

                # 准备额外的上下文
                notebook_history = get_notebook_history()
                completed_tasks = get_completed_tasks()

                # 调用规划器生成任务列表
                tasks = planner.create_plan(
                    content,
                    data_context=current_data_context,
                    notebook_history=notebook_history,
                    completed_tasks=completed_tasks
                )

                if tasks:
                    # 创建新规划
                    num_tasks = plan_manager.create_plan(tasks)

                    print(f"\n{'='*50}")
                    print(plan_manager.get_plan_summary())
                    print(f"{'='*50}\n")

                    print("提示:")
                    print("  - 输入 '按计划进行' 开始执行第一个任务")
                    print("  - 输入 '查看规划' 查看详细进度\n")
                else:
                    print("    [错误] 规划生成失败，请重新描述您的需求。\n")

            # === 动作: 按计划执行 (FOLLOW_PLAN) ===
            elif action_type == "FOLLOW_PLAN":
                if not plan_manager.has_active_plan():
                    print("    [提示] 当前没有活跃的规划。请先描述您的需求。")
                    continue

                if plan_manager.is_plan_completed():
                    print("    [完成] 所有规划任务已执行完毕！")
                    plan_manager.clear_plan()
                    continue

                # 获取当前任务
                current_task = plan_manager.get_current_task()
                if not current_task:
                    print("    [错误] 无法获取当前任务。")
                    continue

                print(f"\n{'='*50}")
                print(f">>> [执行任务 {current_task['id']}]: {current_task['task']}")
                print(f"{'='*50}\n")

                # 标记任务为进行中
                current_task['status'] = 'in_progress'
                plan_manager.save_plan()

                # 将当前任务作为新的用户输入，传给意图识别器
                # 添加前缀标识这是来自规划的任务
                task_input = f"[规划任务]: {current_task['task']}"

                print(f"    [系统] 将任务提交给意图识别器...")

                # 调用路由器解析这个任务
                task_actions = router.parse(task_input, nb_manager.cursor, total_cells)

                print(f"    [系统] 识别到的动作: {[a.get('type') for a in task_actions]}")

                # 执行识别到的动作（合并到当前的动作链中）
                for task_action in task_actions:
                    # 递归处理任务动作
                    action_type = task_action.get("type")
                    action_content = task_action.get("content")

                    # 跳过 FOLLOW_PLAN 本身，避免无限循环
                    if action_type == "FOLLOW_PLAN":
                        continue

                    # 将任务动作插入到当前循环中处理
                    # 这里我们简单地处理 AI_GEN 动作（最常见的情况）
                    if action_type == "AI_GEN":
                        print(f"    [AI] 正在生成代码...")

                        # 准备额外的上下文
                        notebook_history = get_notebook_history()
                        completed_tasks = get_completed_tasks()

                        steps = code_programmer.generate_code(
                            action_content,
                            data_context=current_data_context,
                            notebook_history=notebook_history,
                            completed_tasks=completed_tasks
                        )

                        if not steps:
                            print("    [警告] 未生成有效代码。")
                            break

                        print(f"    [系统] AI 生成了 {len(steps)} 个代码块，正在写入 Notebook...")

                        # 记录这批新代码的起始索引
                        first_new_cell_idx = -1

                        # 批量插入代码
                        for i, code in enumerate(steps):
                            # 插入空白 Cell
                            nb_manager.insert_cell("", position="AFTER")

                            # 填入代码（代码已包含注释）
                            nb_manager.set_current_cell_code(code)

                            # 记录第一块的位置
                            if i == 0:
                                first_new_cell_idx = nb_manager.cursor

                        # 光标回跳到第一个新 Cell
                        if first_new_cell_idx != -1:
                            nb_manager.jump_to(first_new_cell_idx)
                            print(f"    [完成] 代码已写入。光标已移至 Cell {first_new_cell_idx + 1}。")
                            print(f"\n>>> 请按 [回车] 逐个运行代码块。")
                            print(f">>> 运行完成后，输入 '继续' 执行下一个任务。\n")

                            # 标记当前任务为已完成
                            plan_manager.mark_current_completed()

                            # 显示进度
                            progress = plan_manager.get_progress()
                            print(f"[进度] {progress['completed']}/{progress['total']} 任务已完成 ({progress['percentage']}%)")

                            code_modified = True
                            break
                    else:
                        print(f"    [提示] 识别到动作: {action_type}，暂未处理规划任务的此动作类型")
                        # 标记任务完成，避免卡住
                        plan_manager.mark_current_completed()
                        break
            
            # === 动作: 问答 (QA) ===
            elif action_type == "QA":
                print(f"\n>>> [顾问] 正在分析您的问题...")
                
                # 获取 notebook 历史
                try:
                    # 优先使用简化版历史（避免上下文过长）
                    notebook_history = nb_manager.export_history_summary(max_cells=10)
                    
                    # 如果历史为空，提供提示
                    if notebook_history == "[]":
                        notebook_history = "当前还没有执行过任何代码。"
                    
                except Exception as e:
                    print(f"    [警告] 获取历史失败: {e}")
                    notebook_history = "历史记录不可用。"
                
                # 咨询项目顾问
                try:
                    answer = advisor.ask(
                        user_question=content,
                        global_context=current_data_context,
                        notebook_history_json=notebook_history
                    )
                    
                    print(f"\n{'='*50}")
                    print(f"[顾问回答]:")
                    print(answer)
                    print(f"{'='*50}\n")
                    
                except Exception as e:
                    print(f"    [错误] 顾问服务异常: {e}")
                    print(f"    提示: 请检查 LLM 服务是否正常运行。")

        if should_exit:
            break

        # --- 交互提示 ---
        if code_modified:
            print("-" * 40)
            print(f"代码已就绪 (Cell {nb_manager.cursor + 1})。按 [回车] 运行，或输入指令修改。")
            print("-" * 40)

# ================= 程序入口 =================
if __name__ == "__main__":
    try:
        main_loop()
    except Exception as e:
        print(f"\n!!! 程序发生未捕获异常: {e}")
    finally:
        # 无论如何都会执行这里
        print("\n" + "="*30)
        print(">>> 正在清理资源...")
        kernel.shutdown()  # <--- 调用封装好的清理方法
        print(">>> Bye!")






