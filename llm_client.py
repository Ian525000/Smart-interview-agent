"""LLM 客户端，兼容 OpenAI API。"""

from typing import Dict, List, Optional

from openai import OpenAI

from config import API_KEY, BASE_URL, LLM_TIMEOUT, MODEL_ID


class HelloAgentsLLM:
    """
    OpenAI 兼容 LLM 客户端，支持流式与非流式调用。
    """

    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: Optional[int] = None,
    ):
        """
        @param model - 模型 ID
        @param api_key - API 密钥
        @param base_url - 服务地址
        @param timeout - 请求超时（秒）
        """
        self.model = model or MODEL_ID
        api_key = api_key or API_KEY
        base_url = base_url or BASE_URL
        timeout = timeout if timeout is not None else LLM_TIMEOUT

        if not all([self.model, api_key, base_url]):
            raise ValueError("模型 ID、API 密钥和服务地址必须在 .env 中配置。")

        self.client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)

    def think(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0,
        stream: bool = False,
    ) -> Optional[str]:
        """
        调用大语言模型并返回完整文本。

        @param messages - OpenAI 格式消息列表
        @param temperature - 采样温度
        @param stream - 是否流式输出到控制台
        @returns 模型响应文本
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                stream=stream,
            )

            if not stream:
                return response.choices[0].message.content or ""

            collected: List[str] = []
            for chunk in response:
                if not chunk.choices:
                    continue
                content = chunk.choices[0].delta.content or ""
                print(content, end="", flush=True)
                collected.append(content)
            print()
            return "".join(collected)
        except Exception as exc:
            print(f"[ERROR] LLM 调用失败: {exc}")
            return None
