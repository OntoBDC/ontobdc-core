#!/bin/bash
FULLHLINE() {
  local cols
  cols="$(tput cols 2>/dev/null || true)"
  if [ -z "$cols" ] || [ "$cols" -le 0 ] 2>/dev/null; then
    cols="${COLUMNS:-80}"
  fi
  printf '%*s' "$cols" '' | tr ' ' '-'
}

FULL_HLINE="$(FULLHLINE)"
