"""Human-friendly scale and rounding helpers.

Used when a raw continuous step/size needs to be snapped to a "nice"
base-10 discrete value that reads clearly on axes, rulers, grids and
timelines. Decoupled from any single feature so every visualisation
(e.g. reference-grid spacing, chart ticks, callout rulers, survey
tolerances) shares the same snapping semantics.
"""

from __future__ import annotations

import math


class ScaleMath:
    """Scalar scale utilities shared across every numeric-visualisation feature."""

    @staticmethod
    def nice_step(raw: float) -> float:
        """Snap ``raw`` to the next "human-readable" step value in base-10.

        The standard (1, 2, 2.5, 5, 10) ladder is used so that every output
        divides evenly into multiples of 10^n for some integer ``n``,
        yielding clean tick labels like 0.5, 1, 2, 25, 500 etc.
        """
        if raw <= 0:
            return 1.0
        exponent = math.floor(math.log10(raw))
        fraction = raw / (10 ** exponent)
        for candidate in (1.0, 2.0, 2.5, 5.0, 10.0):
            if fraction <= candidate:
                return candidate * (10 ** exponent)
        return 10.0 * (10 ** exponent)
