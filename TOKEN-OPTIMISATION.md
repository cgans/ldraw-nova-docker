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
4. *Planned, depending on the makeup:* load the builder guides on demand
   instead of in every system prompt; or stable system-prompt prefix (move the work listing and NOTES.md
   to the end) so consecutive turns share a cache.
5. *Planned:* resume the runtime session between turns instead of replaying
   the whole history as JSON. Only shows on runs that need repair rounds.

## Later (deprioritised)

- **Jev (TypeSafe semantic search) on vs off.** Without `TYPESAFE_API_KEY`
  the agent uses keyword search. Worth a measured comparison (steps, input
  per step, cost including Jev's charges, model quality) once the token
  work is done; rate limits are not a concern for a household. Pricing
  still to check.
- **Tell the agent when Jev is not configured**, so it skips the
  availability check at the start of every design.

