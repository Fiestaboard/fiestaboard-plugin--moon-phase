"""Display the current moon phase and illumination percentage."""

from __future__ import annotations

import datetime
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

# Illumination (%) at each quarter-phase boundary
_QUARTER_ILLUMINATION = {
    "New Moon": 0,
    "First Quarter": 50,
    "Full Moon": 100,
    "Last Quarter": 50,
}


class MoonPhasePlugin(PluginBase):
    """Moon Phase plugin for FiestaBoard."""

    @property
    def plugin_id(self) -> str:
        return "moon_phase"

    def fetch_data(self) -> PluginResult:
        try:
            today = datetime.date.today()
            # Start 30 days ago so the window brackets today with past and future events
            start_date = today - datetime.timedelta(days=30)
            response = requests.get(
                API_URL,
                params={"date": start_date.strftime("%Y-%m-%d"), "nump": 6},
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

            current_phase = "Unknown"
            illumination = 0

            if last_phase:
                last_name = last_phase.get("phase", "")
                last_date = entry_date(last_phase)
                if last_date == today:
                    current_phase = last_name
                    illumination = _QUARTER_ILLUMINATION.get(last_name, 0)
                elif next_phase:
                    next_name = next_phase.get("phase", "")
                    next_date = entry_date(next_phase)
                    current_phase = _BETWEEN_PHASE.get((last_name, next_name), "Unknown")
                    days_total = (next_date - last_date).days
                    days_elapsed = (today - last_date).days
                    frac = days_elapsed / days_total if days_total else 0
                    illum_start = _QUARTER_ILLUMINATION.get(last_name, 0)
                    illum_end = _QUARTER_ILLUMINATION.get(next_name, 0)
                    illumination = round(illum_start + frac * (illum_end - illum_start))

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
