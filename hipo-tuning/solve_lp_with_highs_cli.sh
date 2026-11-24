#!/bin/zsh
# Solve work/lps/<LP>.lp with a HiGHS binary: BUILD_DIR LP LABEL [option=value ...]; HiPO, 1 thread, no crossover.
# Logs to work/logs/diag_<lp>_<label>.log at log_dev_level 2 and stops the solve once HiPO hands over to IPX.
B=${0:A:h}/work
cd $B
build=$1; lp=$2; label=$3; shift 3
log=logs/diag_${lp}_${label}.log; options_file=$B/opts/${lp}_${label}.txt
mkdir -p opts logs
{ echo "solver = hipo"; echo "run_crossover = off"; echo "log_dev_level = 2"; echo "threads = 1"
  for o in "$@"; do echo "${o%%=*} = ${o#*=}"; done } > $options_file
DYLD_LIBRARY_PATH=$build/lib /usr/bin/time -l $build/bin/highs --options_file $options_file $B/lps/$lp.lp > $log 2>&1 &
solve_pid=$!
while kill -0 $solve_pid 2>/dev/null; do
  if grep -q "Restarting with IPX" $log; then
    pkill -f "highs --options_file $options_file"
    echo "Stopped at IPX restart" >> $log
    break
  fi
  sleep 2
done
wait
