# Moon Phase Setup Guide

Display the current moon phase and illumination percentage.

## Overview

The Moon Phase plugin queries the US Naval Observatory API for lunar phase data. It shows the current phase name (New Moon, Waxing Crescent, etc.) and the percentage of the Moon that is illuminated. No API key is required.

- API reference: https://aa.usno.navy.mil/data/api

### Prerequisites

No API key or account required.

## Quick Setup

1. **Enable** — Go to **Integrations** in your FiestaBoard settings and enable **Moon Phase**.
2. **Configure** — Fill in the plugin settings (see Configuration Reference below).
3. **Template** — Add a page using the `moon_phase` plugin variables:
   ```
   {{{ moon_phase.status }}}
   ```
4. **View** — Navigate to your board page to see the live display.

## Template Variables

| Variable | Description | Example |
|---|---|---|
| `moon_phase.phase` | Current moon phase name | `Waxing Crescent` |
| `moon_phase.illumination` | Percentage of illumination (0-100) | `42.5` |
| `moon_phase.next_full_moon` | Date of next full moon (YYYY-MM-DD) | `2026-05-12` |

## Configuration Reference

| Setting | Name | Description | Default |
|---|---|---|---|
| `enabled` | Enabled |  | `False` |
| `refresh_seconds` | Refresh Interval (seconds) | How often to fetch moon phase data. | `3600` |

## Troubleshooting

- **No data** — verify the device can reach `aa.usno.navy.mil`.
- **Wrong phase** — the plugin uses the next upcoming phase from the API.

