# staged-pipeline-runner

A small, dependency-free runner for **multi-stage pipelines where stages are slow or flaky** (generation, rendering, ETL, model inference).

- **Versioned runs.** Every run of a label gets `v001`, `v002`, ... Nothing is overwritten, so you can compare outputs.
- **Checkpointed stages.** Each stage's output is saved as JSON the moment it finishes.
- **`resume`.** After a failure, continue the latest version and skip stages that already finished.
- **`rerun_from(stage)`.** Tweak one stage and recompute from there into a *new* version, reusing everything upstream.

```
<root>/knight/v001/image.json  mesh.json  rig.json  _meta.json
<root>/knight/v002/image.json  (copied)   mesh.json (recomputed) ...
```

## Why
When stage 7 of 9 fails on an expensive GPU, you want to retry stage 7, not pay for stages 1-6 again. When you tweak stage 4, you want a new version that reuses 1-3 and keeps the old result for comparison.

## Run

```bash
python examples/demo.py
python - <<'PY'
import sys; sys.path.insert(0, "tests")
import test_runner as t
[getattr(t, n)() for n in dir(t) if n.startswith("test_")]
print("ok")
PY
```

## Notes
- Stage outputs must be JSON-serialisable (store big files elsewhere and pass paths).
- Single-process, local-disk by design. For distributed workers swap the file checkpoints for your store (object storage, DB) behind the same two calls.

## License
MIT
