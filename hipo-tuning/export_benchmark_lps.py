"""Write the benchmark LPs to files, built exactly as in the Ebro runs, so that each solver reads the same problem.

Designs at 3-hour steps (as ebro_robust_multi_year_designs.py): d1 = 2025, d5 = 2015-2019, d10 = 2016-2025,
d26 = 2000-2025, all with shaft minimum load 0.5. op26 = the single-2025 design operated hourly through 2000-2025
with the on/off shaft (minimum down time 24 h), linearised commitment, cyclic stores (ebro_continuous_operation pf).
Run: py.sh <python> export_benchmark_lps.py NAME [NAME ...]
"""
import os
import re
import sys
import time
from pathlib import Path

import pandas as pd

pd.set_option("future.infer_string", False)
import pypsa  # noqa: E402

WORK_DIR = Path(__file__).resolve().parent / "work"
SERIES_DIR = Path(os.environ["EBRO_SERIES_DIR"])  # one parquet of hourly capacity factors per weather year
HOURS_PER_STEP = 3
DESIGN_YEARS = {"d1": (2025,), "d5": tuple(range(2015, 2020)), "d10": tuple(range(2016, 2026)),
                "d26": tuple(range(2000, 2026))}


def read_year_series_on_own_calendar(year: int) -> pd.DataFrame:
    year_series = pd.read_parquet(SERIES_DIR / f"{year}.parquet")
    own_calendar = pd.date_range(f"{year}-01-01", periods=8784 if year % 4 == 0 else 8760, freq="h")
    year_series.index = own_calendar[~((own_calendar.month == 2) & (own_calendar.day == 29))]
    return year_series


def average_consecutive_hours(year_series: pd.DataFrame) -> pd.DataFrame:
    block = pd.Series(range(len(year_series))) // HOURS_PER_STEP
    averaged = year_series.groupby(block.values).mean()
    averaged.index = year_series.index[::HOURS_PER_STEP]
    return averaged


def add_battery_tie_and_year_end_store_levels(n: pypsa.Network, snapshots, tie_store_levels: bool = True) -> None:
    """Battery charger and discharger share one inverter rating; store levels match at every year end if tied."""
    p_nom = n.model.variables["Link-p_nom"]
    discharge_efficiency = n.links.at["battery_discharger", "efficiency"]
    n.model.add_constraints(p_nom.loc["battery_charger"] - discharge_efficiency * p_nom.loc["battery_discharger"] == 0,
                            name="battery_inverter_rating")
    if not tie_store_levels:
        return
    store_level = n.model.variables["Store-e"]
    year_ends = pd.Series(snapshots, index=snapshots).groupby(snapshots.year).max()
    for year_end in year_ends.iloc[:-1]:
        n.model.add_constraints(store_level.loc[year_end] - store_level.loc[year_ends.iloc[-1]] == 0,
                                name=f"store_level_at_year_end_{year_end.year}")


def build_design_model_on_years(years: tuple[int, ...], clip_below: float = 0.0,
                                tie_break_cost: float = 0.0, tie_store_levels: bool = True,
                                min_load: float = 0.5) -> pypsa.Network:
    n = pypsa.Network(WORK_DIR / "base_network.nc")
    design_series = pd.concat([average_consecutive_hours(read_year_series_on_own_calendar(year)) for year in years])
    generator_columns = n.generators_t.p_max_pu.columns
    n.set_snapshots(design_series.index)
    n.snapshot_weightings.loc[:, "objective"] = HOURS_PER_STEP / len(years)
    n.snapshot_weightings.loc[:, ["stores", "generators"]] = float(HOURS_PER_STEP)
    capacity_factors = design_series[generator_columns]
    n.generators_t.p_max_pu = capacity_factors.where(capacity_factors >= clip_below, 0.0)
    n.links.at["h2-dri", "p_min_pu"] = min_load
    zero_cost_links = n.links.index[n.links.marginal_cost == 0]
    n.generators.loc[n.generators.marginal_cost == 0, "marginal_cost"] = tie_break_cost
    n.links.loc[zero_cost_links, "marginal_cost"] = tie_break_cost
    n.optimize.create_model()
    add_battery_tie_and_year_end_store_levels(n, n.snapshots, tie_store_levels)
    return n


def build_on_off_operation_model() -> pypsa.Network:
    sys.path.insert(0, os.environ["EBRO_OPERATION_MODEL_DIR"])  # holds ebro_continuous_operation.py
    import ebro_continuous_operation as eco
    design_spec = eco.DESIGNS["single-2025"]
    design = pypsa.Network(design_spec["path"])
    _, lost_tonne_price, _ = eco.design_prices(design)
    n = eco.operating_network(design, eco.continuous_series(), lost_tonne_price, 24, design_spec["min_load"],
                              design_spec["ramp"])
    n.stores["e_cyclic"] = True
    n.optimize.create_model(linearized_unit_commitment=True)
    return n


for name in sys.argv[1:]:
    start = time.time()
    # NAME = design [c<k>] [m<j>]: c clips capacity factors below 1e-k to 0, m puts a tie-break cost of 1e-j
    # (EUR/MWh) on every zero-cost generator and link; f leaves store levels free across year ends (cyclic once);
    # l<d> sets the shaft minimum load to d/10 instead of 0.5; design is d1/d5/d10/d26 or y<first>-<last>, e.g. y2008-2017m2
    parts = re.fullmatch(r"(?P<design>d\d+|y\d{4}-\d{4}|op26)(c(?P<clip>\d+))?(m(?P<tie>\d+))?(?P<free>f)?(l(?P<load>\d))?", name)
    design_name = parts["design"]
    if design_name.startswith("y"):
        first, last = design_name[1:].split("-")
        DESIGN_YEARS[design_name] = tuple(range(int(first), int(last) + 1))
    clip_below = 10.0 ** -int(parts["clip"]) if parts["clip"] else 0.0
    tie_break_cost = 10.0 ** -int(parts["tie"]) if parts["tie"] else 0.0
    n = (build_on_off_operation_model() if name == "op26"
         else build_design_model_on_years(DESIGN_YEARS[design_name], clip_below, tie_break_cost,
                                                   tie_store_levels=not parts["free"],
                                                   min_load=int(parts["load"]) / 10 if parts["load"] else 0.5))
    lp_path = WORK_DIR / "lps" / f"{name}.lp"
    n.model.to_file(lp_path)
    print(f"{name}: written in {time.time() - start:.0f} s to {lp_path}", flush=True)
