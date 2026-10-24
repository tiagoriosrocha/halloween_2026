#!/bin/zsh
cd "${0:A:h}" || exit 1
conda_executable="${CONDA_EXE:-}"
if [[ ! -x "$conda_executable" ]]; then
  conda_executable="$(command -v conda)"
fi
if [[ ! -x "$conda_executable" ]]; then
  for candidate in "$HOME/miniconda3/bin/conda" "$HOME/anaconda3/bin/conda" /opt/anaconda3/bin/conda /opt/miniconda3/bin/conda /opt/homebrew/bin/conda; do
    if [[ -x "$candidate" ]]; then
      conda_executable="$candidate"
      break
    fi
  done
fi
if [[ ! -x "$conda_executable" ]]; then
  print "Conda não encontrado. Siga as instruções do README.md."
  read "?Pressione Enter para fechar."
  exit 1
fi
"$conda_executable" run --no-capture-output -n halloween python main.py "$@"
result=$?
if (( result != 0 )); then
  read "?Pressione Enter para fechar."
fi
exit "$result"
