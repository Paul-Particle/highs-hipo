"""Check that the installed highspy runs HiPO with the fork's options and matches simplex on a transport LP.

Run after installing the wheel and highspy-extras: python check_wheel_hipo.py
"""
import sys

import highspy
import numpy as np

FORK_OPTIONS = {
    "solver": "hipo",
    "presolve": "off",
    "run_crossover": "off",
    "hipo_correctors": 3,
    "hipo_stagnation_min_progress": 0.1,
    "hipo_feasibility_tolerance_factor": 0.1,
    "hipo_primal_regularisation": 1e-10,
    "hipo_dual_regularisation": 1e-8,
    "hipo_check_best_iterate": True,
}

# 150 sources and 200 sinks: big enough that the factorisation runs through BLAS, Metis
# and AMD, which a toy LP of a few variables barely touches.
NUM_SOURCES, NUM_SINKS = 150, 200


def solve_random_transport_lp(options: dict) -> highspy.Highs:
    """Minimise shipping cost from sources with capped supply to sinks with fixed demand."""
    rng = np.random.default_rng(1)
    supply = rng.uniform(50, 150, NUM_SOURCES)
    demand = np.full(NUM_SINKS, 0.9 * supply.sum() / NUM_SINKS)
    num_cols = NUM_SOURCES * NUM_SINKS
    col_index = np.arange(num_cols, dtype=np.int32).reshape(NUM_SOURCES, NUM_SINKS)
    h = highspy.Highs()
    h.setOptionValue("output_flag", False)
    for name, value in options.items():
        if h.setOptionValue(name, value) != highspy.HighsStatus.kOk:
            raise SystemExit(f"highspy {h.version()} rejects option {name}={value!r}")
    no_entries = np.array([], dtype=np.int32)
    h.addCols(num_cols, rng.uniform(1, 10, num_cols), np.zeros(num_cols), np.full(num_cols, highspy.kHighsInf),
              0, no_entries, no_entries, np.array([]))
    h.addRows(NUM_SOURCES, np.full(NUM_SOURCES, -highspy.kHighsInf), supply, num_cols,
              np.arange(0, num_cols, NUM_SINKS, dtype=np.int32), col_index.ravel(), np.ones(num_cols))
    h.addRows(NUM_SINKS, demand, np.full(NUM_SINKS, highspy.kHighsInf), num_cols,
              np.arange(0, num_cols, NUM_SOURCES, dtype=np.int32), col_index.T.ravel(), np.ones(num_cols))
    h.run()
    return h


simplex = solve_random_transport_lp({"solver": "simplex"})
hipo = solve_random_transport_lp(FORK_OPTIONS)
simplex_objective = simplex.getInfo().objective_function_value
hipo_info = hipo.getInfo()
hipo_status = hipo.modelStatusToString(hipo.getModelStatus())
relative_gap = abs(hipo_info.objective_function_value - simplex_objective) / abs(simplex_objective)
if hipo_status != "Optimal" or hipo_info.ipm_iteration_count == 0 or relative_gap > 1e-6:
    windows_hint = ("\nOn Windows with an AVX-512 CPU, set OPENBLAS_CORETYPE=Haswell: highspy-extras' OpenBLAS kernels "
                    "for AVX-512 give HiPO NaN there." if sys.platform == "win32" else "")
    raise SystemExit(f"HiPO check failed: status {hipo_status}, {hipo_info.ipm_iteration_count} IPM iterations, "
                     f"objective {hipo_info.objective_function_value} against simplex's {simplex_objective}{windows_hint}")
print(f"highspy {hipo.version()}: HiPO with the fork's options solved the transport LP in "
      f"{hipo_info.ipm_iteration_count} iterations, within {relative_gap:.0e} of simplex")
