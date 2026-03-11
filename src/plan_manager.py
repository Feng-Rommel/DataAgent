# src/plan_manager.py
import json
from pathlib import Path

class PlanManager:
    """
    规划管理器 - 负责存储和管理任务规划
    支持：
    1. 保存规划到文件
    2. 追踪当前执行进度
    3. 获取下一个待执行任务
    4. 标记任务完成状态
    """
    
    def __init__(self, plan_file="current_plan.json"):
        self.plan_file = plan_file
        self.plan = None
        self.current_task_index = 0
        self.load_plan()
    
    def load_plan(self):
        """从文件加载现有规划"""
        if Path(self.plan_file).exists():
            try:
                with open(self.plan_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.plan = data.get('tasks', [])
                    self.current_task_index = data.get('current_index', 0)
                    return True
            except:
                pass
        return False
    
    def save_plan(self):
        """保存规划到文件"""
        if self.plan is None:
            return
        
        data = {
            'tasks': self.plan,
            'current_index': self.current_task_index,
            'total': len(self.plan)
        }
        
        with open(self.plan_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def create_plan(self, tasks):
        """
        创建新规划
        :param tasks: 任务列表，格式 [{"id": 1, "task": "..."}, ...]
        """
        self.plan = tasks
        self.current_task_index = 0
        
        # 为每个任务添加状态字段
        for task in self.plan:
            task['status'] = 'pending'  # pending, in_progress, completed
        
        self.save_plan()
        return len(self.plan)
    
    def has_active_plan(self):
        """检查是否有活跃的规划"""
        return self.plan is not None and len(self.plan) > 0
    
    def get_current_task(self):
        """获取当前待执行的任务"""
        if not self.has_active_plan():
            return None
        
        if self.current_task_index >= len(self.plan):
            return None  # 所有任务已完成
        
        return self.plan[self.current_task_index]
    
    def get_next_task(self):
        """获取下一个任务（不移动指针）"""
        if not self.has_active_plan():
            return None
        
        next_index = self.current_task_index + 1
        if next_index >= len(self.plan):
            return None
        
        return self.plan[next_index]
    
    def mark_current_completed(self):
        """标记当前任务为已完成，并移动到下一个"""
        if not self.has_active_plan():
            return False
        
        if self.current_task_index < len(self.plan):
            self.plan[self.current_task_index]['status'] = 'completed'
            self.current_task_index += 1
            self.save_plan()
            return True
        
        return False
    
    def get_progress(self):
        """获取进度信息"""
        if not self.has_active_plan():
            return None
        
        completed = sum(1 for task in self.plan if task['status'] == 'completed')
        total = len(self.plan)
        
        return {
            'completed': completed,
            'total': total,
            'current_index': self.current_task_index,
            'percentage': int((completed / total) * 100) if total > 0 else 0
        }
    
    def get_plan_summary(self):
        """获取规划摘要（用于显示）"""
        if not self.has_active_plan():
            return "当前无活跃规划。"
        
        lines = ["当前规划:"]
        for i, task in enumerate(self.plan):
            status_icon = "✓" if task['status'] == 'completed' else "→" if i == self.current_task_index else "○"
            lines.append(f"  {status_icon} {task['id']}. {task['task']}")
        
        progress = self.get_progress()
        lines.append(f"\n进度: {progress['completed']}/{progress['total']} ({progress['percentage']}%)")
        
        return "\n".join(lines)
    
    def clear_plan(self):
        """清除当前规划"""
        self.plan = None
        self.current_task_index = 0
        
        if Path(self.plan_file).exists():
            Path(self.plan_file).unlink()
    
    def is_plan_completed(self):
        """检查规划是否全部完成"""
        if not self.has_active_plan():
            return True
        
        return self.current_task_index >= len(self.plan)
