#!/bin/bash
# Build this repo's highspy into a Python 3.12 venv on Linux (x86_64 or arm64), with the released extras package,
# which brings OpenBLAS, Metis and AMD prebuilt, so no system BLAS is needed. Needs gcc/g++ and uv.
# Run: build_highspy.sh [VENV_DIR]   (default: .venv next to the repo checkout)
set -euo pipefail
repo_dir=$(cd "$(dirname "$0")/../.." && pwd)
venv_dir=${1:-$repo_dir/../.venv-highs-hipo}
[ -d "$venv_dir" ] || uv venv -q --python 3.12 "$venv_dir"
export CMAKE_BUILD_PARALLEL_LEVEL=${CMAKE_BUILD_PARALLEL_LEVEL:-$(nproc)}
uv pip install -q --python "$venv_dir/bin/python" highspy-extras==1.16.0 "$repo_dir"
"$venv_dir/bin/python" -c "import highspy; h = highspy.Highs(); h.setOptionValue('output_flag', False); \
print(h.version(), 'hipo_correctors accepted:', h.setOptionValue('hipo_correctors', 3) == highspy.HighsStatus.kOk)"
