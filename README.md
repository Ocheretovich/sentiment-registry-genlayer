# SentimentRegistry — GenLayer Intelligent Contract

A minimal Intelligent Contract that classifies the sentiment of user-submitted
text (positive / negative / neutral) using an LLM, with validator consensus
handled entirely by GenLayer's built-in `gl.eq_principle.prompt_non_comparative`
helper.

## Why it's built this way

Most Intelligent Contract examples reach consensus with a hand-written
`leader_fn` / `validator_fn` pair. This contract avoids that, using
GenLayer's built-in equivalence helpers instead — with one important
correction from an earlier version:

- **Validators independently classify the text, not just check its format.**
  An earlier version used `gl.eq_principle.prompt_non_comparative` with
  criteria that only verified the leader's answer was one of three allowed
  words ("positive", "negative", "neutral") — it never checked that the
  chosen word actually matched what the text said. A leader could have
  returned "positive" for a clearly negative review and every validator
  would have accepted it, since nothing tied the label to the input.
  This version uses `gl.eq_principle.prompt_comparative` instead: each
  validator re-runs the same classification prompt on the same submitted
  text themselves, and an NLP judge only accepts the result if their
  independently-derived label matches the leader's. Agreement now requires
  genuinely classifying the same text the same way.
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
