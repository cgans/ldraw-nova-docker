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
