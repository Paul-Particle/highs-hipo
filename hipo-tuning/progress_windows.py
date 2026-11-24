"""For each log: ratio of the KKT merit max(pinf/1e-7, dinf/1e-7, gap/1e-8) at the end vs the start of every run
of >= 5 consecutive short steps (min alpha < 0.05). Small ratio = real progress despite short steps."""
import glob
import sys

for path in sorted(sys.argv[1:]):
    rows, in_hipo = [], False
    for line in open(path):
        if line.startswith("Running HiPO"): in_hipo = True
        if line.startswith("Restarting with IPX"): in_hipo = False
        f = line.split()
        if in_hipo and len(f) > 15 and f[0].isdigit():
            merit = max(float(f[3]) / 1e-7, float(f[4]) / 1e-7, float(f[5]) / 1e-8)
            rows.append((int(f[0]), min(float(f[7]), float(f[8])), merit))
    ratios, run_start = [], None
    for i, (it, step, merit) in enumerate(rows):
        if step < 0.05:
            if run_start is None: run_start = i - 1
            if i - run_start == 5:
                ratios.append(round(merit / rows[run_start][2], 2)); run_start = i
        else:
            run_start = None
    print(path.split("diag_")[-1][:40], "5-short-step windows, merit end/start:", ratios)
