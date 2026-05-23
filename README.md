# Mova Pet Feeder

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

Home Assistant integration for the **Mova PF10** (and compatible `mova.feeder.q2401`) automatic pet feeder, using the MOVAhome cloud API.

## Features

| Entity | Type | Description |
|--------|------|-------------|
| Feed now | Button | Trigger an immediate feeding |
| Portion size | Number | Set portions per feeding (1–50) |
| Schedule | Switch | Enable/disable scheduled feedings |
| Sound | Switch | Enable/disable feeding sound |
| Feedings today | Sensor | Number of feedings dispensed today |
| Portion size | Sensor | Current portion size (read-only mirror) |

## Requirements

- MOVAhome account with at least one feeder added
- Home Assistant 2024.6.0 or newer

## Installation

### Via HACS (recommended)

1. Open HACS → **Integrations** → ⋮ menu → **Custom repositories**
2. Add `https://github.com/iblur01/ha-mova-petfeeder` as type **Integration**
3. Install **Mova Pet Feeder** and restart Home Assistant

### Manual

Copy `custom_components/mova_petfeeder/` into your HA `custom_components/` directory and restart.

## Setup

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **Mova Pet Feeder**
3. Enter your MOVAhome app email, password, and server region

## Supported regions

| Region | Server |
|--------|--------|
| Europe | `eu` |
| North America | `us` |
| Asia | `cn` |

## Notes

- Data is polled from the Mova cloud every 60 seconds.
- The feeder must be online (connected to Wi-Fi) for actions (feed, property changes) to reach the device.
- Schedule content is stored on the device; this integration does not expose individual schedule entries — only the master schedule on/off switch.
