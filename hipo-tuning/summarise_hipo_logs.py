"""One line per diagnosis log: status, HiPO iterations, short steps (min alpha < 0.05), longest run of them,
resets, whether IPX took over, HiGHS run time and objective. Needs logs written with log_dev_level=2 for step data.
Run: python3 summarise_hipo_logs.py [glob]   (default work/logs/diag_*.log)
"""
import glob
import re
import sys
from pathlib import Path

pattern = sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).resolve().parent / "work/logs/diag_*.log")
print(f"{'log':58s} {'status':10s} {'iters':>5s} {'short':>5s} {'run':>4s} {'resets':>6s} {'ipx':>3s} "
      f"{'time_s':>7s} {'objective':>16s} {'alpha':>5s} {'cor':>4s}")
for path in sorted(glob.glob(pattern)):
    text = open(path).read()
    status = re.findall(r"Model status\s*:\s*(.+)", text)
    run_time = re.findall(r"HiGHS run time\s*:\s*([\d.]+)", text)
    objective = re.findall(r"Objective value\s*:\s*([-\d.e+]+)", text)
    in_hipo, iterations, short_steps, run, longest_run, steps, correctors = False, 0, 0, 0, 0, [], []
    for line in text.splitlines():
        if line.startswith("Running HiPO"):
            in_hipo = True
        if line.startswith("Restarting with IPX"):
            in_hipo = False
        fields = line.split()
        if in_hipo and len(fields) > 15 and fields[0].isdigit():
            iterations += 1
            if iterations == 1:
                continue
            step = min(float(fields[7]), float(fields[8]))
            steps.append(step)
            correctors.append(int(fields[11]))
            run = run + 1 if step < 0.05 else 0
            short_steps += step < 0.05
            longest_run = max(longest_run, run)
    name = path.split("/")[-1].removeprefix("diag_").removesuffix(".log")
    print(f"{name:58s} {(status or ['stopped' if 'Stopped at IPX restart' in text else 'running'])[-1][:10]:10s} {iterations:5d} {short_steps:5d} {longest_run:4d} "
          f"{text.count('Resetting to iteration'):6d} {('yes' if 'Restarting with IPX' in text else 'no'):>3s} "
          f"{(run_time or ['-'])[-1]:>7s} {(objective or ['-'])[-1]:>16s} "
          f"{(sum(steps) / len(steps) if steps else 0):5.2f} {(sum(correctors) / len(correctors) if correctors else 0):4.1f}")
