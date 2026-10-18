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
3. *Planned:* stable system-prompt prefix (move the work listing and NOTES.md
   to the end) so consecutive turns share a cache.
4. *Planned:* resume the runtime session between turns instead of replaying
   the whole history as JSON. Only shows on runs that need repair rounds.
