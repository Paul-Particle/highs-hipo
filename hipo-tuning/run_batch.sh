#!/bin/zsh
# Run each line of a batch file as a shell command, N at a time: run_batch.sh FILE [N]
cd ${0:A:h}
tr '\n' '\0' < $1 | xargs -0 -P ${2:-3} -I{} sh -c '{}'
echo "$1 done"
