"""A fake asset pipeline: prompt -> image -> mesh -> rig. The 'mesh' stage fails once, then we resume.

    python examples/demo.py
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from staged_runner import Pipeline, Stage, StageFailed  # noqa: E402

state = {"mesh_calls": 0}


def image(inp): return {"image": "knight.png"}
def mesh(inp):
    state["mesh_calls"] += 1
    if state["mesh_calls"] == 1:
        raise RuntimeError("GPU out of memory")
    return {"mesh": "knight.obj", "from": inp["image"]["image"]}
def rig(inp): return {"rig": "knight.fbx", "from": inp["mesh"]["mesh"]}


p = Pipeline(tempfile.mkdtemp(), [Stage("image", image), Stage("mesh", mesh), Stage("rig", rig)])
try:
    p.run("knight")
except StageFailed as e:
    print("FAILED:", e)
print("resume ->", p.resume("knight")["rig"])          # skips 'image', retries 'mesh'
p.rerun_from("knight", "mesh")                         # new version, reuses 'image'
print("versions:", p.versions("knight"))
