"""
cityline_des_advanced.py
------------------------
Extends the Chapter 11 CityLine model from evaluating fixed points to two things
a formula cannot do:

  (1) ROBUSTNESS  - stress a future-state design (variability up) and read not the
      mean but the 95th percentile of flow time and the risk of missing demand.
  (2) DESIGN SEARCH - evaluate a grid of designs against a demand of 36/day and
      find the cheapest one that meets it robustly.

Demand-driven arrivals (Poisson) replace the CONWIP release, so a design whose
capacity sits below demand shows an exploding queue - exactly the failure a
point estimate hides.
"""

import simpy
import numpy as np
from math import sqrt

STATIONS = [                       # (name, mean CT min, n_servers key)
    ("Frame & painting", 10.0, "paint"),
    ("Fork & steering",   8.0, None),
    ("Wheels",           11.0, None),
    ("Transmission", 16.0 / 0.9,  "trans"),
    ("Brakes",           12.0, None),
    ("Accessories",       9.0, None),
    ("Final inspection",  7.0, None),
]
SHIFT = 480.0
REWORK_TIME = 8.0
COLOR_CHANGE_EVERY = 5

def ln(rng, mean, cv):
    if mean <= 0:
        return 0.0
    sig = sqrt(np.log(1 + cv ** 2))
    mu = np.log(mean) - 0.5 * sig ** 2
    return float(rng.lognormal(mu, sig))

def run_once(seed, design, stress, sim_days=80, warmup_days=20):
    """design: dict(cc_setup, rework, n_paint, n_trans); stress: dict(demand, cv)."""
    rng = np.random.default_rng(seed)
    env = simpy.Environment()
    caps = {"paint": design["n_paint"], "trans": design["n_trans"]}
    servers = {name: simpy.Resource(env, capacity=caps.get(key, 1))
               for name, _, key in STATIONS}
    cv = stress["cv"]
    cc = design["cc_setup"]
    rework = design["rework"]
    paint_n = {"k": 0}
    recs = []

    def frame(env):
        entry = env.now
        for name, ct, key in STATIONS:
            with servers[name].request() as req:
                yield req
                if name == "Frame & painting":
                    paint_n["k"] += 1
                    if paint_n["k"] % COLOR_CHANGE_EVERY == 0:
                        yield env.timeout(ln(rng, cc, cv))
                    yield env.timeout(ln(rng, ct, cv))
                    if rng.random() < rework:
                        yield env.timeout(ln(rng, REWORK_TIME, cv))
                else:
                    yield env.timeout(ln(rng, ct, cv))
        recs.append((entry, env.now))

    def source(env):
        ia = SHIFT / stress["demand"]          # mean inter-arrival (min)
        while True:
            yield env.timeout(rng.exponential(ia))
            env.process(frame(env))

    env.process(source(env))
    env.run(until=sim_days * SHIFT)

    warm = warmup_days * SHIFT
    steady = [(a, b) for (a, b) in recs if a >= warm]
    days = sim_days - warmup_days
    thr = len(steady) / days
    flows = np.array([(b - a) / SHIFT for (a, b) in steady]) if steady else np.array([0])
    return thr, flows.mean(), np.percentile(flows, 95)

def evaluate(design, stress, reps=8):
    t, m, p = [], [], []
    for r in range(reps):
        thr, fm, fp = run_once(2000 + r, design, stress)
        t.append(thr); m.append(fm); p.append(fp)
    return np.mean(t), np.mean(m), np.mean(p)

# design levers
CC_SMED = 13.2      # SMED paint setup budget (100 min/day) -> painting cap ~38/server
RW_LEAN = 0.015     # Six Sigma rework rate
def design(n_paint=1, n_trans=1):
    return dict(cc_setup=CC_SMED, rework=RW_LEAN, n_paint=n_paint, n_trans=n_trans)

if __name__ == "__main__":
    print("=== DESIGN SEARCH: does the design meet demand? (CV 0.40) ===")
    grid = [("SMED, 1 paint, 1 trans", design(1, 1)),
            ("SMED, 1 paint, 2 trans", design(1, 2)),
            ("SMED, 2 paint, 2 trans", design(2, 2))]
    for dem in [36.0, 40.0]:
        print(f"\n-- demand {dem:.0f}/day --")
        for label, d in grid:
            thr, fm, fp = evaluate(d, dict(demand=dem, cv=0.40))
            meets = "MEETS" if thr >= 0.99 * dem else "MISSES"
            print(f"  {label:<26} thr {thr:5.1f}/day  flow p95 {fp:5.2f} d   {meets}")

    print("\n=== ROBUSTNESS to a demand forecast error (CV 0.40) ===")
    for label, d in [("thin margin: 1 paint, 2 trans (cap ~38)", design(1, 2)),
                     ("robust: 2 paint, 2 trans (cap ~54)", design(2, 2))]:
        print(f"-- {label} --")
        for dem in [32, 34, 36, 38, 40, 42, 44]:
            thr, fm, fp = evaluate(d, dict(demand=float(dem), cv=0.40))
            print(f"  demand {dem}:  thr {thr:5.1f}/day   p95 flow {fp:6.2f} days")
