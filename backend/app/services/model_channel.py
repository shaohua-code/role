"""模型测试台受控 Provider 出口（OpenAI 兼容 chat/completions，设计文档 §5）。

边界与诚实性约束：
- 凭据只从受控引用解析（secret://env/<变量名>），解析结果只在内存中随请求发送，
  绝不写日志、不进审计、不回传浏览器；vault:// 引用未接入时给出明确分类错误。
- 外呼仅服务端发起（受控出口），浏览器不直连 Provider；错误统一分类为稳定 code，
  不向调用方透传上游原始异常正文。
- 流式返回按 SSE data 行解析：reasoning_content → 可见思考（仅 thinking_output
  能力模型由调用方转发），content → 正文，usage → 真实用量。
"""

import json
import os
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

import httpx

from app.core.config import get_settings


class ChannelError(Exception):
    """通道错误：稳定 code + 面向操作者的安全提示；不携带上游原始正文。"""

    def __init__(self, code: str, message: str, *, http_status: int | None = None,
                 retry_after_seconds: int | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status
        self.retry_after_seconds = retry_after_seconds


@dataclass
class StreamChunk:
    """流式切片：reasoning=可见思考 / answer=正文 / usage=真实用量 / finish=结束原因。"""

    kind: str
    text: str = ""
    input_tokens: int | None = None
    output_tokens: int | None = None
    finish_reason: str | None = None
    raw: dict = field(default_factory=dict)


def resolve_credential(credential_ref: str | None) -> str:
    """解析受控凭据引用；仅支持 secret://env/<变量名>（环境变量由部署平台注入）。"""
    if not credential_ref:
        raise ChannelError("credential_unavailable", "模型未配置凭证引用，请先在模型目录配置凭证")
    if credential_ref.startswith("secret://env/"):
        var_name = credential_ref.removeprefix("secret://env/")
        value = os.environ.get(var_name, "")
        if not value:
            raise ChannelError(
                "credential_unavailable",
                f"凭据引用指向的环境变量 {var_name} 未注入或为空；请由部署平台注入后重试")
        return value
    if credential_ref.startswith("vault://"):
        raise ChannelError(
            "credential_unavailable",
            "暂未接入 vault 密钥管理器；请改用 secret://env/<变量名> 形式的凭据引用")
    raise ChannelError("credential_unavailable", "凭据引用格式不受支持；仅接受 secret://env/<变量名>")


# 无 endpoint_url 时按 Provider 的公开 API 默认值解析（均为 OpenAI 兼容端点，
# 与 stream_chat 的 SSE 协议匹配）；未列入的 Provider 必须显式配置端点。
_PROVIDER_DEFAULT_BASE_URLS = {
    "deepseek": "https://api.deepseek.com/v1",
    "openai": "https://api.openai.com/v1",
    # 月之暗面 Kimi（中国大陆站）
    "moonshot": "https://api.moonshot.cn/v1",
    # 阿里云百炼 DashScope 的 OpenAI 兼容模式（qwen 系列作为常用别名）
    "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "dashscope": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    # 智谱 GLM
    "zhipu": "https://open.bigmodel.cn/api/paas/v4",
    "glm": "https://open.bigmodel.cn/api/paas/v4",
    # Yasoll 聚合网关
    "yasoll": "https://api.yasoll.tech/v1",
    # OpenRouter / SiliconFlow 聚合网关
    "openrouter": "https://openrouter.ai/api/v1",
    "siliconflow": "https://api.siliconflow.cn/v1",
}


def resolve_base_url(endpoint_url: str | None, provider: str) -> str:
    """外呼基底地址：目录 endpoint_url 优先，其次 Provider 内置默认，否则明确报错。"""
    if endpoint_url and endpoint_url.strip():
        return endpoint_url.strip().rstrip("/")
    default = _PROVIDER_DEFAULT_BASE_URLS.get(provider.strip().lower())
    if default:
        return default
    raise ChannelError(
        "provider_config_invalid",
        f"Provider「{provider}」没有内置端点默认值，请在模型目录配置 endpoint_url")


def _timeout() -> httpx.Timeout:
    settings = get_settings()
    return httpx.Timeout(settings.model_test_read_timeout_seconds,
                         connect=settings.model_test_connect_timeout_seconds)


def _classify_request_error(error: httpx.HTTPError) -> ChannelError:
    """httpx 异常 → 稳定错误分类；超时区分连接阶段与读取阶段。"""
    if isinstance(error, httpx.ConnectTimeout):
        return ChannelError("connect_timeout", "Provider 连接超时（TLS/网络未在限定时间内建立）")
    if isinstance(error, httpx.ReadTimeout):
        return ChannelError("read_timeout", "Provider 响应超时（连接已建立但未在限定时间内返回）")
    if isinstance(error, httpx.TimeoutException):
        return ChannelError("connect_timeout", "Provider 连接超时")
    return ChannelError("network_error", "网络错误：无法连接到 Provider 端点")


def _raise_for_status(response: httpx.Response) -> None:
    """非 2xx → 分类错误；429 带可用的重试等待；不透传上游响应正文。"""
    if response.status_code < 400:
        return
    retry_after = None
    retry_header = response.headers.get("Retry-After")
    if retry_header and retry_header.isdigit():
        retry_after = int(retry_header)
    if response.status_code == 401:
        raise ChannelError("credential_rejected", "凭据被 Provider 拒绝（401），请检查凭据引用指向的密钥",
                           http_status=401)
    if response.status_code == 429:
        raise ChannelError("rate_limited", "Provider 限流（429），请稍后重试",
                           http_status=429, retry_after_seconds=retry_after)
    if response.status_code >= 500:
        raise ChannelError("upstream_error", f"Provider 上游故障（{response.status_code}）",
                           http_status=response.status_code, retry_after_seconds=retry_after)
    raise ChannelError("upstream_error", f"Provider 返回 {response.status_code}，请求未进入生成",
                       http_status=response.status_code)


async def probe_provider(base_url: str, api_key: str, *, transport: httpx.AsyncBaseTransport | None = None) -> list[dict]:
    """连接探针：网络/TLS 与 Provider 响应两阶段（凭据解析阶段由调用方先行完成）。

    使用 OpenAI 兼容 GET /models 作为固定短探针，不产生对话与计费 token。
    transport 仅供单测注入 MockTransport，生产恒为 None。
    """
    stages: list[dict] = []
    async with httpx.AsyncClient(timeout=_timeout(), transport=transport) as client:
        try:
            await client.get(f"{base_url}/models",
                             headers={"Authorization": f"Bearer {api_key}"})
        except httpx.HTTPError as error:
            raise _classify_request_error(error) from None
        stages.append({"name": "网络 / TLS", "ok": True})
    return stages


async def stream_chat(base_url: str, api_key: str, *, model_name: str, messages: list[dict],
                      temperature: float, top_p: float, max_tokens: int,
                      cancel_event=None, transport: httpx.AsyncBaseTransport | None = None) -> AsyncIterator[StreamChunk]:
    """流式对话外呼：逐片产出 reasoning/answer/usage/finish；cancel_event 置位时中断。

    max_tokens 由服务端上限收紧（设计文档 §4：输出上限由服务端强制）。
    transport 仅供单测注入 MockTransport，生产恒为 None。
    """
    payload = {
        "model": model_name,
        "messages": messages,
        "temperature": temperature,
        "top_p": top_p,
        "max_tokens": min(max_tokens, get_settings().model_test_max_output_tokens),
        "stream": True,
        # OpenAI 兼容扩展：流式返回真实用量（Provider 不支持时忽略，走估算兜底）。
        "stream_options": {"include_usage": True},
    }
    async with httpx.AsyncClient(timeout=_timeout(), transport=transport) as client:
        try:
            async with client.stream(
                "POST", f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
            ) as response:
                _raise_for_status(response)
                async for line in response.aiter_lines():
                    if cancel_event is not None and cancel_event.is_set():
                        return
                    line = line.strip()
                    if not line.startswith("data:"):
                        continue
                    data_text = line.removeprefix("data:").strip()
                    if data_text == "[DONE]":
                        return
                    try:
                        chunk = json.loads(data_text)
                    except ValueError:
                        continue
                    usage = chunk.get("usage")
                    if usage:
                        yield StreamChunk(
                            kind="usage",
                            input_tokens=usage.get("prompt_tokens"),
                            output_tokens=usage.get("completion_tokens"),
                            raw=usage,
                        )
                    choices = chunk.get("choices") or []
                    if not choices:
                        continue
                    delta = choices[0].get("delta") or {}
                    reasoning = delta.get("reasoning_content")
                    if reasoning:
                        yield StreamChunk(kind="reasoning", text=reasoning)
                    content = delta.get("content")
                    if content:
                        yield StreamChunk(kind="answer", text=content)
                    finish_reason = choices[0].get("finish_reason")
                    if finish_reason:
                        yield StreamChunk(kind="finish", finish_reason=finish_reason)
        except httpx.HTTPError as error:
            raise _classify_request_error(error) from None
