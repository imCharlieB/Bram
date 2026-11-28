"""Cloud models: only when the owner chooses one (E1), pictures only with their own switch (E2)."""
import json

import httpx
import pytest

from bram import local_model
from bram.local_model import cloud, open_brain, pictures_allowed
from bram.models.base import Image, Message, ModelError
from bram.models.cloud import Anthropic, OpenAICompatible, provider
from bram.settings import Settings

JPEG = b"\xff\xd8 picture"


def recorder(answer):
    seen = []

    def handle(request):
        seen.append(request)
        return httpx.Response(200, json=answer(request))
    return seen, httpx.MockTransport(handle)


async def test_openai_compatible():
    seen, transport = recorder(lambda r: {"data": [{"id": "models/gpt-x"}]} if r.url.path.endswith(
        "/models") else {"choices": [{"message": {"content": "Hello."}, "finish_reason": "stop"}]})
    model = OpenAICompatible("https://api.example/v1", "sk-1", "gpt-x", transport=transport)
    assert await model.models() == ["gpt-x"]
    reply = await model.chat([Message("system", "Rules"),
                              Message("user", "What is this?", images=(Image(JPEG),))],
                             schema={"type": "object"})
    await model.close()
    assert reply.text == "Hello."
    asked = seen[-1]
    assert str(asked.url) == "https://api.example/v1/chat/completions"
    assert asked.headers["Authorization"] == "Bearer sk-1"
    body = json.loads(asked.content)
    assert body["messages"][1]["content"][1]["image_url"]["url"].startswith(
        "data:image/jpeg;base64,")
    assert body["response_format"]["type"] == "json_schema"


async def test_anthropic():
    seen, transport = recorder(lambda r: {"content": [{"type": "text", "text": "Hi."}],
                                          "stop_reason": "end_turn"})
    model = Anthropic("ak-1", "claude-x", transport=transport)
    reply = await model.chat([Message("system", "Rules"), Message("user", "Hello")])
    await model.close()
    assert reply.text == "Hi."
    asked = seen[-1]
    assert asked.headers["x-api-key"] == "ak-1" and asked.headers["anthropic-version"]
    body = json.loads(asked.content)
    assert body["system"] == "Rules" and [m["role"] for m in body["messages"]] == ["user"]


async def test_a_refused_key_is_said_plainly():
    transport = httpx.MockTransport(lambda r: httpx.Response(401, json={}))
    model = provider({"provider": "openai", "key": "bad", "model": "m"}, transport=transport)
    with pytest.raises(ModelError, match="did not accept the API key"):
        await model.chat([Message("user", "hi")])
    await model.close()


@pytest.mark.rule("E1")
async def test_nothing_goes_to_the_cloud_unless_chosen(monkeypatch):
    settings = Settings(":memory:")
    used = []

    async def local(*args, **kw):
        used.append("local")
        raise ModelError("your own model is down")

    monkeypatch.setattr(local_model, "open_model", local)
    # A key alone is not a choice; a provider without a key is not either.
    settings.update_channel("cloud", {"key": "sk-1", "provider": ""})
    assert cloud(settings) == {}
    with pytest.raises(ModelError, match="your own model is down"):
        await open_brain(settings, "http://127.0.0.1:11434", "m", 8192)
    assert used == ["local"]  # and no fallback to the cloud when it fails
    settings.update_channel("cloud", {"provider": "openai", "key": "sk-1", "model": "gpt-x"})
    chosen = await open_brain(settings, "", "gpt-x", 8192)
    assert isinstance(chosen, OpenAICompatible) and used == ["local"]
    await chosen.close()
    settings.close()


@pytest.mark.rule("E2")
def test_camera_pictures_need_their_own_switch():
    settings = Settings(":memory:")
    assert pictures_allowed(settings)  # your own model: Describe decides, per camera
    settings.update_channel("cloud", {"provider": "gemini", "key": "k", "model": "m"})
    assert not pictures_allowed(settings)
    settings.update_channel("cloud", {"images": True})
    assert pictures_allowed(settings)
    settings.close()
