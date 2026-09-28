"""Small web gateway for the open-channel hydraulics engine."""

import json
import math
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import solver
import db


ROOT = Path(__file__).resolve().parent


def required(data, key):
    value = data.get(key)
    if value is None or value == "":
        raise ValueError(f"{key.replace('_', ' ').capitalize()} is required.")
    return value


def positive(data, key):
    try:
        value = float(required(data, key))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key.replace('_', ' ').capitalize()} must be a positive number.") from exc
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{key.replace('_', ' ').capitalize()} must be a positive number.")
    return value


def positive_list(data, key):
    values = data.get(key)
    if not isinstance(values, list) or not values:
        raise ValueError(f"At least one {key.replace('_', ' ')} is required.")
    parsed = []
    for value in values:
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Every {key.replace('_', ' ')} must be numeric.") from exc
        if not math.isfinite(number) or number <= 0:
            raise ValueError(f"Every {key.replace('_', ' ')} must be positive.")
        parsed.append(number)
    return parsed


def dimensions(shape, data):
    if shape in ("rectangular", "wide_rectangular"):
        return {"b": 1.0 if data.get("discharge_kind") == "q" else positive(data, "b")}
    if shape == "triangular":
        return {"theta": math.radians(positive(data, "theta"))}
    if shape == "trapezoidal":
        return {"b": positive(data, "b"), "z": positive(data, "z")}
    if shape in ("circular", "semi_circular"):
        return {"d": positive(data, "d")}
    raise ValueError("Choose a supported channel shape.")


def discharge(data):
    kind = data.get("discharge_kind", "Q")
    if kind not in ("Q", "q"):
        raise ValueError("Discharge must be total Q or unit q.")
    if kind == "q" and data.get("shape") not in ("rectangular", "wide_rectangular"):
        raise ValueError("Unit discharge is available only for rectangular sections.")
    return {"kind": kind, "value": positive(data, "discharge")}


def resistance(data):
    kind = data.get("resistance_kind", "n")
    if kind not in ("n", "C"):
        raise ValueError("Roughness must be Manning n or Chezy C.")
    return {"kind": kind, "value": positive(data, "roughness")}


def calculate(data):
    shape = required(data, "shape")
    category = required(data, "category")
    operation = required(data, "operation")
    dims = dimensions(shape, data)
    flow = discharge(data)

    if category == "uf":
        if operation == "critical_depth":
            return {"type": "metrics", "title": "Critical depth", "metrics": [{"label": "yc", "value": solver.critical_depth(shape, dims, flow), "unit": "m"}]}
        if operation == "critical_slope":
            yc, slope = solver.compute_critical_slope(shape, dims, flow, resistance(data))
            return {"type": "metrics", "title": "Critical slope", "metrics": [{"label": "yc", "value": yc, "unit": "m"}, {"label": "Sc", "value": slope, "unit": ""}]}
        if operation == "normal_depth":
            cases = [{"slope": slope, "depth": solver.normal_depth(shape, dims, flow, resistance(data), slope)} for slope in positive_list(data, "slopes")]
            return {"type": "cases", "title": "Normal depth", "cases": cases}
        if operation in ("froude", "specific_energy"):
            y = positive(data, "y")
            if operation == "froude":
                value, regime = solver.compute_froude(shape, dims, flow, y)
                return {"type": "metrics", "title": "Froude number", "metrics": [{"label": "Fr", "value": value, "unit": ""}, {"label": "Regime", "value": regime, "unit": ""}]}
            return {"type": "metrics", "title": "Specific energy", "metrics": [{"label": "E", "value": solver.compute_specific_energy(shape, dims, flow, y), "unit": "m"}]}
        if operation == "general":
            rough = resistance(data)
            cases = []
            for slope in positive_list(data, "slopes"):
                depth, froude, energy, regime = solver.compute_uf_general_case(shape, dims, flow, rough, slope)
                cases.append({"slope": slope, "depth": depth, "froude": froude, "energy": energy, "regime": regime})
            yc, critical_slope = solver.compute_critical_slope(shape, dims, flow, rough)
            return {"type": "general", "title": "Uniform-flow analysis", "summary": [{"label": "Critical depth", "value": yc, "unit": "m"}, {"label": "Critical slope", "value": critical_slope, "unit": ""}], "cases": cases}

    if category == "jumps":
        result = solver.compute_conjugate_depth(shape, dims, flow, positive(data, "y1"))
        return {"type": "metrics", "title": "Hydraulic jump", "metrics": [{"label": "Initial depth", "value": result["y1"], "unit": "m"}, {"label": "Initial Fr", "value": result["Fr1"], "unit": ""}, {"label": "Conjugate depth", "value": result["y2"], "unit": "m"}, {"label": "Post-jump Fr", "value": result["Fr2"], "unit": ""}, {"label": "Head loss", "value": result["head_loss"], "unit": "m"}]}

    if category == "contractions" and operation == "critical":
        narrow = dimensions(shape, {**data, "b": data.get("narrow_b"), "z": data.get("narrow_z"), "d": data.get("narrow_d")})
        depth, energy = solver.compute_contraction_critical(shape, narrow, flow)
        return {"type": "metrics", "title": "Narrow-section control", "metrics": [{"label": "Critical depth", "value": depth, "unit": "m"}, {"label": "Critical energy", "value": energy, "unit": "m"}]}

    rough = resistance(data)
    slopes = positive_list(data, "slopes")
    if category == "weirs":
        if operation == "transitions":
            rows = []
            for slope in slopes:
                result = solver.compute_weir_transitions(shape, dims, flow, slope, rough, positive(data, "weir_height"))
                rows.append({"slope": slope, **{key: result[key] for key in ("y_up", "yw", "y_down", "Fr_up", "Fr_w", "Fr_d", "regime_up", "regime_w", "regime_d", "choked")}})
            return {"type": "weir", "title": "Weir transitions", "cases": rows}
        tables = []
        for slope in slopes:
            table, distance = solver.compute_weir_gvf(shape, dims, flow, slope, rough, positive(data, "weir_height"), positive(data, "target_rise"), int(positive(data, "steps")))
            tables.append({"slope": slope, "distance": distance, "rows": [{"step": row[0], "distance": row[1], "depth": row[2], "rise": row[3]} for row in table]})
        return {"type": "gvf", "title": "Weir GVF profile", "cases": tables}

    if category == "contractions":
        if operation == "far_upstream":
            return {"type": "cases", "title": "Far-upstream depth", "cases": [{"slope": slope, "depth": solver.normal_depth(shape, dims, flow, rough, slope)} for slope in slopes]}
        narrow = dimensions(shape, {**data, "b": data.get("narrow_b"), "z": data.get("narrow_z"), "d": data.get("narrow_d")})
        cases = []
        for slope in slopes:
            for dz in data.get("bed_changes", []):
                result = solver.compute_contraction_bed_change(shape, dims, narrow, flow, slope, rough, float(dz))
                cases.append({"slope": slope, "bed_change": float(dz), **{key: result[key] for key in ("y_up", "y_narrow", "y_down", "E_approach", "Ec_narrow", "choked")}})
        return {"type": "contraction", "title": "Contraction bed changes", "cases": cases}

    dz = positive(data, "depression")
    if operation == "no_weir":
        return {"type": "cases", "title": "Depression without weir", "cases": [{"slope": slope, **solver.compute_depression_no_weir(shape, dims, flow, slope, rough, dz)} for slope in slopes]}
    cases = []
    for slope in slopes:
        cases.append({"slope": slope, **solver.compute_depression_with_weir_full(shape, dims, flow, slope, rough, dz, positive(data, "weir_height"))})
    return {"type": "depression", "title": "Depression with weir", "cases": cases}


class Handler(BaseHTTPRequestHandler):
    def send_json(self, payload, status=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/health":
            self.send_json({"ok": True, "database_configured": db.configured()})
            return
        if path == "/api/history":
            self.send_json({"ok": True, "items": db.recent()})
            return
        file_path = ROOT / ("index.html" if path == "/" else path.lstrip("/"))
        if file_path.is_file() and ROOT in file_path.parents:
            content_type = "text/css" if file_path.suffix == ".css" else "application/javascript" if file_path.suffix == ".js" else "text/html"
            body = file_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_json({"error": "Not found."}, 404)

    def do_POST(self):
        if urlparse(self.path).path != "/api/calculate":
            self.send_json({"error": "Not found."}, 404)
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(size))
            result = calculate(payload)
            db.record(payload, result)
            self.send_json({"ok": True, "result": result})
        except (ValueError, KeyError, solver.SolverError, json.JSONDecodeError) as exc:
            self.send_json({"ok": False, "error": str(exc)}, 400)
        except Exception as exc:
            self.send_json({"ok": False, "error": f"Unexpected calculation error: {exc}"}, 500)

    def log_message(self, format_string, *args):
        return


if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Hydraulics web app running at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()