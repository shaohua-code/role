"""模型测试台多轮上下文契约：仅完整轮次进入 Provider 请求。"""

import asyncio
import time
import unittest
from unittest.mock import patch
from uuid import uuid4

from pydantic import ValidationError

from app.api.v1.admin.model_tests import (
    TestConversationCreate, _Conversation, _ModelSnapshot,
    _execute_conversation, _provider_messages,
)
from app.services.model_channel import StreamChunk


class ModelTestHistoryTests(unittest.TestCase):
    def _body(self, history: list[dict], **extra) -> TestConversationCreate:
        return TestConversationCreate.model_validate({
            "application_id": str(uuid4()),
            "message": "接着解释",
            "history": history,
            **extra,
        })

    def test_complete_turns_preserve_order_and_system_instruction(self) -> None:
        history = [
            {"role": "user", "content": "第一问"},
            {"role": "assistant", "content": "第一答"},
            {"role": "user", "content": "第二问"},
            {"role": "assistant", "content": "第二答"},
        ]
        body = self._body(history)
        self.assertEqual(_provider_messages(
            body.message, [turn.model_dump() for turn in body.history],
            {"system_prompt": "简洁回答"}), [
                {"role": "system", "content": "简洁回答"},
                *history,
                {"role": "user", "content": "接着解释"},
            ])

    def test_rejects_incomplete_or_out_of_order_history(self) -> None:
        invalid = [
            [{"role": "user", "content": "孤立问题"}],
            [{"role": "assistant", "content": "先回答"}, {"role": "user", "content": "后提问"}],
            [{"role": "user", "content": "问题"}, {"role": "assistant", "content": "   "}],
        ]
        for history in invalid:
            with self.subTest(history=history), self.assertRaises(ValidationError):
                self._body(history)

    def test_rejects_oversized_history_and_unsupported_parameters(self) -> None:
        history = [{"role": "user", "content": "x" * 16000},
                   {"role": "assistant", "content": "y" * 16000},
                   {"role": "user", "content": "z"},
                   {"role": "assistant", "content": "a"}]
        with self.assertRaises(ValidationError):
            self._body(history)
        with self.assertRaises(ValidationError):
            self._body([], params={"thinking": True})
        with self.assertRaises(ValidationError):
            self._body([], user_id=str(uuid4()))


class ModelTestForwardingTests(unittest.IsolatedAsyncioTestCase):
    async def test_completed_history_reaches_provider_in_order(self) -> None:
        captured: list[dict] = []

        async def fake_stream(_base_url, _api_key, **kwargs):
            captured.extend(kwargs["messages"])
            yield StreamChunk(kind="answer", text="第二答")
            yield StreamChunk(kind="usage", input_tokens=12, output_tokens=4)
            yield StreamChunk(kind="finish", finish_reason="stop")

        model_id = uuid4()
        conversation = _Conversation(
            conversation_id="test", request_id="request", model_id=model_id,
            application_id=uuid4(), tenant_id=uuid4(), operator_id=uuid4(),
            created_at=time.monotonic(), cancel_event=asyncio.Event(),
        )
        snapshot = _ModelSnapshot(
            id=model_id, key="demo", model_name="demo", provider="test",
            credential_ref="secret://env/TEST", endpoint_url="https://example.test/v1",
        )
        history = [{"role": "user", "content": "第一问"},
                   {"role": "assistant", "content": "第一答"}]
        with (patch("app.api.v1.admin.model_tests.resolve_credential", return_value="test-key"),
              patch("app.api.v1.admin.model_tests.resolve_base_url", return_value="https://example.test/v1"),
              patch("app.api.v1.admin.model_tests.stream_chat", side_effect=fake_stream),
              patch("app.api.v1.admin.model_tests._record_usage_sync")):
            await _execute_conversation(
                conversation, snapshot, "第二问", history,
                {"system_prompt": "简洁回答", "max_tokens": 64}, time.monotonic(),
            )
        self.assertEqual(captured, [
            {"role": "system", "content": "简洁回答"},
            *history,
            {"role": "user", "content": "第二问"},
        ])
        self.assertEqual(conversation.events[-1]["type"], "done")


if __name__ == "__main__":
    unittest.main()
