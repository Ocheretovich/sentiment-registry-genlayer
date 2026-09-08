# SentimentModerationRegistry — GenLayer Intelligent Contract

A consensus-validated feedback moderation registry: text goes in, and a
validated sentiment classification drives a configurable moderation
decision and a set of aggregate counters — the classification isn't just
stored, it determines what happens next.

```
submitted text
      -> independent comparative classification (validator consensus)
      -> validated sentiment
      -> configurable policy rule
      -> stored moderation decision
      -> aggregate counters
```

## Why it's built this way

This is the third iteration. Each earlier version fixed a specific problem:

1. **v1** used `gl.eq_principle.prompt_non_comparative` with criteria that
   only checked the leader's answer was one of three allowed words — it
   never verified the label actually matched the text. A leader could
   have returned "positive" for a negative review and every validator
   would have accepted it.
2. **v2** switched to `gl.eq_principle.prompt_comparative`: every
   validator independently re-runs the same classification prompt on the
   same submitted text, and agreement is only reached if their
   independently-derived label matches the leader's. This fixed the
   consensus issue, but the contract was still just "classify and store"
   — the sentiment label had no consequence beyond sitting in storage.
3. **v3 (this version)** adds a deploy-time-configurable policy that maps
   each validated sentiment to a moderation decision (default:
   `positive -> accepted`, `neutral -> review`, `negative -> flagged`),
   and aggregate counters that update on every submission. The validated
   result now drives real contract behavior instead of being a dead end.

   One tuning note from testing: the `principle` text passed to
   `prompt_comparative` needs to be short and unambiguous. An earlier
   phrasing ("not just any one of the three allowed words") used a
   double negative that made the automatic equivalence judge overly
   strict — validators would sometimes disagree with an obviously
   correct leader result. Rewording it to a direct positive statement
   ("must match the sentiment expressed in the submitted text") resolved
   the false disagreements in testing.

Other deliberate choices:

- **No silent fallback on bad output.** An earlier version coerced any
  unrecognized model response into `"neutral"`. That masks a failure
  instead of handling one — this version raises and reverts the
  transaction if consensus doesn't land on a known label.
- **No web fetch.** The input is passed directly by the caller, so
  there's no dependency on an external page being reachable or unchanged.
- **No custom validator_fn.** Consensus is handled entirely by
  `gl.eq_principle.prompt_comparative`, so there's no hand-written
  comparison logic that could be written incorrectly.

## Contract

Deployed on GenLayer Studionet: `0xeE34b8b3EB471ADa6686705F7fB17F050e554fF5`

Open directly in Studio: `https://studio.genlayer.com/?import-contract=0xeE34b8b3EB471ADa6686705F7fB17F050e554fF5`

### Constructor

```python
__init__(
    positive_decision: str = "accepted",
    neutral_decision: str = "review",
    negative_decision: str = "flagged",
)
```

Deployers choose what each sentiment means for their use case — this
default mapping suits a support-feedback triage queue, but any three
strings work.

### Methods

| Method | Type | Description |
|---|---|---|
| `submit_feedback(text)` | write | Classifies `text` via validator consensus, applies the policy, stores the entry, and updates counters. Returns the new entry's id. |
| `get_feedback(feedback_id)` | view | Returns `{text, sentiment, decision}` for a given entry. |
| `total_feedback()` | view | Returns the number of stored entries. |
| `get_policy()` | view | Returns the deploy-time sentiment -> decision mapping. |
| `get_stats()` | view | Returns `{total, positive_count, neutral_count, negative_count}`. |

### Source

See [`sentiment_moderation_registry.py`](./sentiment_moderation_registry.py).

## Testing

Deployed and tested in GenLayer Studio:
- Deploy -> `FINALIZED`
- `submit_feedback("Very satisfied with the service.")` -> sentiment `positive`, decision `accepted`
- `submit_feedback("Terrible service, I will never come back.")` -> sentiment `negative`, decision `flagged`
- `get_stats()` reflects both submissions correctly
