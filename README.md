# Moon Phase Plugin

Display the current moon phase and illumination percentage.

![Moon Phase Display](./docs/board-display.png)

**→ [Setup Guide](./docs/SETUP.md)**

## Overview

The Moon Phase plugin computes lunar phases on the device with standard astronomical formulas (Jean Meeus, *Astronomical Algorithms*), so it needs no internet connection and no API key. It shows the current phase name (New Moon, Waxing Crescent, etc.), the percentage of the Moon that is illuminated, and the date of the next full moon.

## Template Variables

| Variable | Description | Example |
|---|---|---|
| `moon_phase.phase` | Current moon phase name | `Waxing Crescent` |
| `moon_phase.illumination` | Percentage of illumination (0-100) | `42.5` |
| `moon_phase.next_full_moon` | Date of next full moon (YYYY-MM-DD) | `2026-05-12` |

## Example Templates

```
MOON PHASE
{{moon_phase.phase}}
Illumination: {{moon_phase.illumination}}%
Next Full:
{{moon_phase.next_full_moon}}

```

## Configuration

| Setting | Name | Description | Required |
|---|---|---|---|
| `refresh_seconds` | Refresh Interval | How often to fetch data (seconds) | No |

## Features

- Current moon phase name
- Illumination percentage
- Next full moon date
- No API key or internet connection required

## Author

FiestaBoard Team
