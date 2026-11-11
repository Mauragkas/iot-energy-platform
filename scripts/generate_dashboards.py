#!/usr/bin/env python3
"""
generate_dashboards.py
Generates the provisioned Grafana dashboards for Module F:
- grid_telemetry.json
- pipeline_system.json
- grid_anomalies.json
"""

import json
from pathlib import Path

OUT_DIR = Path("deploy/grafana/provisioning/dashboards/json")
OUT_DIR.mkdir(parents=True, exist_ok=True)

PG_DATASOURCE = {"type": "postgres", "uid": "timescaledb"}
PROM_DATASOURCE = {"type": "prometheus", "uid": "prometheus"}


# ==============================================================================
# Dashboard 1: Grid Telemetry (grid_telemetry.json)
# ==============================================================================
def make_grid_telemetry_dashboard():
    return {
        "annotations": {
            "list": [
                {
                    "builtIn": 1,
                    "datasource": {"type": "grafana", "uid": "-- Grafana --"},
                    "enable": True,
                    "hide": True,
                    "name": "Annotations & Alerts",
                    "type": "dashboard",
                }
            ]
        },
        "editable": True,
        "fiscalYearStartMonth": 0,
        "graphTooltip": 1,
        "id": None,
        "links": [],
        "liveNow": False,
        "refresh": "5s",
        "schemaVersion": 38,
        "style": "dark",
        "tags": ["iot", "grid", "telemetry", "timescaledb", "power-quality"],
        "templating": {
            "list": [
                {
                    "current": {"selected": True, "text": "All", "value": "All"},
                    "datasource": PG_DATASOURCE,
                    "definition": "SELECT DISTINCT meter_id FROM meter_readings ORDER BY 1;",
                    "hide": 0,
                    "includeAll": True,
                    "allValue": "All",
                    "label": "Meter ID",
                    "multi": False,
                    "name": "meter_id",
                    "options": [],
                    "query": "SELECT DISTINCT meter_id FROM meter_readings ORDER BY 1;",
                    "refresh": 1,
                    "regex": "",
                    "skipUrlSync": False,
                    "sort": 1,
                    "type": "query",
                },
                {
                    "auto": True,
                    "auto_count": 30,
                    "auto_min": "1s",
                    "current": {
                        "selected": True,
                        "text": "auto",
                        "value": "$__auto_interval",
                    },
                    "hide": 0,
                    "label": "Interval",
                    "name": "interval",
                    "options": [
                        {"selected": True, "text": "auto", "value": "$__auto_interval"},
                        {"selected": False, "text": "1s", "value": "1s"},
                        {"selected": False, "text": "5s", "value": "5s"},
                        {"selected": False, "text": "10s", "value": "10s"},
                        {"selected": False, "text": "30s", "value": "30s"},
                        {"selected": False, "text": "1m", "value": "1m"},
                        {"selected": False, "text": "5m", "value": "5m"},
                        {"selected": False, "text": "15m", "value": "15m"},
                        {"selected": False, "text": "1h", "value": "1h"},
                    ],
                    "query": "1s,5s,10s,30s,1m,5m,15m,1h",
                    "refresh": 2,
                    "type": "interval",
                },
            ]
        },
        "time": {"from": "now-15m", "to": "now"},
        "timepicker": {"refresh_intervals": ["1s", "5s", "10s", "30s", "1m", "5m"]},
        "timezone": "browser",
        "title": "Grid Telemetry & Power Quality",
        "uid": "grid-telemetry",
        "version": 1,
        "weekStart": "",
        "panels": [
            # Row 0: Fleet KPIs
            {
                "gridPos": {"h": 4, "w": 6, "x": 0, "y": 0},
                "id": 1,
                "title": "Active Reporting Meters",
                "type": "stat",
                "datasource": PG_DATASOURCE,
                "targets": [
                    {
                        "datasource": PG_DATASOURCE,
                        "editorMode": "code",
                        "format": "table",
                        "rawQuery": True,
                        "rawSql": 'SELECT NOW() AS "time", COUNT(DISTINCT meter_id) AS "Active Meters"\nFROM meter_readings\nWHERE time >= NOW() - INTERVAL \'5 minutes\';',
                        "refId": "A",
                    }
                ],
                "fieldConfig": {
                    "defaults": {
                        "color": {"mode": "thresholds"},
                        "mappings": [],
                        "thresholds": {
                            "mode": "absolute",
                            "steps": [
                                {"color": "red", "value": None},
                                {"color": "yellow", "value": 1},
                                {"color": "green", "value": 10},
                            ],
                        },
                        "unit": "none",
                    },
                    "overrides": [],
                },
                "options": {
                    "colorMode": "value",
                    "graphMode": "none",
                    "justifyMode": "auto",
                    "orientation": "auto",
                    "reduceOptions": {
                        "calcs": ["lastNotNull"],
                        "fields": "",
                        "values": False,
                    },
                    "textMode": "auto",
                },
            },
            {
                "gridPos": {"h": 4, "w": 6, "x": 6, "y": 0},
                "id": 2,
                "title": "Fleet Total Active Power",
                "type": "stat",
                "datasource": PG_DATASOURCE,
                "targets": [
                    {
                        "datasource": PG_DATASOURCE,
                        "editorMode": "code",
                        "format": "table",
                        "rawQuery": True,
                        "rawSql": 'SELECT NOW() AS "time", COALESCE(SUM(active_power_kw), 0) AS "Total Load"\nFROM (\n  SELECT DISTINCT ON (meter_id) active_power_kw\n  FROM meter_readings\n  WHERE time >= NOW() - INTERVAL \'5 minutes\'\n  ORDER BY meter_id, time DESC\n) latest;',
                        "refId": "A",
                    }
                ],
                "fieldConfig": {
                    "defaults": {
                        "color": {"mode": "palette-classic"},
                        "mappings": [],
                        "thresholds": {
                            "mode": "absolute",
                            "steps": [{"color": "blue", "value": None}],
                        },
                        "unit": "kw",
                    },
                    "overrides": [],
                },
                "options": {
                    "colorMode": "value",
                    "graphMode": "area",
                    "justifyMode": "auto",
                    "orientation": "auto",
                    "reduceOptions": {
                        "calcs": ["lastNotNull"],
                        "fields": "",
                        "values": False,
                    },
                    "textMode": "auto",
                },
            },
            {
                "gridPos": {"h": 4, "w": 6, "x": 12, "y": 0},
                "id": 3,
                "title": "Grid AC Frequency (Mean)",
                "type": "stat",
                "datasource": PG_DATASOURCE,
                "targets": [
                    {
                        "datasource": PG_DATASOURCE,
                        "editorMode": "code",
                        "format": "table",
                        "rawQuery": True,
                        "rawSql": 'SELECT NOW() AS "time", ROUND(AVG(frequency_hz)::numeric, 2) AS "Mean Frequency"\nFROM meter_readings\nWHERE time >= NOW() - INTERVAL \'5 minutes\';',
                        "refId": "A",
                    }
                ],
                "fieldConfig": {
                    "defaults": {
                        "color": {"mode": "thresholds"},
                        "mappings": [],
                        "thresholds": {
                            "mode": "absolute",
                            "steps": [
                                {"color": "red", "value": None},
                                {"color": "yellow", "value": 49.5},
                                {"color": "green", "value": 49.8},
                                {"color": "yellow", "value": 50.2},
                                {"color": "red", "value": 50.5},
                            ],
                        },
                        "unit": "hertz",
                    },
                    "overrides": [],
                },
                "options": {
                    "colorMode": "value",
                    "graphMode": "none",
                    "justifyMode": "auto",
                    "orientation": "auto",
                    "reduceOptions": {
                        "calcs": ["lastNotNull"],
                        "fields": "",
                        "values": False,
                    },
                    "textMode": "auto",
                },
            },
            {
                "gridPos": {"h": 4, "w": 6, "x": 18, "y": 0},
                "id": 4,
                "title": "Fleet Mean Power Factor",
                "type": "stat",
                "datasource": PG_DATASOURCE,
                "targets": [
                    {
                        "datasource": PG_DATASOURCE,
                        "editorMode": "code",
                        "format": "table",
                        "rawQuery": True,
                        "rawSql": 'SELECT NOW() AS "time", ROUND(AVG(power_factor)::numeric, 3) AS "Mean Power Factor"\nFROM meter_readings\nWHERE time >= NOW() - INTERVAL \'5 minutes\';',
                        "refId": "A",
                    }
                ],
                "fieldConfig": {
                    "defaults": {
                        "color": {"mode": "thresholds"},
                        "decimals": 3,
                        "mappings": [],
                        "max": 1,
                        "min": 0,
                        "thresholds": {
                            "mode": "absolute",
                            "steps": [
                                {"color": "red", "value": None},
                                {"color": "yellow", "value": 0.85},
                                {"color": "green", "value": 0.95},
                            ],
                        },
                        "unit": "none",
                    },
                    "overrides": [],
                },
                "options": {
                    "colorMode": "value",
                    "graphMode": "none",
                    "justifyMode": "auto",
                    "orientation": "auto",
                    "reduceOptions": {
                        "calcs": ["lastNotNull"],
                        "fields": "",
                        "values": False,
                    },
                    "textMode": "auto",
                },
            },
            # Row 1: Active Power Load Curves
            {
                "collapsed": False,
                "gridPos": {"h": 1, "w": 24, "x": 0, "y": 4},
                "id": 100,
                "title": "3-Phase Active Power (kW) Load Curves",
                "type": "row",
            },
            {
                "gridPos": {"h": 8, "w": 16, "x": 0, "y": 5},
                "id": 5,
                "title": "Active Power (kW) Load Curves by Meter",
                "description": "3-phase Active Power (kW) consumption curve over time retrieved from TimescaleDB hypertable.",
                "type": "timeseries",
                "datasource": PG_DATASOURCE,
                "targets": [
                    {
                        "datasource": PG_DATASOURCE,
                        "editorMode": "code",
                        "format": "time_series",
                        "rawQuery": True,
                        "rawSql": "SELECT\n  time_bucket('$interval', time) AS \"time\",\n  meter_id AS metric,\n  AVG(active_power_kw) AS \"Active Power (kW)\"\nFROM meter_readings\nWHERE\n  $__timeFilter(time)\n  AND ('$meter_id' = 'All' OR meter_id = '$meter_id')\nGROUP BY 1, 2\nORDER BY 1;",
                        "refId": "A",
                    }
                ],
                "fieldConfig": {
                    "defaults": {
                        "color": {"mode": "palette-classic"},
                        "custom": {
                            "axisCenteredZero": False,
                            "axisColorMode": "text",
                            "axisLabel": "Active Power (kW)",
                            "axisPlacement": "auto",
                            "drawStyle": "line",
                            "fillOpacity": 12,
                            "lineInterpolation": "smooth",
                            "lineWidth": 2,
                            "pointSize": 5,
                            "showPoints": "never",
                            "spanNulls": False,
                        },
                        "mappings": [],
                        "thresholds": {
                            "mode": "absolute",
                            "steps": [
                                {"color": "green", "value": None},
                                {"color": "yellow", "value": 5},
                                {"color": "red", "value": 15},
                            ],
                        },
                        "unit": "kw",
                    },
                    "overrides": [],
                },
                "options": {
                    "legend": {
                        "calcs": ["mean", "max", "last"],
                        "displayMode": "table",
                        "placement": "bottom",
                        "showLegend": True,
                    },
                    "tooltip": {"mode": "multi", "sort": "desc"},
                },
            },
            {
                "gridPos": {"h": 8, "w": 8, "x": 16, "y": 5},
                "id": 6,
                "title": "Aggregated Grid Load Curve (kW)",
                "description": "Total combined active real power across the grid fleet.",
                "type": "timeseries",
                "datasource": PG_DATASOURCE,
                "targets": [
                    {
                        "datasource": PG_DATASOURCE,
                        "editorMode": "code",
                        "format": "time_series",
                        "rawQuery": True,
                        "rawSql": 'SELECT\n  time_bucket(\'$interval\', time) AS "time",\n  SUM(active_power_kw) AS "Total Fleet Load (kW)"\nFROM meter_readings\nWHERE\n  $__timeFilter(time)\nGROUP BY 1\nORDER BY 1;',
                        "refId": "A",
                    }
                ],
                "fieldConfig": {
                    "defaults": {
                        "color": {"mode": "fixed", "fixedColor": "super-light-blue"},
                        "custom": {
                            "axisCenteredZero": False,
                            "axisColorMode": "text",
                            "axisLabel": "Fleet Power (kW)",
                            "axisPlacement": "auto",
                            "drawStyle": "line",
                            "fillOpacity": 25,
                            "gradientMode": "opacity",
                            "lineInterpolation": "smooth",
                            "lineWidth": 2,
                            "showPoints": "never",
                            "spanNulls": False,
                        },
                        "mappings": [],
                        "unit": "kw",
                    },
                    "overrides": [],
                },
                "options": {
                    "legend": {
                        "calcs": ["mean", "max", "last"],
                        "displayMode": "table",
                        "placement": "bottom",
                        "showLegend": True,
                    },
                    "tooltip": {"mode": "single", "sort": "none"},
                },
            },
            # Row 2: Voltage Stability Monitoring
            {
                "collapsed": False,
                "gridPos": {"h": 1, "w": 24, "x": 0, "y": 13},
                "id": 101,
                "title": "Voltage Stability Monitoring (EN 50160: 207V - 253V)",
                "type": "row",
            },
            {
                "gridPos": {"h": 8, "w": 16, "x": 0, "y": 14},
                "id": 7,
                "title": "3-Phase Voltage Monitoring (V_L1, V_L2, V_L3)",
                "description": "Phase voltages against EN 50160 standard limits: lower critical threshold at 207V (-10% nominal) and upper critical threshold at 253V (+10% nominal).",
                "type": "timeseries",
                "datasource": PG_DATASOURCE,
                "targets": [
                    {
                        "datasource": PG_DATASOURCE,
                        "editorMode": "code",
                        "format": "time_series",
                        "rawQuery": True,
                        "rawSql": "SELECT\n  time_bucket('$interval', time) AS \"time\",\n  AVG(voltage_l1) AS \"V_L1 (Phase 1)\",\n  AVG(voltage_l2) AS \"V_L2 (Phase 2)\",\n  AVG(voltage_l3) AS \"V_L3 (Phase 3)\"\nFROM meter_readings\nWHERE\n  $__timeFilter(time)\n  AND ('$meter_id' = 'All' OR meter_id = '$meter_id')\nGROUP BY 1\nORDER BY 1;",
                        "refId": "A",
                    }
                ],
                "fieldConfig": {
                    "defaults": {
                        "color": {"mode": "palette-classic"},
                        "custom": {
                            "axisCenteredZero": False,
                            "axisColorMode": "text",
                            "axisLabel": "Voltage (V)",
                            "axisPlacement": "auto",
                            "drawStyle": "line",
                            "fillOpacity": 5,
                            "lineInterpolation": "smooth",
                            "lineWidth": 2,
                            "showPoints": "never",
                            "spanNulls": False,
                            "thresholdsStyle": {"mode": "line"},
                        },
                        "mappings": [],
                        "max": 280,
                        "min": 180,
                        "thresholds": {
                            "mode": "absolute",
                            "steps": [
                                {"color": "red", "value": None},
                                {"color": "yellow", "value": 207},
                                {"color": "green", "value": 215},
                                {"color": "yellow", "value": 245},
                                {"color": "red", "value": 253},
                            ],
                        },
                        "unit": "volt",
                    },
                    "overrides": [
                        {
                            "matcher": {"id": "byName", "options": "V_L1 (Phase 1)"},
                            "properties": [
                                {
                                    "id": "color",
                                    "value": {"fixedColor": "#73BF69", "mode": "fixed"},
                                }
                            ],
                        },
                        {
                            "matcher": {"id": "byName", "options": "V_L2 (Phase 2)"},
                            "properties": [
                                {
                                    "id": "color",
                                    "value": {"fixedColor": "#FADE2A", "mode": "fixed"},
                                }
                            ],
                        },
                        {
                            "matcher": {"id": "byName", "options": "V_L3 (Phase 3)"},
                            "properties": [
                                {
                                    "id": "color",
                                    "value": {"fixedColor": "#5794F2", "mode": "fixed"},
                                }
                            ],
                        },
                    ],
                },
                "options": {
                    "legend": {
                        "calcs": ["min", "mean", "max", "last"],
                        "displayMode": "table",
                        "placement": "bottom",
                        "showLegend": True,
                    },
                    "tooltip": {"mode": "multi", "sort": "none"},
                },
            },
            {
                "gridPos": {"h": 8, "w": 8, "x": 16, "y": 14},
                "id": 8,
                "title": "Instantaneous Phase Voltage Status",
                "description": "Live gauge showing 3-phase voltages against 207V - 253V warning/critical boundaries.",
                "type": "gauge",
                "datasource": PG_DATASOURCE,
                "targets": [
                    {
                        "datasource": PG_DATASOURCE,
                        "editorMode": "code",
                        "format": "table",
                        "rawQuery": True,
                        "rawSql": "SELECT\n  ROUND(AVG(voltage_l1)::numeric, 1) AS \"V_L1\",\n  ROUND(AVG(voltage_l2)::numeric, 1) AS \"V_L2\",\n  ROUND(AVG(voltage_l3)::numeric, 1) AS \"V_L3\"\nFROM meter_readings\nWHERE\n  time >= NOW() - INTERVAL '2 minutes'\n  AND ('$meter_id' = 'All' OR meter_id = '$meter_id');",
                        "refId": "A",
                    }
                ],
                "fieldConfig": {
                    "defaults": {
                        "color": {"mode": "thresholds"},
                        "mappings": [],
                        "max": 270,
                        "min": 190,
                        "thresholds": {
                            "mode": "absolute",
                            "steps": [
                                {"color": "red", "value": None},
                                {"color": "yellow", "value": 207},
                                {"color": "green", "value": 215},
                                {"color": "yellow", "value": 245},
                                {"color": "red", "value": 253},
                            ],
                        },
                        "unit": "volt",
                    },
                    "overrides": [],
                },
                "options": {
                    "orientation": "auto",
                    "reduceOptions": {
                        "calcs": ["lastNotNull"],
                        "fields": "",
                        "values": False,
                    },
                    "showThresholdLabels": True,
                    "showThresholdMarkers": True,
                },
            },
            # Row 3: Current per Phase
            {
                "collapsed": False,
                "gridPos": {"h": 1, "w": 24, "x": 0, "y": 22},
                "id": 102,
                "title": "Current per Phase (I_L1, I_L2, I_L3)",
                "type": "row",
            },
            {
                "gridPos": {"h": 8, "w": 24, "x": 0, "y": 23},
                "id": 9,
                "title": "Phase Currents (I_L1, I_L2, I_L3)",
                "description": "Current flow per phase (Amperes) monitored to detect unbalanced loads across phases.",
                "type": "timeseries",
                "datasource": PG_DATASOURCE,
                "targets": [
                    {
                        "datasource": PG_DATASOURCE,
                        "editorMode": "code",
                        "format": "time_series",
                        "rawQuery": True,
                        "rawSql": "SELECT\n  time_bucket('$interval', time) AS \"time\",\n  AVG(current_l1) AS \"I_L1 (Phase 1)\",\n  AVG(current_l2) AS \"I_L2 (Phase 2)\",\n  AVG(current_l3) AS \"I_L3 (Phase 3)\"\nFROM meter_readings\nWHERE\n  $__timeFilter(time)\n  AND ('$meter_id' = 'All' OR meter_id = '$meter_id')\nGROUP BY 1\nORDER BY 1;",
                        "refId": "A",
                    }
                ],
                "fieldConfig": {
                    "defaults": {
                        "color": {"mode": "palette-classic"},
                        "custom": {
                            "axisCenteredZero": False,
                            "axisColorMode": "text",
                            "axisLabel": "Current (A)",
                            "axisPlacement": "auto",
                            "drawStyle": "line",
                            "fillOpacity": 10,
                            "lineInterpolation": "smooth",
                            "lineWidth": 2,
                            "showPoints": "never",
                            "spanNulls": False,
                        },
                        "mappings": [],
                        "unit": "amp",
                    },
                    "overrides": [],
                },
                "options": {
                    "legend": {
                        "calcs": ["min", "mean", "max", "last"],
                        "displayMode": "table",
                        "placement": "bottom",
                        "showLegend": True,
                    },
                    "tooltip": {"mode": "multi", "sort": "desc"},
                },
            },
            # Row 4: Power Factor Heatmap & Quality
            {
                "collapsed": False,
                "gridPos": {"h": 1, "w": 24, "x": 0, "y": 31},
                "id": 103,
                "title": "Power Factor Heatmap & Frequency Quality",
                "type": "row",
            },
            {
                "gridPos": {"h": 9, "w": 16, "x": 0, "y": 32},
                "id": 10,
                "title": "Power Factor Heatmap Across Meters",
                "description": "Heatmap distribution of power factor values across meters to identify inductive loads and reactive power penalties.",
                "type": "heatmap",
                "datasource": PG_DATASOURCE,
                "targets": [
                    {
                        "datasource": PG_DATASOURCE,
                        "editorMode": "code",
                        "format": "time_series",
                        "rawQuery": True,
                        "rawSql": "SELECT\n  time_bucket('$interval', time) AS \"time\",\n  meter_id AS metric,\n  AVG(power_factor) AS value\nFROM meter_readings\nWHERE\n  $__timeFilter(time)\n  AND ('$meter_id' = 'All' OR meter_id = '$meter_id')\nGROUP BY 1, 2\nORDER BY 1;",
                        "refId": "A",
                    }
                ],
                "fieldConfig": {
                    "defaults": {
                        "custom": {
                            "hideFrom": {
                                "legend": False,
                                "tooltip": False,
                                "viz": False,
                            }
                        }
                    },
                    "overrides": [],
                },
                "options": {
                    "calculate": False,
                    "color": {
                        "exponent": 0.5,
                        "fill": "dark-orange",
                        "mode": "scheme",
                        "reverse": False,
                        "scale": "exponential",
                        "scheme": "Spectral",
                    },
                    "exemplars": {"color": "rgba(255,0,255,0.7)"},
                    "filterValues": {"le": 1e-09},
                    "legend": {"show": True},
                    "rowsFrame": {"layout": "auto"},
                    "tooltip": {"show": True, "yHistogram": False},
                    "yAxis": {
                        "axisPlacement": "left",
                        "max": 1,
                        "min": 0.7,
                        "unit": "none",
                    },
                },
            },
            {
                "gridPos": {"h": 9, "w": 8, "x": 16, "y": 32},
                "id": 11,
                "title": "Mains Frequency Stability (Hz)",
                "description": "Grid frequency variation against 50 Hz nominal reference (EN 50160 ±1%).",
                "type": "timeseries",
                "datasource": PG_DATASOURCE,
                "targets": [
                    {
                        "datasource": PG_DATASOURCE,
                        "editorMode": "code",
                        "format": "time_series",
                        "rawQuery": True,
                        "rawSql": "SELECT\n  time_bucket('$interval', time) AS \"time\",\n  AVG(frequency_hz) AS \"Frequency (Hz)\"\nFROM meter_readings\nWHERE\n  $__timeFilter(time)\n  AND ('$meter_id' = 'All' OR meter_id = '$meter_id')\nGROUP BY 1\nORDER BY 1;",
                        "refId": "A",
                    }
                ],
                "fieldConfig": {
                    "defaults": {
                        "color": {"mode": "palette-classic"},
                        "custom": {
                            "axisCenteredZero": False,
                            "axisColorMode": "text",
                            "axisLabel": "Frequency (Hz)",
                            "axisPlacement": "auto",
                            "drawStyle": "line",
                            "fillOpacity": 10,
                            "lineInterpolation": "smooth",
                            "lineWidth": 2,
                            "showPoints": "never",
                            "spanNulls": False,
                            "thresholdsStyle": {"mode": "line"},
                        },
                        "mappings": [],
                        "max": 51,
                        "min": 49,
                        "thresholds": {
                            "mode": "absolute",
                            "steps": [
                                {"color": "red", "value": None},
                                {"color": "yellow", "value": 49.5},
                                {"color": "green", "value": 49.8},
                                {"color": "yellow", "value": 50.2},
                                {"color": "red", "value": 50.5},
                            ],
                        },
                        "unit": "hertz",
                    },
                    "overrides": [],
                },
                "options": {
                    "legend": {
                        "calcs": ["min", "mean", "max", "last"],
                        "displayMode": "table",
                        "placement": "bottom",
                        "showLegend": True,
                    },
                    "tooltip": {"mode": "single", "sort": "none"},
                },
            },
        ],
    }


# ==============================================================================
# Dashboard 2: Pipeline System (pipeline_system.json)
# ==============================================================================
def make_pipeline_system_dashboard():
    return {
        "annotations": {
            "list": [
                {
                    "builtIn": 1,
                    "datasource": {"type": "grafana", "uid": "-- Grafana --"},
                    "enable": True,
                    "hide": True,
                    "name": "Annotations & Alerts",
                    "type": "dashboard",
                }
            ]
        },
        "editable": True,
        "fiscalYearStartMonth": 0,
        "graphTooltip": 1,
        "id": None,
        "links": [],
        "liveNow": False,
        "refresh": "5s",
        "schemaVersion": 38,
        "style": "dark",
        "tags": ["iot", "pipeline", "prometheus", "kafka", "timescaledb", "system"],
        "templating": {
            "list": [
                {
                    "auto": True,
                    "auto_count": 30,
                    "auto_min": "1s",
                    "current": {
                        "selected": True,
                        "text": "auto",
                        "value": "$__auto_interval",
                    },
                    "hide": 0,
                    "label": "Interval",
                    "name": "interval",
                    "options": [
                        {"selected": True, "text": "auto", "value": "$__auto_interval"},
                        {"selected": False, "text": "1s", "value": "1s"},
                        {"selected": False, "text": "5s", "value": "5s"},
                        {"selected": False, "text": "10s", "value": "10s"},
                        {"selected": False, "text": "30s", "value": "30s"},
                        {"selected": False, "text": "1m", "value": "1m"},
                        {"selected": False, "text": "5m", "value": "5m"},
                    ],
                    "query": "1s,5s,10s,30s,1m,5m",
                    "refresh": 2,
                    "type": "interval",
                }
            ]
        },
        "time": {"from": "now-15m", "to": "now"},
        "timepicker": {"refresh_intervals": ["1s", "5s", "10s", "30s", "1m", "5m"]},
        "timezone": "browser",
        "title": "Pipeline & System Performance",
        "uid": "pipeline-system",
        "version": 1,
        "weekStart": "",
        "panels": [
            # Row 0: Pipeline KPIs
            {
                "gridPos": {"h": 4, "w": 5, "x": 0, "y": 0},
                "id": 1,
                "title": "MQTT Ingestion Rate",
                "type": "stat",
                "datasource": PROM_DATASOURCE,
                "targets": [
                    {
                        "datasource": PROM_DATASOURCE,
                        "editorMode": "code",
                        "expr": "sum(rate(telemetry_messages_received_total[1m])) or vector(0)",
                        "legendFormat": "Messages/sec",
                        "range": True,
                        "refId": "A",
                    }
                ],
                "fieldConfig": {
                    "defaults": {
                        "color": {"mode": "palette-classic"},
                        "mappings": [],
                        "thresholds": {
                            "mode": "absolute",
                            "steps": [{"color": "blue", "value": None}],
                        },
                        "unit": "reqps",
                    },
                    "overrides": [],
                },
                "options": {
                    "colorMode": "value",
                    "graphMode": "area",
                    "justifyMode": "auto",
                    "orientation": "auto",
                    "reduceOptions": {
                        "calcs": ["lastNotNull"],
                        "fields": "",
                        "values": False,
                    },
                    "textMode": "auto",
                },
            },
            {
                "gridPos": {"h": 4, "w": 5, "x": 5, "y": 0},
                "id": 2,
                "title": "Kafka Published Rate",
                "type": "stat",
                "datasource": PROM_DATASOURCE,
                "targets": [
                    {
                        "datasource": PROM_DATASOURCE,
                        "editorMode": "code",
                        "expr": "sum(rate(telemetry_messages_published_total[1m])) or vector(0)",
                        "legendFormat": "Published/sec",
                        "range": True,
                        "refId": "A",
                    }
                ],
                "fieldConfig": {
                    "defaults": {
                        "color": {"mode": "palette-classic"},
                        "mappings": [],
                        "thresholds": {
                            "mode": "absolute",
                            "steps": [{"color": "green", "value": None}],
                        },
                        "unit": "reqps",
                    },
                    "overrides": [],
                },
                "options": {
                    "colorMode": "value",
                    "graphMode": "area",
                    "justifyMode": "auto",
                    "orientation": "auto",
                    "reduceOptions": {
                        "calcs": ["lastNotNull"],
                        "fields": "",
                        "values": False,
                    },
                    "textMode": "auto",
                },
            },
            {
                "gridPos": {"h": 4, "w": 5, "x": 10, "y": 0},
                "id": 3,
                "title": "DB Persisted Throughput",
                "type": "stat",
                "datasource": PROM_DATASOURCE,
                "targets": [
                    {
                        "datasource": PROM_DATASOURCE,
                        "editorMode": "code",
                        "expr": "sum(rate(telemetry_persisted_records_total[1m])) or vector(0)",
                        "legendFormat": "Records/sec",
                        "range": True,
                        "refId": "A",
                    }
                ],
                "fieldConfig": {
                    "defaults": {
                        "color": {"mode": "palette-classic"},
                        "mappings": [],
                        "thresholds": {
                            "mode": "absolute",
                            "steps": [{"color": "purple", "value": None}],
                        },
                        "unit": "ops",
                    },
                    "overrides": [],
                },
                "options": {
                    "colorMode": "value",
                    "graphMode": "area",
                    "justifyMode": "auto",
                    "orientation": "auto",
                    "reduceOptions": {
                        "calcs": ["lastNotNull"],
                        "fields": "",
                        "values": False,
                    },
                    "textMode": "auto",
                },
            },
            {
                "gridPos": {"h": 4, "w": 4, "x": 15, "y": 0},
                "id": 4,
                "title": "Deduplication Ratio",
                "type": "stat",
                "datasource": PROM_DATASOURCE,
                "targets": [
                    {
                        "datasource": PROM_DATASOURCE,
                        "editorMode": "code",
                        "expr": "clamp_max((sum(rate(telemetry_messages_deduplicated_total[5m])) / clamp_min(sum(rate(telemetry_messages_received_total[5m])), 0.0001)) * 100, 100) or vector(0)",
                        "legendFormat": "Dedup %",
                        "range": True,
                        "refId": "A",
                    }
                ],
                "fieldConfig": {
                    "defaults": {
                        "color": {"mode": "thresholds"},
                        "decimals": 1,
                        "mappings": [],
                        "thresholds": {
                            "mode": "absolute",
                            "steps": [
                                {"color": "green", "value": None},
                                {"color": "yellow", "value": 15},
                                {"color": "red", "value": 40},
                            ],
                        },
                        "unit": "percent",
                    },
                    "overrides": [],
                },
                "options": {
                    "colorMode": "value",
                    "graphMode": "none",
                    "justifyMode": "auto",
                    "orientation": "auto",
                    "reduceOptions": {
                        "calcs": ["lastNotNull"],
                        "fields": "",
                        "values": False,
                    },
                    "textMode": "auto",
                },
            },
            {
                "gridPos": {"h": 4, "w": 5, "x": 19, "y": 0},
                "id": 5,
                "title": "Pipeline Services Health",
                "type": "stat",
                "datasource": PROM_DATASOURCE,
                "targets": [
                    {
                        "datasource": PROM_DATASOURCE,
                        "editorMode": "code",
                        "expr": 'sum(up{job=~"ingestor-rs|persister-rs|anomaly-worker-py|api-rs"}) or vector(0)',
                        "legendFormat": "Healthy Services",
                        "range": True,
                        "refId": "A",
                    }
                ],
                "fieldConfig": {
                    "defaults": {
                        "color": {"mode": "thresholds"},
                        "mappings": [],
                        "max": 4,
                        "min": 0,
                        "thresholds": {
                            "mode": "absolute",
                            "steps": [
                                {"color": "red", "value": None},
                                {"color": "yellow", "value": 2},
                                {"color": "green", "value": 4},
                            ],
                        },
                        "unit": "none",
                    },
                    "overrides": [],
                },
                "options": {
                    "colorMode": "value",
                    "graphMode": "none",
                    "justifyMode": "auto",
                    "orientation": "auto",
                    "reduceOptions": {
                        "calcs": ["lastNotNull"],
                        "fields": "",
                        "values": False,
                    },
                    "textMode": "auto",
                },
            },
            # Row 1: Ingestion & Deduplication
            {
                "collapsed": False,
                "gridPos": {"h": 1, "w": 24, "x": 0, "y": 4},
                "id": 100,
                "title": "Ingestion Throughput & Deduplication Metrics",
                "type": "row",
            },
            {
                "gridPos": {"h": 8, "w": 12, "x": 0, "y": 5},
                "id": 6,
                "title": "Ingestion Rate (MQTT messages/sec)",
                "description": "Per-second rate of incoming MQTT telemetry payloads processed by ingestor-rs.",
                "type": "timeseries",
                "datasource": PROM_DATASOURCE,
                "targets": [
                    {
                        "datasource": PROM_DATASOURCE,
                        "editorMode": "code",
                        "expr": "sum(rate(telemetry_messages_received_total[1m]))",
                        "legendFormat": "MQTT Received (msg/s)",
                        "range": True,
                        "refId": "A",
                    }
                ],
                "fieldConfig": {
                    "defaults": {
                        "color": {"mode": "fixed", "fixedColor": "light-blue"},
                        "custom": {
                            "axisCenteredZero": False,
                            "axisColorMode": "text",
                            "axisLabel": "Messages/sec",
                            "axisPlacement": "auto",
                            "drawStyle": "line",
                            "fillOpacity": 15,
                            "gradientMode": "opacity",
                            "lineInterpolation": "smooth",
                            "lineWidth": 2,
                            "showPoints": "never",
                            "spanNulls": False,
                        },
                        "mappings": [],
                        "unit": "reqps",
                    },
                    "overrides": [],
                },
                "options": {
                    "legend": {
                        "calcs": ["mean", "max", "last"],
                        "displayMode": "table",
                        "placement": "bottom",
                        "showLegend": True,
                    },
                    "tooltip": {"mode": "single", "sort": "none"},
                },
            },
            {
                "gridPos": {"h": 8, "w": 12, "x": 12, "y": 5},
                "id": 7,
                "title": "Ingestor Deduplication Hits vs Published Rate",
                "description": "Deduplication drops versus successful Kafka publications and rejected invalid messages.",
                "type": "timeseries",
                "datasource": PROM_DATASOURCE,
                "targets": [
                    {
                        "datasource": PROM_DATASOURCE,
                        "editorMode": "code",
                        "expr": "sum(rate(telemetry_messages_published_total[1m]))",
                        "legendFormat": "Published to Kafka (msg/s)",
                        "range": True,
                        "refId": "A",
                    },
                    {
                        "datasource": PROM_DATASOURCE,
                        "editorMode": "code",
                        "expr": "sum(rate(telemetry_messages_deduplicated_total[1m]))",
                        "legendFormat": "Deduplication Hits / Drops (msg/s)",
                        "range": True,
                        "refId": "B",
                    },
                    {
                        "datasource": PROM_DATASOURCE,
                        "editorMode": "code",
                        "expr": "sum(rate(telemetry_messages_rejected_total[1m]))",
                        "legendFormat": "Rejected Invalid Payloads (msg/s)",
                        "range": True,
                        "refId": "C",
                    },
                ],
                "fieldConfig": {
                    "defaults": {
                        "color": {"mode": "palette-classic"},
                        "custom": {
                            "axisCenteredZero": False,
                            "axisColorMode": "text",
                            "axisLabel": "Rate (msg/s)",
                            "axisPlacement": "auto",
                            "drawStyle": "line",
                            "fillOpacity": 10,
                            "lineInterpolation": "smooth",
                            "lineWidth": 2,
                            "showPoints": "never",
                            "spanNulls": False,
                        },
                        "mappings": [],
                        "unit": "reqps",
                    },
                    "overrides": [
                        {
                            "matcher": {
                                "id": "byName",
                                "options": "Published to Kafka (msg/s)",
                            },
                            "properties": [
                                {
                                    "id": "color",
                                    "value": {"fixedColor": "#73BF69", "mode": "fixed"},
                                }
                            ],
                        },
                        {
                            "matcher": {
                                "id": "byName",
                                "options": "Deduplication Hits / Drops (msg/s)",
                            },
                            "properties": [
                                {
                                    "id": "color",
                                    "value": {"fixedColor": "#FF9830", "mode": "fixed"},
                                }
                            ],
                        },
                        {
                            "matcher": {
                                "id": "byName",
                                "options": "Rejected Invalid Payloads (msg/s)",
                            },
                            "properties": [
                                {
                                    "id": "color",
                                    "value": {"fixedColor": "#F2495C", "mode": "fixed"},
                                }
                            ],
                        },
                    ],
                },
                "options": {
                    "legend": {
                        "calcs": ["mean", "max", "last"],
                        "displayMode": "table",
                        "placement": "bottom",
                        "showLegend": True,
                    },
                    "tooltip": {"mode": "multi", "sort": "desc"},
                },
            },
            # Row 2: Kafka Consumer Lag
            {
                "collapsed": False,
                "gridPos": {"h": 1, "w": 24, "x": 0, "y": 13},
                "id": 101,
                "title": "Kafka Consumer Lag & Pipeline Buffering",
                "type": "row",
            },
            {
                "gridPos": {"h": 8, "w": 24, "x": 0, "y": 14},
                "id": 8,
                "title": "Kafka Consumer Lag Across Consumer Groups",
                "description": "Offset lag between producer commit and consumer group offsets for persister and anomaly detection worker.",
                "type": "timeseries",
                "datasource": PROM_DATASOURCE,
                "targets": [
                    {
                        "datasource": PROM_DATASOURCE,
                        "editorMode": "code",
                        "expr": 'sum by (consumergroup) (kafka_consumergroup_lag{consumergroup=~"persister.*|anomaly.*"}) or (clamp_min(sum(telemetry_messages_published_total) - sum(telemetry_persisted_records_total), 0))',
                        "legendFormat": "Consumer Lag: {{consumergroup}}",
                        "range": True,
                        "refId": "A",
                    },
                    {
                        "datasource": PROM_DATASOURCE,
                        "editorMode": "code",
                        "expr": "clamp_min(sum(telemetry_messages_published_total) - sum(telemetry_persisted_records_total), 0)",
                        "legendFormat": "Pipeline Backpressure Lag (Published - Persisted)",
                        "range": True,
                        "refId": "B",
                    },
                ],
                "fieldConfig": {
                    "defaults": {
                        "color": {"mode": "palette-classic"},
                        "custom": {
                            "axisCenteredZero": False,
                            "axisColorMode": "text",
                            "axisLabel": "Unconsumed Messages",
                            "axisPlacement": "auto",
                            "drawStyle": "line",
                            "fillOpacity": 15,
                            "lineInterpolation": "smooth",
                            "lineWidth": 2,
                            "showPoints": "never",
                            "spanNulls": False,
                            "thresholdsStyle": {"mode": "line"},
                        },
                        "mappings": [],
                        "thresholds": {
                            "mode": "absolute",
                            "steps": [
                                {"color": "green", "value": None},
                                {"color": "yellow", "value": 500},
                                {"color": "red", "value": 2000},
                            ],
                        },
                        "unit": "short",
                    },
                    "overrides": [],
                },
                "options": {
                    "legend": {
                        "calcs": ["mean", "max", "last"],
                        "displayMode": "table",
                        "placement": "bottom",
                        "showLegend": True,
                    },
                    "tooltip": {"mode": "multi", "sort": "desc"},
                },
            },
            # Row 3: Persister Throughput & Batch Duration
            {
                "collapsed": False,
                "gridPos": {"h": 1, "w": 24, "x": 0, "y": 22},
                "id": 102,
                "title": "TimescaleDB Persister Throughput & Batch Insertion Latency",
                "type": "row",
            },
            {
                "gridPos": {"h": 8, "w": 12, "x": 0, "y": 23},
                "id": 9,
                "title": "DB Insertion Throughput (Records/sec & Batches/sec)",
                "description": "Rate of records successfully committed into TimescaleDB and batch execution frequency.",
                "type": "timeseries",
                "datasource": PROM_DATASOURCE,
                "targets": [
                    {
                        "datasource": PROM_DATASOURCE,
                        "editorMode": "code",
                        "expr": "sum(rate(telemetry_persisted_records_total[1m]))",
                        "legendFormat": "Persisted Records/sec",
                        "range": True,
                        "refId": "A",
                    },
                    {
                        "datasource": PROM_DATASOURCE,
                        "editorMode": "code",
                        "expr": "sum(rate(telemetry_persist_batches_total[1m]))",
                        "legendFormat": "Batches Inserted/sec",
                        "range": True,
                        "refId": "B",
                    },
                    {
                        "datasource": PROM_DATASOURCE,
                        "editorMode": "code",
                        "expr": "sum(rate(telemetry_persist_errors_total[1m]))",
                        "legendFormat": "Persist Errors/sec",
                        "range": True,
                        "refId": "C",
                    },
                ],
                "fieldConfig": {
                    "defaults": {
                        "color": {"mode": "palette-classic"},
                        "custom": {
                            "axisCenteredZero": False,
                            "axisColorMode": "text",
                            "axisLabel": "Throughput (ops)",
                            "axisPlacement": "auto",
                            "drawStyle": "line",
                            "fillOpacity": 12,
                            "lineInterpolation": "smooth",
                            "lineWidth": 2,
                            "showPoints": "never",
                            "spanNulls": False,
                        },
                        "mappings": [],
                        "unit": "ops",
                    },
                    "overrides": [
                        {
                            "matcher": {
                                "id": "byName",
                                "options": "Persist Errors/sec",
                            },
                            "properties": [
                                {
                                    "id": "color",
                                    "value": {"fixedColor": "#F2495C", "mode": "fixed"},
                                }
                            ],
                        }
                    ],
                },
                "options": {
                    "legend": {
                        "calcs": ["mean", "max", "last"],
                        "displayMode": "table",
                        "placement": "bottom",
                        "showLegend": True,
                    },
                    "tooltip": {"mode": "multi", "sort": "desc"},
                },
            },
            {
                "gridPos": {"h": 8, "w": 12, "x": 12, "y": 23},
                "id": 10,
                "title": "Persister Batch Duration & Latency",
                "description": "Batch execution duration in seconds for multi-row INSERT queries into TimescaleDB.",
                "type": "timeseries",
                "datasource": PROM_DATASOURCE,
                "targets": [
                    {
                        "datasource": PROM_DATASOURCE,
                        "editorMode": "code",
                        "expr": "histogram_quantile(0.99, sum(rate(telemetry_persist_batch_duration_seconds_bucket[1m])) by (le))",
                        "legendFormat": "p99 Batch Duration",
                        "range": True,
                        "refId": "A",
                    },
                    {
                        "datasource": PROM_DATASOURCE,
                        "editorMode": "code",
                        "expr": "histogram_quantile(0.95, sum(rate(telemetry_persist_batch_duration_seconds_bucket[1m])) by (le))",
                        "legendFormat": "p95 Batch Duration",
                        "range": True,
                        "refId": "B",
                    },
                    {
                        "datasource": PROM_DATASOURCE,
                        "editorMode": "code",
                        "expr": "sum(rate(telemetry_persist_batch_duration_seconds_sum[1m])) / sum(rate(telemetry_persist_batch_duration_seconds_count[1m]))",
                        "legendFormat": "Avg Batch Duration",
                        "range": True,
                        "refId": "C",
                    },
                ],
                "fieldConfig": {
                    "defaults": {
                        "color": {"mode": "palette-classic"},
                        "custom": {
                            "axisCenteredZero": False,
                            "axisColorMode": "text",
                            "axisLabel": "Duration (seconds)",
                            "axisPlacement": "auto",
                            "drawStyle": "line",
                            "fillOpacity": 8,
                            "lineInterpolation": "smooth",
                            "lineWidth": 2,
                            "showPoints": "never",
                            "spanNulls": False,
                            "thresholdsStyle": {"mode": "line"},
                        },
                        "mappings": [],
                        "thresholds": {
                            "mode": "absolute",
                            "steps": [
                                {"color": "green", "value": None},
                                {"color": "yellow", "value": 0.25},
                                {"color": "red", "value": 1.0},
                            ],
                        },
                        "unit": "s",
                    },
                    "overrides": [],
                },
                "options": {
                    "legend": {
                        "calcs": ["mean", "max", "last"],
                        "displayMode": "table",
                        "placement": "bottom",
                        "showLegend": True,
                    },
                    "tooltip": {"mode": "multi", "sort": "desc"},
                },
            },
            # Row 4: API Request Latency Histogram
            {
                "collapsed": False,
                "gridPos": {"h": 1, "w": 24, "x": 0, "y": 31},
                "id": 103,
                "title": "API Request Latency & Throughput",
                "type": "row",
            },
            {
                "gridPos": {"h": 8, "w": 14, "x": 0, "y": 32},
                "id": 11,
                "title": "API p95 & p99 Request Latency Histogram",
                "description": "Actix-web REST API request latency percentiles (p50, p95, p99) computed from Prometheus duration histogram.",
                "type": "timeseries",
                "datasource": PROM_DATASOURCE,
                "targets": [
                    {
                        "datasource": PROM_DATASOURCE,
                        "editorMode": "code",
                        "expr": 'histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket{job="api-rs"}[1m])) by (le)) or histogram_quantile(0.99, sum(rate(actix_http_request_duration_seconds_bucket[1m])) by (le)) or histogram_quantile(0.99, sum(rate(api_request_duration_seconds_bucket[1m])) by (le))',
                        "legendFormat": "p99 Latency",
                        "range": True,
                        "refId": "A",
                    },
                    {
                        "datasource": PROM_DATASOURCE,
                        "editorMode": "code",
                        "expr": 'histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket{job="api-rs"}[1m])) by (le)) or histogram_quantile(0.95, sum(rate(actix_http_request_duration_seconds_bucket[1m])) by (le)) or histogram_quantile(0.95, sum(rate(api_request_duration_seconds_bucket[1m])) by (le))',
                        "legendFormat": "p95 Latency",
                        "range": True,
                        "refId": "B",
                    },
                    {
                        "datasource": PROM_DATASOURCE,
                        "editorMode": "code",
                        "expr": 'histogram_quantile(0.50, sum(rate(http_request_duration_seconds_bucket{job="api-rs"}[1m])) by (le)) or histogram_quantile(0.50, sum(rate(actix_http_request_duration_seconds_bucket[1m])) by (le)) or histogram_quantile(0.50, sum(rate(api_request_duration_seconds_bucket[1m])) by (le))',
                        "legendFormat": "p50 (Median) Latency",
                        "range": True,
                        "refId": "C",
                    },
                ],
                "fieldConfig": {
                    "defaults": {
                        "color": {"mode": "palette-classic"},
                        "custom": {
                            "axisCenteredZero": False,
                            "axisColorMode": "text",
                            "axisLabel": "Latency (s)",
                            "axisPlacement": "auto",
                            "drawStyle": "line",
                            "fillOpacity": 8,
                            "lineInterpolation": "smooth",
                            "lineWidth": 2,
                            "showPoints": "never",
                            "spanNulls": False,
                            "thresholdsStyle": {"mode": "line"},
                        },
                        "mappings": [],
                        "thresholds": {
                            "mode": "absolute",
                            "steps": [
                                {"color": "green", "value": None},
                                {"color": "yellow", "value": 0.05},
                                {"color": "red", "value": 0.20},
                            ],
                        },
                        "unit": "s",
                    },
                    "overrides": [
                        {
                            "matcher": {"id": "byName", "options": "p99 Latency"},
                            "properties": [
                                {
                                    "id": "color",
                                    "value": {"fixedColor": "#F2495C", "mode": "fixed"},
                                }
                            ],
                        },
                        {
                            "matcher": {"id": "byName", "options": "p95 Latency"},
                            "properties": [
                                {
                                    "id": "color",
                                    "value": {"fixedColor": "#FF9830", "mode": "fixed"},
                                }
                            ],
                        },
                        {
                            "matcher": {
                                "id": "byName",
                                "options": "p50 (Median) Latency",
                            },
                            "properties": [
                                {
                                    "id": "color",
                                    "value": {"fixedColor": "#73BF69", "mode": "fixed"},
                                }
                            ],
                        },
                    ],
                },
                "options": {
                    "legend": {
                        "calcs": ["mean", "max", "last"],
                        "displayMode": "table",
                        "placement": "bottom",
                        "showLegend": True,
                    },
                    "tooltip": {"mode": "multi", "sort": "desc"},
                },
            },
            {
                "gridPos": {"h": 8, "w": 10, "x": 14, "y": 32},
                "id": 12,
                "title": "API Request Throughput by Status",
                "description": "Incoming HTTP request traffic by response status code class (2xx, 4xx, 5xx).",
                "type": "timeseries",
                "datasource": PROM_DATASOURCE,
                "targets": [
                    {
                        "datasource": PROM_DATASOURCE,
                        "editorMode": "code",
                        "expr": 'sum by (status) (rate(http_requests_total{job="api-rs"}[1m])) or sum by (status) (rate(actix_http_requests_total[1m])) or sum by (status) (rate(api_requests_total[1m]))',
                        "legendFormat": "HTTP {{status}}",
                        "range": True,
                        "refId": "A",
                    }
                ],
                "fieldConfig": {
                    "defaults": {
                        "color": {"mode": "palette-classic"},
                        "custom": {
                            "axisCenteredZero": False,
                            "axisColorMode": "text",
                            "axisLabel": "Requests/sec",
                            "axisPlacement": "auto",
                            "drawStyle": "bars",
                            "fillOpacity": 60,
                            "lineWidth": 1,
                            "showPoints": "never",
                            "stacking": {"group": "A", "mode": "normal"},
                        },
                        "mappings": [],
                        "unit": "reqps",
                    },
                    "overrides": [],
                },
                "options": {
                    "legend": {
                        "calcs": ["mean", "max", "last"],
                        "displayMode": "table",
                        "placement": "bottom",
                        "showLegend": True,
                    },
                    "tooltip": {"mode": "multi", "sort": "desc"},
                },
            },
        ],
    }


# ==============================================================================
# Dashboard 3: Grid Anomalies (grid_anomalies.json)
# ==============================================================================
def make_grid_anomalies_dashboard():
    return {
        "annotations": {
            "list": [
                {
                    "builtIn": 1,
                    "datasource": {"type": "grafana", "uid": "-- Grafana --"},
                    "enable": True,
                    "hide": True,
                    "name": "Annotations & Alerts",
                    "type": "dashboard",
                }
            ]
        },
        "editable": True,
        "fiscalYearStartMonth": 0,
        "graphTooltip": 1,
        "id": None,
        "links": [],
        "liveNow": False,
        "refresh": "5s",
        "schemaVersion": 38,
        "style": "dark",
        "tags": ["iot", "grid", "anomalies", "alerts", "timescaledb", "safety"],
        "templating": {
            "list": [
                {
                    "current": {"selected": True, "text": "All", "value": "All"},
                    "hide": 0,
                    "label": "Severity",
                    "name": "severity",
                    "options": [
                        {"selected": True, "text": "All", "value": "All"},
                        {"selected": False, "text": "CRITICAL", "value": "CRITICAL"},
                        {"selected": False, "text": "WARNING", "value": "WARNING"},
                        {"selected": False, "text": "INFO", "value": "INFO"},
                    ],
                    "query": "All,CRITICAL,WARNING,INFO",
                    "type": "custom",
                },
                {
                    "current": {"selected": True, "text": "All", "value": "All"},
                    "hide": 0,
                    "label": "Anomaly Type",
                    "name": "alert_type",
                    "options": [
                        {"selected": True, "text": "All", "value": "All"},
                        {
                            "selected": False,
                            "text": "VOLTAGE_SAG",
                            "value": "VOLTAGE_SAG",
                        },
                        {
                            "selected": False,
                            "text": "VOLTAGE_SWELL",
                            "value": "VOLTAGE_SWELL",
                        },
                        {
                            "selected": False,
                            "text": "DEMAND_SPIKE",
                            "value": "DEMAND_SPIKE",
                        },
                        {
                            "selected": False,
                            "text": "PHASE_IMBALANCE",
                            "value": "PHASE_IMBALANCE",
                        },
                        {
                            "selected": False,
                            "text": "LOW_POWER_FACTOR",
                            "value": "LOW_POWER_FACTOR",
                        },
                        {
                            "selected": False,
                            "text": "FREQUENCY_DEVIATION",
                            "value": "FREQUENCY_DEVIATION",
                        },
                    ],
                    "query": "All,VOLTAGE_SAG,VOLTAGE_SWELL,DEMAND_SPIKE,PHASE_IMBALANCE,LOW_POWER_FACTOR,FREQUENCY_DEVIATION",
                    "type": "custom",
                },
                {
                    "current": {"selected": True, "text": "All", "value": "All"},
                    "datasource": PG_DATASOURCE,
                    "definition": "SELECT DISTINCT meter_id FROM meter_alerts ORDER BY 1;",
                    "hide": 0,
                    "includeAll": True,
                    "allValue": "All",
                    "label": "Meter ID",
                    "multi": False,
                    "name": "meter_id",
                    "options": [],
                    "query": "SELECT DISTINCT meter_id FROM meter_alerts ORDER BY 1;",
                    "refresh": 1,
                    "type": "query",
                },
                {
                    "auto": True,
                    "auto_count": 30,
                    "auto_min": "5s",
                    "current": {
                        "selected": True,
                        "text": "auto",
                        "value": "$__auto_interval",
                    },
                    "hide": 0,
                    "label": "Interval",
                    "name": "interval",
                    "options": [
                        {"selected": True, "text": "auto", "value": "$__auto_interval"},
                        {"selected": False, "text": "5s", "value": "5s"},
                        {"selected": False, "text": "10s", "value": "10s"},
                        {"selected": False, "text": "30s", "value": "30s"},
                        {"selected": False, "text": "1m", "value": "1m"},
                        {"selected": False, "text": "5m", "value": "5m"},
                    ],
                    "query": "5s,10s,30s,1m,5m",
                    "refresh": 2,
                    "type": "interval",
                },
            ]
        },
        "time": {"from": "now-30m", "to": "now"},
        "timepicker": {"refresh_intervals": ["1s", "5s", "10s", "30s", "1m", "5m"]},
        "timezone": "browser",
        "title": "Grid Anomalies & Power Quality Alerts",
        "uid": "grid-anomalies",
        "version": 1,
        "weekStart": "",
        "panels": [
            # Row 0: Real-Time Alert Counts by Severity
            {
                "gridPos": {"h": 4, "w": 5, "x": 0, "y": 0},
                "id": 1,
                "title": "CRITICAL Alerts",
                "type": "stat",
                "datasource": PG_DATASOURCE,
                "targets": [
                    {
                        "datasource": PG_DATASOURCE,
                        "editorMode": "code",
                        "format": "table",
                        "rawQuery": True,
                        "rawSql": "SELECT NOW() AS \"time\", COUNT(*) AS \"Critical\"\nFROM meter_alerts\nWHERE\n  severity = 'CRITICAL'\n  AND $__timeFilter(time)\n  AND ('$alert_type' = 'All' OR alert_type = '$alert_type')\n  AND ('$meter_id' = 'All' OR meter_id = '$meter_id');",
                        "refId": "A",
                    }
                ],
                "fieldConfig": {
                    "defaults": {
                        "color": {"mode": "fixed", "fixedColor": "red"},
                        "mappings": [],
                        "thresholds": {
                            "mode": "absolute",
                            "steps": [{"color": "red", "value": None}],
                        },
                        "unit": "short",
                    },
                    "overrides": [],
                },
                "options": {
                    "colorMode": "value",
                    "graphMode": "area",
                    "justifyMode": "auto",
                    "orientation": "auto",
                    "reduceOptions": {
                        "calcs": ["lastNotNull"],
                        "fields": "",
                        "values": False,
                    },
                    "textMode": "auto",
                },
            },
            {
                "gridPos": {"h": 4, "w": 5, "x": 5, "y": 0},
                "id": 2,
                "title": "WARNING Alerts",
                "type": "stat",
                "datasource": PG_DATASOURCE,
                "targets": [
                    {
                        "datasource": PG_DATASOURCE,
                        "editorMode": "code",
                        "format": "table",
                        "rawQuery": True,
                        "rawSql": "SELECT NOW() AS \"time\", COUNT(*) AS \"Warning\"\nFROM meter_alerts\nWHERE\n  severity = 'WARNING'\n  AND $__timeFilter(time)\n  AND ('$alert_type' = 'All' OR alert_type = '$alert_type')\n  AND ('$meter_id' = 'All' OR meter_id = '$meter_id');",
                        "refId": "A",
                    }
                ],
                "fieldConfig": {
                    "defaults": {
                        "color": {"mode": "fixed", "fixedColor": "orange"},
                        "mappings": [],
                        "thresholds": {
                            "mode": "absolute",
                            "steps": [{"color": "orange", "value": None}],
                        },
                        "unit": "short",
                    },
                    "overrides": [],
                },
                "options": {
                    "colorMode": "value",
                    "graphMode": "area",
                    "justifyMode": "auto",
                    "orientation": "auto",
                    "reduceOptions": {
                        "calcs": ["lastNotNull"],
                        "fields": "",
                        "values": False,
                    },
                    "textMode": "auto",
                },
            },
            {
                "gridPos": {"h": 4, "w": 4, "x": 10, "y": 0},
                "id": 3,
                "title": "INFO Alerts",
                "type": "stat",
                "datasource": PG_DATASOURCE,
                "targets": [
                    {
                        "datasource": PG_DATASOURCE,
                        "editorMode": "code",
                        "format": "table",
                        "rawQuery": True,
                        "rawSql": "SELECT NOW() AS \"time\", COUNT(*) AS \"Info\"\nFROM meter_alerts\nWHERE\n  severity = 'INFO'\n  AND $__timeFilter(time)\n  AND ('$alert_type' = 'All' OR alert_type = '$alert_type')\n  AND ('$meter_id' = 'All' OR meter_id = '$meter_id');",
                        "refId": "A",
                    }
                ],
                "fieldConfig": {
                    "defaults": {
                        "color": {"mode": "fixed", "fixedColor": "blue"},
                        "mappings": [],
                        "thresholds": {
                            "mode": "absolute",
                            "steps": [{"color": "blue", "value": None}],
                        },
                        "unit": "short",
                    },
                    "overrides": [],
                },
                "options": {
                    "colorMode": "value",
                    "graphMode": "area",
                    "justifyMode": "auto",
                    "orientation": "auto",
                    "reduceOptions": {
                        "calcs": ["lastNotNull"],
                        "fields": "",
                        "values": False,
                    },
                    "textMode": "auto",
                },
            },
            {
                "gridPos": {"h": 4, "w": 5, "x": 14, "y": 0},
                "id": 4,
                "title": "Total Incident Breaches",
                "type": "stat",
                "datasource": PG_DATASOURCE,
                "targets": [
                    {
                        "datasource": PG_DATASOURCE,
                        "editorMode": "code",
                        "format": "table",
                        "rawQuery": True,
                        "rawSql": "SELECT NOW() AS \"time\", COUNT(*) AS \"Total Incidents\"\nFROM meter_alerts\nWHERE\n  $__timeFilter(time)\n  AND ('$severity' = 'All' OR severity = '$severity')\n  AND ('$alert_type' = 'All' OR alert_type = '$alert_type')\n  AND ('$meter_id' = 'All' OR meter_id = '$meter_id');",
                        "refId": "A",
                    }
                ],
                "fieldConfig": {
                    "defaults": {
                        "color": {"mode": "thresholds"},
                        "mappings": [],
                        "thresholds": {
                            "mode": "absolute",
                            "steps": [
                                {"color": "green", "value": None},
                                {"color": "yellow", "value": 1},
                                {"color": "red", "value": 10},
                            ],
                        },
                        "unit": "short",
                    },
                    "overrides": [],
                },
                "options": {
                    "colorMode": "value",
                    "graphMode": "none",
                    "justifyMode": "auto",
                    "orientation": "auto",
                    "reduceOptions": {
                        "calcs": ["lastNotNull"],
                        "fields": "",
                        "values": False,
                    },
                    "textMode": "auto",
                },
            },
            {
                "gridPos": {"h": 4, "w": 5, "x": 19, "y": 0},
                "id": 5,
                "title": "Severity Proportion",
                "type": "piechart",
                "datasource": PG_DATASOURCE,
                "targets": [
                    {
                        "datasource": PG_DATASOURCE,
                        "editorMode": "code",
                        "format": "table",
                        "rawQuery": True,
                        "rawSql": "SELECT severity AS \"Severity\", COUNT(*) AS \"Count\"\nFROM meter_alerts\nWHERE\n  $__timeFilter(time)\n  AND ('$alert_type' = 'All' OR alert_type = '$alert_type')\n  AND ('$meter_id' = 'All' OR meter_id = '$meter_id')\nGROUP BY 1\nORDER BY 2 DESC;",
                        "refId": "A",
                    }
                ],
                "fieldConfig": {
                    "defaults": {"color": {"mode": "palette-classic"}, "mappings": []},
                    "overrides": [
                        {
                            "matcher": {"id": "byName", "options": "CRITICAL"},
                            "properties": [
                                {
                                    "id": "color",
                                    "value": {"fixedColor": "#F2495C", "mode": "fixed"},
                                }
                            ],
                        },
                        {
                            "matcher": {"id": "byName", "options": "WARNING"},
                            "properties": [
                                {
                                    "id": "color",
                                    "value": {"fixedColor": "#FF9830", "mode": "fixed"},
                                }
                            ],
                        },
                        {
                            "matcher": {"id": "byName", "options": "INFO"},
                            "properties": [
                                {
                                    "id": "color",
                                    "value": {"fixedColor": "#5794F2", "mode": "fixed"},
                                }
                            ],
                        },
                    ],
                },
                "options": {
                    "displayLabels": ["percent"],
                    "legend": {
                        "displayMode": "table",
                        "placement": "right",
                        "showLegend": True,
                        "values": ["value"],
                    },
                    "pieType": "donut",
                    "reduceOptions": {
                        "calcs": ["lastNotNull"],
                        "fields": "",
                        "values": False,
                    },
                    "tooltip": {"mode": "single", "sort": "none"},
                },
            },
            # Row 1: Anomaly Timeline by Type
            {
                "collapsed": False,
                "gridPos": {"h": 1, "w": 24, "x": 0, "y": 4},
                "id": 100,
                "title": "Anomaly Timeline by Type (VOLTAGE_SAG, VOLTAGE_SWELL, DEMAND_SPIKE, PHASE_IMBALANCE)",
                "type": "row",
            },
            {
                "gridPos": {"h": 8, "w": 16, "x": 0, "y": 5},
                "id": 6,
                "title": "Anomaly Timeline by Type",
                "description": "Temporal breakdown of grid events: VOLTAGE_SAG, VOLTAGE_SWELL, DEMAND_SPIKE, and PHASE_IMBALANCE.",
                "type": "timeseries",
                "datasource": PG_DATASOURCE,
                "targets": [
                    {
                        "datasource": PG_DATASOURCE,
                        "editorMode": "code",
                        "format": "time_series",
                        "rawQuery": True,
                        "rawSql": "SELECT\n  time_bucket('$interval', time) AS \"time\",\n  alert_type AS metric,\n  COUNT(*) AS \"count\"\nFROM meter_alerts\nWHERE\n  $__timeFilter(time)\n  AND ('$severity' = 'All' OR severity = '$severity')\n  AND ('$alert_type' = 'All' OR alert_type = '$alert_type')\n  AND ('$meter_id' = 'All' OR meter_id = '$meter_id')\nGROUP BY 1, 2\nORDER BY 1;",
                        "refId": "A",
                    }
                ],
                "fieldConfig": {
                    "defaults": {
                        "color": {"mode": "palette-classic"},
                        "custom": {
                            "axisCenteredZero": False,
                            "axisColorMode": "text",
                            "axisLabel": "Incidents / Interval",
                            "axisPlacement": "auto",
                            "drawStyle": "bars",
                            "fillOpacity": 85,
                            "lineWidth": 1,
                            "showPoints": "never",
                            "spanNulls": False,
                            "stacking": {"group": "A", "mode": "normal"},
                        },
                        "mappings": [],
                        "unit": "short",
                    },
                    "overrides": [
                        {
                            "matcher": {"id": "byName", "options": "VOLTAGE_SAG"},
                            "properties": [
                                {
                                    "id": "color",
                                    "value": {"fixedColor": "#E02F44", "mode": "fixed"},
                                }
                            ],
                        },
                        {
                            "matcher": {"id": "byName", "options": "VOLTAGE_SWELL"},
                            "properties": [
                                {
                                    "id": "color",
                                    "value": {"fixedColor": "#FA6400", "mode": "fixed"},
                                }
                            ],
                        },
                        {
                            "matcher": {"id": "byName", "options": "DEMAND_SPIKE"},
                            "properties": [
                                {
                                    "id": "color",
                                    "value": {"fixedColor": "#FADE2A", "mode": "fixed"},
                                }
                            ],
                        },
                        {
                            "matcher": {"id": "byName", "options": "PHASE_IMBALANCE"},
                            "properties": [
                                {
                                    "id": "color",
                                    "value": {"fixedColor": "#5794F2", "mode": "fixed"},
                                }
                            ],
                        },
                        {
                            "matcher": {"id": "byName", "options": "LOW_POWER_FACTOR"},
                            "properties": [
                                {
                                    "id": "color",
                                    "value": {"fixedColor": "#8AB8FF", "mode": "fixed"},
                                }
                            ],
                        },
                        {
                            "matcher": {
                                "id": "byName",
                                "options": "FREQUENCY_DEVIATION",
                            },
                            "properties": [
                                {
                                    "id": "color",
                                    "value": {"fixedColor": "#B877D9", "mode": "fixed"},
                                }
                            ],
                        },
                    ],
                },
                "options": {
                    "legend": {
                        "calcs": ["sum", "max"],
                        "displayMode": "table",
                        "placement": "bottom",
                        "showLegend": True,
                    },
                    "tooltip": {"mode": "multi", "sort": "desc"},
                },
            },
            {
                "gridPos": {"h": 8, "w": 8, "x": 16, "y": 5},
                "id": 7,
                "title": "Anomaly Distribution by Type",
                "description": "Total incident count categorized by anomaly classification.",
                "type": "piechart",
                "datasource": PG_DATASOURCE,
                "targets": [
                    {
                        "datasource": PG_DATASOURCE,
                        "editorMode": "code",
                        "format": "table",
                        "rawQuery": True,
                        "rawSql": "SELECT alert_type AS \"Anomaly Type\", COUNT(*) AS \"Count\"\nFROM meter_alerts\nWHERE\n  $__timeFilter(time)\n  AND ('$severity' = 'All' OR severity = '$severity')\n  AND ('$alert_type' = 'All' OR alert_type = '$alert_type')\n  AND ('$meter_id' = 'All' OR meter_id = '$meter_id')\nGROUP BY 1\nORDER BY 2 DESC;",
                        "refId": "A",
                    }
                ],
                "fieldConfig": {
                    "defaults": {"color": {"mode": "palette-classic"}, "mappings": []},
                    "overrides": [],
                },
                "options": {
                    "displayLabels": ["percent", "name"],
                    "legend": {
                        "displayMode": "table",
                        "placement": "bottom",
                        "showLegend": True,
                        "values": ["value", "percent"],
                    },
                    "pieType": "donut",
                    "reduceOptions": {
                        "calcs": ["lastNotNull"],
                        "fields": "",
                        "values": False,
                    },
                    "tooltip": {"mode": "single", "sort": "none"},
                },
            },
            # Row 2: Active Grid Incident Table
            {
                "collapsed": False,
                "gridPos": {"h": 1, "w": 24, "x": 0, "y": 13},
                "id": 101,
                "title": "Active Grid Incident Table",
                "type": "row",
            },
            {
                "gridPos": {"h": 10, "w": 24, "x": 0, "y": 14},
                "id": 8,
                "title": "Active Grid Incident Table",
                "description": "Live detailed incident log with meter_id, severity, observed value, threshold, and timestamp.",
                "type": "table",
                "datasource": PG_DATASOURCE,
                "targets": [
                    {
                        "datasource": PG_DATASOURCE,
                        "editorMode": "code",
                        "format": "table",
                        "rawQuery": True,
                        "rawSql": "SELECT\n  time AS \"timestamp\",\n  meter_id,\n  severity,\n  alert_type,\n  ROUND(value::numeric, 2) AS value,\n  ROUND(threshold::numeric, 2) AS threshold,\n  message\nFROM meter_alerts\nWHERE\n  $__timeFilter(time)\n  AND ('$severity' = 'All' OR severity = '$severity')\n  AND ('$alert_type' = 'All' OR alert_type = '$alert_type')\n  AND ('$meter_id' = 'All' OR meter_id = '$meter_id')\nORDER BY time DESC\nLIMIT 200;",
                        "refId": "A",
                    }
                ],
                "fieldConfig": {
                    "defaults": {
                        "color": {"mode": "thresholds"},
                        "custom": {
                            "align": "auto",
                            "cellOptions": {"type": "auto"},
                            "inspect": False,
                        },
                        "mappings": [],
                    },
                    "overrides": [
                        {
                            "matcher": {"id": "byName", "options": "severity"},
                            "properties": [
                                {
                                    "id": "custom.cellOptions",
                                    "value": {"type": "color-background"},
                                },
                                {
                                    "id": "mappings",
                                    "value": [
                                        {
                                            "options": {
                                                "CRITICAL": {
                                                    "color": "red",
                                                    "index": 0,
                                                    "text": "CRITICAL",
                                                }
                                            },
                                            "type": "value",
                                        },
                                        {
                                            "options": {
                                                "WARNING": {
                                                    "color": "orange",
                                                    "index": 1,
                                                    "text": "WARNING",
                                                }
                                            },
                                            "type": "value",
                                        },
                                        {
                                            "options": {
                                                "INFO": {
                                                    "color": "blue",
                                                    "index": 2,
                                                    "text": "INFO",
                                                }
                                            },
                                            "type": "value",
                                        },
                                    ],
                                },
                            ],
                        },
                        {
                            "matcher": {"id": "byName", "options": "meter_id"},
                            "properties": [
                                {"id": "custom.align", "value": "center"},
                                {"id": "displayName", "value": "Meter ID"},
                            ],
                        },
                        {
                            "matcher": {"id": "byName", "options": "alert_type"},
                            "properties": [
                                {"id": "displayName", "value": "Anomaly Type"}
                            ],
                        },
                        {
                            "matcher": {"id": "byName", "options": "value"},
                            "properties": [
                                {"id": "displayName", "value": "Observed Value"}
                            ],
                        },
                        {
                            "matcher": {"id": "byName", "options": "threshold"},
                            "properties": [{"id": "displayName", "value": "Threshold"}],
                        },
                        {
                            "matcher": {"id": "byName", "options": "message"},
                            "properties": [
                                {"id": "displayName", "value": "Diagnosis / Context"}
                            ],
                        },
                        {
                            "matcher": {"id": "byName", "options": "timestamp"},
                            "properties": [
                                {"id": "custom.align", "value": "center"},
                                {"id": "displayName", "value": "Timestamp"},
                            ],
                        },
                    ],
                },
                "options": {
                    "cellHeight": "sm",
                    "footer": {
                        "countRows": False,
                        "fields": "",
                        "reducer": ["sum"],
                        "show": False,
                    },
                    "showHeader": True,
                    "sortBy": [{"desc": True, "displayName": "Timestamp"}],
                },
            },
            # Row 3: Top Affected Meters
            {
                "collapsed": False,
                "gridPos": {"h": 1, "w": 24, "x": 0, "y": 24},
                "id": 102,
                "title": "Incident Concentration & Hotspots",
                "type": "row",
            },
            {
                "gridPos": {"h": 8, "w": 12, "x": 0, "y": 25},
                "id": 9,
                "title": "Top 10 Affected Meters by Incident Count",
                "description": "Smart meters experiencing the highest frequency of power quality disturbances.",
                "type": "barchart",
                "datasource": PG_DATASOURCE,
                "targets": [
                    {
                        "datasource": PG_DATASOURCE,
                        "editorMode": "code",
                        "format": "table",
                        "rawQuery": True,
                        "rawSql": "SELECT meter_id AS \"Meter\", COUNT(*) AS \"Incidents\"\nFROM meter_alerts\nWHERE\n  $__timeFilter(time)\n  AND ('$severity' = 'All' OR severity = '$severity')\n  AND ('$alert_type' = 'All' OR alert_type = '$alert_type')\nGROUP BY 1\nORDER BY 2 DESC\nLIMIT 10;",
                        "refId": "A",
                    }
                ],
                "fieldConfig": {
                    "defaults": {
                        "color": {"mode": "palette-classic"},
                        "custom": {
                            "axisCenteredZero": False,
                            "axisColorMode": "text",
                            "axisLabel": "Total Incidents",
                            "axisPlacement": "auto",
                            "fillOpacity": 80,
                            "gradientMode": "none",
                            "lineWidth": 1,
                        },
                        "mappings": [],
                        "unit": "short",
                    },
                    "overrides": [],
                },
                "options": {
                    "barRadius": 0.1,
                    "barWidth": 0.8,
                    "groupWidth": 0.7,
                    "legend": {
                        "displayMode": "none",
                        "placement": "bottom",
                        "showLegend": False,
                    },
                    "orientation": "horizontal",
                    "showValue": "always",
                    "stacking": "none",
                    "tooltip": {"mode": "single", "sort": "none"},
                    "xField": "Meter",
                    "yField": "Incidents",
                },
            },
            {
                "gridPos": {"h": 8, "w": 12, "x": 12, "y": 25},
                "id": 10,
                "title": "Real-Time Anomaly Stream Rate (Worker)",
                "description": "Streaming anomaly detection output rate from anomaly-worker-py.",
                "type": "timeseries",
                "datasource": PROM_DATASOURCE,
                "targets": [
                    {
                        "datasource": PROM_DATASOURCE,
                        "editorMode": "code",
                        "expr": "sum by (alert_type) (rate(anomaly_alerts_total[1m])) or sum(rate(anomaly_alerts_total[1m])) or vector(0)",
                        "legendFormat": "Alerts: {{alert_type}}",
                        "range": True,
                        "refId": "A",
                    }
                ],
                "fieldConfig": {
                    "defaults": {
                        "color": {"mode": "palette-classic"},
                        "custom": {
                            "axisCenteredZero": False,
                            "axisColorMode": "text",
                            "axisLabel": "Alerts / sec",
                            "axisPlacement": "auto",
                            "drawStyle": "line",
                            "fillOpacity": 15,
                            "lineInterpolation": "smooth",
                            "lineWidth": 2,
                            "showPoints": "never",
                            "spanNulls": False,
                        },
                        "mappings": [],
                        "unit": "reqps",
                    },
                    "overrides": [],
                },
                "options": {
                    "legend": {
                        "calcs": ["mean", "max", "last"],
                        "displayMode": "table",
                        "placement": "bottom",
                        "showLegend": True,
                    },
                    "tooltip": {"mode": "multi", "sort": "desc"},
                },
            },
        ],
    }


def main():
    dashboards = {
        "grid_telemetry.json": make_grid_telemetry_dashboard(),
        "pipeline_system.json": make_pipeline_system_dashboard(),
        "grid_anomalies.json": make_grid_anomalies_dashboard(),
    }

    for filename, content in dashboards.items():
        filepath = OUT_DIR / filename
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(content, f, indent=2)
            f.write("\n")
        print(f"Generated: {filepath}")


if __name__ == "__main__":
    main()
