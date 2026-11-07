"""Localhost-only, read-only multi-appliance Midea LAN status dashboard."""

import argparse
import asyncio
import csv
import json
import sys
import webbrowser
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from midealocal.const import ProtocolVersion
from midealocal.devices import device_selector

BASE = Path(__file__).resolve().parent
CSV_FIELDS = ("timestamp_utc", "device_id", "device_type", "model", "ip_address", "attribute", "value_json", "error")


def json_value(value: Any) -> Any:
    """Convert library attribute values into JSON-compatible values."""
    if hasattr(value, "value"):
        return value.value
    if isinstance(value, dict):
        return {str(key): json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_value(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def build_device(info: dict[str, Any]) -> Any:
    """Instantiate only a device parser registered by midea-local."""
    device = device_selector(
        name=str(info["device_id"]),
        device_id=int(info["device_id"]),
        device_type=int(info["type"]),
        ip_address=str(info["ip_address"]),
        port=int(info["port"]),
        token="",
        key="",
        device_protocol=ProtocolVersion(int(info["protocol"])),
        model=str(info.get("model", "")),
        subtype=int(info.get("subtype", 0)),
        mac=info.get("mac"),
        serial_number=info.get("sn"),
    )
    if device is None:
        raise ValueError(f"No midea-local parser for device type 0x{int(info['type']):02X}")
    return device


def page() -> bytes:
    return PAGE.encode("utf-8")


PAGE = r'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Midea 家庭设备只读监控</title>
<style>body{font:16px system-ui,"Microsoft YaHei",sans-serif;background:#f3f5f8;color:#17202a;margin:0;padding:20px}main{max-width:1200px;margin:auto}h1{font-size:22px}.note{color:#566573;font-size:14px}.device{background:white;border-radius:12px;padding:16px;margin:14px 0;box-shadow:0 1px 5px #0001}.head{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap}.badge{padding:5px 10px;border-radius:18px;background:#eee}.ok{background:#d9f5e6;color:#145a32}.bad{background:#fde2e2;color:#922b21}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:9px;margin-top:14px}.cell{background:#f7f8fa;padding:10px;border-radius:8px;overflow-wrap:anywhere}.key{font-size:12px;color:#65727e}.value{font-size:17px;font-weight:600;margin-top:4px;white-space:pre-wrap}</style>
<main><h1>Midea 家庭设备 · 局域网只读监控</h1><p class="note">仅显示 midea-local 实际解析并返回的属性。监控页不提供控制操作；不同设备可回报不同字段。</p><div id="list">等待设备状态…</div></main>
<script>
function text(tag,value,cls){const e=document.createElement(tag);if(cls)e.className=cls;e.textContent=value;return e}
function render(data){const root=document.getElementById('list');root.replaceChildren();for(const d of data.devices||[]){const card=text('section','','device'),head=text('div','','head'),title=text('strong',`${d.model||'未知型号'} · 类型 0x${Number(d.device_type).toString(16).toUpperCase()}`),badge=text('span',d.connected?'已连接':'未连接','badge '+(d.connected?'ok':'bad'));head.append(title,badge);card.append(head,text('div',`IP ${d.ip_address} · 上次采样 ${d.timestamp_utc||'尚无'}${d.error?' · '+d.error:''}`,'note'));const grid=text('div','','grid');for(const [key,value] of Object.entries(d.attributes||{})){const cell=text('div','','cell');cell.append(text('div',key,'key'),text('div',value===null?'null':typeof value==='object'?JSON.stringify(value):String(value),'value'));grid.append(cell)}if(!Object.keys(d.attributes||{}).length)grid.append(text('div',d.error||'尚未取得状态属性','note'));card.append(grid);root.append(card)}}
async function poll(){try{const response=await fetch('/api/status',{cache:'no-store'});render(await response.json())}catch{document.getElementById('list').textContent='本地监控服务暂不可用'}}poll();setInterval(poll,1000);
</script></html>'''


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device-file", type=Path, default=BASE / "home_devices.json")
    parser.add_argument("--host", default="127.0.0.1", help="Dashboard must remain localhost-only")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--interval", type=float, default=5.0)
    parser.add_argument("--duration-seconds", type=float)
    parser.add_argument("--open-browser", action="store_true")
    args = parser.parse_args()
    if args.host not in ("127.0.0.1", "localhost", "::1"):
        parser.error("For privacy, the dashboard may bind only to localhost")
    if args.interval < 1:
        parser.error("--interval must be at least 1 second")

    infos = json.loads(args.device_file.read_text(encoding="utf-8")).get("devices", [])
    if not infos:
        raise SystemExit("Device file has no selected devices. Run initialize_home_devices.py first.")
    entries = []
    for info in infos:
        device = build_device(info)
        entries.append({
            "device": device,
            "info": info,
            "state": {
                "device_id": str(info["device_id"]),
                "device_type": int(info["type"]),
                "model": str(info.get("model", "")),
                "ip_address": str(info["ip_address"]),
                "connected": False,
                "timestamp_utc": None,
                "attributes": {},
                "error": None,
            },
        })
    shared: dict[str, Any] = {"devices": [entry["state"] for entry in entries]}
    csv_stream = (BASE / "home_monitor.csv").open("a", newline="", encoding="utf-8-sig")
    jsonl_stream = (BASE / "home_monitor.jsonl").open("a", encoding="utf-8")
    csv_writer = csv.DictWriter(csv_stream, fieldnames=CSV_FIELDS)
    if csv_stream.tell() == 0:
        csv_writer.writeheader()

    async def sample(entry: dict[str, Any]) -> None:
        device, info, state = entry["device"], entry["info"], entry["state"]
        failures = 0
        connected = False
        started = asyncio.get_running_loop().time()
        try:
            while args.duration_seconds is None or asyncio.get_running_loop().time() - started < args.duration_seconds:
                try:
                    if not connected:
                        connected = await device.connect()
                        if not connected:
                            raise ConnectionError("local connection or authentication failed")
                    await device.refresh_status(check_protocol=True)
                    attributes = {str(key): json_value(value) for key, value in device.attributes.items()}
                    timestamp = datetime.now(timezone.utc).isoformat()
                    state.update(connected=True, timestamp_utc=timestamp, attributes=attributes, error=None)
                    record = {
                        "timestamp_utc": timestamp,
                        "device_id": str(info["device_id"]),
                        "device_type": int(info["type"]),
                        "model": str(info.get("model", "")),
                        "ip_address": str(info["ip_address"]),
                        "attributes": attributes,
                    }
                    jsonl_stream.write(json.dumps(record, ensure_ascii=False) + "\n")
                    for attribute, value in attributes.items():
                        csv_writer.writerow({
                            "timestamp_utc": timestamp,
                            "device_id": str(info["device_id"]),
                            "device_type": f"0x{int(info['type']):02X}",
                            "model": str(info.get("model", "")),
                            "ip_address": str(info["ip_address"]),
                            "attribute": attribute,
                            "value_json": json.dumps(value, ensure_ascii=False),
                            "error": "",
                        })
                    jsonl_stream.flush()
                    csv_stream.flush()
                    failures = 0
                except Exception as exc:  # bounded retry; exceptions never include credentials
                    failures += 1
                    connected = False
                    state.update(connected=False, error=type(exc).__name__)
                    if failures >= 3:
                        state["error"] = f"stopped after 3 failures ({type(exc).__name__})"
                        break
                    await device.close_socket()
                    await asyncio.sleep(min(10 * failures, 30))
                    continue
                await asyncio.sleep(args.interval)
        finally:
            await device.close_socket()

    async def serve(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            request = await asyncio.wait_for(reader.readline(), timeout=3)
            parts = request.decode("ascii", "replace").split()
            while await asyncio.wait_for(reader.readline(), timeout=3) not in (b"\r\n", b"\n", b""):
                pass
            if len(parts) < 2 or parts[0] != "GET":
                status, content_type, body = "405 Method Not Allowed", "text/plain; charset=utf-8", b"GET only"
            elif parts[1] == "/api/status":
                status, content_type = "200 OK", "application/json; charset=utf-8"
                body = json.dumps(shared, ensure_ascii=False).encode("utf-8")
            elif parts[1] == "/":
                status, content_type, body = "200 OK", "text/html; charset=utf-8", page()
            else:
                status, content_type, body = "404 Not Found", "text/plain; charset=utf-8", b"Not found"
            writer.write(f"HTTP/1.1 {status}\r\nContent-Type: {content_type}\r\nContent-Length: {len(body)}\r\nCache-Control: no-store\r\nConnection: close\r\n\r\n".encode("ascii") + body)
            await writer.drain()
        except (asyncio.TimeoutError, ConnectionError):
            pass
        finally:
            writer.close()
            await writer.wait_closed()

    server = await asyncio.start_server(serve, args.host, args.port)
    if args.open_browser:
        webbrowser.open(f"http://127.0.0.1:{args.port}/")
    print(f"Read-only multi-device monitor: http://127.0.0.1:{args.port}/", flush=True)
    try:
        async with server:
            await asyncio.gather(*(sample(entry) for entry in entries))
    finally:
        csv_stream.close()
        jsonl_stream.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Monitor stopped; no device control was sent.", file=sys.stderr)
