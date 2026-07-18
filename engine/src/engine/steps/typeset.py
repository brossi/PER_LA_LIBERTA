"""typeset step — scaffold stub.

Ported from the top-level ``typeset.py`` in M3b (split out from M3). The real signature is
``run(ws: BookWorkspace, cfg: ResolvedConfig, lang: LanguagePlugin, **opts)``:
the step takes the workspace + resolved config + active language plugin and
replaces every book/scan/language constant with a ``cfg.*`` / ``lang.*`` read.
"""

from __future__ import annotations

PORTED_IN = "M3b"


def run(*args, **kwargs):
    raise NotImplementedError(
        "engine.steps.typeset.run is an M0 scaffold stub; ported in M3b."
    )
