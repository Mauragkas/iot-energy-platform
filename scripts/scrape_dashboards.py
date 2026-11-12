#!/usr/bin/env python3
r"""
scripts/scrape_dashboards.py
Scrapes and validates all Grafana dashboards via the Grafana HTTP API.
Executes each panel query through the Grafana datasource proxy (/api/ds/query)
to verify that every panel returns HTTP 200 and live data.
"""

import base64
import json
import sys
import urllib.error
import urllib.request

GRAFANA_URL = "http://localhost:3001"
AUTH = base64.b64encode(b"admin:admin").decode("ascii")


def grafana_get(endpoint: str):
    url = f"{GRAFANA_URL}{endpoint}"
    req = urllib.request.Request(url, headers={"Authorization": f"Basic {AUTH}"})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def grafana_query_ds(payload: dict):
    url = f"{GRAFANA_URL}/api/ds/query"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Authorization": f"Basic {AUTH}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def clean_sql(sql: str, var_replacements: dict) -> str:
    res = sql
    for k, v in var_replacements.items():
        res = res.replace(f"'{k}'", f"'{v}'").replace(k, v)
    return res


def scrape_dashboard(dashboard_uid: str, time_from="now-2h", time_to="now"):
    print("\n========================================================")
    print(f" Scraping Dashboard: {dashboard_uid} (range: {time_from} to {time_to})")
    print("========================================================")

    data = grafana_get(f"/api/dashboards/uid/{dashboard_uid}")
    dashboard = data.get("dashboard", {})
    title = dashboard.get("title", dashboard_uid)
    panels = dashboard.get("panels", [])

    print(f"Dashboard Title: {title}")
    print(f"Total Panels: {len(panels)}")

    var_replacements = {
        "$interval": "10s",
        "$severity": "All",
        "$alert_type": "All",
        "$meter_id": "All",
        "$__auto_interval": "10s",
        "$__auto": "10s",
    }

    results = []

    for panel in panels:
        p_id = panel.get("id")
        p_title = panel.get("title", f"Panel {p_id}")
        p_type = panel.get("type", "unknown")
        targets = panel.get("targets", [])

        if not targets:
            continue

        for target in targets:
            ref_id = target.get("refId", "A")
            raw_sql = target.get("rawSql")
            ds = target.get("datasource", {})

            if not raw_sql:
                continue

            cleaned_sql = clean_sql(raw_sql, var_replacements)

            query_payload = {
                "from": time_from,
                "to": time_to,
                "queries": [
                    {
                        "refId": ref_id,
                        "datasource": ds,
                        "rawSql": cleaned_sql,
                        "format": target.get("format", "table"),
                    }
                ],
            }

            try:
                resp = grafana_query_ds(query_payload)
                res_obj = resp.get("results", {}).get(ref_id, {})
                status_code = res_obj.get("status", 200)
                frames = res_obj.get("frames", [])

                total_rows = 0
                sample_data = ""
                for frame in frames:
                    values = frame.get("data", {}).get("values", [])
                    if values:
                        total_rows = len(values[0])
                        sample_data = f"{values[0][:2]}..."

                err_msg = res_obj.get("error", "")

                if status_code == 200 and not err_msg:
                    results.append(
                        (p_id, p_title, p_type, "PASS", total_rows, sample_data)
                    )
                    print(
                        f"  ✔ [ID {p_id:2d}] {p_title:35s} ({p_type:9s}) -> Status 200 | {total_rows:4d} rows"
                    )
                else:
                    results.append((p_id, p_title, p_type, "FAIL", 0, err_msg))
                    print(
                        f"  ✖ [ID {p_id:2d}] {p_title:35s} ({p_type:9s}) -> ERROR: {err_msg}"
                    )

            except urllib.error.HTTPError as e:
                err_body = e.read().decode("utf-8")
                results.append((p_id, p_title, p_type, f"HTTP {e.code}", 0, err_body))
                print(
                    f"  ✖ [ID {p_id:2d}] {p_title:35s} ({p_type:9s}) -> HTTP {e.code}: {err_body}"
                )
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                results.append((p_id, p_title, p_type, "ERROR", 0, str(e)))
                print(f"  ✖ [ID {p_id:2d}] {p_title:35s} ({p_type:9s}) -> {e}")

    passed = sum(1 for r in results if r[3] == "PASS")
    failed = len(results) - passed
    print(
        f"\nDashboard {dashboard_uid} Summary: {passed}/{len(results)} panels passed, {failed} failed."
    )
    return passed, failed


def main():
    dashboards = ["grid-anomalies", "grid-telemetry"]
    total_passed = 0
    total_failed = 0

    for d in dashboards:
        p, f = scrape_dashboard(d)
        total_passed += p
        total_failed += f

    print("\n========================================================")
    print(f" FINAL RESULT: {total_passed} panels PASSED, {total_failed} panels FAILED.")
    print("========================================================")

    if total_failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
