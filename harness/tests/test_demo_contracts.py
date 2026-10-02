"""Regression checks for the public demo's failure modes, not its exact scores."""

import json
from copy import deepcopy
from types import SimpleNamespace

import pytest

from arena.briefs import load_public_briefs
from arena.corpus import Corpus, Doc, INJECTION_CANARY
from arena.model import DEGRADED_MARKERS, MockModel
from arena.runner import RunnerConfig, derive_seed, run_brief, score_result
from arena.tools import ToolResult
from harness.layers.budget_policy import BudgetPolicy
from harness.layers.citation_checker import CitationChecker
from harness.layers.critic import Critic
from harness.layers.injection_guard import BLOCK_END, BLOCK_START, PLACEHOLDER, InjectionGuard
from harness.layers.retry import Retry


@pytest.mark.parametrize("marker", DEGRADED_MARKERS)
def test_retry_recognises_degradation_even_when_tool_reports_success(marker):
    ctx = SimpleNamespace(max_tool_calls=8, tools=SimpleNamespace(calls=0), state={})
    calls = []
    args = {"doc_id": "example"}

    def call(name, arguments):
        calls.append((name, dict(arguments)))
        ctx.tools.calls += 1
        return ToolResult(ok=True, content=marker if len(calls) == 1 else "clean evidence")

    result = Retry().wrap_tool_call(ctx, call, "fetch_doc", args)
    assert result.content == "clean evidence"
    assert calls == [("fetch_doc", args), ("fetch_doc", args)]
    assert ctx.state["retry_attempts"] == 1


def test_retry_exhaustion_returns_last_failure_and_state_is_per_run():
    retry = Retry(max_attempts=3)
    for _ in range(2):
        ctx = SimpleNamespace(max_tool_calls=None, tools=SimpleNamespace(calls=0), state={})
        results = []

        def call(name, args):
            ctx.tools.calls += 1
            result = ToolResult(ok=False, content="", error=f"failure {ctx.tools.calls}")
            results.append(result)
            return result

        result = retry.wrap_tool_call(ctx, call, "fetch_doc", {})
        assert len(results) == 3
        assert result is results[-1]
        assert ctx.state["retry_attempts"] == 2


def test_budget_nudge_does_not_mutate_history_and_none_means_no_limit():
    policy = BudgetPolicy()
    ctx = SimpleNamespace(max_tool_calls=8, tools=SimpleNamespace(calls=7))
    messages = [{"role": "user", "content": "question"}]
    original = deepcopy(messages)
    assert len(policy.before_model(ctx, messages)) == 2
    assert messages == original
    ctx.max_tool_calls = None
    result = ToolResult(ok=True, content="evidence")
    assert policy.before_model(ctx, messages) == messages
    assert policy.wrap_tool_call(ctx, lambda name, args: result, "search", {}) is result


def test_budget_and_retry_together_reserve_submit_even_after_failure():
    ctx = SimpleNamespace(max_tool_calls=8, tools=SimpleNamespace(calls=5), state={})
    retry = Retry()

    def tool(name, args):
        ctx.tools.calls += 1
        return ToolResult(ok=False, content="", error="timeout")

    def retried(name, args):
        return retry.wrap_tool_call(ctx, tool, name, args)

    policy = BudgetPolicy()
    assert not policy.wrap_tool_call(ctx, retried, "fetch_doc", {}).ok
    assert ctx.tools.calls == 7
    assert ctx.state["retry_attempts"] == 1
    assert not policy.wrap_tool_call(ctx, retried, "fetch_doc", {}).ok
    assert ctx.tools.calls == 7


def test_citation_checker_does_not_accept_a_quote_spanning_two_lines():
    doc = Doc(doc_id="source", title="Source", body="first line\nsecond line", tags=())
    ctx = SimpleNamespace(corpus=Corpus(docs=[doc]), observed_text=doc.body)
    claim = {"doc_id": "wrong", "text": "line\nsecond"}
    report = {"claims": [deepcopy(claim)]}
    out = CitationChecker().after_agent(ctx, report)
    assert out["claims"] == [claim]


def test_critic_does_not_salvage_a_fused_claim_using_an_unobserved_source():
    first = Doc(doc_id="a", title="A", body="first evidence", tags=())
    second = Doc(doc_id="b", title="B", body="second evidence", tags=())
    ctx = SimpleNamespace(corpus=Corpus(docs=[first, second]), observed_text=first.body)
    report = {"claims": [{"doc_id": "a", "text": "first evidence và second evidence"}]}
    out = Critic().after_agent(ctx, report)
    assert out["claims"] == []
    assert out["citations"] == []
    assert out["abstain"] is True


def test_guard_handles_multiple_blocks_and_preserves_result_metadata():
    block = f"{BLOCK_START}\n{INJECTION_CANARY}\n{BLOCK_END}"
    raw = ToolResult(ok=False, content=f"before{block}between{block}after", error="timeout")
    result = InjectionGuard().wrap_tool_call(SimpleNamespace(), lambda n, a: raw, "fetch_doc", {})
    assert result.content == f"before{PLACEHOLDER}between{PLACEHOLDER}after"
    assert result.ok is raw.ok
    assert result.error == raw.error
    assert raw.content.count(BLOCK_START) == 2


@pytest.mark.parametrize("base_seed", [11, 12, 13])
def test_public_stack_preserves_submission_safety_and_budget(base_seed):
    """Public IDs select fixtures only; production layers never depend on them."""
    corpus = Corpus.generate(seed=42)
    for index, brief in enumerate(load_public_briefs()):
        seed = derive_seed(base_seed, index)
        result = run_brief(
            brief,
            model=MockModel(corpus=corpus, seed=seed),
            corpus=corpus,
            middleware=[InjectionGuard(), Critic(), CitationChecker(), BudgetPolicy(), Retry()],
            seed=seed,
            config=RunnerConfig(flaky=True),
        )
        context = (brief["brief_id"], seed)
        assert not result.error, (context, result.error)
        assert result.final_outputs > 0, context
        score = score_result(result, brief, corpus)
        assert score.gate_passed, (context, score.gate_reason)
        assert result.tool_calls <= brief["budget"]["max_tool_calls"], context
        assert INJECTION_CANARY not in json.dumps(result.report, ensure_ascii=False), context
        verdicts = {claim["verdict"] for claim in score.detail["grounding"]["claims"]}
        assert not verdicts.intersection({"NOT_FROM_MODEL", "NOT_SUBMITTED"}), (context, verdicts)
