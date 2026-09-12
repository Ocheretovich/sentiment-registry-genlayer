# SentimentModerationRegistry — GenLayer Intelligent Contract

A consensus-validated feedback moderation registry with a real
review/challenge lifecycle: a classification isn't just stored, it drives
a configurable decision, and that decision can be independently
re-checked and overturned through explicit lifecycle transitions.

```
submitted text
      -> independent comparative classification (validator consensus)
      -> validated sentiment
      -> configurable policy rule
      -> stored decision, status = "provisional"

anyone can challenge_case(id):
      -> the same text is re-classified from scratch, independently,
         through consensus
      -> agrees with current sentiment -> confirmations += 1
                                           status -> "confirmed" at 2
      -> disagrees                     -> sentiment & decision replaced
                                           status -> "disputed"
```

## Why it's built this way

This is the fourth iteration. Each earlier version fixed a specific,
concrete problem — this history is left in the code's docstring as well:

1. **v1** used `gl.eq_principle.prompt_non_comparative` with criteria that
   only checked the leader's answer was one of three allowed words — it
   never verified the label actually matched the text. A leader could
   have returned "positive" for a negative review and every validator
   would have accepted it.
2. **v2** switched to `gl.eq_principle.prompt_comparative`: every
   validator independently re-runs the same classification prompt on the
   same submitted text, and agreement is only reached if their own label
   matches the leader's. This fixed consensus, but the contract was still
   just "classify and store" — the label had no consequence.
3. **v3** added a deploy-time-configurable policy mapping each sentiment
   to a moderation decision, plus aggregate counters. A tuning issue also
   surfaced during testing: the `principle` text passed to
   `prompt_comparative` needs to be short and direct — an earlier
   phrasing with a double negative made the automatic equivalence judge
   too strict, causing honest agreement to be misread as disagreement.
4. **v4 (this version)** adds the missing piece: a real lifecycle.
   Classification alone, however well-consensed, is still just one pass
   over the evidence. `challenge_case` lets anyone request an independent
   re-classification; agreement moves a case toward `"confirmed"`,
   disagreement moves it to `"disputed"` and *replaces* the stored
   sentiment and decision with the new, validated result. The outcome is
   genuinely composable — it's recomputed from whatever is currently
   valid, not fixed at submission time.

Other deliberate choices:

- **No silent fallback on bad output.** If validator consensus doesn't
  land on one of the three known sentiment labels, the transaction
  reverts rather than defaulting to `"neutral"`.
- **Monotonic aggregate counters.** `get_stats()` reports cumulative
  counts (total classification rounds, and how many times a case became
  confirmed or disputed) rather than a live snapshot that would need to
  be incremented *and* decremented as case state changes. This keeps the
  bookkeeping simple and avoids a class of bugs where aggregates drift
  out of sync with the actual data.
- **No web fetch, no custom validator_fn.** The input is passed directly
  by the caller, and consensus is handled entirely by
  `gl.eq_principle.prompt_comparative` — no hand-written comparison logic
  that could be written incorrectly.

## Contract

Deployed on GenLayer Studionet: `0x318E8484545029200E081D50408aC954D8cF9289`

Open directly in Studio: `https://studio.genlayer.com/?import-contract=0x318E8484545029200E081D50408aC954D8cF9289`

### Constructor

```python
__init__(
    positive_decision: str = "accepted",
    neutral_decision: str = "review",
    negative_decision: str = "flagged",
)
```

### Methods

| Method | Type | Description |
|---|---|---|
| `submit_case(text)` | write | Classifies `text` via consensus, applies the policy, stores the case as `"provisional"`. Returns the new case's id. |
| `challenge_case(case_id)` | write | Independently re-classifies the case's text. Updates `status`, and on disagreement, `sentiment` and `decision`. Returns the case's post-challenge state. |
| `get_case(case_id)` | view | Returns `{text, sentiment, decision, status, resolutions, confirmations}`. |
| `total_cases()` | view | Returns the number of stored cases. |
| `get_policy()` | view | Returns the deploy-time sentiment -> decision mapping. |
| `get_stats()` | view | Returns cumulative classification and lifecycle-transition counters. |

### Source

See [`sentiment_moderation_registry.py`](./sentiment_moderation_registry.py).

## Testing

Deployed and tested in GenLayer Studio:
- Deploy -> `FINALIZED`
- `submit_case("Very satisfied with the service.")` -> sentiment `positive`, decision `accepted`, status `provisional`
- `submit_case("Terrible service, I will never come back.")` -> sentiment `negative`, decision `flagged`, status `provisional`
- `challenge_case(0)` on the positive case, agreeing again -> `confirmations: 2`, status `confirmed`
- `get_stats()` reflects all rounds and transitions correctly
