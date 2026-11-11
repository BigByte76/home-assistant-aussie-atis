# AGENTS.md

Instructions for AI coding assistants working in this repository. `CLAUDE.md` is a symbolic link to this file, so every tool reads the same instructions.

## Overview

A Home Assistant custom integration (domain `aussie_atis`), distributed through the Home Assistant **Marketplace** (Home Assistant 2026.11 and newer) and HACS (older versions). Both use the same catalog and the same `hacs.json`. It scrapes `https://aussieadsb.com/airportinfo/{icao}` for ATIS, METAR and TAF data. Each selected airport becomes a device named `"{ICAO} ATIS"`, with one sensor per ATIS field, e.g. `sensor.yssy_atis` and `sensor.yssy_atis_wind_speed`.

The minimum Home Assistant version is 2025.1 (`homeassistant` in `hacs.json`). The test suite has been run against 2025.1.4 and 2026.2.3. Code relies on `entry.runtime_data`, the `type X = ConfigEntry[...]` alias, `DataUpdateCoordinator(config_entry=...)`, and `OptionsFlow.config_entry` without passing it in. Don't raise the minimum without updating `hacs.json`.

## Commands

```bash
pip install -r requirements_test.txt        # pytest-homeassistant-custom-component (pulls in homeassistant)
pytest                                      # all tests
pytest tests/test_atis_parser.py            # parser only
pytest tests/test_init.py -k options_flow   # a single test
ruff check custom_components tests && ruff format custom_components tests
```

CI (`.github/workflows/validate.yml`) runs on push, on pull requests and nightly. It runs hassfest, the HACS action (`category: integration`, with **no** `ignore`, because the catalog doesn't accept ignored checks), ruff and pytest.

## Architecture

- **`atis_parser.py`** does all the HTML and ATIS decoding and has **no Home Assistant imports**. This is deliberate. `tests/conftest.py` puts the package directory on `sys.path`, so the parser tests `import atis_parser` directly. Keep it free of Home Assistant imports.
  - The page has sections `<h6>ATIS|METAR/SPECI|TAF</h6>`, each followed by `<p class="monospace">`. The text is HTML-entity encoded (`&#xA;` for newlines, `&#x2B;` for `+`).
  - ATIS lines are `LABEL: value`. Labels differ by airport (`WND`/`WIND`, `WX`/`PRES WX`, `SFC COND`/`SURFACE COND`/…), and `_FIELD_ALIASES` maps them all to field names.
  - A line without a label continues the previous field. The exception is fields in `_SINGLE_LINE_FIELDS` (TMP, QNH): unlabelled lines after those, and labelled lines with an unknown label, go to `other_info`.
  - A leading `+` marks a field that changed since the last ATIS, and is recorded in `changed_fields`.
  - `parse_runways` splits the RWY field into clauses on `.`, `,` and `;`. It expands `34L AND R` and `34L/R` to `34L, 34R`. Each clause is tagged as arrival and/or departure by its ARR/DEP keywords, and a clause with neither keyword counts as both.
- **`coordinator.py`**: a single `DataUpdateCoordinator` for all airports. It fetches them concurrently through HA's shared aiohttp session. `data` is `{icao: AirportInfo}`. An airport whose fetch failed is left out of `data`, so only its entities go unavailable. `UpdateFailed` is raised only when every airport fails, which makes the first refresh raise `ConfigEntryNotReady`.
- **`__init__.py`**: the selection is read with `get_airports(entry)`, where options override data. Setup removes devices for deselected airports. An update listener reloads the entry when the options change.
- **`config_flow.py`**: the integration is single-instance (`single_config_entry` in the manifest). The user step and the options flow share one multi-select of `AIRPORTS` from `const.py`, so adding an airport is a one-line change in `const.py`. The config entry is `VERSION = 1`, with data `{"airports": [...]}`. Changing that shape needs `async_migrate_entry`.
- **`sensor.py`**: a tuple of `AtisSensorEntityDescription` with `value_fn`.
  - Unique IDs are `{ICAO}_{key}`. Changing a key breaks users' entities.
  - States longer than 255 characters are truncated. Descriptions with `long_text=True` also expose the untruncated text as a `full_text` attribute.
  - `atis` and `full_text` are in `_unrecorded_attributes`.
  - The main `atis` sensor uses `name=None`, so its translation must **not** have a `name`. Otherwise the entity ID becomes `sensor.x_atis_atis`.
- Entity names come from `translations/en.json` (`entity.sensor.<key>.name`) and icons from `icons.json`. Custom integrations don't use `strings.json`.

## Marketplace requirements

- **`manifest.json`**:
  - `version` is required. It must match the tag of the GitHub release it ships in. Releases must be *published*, not just tagged.
  - `issue_tracker`, `documentation`, `codeowners` and `name` are required by the catalog.
  - Keep `domain` and `name` first, with the other keys sorted alphabetically.
  - `requirements` stays empty: aiohttp ships with Home Assistant.
  - `categories` (`vehicles_transport.flights`, `weather_alerts`) must be valid values from the core category list. The HACS action fails on unknown ones.
- **`brand/icon.png`** (256×256) and **`brand/icon@2x.png`** (512×512) live inside the integration folder. They must not use Home Assistant branded images.
- **`hacs.json`** keys the Marketplace reads: `name`, `content_in_root`, `homeassistant`, `country`, `zip_release`, `filename`, `persistent_directory`, `hide_default_branch`, `hacs`. Others are ignored.
- **README**: sections wrapped in `<!-- ha-marketplace:exclude-start -->` … `<!-- ha-marketplace:exclude-end -->` show on GitHub but are hidden on the Marketplace page. This is used for install instructions and development notes.
- Everything the integration needs must be inside `custom_components/aussie_atis/`. Updates replace that folder.

## Working rules (Home Assistant AI policy)

- A human reviews and submits every change. Don't open issues or pull requests, push, publish releases, or post comments on GitHub unless the user explicitly asks in that conversation.
- Before saying something works, run `pytest` and ruff. Read the full diff before committing.
- Check lifecycle cases when you touch setup code: first install, unload and reload, options changes, deselected airports, an empty selection, and existing config entries from older versions.
- Check claims about Home Assistant or Marketplace behavior against the current docs at contributors.home-assistant.io or the code, not memory.

## Testing notes

- `tests/fixtures/*.html` are trimmed copies of real aussieadsb.com pages: just the h6 and monospace sections. They cover parallel runways (YSSY, YBBN), split runways (YMML, YMEN, YPAD), a tower-closed military ATIS (YAMB) and an airport with no ATIS (YBAS). When the site's format changes, capture a new page and trim it the same way.
- The integration tests mock HTTP with `aioclient_mock` against `BASE_URL`.
- To test an older Home Assistant, install `homeassistant==<version>` alongside `pytest-homeassistant-custom-component` in a separate venv. Pin `pycares<4.9` for 2025.x: newer pycares starts a background thread that the old harness reports as a lingering-thread error.
