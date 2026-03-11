import streamlit as st
import json
import time
import jupyter_client # 需要确保安装了 jupyter_client
from typing import List, Dict, Any

# 引入业务逻辑模块
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
from src.llm_factory import LLMFactory, create_default_llm, LLMConfig
from jupyter_client.kernelspec import KernelSpecManager
#from src.chat_manager import get_chat_manager
from src.chat_manager import ChatManager, init_chat_state

# ================= 配置 =================
NOTEBOOK_FILE = "analysis_result.ipynb"

# ================= 初始化 Session State =================
def init_session_state():
    # 0. 动态检测系统内核 (增强版)
    if 'available_kernels' not in st.session_state:
        try:
            ksm = KernelSpecManager()
            # 获取所有内核的详细规格
            specs = ksm.get_all_specs()
            
            kernels = {}
            for name, details in specs.items():
                # details 结构通常是: {'resource_dir': '...', 'spec': {'display_name': '...', ...}}
                spec = details.get('spec', {})
                display_name = spec.get('display_name', name)
                
                # 处理同名显示的情况 (防止 display_name 重复覆盖)
                if display_name in kernels:
                    display_name = f"{display_name} ({name})"
                
                kernels[display_name] = name
            
            # 按名称排序，方便查找
            sorted_kernels = dict(sorted(kernels.items()))
            st.session_state.available_kernels = sorted_kernels
            
            # 保存一下搜索路径，方便调试
            st.session_state.kernel_dirs = ksm.kernel_dirs
            
        except Exception as e:
            st.error(f"内核检测严重失败: {e}")
            # 兜底默认值
            st.session_state.available_kernels = {"Python 3 (Default)": "python3", "R (Default)": "ir"}

    # 1. 核心状态
    if 'kernel_display_name' not in st.session_state:
        # 默认尝试找 Python 或 R
        keys = list(st.session_state.available_kernels.keys())
        default_k = next((k for k in keys if "python" in k.lower()), keys[0])
        st.session_state.kernel_display_name = default_k
        st.session_state.kernel_name = st.session_state.available_kernels[default_k]

    if 'kernel' not in st.session_state:
        st.session_state.kernel = UnifiedKernelSession(st.session_state.kernel_name)
        st.session_state.kernel_ready = True

    if 'nb_manager' not in st.session_state:
        st.session_state.nb_manager = NotebookManager(NOTEBOOK_FILE)
    
    # 2. LLM 相关
    if 'llm_config' not in st.session_state:
        # 尝试从文件或环境变量加载配置
        config = LLMFactory.load_from_file()
        if not config:
            config = LLMFactory.load_from_env()
        if not config:
            config = LLMFactory.get_default_config("ollama")

        st.session_state.llm_config = config

    if 'llm' not in st.session_state:
        try:
            st.session_state.llm = LLMFactory.create_llm(st.session_state.llm_config)
            st.session_state.llm_ready = True
        except Exception as e:
            st.session_state.llm_ready = False
            st.error(f"LLM 初始化失败: {e}")
            
    # 3. Agent 组件
    if 'router' not in st.session_state: st.session_state.router = ChatRouter(st.session_state.llm)
    if 'knowledge_retriever' not in st.session_state: st.session_state.knowledge_retriever = KnowledgeRetriever(st.session_state.llm, knowledge_base_path="./知识库")
    if 'code_programmer' not in st.session_state: st.session_state.code_programmer = CodeProgrammer(st.session_state.llm, knowledge_retriever=st.session_state.knowledge_retriever)
    if 'code_modifier' not in st.session_state: st.session_state.code_modifier = CodeModifier(st.session_state.llm)
    if 'data_summarizer' not in st.session_state: st.session_state.data_summarizer = DataSummarizer(st.session_state.llm)
    if 'plan_manager' not in st.session_state: st.session_state.plan_manager = PlanManager()
    if 'planner' not in st.session_state: st.session_state.planner = Planner(st.session_state.llm, knowledge_retriever=st.session_state.knowledge_retriever)
    if 'advisor' not in st.session_state: st.session_state.advisor = ProjectAdvisor(st.session_state.llm, knowledge_retriever=st.session_state.knowledge_retriever)

    # 4. 界面交互状态
    #if 'chat_messages' not in st.session_state: st.session_state.chat_messages = []
    if 'global_memory' not in st.session_state: st.session_state.global_memory = {}
    if 'current_data_context' not in st.session_state: st.session_state.current_data_context = "当前无数据上下文。"
    if 'last_run_context' not in st.session_state: st.session_state.last_run_context = None
    if 'is_editing' not in st.session_state: st.session_state.is_editing = False
    init_chat_state()


def restart_kernel(display_name):
    """根据显示名称切换内核"""
    if st.session_state.kernel: st.session_state.kernel.shutdown()
    
    new_kernel_name = st.session_state.available_kernels.get(display_name, "python3")
    try:
        st.session_state.kernel = UnifiedKernelSession(new_kernel_name)
        st.session_state.kernel_display_name = display_name
        st.session_state.kernel_name = new_kernel_name
        st.toast(f"内核已切换为 {display_name}", icon="🔄")
    except Exception as e:
        st.error(f"内核启动失败: {e}")

# ================= 辅助函数 =================
def get_memory_context_str():
    """获取全局数据上下文字符串"""
    if not st.session_state.global_memory:
        return "当前内存为空。"
    return json.dumps(st.session_state.global_memory, indent=2, ensure_ascii=False)

def get_notebook_history():
    """获取 Notebook 历史摘要"""
    try:
        history = st.session_state.nb_manager.export_history_summary(max_cells=15)
        if history == "[]":
            return "暂无历史代码。"
        return history
    except Exception as e:
        return "历史记录不可用。"

def get_completed_tasks():
    """获取已完成的任务列表"""
    if st.session_state.plan_manager.has_active_plan():
        completed = [task for task in st.session_state.plan_manager.plan if task['status'] == 'completed']
        if completed:
            return "\n".join([f"- {task['task']}" for task in completed])
    return "暂无已完成任务。"

def add_chat_message(role: str, content: str, is_system: bool = False):
    """添加聊天消息到历史记录 - 使用新的 ChatManager"""
    chat = ChatManager()
    # 系统消息作为 assistant 消息显示
    if is_system:
        chat.add_assistant(f"🔔 {content}")
    elif role == "assistant":
        chat.add_assistant(content)
    elif role == "user":
        chat.add_user(content)

def execute_actions(actions: List[Dict[str, Any]]):
    """执行动作链 - 支持所有动作类型"""
    if not actions:
        return

    batch_log_buffer = ""
    has_execution = False
    code_modified = False
    print(f"[DEBUG] 开始执行动作链，共 {len(actions)} 个动作")

    # 检测并防止重复执行 FOLLOW_PLAN
    follow_plan_count = sum(1 for a in actions if a.get("type") in ["FOLLOW_PLAN", "NEXT_TASK"])
    if follow_plan_count > 1:
        print(f"[WARNING] 检测到 {follow_plan_count} 个 FOLLOW_PLAN/NEXT_TASK 动作，只执行第一个")

    # 标记是否已经执行过 FOLLOW_PLAN/NEXT_TASK
    has_executed_plan_action = False

    for action in actions:
        action_type = action.get("type")
        action_type = action.get("type")
        content = action.get("content")
        target = action.get("target")
        position = action.get("position", "AFTER")
        
        # === 导航与结构 ===
        if action_type == "JUMP":
            if target == "last":
                target_idx = len(st.session_state.nb_manager.nb.cells) - 1
            else:
                target_idx = int(target) - 1
            st.session_state.nb_manager.jump_to(target_idx)
            add_chat_message("system", f"已跳转到 Cell {target_idx + 1}", True)
        
        elif action_type == "INSERT_CELL":
            st.session_state.nb_manager.insert_cell("", position=position)
            add_chat_message("system", "已插入新单元格", True)
        
        elif action_type == "DELETE_CELL":
            st.session_state.nb_manager.delete_current_cell()
            add_chat_message("system", "已删除当前单元格", True)
        
        # === 内容生成 ===
        elif action_type == "DIRECT_CODE":
            code_to_write = content
            if code_to_write:
                st.session_state.nb_manager.set_current_cell_code(code_to_write)
                add_chat_message("system", "代码已填入当前单元格", True)
                code_modified = True
        
        elif action_type == "MODIFY_CODE":
            add_chat_message("system", "正在分析并修改当前 Cell...", True)
            
            current_code = st.session_state.nb_manager.get_current_cell_content()
            
            if not current_code or current_code.strip() == "":
                add_chat_message("system", "当前 Cell 为空，无法修改。", True)
                continue
            
            # 获取当前 Cell 的运行输出
            if 0 <= st.session_state.nb_manager.cursor < len(st.session_state.nb_manager.nb.cells):
                cell = st.session_state.nb_manager.nb.cells[st.session_state.nb_manager.cursor]
                parsed_output = st.session_state.nb_manager.categorize_outputs(cell.outputs)
                
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
            
            try:
                modified_code = st.session_state.code_modifier.modify_code(
                    current_code=current_code,
                    user_request=content,
                    execution_output=execution_output
                )
                
                if modified_code and modified_code != current_code:
                    st.session_state.nb_manager.set_current_cell_code(modified_code)
                    add_chat_message("system", "代码已修改。", True)
                    code_modified = True
                else:
                    add_chat_message("system", "代码未发生变化。", True)
            except Exception as e:
                add_chat_message("system", f"代码修改失败: {e}", True)
        
        elif action_type == "AI_GEN":
            add_chat_message("system", f"正在规划并生成代码块: {content}", True)
            
            notebook_history = get_notebook_history()
            completed_tasks = get_completed_tasks()
            
            steps = st.session_state.code_programmer.generate_code(
                content,
                data_context=st.session_state.current_data_context,
                notebook_history=notebook_history,
                completed_tasks=completed_tasks
            )
            
            if not steps:
                add_chat_message("system", "未生成有效代码。", True)
                continue
            
            add_chat_message("system", f"AI 生成了 {len(steps)} 个代码块，正在写入 Notebook...", True)
            
            first_new_cell_idx = -1
            
            for i, code in enumerate(steps):
                st.session_state.nb_manager.insert_cell("", position="AFTER")
                st.session_state.nb_manager.set_current_cell_code(code)
                
                if i == 0:
                    first_new_cell_idx = st.session_state.nb_manager.cursor
            
            if first_new_cell_idx != -1:
                st.session_state.nb_manager.jump_to(first_new_cell_idx)
                add_chat_message("system", f"代码已批量写入。光标已移回 Cell {first_new_cell_idx + 1}。", True)
                code_modified = True

        # === 运行 ===
        elif action_type == "RUN":
            success, outputs, _ = st.session_state.nb_manager.execute_current_cell(st.session_state.kernel)
            
            parsed = st.session_state.nb_manager.categorize_outputs(outputs)
            if success:
                if parsed['images'] > 0:
                    add_chat_message("system", "图片已生成。", True)
                
                st.session_state.last_run_context = st.session_state.nb_manager.get_cell_context(
                    st.session_state.nb_manager.cursor - 1 if st.session_state.nb_manager.cursor > 0 else 0
                )
                add_chat_message("system", "运行成功，上下文已缓存。", True)
            else:
                add_chat_message("system", f"运行报错: {parsed['error']}", True)
            
            has_execution = True
        
        # === 总结 ===
        elif action_type == "SUMMARIZE" or action_type == "DATA_SUMMARIZE":
            if st.session_state.last_run_context:
                add_chat_message("system", "正在基于【代码+结果】更新记忆...", True)
                
                new_summary = st.session_state.data_summarizer.generate_update_patch(
                    st.session_state.last_run_context,
                    global_context=get_memory_context_str()
                )
                
                if new_summary:
                    st.session_state.global_memory.update(new_summary)
                    st.session_state.current_data_context = json.dumps(
                        st.session_state.global_memory, indent=2, ensure_ascii=False
                    )
                    add_chat_message("system", f"记忆更新: {st.session_state.current_data_context}", True)
                else:
                    add_chat_message("system", "无新的状态变化。", True)
            else:
                add_chat_message("system", "没有可总结的运行上下文。", True)
        
        # === 规划 ===
        elif action_type == "SHOW_PLAN":
            if st.session_state.plan_manager.has_active_plan():
                add_chat_message("assistant", f"```\n{st.session_state.plan_manager.get_plan_summary()}\n```", False)
            else:
                add_chat_message("system", "当前没有活跃的规划。", True)
        
        elif action_type == "CREATE_PLAN":
            add_chat_message("system", "检测到复杂需求，正在生成规划...", True)
            
            notebook_history = get_notebook_history()
            completed_tasks = get_completed_tasks()
            
            tasks = st.session_state.planner.create_plan(
                content,
                data_context=st.session_state.current_data_context,
                notebook_history=notebook_history,
                completed_tasks=completed_tasks
            )
            
            if tasks:
                num_tasks = st.session_state.plan_manager.create_plan(tasks)
                add_chat_message("assistant", f"```\n{st.session_state.plan_manager.get_plan_summary()}\n```", False)
            else:
                add_chat_message("system", "规划生成失败，请重新描述您的需求。", True)
        
        elif action_type == "FOLLOW_PLAN" or action_type == "NEXT_TASK":
            # 防止重复执行 FOLLOW_PLAN/NEXT_TASK
            if has_executed_plan_action:
                print(f"[WARNING] 跳过重复的 {action_type} 动作")
                continue

            has_executed_plan_action = True

            if not st.session_state.plan_manager.has_active_plan():
                add_chat_message("system", "当前没有活跃的规划。请先描述您的需求。", True)
                continue

            if st.session_state.plan_manager.is_plan_completed():
                add_chat_message("system", "所有规划任务已执行完毕！", True)
                st.session_state.plan_manager.clear_plan()
                continue

            # 获取当前任务
            current_task = st.session_state.plan_manager.get_current_task()
            if not current_task:
                add_chat_message("system", "无法获取当前任务。", True)
                continue

            # 检查当前任务是否已经在执行中，防止重复
            if current_task.get('status') == 'completed':
                add_chat_message("system", f"任务 {current_task['id']} 已经完成，跳过", True)
                continue

            add_chat_message("system", f"正在执行任务 {current_task['id']}: {current_task['task']}", True)
            current_task['status'] = 'in_progress'
            st.session_state.plan_manager.save_plan()

            notebook_history = get_notebook_history()
            completed_tasks = get_completed_tasks()

            steps = st.session_state.code_programmer.generate_code(
                current_task['task'],
                data_context=st.session_state.current_data_context,
                notebook_history=notebook_history,
                completed_tasks=completed_tasks
            )

            if not steps:
                add_chat_message("system", "未生成有效代码。", True)
                continue

            add_chat_message("system", f"AI 生成了 {len(steps)} 个代码块，正在写入 Notebook...", True)

            first_new_cell_idx = -1

            for i, code in enumerate(steps):
                st.session_state.nb_manager.insert_cell("", position="AFTER")
                st.session_state.nb_manager.set_current_cell_code(code)

                if i == 0:
                    first_new_cell_idx = st.session_state.nb_manager.cursor

            if first_new_cell_idx != -1:
                st.session_state.nb_manager.jump_to(first_new_cell_idx)
                st.session_state.plan_manager.mark_current_completed()

                progress = st.session_state.plan_manager.get_progress()
                add_chat_message("system",
                    f"代码已写入。光标已移至 Cell {first_new_cell_idx + 1}。进度: {progress['completed']}/{progress['total']} 任务已完成 ({progress['percentage']}%)",
                    True
                )
                code_modified = True
        
        # === 问答 ===
        elif action_type == "QA":
            add_chat_message("system", "正在分析您的问题...", True)
            
            try:
                notebook_history = st.session_state.nb_manager.export_history_summary(max_cells=10)
                if notebook_history == "[]":
                    notebook_history = "当前还没有执行过任何代码。"
            except Exception as e:
                notebook_history = "历史记录不可用。"
            
            try:
                answer = st.session_state.advisor.ask(
                    user_question=content,
                    global_context=st.session_state.current_data_context,
                    notebook_history_json=notebook_history
                )
                add_chat_message("assistant", answer, False)
            except Exception as e:
                add_chat_message("system", f"顾问服务异常: {e}", True)

    # 返回是否需要重新加载（移除内部的 st.rerun() 调用）
    return code_modified


# ================= UI 渲染组件 =================

def render_sidebar():
    with st.sidebar:
        st.title("🧩 Agent Pro")
        
        # 1. 动态内核选择
        st.caption("运行环境")
        kernels_map = st.session_state.available_kernels
        
        # 如果没有检测到任何内核（理论上不应该），给个提示
        if not kernels_map:
            st.error("未检测到任何 Jupyter 内核！")
        
        display_names = list(kernels_map.keys())
        
        # 保持当前选择状态
        current_idx = 0
        if st.session_state.kernel_display_name in display_names:
            current_idx = display_names.index(st.session_state.kernel_display_name)
        elif display_names:
            # 如果之前的名字找不到了，默认选第一个
            current_idx = 0
            
        sel_kernel = st.selectbox(
            "Kernel", 
            display_names, 
            index=current_idx, 
            label_visibility="collapsed"
        )
        
        # 真正的内核内部名称 (如 python3, ir)
        real_kernel_name = kernels_map.get(sel_kernel, "python3")
        
        # 显示当前真实的内核名，方便确认
        st.caption(f"ID: `{real_kernel_name}`")
        
        if sel_kernel != st.session_state.kernel_display_name:
            # 传入显示名称和真实名称
            restart_kernel(sel_kernel) 
            st.rerun()
            
        # === 新增：内核调试信息 (平时折叠) ===
        with st.expander("🔍 内核没找到？"):
            st.write("程序搜索了以下路径：")
            # 显示 jupyter 搜索路径
            dirs = st.session_state.get('kernel_dirs', [])
            for d in dirs:
                st.code(d, language="bash")
            st.write("---")
            st.write("检测到的原始列表：")
            st.json(st.session_state.available_kernels)
            st.info("提示：如果内核不在上述路径中，请使用命令注册。")

        st.divider()

        # 2. 大模型选择
        st.caption("大模型配置")
        llm_config = st.session_state.llm_config

        # 模型类型选择
        llm_type_options = {v: k for k, v in LLMFactory.SUPPORTED_TYPES.items()}
        selected_type = st.selectbox(
            "模型类型",
            options=list(llm_type_options.keys()),
            index=list(llm_type_options.values()).index(llm_config.llm_type) if llm_config.llm_type in llm_type_options.values() else 0,
            label_visibility="collapsed"
        )

        # 根据类型显示不同的配置选项
        config_type = llm_type_options[selected_type]

        # 模型名称
        if config_type == "ollama":
            st.text_input(
                "模型名称",
                value=llm_config.model,
                key="llm_model_name",
                help="例如: qwen3-coder:30b"
            )
            st.text_input(
                "Base URL",
                value=llm_config.base_url or "http://localhost:11434",
                key="llm_base_url",
                help="Ollama 服务地址"
            )
        elif config_type == "openai":
            st.text_input(
                "模型名称",
                value=llm_config.model or "gpt-4",
                key="llm_model_name",
                help="例如: gpt-4, gpt-3.5-turbo"
            )
            st.text_input(
                "Base URL",
                value=llm_config.base_url or "https://api.openai.com/v1",
                key="llm_base_url",
                help="API endpoint"
            )
            st.text_input(
                "API Key",
                value=llm_config.api_key or "",
                type="password",
                key="llm_api_key",
                help="OpenAI API Key"
            )
        elif config_type == "qianwen":
            st.text_input(
                "模型名称",
                value=llm_config.model or "qwen-max",
                key="llm_model_name",
                help="例如: qwen-max, qwen-plus"
            )
            st.text_input(
                "API Key",
                value=llm_config.api_key or "",
                type="password",
                key="llm_api_key",
                help="阿里云 DashScope API Key"
            )
        elif config_type == "zhipu":
            st.text_input(
                "模型名称",
                value=llm_config.model or "glm-4",
                key="llm_model_name",
                help="例如: glm-4, glm-3-turbo"
            )
            st.text_input(
                "API Key",
                value=llm_config.api_key or "",
                type="password",
                key="llm_api_key",
                help="智谱 AI API Key"
            )
        else:
            st.text_input(
                "模型名称",
                value=llm_config.model or "gpt-4",
                key="llm_model_name",
                help="模型名称"
            )
            st.text_input(
                "Base URL",
                value=llm_config.base_url or "",
                key="llm_base_url",
                help="API endpoint"
            )
            st.text_input(
                "API Key",
                value=llm_config.api_key or "",
                type="password",
                key="llm_api_key",
                help="API Key"
            )

        # 通用参数
        col1, col2 = st.columns(2)
        with col1:
            temperature = st.slider(
                "温度",
                min_value=0.0,
                max_value=2.0,
                value=llm_config.temperature or 0.7,
                step=0.1,
                key="llm_temperature",
                help="控制输出的随机性，越高越随机"
            )
        with col2:
            max_tokens = st.text_input(
                "最大长度",
                value=str(llm_config.max_tokens) if llm_config.max_tokens else "",
                key="llm_max_tokens",
                help="限制生成长度（可选）"
            )

        # 保存按钮
        if st.button("💾 保存配置", use_container_width=True):
            try:
                # 构建新配置（安全获取 session state 值）
                new_config = LLMConfig(
                    llm_type=config_type,
                    model=st.session_state.get('llm_model_name', llm_config.model or 'gpt-4'),
                    base_url=st.session_state.get('llm_base_url', llm_config.base_url),
                    api_key=st.session_state.get('llm_api_key', llm_config.api_key or ''),
                    temperature=st.session_state.get('llm_temperature', llm_config.temperature or 0.7),
                    max_tokens=int(st.session_state.llm_max_tokens) if st.session_state.get('llm_max_tokens') else None
                )

                # 保存到文件
                LLMFactory.save_to_file(new_config)

                # 更新 session state
                st.session_state.llm_config = new_config
                st.session_state.llm = LLMFactory.create_llm(new_config)

                # 重新初始化所有依赖 LLM 的组件
                st.session_state.router = ChatRouter(st.session_state.llm)
                st.session_state.knowledge_retriever = KnowledgeRetriever(st.session_state.llm, knowledge_base_path="./知识库")
                st.session_state.code_programmer = CodeProgrammer(st.session_state.llm, knowledge_retriever=st.session_state.knowledge_retriever)
                st.session_state.code_modifier = CodeModifier(st.session_state.llm)
                st.session_state.data_summarizer = DataSummarizer(st.session_state.llm)
                st.session_state.planner = Planner(st.session_state.llm, knowledge_retriever=st.session_state.knowledge_retriever)
                st.session_state.advisor = ProjectAdvisor(st.session_state.llm, knowledge_retriever=st.session_state.knowledge_retriever)

                st.success(f"✓ 模型配置已保存并应用：{selected_type} - {new_config.model}")
                st.rerun()

            except Exception as e:
                st.error(f"保存配置失败: {e}")

        # 显示当前配置摘要
        st.caption(f"当前: {selected_type} - {st.session_state.llm_config.model}")
        st.divider()

        # 3. 知识库 (带计数)
        st.caption("知识库")
        kr = st.session_state.knowledge_retriever
        if kr.knowledge_categories:
            selected_cats = st.multiselect(
                "KB", 
                options=kr.knowledge_categories, 
                default=None, 
                label_visibility="collapsed"
            )
            
            # 计算选中分类下的文件总数
            total_docs = 0
            if selected_cats:
                for cat in selected_cats:
                    total_docs += len(kr.knowledge_index.get(cat, []))
                st.info(f"📚 已选 {len(selected_cats)} 类，包含 {total_docs} 篇文档")
            else:
                st.caption(f"共索引 {sum([len(v) for v in kr.knowledge_index.values()])} 篇文档")
        
        st.divider()

        # 3. 规划
        st.caption("当前任务")
        pm = st.session_state.plan_manager
        if pm.has_active_plan():
            progress = pm.get_progress()
            st.progress(progress['percentage'] / 100)
            with st.expander(f"进度 {progress['completed']}/{progress['total']}", expanded=True):
                for task in pm.plan:
                    color = "green" if task['status'] == 'completed' else "gray"
                    st.markdown(f":{color}[●] {task['task']}")
        else:
            st.caption("无活跃任务")

def render_notebook_cell(index: int, cell, is_current: bool = False):
    """渲染单元格：针对 help 参数生成的 Tooltip 结构进行深度修复"""
    
    # 1. 变量定义
    marker_class = f"cell-marker-{index}"
    status_class = "status-active" if is_current else "status-inactive"
    
    # 颜色策略：背景透明，选中时只显示深绿色边框
    bg_color = "transparent"
    border_color = "#22c55e" if is_current else "transparent"
    
    st.markdown(f"""
    <style>
    /* ================= 1. 左侧列 (30px) ================= */
    div[data-testid="column"]:nth-of-type(1) {{
        flex: 0 0 30px !important; 
        min-width: 30px !important;
        padding: 0px !important;
        display: flex;
        flex-direction: column;
        align-items: center; 
        overflow: visible !important; /* 允许 Tooltip 显示 */
    }}
    
    .cell-index-label {{
        font-family: 'Consolas', monospace;
        font-size: 10px; color: #94a3b8;
        margin-bottom: -2px; margin-top: 4px;
        text-align: center; line-height: 1;
    }}

    /* ================= 2. 按钮深度修复 (针对 help Tooltip) ================= */
    
    /* 2.1 压缩 stButton 外壳 */
    div[data-testid="column"]:nth-of-type(1) .stButton {{
        width: 100% !important;
        margin-bottom: -12px !important; /* 紧凑排列 */
        display: flex;
        justify-content: center;
    }}

    /* 2.2 【关键修复】处理 Tooltip 中间层 */
    /* 你的截图中显示的 stTooltipHoverTarget */
    div[data-testid="column"]:nth-of-type(1) [data-testid="stTooltipIcon"] > div {{
        display: flex !important;
        justify-content: center !important;
        width: 100% !important;
    }}

    /* 2.3 按钮本体 (button) 强制极小化 */
    div[data-testid="column"]:nth-of-type(1) button[data-testid="stBaseButton-secondary"] {{
        /* 尺寸锁定 */
        width: 20px !important;
        height: 20px !important;
        min-height: 0px !important;
        min-width: 0px !important;
        
        /* 外观清除 */
        padding: 0px !important;
        background-color: transparent !important;
        border: none !important;
        box-shadow: none !important;
        
        /* 内容对齐 */
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        
        /* 文字设置 */
        color: #cbd5e1 !important;
        line-height: 1 !important;
    }}
    
    /* 2.4 内部文字/图标大小 */
    div[data-testid="column"]:nth-of-type(1) button p {{
        font-size: 14px !important;
        margin: 0 !important;
        padding: 0 !important;
    }}
    
    /* 2.5 鼠标悬停交互 */
    div[data-testid="column"]:nth-of-type(1) button:hover {{
        color: #22c55e !important;
        background-color: rgba(34, 197, 94, 0.1) !important;
        border-radius: 4px !important;
        transform: scale(1.1);
    }}

    /* ================= 3. 右侧内容 (选中显示绿框) ================= */
    
    /* 3.1 边框样式 */
    div[data-testid="column"]:has(div.{marker_class}.status-active) {{
        background-color: {bg_color} !important;
        border: 2px solid {border_color} !important; /* 2px 实线边框 */
        border-radius: 6px;
        padding: 6px 10px !important;
    }}

    /* 3.2 调整代码块间距 */
    div[data-testid="column"]:has(div.{marker_class}) .stCode {{
        margin-top: -1em !important; 
    }}

    /* 3.3 防止右侧被挤压 */
    div[data-testid="column"]:nth-of-type(2) {{
         width: calc(100% - 30px) !important;
         flex: 1 !important;
    }}
    </style>
    """, unsafe_allow_html=True)
    
    # 布局
    col_left, col_content = st.columns([1, 20], gap="small")
    
    # === 左侧 ===
    with col_left:
        st.markdown(f'<div class="cell-index-label">{index+1}</div>', unsafe_allow_html=True)
        
        # 按钮 1
        icon_char = "●" if is_current else "○" 
        if st.button(icon_char, key=f"sel_{index}", help="选中"):
             if not is_current:
                st.session_state.nb_manager.jump_to(index)
                st.session_state.is_editing = False
                st.rerun()

        # 按钮 2
        if st.button("✎", key=f"edit_{index}", help="编辑"):
            st.session_state.nb_manager.jump_to(index)
            if is_current:
                st.session_state.is_editing = not st.session_state.is_editing
            else:
                st.session_state.is_editing = True
            st.rerun()

    # === 右侧 ===
    with col_content:
        # 埋点 Div
        st.markdown(f'<div class="{marker_class} {status_class}" style="width:0; height:0; overflow:hidden; opacity:0; margin:0;"></div>', unsafe_allow_html=True)
        
        if is_current and st.session_state.is_editing:
            with st.form(key=f"edit_form_{index}"):
                new_source = st.text_area("Code", value=cell.source, height=150, label_visibility="collapsed", key=f"edit_area_{index}")
                submitted = st.form_submit_button("💾 保存", type="primary", use_container_width=True)
                if submitted:
                    st.session_state.nb_manager.set_current_cell_code(new_source)
                    st.session_state.is_editing = False
                    st.rerun()
        else:
            lang = "python"
            if "r" in st.session_state.kernel_name.lower(): lang = "r"
            elif "bash" in st.session_state.kernel_name.lower(): lang = "bash"

            if cell.cell_type == 'code':
                st.code(cell.source, language=lang, line_numbers=False)
            else:
                st.markdown(cell.source)
            
            # 输出区域
            if cell.outputs:
                for output in cell.outputs:
                    if output.output_type == 'stream':
                        st.text(output.text)
                    elif output.output_type == 'execute_result':
                        if 'text/plain' in output.data:
                             st.markdown(f"""
                            <div style="font-family: monospace; font-size: 13px; color: #475569;
                                        margin-left: 2px; border-left: 2px solid #e2e8f0;
                                        margin-top: 4px; padding: 4px 0 4px 8px; white-space: pre-wrap;">
                            {output.data['text/plain']}
                            </div>
                            """, unsafe_allow_html=True)
                    elif output.output_type == 'display_data':
                        # 处理图片
                        if 'image/png' in output.data:
                            import base64
                            st.image(base64.b64decode(output.data['image/png']))
                        # 优先使用 Markdown 格式（更简洁）
                        elif 'text/markdown' in output.data:
                            st.markdown(''.join(output.data['text/markdown']))
                        # 其次使用 HTML 格式
                        elif 'text/html' in output.data:
                            st.markdown(''.join(output.data['text/html']), unsafe_allow_html=True)
                        # 最后才使用 text/plain（通常包含格式化字符）
                        elif 'text/plain' in output.data:
                            # 清理 text/plain 的前导空格
                            text = output.data['text/plain']
                            if isinstance(text, list):
                                text = '\n'.join(text)
                            # 移除每行开头和结尾的空白
                            text = '\n'.join(line.strip() for line in text.split('\n'))
                            st.markdown(f"""
                                <div style="font-family: monospace; font-size: 13px; color: #475569;
                                            margin-left: 2px; border-left: 2px solid #e2e8f0;
                                            margin-top: 4px; padding: 4px 0 4px 8px; white-space: pre-wrap;">
                                {text}
                                </div>
                                """, unsafe_allow_html=True)
                    elif output.output_type == 'error':
                        st.error(f"{output.ename}: {output.evalue}")

#from src.chat_manager import get_chat_manager
from src.chat_manager import ChatManager
def render_main_area():
    col_notebook, col_chat = st.columns([2, 1])
    
    # ================= 左侧：Notebook =================
    with col_notebook:
        # 工具栏 CSS
        st.markdown("""
        <style>
        /* 1. 按钮样式 (保持不变) */
        .compact-toolbar .stButton button {
            height: 20px !important;
            min-height: 20px !important;
            padding-top: 0px !important;
            padding-bottom: 0px !important;
            font-size: 14px !important;
            /* 移除之前的 margin-top: -15px，改由容器控制布局，防止错位 */
            margin-top: 0px !important; 
            border: none !important;
            background-color: transparent !important;
            box-shadow: none !important;
            color: #64748b !important;
        }
        .compact-toolbar .stButton button:hover {
            color: #0ea5e9 !important;
            background-color: #f1f5f9 !important;
        }
        
        /* 2. Spinner 样式 */
        div[data-testid="stSpinner"] {
            font-size: 14px !important;
            color: #64748b !important;
            display: flex;
            align-items: center;
        }

        /* 3. 防止变灰 */
        .stApp .block-container, 
        div[data-testid="stVerticalBlock"], 
        div[data-testid="stHorizontalBlock"],
        div[data-testid="column"],
        .element-container, .stMarkdown, .stCode {
            opacity: 1 !important;
            filter: none !important;
            transition: none !important;
        }

        /* === 新增：强制压缩工具栏容器高度 === */
        
        /* 针对左侧列的第一个水平布局块(即工具栏)进行压缩 */
        div[data-testid="column"]:nth-of-type(1) div[data-testid="stHorizontalBlock"] {
            gap: 0.5rem !important;    /* 减小按钮之间的间距 */
            align-items: center !important; 
            margin-top: -15px !important; /* 【关键】整体向上提，抵消掉 padding */
            margin-bottom: -15px !important; /* 【关键】整体拉动下方内容向上 */
            height: 30px !important; /* 强制锁定高度 */
            min-height: 30px !important;
            overflow: hidden !important;
        }
        
        /* 移除工具栏内部元素多余的 margin */
        div[data-testid="column"]:nth-of-type(1) div[data-testid="stHorizontalBlock"] .element-container {
            margin-bottom: 0px !important;
        }

        /* 自定义分割线 */
        .custom-hr {
            margin-top: 5px !important;
            margin-bottom: 5px !important;
            border-bottom: 1px solid #f1f5f9;
        }
        </style>
        """, unsafe_allow_html=True)
        
        # 这里的 div class 虽然不直接包裹 button，但可作为定位参考（如果需要）
        st.markdown('<div class="compact-toolbar"></div>', unsafe_allow_html=True)
        
        t1, t2, t3, status_area = st.columns([1, 1, 1, 5])
        
        run_clicked = False
        with t1:
            if st.button("▶️ 运行", use_container_width=True): run_clicked = True
        with t2:
            if st.button("➕ 添加", use_container_width=True):
                st.session_state.nb_manager.insert_cell("", position="AFTER")
                st.session_state.is_editing = False
                st.rerun()
        with t3:
            if st.button("🗑️ 删除", use_container_width=True):
                st.session_state.nb_manager.delete_current_cell()
                st.rerun()
        
        # 运行逻辑
        if run_clicked:
            if st.session_state.is_editing: st.session_state.is_editing = False
            current_idx = st.session_state.nb_manager.cursor + 1
            with status_area:
                with st.spinner(f"Running cell {current_idx}..."):
                    # 运行并自动跳转到下一个单元格
                    success, outputs, _ = st.session_state.nb_manager.execute_current_cell(st.session_state.kernel, auto_advance=True)
            st.rerun()
            
        # 分割线
        st.markdown('<div class="custom-hr"></div>', unsafe_allow_html=True)
        
        # Notebook 容器
        with st.container(height=820, border=False):
            nb = st.session_state.nb_manager.nb
            cursor = st.session_state.nb_manager.cursor
            
            if not nb.cells:
                st.info("暂无代码块")
            else:
                for i, cell in enumerate(nb.cells):
                    is_curr = (i == cursor)
                    with st.container():
                        render_notebook_cell(i, cell, is_curr)

    # ================= 右侧：聊天（稳定持久版） =================
    with col_chat:
        st.subheader("💬 对话")

        chat = ChatManager()

        # === 聊天显示容器 ===
        chat_container = st.container(height=650, border=False)

        # --- 1. 渲染历史 ---
        with chat_container:
            if not chat.messages:
                st.caption("暂无消息")
            else:
                for msg in chat.messages:
                    avatar = "🤖" if msg["role"] == "assistant" else "👤"
                    with st.chat_message(msg["role"], avatar=avatar):
                        st.markdown(msg["content"])

        # --- 2. 输入 ---
        prompt = st.chat_input("输入指令...")

        # 初始化处理标志
        if "processing_prompt" not in st.session_state:
            st.session_state.processing_prompt = None

        if prompt:
            # A. 用户消息入库
            chat.add_user(prompt)
            
            # 设置待处理的提示词
            st.session_state.processing_prompt = prompt
            
            # 立即刷新页面，显示用户消息
            st.rerun()
        
        # 检查是否有待处理的用户输入
        elif st.session_state.processing_prompt:
            # 保存当前 prompt 用于显示
            current_prompt = st.session_state.processing_prompt

            # 立即清除 processing_prompt，防止 execute_actions() 内部 rerun 时重复执行
            st.session_state.processing_prompt = None

            # B. 执行 Agent / Notebook / QA
            with chat_container:
                with st.chat_message("assistant", avatar="🤖"):
                    with st.status("正在处理...", expanded=True) as status:

                        cursor = st.session_state.nb_manager.cursor
                        total = len(st.session_state.nb_manager.nb.cells)

                        actions = st.session_state.router.parse(current_prompt, cursor, total)
                        print(f"[DEBUG] Router解析到的actions: {actions}")

                        if actions:
                            needs_rerun = execute_actions(actions)
                            # QA 动作已经在 execute_actions 内添加了消息，不需要再添加
                            # 其他动作需要添加完成消息
                            has_qa_action = any(action.get('action') == 'QA' for action in actions)
                            answer = None if has_qa_action else "任务已完成"
                        else:
                            answer = "我没理解你的指令，可以换个说法试试。"
                            needs_rerun = False

            # C. assistant 消息入库（仅在没有通过 execute_actions 添加时）
            if answer:
                chat.add_assistant(answer)

            # D. 刷新显示AI回复（总是需要刷新以显示新消息）
            st.rerun()


# ================= 主程序 =================
def main():
    st.set_page_config(layout="wide", page_title="Agent Pro", page_icon="📊")
    
    st.markdown("""
    <style>
    /* 锁死全局滚动 */
    body { overflow: hidden; }
    
    /* === 修改点：极致压缩顶部空白 === */
    .block-container {
        padding-top: 0.5rem !important; /* 原来是 2rem，改为 0.5rem */
        padding-bottom: 0rem !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
    }
    
    /* 隐藏 Header Footer */
    header {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* 调整分割线颜色 */
    hr { margin: 0.2rem 0 !important; border-color: #f1f5f9; }
    
    /* 滚动条细化 */
    ::-webkit-scrollbar { width: 5px; height: 5px; }
    ::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 3px; }
    
    [data-testid="stVerticalBlockBorderWrapper"] > div {
        box-shadow: none !important;
    }
    </style>
    """, unsafe_allow_html=True)

    init_session_state()
    render_sidebar()
    render_main_area()

if __name__ == "__main__":
    main()



