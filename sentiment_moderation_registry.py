# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

from genlayer import *
from dataclasses import dataclass
import typing


@allow_storage
@dataclass
class Case:
    text: str
    sentiment: str      # "positive" | "negative" | "neutral" — currently validated label
    decision: str        # policy-derived outcome, e.g. "accepted" | "review" | "flagged"
    status: str          # "provisional" | "confirmed" | "disputed"
    resolutions: u32      # how many independent classification rounds this case has been through
    confirmations: u32    # consecutive rounds in a row that agreed on the same sentiment


class SentimentModerationRegistry(gl.Contract):
    """
    A consensus-validated feedback moderation registry with a real
    review/challenge lifecycle.

        submitted text
              -> independent comparative classification (validator consensus)
              -> validated sentiment
              -> configurable policy rule
              -> stored decision, status = "provisional"

        anyone can challenge_case(id) at any time:
              -> the same text is independently re-classified through
                 consensus, from scratch
              -> if the new sentiment agrees with the current one:
                    confirmations += 1
                    status -> "confirmed" once confirmations reach 2
              -> if it disagrees:
                    sentiment and decision are replaced with the new,
                    validated result
                    confirmations reset to 1
                    status -> "disputed"

    This is a deliberate design choice: a single classification is
    provisional, not authoritative. A case only becomes "confirmed" once
    two independent rounds in a row agree, and a disagreement doesn't get
    silently ignored — it overturns the stored decision and is recorded
    as a dispute. The lifecycle transitions are explicit and the outcome
    (decision) is recomputed from whatever sentiment is currently valid,
    not fixed at submission time.

    Earlier versions of this contract:
    - classified text and stored the label with no consequence beyond
      storage (fixed by adding the decision policy below);
    - used `gl.eq_principle.prompt_non_comparative` with format-only
      criteria, so validators never actually checked the label against
      the text (fixed by switching to `prompt_comparative`, where every
      validator independently re-derives the label);
    - used an overly convoluted `principle` wording ("not just any one of
      the three allowed words") that made the automatic equivalence judge
      too strict, causing honest agreement to be misread as disagreement
      (fixed by simplifying the wording to a direct positive statement).

    On invalid model output: if validator consensus doesn't land on one
    of the three known sentiment labels, the transaction reverts. An
    unrecognized result is never silently coerced into a default label —
    that would mask exactly the kind of disagreement this contract exists
    to catch.
    """

    cases: TreeMap[u32, Case]
    next_id: u32

    # Configurable policy, set once at deploy time.
    positive_decision: str
    neutral_decision: str
    negative_decision: str

    # Cumulative counters. These are monotonic — they count how many
    # classification rounds and lifecycle transitions have happened in
    # total, not a live snapshot of current case states. That keeps the
    # bookkeeping simple: every counter here only ever increments, so
    # there's no decrement/rebalance logic that could drift out of sync
    # with the actual case data.
    total_classifications: u32
    positive_classifications: u32
    negative_classifications: u32
    neutral_classifications: u32
    confirmed_events: u32
    disputed_events: u32

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

        self.total_classifications = u32(0)
        self.positive_classifications = u32(0)
        self.negative_classifications = u32(0)
        self.neutral_classifications = u32(0)
        self.confirmed_events = u32(0)
        self.disputed_events = u32(0)

    def _policy_for(self, sentiment: str) -> str:
        if sentiment == "positive":
            return self.positive_decision
        if sentiment == "negative":
            return self.negative_decision
        return self.neutral_decision  # sentiment == "neutral"

    def _classify_text(self, text: str) -> str:
        """
        Runs one independent, consensus-validated classification round on
        `text` and updates the cumulative classification counters. Used
        by both submit_case (the first round) and challenge_case (every
        subsequent round) so both paths go through identical, tested
        logic.
        """

        def classify() -> str:
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
            raise gl.vm.UserError(
                f"Validated sentiment '{raw_sentiment}' is not a recognized label"
            )

        self.total_classifications = u32(self.total_classifications + 1)
        if sentiment == "positive":
            self.positive_classifications = u32(self.positive_classifications + 1)
        elif sentiment == "negative":
            self.negative_classifications = u32(self.negative_classifications + 1)
        else:
            self.neutral_classifications = u32(self.neutral_classifications + 1)

        return sentiment

    @gl.public.write
    def submit_case(self, text: str) -> u32:
        """
        Classifies `text` via validator consensus, applies the deploy-time
        policy to derive an initial decision, and stores the case in
        "provisional" status. Returns the new case's id.
        """
        if not text.strip():
            raise gl.vm.UserError("Case text cannot be empty")

        sentiment = self._classify_text(text)
        decision = self._policy_for(sentiment)

        case_id = self.next_id
        self.cases[case_id] = Case(
            text=text,
            sentiment=sentiment,
            decision=decision,
            status="provisional",
            resolutions=u32(1),
            confirmations=u32(1),
        )
        self.next_id = u32(self.next_id + 1)
        return case_id

    @gl.public.write
    def challenge_case(self, case_id: u32) -> typing.Any:
        """
        Re-runs an independent, consensus-validated classification of the
        case's stored text. If it agrees with the current sentiment, the
        case moves toward "confirmed"; if it disagrees, the sentiment and
        decision are replaced and the case becomes "disputed". Returns the
        case's state after the challenge.
        """
        if case_id not in self.cases:
            raise gl.vm.UserError("Unknown case id")

        case = self.cases[case_id]
        new_sentiment = self._classify_text(case.text)
        case.resolutions = u32(case.resolutions + 1)

        if new_sentiment == case.sentiment:
            case.confirmations = u32(case.confirmations + 1)
            if case.confirmations >= u32(2):
                if case.status != "confirmed":
                    self.confirmed_events = u32(self.confirmed_events + 1)
                case.status = "confirmed"
        else:
            case.sentiment = new_sentiment
            case.decision = self._policy_for(new_sentiment)
            case.confirmations = u32(1)
            case.status = "disputed"
            self.disputed_events = u32(self.disputed_events + 1)

        self.cases[case_id] = case
        return {
            "case_id": case_id,
            "sentiment": case.sentiment,
            "decision": case.decision,
            "status": case.status,
            "resolutions": case.resolutions,
            "confirmations": case.confirmations,
        }

    @gl.public.view
    def get_case(self, case_id: u32) -> typing.Any:
        if case_id not in self.cases:
            raise gl.vm.UserError("Unknown case id")
        c = self.cases[case_id]
        return {
            "text": c.text,
            "sentiment": c.sentiment,
            "decision": c.decision,
            "status": c.status,
            "resolutions": c.resolutions,
            "confirmations": c.confirmations,
        }

    @gl.public.view
    def total_cases(self) -> u32:
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
            "total_cases": self.next_id,
            "total_classifications": self.total_classifications,
            "positive_classifications": self.positive_classifications,
            "negative_classifications": self.negative_classifications,
            "neutral_classifications": self.neutral_classifications,
            "confirmed_events": self.confirmed_events,
            "disputed_events": self.disputed_events,
        }
