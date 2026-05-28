"""Tests for decepticon.runtime.cart."""

from __future__ import annotations

import time

from decepticon.runtime.cart import (
    ChangeEvent,
    EngagementSnapshot,
    LinearOPPLANAdapter,
    ReplayPlan,
    ReplayRunner,
    SnapshotNodeKey,
    Watcher,
    diff_snapshots,
)


class _Node:
    def __init__(self, node_id, kind, label, properties=None):
        self.id = node_id
        self.kind = kind
        self.label = label
        self.properties = properties or {}


class _Edge:
    def __init__(self, source, target, kind, properties=None):
        self.source = source
        self.target = target
        self.kind = kind
        self.properties = properties or {}


class _Graph:
    def __init__(self, nodes, edges=None):
        self.nodes = {n.id: n for n in nodes}
        self.edges = {f"e{i}": e for i, e in enumerate(edges or [])}


def test_snapshot_id_is_stable_for_identical_graphs():
    g1 = _Graph([_Node("a", "host", "10.0.0.1")])
    g2 = _Graph([_Node("a-different-id", "host", "10.0.0.1")])
    assert (
        EngagementSnapshot.from_graph(g1).snapshot_id
        == EngagementSnapshot.from_graph(g2).snapshot_id
    )


def test_snapshot_id_changes_with_node_changes():
    g1 = _Graph([_Node("a", "host", "10.0.0.1")])
    g2 = _Graph([_Node("a", "host", "10.0.0.2")])
    assert (
        EngagementSnapshot.from_graph(g1).snapshot_id
        != EngagementSnapshot.from_graph(g2).snapshot_id
    )


def test_diff_snapshots_detects_added_nodes():
    s1 = EngagementSnapshot.from_graph(_Graph([_Node("a", "host", "10.0.0.1")]))
    s2 = EngagementSnapshot.from_graph(
        _Graph([_Node("a", "host", "10.0.0.1"), _Node("b", "host", "10.0.0.2")])
    )
    delta = diff_snapshots(s1, s2)
    assert SnapshotNodeKey(kind="host", label="10.0.0.2") in delta.added_nodes
    assert not delta.removed_nodes


def test_diff_snapshots_detects_removed_nodes():
    s1 = EngagementSnapshot.from_graph(
        _Graph([_Node("a", "host", "10.0.0.1"), _Node("b", "host", "10.0.0.2")])
    )
    s2 = EngagementSnapshot.from_graph(_Graph([_Node("a", "host", "10.0.0.1")]))
    delta = diff_snapshots(s1, s2)
    assert SnapshotNodeKey(kind="host", label="10.0.0.2") in delta.removed_nodes


def test_diff_snapshots_detects_changed_nodes():
    s1 = EngagementSnapshot.from_graph(
        _Graph([_Node("a", "host", "10.0.0.1", {"state": "up"})])
    )
    s2 = EngagementSnapshot.from_graph(
        _Graph([_Node("a", "host", "10.0.0.1", {"state": "compromised"})])
    )
    delta = diff_snapshots(s1, s2)
    assert SnapshotNodeKey(kind="host", label="10.0.0.1") in delta.changed_nodes


def test_diff_snapshots_extracts_affected_techniques():
    s1 = EngagementSnapshot.from_graph(_Graph([]))
    s2 = EngagementSnapshot.from_graph(
        _Graph([_Node("a", "finding", "f1", {"mitre_attack": "T1190"})])
    )
    delta = diff_snapshots(s1, s2)
    assert "T1190" in delta.affected_techniques


def test_diff_snapshots_handles_list_mitre_tags():
    s1 = EngagementSnapshot.from_graph(_Graph([]))
    s2 = EngagementSnapshot.from_graph(
        _Graph([_Node("a", "finding", "f", {"mitre_attack": ["T1003", "T1059"]})])
    )
    delta = diff_snapshots(s1, s2)
    assert set(delta.affected_techniques) >= {"T1003", "T1059"}


def test_empty_delta_flag_works():
    s = EngagementSnapshot.from_graph(_Graph([_Node("a", "host", "10.0.0.1")]))
    delta = diff_snapshots(s, s)
    assert delta.is_empty


class _Obj:
    def __init__(self, name, mitre=None):
        self.id = name
        self.mitre = mitre


class _OPPLAN:
    def __init__(self, objectives):
        self.objectives = objectives


def test_linear_adapter_all_objectives_returns_declaration_order():
    o = _OPPLAN([_Obj("o1"), _Obj("o2"), _Obj("o3")])
    adapter = LinearOPPLANAdapter(o)
    assert adapter.all_objectives() == ["o1", "o2", "o3"]


def test_linear_adapter_filters_by_technique_tag():
    o = _OPPLAN(
        [
            _Obj("o1", mitre="T1190"),
            _Obj("o2", mitre="T1003"),
            _Obj("o3", mitre=["T1190", "T1059"]),
        ]
    )
    adapter = LinearOPPLANAdapter(o)
    assert sorted(adapter.objectives_for_techniques(["T1190"])) == ["o1", "o3"]


def test_linear_adapter_returns_all_when_techniques_empty():
    o = _OPPLAN([_Obj("a", mitre="T1190"), _Obj("b", mitre="T1003")])
    adapter = LinearOPPLANAdapter(o)
    assert sorted(adapter.objectives_for_techniques([])) == ["a", "b"]


def _build_runner(record_path=None, dry_run=True):
    opplan = _OPPLAN([_Obj("scan", mitre="T1190"), _Obj("dump", mitre="T1003")])
    adapter = LinearOPPLANAdapter(opplan)
    base_snapshot = EngagementSnapshot.from_graph(_Graph([]))
    snapshot_provider = lambda: EngagementSnapshot.from_graph(  # noqa: E731
        _Graph([_Node("a", "finding", "f1", {"mitre_attack": "T1190"})])
    )
    runner = ReplayRunner(
        opplan_adapter=adapter,
        snapshot_provider=snapshot_provider,
        record_path=record_path,
        dry_run=dry_run,
    )
    return runner, base_snapshot


def test_replay_runner_plan_picks_objectives_by_technique():
    runner, base = _build_runner()
    event = ChangeEvent(
        source="cloudtrail",
        event_type="EC2 RunInstances",
        resource_id="i-abc",
        resource_kind="ec2_instance",
        technique_tags=["T1190"],
        observed_at=time.time(),
    )
    plan = runner.plan(event, base)
    assert plan.selected_objectives == ["scan"]
    assert plan.delta_summary["added_nodes"] == 1


def test_replay_runner_execute_dry_run_returns_status():
    runner, base = _build_runner(dry_run=True)
    event = ChangeEvent(
        source="cloudtrail",
        event_type="x",
        resource_id="r",
        resource_kind="k",
        technique_tags=["T1190"],
    )
    plan = runner.plan(event, base)
    result = runner.execute(plan)
    assert result["status"] == "dry_run"
    assert result["plan_id"] == plan.plan_id


def test_replay_runner_execute_live_reports_unwired():
    runner, base = _build_runner(dry_run=False)
    event = ChangeEvent(
        source="cloudtrail",
        event_type="x",
        resource_id="r",
        resource_kind="k",
        technique_tags=["T1190"],
    )
    plan = runner.plan(event, base)
    result = runner.execute(plan)
    assert result["status"] == "live_unwired"
    assert "SubAgentTaskSpec" in result["reason"]


def test_watcher_dispatches_plans_to_subscribers():
    runner, base = _build_runner()
    watcher = Watcher(runner=runner, previous_snapshot=base)
    captured: list[ReplayPlan] = []
    watcher.subscribe(captured.append)
    event = ChangeEvent(
        source="k8s_audit",
        event_type="Pod created",
        resource_id="pod-x",
        resource_kind="pod",
        technique_tags=["T1190"],
    )
    plan = watcher.handle_event(event)
    assert len(captured) == 1
    assert captured[0] is plan


def test_watcher_subscriber_exception_does_not_break_dispatch():
    runner, base = _build_runner()
    watcher = Watcher(runner=runner, previous_snapshot=base)

    def _bad(_):
        raise RuntimeError("oops")

    good_calls: list[ReplayPlan] = []
    watcher.subscribe(_bad)
    watcher.subscribe(good_calls.append)
    plan = watcher.handle_event(
        ChangeEvent(
            source="x",
            event_type="x",
            resource_id="r",
            resource_kind="k",
            technique_tags=["T1190"],
        )
    )
    assert len(good_calls) == 1
    assert good_calls[0] is plan
