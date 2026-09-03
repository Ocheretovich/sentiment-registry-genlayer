# SentimentRegistry — GenLayer Intelligent Contract

A minimal Intelligent Contract that classifies the sentiment of user-submitted
text (positive / negative / neutral) using an LLM, with validator consensus
handled entirely by GenLayer's built-in `gl.eq_principle.prompt_non_comparative`
helper.

## Why it's built this way

Most Intelligent Contract examples reach consensus with a hand-written
`leader_fn` / `validator_fn` pair. This contract deliberately avoids that:

- **No custom validator logic** — `prompt_non_comparative` handles the
  leader/validator agreement internally, so there's no comparison code that
  could be written incorrectly.
- **No web fetch** — the input is passed directly by the caller, so there's
  no dependency on an external page being reachable or unchanged.
- **No multi-stage state machine** — each submission is classified once and
  stored. There's nothing that can get stuck in an intermediate state.
- **Defensive normalization** — the LLM's raw response is stripped,
  lowercased, and validated against the three known labels before being
  stored, so an unexpected model output can never be saved as an invalid
  sentiment value.

The trade-off: a submission's sentiment can't be re-checked or disputed
later. That's a deliberate simplification, not an oversight.

## Contract

Deployed on GenLayer Studionet: `0x0aF7c1BaCC0F9403e0070C6E48192304e87bF80f`

Open directly in Studio: https://studio.genlayer.com/?import-contract=0x0aF7c1BaCC0F9403e0070C6E48192304e87bF80f

### Methods

| Method | Type | Description |
|---|---|---|
| `submit_feedback(text)` | write | Classifies the sentiment of `text` via an LLM and stores it. Returns the new entry's id. |
| `get_feedback(feedback_id)` | view | Returns `{text, sentiment}` for a given entry. |
| `total_feedback()` | view | Returns the number of stored entries. |

### Source

See [`sentiment_registry.py`](./sentiment_registry.py).

## Testing

Deployed and tested in GenLayer Studio:
- Deploy → `FINALIZED`
- `submit_feedback("Very satisfied with the service.")` → `FINALIZED`
- `get_feedback(0)` → `{"text": "Very satisfied with the service.", "sentiment": "positive"}`
