"""Low-overhead, opt-in telemetry for structure re-binding.

The recorder deliberately performs no logging or filesystem I/O.  It keeps a small in-memory
span table and optionally publishes the current stage through a caller-supplied callback.  Scale
and diagnostic harnesses may therefore observe a live rebind without coupling the production
engine to a particular logger.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field

REBIN_TELEMETRY_SCHEMA = "engine-rebind-telemetry@v1"

# Stable stage names used by the scale harness's shared live-stage register.  Appending is safe;
# renaming or reordering requires a telemetry schema revision.
REBIN_TELEMETRY_STAGES = (
    "structure-map.write.tier1",
    "structure-map.write.render",
    "structure-map.write.io",
    "structure-map.load.read",
    "structure-map.load.parse",
    "structure-map.load.tier1",
    "structure-map.load.typed-build",
    "structure-map.load.tier2",
    "rebind.enumerate-slots",
    "rebind.materialize-old-tokens",
    "rebind.materialize-fresh-tokens",
    "rebind.align-tokens",
    "rebind.prepare-anchor-queries",
    "rebind.locate-old-anchors",
    "rebind.locate-fresh-anchors",
    "rebind.index-boundary-owners",
    "rebind.detect-token-duplication",
    "rebind.detect-tokenless-duplication",
    "rebind.resolve-slots",
    "rebind.aggregate-nodes",
    "rebind.migrate-projection",
    "rebind.validate-projection",
    "rebind.restamp-evidence",
    "rebind.assemble-report",
)

StageCallback = Callable[[str, int | None, int | None], None]


@dataclass(slots=True)
class TelemetrySpan:
    """Mutable attributes yielded to one measured telemetry span."""

    name: str
    parent: str | None
    started_wall_ns: int
    started_cpu_ns: int
    attributes: dict[str, object] = field(default_factory=dict)

    def update(self, **attributes: object) -> None:
        self.attributes.update(attributes)


class RebindTelemetry:
    """Collect nested wall/CPU spans and publish coarse live stage progress."""

    def __init__(
        self,
        *,
        stage_callback: StageCallback | None = None,
        enabled: bool = True,
    ) -> None:
        self._enabled = enabled
        self._origin_wall_ns = time.perf_counter_ns()
        self._stage_callback = stage_callback
        self._stack: list[TelemetrySpan] = []
        self._records: list[dict[str, object]] = []

    @property
    def active_stage(self) -> str:
        return self._stack[-1].name if self._stack else "idle"

    def _publish(
        self,
        stage: str,
        completed: int | None = None,
        total: int | None = None,
    ) -> None:
        if self._enabled and self._stage_callback is not None:
            self._stage_callback(stage, completed, total)

    @contextmanager
    def span(self, name: str, **attributes: object) -> Iterator[TelemetrySpan]:
        if not name:
            raise ValueError("telemetry span name must not be empty")
        if not self._enabled:
            yield TelemetrySpan(name, None, 0, 0, dict(attributes))
            return
        parent = self._stack[-1].name if self._stack else None
        span = TelemetrySpan(
            name=name,
            parent=parent,
            started_wall_ns=time.perf_counter_ns(),
            started_cpu_ns=time.process_time_ns(),
            attributes=dict(attributes),
        )
        self._stack.append(span)
        self._publish(name)
        try:
            yield span
        except BaseException as exc:
            span.attributes["error_type"] = type(exc).__name__
            raise
        finally:
            ended_cpu_ns = time.process_time_ns()
            ended_wall_ns = time.perf_counter_ns()
            popped = self._stack.pop()
            if popped is not span:
                raise AssertionError("telemetry span stack was corrupted")
            self._records.append(
                {
                    "name": span.name,
                    "parent": span.parent,
                    "start_offset_seconds": (
                        span.started_wall_ns - self._origin_wall_ns
                    )
                    / 1_000_000_000,
                    "wall_seconds": (ended_wall_ns - span.started_wall_ns)
                    / 1_000_000_000,
                    "cpu_seconds": (ended_cpu_ns - span.started_cpu_ns) / 1_000_000_000,
                    "attributes": dict(span.attributes),
                }
            )
            self._publish(self.active_stage)

    def progress(self, completed: int, total: int) -> None:
        if isinstance(completed, bool) or isinstance(total, bool):
            raise TypeError("telemetry progress values must be integers")
        if not 0 <= completed <= total:
            raise ValueError("telemetry progress must satisfy 0 <= completed <= total")
        self._publish(self.active_stage, completed, total)

    def record_aggregate_span(
        self,
        name: str,
        *,
        first_started_wall_ns: int,
        wall_ns: int,
        cpu_ns: int,
        occurrences: int,
        **attributes: object,
    ) -> None:
        """Record the total of repeated, disjoint work as one nested diagnostic span.

        Per-slot resolver operations are too numerous to retain as individual span records.  Their
        timers therefore accumulate in the caller and publish one explicitly labelled aggregate
        while the parent span is still active.  The aggregate preserves exact wall/CPU totals and
        call counts without flooding scale artifacts or changing the live-stage register.
        """
        if not name:
            raise ValueError("aggregate telemetry span name must not be empty")
        if min(first_started_wall_ns, wall_ns, cpu_ns, occurrences) < 0:
            raise ValueError("aggregate telemetry span values must be non-negative")
        if not self._enabled or occurrences == 0:
            return
        parent = self._stack[-1].name if self._stack else None
        self._records.append(
            {
                "name": name,
                "parent": parent,
                "start_offset_seconds": (
                    first_started_wall_ns - self._origin_wall_ns
                )
                / 1_000_000_000,
                "wall_seconds": wall_ns / 1_000_000_000,
                "cpu_seconds": cpu_ns / 1_000_000_000,
                "attributes": {
                    "aggregation": "disjoint-call-total",
                    "occurrences": occurrences,
                    **attributes,
                },
            }
        )

    def to_json(self) -> dict[str, object]:
        return {
            "schema": REBIN_TELEMETRY_SCHEMA,
            "active_stage": self.active_stage,
            "spans": [dict(record) for record in self._records],
        }

    def span_totals(self) -> Mapping[str, float]:
        """Return summed wall time by span name for compact diagnostic comparisons."""
        totals: dict[str, float] = {}
        for record in self._records:
            name = str(record["name"])
            totals[name] = totals.get(name, 0.0) + float(record["wall_seconds"])
        return totals


NULL_REBIND_TELEMETRY = RebindTelemetry(enabled=False)
