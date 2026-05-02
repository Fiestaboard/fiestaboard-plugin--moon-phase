"""Display the current moon phase and illumination percentage."""

from __future__ import annotations

import logging
from typing import Any, Dict, List
import requests

from src.plugins.base import PluginBase, PluginResult

logger = logging.getLogger(__name__)

API_URL = "https://aa.usno.navy.mil/api/moon/phases/date"
USER_AGENT = "FiestaBoard Moon Phase Plugin (https://github.com/Fiestaboard/fiestaboard-plugin--moon-phase)"


class MoonPhasePlugin(PluginBase):
    """Moon Phase plugin for FiestaBoard."""

    @property
    def plugin_id(self) -> str:
        return "moon_phase"

    def fetch_data(self) -> PluginResult:
        import datetime
        try:
            today = datetime.date.today()
            response = requests.get(
                API_URL,
                params={"date": today.strftime("%Y-%m-%d"), "nump": 4},
                headers={"User-Agent": USER_AGENT},
                timeout=10,
            )
            response.raise_for_status()
            d = response.json()

            phases = d.get("phasedata", [])
            # Find the most recently passed phase and next full moon
            # USNO returns a list of upcoming phase events
            phase_map = {
                "New Moon": "New Moon",
                "First Quarter": "First Quarter",
                "Full Moon": "Full Moon",
                "Last Quarter": "Last Quarter",
            }
            current_phase = "Unknown"
            next_full = ""
            for entry in phases:
                phase_name = entry.get("phase", "")
                if phase_name in phase_map and not next_full:
                    if phase_name == "Full Moon":
                        next_full = f"{entry.get('year', '')}-{entry.get('month', ''):02d}-{entry.get('day', ''):02d}"
            if phases:
                first = phases[0]
                current_phase = first.get("phase", "Unknown")

            # Approximate illumination from phase name
            illumination_map = {
                "New Moon": 0,
                "First Quarter": 50,
                "Full Moon": 100,
                "Last Quarter": 50,
                "Waxing Crescent": 25,
                "Waxing Gibbous": 75,
                "Waning Gibbous": 75,
                "Waning Crescent": 25,
            }
            illumination = illumination_map.get(current_phase, 0)

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
