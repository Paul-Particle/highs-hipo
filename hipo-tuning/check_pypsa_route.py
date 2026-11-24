"""Solve the 1-year design through PyPSA and linopy with the installed highspy and the recommended HiPO options.

Run: py.sh <python with the patched highspy> check_pypsa_route.py   (IPX reference: 1060.265568581408 EUR/t)
"""
import sys
from pathlib import Path

sys.argv = ["export_benchmark_lps.py"]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import export_benchmark_lps as export  # noqa: E402

RECOMMENDED_OPTIONS = {"solver": "hipo", "run_crossover": "off", "threads": 1, "hipo_correctors": 3,
                       "hipo_stagnation_min_progress": 0.1, "hipo_feasibility_tolerance_factor": 0.1,
                       "hipo_primal_regularisation": 1e-10, "hipo_dual_regularisation": 1e-8,
                       "hipo_check_best_iterate": True,
                       "ipm_iteration_limit": 500}

n = export.build_design_model_on_years((2025,))
status, condition = n.optimize.solve_model(solver_name="highs", **RECOMMENDED_OPTIONS)
steel_tonnes = n.loads.at["steel_load", "p_set"] * n.snapshot_weightings.objective.sum()
levelised_cost = n.objective / steel_tonnes
print("RESULT", status, condition, "lcos", levelised_cost, "IPX reference 1060.265568581408")
