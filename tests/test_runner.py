import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from staged_runner import Pipeline, Stage, StageFailed  # noqa: E402


def make(calls, fail_mesh_once=False):
    def a(i): calls["a"] += 1; return 1
    def b(i):
        calls["b"] += 1
        if fail_mesh_once and calls["b"] == 1:
            raise RuntimeError("boom")
        return i["a"] + 1
    def c(i): calls["c"] += 1; return i["b"] + 1
    return Pipeline(tempfile.mkdtemp(), [Stage("a", a), Stage("b", b), Stage("c", c)])


def test_runs_all_stages_and_versions_increment():
    calls = dict(a=0, b=0, c=0)
    p = make(calls)
    assert p.run("x")["c"] == 3
    p.run("x")
    assert p.versions("x") == [1, 2]


def test_resume_skips_finished_stages():
    calls = dict(a=0, b=0, c=0)
    p = make(calls, fail_mesh_once=True)
    try:
        p.run("x")
        assert False
    except StageFailed as e:
        assert e.stage == "b"
    assert p.completed("x", 1) == ["a"]
    assert p.resume("x")["c"] == 3
    assert calls["a"] == 1 and calls["b"] == 2


def test_rerun_from_reuses_earlier_stages_in_new_version():
    calls = dict(a=0, b=0, c=0)
    p = make(calls)
    p.run("x")
    p.rerun_from("x", "b")
    assert p.versions("x") == [1, 2]
    assert calls == dict(a=1, b=2, c=2)
    assert p.load("x", 1, "c") == 3  # history untouched
