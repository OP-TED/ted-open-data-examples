#!/usr/bin/env python3
"""Fail if web-library.yaml lists two entries whose `sparql:` paths share
a basename.

Why this matters
----------------

The ted-open-data web app's query library fetcher and
`extract-query-parameters.js` key a JSON lookup table by the basename of
each `sparql:` path (`query.sparql.split('/').pop()`), not the full path.
If this file ever listed two entries whose paths differ but share a
basename (e.g. two files both named `notices-per-day.sparql` in
different folders), the web app would silently mismatch/collide the
wrong query text with the wrong entry — no error, just wrong behaviour
downstream.

This script parses the YAML file(s) given on the command line (defaults
to `web-library.yaml` at the repo root), extracts the basename of every
entry's `sparql:` path, and exits non-zero with a clear message if any
basename is shared by more than one distinct path.

Usage:
    python3 ci/check_unique_basenames.py [file.yaml ...]
"""

from __future__ import annotations

import pathlib
import sys
from collections import defaultdict

try:
    import yaml
except ImportError:
    sys.stderr.write("ERROR: PyYAML not installed. pip install pyyaml\n")
    sys.exit(2)


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_LIBRARY_YAML = REPO_ROOT / "web-library.yaml"


def collect_paths(library_yaml: pathlib.Path) -> list[str]:
    """Return the list of non-empty `sparql:` path strings in a library
    YAML file."""
    if not library_yaml.is_file():
        sys.stderr.write(f"ERROR: {library_yaml} not found.\n")
        sys.exit(2)

    library = yaml.safe_load(library_yaml.read_text(encoding="utf-8")) or {}
    if not isinstance(library, dict):
        sys.stderr.write(
            f"ERROR: {library_yaml} does not parse to a mapping with a "
            f"'queries' list at the top level.\n"
        )
        sys.exit(2)
    queries = library.get("queries") or []
    if not isinstance(queries, list):
        sys.stderr.write(
            f"ERROR: {library_yaml} has a 'queries' key that is not a "
            f"list: {queries!r}\n"
        )
        sys.exit(2)

    paths = []
    for q in queries:
        if not isinstance(q, dict):
            sys.stderr.write(
                f"ERROR: {library_yaml} has a 'queries' entry that is not "
                f"a mapping: {q!r}\n"
            )
            sys.exit(2)
        sparql_rel = (q.get("sparql") or "").strip()
        if sparql_rel:
            paths.append(sparql_rel)
    return paths


def find_basename_collisions(paths: list[str]) -> dict[str, set[str]]:
    """Group paths by basename and return only the basenames that map to
    more than one distinct path."""
    by_basename: dict[str, set[str]] = defaultdict(set)
    for path in paths:
        basename = path.split("/")[-1]
        by_basename[basename].add(path)

    return {
        basename: distinct_paths
        for basename, distinct_paths in by_basename.items()
        if len(distinct_paths) > 1
    }


def main() -> int:
    library_files = [pathlib.Path(p) for p in sys.argv[1:]] or [DEFAULT_LIBRARY_YAML]

    exit_code = 0
    for library_yaml in library_files:
        paths = collect_paths(library_yaml)
        collisions = find_basename_collisions(paths)

        if collisions:
            exit_code = 1
            sys.stderr.write(
                f"ERROR: {library_yaml} contains {len(collisions)} basename "
                f"collision(s) among `sparql:` paths.\n"
                "The web app's query fetcher keys its lookup table by "
                "basename, so entries with different paths but the same "
                "filename will silently collide.\n\n"
            )
            for basename, distinct_paths in sorted(collisions.items()):
                sys.stderr.write(f"  {basename!r} is used by {len(distinct_paths)} paths:\n")
                for path in sorted(distinct_paths):
                    sys.stderr.write(f"    - {path}\n")
            sys.stderr.write("\n")
        else:
            print(f"OK: {library_yaml} — {len(paths)} entries, no basename collisions.")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
