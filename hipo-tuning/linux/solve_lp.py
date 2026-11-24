"""Solve one LP file with highspy (HiPO, 1 thread, no crossover) and print one line: solve_lp.py LP LABEL [option=value ...]."""
import sys
import time

import highspy

lp_path, label = sys.argv[1], sys.argv[2]
h = highspy.Highs()
h.setOptionValue("output_flag", False)
for option, value in {"solver": "hipo", "run_crossover": "off", "threads": 1}.items():
    h.setOptionValue(option, value)
for pair in sys.argv[3:]:
    key, value = pair.split("=", 1)
    typed = int(value) if value.lstrip("-").isdigit() else float(value) if value.replace(".", "", 1).replace("e-", "", 1).isdigit() else value
    h.setOptionValue(key, typed)
h.readModel(lp_path)
start = time.time()
h.run()
info = h.getInfo()
print(f"{label:30s} {lp_path.split('/')[-1]:18s} {h.modelStatusToString(h.getModelStatus()):10s} "
      f"obj {info.objective_function_value:.10e} ipm_iter {info.ipm_iteration_count:4d} {time.time() - start:7.1f} s", flush=True)
