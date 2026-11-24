# HiPO options for multi-year energy design LPs

This repository is HiGHS 1.16.0 (upstream commit `f3f113d`) plus commits that add nine options to HiPO, HiGHS's interior-point solver. Their defaults reproduce stock HiGHS exactly; set them, and
HiPO solves every steel-plant design and operation LP we have, where stock HiPO fails on most multi-year designs.
This folder holds the findings, the benchmark scripts and the results.

## Bottom line
- **Stock HiPO fails on most of our 10- and 26-year designs.** It mistakes slow progress for stagnation, throws its
  progress away and hands over to IPX, which then takes hours.
- **With the options below it solves all of them, 10-100x faster than IPX**, with objectives matching IPX to about
  1e-8. A 26-year design takes about 3 minutes instead of 2.5-5 hours; a 26-year hourly operation
  run about 5.5 minutes instead of 4.9 hours.
- **Threads do not help** on these LPs: HiPO picks its serial factorisation. Run several single-thread solves side by
  side instead, limited by memory (3.5 GB per 26-year design, 7-9 GB per 26-year operation run).

## Recommended options
```python
solver_options = {"solver": "hipo", "run_crossover": "off", "threads": 1,
                  "hipo_correctors": 3, "hipo_stagnation_min_progress": 0.1,
                  "hipo_feasibility_tolerance_factor": 0.1, "hipo_primal_regularisation": 1e-10,
                  "hipo_dual_regularisation": 1e-8, "hipo_check_best_iterate": True,
                  "ipm_iteration_limit": 500}
```

| Option | Default | Recommended | What it does |
|---|---|---|---|
| `hipo_correctors` | -1 (automatic) | 3 | Centrality correctors per iteration. Automatic weighs factorisation cost against solve cost and gives 1 for our LPs |
| `hipo_stagnation_min_progress` | 0 (off) | 0.1 | A run of short steps is not stagnation if primal infeasibility, dual infeasibility or the gap fell by at least this fraction over it |
| `hipo_max_short_steps` | 5 | 5 | Short steps in a row before the stagnation test |
| `hipo_short_step` | 0.05 | 0.05 | Step length (fraction of the way to the boundary) below which a step counts as short |
| `hipo_feasibility_tolerance_factor` | 1 | 0.1 | HiPO stops at this multiple of the feasibility tolerance, so the final check after postsolve passes |
| `hipo_corrector_min_increase` | 0.01 | 0.01 | Step increase a corrector must bring to be kept |
| `hipo_primal_regularisation` | 1e-12 | 1e-10 | Static primal regularisation added to the pivots of the Newton system |
| `hipo_dual_regularisation` | 1e-10 | 1e-8 | Static dual regularisation added to the pivots of the Newton system |
| `hipo_check_best_iterate` | false | true | When HiPO cannot go on (it stalls, or its direction is NaN with no factorisation left), its best iterate goes to the final KKT check before the current one |
| `ipm_iteration_limit` (existing) | 200 | 500 | The hardest design (26 years, min load 0) needs about 160 iterations |

## Why stock HiPO fails, read from the 1.16.0 source and the logs
Two different things look alike to HiPO: both are runs of short steps.

| | Mid-run short steps | End-game breakdown |
|---|---|---|
| Steps | 0.02-0.15 of the way to the boundary | exactly 0 |
| Progress | infeasibility and gap fall a few % per iteration | none; the iterate is frozen |
| Cause | poorly centred iterates, only one corrector | the serial up-looking factorisation loses accuracy near the optimum |
| Right response | keep going; more correctors | switch to the multifrontal factorisation at once |
| Stock rule (5 short steps) | misfires | right; this is why the rule exists |

What happens in a failing run:
1. **One corrector.** `Solver::chooseNumberOfCorrectors` compares factorisation and solve effort. Our factors are
   large but cheap to compute (d10: 1.1e7 nonzeros, 1.9e8 flops), so it picks the minimum of one.
2. **Short steps.** With one corrector about 40 % of steps are shorter than 0.05.
3. **False stagnation.** Five short steps in a row trigger the stagnation response while the run is still making
   progress.
4. **Reset to the start.** The response switches factorisation and resets to the "best" iterate, by
   max(pinf/feas_tol, dinf/feas_tol, gap/opt_tol). Our starting points have a small relative gap, so the best
   iterate is often iteration 0 and all progress is lost.
5. **IPX from the start.** The second stagnation ends HiPO; IPX restarts from that same "best" point and takes hours.

The fix keeps the stagnation rule for real stalls and adds a progress test for slow-but-real progress, and raises the
corrector count so steps are longer in the first place. The progress test compares the current iterate with the
one before the run of short steps; the existing "best iterate" measure cannot be used, because it stays at
iteration 0 for dozens of iterations. Each part alone is not enough: the progress test alone failed on one 10-year
window (2012-2021); three correctors with the stock rule failed on the 26-year design. Raising the short-step count
instead (to 20) also works, but wastes up to 20 iterations in the end-game breakdown.

### A third problem: the linear algebra breaks down just short of optimal
The first two fixes left about 1 % of LPs failing in the last iterations, with infeasibilities near 1e-10 and
the gap within a factor of 10-20 of its target. Near the optimum the scaling of the Newton system spans 1e-12 to 1e13,
and the solves lose all accuracy (linear-solve residual up to 1). Three outcomes were seen:
- **NaN with no factorisation left** (Spanish plant 2016-2025 and 2000-2025 with free stores, an Ebro cell 2006-2015):
  the up-looking factorisation returned a NaN direction, HiPO switched to the multifrontal one, which returned NaN
  too, and HiPO ended with "Internal error", discarding a nearly optimal point.
- **Degraded last iterate** (Australian cell -25.00, 118.25, 2003-2012): after the switch, two more steps made the
  iterate worse; HiPO then stalled and KKT-checked that degraded iterate, which passed inside HiPO at 80x the tolerance
  (100x allowed) but failed after postsolve at 240x, so HiGHS reported "Unknown".
- **Normal finish, failed after postsolve** (an Australian single year, 2015; 17 Australian single-year designs fell
  back to simplex, all in 2000, 2001 and 2013-2015, the years added last): HiPO met its targets
  and its own check passed at 41x, but the same absolute row error is measured against a bound norm of 342 inside
  HiPO and 114 after postsolve, so it failed there at 121x.

**Fix at the root: more static regularisation.** HiPO adds a fixed 1e-12 (primal) and 1e-10 (dual) to the pivots of
its Newton system; at 1e-10 and 1e-8 all of the above solve without a NaN and pass the final check within tolerance,
with objectives within 1e-9 of simplex's (before: 2e-8). The hardest Ebro designs keep their objectives and need
similar or fewer iterations (26 years at min load 0: 111 instead of 156).

**Safety net: the best iterate.** Stock HiPO returns its best iterate on every failure path except these two: when it
stalls for good it checks its current iterate, and when the direction is NaN with no factorisation left it returns
nothing. With `hipo_check_best_iterate` it offers its best iterate to the final check first, and the current one if
that fails. Without the regularisation, this alone rescued the first two outcomes (final check at 1.4-94x), but not
the third.

Not taken: a tighter `primal_residual_tolerance` (1e-8) gives HiPO's own check a margin and fixed the third outcome,
but it also made the rescued best iterate of the Ebro cell fail the check. Two or four correctors instead of three
avoided some breakdowns by taking a different path, which does not prevent them elsewhere.

The other safeguards are unchanged: collapsing directions (dx/x below 1e-30 of its largest), infeasibility jumping
by 1e12, divergence tests for infeasible or unbounded problems, and "HiPO stagnated but HiGHS considers the solution
acceptable" at the end.

## What did not work (options and formulation, before patching)
| Tried | Result |
|---|---|
| Bound scaling (`user_bound_scale` -5, -10, -15) | A lottery: each value fixes some windows and breaks others; 2008-2017 failed at all three |
| Cost scaling (`user_cost_scale`) | No effect; HiPO normalises costs, iterates are bit-identical |
| `hipo_factor=multifrontal` from the start | Worse: removes HiPO's one switch, so the first stagnation ends the run |
| `hipo_system=normaleq` | Solve error |
| Tighter `primal_feasibility_tolerance` | Also tightens the final check, so the "Unknown" status moves to other runs |
| Tie-break costs of 0.01 and 0.1 EUR/MWh on zero-cost dispatch | No help |
| Clipping capacity factors below 1e-3 or 1e-2 to zero | One success, one failure |
| Dropping the year-end store ties | Stock HiPO then succeeds, but it is a different model |

## Results
Mac (M1 Max VM, Apple Accelerate), 1 thread, recommended options; IPX times from earlier runs of the same LPs.

| LP | IPX | Stock HiPO | HiPO, recommended options | LCOS (EUR/t), HiPO vs IPX |
|---|---|---|---|---|
| Design, 1 year (2025) | 34 s | optimal, 3 s | optimal, 4 s | 1060.2655705 vs 1060.2655686 |
| Design, 5 years (2015-19) | 669 s | optimal, 20 s | optimal, 22 s | 1058.2505893 vs 1058.2505884 |
| Design, 10 years (2016-25) | 44-51 min | fails, IPX takes over | optimal, 52 s | 1069.1828731 vs 1069.1828725 |
| Design, 26 years, min load 0.5 | 155-299 min | fails | optimal, 185 s | 1072.2398788 vs 1072.2398784 |
| Design, 26 years, min load 0.2 | 2.2 h (AWS, after HiPO failed) | fails (Mac and AWS) | optimal, 188 s | 1032.7415210 vs 1032.7415207 |
| Design, 26 years, min load 0 | hours | not run | optimal, 550 s | 1032.6938549 vs 1032.6937802 (7e-8) |
| Operation, 26 years hourly, on/off shaft | 4.9 h | optimal, 333 s | optimal, 358 s | objective 8.3434795536e9 vs 8.3434795525e9 |

All 13 design windows (five of 5 years, eight of 10 years, from 2000-2025): stock HiPO failed on 4 of the 8 ten-year
windows; with the recommended options all 13 solved in 18-65 s each, plus a 10-year window at min load 0.2 in 63 s.
Peak memory: 3.5 GB for a 26-year design, 7.2 GB for the 26-year operation run.

Australia and Spain (Mac, the options without regularisation and `hipo_check_best_iterate`): 466 of 467 Australian
10-year windows with year-end ties, and 1,949 of 1,971 cell designs and 4 of 6 Spanish plant designs with free stores,
optimal by HiPO, mostly in under a minute. The rest needed simplex, up to hours for the 26-year plant design. Five of
them, one of each kind above plus the two Spanish plant designs, re-solved with the regularisation: all optimal, with
objectives within 1e-9 of simplex's.

Linux (Ubuntu 26.04 x86_64, OpenBLAS, 1 thread): stock HiPO did not finish the 10-year design in 400 s or the 26-year
design in 900 s; with the recommended options they took 77 s and 348 s.

AWS (Graviton, stock HiGHS 1.16.0, 6 threads), 26-year designs: stock HiPO solved the three whose stores carry across
years in minutes; the one with year-end store ties at min load 0.2 fell back to IPX, which took 2.2 hours. The
year-end ties are what trip stock HiPO's stagnation rule (see "What did not work": without them stock HiPO succeeds).

The model's demo (18 small one-year solves): 173 s of solver time with HiPO (at most 19 s per solve), 1,107 s with
HiPO plus crossover, 4,324 s with simplex, HiGHS's default (up to 697 s per solve). Total cost, LCOS and capacities
agree across all three. Dispatch figures (generation, curtailment, storage throughput, losses, and costs allocated by
them) differ by up to 90 %, also between crossover and simplex: the model's dispatch is degenerate (curtailment and
storage cycling are free), so every solver may return a different one of many equally cheap patterns.

## Install
The released `highspy-extras` 1.16.0 wheel brings OpenBLAS (Linux), Metis and AMD; HiPO itself is in core HiGHS, so
only highspy needs building from this repo:
```bash
uv pip install --python <venv>/bin/python highspy-extras==1.16.0 <this repo>
```
- **Mac:** uses Apple Accelerate; builds in about 3 minutes.
- **Linux (x86_64 and arm64, e.g. AWS Graviton):** `hipo-tuning/linux/build_highspy.sh [VENV_DIR]`; needs gcc and
  uv, no system BLAS. Tested on Ubuntu 26.04 x86_64; arm64 untested.
- **Command line binary** (for `solve_lp_with_highs_cli.sh`):
  `cmake -S . -B build -DHIPO=ON -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=OFF && make -C build -j highs-bin highs_extras`.
  On Linux this needs a BLAS (`-DBUILD_OPENBLAS=ON`, or a system OpenBLAS).
- linopy ignores HiGHS's refusal of an unknown option, so with a stock highspy the `hipo_*` options are silently
  dropped. Check `Highs().setOptionValue("hipo_correctors", 3) == HighsStatus.kOk` before relying on them.

## Reproduce
LPs are exported from the Ebro design and operation models into `work/lps/` (not in git; `work/` also holds logs).
- `export_benchmark_lps.py NAME ...`: d1, d5, d10, d26, `y<first>-<last>` windows, op26, with suffixes `c<k>` (clip
  capacity factors below 1e-k), `m<j>` (tie-break cost 1e-j EUR/MWh), `f` (free store levels across year ends),
  `l<d>` (shaft minimum load d/10). Needs `work/base_network.nc` and the Ebro weather series (`EBRO_SERIES_DIR`), and for op26 the
  operation model script (`EBRO_OPERATION_MODEL_DIR`); these come from the steel study and are not in this repo.
- `solve_lp_with_highs_cli.sh BUILD_DIR LP LABEL [option=value ...]`: one solve with the command-line binary at
  log_dev_level 2, stopped as soon as HiPO hands over to IPX.
- `solve_lp_file.py LP SOLVER THREADS LABEL [option=value ...]`: the same through highspy, appending to
  `work/solves.csv`.
- `run_batch.sh FILE [N]`: run a file of command lines N at a time.
- `summarise_hipo_logs.py [glob]`: one line per log: status, iterations, short steps, longest run, resets, IPX
  take-over, time, objective, mean step, mean correctors.
- `progress_windows.py LOG ...`: progress over each window of five short steps.
- `check_pypsa_route.py`: the 1-year design through PyPSA and linopy with the recommended options.
- `linux/solve_lp.py`: a one-line-per-solve variant for remote machines.
- `results/solves.csv`: every highspy solve of the study.

## Caveats
- Tested on one plant and site (Ebro, Spain): 13 design windows of 1-26 years at three minimum loads, and one 26-year
  hourly operation LP. Other sites and grid-tied variants are untested.
- The end-game breakdown of the up-looking factorisation and the cost model for correctors look worth raising
  upstream; nothing has been sent.
