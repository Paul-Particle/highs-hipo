"""Check that the installed highspy runs HiPO and accepts the fork's options, on a two-variable LP.

Run after installing the wheel and highspy-extras: python check_wheel_hipo.py
"""
import highspy

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

h = highspy.Highs()
for name, value in FORK_OPTIONS.items():
    option_status = h.setOptionValue(name, value)
    if option_status != highspy.HighsStatus.kOk:
        raise SystemExit(f"highspy {h.version()} rejects option {name}={value!r}")
x = h.addVariable(lb=0)
y = h.addVariable(lb=0)
h.addConstr(x + 2 * y >= 2)
h.addConstr(3 * x + y >= 3)
h.minimize(x + y)

model_status = h.modelStatusToString(h.getModelStatus())
info = h.getInfo()
expected_objective = 1.4
if model_status != "Optimal" or abs(info.objective_function_value - expected_objective) > 1e-6 or info.ipm_iteration_count == 0:
    raise SystemExit(f"HiPO check failed: status {model_status}, objective {info.objective_function_value}, "
                     f"{info.ipm_iteration_count} IPM iterations")
print(f"highspy {h.version()}: HiPO solved the check LP in {info.ipm_iteration_count} iterations with the fork's options")
