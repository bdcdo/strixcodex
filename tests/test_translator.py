"""Tests for the chat-completions <-> responses translator."""
from __future__ import annotations

import json

import pytest

from strixcodex.translator import (
    chat_to_responses,
    responses_to_chat,
    stream_responses_to_chat,
)


def test_simple_user_prompt():
    out = chat_to_responses(
        {
            "model": "gpt-5.4",
            "messages": [{"role": "user", "content": "hello"}],
        }
    )
    assert out["model"] == "gpt-5.4"
    assert out["store"] is False
    assert out["instructions"] == "You are a helpful assistant."
    assert out["input"] == [
        {"role": "user", "content": [{"type": "input_text", "text": "hello"}]}
    ]


def test_system_message_becomes_instructions():
    out = chat_to_responses(
        {
            "model": "gpt-5.4",
            "messages": [
                {"role": "system", "content": "you are a pirate"},
                {"role": "user", "content": "hi"},
            ],
        }
    )
    assert out["instructions"] == "you are a pirate"
    assert len(out["input"]) == 1
    assert out["input"][0]["role"] == "user"


def test_multiple_system_messages_concatenate():
    out = chat_to_responses(
        {
            "model": "gpt-5.4",
            "messages": [
                {"role": "system", "content": "rule one"},
                {"role": "system", "content": "rule two"},
                {"role": "user", "content": "hi"},
            ],
        }
    )
    assert out["instructions"] == "rule one\n\nrule two"


def test_assistant_with_tool_calls():
    out = chat_to_responses(
        {
            "model": "gpt-5.4",
            "messages": [
                {"role": "user", "content": "list files"},
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_abc",
                            "type": "function",
                            "function": {
                                "name": "list_files",
                                "arguments": '{"path":"/tmp"}',
                            },
                        }
                    ],
                },
                {
                    "role": "tool",
                    "tool_call_id": "call_abc",
                    "content": "a.txt\nb.txt",
                },
                {"role": "user", "content": "thanks"},
            ],
        }
    )
    inp = out["input"]
    # user, function_call, function_call_output, user
    assert len(inp) == 4
    assert inp[0]["role"] == "user"
    assert inp[1] == {
        "type": "function_call",
        "call_id": "call_abc",
        "name": "list_files",
        "arguments": '{"path":"/tmp"}',
    }
    assert inp[2] == {
        "type": "function_call_output",
        "call_id": "call_abc",
        "output": "a.txt\nb.txt",
    }
    assert inp[3]["role"] == "user"


def test_tool_definition_translation():
    out = chat_to_responses(
        {
            "model": "gpt-5.4",
            "messages": [{"role": "user", "content": "x"}],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "add",
                        "description": "add two numbers",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "a": {"type": "number"},
                                "b": {"type": "number"},
                            },
                            "required": ["a", "b"],
                        },
                    },
                }
            ],
        }
    )
    assert out["tools"] == [
        {
            "type": "function",
            "name": "add",
            "description": "add two numbers",
            "parameters": {
                "type": "object",
                "properties": {
                    "a": {"type": "number"},
                    "b": {"type": "number"},
                },
                "required": ["a", "b"],
            },
            "strict": False,
        }
    ]


def test_image_user_message():
    out = chat_to_responses(
        {
            "model": "gpt-5.4",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "what is this?"},
                        {
                            "type": "image_url",
                            "image_url": {"url": "https://example.com/x.png"},
                        },
                    ],
                }
            ],
        }
    )
    blocks = out["input"][0]["content"]
    assert blocks[0] == {"type": "input_text", "text": "what is this?"}
    assert blocks[1]["type"] == "input_image"
    assert blocks[1]["image_url"] == "https://example.com/x.png"


def test_max_tokens_renamed():
    out = chat_to_responses(
        {
            "model": "gpt-5.4",
            "messages": [{"role": "user", "content": "x"}],
            "max_tokens": 256,
        }
    )
    assert out["max_output_tokens"] == 256
    assert "max_tokens" not in out


def test_reasoning_effort_passthrough():
    out = chat_to_responses(
        {
            "model": "gpt-5.4",
            "messages": [{"role": "user", "content": "x"}],
            "reasoning_effort": "high",
        }
    )
    assert out["reasoning"] == {"effort": "high"}


def test_response_format_json_schema():
    out = chat_to_responses(
        {
            "model": "gpt-5.4",
            "messages": [{"role": "user", "content": "x"}],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "result",
                    "schema": {"type": "object", "properties": {"ok": {"type": "boolean"}}},
                },
            },
        }
    )
    assert out["text"]["format"]["type"] == "json_schema"
    assert out["text"]["format"]["name"] == "result"
    assert out["text"]["format"]["schema"]["properties"] == {"ok": {"type": "boolean"}}


def test_responses_to_chat_text_only():
    upstream = {
        "id": "resp_123",
        "output": [
            {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": "hi there"}],
            }
        ],
        "usage": {"input_tokens": 5, "output_tokens": 3, "total_tokens": 8},
    }
    chat = responses_to_chat(upstream, model="gpt-5.4")
    assert chat["choices"][0]["message"]["content"] == "hi there"
    assert chat["choices"][0]["finish_reason"] == "stop"
    assert chat["usage"] == {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8}
    assert chat["model"] == "gpt-5.4"


def test_responses_to_chat_with_tool_call():
    upstream = {
        "output": [
            {
                "type": "function_call",
                "call_id": "call_1",
                "name": "search",
                "arguments": '{"q":"foo"}',
            }
        ],
        "usage": {"input_tokens": 1, "output_tokens": 2},
    }
    chat = responses_to_chat(upstream, model="gpt-5.4")
    msg = chat["choices"][0]["message"]
    assert msg["content"] is None
    assert msg["tool_calls"][0] == {
        "id": "call_1",
        "type": "function",
        "function": {"name": "search", "arguments": '{"q":"foo"}'},
    }
    assert chat["choices"][0]["finish_reason"] == "tool_calls"


async def _to_list(aiter):
    out = []
    async for x in aiter:
        out.append(x)
    return out


async def _async_iter(items):
    for it in items:
        yield it


@pytest.mark.asyncio
async def test_stream_text_chunks():
    events = [
        {"type": "response.output_text.delta", "delta": "Hel"},
        {"type": "response.output_text.delta", "delta": "lo"},
        {
            "type": "response.completed",
            "response": {"usage": {"input_tokens": 2, "output_tokens": 2}},
        },
    ]
    chunks = await _to_list(stream_responses_to_chat(_async_iter(events), model="gpt-5.4"))
    decoded = b"".join(chunks).decode()
    assert "Hel" in decoded
    assert "lo" in decoded
    assert decoded.endswith("data: [DONE]\n\n")
    # role chunk goes first
    first_payload = json.loads(decoded.split("\n\n")[0][len("data: ") :])
    assert first_payload["choices"][0]["delta"]["role"] == "assistant"


@pytest.mark.asyncio
async def test_stream_tool_call_assembly():
    events = [
        {
            "type": "response.output_item.added",
            "item": {
                "type": "function_call",
                "id": "item_1",
                "call_id": "call_xyz",
                "name": "search",
            },
        },
        {
            "type": "response.function_call_arguments.delta",
            "item_id": "item_1",
            "delta": '{"q":',
        },
        {
            "type": "response.function_call_arguments.delta",
            "item_id": "item_1",
            "delta": '"foo"}',
        },
        {
            "type": "response.completed",
            "response": {"usage": {"input_tokens": 1, "output_tokens": 5}},
        },
    ]
    chunks = await _to_list(stream_responses_to_chat(_async_iter(events), model="gpt-5.4"))
    decoded = b"".join(chunks).decode()
    # collect all delta payloads
    payloads = []
    for line in decoded.split("\n\n"):
        line = line.strip()
        if line.startswith("data: ") and line[6:] != "[DONE]":
            payloads.append(json.loads(line[6:]))
    # find the final chunk with finish_reason
    finishes = [p for p in payloads if p["choices"][0]["finish_reason"] == "tool_calls"]
    assert finishes, "expected tool_calls finish"
    # arguments deltas should appear
    arg_chunks = [
        p
        for p in payloads
        if p["choices"][0]["delta"].get("tool_calls")
        and p["choices"][0]["delta"]["tool_calls"][0].get("function", {}).get("arguments")
    ]
    joined = "".join(
        p["choices"][0]["delta"]["tool_calls"][0]["function"]["arguments"]
        for p in arg_chunks
    )
    assert joined == '{"q":"foo"}'
