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

    - One write method, one LLM call per validator.
    - Uses GenLayer's built-in `gl.eq_principle.prompt_comparative` helper
      for consensus. Each validator independently re-runs the same
      classification prompt on the *same submitted text* and an NLP judge
      checks that their result matches the leader's under `principle`.
      This is important: an earlier version of this contract used
      `prompt_non_comparative` with criteria that only checked the
      leader's answer was one of three allowed words — it never verified
      that the chosen word actually matched the sentiment of the text.
      A leader could have returned "positive" for a negative text and
      validators would have accepted it, since nothing tied the label to
      the input. `prompt_comparative` fixes this by having every
      validator independently derive their own label from the same text,
      so agreement can only happen if they'd genuinely classify it the
      same way.
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

        def classify() -> str:
            # Each validator runs this itself, independently, on the same
            # `text` — the label they arrive at is what gets compared
            # against the leader's, not just format-checked.
            response = gl.nondet.exec_prompt(
                "Classify the sentiment of the following text. "
                "Respond with exactly one word: positive, negative, or neutral. "
                "No punctuation, no extra words, no explanation.\n\n"
                f"TEXT:\n{text}"
            )
            return response.strip().lower().strip(".")

        raw_sentiment = gl.eq_principle.prompt_comparative(
            classify,
            principle=(
                "The result is exactly one of: positive, negative, neutral. "
                "It correctly reflects the sentiment actually expressed in the "
                "submitted text — not just any one of the three allowed words."
            ),
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
