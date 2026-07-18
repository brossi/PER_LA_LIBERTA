"""S4.7 item-2 invariant harness (Component 0) — test-support code, never production.

Spec: engine/docs/s4_7_item2_invariants_plan.md §1. The drift generator's provenance relation
is the ground truth every invariant oracle reads; it must stay independent of the production
alignment layer (src/engine/structure/), so nothing in here may import from
engine.structure.rebind or the future #48 alignment modules.
"""
