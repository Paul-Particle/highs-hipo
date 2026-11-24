"""Solve work/lps/<LP>.lp with highspy and append time, status, objective and iterations to work/solves.csv.

Run: py.sh <python> solve_lp_file.py LP_NAME SOLVER THREADS LABEL
SOLVER is HiGHS's "solver" option (ipx or hipo); crossover off. Further option=value pairs follow LABEL.
"""
import csv
import os
import sys
import time
from pathlib import Path

import highspy

WORK_DIR = Path(__file__).resolve().parent / "work"
lp_name, solver, threads, label = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]

h = highspy.Highs()
h.setOptionValue("solver", solver)
h.setOptionValue("run_crossover", "off")
h.setOptionValue("threads", threads)
extra_options = dict(option.split("=", 1) for option in sys.argv[5:])  # e.g. presolve=off hipo_system=normaleq
for key, value in extra_options.items():
    typed_value = int(value) if value.lstrip("-").isdigit() else float(value) if value.replace(".", "", 1).replace("e-", "", 1).isdigit() else value
    h.setOptionValue(key, typed_value)
h.readModel(str(WORK_DIR / "lps" / f"{lp_name}.lp"))
load_before = os.getloadavg()[0]
start = time.time()
h.run()
wall_seconds = time.time() - start
info = h.getInfo()
row = {"lp": lp_name, "label": label, "highs_version": h.version(), "solver": solver, "threads": threads, "options": " ".join(sys.argv[5:]),
       "status": h.modelStatusToString(h.getModelStatus()), "objective": info.objective_function_value,
       "ipm_iterations": info.ipm_iteration_count, "wall_seconds": round(wall_seconds, 1),
       "load_before": round(load_before, 2), "load_after": round(os.getloadavg()[0], 2)}
results_csv = WORK_DIR / "solves.csv"
with open(results_csv, "a", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=list(row))
    if handle.tell() == 0:
        writer.writeheader()
    writer.writerow(row)
print(row, flush=True)
