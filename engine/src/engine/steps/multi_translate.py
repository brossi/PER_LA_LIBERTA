"""multi_translate step — scaffold stub.

Ported from the top-level ``multi_translate.py`` in M5. The real signature is
``run(ws: BookWorkspace, cfg: ResolvedConfig, lang: LanguagePlugin, **opts)``:
the step takes the workspace + resolved config + active language plugin and
replaces every book/scan/language constant with a ``cfg.*`` / ``lang.*`` read.
"""

from __future__ import annotations

PORTED_IN = "M5"


def run(*args, **kwargs):
    raise NotImplementedError(
        "engine.steps.multi_translate.run is an M0 scaffold stub; ported in M5."
    )
