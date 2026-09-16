import asyncio
import json
from types import SimpleNamespace

import pytest
from content_os.editor import Editor, LLMTruncatedError


class Response:
    status = 200
    async def __aenter__(self): return self
    async def __aexit__(self, *args): pass
    async def text(self): return "partial"
    async def json(self): return {"choices":[{"finish_reason":"length","message":{"content":"partial json"}}]}


def test_remix_has_own_budget_and_detects_truncation(monkeypatch):
    payloads=[]
    class Client:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self,*args): pass
        def post(self,url,**kwargs): payloads.append(kwargs["json"]); return Response()
    monkeypatch.setattr("content_os.editor.aiohttp.ClientSession",Client)
    editor=Editor(SimpleNamespace(llm_key="test",llm_model="test",llm_url="http://test"),None)
    with pytest.raises(LLMTruncatedError) as exc:
        asyncio.run(editor.remix_llm("system","prompt"))
    assert exc.value.partial == "partial json"
    assert payloads[0]["max_tokens"] == 3600
    assert asyncio.run(editor.llm("system","prompt")) == "partial json"
    assert payloads[1]["max_tokens"] == 1600
