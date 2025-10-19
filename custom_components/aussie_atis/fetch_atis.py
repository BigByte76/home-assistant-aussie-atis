import re
import aiohttp
import logging
from datetime import datetime, timezone

_LOGGER = logging.getLogger(__name__)

BASE_URL = "http://aussieadsb.com/airportinfo/{code}"


async def fetch_atis(airport_code: str) -> str:
    """Fetch ATIS HTML from AussieADSB."""
    url = BASE_URL.format(code=airport_code.lower())
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                if resp.status == 200:
                    return await resp.text()
                _LOGGER.warning("ATIS fetch failed for %s (HTTP %s)", airport_code, resp.status)
    except Exception as err:
        _LOGGER.warning("Error fetching ATIS for %s: %s", airport_code, err)
    return None


def parse_atis(html: str) -> dict:
    """Parse AussieADSB ATIS HTML into structured data."""
    if not html:
        return {"error": "No data"}

    # ---- EXTRACT ATIS BLOCK ----
    atis_match = re.search(r"<h6>ATIS</h6>.*?<p class=\"monospace\">(.*?)</p>", html, re.DOTALL)
    atis_raw = atis_match.group(1).replace("&#xA;", "\n").strip() if atis_match else None
    atis_lines = [line.strip(" +") for line in atis_raw.splitlines()] if atis_raw else []

    # ---- ATIS CODE ----
    code_match = re.search(r"ATIS .* (\w)\s+", atis_raw or "")
    atis_code = code_match.group(1) if code_match else None

    # ---- APPROACH ----
    approach_match = re.search(r"APCH:\s*(.+)", atis_raw or "")
    approach = approach_match.group(1).strip() if approach_match else None

    # ---- RUNWAYS ----
    rwy_match = re.search(r"RWY:\s*(.+)", atis_raw or "")
    runway_line = rwy_match.group(1).strip() if rwy_match else None

    runway_arr = None
    runway_dep = None
    if runway_line:
        if re.fullmatch(r"\d{2}[A-Z]?", runway_line):  # Single runway
            runway_arr = runway_line
            runway_dep = runway_line
        else:
            runway_arr = runway_line

    # ---- OPR INFO ----
    opr_lines = []
    collect = False
    for line in atis_lines:
        if line.startswith("OPR INFO:"):
            text = line.replace("OPR INFO:", "").strip()
            if text:
                opr_lines.append(text)
            collect = True
            continue
        if collect:
            if any(line.startswith(k) for k in ["WND:", "WX:", "TMP:", "QNH:", "SIGWX:"]):
                collect = False
            else:
                opr_lines.append(line.strip())
    opr_info = " ".join(opr_lines) if opr_lines else None

    # ---- WIND ----
    wind_match = re.search(r"WND:\s*([\w/0-9., \-]+)", atis_raw or "")
    wind = wind_match.group(1).strip() if wind_match else None

    wind_dir = None
    wind_speed = None
    wind_gust = None
    wind_max_tw = None

    if wind:
        wind_base = re.search(r"(\d{3})/(\d+)(?:-(\d+))?", wind)
        if wind_base:
            wind_dir = wind_base.group(1)
            wind_speed = wind_base.group(2)
            wind_gust = wind_base.group(3)
        max_tw_match = re.search(r"MAX\s+(?:TW|XW)\s*(\d+)", wind)
        if max_tw_match:
            wind_max_tw = max_tw_match.group(1)

    # ---- WEATHER ----
    weather_match = re.search(r"WX:\s*(\S+)", atis_raw or "")
    weather = weather_match.group(1) if weather_match else None

    # ---- TEMPERATURE ----
    tmp_match = re.search(r"TMP:\s*(\d+)", atis_raw or "")
    temperature = tmp_match.group(1) if tmp_match else None

    # ---- QNH ----
    qnh_match = re.search(r"QNH:\s*(\d+)", atis_raw or "")
    qnh = qnh_match.group(1) if qnh_match else None

    # ---- SIGWX ----
    sigwx_match = re.search(r"SIGWX:\s*(.+)", atis_raw or "")
    sigwx = sigwx_match.group(1).strip() if sigwx_match else None

    # ---- METAR ----
    metar_match = re.search(r"<h6>METAR/SPECI</h6>.*?<p class=\"monospace\">(.*?)</p>", html, re.DOTALL)
    metar = metar_match.group(1).strip() if metar_match else None

    # ---- TAF ----
    taf_match = re.search(r"<h6>TAF</h6>.*?<p class=\"monospace\">(.*?)</p>", html, re.DOTALL)
    taf = taf_match.group(1).replace("&#xA;", "\n").strip() if taf_match else None

    # ---- BUILD OUTPUT ----
    return {
        "atis": atis_raw,
        "code": atis_code,
        "approach": approach,
        "runway_arr": runway_arr,
        "runway_dep": runway_dep,
        "opr_info": opr_info,
        "wind": wind,
        "wind_dir": wind_dir,
        "wind_speed": wind_speed,
        "wind_gust": wind_gust,
        "wind_max_tw": wind_max_tw,
        "weather": weather,
        "temperature": temperature,
        "qnh": qnh,
        "sigwx": sigwx,
        "metar": metar,
        "taf": taf,
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }
