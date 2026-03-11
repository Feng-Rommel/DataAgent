"""
模型测试脚本 - 测试不同 LLM 的连接和响应
"""

import sys
import os
from src.llm_factory import LLMFactory, LLMConfig, create_default_llm


def test_llm(config: LLMConfig, test_prompt: str = "你好，请用一句话自我介绍。"):
    """
    测试 LLM 连接和响应

    Args:
        config: LLM 配置
        test_prompt: 测试提示词

    Returns:
        bool: 是否测试成功
    """
    print(f"\n{'='*60}")
    print(f"测试模型: {config.llm_type} - {config.model}")
    print(f"{'='*60}")

    try:
        # 创建 LLM
        print(f"[*] 创建 LLM 实例...")
        llm = LLMFactory.create_llm(config)

        # 发送测试请求
        print(f"[*] 发送测试请求...")
        response = llm.invoke(test_prompt)

        # 显示响应
        result = response.content if hasattr(response, 'content') else str(response)
        print(f"\n[✓] 测试成功！\n")
        print(f"模型响应:\n{result}\n")

        return True

    except Exception as e:
        print(f"\n[✗] 测试失败: {e}\n")
        return False


def test_from_file(filepath: str):
    """
    从配置文件测试

    Args:
        filepath: 配置文件路径
    """
    if not os.path.exists(filepath):
        print(f"✗ 配置文件不存在: {filepath}")
        return

    config = LLMFactory.load_from_file(filepath)
    if config:
        test_llm(config)


def interactive_test():
    """交互式测试"""
    print("\n" + "=" * 60)
    print("LLM 交互式测试工具")
    print("=" * 60)

    while True:
        print("\n请选择操作:")
        print("1. 测试默认配置")
        print("2. 测试 Ollama")
        print("3. 测试 OpenAI")
        print("4. 测试通义千问")
        print("5. 测试智谱 AI")
        print("6. 从配置文件测试")
        print("7. 自定义测试")
        print("0. 退出")

        choice = input("\n请输入选项 (0-7): ").strip()

        if choice == "0":
            print("退出测试")
            break

        elif choice == "1":
            print("\n[测试默认配置]")
            llm = create_default_llm()
            test_llm(llm)

        elif choice == "2":
            print("\n[测试 Ollama]")
            config = LLMFactory.get_default_config("ollama")
            test_llm(config)

        elif choice == "3":
            print("\n[测试 OpenAI]")
            base_url = input("Base URL (默认 https://api.openai.com/v1): ").strip() or "https://api.openai.com/v1"
            api_key = input("API Key: ").strip()
            model = input("模型 (默认 gpt-4): ").strip() or "gpt-4"

            config = LLMConfig(
                llm_type="openai",
                model=model,
                base_url=base_url,
                api_key=api_key
            )
            test_llm(config)

        elif choice == "4":
            print("\n[测试通义千问]")
            api_key = input("API Key: ").strip()
            model = input("模型 (默认 qwen-max): ").strip() or "qwen-max"

            config = LLMConfig(
                llm_type="qianwen",
                model=model,
                api_key=api_key
            )
            test_llm(config)

        elif choice == "5":
            print("\n[测试智谱 AI]")
            api_key = input("API Key: ").strip()
            model = input("模型 (默认 glm-4): ").strip() or "glm-4"

            config = LLMConfig(
                llm_type="zhipu",
                model=model,
                api_key=api_key
            )
            test_llm(config)

        elif choice == "6":
            filepath = input("\n配置文件路径: ").strip()
            test_from_file(filepath)

        elif choice == "7":
            print("\n[自定义测试]")
            llm_type = input("LLM 类型 (ollama/openai/qianwen/zhipu/custom): ").strip().lower()
            model = input("模型名称: ").strip()
            base_url = input("Base URL (可选): ").strip() or None
            api_key = input("API Key (可选): ").strip() or None
            test_prompt = input("测试提示词 (可选，回车使用默认): ").strip() or None

            config = LLMConfig(
                llm_type=llm_type,
                model=model,
                base_url=base_url,
                api_key=api_key
            )
            test_llm(config, test_prompt or "你好，请用一句话自我介绍。")

        else:
            print("✗ 无效选项")


def main():
    """主函数"""
    if len(sys.argv) > 1:
        # 命令行模式
        arg = sys.argv[1]

        if arg == "default":
            llm = create_default_llm()
            test_llm(llm)

        elif arg == "ollama":
            config = LLMFactory.get_default_config("ollama")
            test_llm(config)

        elif arg == "openai":
            config = LLMFactory.get_default_config("openai")
            test_llm(config)

        elif arg == "qwen":
            config = LLMFactory.get_default_config("qianwen")
            test_llm(config)

        elif arg == "zhipu":
            config = LLMFactory.get_default_config("zhipu")
            test_llm(config)

        elif os.path.exists(arg):
            # 文件模式
            test_from_file(arg)

        else:
            print(f"✗ 未知参数: {arg}")
            print("用法: python test_llm.py [default|ollama|openai|qwen|zhipu|配置文件路径]")

    else:
        # 交互式模式
        interactive_test()


if __name__ == "__main__":
    main()
