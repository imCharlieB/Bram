import base64
import json

import httpx
import pytest

from bram.models import Image, Message, ModelError, OllamaProvider, Tool


def provider(handler, model="m:1"):
    return OllamaProvider("http://model", model, transport=httpx.MockTransport(handler))


def answering(body, status=200):
    return provider(lambda request: httpx.Response(status, json=body))


async def test_request_and_reply():
    sent = {}

    def handler(request):
        sent.update(json.loads(request.content))
        return httpx.Response(200, json={
            "message": {"content": "", "tool_calls": [
                {"function": {"name": "t", "arguments": {"x": 1}}}]},
            "eval_count": 10, "eval_duration": 2_000_000_000, "done_reason": "stop"})

    reply = await provider(handler).chat(
        [Message("user", "hi", images=(Image(b"abc"),))],
        [Tool("t", "d", {"type": "object"})], {"type": "object"})
    assert sent["messages"][0]["images"] == [base64.b64encode(b"abc").decode()]
    assert sent["tools"][0]["function"]["name"] == "t"
    assert sent["format"] == {"type": "object"} and sent["stream"] is False
    assert reply.tool_calls[0].arguments == {"x": 1}
    assert reply.output_seconds == 2 and not reply.truncated


@pytest.mark.parametrize("call", [
    {}, {"function": {"name": "t"}}, {"function": {"name": "", "arguments": {}}},
    {"function": {"name": "t", "arguments": "{\"x\": 1}"}}, "bad"])
async def test_malformed_tool_call_is_refused(call):
    with pytest.raises(ModelError):
        await answering({"message": {"content": "", "tool_calls": [call]}}).chat([])


async def test_errors_become_model_errors():
    def down(request):
        raise httpx.ConnectError("no")

    for p in (provider(down), answering({"error": "x"}, 500), answering({}), answering([])):
        with pytest.raises(ModelError):
            await p.chat([Message("user", "hi")])


async def test_redirect_is_not_followed():
    hosts = []

    def handler(request):
        hosts.append(request.url.host)
        return httpx.Response(307, headers={"location": "http://elsewhere/"})

    with pytest.raises(ModelError):
        await provider(handler).chat([Message("user", "private")])
    assert hosts == ["model"]


async def test_identity_changes_with_digest():
    one = await answering({"models": [{"name": "m:1", "digest": "a"}]}).identity()
    two = await answering({"models": [{"name": "m:1", "digest": "b"}]}).identity()
    assert one != two
    with pytest.raises(ModelError):
        await answering({"models": []}).identity()


async def test_truncated():
    reply = await answering({"message": {"content": "x"}, "done_reason": "length"}).chat([])
    assert reply.truncated
