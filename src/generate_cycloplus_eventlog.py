"""
generate_cycloplus_eventlog.py
--------------------------------
Reproducible event log for the CityLine assembly line at CycloPlus SA, the raw
material for Chapter 10 (Process Mining).

Engine: a discrete-event simulation of the seven-station line with a CONWIP
release policy that holds work in process at the book's VSM value (67 units).
By construction throughput settles at the bottleneck rate (painting, 25.5/day)
and, by Little's Law, flow time settles at 67 / 25.5 = 2.6 working days. The log
therefore *demonstrates* Little's Law (ch.3) and the WIP cap of ch.7, while
exposing the rework loops and variants the hand-drawn map omits.

Time runs as a continuous production stream in working minutes (480-min days),
so measured flow time is directly comparable to the book's 2.6-day figure.

Provenance of parameters (mirror of CycloPlus_Master_Data_Model, Assumptions):
  A  = validated reference data: station cycle times, painting setup budget,
       rework cost, observed WIP total (67).
  C  = authored capability (paint mean/sd -> rework rate) and transmission
       performance rate.
  C* = authored here, to add to the Assumptions sheet: processing-time CV,
       color-change size/cadence, final-inspection fail rate, expedite share,
       warm-up, kept cases, seed.

Output:
  cycloplus_cityline_eventlog.csv   (case_id, activity, start_timestamp, timestamp, resource, line, cost_chf)
  cycloplus_cityline_eventlog.xes   (PM4Py-native, if pm4py is available)
"""

from pathlib import Path
import heapq
from collections import deque
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from scipy.stats import norm

# --------------------------------------------------------------------------
# 1. Parameters (mirror of the master data model)
# --------------------------------------------------------------------------
SEED = 42                       # C*
WIP_CAP = 67                    # A   total observed WIP at the VSM (20+5+8+25+2+3+4)
WARMUP = 120                    # C*  departures discarded before steady state
N_KEEP = 500                    # C*  departures kept in the log
PROC_CV = 0.35                  # C*  coefficient of variation of processing times

# Stations: name, mean processing time (min), operator.  CTs from master model (A).
# Transmission uses the demonstrated cycle time 16 / performance-rate 0.9 (ch.4).
TP = 0.90                       # C   transmission performance rate
STATIONS = [
    ("Frame & painting", 10.0,        "Op-Paint"),
    ("Fork & steering",   8.0,        "Op-Fork"),
    ("Wheels",           11.0,        "Op-Wheels"),
    ("Transmission",     16.0 / TP,   "Op-Trans"),
    ("Brakes",           12.0,        "Op-Brakes"),
    ("Accessories",       9.0,        "Op-Access"),
    ("Final inspection",  7.0,        "Op-Inspect"),
]
NS = len(STATIONS)

# Painting: distributed color changes ("color changes cut its capacity", ch.3).
# 44 min every 5 frames ~ 8.8 min/frame amortized -> painting effective 18.8 min
# -> pace 480/18.8 = 25.5/day (the book's bottleneck rate), ~ the 225 min/day budget.
COLOR_CHANGE_MIN = 44.0         # C*
COLOR_CHANGE_EVERY = 5          # C*

# Paint rework: rate derived from the "before" capability (master model, C).
LSL, USL, MU, SD = 80, 120, 98, 13
PAINT_REWORK_RATE = norm.cdf((LSL - MU) / SD) + (1 - norm.cdf((USL - MU) / SD))  # ~0.1284
REWORK_MEAN = 8.0               # C*  repaint time
REWORK_COST_CHF = 30.0          # A   paint rework cost/frame

FINAL_FAIL_RATE = 0.05          # C*  final-inspection failure -> adjustment loop
ADJUST_MEAN = 9.0               # C*
EXPEDITE_SHARE = 0.02           # C*  share flagged as express (variant marker)

START_DATE = datetime(2026, 3, 2, 8, 0, 0)
rng = np.random.default_rng(SEED)

def ptime(mean):
    """Positive processing time with given mean and CV=PROC_CV (lognormal)."""
    cv = PROC_CV
    sigma = np.sqrt(np.log(1 + cv ** 2))
    mu = np.log(mean) - 0.5 * sigma ** 2
    return float(rng.lognormal(mu, sigma))

# --------------------------------------------------------------------------
# 2. Discrete-event simulation, single server per station, CONWIP release
# --------------------------------------------------------------------------
server_free = [True] * NS
queues = [deque() for _ in range(NS)]     # frames waiting at each station
paint_served = 0                          # painting count, for color-change cadence
events = []                               # service records
evq = []                                  # event heap: (time, seq, kind, payload)
_seq = 0

def push(t, kind, payload):
    global _seq
    heapq.heappush(evq, (t, _seq, kind, payload))
    _seq += 1

def log(case, activity, resource, start, complete, cost=0.0):
    events.append({"case_id": case, "activity": activity,
                   "start_min": start, "complete_min": complete,
                   "resource": resource, "line": "CityLine", "cost_chf": round(cost, 2)})

class Frame:
    __slots__ = ("cid", "route", "step", "express")
    def __init__(self, cid, express):
        self.cid = cid
        self.express = express
        self.route = [
            (0, "Frame & painting", 10.0, 0.0, False),
            (1, "Fork & steering",   8.0, 0.0, False),
            (2, "Wheels",           11.0, 0.0, False),
            (3, "Transmission", 16.0 / TP, 0.0, False),
            (4, "Brakes",           12.0, 0.0, False),
            (5, "Accessories",       9.0, 0.0, False),
            (6, "Final inspection",  7.0, 0.0, True),
        ]
        self.step = 0

released = 0
completed = 0
departure_order = {}          # cid -> departure index
pool_size = WARMUP + N_KEEP + WIP_CAP + 50

def arrive(frame, t):
    s = frame.route[frame.step][0]
    if frame.step == 0:                       # case-start event = release to the line
        if frame.express:
            log(frame.cid, "Express release", "Planner", t, t)
        else:
            log(frame.cid, "Order released", "Planner", t, t)
    queues[s].append(frame)
    start_service(s, t)

def start_service(s, t):
    global paint_served
    if not server_free[s] or not queues[s]:
        return
    frame = queues[s].popleft()
    server_free[s] = False
    idx, activity, mean, cost, _ = frame.route[frame.step]
    cursor = t
    if activity == "Frame & painting":
        paint_served += 1
        if paint_served % COLOR_CHANGE_EVERY == 0:
            cc = ptime(COLOR_CHANGE_MIN)
            log(frame.cid, "Color change", STATIONS[s][2], cursor, cursor + cc)
            cursor += cc
    pt = ptime(mean)
    log(frame.cid, activity, STATIONS[s][2], cursor, cursor + pt, cost)
    push(cursor + pt, "complete", (s, frame))

def complete(s, frame, t):
    global completed, released
    server_free[s] = True
    _, activity, _, _, first_insp = frame.route[frame.step]
    if activity == "Frame & painting" and rng.random() < PAINT_REWORK_RATE:
        frame.route.insert(frame.step + 1,
                            (0, "Paint rework", REWORK_MEAN, REWORK_COST_CHF, False))
    if activity == "Final inspection" and first_insp and rng.random() < FINAL_FAIL_RATE:
        frame.route.insert(frame.step + 1, (6, "Final adjustment", ADJUST_MEAN, 0.0, False))
        frame.route.insert(frame.step + 2, (6, "Final inspection", 7.0, 0.0, False))
    frame.step += 1
    if frame.step < len(frame.route):
        arrive(frame, t)
    else:
        completed += 1
        departure_order[frame.cid] = completed
        if released < pool_size:
            f = Frame(f"CL-{released+1:05d}", rng.random() < EXPEDITE_SHARE)
            released += 1
            arrive(f, t)
    start_service(s, t)

# seed the line with WIP_CAP frames at t=0 (the standing WIP)
for _ in range(WIP_CAP):
    f = Frame(f"CL-{released+1:05d}", rng.random() < EXPEDITE_SHARE)
    released += 1
    arrive(f, 0.0)

while evq and completed < WARMUP + N_KEEP:
    now, _, kind, payload = heapq.heappop(evq)
    if kind == "complete":
        s, frame = payload
        complete(s, frame, now)

# --------------------------------------------------------------------------
# 3. Keep steady-state cases, map minutes -> timestamps, save
# --------------------------------------------------------------------------
kept = {cid for cid, order in departure_order.items() if order > WARMUP}
df = pd.DataFrame([e for e in events if e["case_id"] in kept])
df["timestamp"] = df["complete_min"].apply(lambda m: START_DATE + timedelta(minutes=m))
df["start_timestamp"] = df["start_min"].apply(lambda m: START_DATE + timedelta(minutes=m))
df = df[["case_id", "activity", "start_timestamp", "timestamp", "resource", "line", "cost_chf"]]
df = df.sort_values(["timestamp", "case_id"]).reset_index(drop=True)

DATA = Path(__file__).resolve().parent.parent / "data"
out_csv = str(DATA / "cycloplus_cityline_eventlog.csv")
df.to_csv(out_csv, index=False)

rel = df.groupby("case_id").start_timestamp.min()
dep = df.groupby("case_id").timestamp.max()
W = (dep - rel).dt.total_seconds() / 60 / 480
span = (dep.max() - dep.min()).total_seconds() / 60 / 480
lam = (len(dep) - 1) / span
print(f"Wrote {out_csv}: {len(df)} events, {df.case_id.nunique()} cases.")
print(f"Throughput  ~ {lam:.1f} units/working-day  (25.5 pace minus rework capacity loss)")
print(f"Flow time   ~ {W.mean()*480:.0f} min = {W.mean():.2f} working days")
print(f"Little's Law: L = lambda*W = {lam*W.mean():.1f} ~ WIP cap 67")
print(f"Flow efficiency = {73/(W.mean()*480)*100:.1f}%  (73-min VA / flow time)")
print(f"Paint rework rate used (master model): {PAINT_REWORK_RATE:.4f}")

try:
    import pm4py
    lg = pm4py.format_dataframe(df.copy(), case_id="case_id",
                                activity_key="activity", timestamp_key="timestamp")
    pm4py.write_xes(lg, str(DATA / "cycloplus_cityline_eventlog.xes"))
    print("Wrote cycloplus_cityline_eventlog.xes")
except Exception as e:
    print("XES skipped:", e)
