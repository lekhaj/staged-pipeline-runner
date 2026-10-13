from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


class StageFailed(RuntimeError):
    def __init__(self, stage: str, version: int, cause: Exception):
        super().__init__(f"stage '{stage}' failed in {version_name(version)}: {cause}")
        self.stage, self.version, self.cause = stage, version, cause


def version_name(v: int) -> str:
    return f"v{v:03d}"


@dataclass(frozen=True)
class Stage:
    """fn(inputs: dict) -> JSON-serialisable output. `inputs` holds outputs of all earlier stages."""

    name: str
    fn: Callable[[dict], Any]


class Pipeline:
    """Stages run in order. Each result is checkpointed to disk.

    Layout:  <root>/<label>/v001/<stage>.json  (+ _meta.json)

    * ``run(label)``                 starts a NEW version (v001, v002, ...) so history is never overwritten.
    * ``resume(label)``              continues the latest version after a failure, skipping finished stages.
    * ``rerun_from(label, stage)``   makes a NEW version that reuses earlier stages' outputs and recomputes from `stage`.
    """

    def __init__(self, root: str | Path, stages: list[Stage]):
        names = [s.name for s in stages]
        if len(set(names)) != len(names):
            raise ValueError("stage names must be unique")
        self.root, self.stages = Path(root), stages

    # -- versions -----------------------------------------------------------
    def versions(self, label: str) -> list[int]:
        d = self.root / label
        return sorted(int(p.name[1:]) for p in d.glob("v[0-9][0-9][0-9]")) if d.exists() else []

    def _dir(self, label: str, v: int) -> Path:
        return self.root / label / version_name(v)

    def _new_version(self, label: str) -> int:
        v = (self.versions(label) or [0])[-1] + 1
        self._dir(label, v).mkdir(parents=True)
        return v

    # -- IO -----------------------------------------------------------------
    def load(self, label: str, version: int, stage: str) -> Any:
        return json.loads((self._dir(label, version) / f"{stage}.json").read_text())

    def completed(self, label: str, version: int) -> list[str]:
        d = self._dir(label, version)
        return [s.name for s in self.stages if (d / f"{s.name}.json").exists()]

    # -- execution ----------------------------------------------------------
    def _execute(self, label: str, version: int, seed: dict) -> dict:
        d = self._dir(label, version)
        results = dict(seed)
        for st in self.stages:
            path = d / f"{st.name}.json"
            if path.exists():
                results[st.name] = json.loads(path.read_text())
                continue
            t0 = time.time()
            try:
                out = st.fn(dict(results))
                path.write_text(json.dumps(out))
            except Exception as exc:
                (d / "_meta.json").write_text(json.dumps({"status": "failed", "stage": st.name, "error": str(exc)}))
                raise StageFailed(st.name, version, exc) from exc
            results[st.name] = out
            print(f"[{label} {version_name(version)}] {st.name} ok ({time.time() - t0:.2f}s)")
        (d / "_meta.json").write_text(json.dumps({"status": "complete"}))
        return results

    def run(self, label: str) -> dict:
        return self._execute(label, self._new_version(label), {})

    def resume(self, label: str) -> dict:
        vs = self.versions(label)
        if not vs:
            raise FileNotFoundError(f"no runs for '{label}'")
        return self._execute(label, vs[-1], {})

    def rerun_from(self, label: str, stage: str, source_version: int | None = None) -> dict:
        names = [s.name for s in self.stages]
        if stage not in names:
            raise ValueError(f"unknown stage '{stage}'")
        src = source_version or (self.versions(label) or [None])[-1]
        if src is None:
            raise FileNotFoundError(f"no runs for '{label}'")
        v = self._new_version(label)
        for name in names[: names.index(stage)]:  # carry forward untouched stages
            p = self._dir(label, src) / f"{name}.json"
            if p.exists():
                (self._dir(label, v) / f"{name}.json").write_text(p.read_text())
        return self._execute(label, v, {})
