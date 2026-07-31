"""
cityline_des.py
---------------
Discrete-event simulation of the CityLine assembly line at CycloPlus SA,
companion to Chapter 11. Built with SimPy.

It reproduces the current state measured by process mining in Chapter 10
(validation), then predicts three future states before any capital is spent:
  - SMED      : paint setup cut 225 -> 100 min/day (painting capacity 25.5 -> 38/day)
  - Six Sigma : paint rework rate cut 12.8% -> ~1.5%
  - Both

Each scenario runs R independent replications with a warm-up period removed,
and reports throughput and flow time with 95% confidence intervals. The line
uses a CONWIP release (a fixed number of frames in process), the whole-line
form of the kanban cap of Chapter 7.

Parameters mirror the CycloPlus master data model (single source of truth).

Changelog
---------
v1.1  Adds an optional finite buffer between painting and transmission, with
      blocking, for Exercise 11.3. The buffer is a second, nested cap inside
      the line-wide CONWIP release: a frame takes a buffer slot when it leaves
      painting and gives it back when it seizes transmission, so the slot
      covers the painting-to-transmission segment (fork and steering, then
      wheels). When no slot is free, painting keeps the booth and cannot start
      the next frame. That is blocking, and it is what a finite buffer does to
      an upstream station. Passing buffer_size=None reproduces v1.0 exactly.
v1.0  Initial version: CONWIP release, four scenarios.
"""

import simpy
import numpy as np
from math import sqrt
from scipy import stats

# --- fixed parameters (master model) ------------------------------------
STATIONS = [                       # (name, mean cycle time min)
    ("Frame & painting", 10.0),
    ("Fork & steering",   8.0),
    ("Wheels",           11.0),
    ("Transmission", 16.0 / 0.9),  # demonstrated CT (perf rate 0.9, ch.4) -> 17.8
    ("Brakes",           12.0),
    ("Accessories",       9.0),
    ("Final inspection",  7.0),
]
PAINT = "Frame & painting"
TRANSMISSION = "Transmission"

PROC_CV = 0.35
COLOR_CHANGE_EVERY = 5
REWORK_TIME = 8.0
WIP_CAP = 67                       # CONWIP, = observed WIP (ch.7/10)
SHIFT = 480.0                      # productive minutes per day

SIM_DAYS = 120
WARMUP_DAYS = 25
R = 12                             # replications

def ln(rng, mean):
    """Lognormal processing time, given mean and CV."""
    if mean <= 0:
        return 0.0
    sig = sqrt(np.log(1 + PROC_CV ** 2))
    mu = np.log(mean) - 0.5 * sig ** 2
    return float(rng.lognormal(mu, sig))

# --- one replication ----------------------------------------------------
def run_once(seed, cc_setup, rework_rate, buffer_size=None):
    """One replication.

    buffer_size: None for the unbuffered line (v1.0 behaviour), or an integer
    number of frames allowed between painting's output and transmission's
    input. Painting blocks while the buffer is full.
    """
    rng = np.random.default_rng(seed)
    env = simpy.Environment()
    servers = {name: simpy.Resource(env, capacity=1) for name, _ in STATIONS}
    wip = simpy.Resource(env, capacity=WIP_CAP)
    segment = (simpy.Resource(env, capacity=buffer_size)
               if buffer_size is not None else None)
    paint_count = {"n": 0}
    records = []          # (entry_time, exit_time)
    blocked = {"minutes": 0.0}

    def frame(env, wip_req):
        entry = env.now
        slot = None
        for name, ct in STATIONS:
            with servers[name].request() as req:
                yield req
                if name == PAINT:
                    paint_count["n"] += 1
                    if paint_count["n"] % COLOR_CHANGE_EVERY == 0:
                        yield env.timeout(ln(rng, cc_setup))     # color change
                    yield env.timeout(ln(rng, ct))
                    if rng.random() < rework_rate:               # paint rework
                        yield env.timeout(ln(rng, REWORK_TIME))
                    if segment is not None:
                        # take a buffer slot before releasing the booth:
                        # while none is free, painting is blocked.
                        t0 = env.now
                        slot = segment.request()
                        yield slot
                        blocked["minutes"] += env.now - t0
                else:
                    if name == TRANSMISSION and slot is not None:
                        # the slot covers the segment; give it back on entry
                        segment.release(slot)
                        slot = None
                    yield env.timeout(ln(rng, ct))
        exit_t = env.now
        records.append((entry, exit_t))
        wip.release(wip_req)

    def source(env):
        while True:
            req = wip.request()
            yield req                      # wait for a free CONWIP slot
            env.process(frame(env, req))

    env.process(source(env))
    env.run(until=SIM_DAYS * SHIFT)

    warm = WARMUP_DAYS * SHIFT
    steady = [(a, b) for (a, b) in records if a >= warm]
    n = len(steady)
    span_days = (SIM_DAYS - WARMUP_DAYS)
    throughput = n / span_days                       # frames per working day
    flow = np.mean([(b - a) / SHIFT for (a, b) in steady])  # working days
    blocking = blocked["minutes"] / (SIM_DAYS * SHIFT)      # share of horizon
    return throughput, flow, blocking

# --- experiment: replications + 95% CI ----------------------------------
def ci95(x):
    x = np.array(x)
    m = x.mean()
    if len(x) < 2:
        return m, 0.0
    h = stats.t.ppf(0.975, len(x) - 1) * x.std(ddof=1) / sqrt(len(x))
    return m, h

def scenario(label, cc_setup, rework_rate, buffer_size=None):
    thr, fl, bl = [], [], []
    for r in range(R):
        t, f, b = run_once(1000 + r, cc_setup, rework_rate, buffer_size)
        thr.append(t); fl.append(f); bl.append(b)
    tm, th = ci95(thr)
    fm, fh = ci95(fl)
    bm, _ = ci95(bl)
    tail = "" if buffer_size is None else f"   painting blocked {bm*100:4.1f}% of the time"
    print(f"{label:<30} throughput {tm:5.1f} +/- {th:.1f} /day   "
          f"flow time {fm:4.2f} +/- {fh:.2f} days{tail}")
    return dict(label=label, thr=tm, thr_ci=th, flow=fm, flow_ci=fh, blocked=bm)

if __name__ == "__main__":
    CC_NOW, CC_SMED = 44.0, 13.2       # color-change setup: 225 vs 100 min/day budget
    RW_NOW, RW_LEAN = 0.128, 0.015     # paint rework rate: before vs after Six Sigma
    print(f"SimPy CityLine DES  |  {R} replications, {SIM_DAYS-WARMUP_DAYS} measured days each\n")
    results = [
        scenario("Current state",        CC_NOW,  RW_NOW),
        scenario("+ SMED (paint setup)",  CC_SMED, RW_NOW),
        scenario("+ Six Sigma (rework)",  CC_NOW,  RW_LEAN),
        scenario("+ Both",                CC_SMED, RW_LEAN),
    ]
    print("\nValidation: current state should match Chapter 10 "
          "(~24.5/day, ~2.72 days).")

    print("\n=== Exercise 11.3: finite buffer between painting and transmission ===")
    scenario("Current state, no buffer", CC_NOW, RW_NOW)
    for b in (4, 8, 16):
        scenario(f"Current state, buffer {b}", CC_NOW, RW_NOW, buffer_size=b)
