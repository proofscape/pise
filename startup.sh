#!/bin/sh

if test $1 = "worker"; then
  if test $2 = "math"; then
    exec python worker.py pfsc-math-calc
  else
    exec python worker.py
  fi
else
  if test $1 = "websrv"; then
    exec python web.py
  else
      echo "Unknown command: $1"
  fi
fi
