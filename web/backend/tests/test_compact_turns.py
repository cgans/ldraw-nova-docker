import json

import agent


def turn(request, steps, answer):
    out = [{"role": "user", "content": request, "_turn_start": True}]
    for n in range(steps):
        out.append({"role": "assistant", "content": None,
                    "tool_calls": [{"id": f"c{request[:3]}{n}", "type": "function",
                                    "function": {"name": "run_shell", "arguments": json.dumps({"command": "x" * 500})}}]})
        out.append({"role": "tool", "tool_call_id": f"c{request[:3]}{n}", "content": "y" * 5000})
    out.append({"role": "assistant", "content": answer})
    return out


def test_first_turn_is_untouched():
    history = turn("Build a tractor", 3, "Done: tractor-v1.mpd")
    assert agent.compact_history(history) == history


def test_follow_up_keeps_brief_last_answer_requests_and_current_turn():
    history = (turn("Build a tractor", 30, "Done: tractor-v1.mpd")
               + turn("Repair round 1: fix colour 1234", 6, "Fixed: tractor-v2.mpd")
               + [{"role": "user", "content": "Repair round 2: attach the seat", "_turn_start": True}])
    compact = agent.compact_history(history)
    assert [m["role"] for m in compact] == ["user", "assistant", "user"]
    assert compact[0]["content"] == "Build a tractor"
    assert compact[-1]["content"] == "Repair round 2: attach the seat"
    note = compact[1]["content"]
    assert "Repair round 1: fix colour 1234" in note
    assert "My last answer before this request:\nFixed: tractor-v2.mpd" in note
    assert "NOTES.md" in note
    assert not any(m.get("tool_calls") or m["role"] == "tool" for m in compact)
    assert len(json.dumps(compact)) < len(json.dumps(history)) / 50


def test_long_earlier_requests_are_shortened():
    history = (turn("Build", 1, "ok") + turn("R" * 5000, 1, "ok2")
               + [{"role": "user", "content": "now", "_turn_start": True}])
    note = agent.compact_history(history)[1]["content"]
    assert "R" * agent.EARLIER_REQUEST_CHARS in note and "R" * (agent.EARLIER_REQUEST_CHARS + 1) not in note
