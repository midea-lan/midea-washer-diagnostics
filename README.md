# midea-washer-diagnostics

Read-only local LAN diagnostics for Midea and Little Swan DA washers.

A small Windows toolkit for discovering a Midea/Little Swan DA washer on the local network and viewing the status attributes it actually reports. It uses the open-source [`midea-local`](https://github.com/midea-lan/midea-local) package; attribution and license boundaries are in [ATTRIBUTION.md](ATTRIBUTION.md).

The monitor is read-only: it sends LAN discovery and status queries, exposes an HTTP page bound to `127.0.0.1`, and has no control endpoint. It does not start a washer, change settings, reset pairing, access cloud credentials, or flash firmware.

## Windows quick start

1. Install Python 3.12 with the Windows Python launcher (`py`).
2. Double-click `install.bat` once. It creates an isolated `.venv` and installs `midea-local` 15.x, which provides the async discovery API used by this toolkit.
3. Double-click `start_live_monitor.bat`. On first use, it discovers DA V1/V2 devices and asks you to select the washer. Device identifiers are written only to the ignored local file `discovery_round2_targeted.json`.
4. The browser opens `http://127.0.0.1:8765/`. Keep the console window open; press Ctrl+C there to stop.

At later launches, the tool rediscovers the selected device by its local device ID and updates its IP, so a DHCP address change does not require editing code. If more than one DA washer is present, the selection is only done at first setup.

## What the page shows

The page shows the DA attributes returned by the current library/device combination, raw program and water-level codes, raw response body, error code, and a rolling water-level-code chart. The target interval is one second; actual timing depends on the device reply and can be slower. A returned `wash_level` is a controller setting code, not measured water volume. The LAN status API does not expose capacitive-electrode state, analog pressure-sensor readings, or motor current.

## Optional multi-appliance overview

The washer dashboard above remains the detailed DA washer diagnostic. For a household overview, `initialize_home_devices.py` and `home_monitor.py` provide a separate generic page that can show multiple discovered device types for which the installed `midea-local` version has a registered parser. Select devices once; the monitor queries each device independently and renders only the attributes that its parser actually returns. The generic page has no device controls and listens on localhost only. Its CSV is long-form (`one row per device attribute`) and its JSONL stores one status snapshot per device sample.

On Windows, run `initialize_home_devices.py` from the project virtual environment once, then double-click `start_home_monitor.bat`. The overview polls every five seconds by default; this can be adjusted with `--interval`. This is a generic parser-backed view, not proof that every appliance type or protocol is compatible. Discovery does not supply cloud credentials: devices that require a token/key will report a connection/authentication failure, and the monitor does not attempt cloud login or credential bypass. Per-device raw protocol fields and specialized plots remain in the corresponding appliance-specific diagnostics.

The household overview has software-only regression coverage. It has not been exercised against a multi-appliance LAN or appliances requiring authentication.

For a file-based sampler, first initialize the same local device file, then run `run_diagnosis.py` with an allowed label such as `idle` or `wash_abnormal`. The sampler is also read-only. Run `plot_diagnosis.py` to render `water_level_trend.svg` from local CSV files. The chart includes only rows with valid timestamps and raw water-level codes; its stage title comes from recorded `progress` values when available.

## Privacy and safety

The repository intentionally contains no device IP, serial number, MAC address, discovery result, live CSV/JSONL, or raw device payload. Local discovery and status logs can contain device identifiers; do not publish those files. The `.gitignore` excludes them by default.

Do not operate the washer with an exposed control board, wiring, or removed protective cover. Disconnect mains power before handling the board or touch electrodes. The LAN page is not an electrical safety instrument and cannot prove that the appliance is safe to run.

## Case notes

See [CASE_STUDY_ZH.md](CASE_STUDY_ZH.md) for an anonymized, evidence-limited example.

## Developer checks

Run the focused standard-library regression tests with `python -m unittest discover -s tests -v`.
