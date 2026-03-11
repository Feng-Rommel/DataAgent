# src/data_summarizer.py
from langchain_core.prompts import PromptTemplate
import json
import re

class DataSummarizer:
    def __init__(self, llm):
        self.llm = llm

        self.prompt_template = """
你是一个生物信息学数据状态追踪专家。
请阅读以下【执行日志】（包含 R 代码和对应的运行输出），生成一个**变量状态更新字典**。

【全局数据上下文】:
{global_context}

【执行日志】:
{execution_log}

【任务要求】：
1. **识别变量**：找出代码中**新建**或**被修改**的主要变量
2. **提取关键信息**：
   - **Seurat 对象**：
     * 记录对象类型（Seurat v3/v4/v5）
     * 提取细胞数和基因数（从输出中读取，如 "3000 cells and 20000 genes"）
     * 提取元数据列名（从 head(meta_data) 输出中获取）
     * 记录已完成的降维方法（PCA, UMAP, tSNE）
     * 记录聚类结果（分辨率、聚类数量）
   - **DataFrame/表格**：
     * 记录行数和列数
     * 记录列名（特别是关键列）
     * 记录数据内容类型（差异基因、marker基因、统计结果等）
   - **向量/列表**：
     * 记录长度
     * 记录元素类型（基因名、细胞ID等）
   - **绘图结果**：
     * 记录图表类型（散点图、小提琴图、热图等）
     * 记录分析目的（可视化、质控、结果展示）
3. **增量更新**：只记录本轮执行中发生变化的信息
4. **语义化描述**：用简洁的中文描述变量状态

【信息提取规则】：
1. **关键函数识别**：
   - `readRDS`, `CreateSeuratObject` → 新建数据对象
   - `NormalizeData`, `ScaleData`, `FindVariableFeatures` → 数据预处理步骤
   - `RunPCA`, `RunUMAP`, `RunTSNE` → 降维步骤
   - `FindNeighbors`, `FindClusters` → 聚类步骤
   - `FindMarkers`, `FindAllMarkers` → 差异分析
   - `DimPlot`, `VlnPlot`, `FeaturePlot` → 绘图
2. **输出解析**：
   - `print()` 或直接输出：查看对象信息
   - `head()`：查看前几行数据
   - `str()`：查看对象结构
   - `summary()`：统计摘要
3. **忽略内容**：
   - `library()` / `require()` - 库加载
   - 纯注释行
   - 简单的赋值（如 `x <- 1`）

【输出格式】：
请直接输出一个 JSON 对象 (字典)。Key 是变量名，Value 是该变量的状态描述。

示例 1 - 新建 Seurat 对象：
{{
  "sc_obj": {{
    "type": "Seurat",
    "desc": "单细胞数据对象，已完成质控",
    "cells": 3000,
    "genes": 20000,
    "meta_cols": ["nCount_RNA", "nFeature_RNA", "percent.mt", "sample"],
    "steps_completed": ["quality_control"],
    "dims": "3000x20000"
  }}
}}

示例 2 - PCA 降维：
{{
  "sc_obj": {{
    "type": "Seurat",
    "desc": "已完成 PCA 降维",
    "steps_completed": ["quality_control", "normalization", "pca"],
    "pcs": 30,
    "variance_explained": "前10个PC解释了85%方差"
  }}
}}

示例 3 - 聚类结果：
{{
  "sc_obj": {{
    "type": "Seurat",
    "desc": "已完成细胞聚类",
    "steps_completed": ["quality_control", "normalization", "pca", "clustering"],
    "cluster_resolution": 0.5,
    "n_clusters": 15
  }},
  "cluster_markers": {{
    "type": "DataFrame",
    "desc": "各cluster的marker基因表",
    "rows": 150
  }}
}}

示例 4 - 差异分析：
{{
  "markers_df": {{
    "type": "DataFrame",
    "desc": "cluster0 vs cluster1 的差异基因",
    "rows": 500,
    "up_regulated": 230,
    "down_regulated": 270
  }}
}}

【注意事项】：
1. 只输出本轮发生变化的变量
2. 如果变量已存在，只更新变化的部分
3. 使用具体的数值而不是模糊描述
4. 保留重要的元数据信息，便于后续代码生成使用
"""

    def generate_update_patch(self, execution_log_str, global_context=""):
        """
        生成变量状态更新补丁

        :param execution_log_str: 拼接好的代码和清洗后的输出字符串
        :param global_context: 全局数据上下文（已有的变量状态）
        :return: 更新补丁字典
        """
        if not execution_log_str.strip():
            return {}

        if not global_context:
            global_context = "当前无全局数据上下文。"

        prompt = PromptTemplate(
            input_variables=["execution_log", "global_context"],
            template=self.prompt_template
        )

        # 截断防止 Token 爆炸 (保留最后 4000 字符，通常包含关键的 head/str 信息)
        safe_log = execution_log_str
        if len(safe_log) > 4000:
            safe_log = "...(前略)...\n" + safe_log[-4000:]

        # 截断全局上下文 (保留最后 3000 字符)
        safe_context = global_context
        if len(safe_context) > 3000:
            safe_context = "...(前略)...\n" + safe_context[-3000:]

        response = self.llm.invoke(prompt.format(
            execution_log=safe_log,
            global_context=safe_context
        ))
        text = response.content if hasattr(response, 'content') else str(response)

        # 解析 JSON
        try:
            pattern = r"```json(.*?)```"
            match = re.search(pattern, text, re.DOTALL)
            json_str = match.group(1).strip() if match else text.strip()

            patch = json.loads(json_str)
            if isinstance(patch, dict):
                return patch
            return {}
        except:
            print(f"    [警告] 总结器 JSON 解析失败。")
            return {}
