# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

from genlayer import *
from dataclasses import dataclass
import typing


@allow_storage
@dataclass
class Feedback:
    text: str
    sentiment: str  # "positive" | "negative" | "neutral"


class SentimentRegistry(gl.Contract):
    """
    A deliberately minimal Intelligent Contract, built to keep the bug
    surface as small as possible:

    - One write method, one LLM call.
    - Uses GenLayer's built-in `gl.eq_principle.prompt_non_comparative`
      helper for consensus, instead of a hand-written leader_fn/validator_fn
      pair. The leader calls the LLM once; every other validator checks
      the leader's answer against the `criteria` text — they don't need
      to independently re-derive and compare a result, so there's no
      custom comparison logic that can be written incorrectly.
    - No web fetch (gl.nondet.web.get), so no dependency on an external
      page being reachable or unchanged.
    - No multi-stage state machine (pending/resolved/finalized/disputed).
      Each submission is classified once and stored — there's nothing
      to get "stuck" in an intermediate state.

    Trade-off: this also means a submission's sentiment can never be
    re-checked or disputed later. That's a deliberate simplification,
    not an oversight — add a resolve()-style re-classification step
    only if you actually need it, since every added state transition
    is another thing that can be modeled wrong.
    """

    feedback: TreeMap[u32, Feedback]
    next_id: u32

    def __init__(self):
        self.next_id = u32(0)

    @gl.public.write
    def submit_feedback(self, text: str) -> u32:
        """Classifies the sentiment of `text` and stores it. Returns the new entry's id."""
        if not text.strip():
            raise gl.vm.UserError("Feedback text cannot be empty")

        def get_input() -> str:
            return text

        raw_sentiment = gl.eq_principle.prompt_non_comparative(
            get_input,
            task=(
                "Classify the sentiment of the given text. "
                "Respond with exactly one word: positive, negative, or neutral."
            ),
            criteria="""
                The response is exactly one of the words: positive, negative, neutral
                No punctuation, no extra words, no explanation
            """,
        )

        # Defensive normalization: even with a tight `criteria`, an LLM can
        # still return "Positive." or similar. Normalize instead of trusting
        # the raw string, and fall back to a safe, valid value if the model
        # still returns something unexpected — never store an arbitrary
        # unvalidated string as if it were one of the three known labels.
        sentiment = raw_sentiment.strip().lower().strip(".")
        if sentiment not in ("positive", "negative", "neutral"):
            sentiment = "neutral"

        feedback_id = self.next_id
        self.feedback[feedback_id] = Feedback(text=text, sentiment=sentiment)
        self.next_id = u32(self.next_id + 1)
        return feedback_id

    @gl.public.view
    def get_feedback(self, feedback_id: u32) -> typing.Any:
        if feedback_id not in self.feedback:
            raise gl.vm.UserError("Unknown feedback id")
        f = self.feedback[feedback_id]
        return {"text": f.text, "sentiment": f.sentiment}

    @gl.public.view
    def total_feedback(self) -> u32:
        return self.next_id
