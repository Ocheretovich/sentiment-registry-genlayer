# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

from genlayer import *
from dataclasses import dataclass
import typing


@allow_storage
@dataclass
class Feedback:
    text: str
    sentiment: str  # "positive" | "negative" | "neutral" — validated by consensus
    decision: str    # policy-derived outcome, e.g. "accepted" | "review" | "flagged"


class SentimentModerationRegistry(gl.Contract):
    """
    A consensus-validated feedback moderation registry.

    Each submission is classified by sentiment through GenLayer's validator
    consensus: every validator independently re-classifies the same text
    (gl.eq_principle.prompt_comparative), and agreement is checked against
    the actual content of the text, not just the format of the answer.

    That validated sentiment is not the end of the story — it's fed into a
    configurable, fully deterministic policy (set once at deploy time) that
    turns it into a moderation decision, and both the sentiment and the
    decision update running aggregate counters:

        submitted text
              -> independent comparative classification (consensus)
              -> validated sentiment
              -> configurable policy rule
              -> stored moderation decision
              -> aggregate counters

    Deployers choose what each sentiment means for their use case — e.g.
    positive -> "accepted", neutral -> "review", negative -> "flagged" for
    a support-feedback triage queue, or a different mapping entirely for a
    different domain. The sentiment doesn't just get stored; it determines
    what happens next.

    On invalid model output: an earlier version of this contract silently
    coerced any unrecognized response into "neutral". That's a masked
    failure, not a handled one — it would hide exactly the kind of
    disagreement this contract exists to catch. This version fails the
    transaction instead if validator consensus doesn't land on one of the
    three known sentiment labels.
    """

    feedback: TreeMap[u32, Feedback]
    next_id: u32

    # Configurable policy, set once at deploy time.
    positive_decision: str
    neutral_decision: str
    negative_decision: str

    # Aggregate counters, updated on every submission.
    positive_count: u32
    neutral_count: u32
    negative_count: u32

    def __init__(
        self,
        positive_decision: str = "accepted",
        neutral_decision: str = "review",
        negative_decision: str = "flagged",
    ):
        self.next_id = u32(0)
        self.positive_decision = positive_decision
        self.neutral_decision = neutral_decision
        self.negative_decision = negative_decision
        self.positive_count = u32(0)
        self.neutral_count = u32(0)
        self.negative_count = u32(0)

    @gl.public.write
    def submit_feedback(self, text: str) -> u32:
        """
        Classifies `text` via validator consensus, applies the deploy-time
        policy to derive a moderation decision, stores both, and updates
        the aggregate counters. Returns the new entry's id.
        """
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
                "The result must be exactly one of: positive, negative, neutral. "
                "It must match the sentiment expressed in the submitted text."
            ),
        )

        sentiment = raw_sentiment.strip().lower().strip(".")
        if sentiment not in ("positive", "negative", "neutral"):
            # Consensus was reached on *something*, but it isn't one of the
            # three labels this contract knows how to act on. Fail loudly
            # rather than silently defaulting to a safe-looking value.
            raise gl.vm.UserError(
                f"Validated sentiment '{raw_sentiment}' is not a recognized label"
            )

        if sentiment == "positive":
            decision = self.positive_decision
            self.positive_count = u32(self.positive_count + 1)
        elif sentiment == "negative":
            decision = self.negative_decision
            self.negative_count = u32(self.negative_count + 1)
        else:
            decision = self.neutral_decision
            self.neutral_count = u32(self.neutral_count + 1)

        feedback_id = self.next_id
        self.feedback[feedback_id] = Feedback(text=text, sentiment=sentiment, decision=decision)
        self.next_id = u32(self.next_id + 1)
        return feedback_id

    @gl.public.view
    def get_feedback(self, feedback_id: u32) -> typing.Any:
        if feedback_id not in self.feedback:
            raise gl.vm.UserError("Unknown feedback id")
        f = self.feedback[feedback_id]
        return {"text": f.text, "sentiment": f.sentiment, "decision": f.decision}

    @gl.public.view
    def total_feedback(self) -> u32:
        return self.next_id

    @gl.public.view
    def get_policy(self) -> typing.Any:
        return {
            "positive": self.positive_decision,
            "neutral": self.neutral_decision,
            "negative": self.negative_decision,
        }

    @gl.public.view
    def get_stats(self) -> typing.Any:
        return {
            "total": self.next_id,
            "positive_count": self.positive_count,
            "neutral_count": self.neutral_count,
            "negative_count": self.negative_count,
        }
