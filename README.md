# 🇦🇺 Australian ATIS for Home Assistant

A Home Assistant custom integration that provides live **ATIS information** for Australian civil and military airports using data from [Aussie ADS-B](http://aussieadsb.com).

## ✈️ Features
- Fetches current ATIS, METAR, and TAF data for selected airports.
- Supports **multiple airport selection** via the integration setup flow.
- Automatically creates sensors for:
  - ATIS Code
  - Approach
  - Arrival Runway
  - Departure Runway
  - Wind / Temperature / QNH / Weather
  - OPR Info
  - METAR & TAF

## 🧰 Installation (HACS)
1. Open HACS in Home Assistant.
2. Click **Custom Repositories** and add:

3. Select **Integration** category.
4. Search for and install **Australian ATIS**.
5. Restart Home Assistant.
6. Go to **Settings → Devices & Services → Add Integration → Australian ATIS** and select airports.

## 💡 Example Sensors
Each selected airport creates sensors such as:
- `sensor.ymml_atis`
- `sensor.ymml_atis_wind`
- `sensor.ymml_atis_temperature`

## 🗺 Supported Airports
Sydney (YSSY), Melbourne (YMML), Brisbane (YBBN), Perth (YPPH), Adelaide (YPAD),  
and many RAAF bases including Amberley, Tindal, and Richmond.

---

## 🔖 Version History
- **v1.0.0** – Initial release with multi-airport support.
