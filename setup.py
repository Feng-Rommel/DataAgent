"""
快速设置脚本 - 安装依赖并创建示例配置
"""

import os
import json
import subprocess

def install_dependencies():
    """安装必要的依赖"""
    print("=" * 60)
    print("正在安装依赖包...")
    print("=" * 60)

    try:
        # 安装基础依赖
        print("\n[1/2] 安装基础依赖...")
        subprocess.run([
            "pip", "install",
            "-r", "requirements_ui.txt"
        ], check=True, capture_output=True, text=True)
        print("✓ 基础依赖安装完成")

        # 安装完整依赖（包含 OpenAI）
        print("\n[2/2] 安装 OpenAI 支持...")
        subprocess.run([
            "pip", "install",
            "langchain-openai>=0.0.5"
        ], check=True, capture_output=True, text=True)
        print("✓ OpenAI 支持安装完成")

        print("\n" + "=" * 60)
        print("✓ 所有依赖安装完成！")
        print("=" * 60)

    except subprocess.CalledProcessError as e:
        print(f"\n✗ 安装失败: {e}")
        print(f"错误输出: {e.stderr}")
        return False

    return True

def create_sample_configs():
    """创建示例配置文件"""
    print("\n" + "=" * 60)
    print("创建示例配置文件...")
    print("=" * 60)

    # Ollama 配置
    ollama_config = {
        "llm_type": "ollama",
        "model": "qwen3-coder:30b",
        "base_url": "http://localhost:11434",
        "temperature": 0.7
    }

    # OpenAI 配置
    openai_config = {
        "llm_type": "openai",
        "model": "gpt-4",
        "base_url": "https://api.openai.com/v1",
        "api_key": "your-api-key-here",
        "temperature": 0.7,
        "max_tokens": 4096
    }

    # 通义千问配置
    qwen_config = {
        "llm_type": "qianwen",
        "model": "qwen-max",
        "api_key": "your-dashscope-key-here",
        "temperature": 0.7,
        "max_tokens": 4096
    }

    # 智谱 AI 配置
    zhipu_config = {
        "llm_type": "zhipu",
        "model": "glm-4",
        "api_key": "your-zhipu-key-here",
        "temperature": 0.7,
        "max_tokens": 4096
    }

    configs = {
        "llm_config.json": ollama_config,
        "llm_config_ollama.json": ollama_config,
        "llm_config_openai.json": openai_config,
        "llm_config_qwen.json": qwen_config,
        "llm_config_zhipu.json": zhipu_config
    }

    for filename, config in configs.items():
        filepath = os.path.join(os.path.dirname(__file__), filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        print(f"✓ 创建: {filename}")

    print("\n" + "=" * 60)
    print("✓ 示例配置文件创建完成！")
    print("=" * 60)

def print_usage_guide():
    """打印使用指南"""
    print("\n" + "=" * 60)
    print("使用指南")
    print("=" * 60)

    print("\n1. 选择一个配置文件：")
    print("   - llm_config_ollama.json  → 使用本地 Ollama（推荐，免费）")
    print("   - llm_config_openai.json   → 使用 OpenAI API")
    print("   - llm_config_qwen.json     → 使用通义千问")
    print("   - llm_config_zhipu.json    → 使用智谱 AI")

    print("\n2. 复制并修改配置：")
    print("   cp llm_config_openai.json llm_config.json")
    print("   # 编辑 llm_config.json，填入你的 API Key")

    print("\n3. 启动程序：")
    print("   python main.py        # 命令行版本")
    print("   streamlit run ui_app.py  # Web UI 版本")

    print("\n4. 在 Web UI 中切换模型（可选）：")
    print("   - 打开侧边栏")
    print("   - 找到'大模型配置'")
    print("   - 选择模型类型并配置")
    print("   - 点击'💾 保存配置'")

    print("\n" + "=" * 60)
    print("详细文档请查看: LLM_GUIDE.md")
    print("=" * 60 + "\n")

def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("数据分析 Agent - 快速设置")
    print("=" * 60)

    # 安装依赖
    if not install_dependencies():
        print("\n✗ 依赖安装失败，请检查错误信息")
        return

    # 创建示例配置
    create_sample_configs()

    # 打印使用指南
    print_usage_guide()

    # 测试导入
    print("正在测试导入...")
    try:
        from src.llm_factory import LLMFactory, LLMConfig
        print("✓ LLM 工厂导入成功")
        print(f"✓ 支持的模型类型: {list(LLMFactory.SUPPORTED_TYPES.keys())}")
    except ImportError as e:
        print(f"⚠ 导入警告: {e}")
        print("  （这可能是正常的，某些可选依赖可能未安装）")

    print("\n" + "=" * 60)
    print("✓ 设置完成！")
    print("=" * 60 + "\n")

if __name__ == "__main__":
    main()
