#!/usr/bin/env bash
set -euo pipefail

blocked_paths=(
  "docs/"
  "first_prompt.txt"
  "first_prompt.md"
  "dev_prompt.txt"
  "dev_prompt.md"
  "PLAN.md"
  ".private/"
  "internal/"
)

violations=()
for path in "${blocked_paths[@]}"; do
  while IFS= read -r tracked; do
    [ -n "$tracked" ] && violations+=("$tracked")
  done < <(git ls-files -- "$path")
done

if [ ${#violations[@]} -gt 0 ]; then
  echo "Blocked private/development files are tracked in git:" >&2
  printf ' - %s\n' "${violations[@]}" >&2
  exit 1
fi

echo "Private file policy check passed."
