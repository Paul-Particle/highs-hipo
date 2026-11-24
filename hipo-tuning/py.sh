#!/bin/zsh
# Run python ($1 = interpreter) with the lcox-steel conda env's PROJ/GDAL data (pypsa imports need them).
E=${LCOX_ENV:-$HOME/micromamba/envs/lcox-steel}
export PROJ_DATA=$E/share/proj GDAL_DATA=$E/share/gdal
PY=$1; shift
exec $PY "$@"
