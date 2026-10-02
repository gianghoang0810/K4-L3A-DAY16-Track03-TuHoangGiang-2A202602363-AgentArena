"""Offline real-endpoint simulations; no provider credentials or network calls."""

import json

import pytest

from arena.corpus import Corpus, Doc
from arena.model import ARENA_SYSTEM_PROMPT, ModelResponse, RealModel
from arena.runner import RunnerConfig, run_brief, score_result
from arena.tools import Tools
from arena.trace import Trace
from harness.agent import MAX_EVIDENCE_DEFERRALS, ReActAgent
from harness.layers.budget_policy import BudgetPolicy
from harness.layers.citation_checker import CitationChecker
from harness.layers.critic import Critic
from harness.layers.injection_guard import InjectionGuard
from harness.layers.retry import Retry


QUOTE = "Thời hạn xử lý hồ sơ là năm ngày làm việc."
CORPUS = Corpus(docs=[Doc(doc_id="doc-0001", title="Quy trình hồ sơ", body=QUOTE, tags=())])
BRIEF = {
    "brief_id": "fixture-evidence-guard",
    "question_vi": "Thời hạn xử lý hồ sơ là bao lâu?",
    "required_facts": [{"claim": QUOTE, "supporting_doc_ids": ["doc-0001"]}],
    "budget": {"max_tool_calls": 8, "max_tokens": 12000, "max_seconds": 60},
}


def final(grounded=False):
    return "FINAL: " + json.dumps({
        "answer": QUOTE if grounded else "Chưa đủ căn cứ.",
        "claims": [{"text": QUOTE, "doc_id": "doc-0001"}] if grounded else [],
        "citations": ["doc-0001"] if grounded else [],
        "abstain": not grounded,
    }, ensure_ascii=False)


def action(tool, **args):
    return "ACTION: " + json.dumps({"tool": tool, "args": args}, ensure_ascii=False)


SEARCH = action("search", query="hồ sơ", k=5)
FETCH = action("fetch_doc", doc_id="doc-0001")


class OfflineEndpoint(RealModel):
    def __init__(self, outputs):
        super().__init__("https://example.invalid/v1", "test-only", "offline-fixture")
        self.outputs = outputs
        self.received = []

    def complete(self, messages, **kwargs):
        self.received.append([dict(m) for m in messages])
        index = min(len(self.received) - 1, len(self.outputs) - 1)
        return ModelResponse(text=self.outputs[index], prompt_tokens=20, completion_tokens=20)


def run(endpoint, *, brief=None, config=None):
    return run_brief(
        brief or BRIEF, model=endpoint, corpus=CORPUS, seed=11,
        middleware=[InjectionGuard(), Critic(), CitationChecker(), BudgetPolicy(), Retry()],
        config=config or RunnerConfig(flaky=False),
    )


def test_premature_final_then_snippet_final_recovers_with_model_authored_evidence():
    endpoint = OfflineEndpoint([final(), SEARCH, final(), FETCH, final(True)])
    result = run(endpoint)
    assert not result.error
    assert result.model_calls == 5
    assert result.tool_calls == 3  # search, fetch, submit
    assert result.report["claims"] == [{"text": QUOTE, "doc_id": "doc-0001"}]
    score = score_result(result, BRIEF, CORPUS)
    assert score.gate_passed
    assert score.detail["grounding"]["claims"][0]["verdict"] == "SUPPORTED"
    assert "single_model_call" not in result.flags
    assert not any(flag.startswith("review:") for flag in result.flags)
    # Every correction is a user instruction, not a fabricated observation or action.
    assert "ACTION gọi search" in endpoint.received[1][-1]["content"]
    assert "ACTION gọi fetch_doc" in endpoint.received[3][-1]["content"]
    assert "PHỤ LỤC GIAO THỨC" in endpoint.received[0][0]["content"]


def test_early_grounded_looking_answer_still_requires_reading():
    endpoint = OfflineEndpoint([final(True), SEARCH, FETCH, final(True)])
    result = run(endpoint)
    assert result.model_calls == 4
    assert result.tool_calls == 3
    assert score_result(result, BRIEF, CORPUS).grounding == 55


def test_abstention_after_one_query_gets_one_opportunity_to_requery():
    endpoint = OfflineEndpoint([
        SEARCH, FETCH, final(),
        action("search", query="thời hạn quy trình hồ sơ", k=5), final(),
    ])
    result = run(endpoint)
    assert not result.error
    assert result.model_calls == 5
    assert result.report["abstain"] is True
    assert "truy vấn khác" in endpoint.received[3][-1]["content"]


def test_endpoint_ignoring_corrections_is_bounded_and_can_still_submit():
    endpoint = OfflineEndpoint([final()])
    result = run(endpoint)
    assert result.model_calls == MAX_EVIDENCE_DEFERRALS + 1
    assert result.tool_calls == 1  # no manufactured search ACTION
    assert result.report["abstain"] is True
    assert result.gate()[0]


@pytest.mark.parametrize("budget", [1, 2])
def test_guard_does_not_request_search_without_room_to_fetch_and_submit(budget):
    brief = {**BRIEF, "budget": {**BRIEF["budget"], "max_tool_calls": budget}}
    result = run(OfflineEndpoint([final()]), brief=brief)
    assert result.model_calls == 1
    assert result.tool_calls == 1


def test_guard_honours_last_step_and_retains_a_real_final_after_invalid_turns():
    endpoint = OfflineEndpoint([final(), "Không có ACTION hợp lệ."])
    result = run(endpoint, config=RunnerConfig(flaky=False, max_steps=2))
    assert result.model_calls == 2
    assert result.stop_reason == "refused_final"
    assert result.report["abstain"] is True
    assert result.gate()[0]
    result = run(OfflineEndpoint([final()]), config=RunnerConfig(flaky=False, max_steps=1))
    assert result.model_calls == 1


def test_custom_prompt_is_preserved_and_guard_can_be_disabled():
    endpoint = OfflineEndpoint([final()])
    trace = Trace("custom-prompt", seed=11)
    agent = ReActAgent(
        endpoint, Tools(CORPUS, trace, seed=11, flaky=False), trace,
        system_prompt="Custom instruction", evidence_guard=False,
    )
    agent.run(BRIEF)
    assert len(endpoint.received) == 1
    assert endpoint.received[0][0]["content"] == "Custom instruction"


def test_custom_adapter_can_opt_in_and_guard_state_resets_each_run():
    class CustomAdapter:
        def __init__(self):
            self.calls = 0

        def complete(self, messages):
            self.calls += 1
            return ModelResponse(text=final(), prompt_tokens=20, completion_tokens=20)

    model = CustomAdapter()
    trace = Trace("custom-adapter", seed=11)
    agent = ReActAgent(model, Tools(CORPUS, trace, seed=11, flaky=False), trace, evidence_guard=True)
    for _ in range(2):
        before = model.calls
        agent.run(BRIEF)
        assert model.calls - before == MAX_EVIDENCE_DEFERRALS + 1
    assert agent.system_prompt == ARENA_SYSTEM_PROMPT
