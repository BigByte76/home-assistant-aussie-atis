# 🇦🇺 Australian ATIS for Home Assistant

Live **ATIS**, **METAR** and **TAF** for major Australian civil and military airports in Home Assistant. Data comes from [Aussie ADS-B](https://aussieadsb.com).

Each airport you pick becomes a device, and every part of its ATIS is a separate sensor: active runways, wind, QNH, temperature and so on. You can add them to dashboards, graph them, or use them in automations.

## ✈️ Features

- **One sensor per ATIS field**, for every airport you choose.
- **Arrival and departure runways are listed separately.** This includes parallel and split operations such as `34L AND R FOR ARRS AND DEPS` or `16 FOR ARR. RWY 27 FOR DEP`.
- **Wind is split into numbers:** direction, speed, gust, maximum crosswind and maximum tailwind, in knots.
- **The full ATIS text** is on the main sensor, along with which fields changed in the latest broadcast.
- **You can change airports at any time** from **Configure**, with no restart needed.
- **Each airport updates on its own.** If one airport can't be reached, the others keep working.
- Updates every 5 minutes.

<!-- ha-marketplace:exclude-start -->
## 🧰 Installation

Requires Home Assistant **2025.1** or newer.

### Marketplace (Home Assistant 2026.11 and newer)

[![Open your Home Assistant instance and open a repository in the Marketplace.](https://my.home-assistant.io/badges/marketplace_repository.svg)](https://my.home-assistant.io/redirect/marketplace_repository/?owner=BigByte76&repository=home-assistant-aussie-atis&category=integration)

1. Select the badge above. If the repository isn't listed yet, the Marketplace offers to add it as a custom repository.
2. Select **Install**. The integration is available straight away, with no restart needed.

### HACS (Home Assistant before 2026.11)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=BigByte76&repository=home-assistant-aussie-atis&category=integration)

1. Select the badge above, or in HACS open **⋮ → Custom repositories** and add `https://github.com/BigByte76/home-assistant-aussie-atis` with the category **Integration**.
2. Install **Australian ATIS**, then restart Home Assistant.

### Manual

1. Copy `custom_components/aussie_atis` into your Home Assistant `config/custom_components/` folder.
2. Restart Home Assistant.
<!-- ha-marketplace:exclude-end -->

## ⚙️ Setup

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=aussie_atis)

1. Select the badge above, or go to **Settings → Devices & Services → Add Integration**.
2. Search for **Australian ATIS**.
3. Select the airports you want.

To add or remove airports later, open the integration and choose **Configure**. When you remove an airport, its device and sensors are removed too.

## 💡 Sensors

Each airport creates a device named `<ICAO> ATIS`. For example, Melbourne (`YMML`) gives:

| Entity | Example state |
| --- | --- |
| `sensor.ymml_atis` | `P`, the current information letter |
| `sensor.ymml_atis_issued` | Time the ATIS was issued |
| `sensor.ymml_atis_approach` | `EXP GLS OR ILS APCH` |
| `sensor.ymml_atis_runway` | `16 FOR ARR. RWY 27 FOR DEP` |
| `sensor.ymml_atis_arrival_runways` | `16` |
| `sensor.ymml_atis_departure_runways` | `27` |
| `sensor.ymml_atis_surface_condition` | `SFC COND CODE 5, 5, 5. WHOLE RWY WET.` |
| `sensor.ymml_atis_operational_info` | `ABN UNSERVICEABLE AS PER NOTAM` |
| `sensor.ymml_atis_wind` | `170/10, MAX TW 5 KTS RWY 27, MAX XW 12 KTS RWY 27` |
| `sensor.ymml_atis_wind_direction` | `170` ° |
| `sensor.ymml_atis_wind_speed` | `10` kn |
| `sensor.ymml_atis_wind_gust` | gust speed in kn, when reported |
| `sensor.ymml_atis_max_crosswind` | `12` kn |
| `sensor.ymml_atis_max_tailwind` | `5` kn |
| `sensor.ymml_atis_visibility` | `GT 10KM` |
| `sensor.ymml_atis_weather` | `CAVOK` |
| `sensor.ymml_atis_cloud` | `FEW025` |
| `sensor.ymml_atis_temperature` | `12` °C |
| `sensor.ymml_atis_qnh` | `1022` hPa |
| `sensor.ymml_atis_significant_weather` | `TS IN AREA` |
| `sensor.ymml_atis_metar` | Latest METAR/SPECI |
| `sensor.ymml_atis_taf` | Latest TAF |

The main `sensor.ymml_atis` sensor has these attributes:

- `atis`: the complete ATIS broadcast text
- `changed_fields`: fields marked as changed since the previous information letter
- `other_info`: any extra lines, such as frequencies or "tower closed" notices

**Notes**

- Home Assistant limits a sensor's value to 255 characters. Longer text, such as most TAFs, is shortened, and the complete text is in the sensor's `full_text` attribute.
- If a field isn't in the current ATIS, its sensor shows `unknown`.

## 🖥️ Dashboard cards

There are two ready-made cards in the [`dashboards`](https://github.com/BigByte76/home-assistant-aussie-atis/tree/main/dashboards) folder. Both use Home Assistant's built-in Markdown card, so you don't need to install anything else.

To add one, open your dashboard and choose **Edit dashboard → Add card → Manual**, then paste in the card's YAML.

**[Airport card](https://github.com/BigByte76/home-assistant-aussie-atis/blob/main/dashboards/atis-airport-card.yaml)**

The full picture for one airport:
- information letter and how long ago it was issued
- arrival and departure runways
- approach, wind, visibility, weather, cloud, temperature and QNH
- operational info and significant weather
- METAR, plus the TAF in a section you can expand

Fields that changed in the latest broadcast are marked 🔸. To pick the airport, change `set icao = 'yssy'` on the first line of `content`.

```text
### ✈️ Sydney (YSSY)
## Information A
Issued 4 minutes ago

| 🛬 Arrivals   | 34L, 34R            |
| 🛫 Departures | 34L, 34R            |
| 💨 Wind       | 100/10 KTS,TW 5 KTS 🔸 |
| QNH           | 1016 hPa 🔸          |
…
```

**[Overview card](https://github.com/BigByte76/home-assistant-aussie-atis/blob/main/dashboards/atis-overview-card.yaml)**

A table with one row per airport you've selected: ATIS letter, arrival and departure runways, wind and QNH. Airports you add later appear in the table automatically.

### Example: a simple entities card

```yaml
type: entities
title: Sydney ATIS
entities:
  - entity: sensor.yssy_atis
  - entity: sensor.yssy_atis_arrival_runways
  - entity: sensor.yssy_atis_departure_runways
  - entity: sensor.yssy_atis_wind
  - entity: sensor.yssy_atis_qnh
```

### Example: notify when the ATIS changes

```yaml
automation:
  - alias: "Sydney ATIS changed"
    triggers:
      - trigger: state
        entity_id: sensor.yssy_atis
    conditions:
      - condition: template
        value_template: "{{ trigger.to_state.state not in ['unknown', 'unavailable'] }}"
    actions:
      - action: notify.notify
        data:
          message: >
            Sydney ATIS {{ states('sensor.yssy_atis') }}:
            ARR {{ states('sensor.yssy_atis_arrival_runways') }},
            DEP {{ states('sensor.yssy_atis_departure_runways') }}
```

## 🗺 Supported airports

**Capital cities:** Sydney (YSSY), Melbourne (YMML), Brisbane (YBBN), Perth (YPPH), Adelaide (YPAD), Canberra (YSCB), Hobart (YMHB), Darwin (YPDN)

**Regional:** Gold Coast (YBCG), Cairns (YBCS), Townsville (YBTL), Sunshine Coast (YBSU), Mackay (YBMK), Rockhampton (YBRK), Launceston (YMLT), Avalon (YMAV), Essendon (YMEN), Newcastle (YWLM), Alice Springs (YBAS), Karratha (YPKA), Port Hedland (YPPD), Learmonth (YPLM)

**Military:** Amberley (YAMB), Oakey (YBOK), Curtin (YCIN), Gingin (YGIG), East Sale (YMES), Point Cook (YMPC), Pearce (YPEA), Edinburgh (YPED), Tindal (YPTN), Woomera (YPWR), Scherger (YBSG), Nowra (YSNW), Richmond (YSRI)

Some regional and military airports only broadcast an ATIS while the tower is open. At other times their ATIS sensors show `unknown` or a "tower closed" message, but METAR and TAF keep updating.

## ❓ Troubleshooting

- **All of an airport's sensors are `unavailable`:** aussieadsb.com couldn't be reached for that airport. It retries every 5 minutes.
- **A field shows `unknown`:** that field isn't in the airport's current ATIS.
- **To see debug logs,** add this to `configuration.yaml`:

  ```yaml
  logger:
    logs:
      custom_components.aussie_atis: debug
  ```

<!-- ha-marketplace:exclude-start -->
## 🧪 Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements_test.txt
pytest
```

Development instructions for coding assistants are in [AGENTS.md](AGENTS.md).
<!-- ha-marketplace:exclude-end -->

## ⚠️ Disclaimer

This integration is for information and hobby use only. It is **not** an official source and must not be used for flight planning or navigation. Always get official ATIS and weather information from Airservices Australia or the Bureau of Meteorology.
