# Open Channel Hydraulic Analysis Bench

This project now includes a browser interface around the existing numerical hydraulic engine.

## Run

From this folder, run:

```powershell
python .\app.py
```

Then open [http://127.0.0.1:8000](http://127.0.0.1:8000).

For a single-platform deployment, Render is a good fit: the included
`render.yaml` creates a Python web service and a managed PostgreSQL database,
then wires the database connection into `DATABASE_URL`. Import the repository
from Render's dashboard and deploy the Blueprint. The server listens on
Render's `PORT` automatically and binds to all interfaces.

For Neon persistence, set `DATABASE_URL` in the process environment using the
connection string supplied by Neon, then start the app. The service creates a
`calculation_history` table on first successful calculation, stores request and
result JSONB, and exposes recent records at `GET /api/history`. The database is
optional; calculations still work when the variable is absent or Neon is
temporarily unavailable.

The service uses only Python's standard library for the web layer. Existing SciPy dependencies are still used by `solver.py` for numerical integration and root finding.

## Included analyses

- Uniform flow: critical depth, critical slope, normal depth, Froude number, specific energy, and general analysis
- Weirs: transitions and GVF step method
- Hydraulic jumps: conjugate depth
- Contractions: upstream depth, narrow-section critical conditions, and bed changes
- Depressions: with or without a weir

The JSON endpoint is `POST /api/calculate`; `GET /api/health` provides a lightweight service check.