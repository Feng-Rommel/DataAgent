# 测试知识库检索功能
import sys
from langchain_community.llms import Ollama
from src.knowledge_retriever import KnowledgeRetriever

# 初始化 LLM
print("正在初始化 LLM...")
llm = Ollama(model="qwen3-coder:30b", base_url='http://localhost:11434')

# 初始化知识库检索器
print("正在初始化知识库检索器...")
retriever = KnowledgeRetriever(llm, knowledge_base_path="./知识库测试")

# 显示知识库摘要
print("\n" + "="*50)
print(retriever.get_knowledge_summary())
print("="*50)

# 测试查询
test_queries = [
    "单细胞数据预处理怎么做？",
    "如何进行细胞聚类？",
    "什么是拟时序分析？",
    "单细胞分析中的质量控制阈值设置",
    "细胞类型注释的方法"
]

print("\n开始测试知识库检索功能...")
print("="*50)

for i, query in enumerate(test_queries, 1):
    print(f"\n【测试 {i}】: {query}")
    print("-"*50)
    
    result = retriever.retrieve(query)
    
    if result:
        print("检索结果:")
        print(result)
    else:
        print("未检索到相关知识")
    
    print("-"*50)

print("\n测试完成！")
