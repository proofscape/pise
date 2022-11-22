#!/usr/bin/env bash

if [[ ! -z "$PFSC_RUN_AS_WORKER" ]]; then
    echo "Running as worker."
    exec python worker.py
elif [[ ! -z "$PFSC_RUN_AS_MATH_WORKER" ]]; then
    echo "Running as math worker."
    exec python worker.py pfsc-math-calc
elif [[ ! -z "$PFSC_RUN_AS_WEB_SERVER" ]]; then
    echo "Running as web server."
    exec python web.py
else
    # Legacy CMD-based control
    if test $1 = "worker"; then
      if test $2 = "math"; then
        echo "Running as math worker."
        exec python worker.py pfsc-math-calc
      else
        echo "Running as worker."
        exec python worker.py
      fi
    else
      if test $1 = "websrv"; then
        echo "Running as web server."
        exec python web.py
      else
          echo "Unknown command: $1"
      fi
    fi
fi
