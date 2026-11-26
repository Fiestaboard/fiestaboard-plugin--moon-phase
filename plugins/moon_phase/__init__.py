"""Display the current moon phase and illumination percentage.

Everything is computed locally from Jean Meeus, *Astronomical Algorithms*
(2nd ed.): chapter 49 for the dates of the primary phases and chapter 48 for
the illuminated fraction. No network access is needed. The plugin used to call
the US Naval Observatory API, which made it fail whenever that server was slow
or blocked. The computed phase times agree with USNO's to within a few minutes.
"""

from __future__ import annotations

import datetime
import logging
import math
from typing import Any, Dict, List, Tuple

from src.plugins.base import PluginBase, PluginResult

logger = logging.getLogger(__name__)

SYNODIC_MONTH = 29.530588861

# Meeus chapter 49 gives Terrestrial Time; UT is about 69 s behind it in the
# 2020s. The difference only matters for an event within a minute of midnight.
_DELTA_T_DAYS = 69.0 / 86400.0

_PHASE_NAMES = {0.0: "New Moon", 0.25: "First Quarter", 0.5: "Full Moon", 0.75: "Last Quarter"}

# Phase name for the interval between two adjacent quarter events
_BETWEEN_PHASE = {
    ("New Moon", "First Quarter"): "Waxing Crescent",
    ("First Quarter", "Full Moon"): "Waxing Gibbous",
    ("Full Moon", "Last Quarter"): "Waning Gibbous",
    ("Last Quarter", "New Moon"): "Waning Crescent",
}

# (coefficient, power of E, multipliers of (M, M', F, Omega)) — Meeus 49
_NEW_MOON_TERMS = [
    (-0.40720, 0, (0, 1, 0, 0)), (0.17241, 1, (1, 0, 0, 0)),
    (0.01608, 0, (0, 2, 0, 0)), (0.01039, 0, (0, 0, 2, 0)),
    (0.00739, 1, (-1, 1, 0, 0)), (-0.00514, 1, (1, 1, 0, 0)),
    (0.00208, 2, (2, 0, 0, 0)), (-0.00111, 0, (0, 1, -2, 0)),
    (-0.00057, 0, (0, 1, 2, 0)), (0.00056, 1, (1, 2, 0, 0)),
    (-0.00042, 0, (0, 3, 0, 0)), (0.00042, 1, (1, 0, 2, 0)),
    (0.00038, 1, (1, 0, -2, 0)), (-0.00024, 1, (-1, 2, 0, 0)),
    (-0.00017, 0, (0, 0, 0, 1)), (-0.00007, 0, (2, 1, 0, 0)),
    (0.00004, 0, (0, 2, -2, 0)), (0.00004, 0, (3, 0, 0, 0)),
    (0.00003, 0, (1, 1, -2, 0)), (0.00003, 0, (0, 2, 2, 0)),
    (-0.00003, 0, (1, 1, 2, 0)), (0.00003, 0, (-1, 1, 2, 0)),
    (-0.00002, 0, (-1, 1, -2, 0)), (-0.00002, 0, (1, 3, 0, 0)),
    (0.00002, 0, (0, 4, 0, 0)),
]

_FULL_MOON_TERMS = [
    (-0.40614, 0, (0, 1, 0, 0)), (0.17302, 1, (1, 0, 0, 0)),
    (0.01614, 0, (0, 2, 0, 0)), (0.01043, 0, (0, 0, 2, 0)),
    (0.00734, 1, (-1, 1, 0, 0)), (-0.00515, 1, (1, 1, 0, 0)),
    (0.00209, 2, (2, 0, 0, 0)),
] + _NEW_MOON_TERMS[7:]

_QUARTER_TERMS = [
    (-0.62801, 0, (0, 1, 0, 0)), (0.17172, 1, (1, 0, 0, 0)),
    (-0.01183, 1, (1, 1, 0, 0)), (0.00862, 0, (0, 2, 0, 0)),
    (0.00804, 0, (0, 0, 2, 0)), (0.00454, 1, (-1, 1, 0, 0)),
    (0.00204, 2, (2, 0, 0, 0)), (-0.00180, 0, (0, 1, -2, 0)),
    (-0.00070, 0, (0, 1, 2, 0)), (-0.00040, 0, (0, 3, 0, 0)),
    (-0.00034, 1, (-1, 2, 0, 0)), (0.00032, 1, (1, 0, 2, 0)),
    (0.00032, 1, (1, 0, -2, 0)), (-0.00028, 2, (2, 1, 0, 0)),
    (0.00027, 1, (1, 2, 0, 0)), (-0.00017, 0, (0, 0, 0, 1)),
    (-0.00005, 0, (-1, 1, -2, 0)), (0.00004, 0, (0, 2, 2, 0)),
    (-0.00004, 0, (1, 1, 2, 0)), (0.00004, 0, (-2, 1, 0, 0)),
    (0.00003, 0, (1, 1, -2, 0)), (0.00003, 0, (3, 0, 0, 0)),
    (0.00002, 0, (0, 2, -2, 0)), (0.00002, 0, (-1, 1, 2, 0)),
    (-0.00002, 0, (1, 3, 0, 0)),
]

# Planetary arguments A1..A14: (constant, rate per lunation, amplitude)
_PLANETARY_TERMS = [
    (251.88, 0.016321, 0.000165), (251.83, 26.651886, 0.000164),
    (349.42, 36.412478, 0.000126), (84.66, 18.206239, 0.000110),
    (141.74, 53.303771, 0.000062), (207.14, 2.453732, 0.000060),
    (154.84, 7.306860, 0.000056), (34.52, 27.261239, 0.000047),
    (207.19, 0.121824, 0.000042), (291.34, 1.844379, 0.000040),
    (161.72, 24.198154, 0.000037), (239.56, 25.513099, 0.000035),
    (331.55, 3.592518, 0.000023),
]


def _sin_deg(x: float) -> float:
    return math.sin(math.radians(x))


def _cos_deg(x: float) -> float:
    return math.cos(math.radians(x))


def _phase_jde(k: float) -> float:
    """Julian Ephemeris Day of the phase with lunation number k (Meeus 49).

    Integer k is a New Moon; +0.25 First Quarter, +0.5 Full, +0.75 Last Quarter.
    """
    t = k / 1236.85
    jde = (2451550.09766 + SYNODIC_MONTH * k + 0.00015437 * t**2
           - 0.000000150 * t**3 + 0.00000000073 * t**4)
    e = 1 - 0.002516 * t - 0.0000074 * t**2
    m = 2.5534 + 29.10535670 * k - 0.0000014 * t**2 - 0.00000011 * t**3
    mp = (201.5643 + 385.81693528 * k + 0.0107582 * t**2 + 0.00001238 * t**3
          - 0.000000058 * t**4)
    f = (160.7108 + 390.67050284 * k - 0.0016118 * t**2 - 0.00000227 * t**3
         + 0.000000011 * t**4)
    omega = 124.7746 - 1.56375588 * k + 0.0020672 * t**2 + 0.00000215 * t**3

    fraction = round(k - math.floor(k), 2)
    terms = {0.0: _NEW_MOON_TERMS, 0.5: _FULL_MOON_TERMS}.get(fraction, _QUARTER_TERMS)
    for coeff, e_pow, (cm, cmp, cf, co) in terms:
        jde += coeff * e**e_pow * _sin_deg(cm * m + cmp * mp + cf * f + co * omega)

    if fraction in (0.25, 0.75):
        w = (0.00306 - 0.00038 * e * _cos_deg(m) + 0.00026 * _cos_deg(mp)
             - 0.00002 * _cos_deg(mp - m) + 0.00002 * _cos_deg(mp + m)
             + 0.00002 * _cos_deg(2 * f))
        jde += w if fraction == 0.25 else -w

    jde += 0.000325 * _sin_deg(299.77 + 0.107408 * k - 0.009173 * t**2)
    for const, rate, amp in _PLANETARY_TERMS:
        jde += amp * _sin_deg(const + rate * k)
    return jde


def _jd_to_datetime(jd: float) -> datetime.datetime:
    """Julian Day (UT) to an aware UTC datetime."""
    epoch = datetime.datetime(2000, 1, 1, 12, tzinfo=datetime.timezone.utc)  # JD 2451545.0
    return epoch + datetime.timedelta(days=jd - 2451545.0)


def _datetime_to_jd(moment: datetime.datetime) -> float:
    epoch = datetime.datetime(2000, 1, 1, 12, tzinfo=datetime.timezone.utc)
    return 2451545.0 + (moment - epoch).total_seconds() / 86400.0


def phase_events(start: datetime.date, end: datetime.date) -> List[Tuple[datetime.datetime, str]]:
    """Primary phases (UTC time, name) whose UT date falls in [start, end], in order."""
    k_start = math.floor((start.year + (start.timetuple().tm_yday - 1) / 365.25 - 2000) * 12.3685) - 1
    events = []
    k = float(k_start)
    while True:
        moment = _jd_to_datetime(_phase_jde(k) - _DELTA_T_DAYS)
        if moment.date() > end:
            break
        if moment.date() >= start:
            events.append((moment, _PHASE_NAMES[round(k - math.floor(k), 2)]))
        k += 0.25
    return events


def illumination_percent(moment: datetime.datetime) -> float:
    """Illuminated fraction of the Moon's disk at `moment`, in percent (Meeus 48)."""
    t = (_datetime_to_jd(moment) - 2451545.0) / 36525.0
    d = 297.8501921 + 445267.1114034 * t - 0.0018819 * t**2 + t**3 / 545868 - t**4 / 113065000
    m = 357.5291092 + 35999.0502909 * t - 0.0001536 * t**2 + t**3 / 24490000
    mp = 134.9633964 + 477198.8675055 * t + 0.0087414 * t**2 + t**3 / 69699 - t**4 / 14712000
    i = (180 - d - 6.289 * _sin_deg(mp) + 2.100 * _sin_deg(m) - 1.274 * _sin_deg(2 * d - mp)
         - 0.658 * _sin_deg(2 * d) - 0.214 * _sin_deg(2 * mp) - 0.110 * _sin_deg(d))
    return (1 + _cos_deg(i)) / 2 * 100


def _today() -> datetime.date:
    return datetime.date.today()


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


class MoonPhasePlugin(PluginBase):
    """Moon Phase plugin for FiestaBoard."""

    @property
    def plugin_id(self) -> str:
        return "moon_phase"

    def fetch_data(self) -> PluginResult:
        try:
            today = _today()
            # 35 days back and 60 ahead always bracket today and include the
            # next Full Moon (at most one synodic month, 29.5 days, away).
            events = phase_events(today - datetime.timedelta(days=35),
                                  today + datetime.timedelta(days=60))
            past = [(m, n) for m, n in events if m.date() <= today]
            future = [(m, n) for m, n in events if m.date() > today]

            # Event dates are UT; a quarter at 23:xx UT can land on "yesterday"
            # even though it's already that calendar day in the user's local
            # timezone. A ±1-day tolerance handles this without requiring
            # knowledge of the user's timezone.
            last_moment, last_name = past[-1]
            if (today - last_moment.date()).days <= 1:
                current_phase = last_name
            else:
                current_phase = _BETWEEN_PHASE[(last_name, future[0][1])]

            next_full = next(m for m, n in future if n == "Full Moon")

            return PluginResult(
                available=True,
                data={
                    "phase": current_phase,
                    "illumination": round(illumination_percent(_utcnow())),
                    "next_full_moon": next_full.strftime("%Y-%m-%d"),
                },
            )
        except Exception as e:
            logger.exception("Error computing moon phase")
            return PluginResult(available=False, error=str(e))

    def validate_config(self, config: Dict[str, Any]) -> List[str]:
        return []

    def cleanup(self) -> None:
        pass
