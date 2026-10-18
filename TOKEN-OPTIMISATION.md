# Token optimisation: measurements

Work on the `token-optimisation` branch. Each change is measured on the same
brief, through brickpipe's design-and-repair loop, with Claude signed in
through the browser (the Claude agent runtime path).

Brief: *A small red tractor, about 60 pieces, with big black rear wheels, a
yellow seat and a grey exhaust pipe. Ordinary bricks, plates and slopes only.*

Per-step input is the steadier comparison: the number of steps varies a lot
between runs of the same brief.

| Run | Change | Turns | Steps | Input | Cached | Output | Input / step | Cost (runtime's figure) |
|---|---|---|---|---|---|---|---|---|
| A | usage recording only | 1 (clean first time) | 40 | 2,386k | 95% | 58k | ~60k | ~$2.58 |
| B | + command output capped at 6000 chars | 1 (clean first time) | 49 | 3,028k | 96% | 61k | ~62k | ~$2.85 |
| C | + context makeup recorded | 1 (clean first time) | 48 | 3,571k | 96% | 70k | ~74k | ~$3.16 |

**C's makeup:** prompt per request 29k first, 88k middle, 137k last (39
requests). Nova-visible additions: system prompt 19k, the agent's tool calls
8k, tool results 14k, narration 1k. The other ~85k of growth is not visible
to Nova: the model's thinking (70k output against ~9k visible output), which
stays in context for the whole single-turn design, and the renders viewed.
The cap in B never fired (no `tool-output` files): tool results are small.
Lever: the runtime's `effort` (brickpipe sent none, so the default "high").

| D | effort **medium** (design turn) | 1 | 54 | 3,521k | 96% | 58k | ~65k | ~$2.91 |
| D | repair turn (one round needed) | 1 | 8 | 618k | 83% | 3.4k | ~103k | ~$1.06 |

**D, design turn:** additions Nova can see: tool calls 8k, tool results 18k,
narration 1k, 11 images ~12k. Thinking text returned is a summary (310), but
output not seen as calls or narration was 49k, against ~61k in C: medium
effort cut thinking by about a fifth, and cost by ~8%. A weak lever on this
model; not worth a quality risk on its own.

**D, repair turn:** the clearest waste so far. A 3.4k-token fix cost $1.06:
every request started at ~99-107k tokens because the whole design
conversation is replayed as one JSON message (earlier turns ~32k by Nova's
count, more once JSON-escaped and with images), and that replay is new to
the cache each turn (105k uncached). Every brickpipe repair round pays this,
and it grows each round.

### Compaction A/B (same repair request, same model, same chat)

brickpipe re-checked run D's round-1 model and sent the same repair request
to the same chat twice, with `LDRAW_NOVA_COMPACT_TURNS=0` and then with
compaction on. The second run had one more earlier turn to carry, so the
comparison is, if anything, against compaction. In both runs the agent
found the fix already in place and confirmed it.

| Repair turn | Earlier turns sent | First request | Input | Cached | Output | Steps | Cost |
|---|---|---|---|---|---|---|---|
| Full replay (`=0`) | ~36k | 106k | 539k | 80% | 1.8k | 6 | ~$1.04 |
| Compacted | ~1k | **32k** | **169k** | 80% | 1.4k | 5 | **~$0.32** |

About 70% less input and cost for a follow-up turn; better than predicted
(~40k, ~$0.40). Still to confirm: a repair that needs new work, to check
the agent loses nothing it needs from the compacted history.

**B did not reduce input per step** (predicted 35-45k). Back-of-envelope: the
system prompt is ~19k tokens and the agent's own writing (generator code sent
as tool arguments, narration; 58-61k tokens per turn) stays in context, about
30k on an average step. That leaves ~10k for tool results, so capping them
could not move the total much. The cap is kept as a guard against outlier
dumps but claims no saving. The instrument now reports where the context
comes from (below) so the next change is chosen from data.

## Changes

1. **Record usage** (`web/backend/usage.py`). Reads the usage every provider
   already returns; streams a `usage` event; ends each turn with a "Tokens
   this turn" notice. No change to what the model sees.
2. **Compact command output** (`tools.compact_output`). Shell, Python and
   toolkit results over `LDRAW_NOVA_TOOL_RESULT_CHARS` (default 6000)
   characters keep their start and end; the full text goes to
   `output/tool-output/` with a pointer the agent can `read_file`. That
   folder is left out of the work listing in the system prompt so the
   listing does not churn. Set the variable to `0` to turn this off for an
   A/B comparison without rebuilding.
3. **Context makeup** (`usage.add_makeup`, `usage.step_input`). The turn's
   notice also reports characters added by origin (system prompt, replayed
   earlier turns, the agent's tool calls, tool results, narration) and the
   prompt size of the first, middle and last request.
4. **Compact follow-up turns** (`agent.compact_history`, Claude runtime
   path). A follow-up turn no longer replays the earlier turns' tool calls
   and outputs: it gets the brief, one note with the earlier follow-up
   requests (first 400 characters each) and the agent's last answer, then
   the new message. The system prompt already carries NOTES.md and the work
   listing. `LDRAW_NOVA_COMPACT_TURNS=0` restores the full replay for A/B.
   Prediction: a repair turn's first request ~99k -> ~40k, cost ~$1.06 ->
   ~$0.40. Measured by repairing the same model from the same chat twice,
   once with the variable at 0 and once at 1.
5. *Later, depending on the makeup:* load the builder guides on demand
   instead of in every system prompt; or stable system-prompt prefix (move the work listing and NOTES.md
   to the end) so consecutive turns share a cache.
6. *Alternative to 4:* resume the runtime session between turns instead of replaying
   the whole history as JSON. Only shows on runs that need repair rounds.

## Later (deprioritised)

- **Jev (TypeSafe semantic search) on vs off.** Without `TYPESAFE_API_KEY`
  the agent uses keyword search. Worth a measured comparison (steps, input
  per step, cost including Jev's charges, model quality) once the token
  work is done; rate limits are not a concern for a household. Pricing
  still to check.
- **Tell the agent when Jev is not configured**, so it skips the
  availability check at the start of every design.

