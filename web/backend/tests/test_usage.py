import usage


class FakeRun:
    def __init__(self):
        self.usage = usage.new_totals()
        self.events = []

    def emit(self, event, data):
        self.events.append((event, data))


def test_normalise_openai_anthropic_and_object_shapes():
    assert usage.normalise({"prompt_tokens": 1000, "completion_tokens": 50,
                            "prompt_tokens_details": {"cached_tokens": 800}}) == \
        {"input": 1000, "output": 50, "cache_read": 800, "cache_write": 0}
    # Anthropic counts cached and uncached input separately; input is the whole prompt.
    assert usage.normalise({"input_tokens": 120, "output_tokens": 40, "cache_read_input_tokens": 900,
                            "cache_creation_input_tokens": 100}) == \
        {"input": 1120, "output": 40, "cache_read": 900, "cache_write": 100}

    class Obj:
        prompt_tokens = 10
        completion_tokens = 2
        prompt_tokens_details = None
        cache_read_input_tokens = None
        cache_creation_input_tokens = None
    assert usage.normalise(Obj()) == {"input": 10, "output": 2, "cache_read": 0, "cache_write": 0}


def test_record_accumulates_streams_and_summarises():
    run = FakeRun()
    usage.record(run, {"prompt_tokens": 20000, "completion_tokens": 300}, model="m", cost=0.1)
    usage.record(run, {"prompt_tokens": 21000, "completion_tokens": 100, "prompt_tokens_details": {"cached_tokens": 19000}},
                 model="m", cost=0.02)
    assert run.usage["input"] == 41000 and run.usage["cache_read"] == 19000 and run.usage["steps"] == 2
    assert run.usage["cost_usd"] == 0.12
    assert run.events[-1][0] == "usage" and run.events[-1][1]["total"]["steps"] == 2
    assert usage.summary(run.usage) == "Tokens this turn: 41k in (19k cached), 400 out, 2 step(s), ~$0.12"
    plain = FakeRun()
    usage.record(plain, {"input_tokens": 500, "output_tokens": 20}, model="m", steps=7)
    assert usage.summary(plain.usage) == "Tokens this turn: 500 in, 20 out, 7 step(s)"


def test_makeup_and_per_step_curve():
    run = FakeRun()
    usage.add_makeup(run, "system_prompt", "s" * 76000)
    usage.add_makeup(run, "tool_calls", "c" * 40000)
    usage.add_makeup(run, "tool_results", "r" * 8000)
    usage.add_makeup(run, "narration", None)
    for n in (20000, 45000, 90000):
        usage.step_input(run, {"prompt_tokens": n})
    text = usage.makeup_summary(run.usage)
    assert text.startswith("Context added this turn (approx. tokens): system prompt 19k, earlier turns 0, "
                           "agent's tool calls 10k, tool results 2k, narration 0, thinking 0, 0 image(s) ~0k")
    assert text.endswith("Prompt per step: first 20k, middle 45k, last 90k (3 requests)")
    run.usage["output"] = 70000
    assert "(mostly thinking): 60k" in usage.makeup_summary(run.usage)


def test_image_tokens_from_png_header():
    def png(w, h):
        return b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + w.to_bytes(4, "big") + h.to_bytes(4, "big") + b"\x08\x06\x00\x00\x00"
    assert usage.image_tokens(png(1024, 768)) == 1024 * 768 // 750
    big = usage.image_tokens(png(3136, 1568))  # scaled to 1568 x 784
    assert big == int(1568 * 784 / 750)
    assert usage.image_tokens(b"not a png") == 0
    run = FakeRun()
    usage.add_images(run, [png(1024, 768), png(1024, 768)])
    assert run.usage["makeup"]["images"] == 2 and run.usage["makeup"]["image_tokens"] == 2 * (1024 * 768 // 750)
