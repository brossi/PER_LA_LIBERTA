"""``python -m engine.structure.authoring`` — the S4.6b authoring-loop CLI (plan DT-2)."""
from engine.structure.authoring import main

# Guarded so a plain import (pkgutil walks, doc generators, coverage import modes) is inert;
# under `python -m` the interpreter sets __name__ to "__main__" and the CLI runs as before.
if __name__ == "__main__":
    raise SystemExit(main())
