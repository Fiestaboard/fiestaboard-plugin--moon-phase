"""Display the current moon phase and illumination percentage."""

from __future__ import annotations

import datetime
import math
import logging
from typing import Any, Dict, List
import requests

from src.plugins.base import PluginBase, PluginResult

logger = logging.getLogger(__name__)

API_URL = "https://aa.usno.navy.mil/api/moon/phases/date"
USER_AGENT = "FiestaBoard Moon Phase Plugin (https://github.com/Fiestaboard/fiestaboard-plugin--moon-phase)"

# Phase name for the interval between two adjacent quarter events
_BETWEEN_PHASE = {
    ("New Moon", "First Quarter"): "Waxing Crescent",
    ("First Quarter", "Full Moon"): "Waxing Gibbous",
    ("Full Moon", "Last Quarter"): "Waning Gibbous",
    ("Last Quarter", "New Moon"): "Waning Crescent",
}


class MoonPhasePlugin(PluginBase):
    """Moon Phase plugin for FiestaBoard."""

    @property
    def plugin_id(self) -> str:
        return "moon_phase"

    def fetch_data(self) -> PluginResult:
        try:
            today = datetime.date.today()
            # Start 35 days ago: guarantees the last New Moon (cycle = 29.53 days)
            # is in the window so we can compute illumination accurately.
            # nump=7 covers ~52 additional days, always including the next Full Moon.
            start_date = today - datetime.timedelta(days=35)
            response = requests.get(
                API_URL,
                params={"date": start_date.strftime("%Y-%m-%d"), "nump": 7},
                headers={"User-Agent": USER_AGENT},
                timeout=10,
            )
            response.raise_for_status()
            d = response.json()

            phases = d.get("phasedata", [])

            def entry_date(e: dict) -> datetime.date:
                return datetime.date(int(e["year"]), int(e["month"]), int(e["day"]))

            past = [e for e in phases if entry_date(e) <= today]
            future = [e for e in phases if entry_date(e) > today]
            last_phase = past[-1] if past else None
            next_phase = future[0] if future else None

            # USNO reports dates in UT; a quarter event at 23:xx UT can land on
            # "yesterday" even though it's already that calendar day in the user's
            # local timezone. A ±1-day tolerance handles this without requiring
            # knowledge of the user's timezone.
            current_phase = "Unknown"
            if last_phase:
                last_name = last_phase.get("phase", "")
                days_since_last = (today - entry_date(last_phase)).days
                if days_since_last <= 1:
                    current_phase = last_name
                elif next_phase:
                    next_name = next_phase.get("phase", "")
                    current_phase = _BETWEEN_PHASE.get((last_name, next_name), "Unknown")

            # Cosine formula gives accurate illumination from days since last New Moon.
            last_new_moon = next(
                (entry_date(e) for e in reversed(past) if e.get("phase") == "New Moon"),
                None,
            )
            if last_new_moon:
                days_into_cycle = (today - last_new_moon).days
                illumination = round(
                    (1 - math.cos(2 * math.pi * days_into_cycle / 29.53059)) / 2 * 100
                )
            else:
                illumination = 0

            next_full = ""
            for entry in future:
                if entry.get("phase") == "Full Moon":
                    y, m, day = int(entry["year"]), int(entry["month"]), int(entry["day"])
                    next_full = f"{y}-{m:02d}-{day:02d}"
                    break

            return PluginResult(
                available=True,
                data={
                    "phase": current_phase,
                    "illumination": illumination,
                    "next_full_moon": next_full,
                },
            )
        except Exception as e:
            logger.exception("Error fetching moon phase")
            return PluginResult(available=False, error=str(e))

    def validate_config(self, config: Dict[str, Any]) -> List[str]:
        return []

    def cleanup(self) -> None:
        pass
