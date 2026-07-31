"""
robustness_corrected.py
------------------------
Corrected robustness analysis. Two fixes over the first attempt:
  (1) the true capacity of a design is the minimum over ALL seven stations,
      not just painting and transmission (brakes at 40/day and wheels at
      43.6/day are real limits once the first two are relieved);
  (2) a queue driven above its capacity has no steady state, so the 95th
      percentile of flow time is reported ONLY where the run is stationary,
      tested by a drift check; beyond capacity the design is marked unstable.
"""
import simpy
import numpy as np
from math import sqrt

CT = [10.0, 8.0, 11.0, 16.0/0.9, 12.0, 9.0, 7.0]     # per-station cycle time
SMED_SETUP = 13.2                                     # SMED color-change (paint cap ~38/booth)

def true_capacity(np_, nt_, nb_):
    caps = [38.0*np_, 60.0, 43.6, 27.0*nt_, 40.0*nb_, 53.3, 68.6]
    i = int(np.argmin(caps))
    return caps[i], ["painting","fork","wheels","transmission","brakes","accessories","inspection"][i]

def ln(rng, m, cv):
    if m <= 0: return 0.0
    s = sqrt(np.log(1+cv**2)); return float(rng.lognormal(np.log(m)-0.5*s**2, s))

def run(seed, demand, np_, nt_, nb_, cv=0.40, days=140, warm=40):
    rng = np.random.default_rng(seed); env = simpy.Environment()
    caps = {0: np_, 3: nt_, 4: nb_}
    sv = [simpy.Resource(env, caps.get(i, 1)) for i in range(7)]
    pc = {"k": 0}; rec = []
    def frame(env):
        e = env.now
        for i in range(7):
            with sv[i].request() as r:
                yield r
                if i == 0:
                    pc["k"] += 1
                    if pc["k"] % 5 == 0: yield env.timeout(ln(rng, SMED_SETUP, cv))
                    yield env.timeout(ln(rng, CT[i], cv))
                    if rng.random() < 0.015: yield env.timeout(ln(rng, 8.0, cv))
                else:
                    yield env.timeout(ln(rng, CT[i], cv))
        rec.append((e, env.now))
    def src(env):
        ia = 480.0/demand
        while True:
            yield env.timeout(rng.exponential(ia)); env.process(frame(env))
    env.process(src(env)); env.run(until=days*480)
    st = sorted([(a, b) for a, b in rec if a >= warm*480])
    if len(st) < 20:
        return None, None, True
    fl = np.array([(b-a)/480 for a, b in st])
    h = len(fl)//2
    p1, p2 = np.percentile(fl[:h], 95), np.percentile(fl[h:], 95)   # drift check
    drift = p2/max(p1, 1e-6)
    unstable = drift > 1.3
    return np.percentile(fl, 95), drift, unstable

def eval_point(demand, np_, nt_, nb_, reps=5):
    ps, dr = [], []
    for s in range(reps):
        p, d, u = run(1000+s, demand, np_, nt_, nb_)
        if p is not None: ps.append(p); dr.append(d)
    if not ps: return None, True
    unstable = np.mean(dr) > 1.3
    return np.mean(ps), unstable

if __name__ == "__main__":
    designs = [("SMED + 2 transmission", 1, 2, 1),
               ("+ 2nd paint booth", 2, 2, 1),
               ("+ 2nd brake station", 2, 2, 2)]
    demands = list(range(30, 47, 2))
    print(f"{'design':<24} capacity  " + "  ".join(f"d{d}" for d in demands))
    results = {}
    for label, np_, nt_, nb_ in designs:
        cap, bott = true_capacity(np_, nt_, nb_)
        row = []
        for d in demands:
            p, unstable = eval_point(float(d), np_, nt_, nb_)
            row.append(("UNS" if (unstable or d >= cap) else f"{p:.2f}"))
        results[label] = (cap, bott, row)
        print(f"{label:<24} {cap:4.1f} ({bott[:5]})  " + "  ".join(f"{v:>5}" for v in row))
    print("\nUNS = unstable / non-stationary (demand at or above the design's capacity).")
    print("p95 flow time in working days, reported only where the run is stationary.")
