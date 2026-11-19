"""模型测试台受控通道客户端回归（httpx MockTransport，不发真实请求）。

覆盖 docs/模型测试台设计.md §4/§5 的通道侧错误分类与流解析：
- 凭据引用解析：secret://env 命中/缺失、vault:// 未接入、格式不支持；
- 端点解析：endpoint_url 优先、Provider 内置默认、未知 Provider 明确报错；
- 状态码分类：401→credential_rejected、429→rate_limited（含 Retry-After）、
  5xx→upstream_error；连接超时→connect_timeout；
- SSE 解析：reasoning_content/content/usage/finish 顺序与内容；
- 取消：cancel_event 预置置位时不产出任何切片（服务端强制停止）。
"""

import asyncio
import unittest
from uuid import uuid4

import httpx

from app.services.model_channel import (
    ChannelError,
    probe_provider,
    resolve_base_url,
    resolve_credential,
    stream_chat,
)


def _sse_response(lines: list[str]) -> httpx.Response:
    """构造 OpenAI 兼容流式响应（MockTransport 用）。"""
    body = "".join(f"data: {line}\n\n" for line in lines) + "data: [DONE]\n\n"
    return httpx.Response(200, content=body.encode("utf-8"),
                          headers={"Content-Type": "text/event-stream"})


class CredentialResolutionTests(unittest.TestCase):
    """凭据引用解析：环境变量注入制，密钥不落库不进日志。"""

    def test_secret_env_reference_resolves(self) -> None:
        import os

        var = f"IAM_TEST_KEY_{uuid4().hex[:8]}"
        os.environ[var] = "sk-test-value"
        try:
            self.assertEqual(resolve_credential(f"secret://env/{var}"), "sk-test-value")
        finally:
            os.environ.pop(var, None)

    def test_missing_env_variable_is_classified(self) -> None:
        with self.assertRaises(ChannelError) as denied:
            resolve_credential(f"secret://env/IAM_MISSING_{uuid4().hex[:8]}")
        self.assertEqual(denied.exception.code, "credential_unavailable")

    def test_vault_reference_not_integrated_yet(self) -> None:
        with self.assertRaises(ChannelError) as denied:
            resolve_credential("vault://production/deepseek-key")
        self.assertEqual(denied.exception.code, "credential_unavailable")

    def test_none_reference_reports_unconfigured(self) -> None:
        with self.assertRaises(ChannelError) as denied:
            resolve_credential(None)
        self.assertEqual(denied.exception.code, "credential_unavailable")


class BaseUrlResolutionTests(unittest.TestCase):
    """端点解析：目录配置优先，deepseek/openai 有内置默认，其余要求显式配置。"""

    def test_endpoint_url_wins(self) -> None:
        self.assertEqual(resolve_base_url("https://gw.example.com/v1/", "custom"),
                         "https://gw.example.com/v1")

    def test_provider_defaults(self) -> None:
        self.assertEqual(resolve_base_url(None, "DeepSeek"), "https://api.deepseek.com/v1")
        self.assertEqual(resolve_base_url(None, "openai"), "https://api.openai.com/v1")

    def test_unknown_provider_requires_endpoint(self) -> None:
        with self.assertRaises(ChannelError) as denied:
            resolve_base_url(None, "internal-llm")
        self.assertEqual(denied.exception.code, "provider_config_invalid")


class StreamChatTests(unittest.IsolatedAsyncioTestCase):
    """SSE 流解析与错误分类（MockTransport 注入，不联网）。"""

    async def test_parses_reasoning_answer_usage_finish(self) -> None:
        lines = [
            '{"choices":[{"delta":{"reasoning_content":"先分析问题"}}]}',
            '{"choices":[{"delta":{"content":"答案第一段"}}]}',
            '{"choices":[{"delta":{"content":"答案第二段"}}]}',
            '{"choices":[{"delta":{},"finish_reason":"stop"}]}',
            '{"choices":[],"usage":{"prompt_tokens":12,"completion_tokens":34}}',
        ]
        transport = httpx.MockTransport(lambda request: _sse_response(lines))
        chunks = [chunk async for chunk in stream_chat(
            "https://api.example.com/v1", "sk-x", model_name="demo",
            messages=[{"role": "user", "content": "hi"}],
            temperature=0.7, top_p=0.9, max_tokens=2048, transport=transport)]
        kinds = [chunk.kind for chunk in chunks]
        self.assertEqual(kinds, ["reasoning", "answer", "answer", "finish", "usage"])
        self.assertEqual(chunks[0].text, "先分析问题")
        self.assertEqual("".join(c.text for c in chunks if c.kind == "answer"), "答案第一段答案第二段")
        usage = chunks[-1]
        self.assertEqual((usage.input_tokens, usage.output_tokens), (12, 34))

    async def test_401_maps_to_credential_rejected(self) -> None:
        transport = httpx.MockTransport(lambda request: httpx.Response(401, text='{"error":"bad key"}'))
        with self.assertRaises(ChannelError) as denied:
            async for _ in stream_chat(
                "https://api.example.com/v1", "sk-bad", model_name="demo",
                messages=[{"role": "user", "content": "hi"}],
                temperature=0.7, top_p=0.9, max_tokens=64, transport=transport):
                pass
        self.assertEqual(denied.exception.code, "credential_rejected")
        self.assertEqual(denied.exception.http_status, 401)

    async def test_429_maps_to_rate_limited_with_retry_after(self) -> None:
        transport = httpx.MockTransport(lambda request: httpx.Response(
            429, text="rate limited", headers={"Retry-After": "12"}))
        with self.assertRaises(ChannelError) as denied:
            async for _ in stream_chat(
                "https://api.example.com/v1", "sk-x", model_name="demo",
                messages=[{"role": "user", "content": "hi"}],
                temperature=0.7, top_p=0.9, max_tokens=64, transport=transport):
                pass
        self.assertEqual(denied.exception.code, "rate_limited")
        self.assertEqual(denied.exception.retry_after_seconds, 12)

    async def test_5xx_maps_to_upstream_error(self) -> None:
        transport = httpx.MockTransport(lambda request: httpx.Response(502, text="bad gateway"))
        with self.assertRaises(ChannelError) as denied:
            async for _ in stream_chat(
                "https://api.example.com/v1", "sk-x", model_name="demo",
                messages=[{"role": "user", "content": "hi"}],
                temperature=0.7, top_p=0.9, max_tokens=64, transport=transport):
                pass
        self.assertEqual(denied.exception.code, "upstream_error")
        self.assertEqual(denied.exception.http_status, 502)

    async def test_connect_timeout_maps_to_connect_timeout(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectTimeout("timed out", request=request)

        transport = httpx.MockTransport(handler)
        with self.assertRaises(ChannelError) as denied:
            async for _ in stream_chat(
                "https://api.example.com/v1", "sk-x", model_name="demo",
                messages=[{"role": "user", "content": "hi"}],
                temperature=0.7, top_p=0.9, max_tokens=64, transport=transport):
                pass
        self.assertEqual(denied.exception.code, "connect_timeout")

    async def test_cancel_event_stops_streaming_immediately(self) -> None:
        lines = ['{"choices":[{"delta":{"content":"不应出现的正文"}}]}']
        transport = httpx.MockTransport(lambda request: _sse_response(lines))
        cancel = asyncio.Event()
        cancel.set()
        chunks = [chunk async for chunk in stream_chat(
            "https://api.example.com/v1", "sk-x", model_name="demo",
            messages=[{"role": "user", "content": "hi"}],
            temperature=0.7, top_p=0.9, max_tokens=64,
            cancel_event=cancel, transport=transport)]
        self.assertEqual(chunks, [])


class ProbeProviderTests(unittest.IsolatedAsyncioTestCase):
    """连接探针：/models 可达即通过；异常按稳定分类抛出。"""

    async def test_reachable_models_endpoint_passes(self) -> None:
        transport = httpx.MockTransport(lambda request: httpx.Response(
            200, json={"data": []}))
        stages = await probe_provider("https://api.example.com/v1", "sk-x", transport=transport)
        self.assertEqual(stages, [{"name": "网络 / TLS", "ok": True}])

    async def test_unreachable_maps_to_network_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("refused", request=request)

        transport = httpx.MockTransport(handler)
        with self.assertRaises(ChannelError) as denied:
            await probe_provider("https://api.example.com/v1", "sk-x", transport=transport)
        self.assertEqual(denied.exception.code, "network_error")


if __name__ == "__main__":
    unittest.main()
