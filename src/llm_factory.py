"""
LLM 工厂模块 - 支持多种大模型接口

支持的模型类型：
1. Ollama（本地）
2. OpenAI API
3. Azure OpenAI
4. 通义千问（阿里云）
5. 智谱 AI（GLM）
6. 百度文心（ERNIE）
7. 其他兼容 OpenAI 接口的 API
"""

import os
from typing import Optional, Dict, Any
from langchain_community.llms import Ollama
from langchain_openai import ChatOpenAI
from langchain_community.chat_models import QianfanChatEndpoint, ChatTongyi


class LLMConfig:
    """LLM 配置类"""
    def __init__(
        self,
        llm_type: str = "ollama",
        model: str = "qwen3-coder:30b",
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ):
        """
        LLM 配置

        Args:
            llm_type: LLM 类型 (ollama, openai, azure, qianwen, zhipu, wenxin, etc.)
            model: 模型名称
            base_url: API base URL（可选）
            api_key: API 密钥（可选）
            temperature: 温度参数
            max_tokens: 最大生成长度
            **kwargs: 其他模型特定参数
        """
        self.llm_type = llm_type.lower()
        self.model = model
        self.base_url = base_url
        self.api_key = api_key
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.kwargs = kwargs

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "llm_type": self.llm_type,
            "model": self.model,
            "base_url": self.base_url,
            "api_key": self.api_key,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens
        }


class LLMFactory:
    """LLM 工厂类 - 根据配置创建 LLM 实例"""

    # 支持的 LLM 类型
    SUPPORTED_TYPES = {
        "ollama": "Ollama（本地）",
        "openai": "OpenAI API",
        "azure": "Azure OpenAI",
        "qianwen": "通义千问（阿里云）",
        "zhipu": "智谱 AI（GLM）",
        "wenxin": "百度文心（ERNIE）",
        "custom": "自定义 OpenAI 兼容接口"
    }

    # 默认模型配置
    DEFAULT_MODELS = {
        "ollama": "qwen3-coder:30b",
        "openai": "gpt-4",
        "azure": "gpt-4",
        "qianwen": "qwen-max",
        "zhipu": "glm-4",
        "wenxin": "ERNIE-Bot-4",
        "custom": "gpt-4"
    }

    # 默认 base URL
    DEFAULT_BASE_URLS = {
        "ollama": "http://localhost:11434",
        "openai": "https://api.openai.com/v1",
        "azure": None,  # 需要单独设置
        "qianwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "zhipu": "https://open.bigmodel.cn/api/paas/v4",
        "wenxin": "https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat",
        "custom": None
    }

    @staticmethod
    def create_llm(config: LLMConfig):
        """
        根据 LLM 配置创建 LLM 实例

        Args:
            config: LLM 配置对象

        Returns:
            LLM 实例

        Raises:
            ValueError: 不支持的 LLM 类型
        """
        llm_type = config.llm_type
        model = config.model
        base_url = config.base_url
        api_key = config.api_key
        temperature = config.temperature
        max_tokens = config.max_tokens
        kwargs = config.kwargs

        print(f">>> [LLM 工厂] 创建 {llm_type} LLM，模型: {model}")

        # 1. Ollama（本地）
        if llm_type == "ollama":
            llm = Ollama(
                model=model,
                base_url=base_url,
                temperature=temperature,
                **kwargs
            )

        # 2. OpenAI API
        elif llm_type == "openai":
            llm = ChatOpenAI(
                model=model,
                base_url=base_url,
                api_key=api_key,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )

        # 3. Azure OpenAI
        elif llm_type == "azure":
            # Azure 需要特殊参数
            llm = ChatOpenAI(
                model=model,
                api_key=api_key,
                temperature=temperature,
                max_tokens=max_tokens,
                deployment_name=kwargs.get("deployment_name", model),
                azure_endpoint=base_url,
                **{k: v for k, v in kwargs.items() if k != "deployment_name"}
            )

        # 4. 通义千问（阿里云）
        elif llm_type == "qianwen":
            llm = ChatTongyi(
                model=model,
                api_key=api_key,
                temperature=temperature,
                max_tokens=max_tokens,
                dashscope_api_key=api_key,
                **kwargs
            )

        # 5. 智谱 AI（GLM）
        elif llm_type == "zhipu":
            llm = QianfanChatEndpoint(
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )

        # 6. 百度文心
        elif llm_type == "wenxin":
            # 百度文心需要特殊处理
            raise NotImplementedError("百度文心 API 正在开发中，请使用其他 API")

        # 7. 自定义 OpenAI 兼容接口
        elif llm_type == "custom":
            llm = ChatOpenAI(
                model=model,
                base_url=base_url,
                api_key=api_key,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )

        else:
            raise ValueError(f"不支持的 LLM 类型: {llm_type}，支持的类型: {list(LLMFactory.SUPPORTED_TYPES.keys())}")

        print(f">>> [LLM 工厂] LLM 创建成功")
        return llm

    @staticmethod
    def create_from_dict(config_dict: Dict[str, Any]):
        """
        从字典创建 LLM

        Args:
            config_dict: 配置字典

        Returns:
            LLM 实例
        """
        config = LLMConfig(**config_dict)
        return LLMFactory.create_llm(config)

    @staticmethod
    def get_default_config(llm_type: str = "ollama") -> LLMConfig:
        """
        获取默认配置

        Args:
            llm_type: LLM 类型

        Returns:
            LLMConfig 对象
        """
        model = LLMFactory.DEFAULT_MODELS.get(llm_type, "gpt-4")
        base_url = LLMFactory.DEFAULT_BASE_URLS.get(llm_type)

        return LLMConfig(
            llm_type=llm_type,
            model=model,
            base_url=base_url
        )

    @staticmethod
    def load_from_env(llm_type: Optional[str] = None) -> LLMConfig:
        """
        从环境变量加载配置

        支持的环境变量：
        - LLM_TYPE: LLM 类型
        - LLM_MODEL: 模型名称
        - LLM_BASE_URL: API base URL
        - LLM_API_KEY: API 密钥

        Args:
            llm_type: LLM 类型（如果不提供，从环境变量读取）

        Returns:
            LLMConfig 对象
        """
        config_type = llm_type or os.getenv("LLM_TYPE", "ollama")
        model = os.getenv("LLM_MODEL", LLMFactory.DEFAULT_MODELS.get(config_type))
        base_url = os.getenv("LLM_BASE_URL", LLMFactory.DEFAULT_BASE_URLS.get(config_type))
        api_key = os.getenv("LLM_API_KEY", None)

        return LLMConfig(
            llm_type=config_type,
            model=model,
            base_url=base_url,
            api_key=api_key
        )

    @staticmethod
    def save_to_file(config: LLMConfig, filepath: str = "llm_config.json"):
        """
        保存配置到文件

        Args:
            config: LLM 配置对象
            filepath: 配置文件路径
        """
        import json
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(config.to_dict(), f, indent=2, ensure_ascii=False)
        print(f">>> [LLM 工厂] 配置已保存到 {filepath}")

    @staticmethod
    def load_from_file(filepath: str = "llm_config.json") -> Optional[LLMConfig]:
        """
        从文件加载配置

        Args:
            filepath: 配置文件路径

        Returns:
            LLMConfig 对象，如果文件不存在返回 None
        """
        import json
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                config_dict = json.load(f)
            print(f">>> [LLM 工厂] 配置已从 {filepath} 加载")
            return LLMConfig(**config_dict)
        except FileNotFoundError:
            print(f">>> [LLM 工厂] 配置文件 {filepath} 不存在")
            return None
        except Exception as e:
            print(f">> [LLM 工厂] 加载配置文件失败: {e}")
            return None


def create_default_llm():
    """
    创建默认 LLM（便捷函数）

    优先级：
    1. 从配置文件加载（llm_config.json）
    2. 从环境变量加载
    3. 使用默认的 Ollama 配置

    Returns:
        LLM 实例
    """
    # 1. 尝试从配置文件加载
    config = LLMFactory.load_from_file()
    if config:
        return LLMFactory.create_llm(config)

    # 2. 尝试从环境变量加载
    try:
        config = LLMFactory.load_from_env()
        return LLMFactory.create_llm(config)
    except Exception as e:
        print(f">>> [LLM 工厂] 从环境变量加载失败: {e}")

    # 3. 使用默认配置
    print(">> [LLM 工厂] 使用默认 Ollama 配置")
    config = LLMFactory.get_default_config("ollama")
    return LLMFactory.create_llm(config)


# 便捷导出
__all__ = [
    'LLMConfig',
    'LLMFactory',
    'create_default_llm'
]
