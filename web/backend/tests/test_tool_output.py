import asyncio

import agent
import tools
from store import ChatStore
from tools import ToolContext


def make_ctx(data_dir):
    import settings
    store = ChatStore(settings.CHATS_DIR, settings.OUTPUT_DIR)
    chat = store.create_chat()
    return ToolContext(chat["id"], store, lambda *a: None), store, chat


def test_short_output_is_untouched(data_dir):
    ctx, _, _ = make_ctx(data_dir)
    assert tools.compact_output(ctx, "ok", 6000) == "ok"
    assert tools.compact_output(ctx, "x" * 50_000, 0) == "x" * 50_000  # cap off


def test_long_output_keeps_head_and_tail_and_saves_the_rest(data_dir):
    ctx, store, chat = make_ctx(data_dir)
    text = "HEAD" + "".join(f"line {i}\n" for i in range(5000)) + "TAIL"
    out = tools.compact_output(ctx, text, 6000)
    assert len(out) < 6600
    assert out.startswith("HEAD") and out.endswith("TAIL")
    assert "characters omitted to save context" in out
    name = out.split("output/tool-output/")[1].split(";")[0]
    saved = ctx.work_dir / "tool-output" / name
    assert saved.read_text() == text
    # the agent can page through it with the file tool it already has
    resumed = asyncio.run(tools.t_read_file(ctx, f"output/tool-output/{name}", max_chars=1000, offset=2000))
    assert resumed.content.startswith(text[2000:2100])
    # and it does not show up in the work-folder listing in the system prompt
    assert "tool-output" not in agent.work_listing(store.work_dir(chat["id"]))


def test_shell_tool_output_is_compacted(data_dir, monkeypatch):
    ctx, _, _ = make_ctx(data_dir)
    monkeypatch.setattr(tools, "TOOL_RESULT_CHARS", 3000)

    class Result:
        def as_text(self):
            return "[exit code 0, 0.1s]\n--- stdout ---\n" + "z" * 20_000

    async def fake_run(ctx, argv, timeout):
        return Result()
    monkeypatch.setattr(tools, "run_command", fake_run)
    result = asyncio.run(tools.t_run_shell(ctx, "yes z | head -c 20000"))
    assert len(result.content) < 3400
    assert result.content.startswith("[exit code 0")
