#!/usr/bin/env python3
"""Refresh the ted-open-data-assistant-queries index in deepset Cloud
from this repo's web-library.yaml.

Reads web-library.yaml from the local checkout, builds a list of
`{url, meta}` entries pointing at the repo's queries/*.sparql files on
GitHub raw, then POSTs a transient indexer pipeline-run to deepset
Cloud's `/haystack/pipelines/run` endpoint. The pipeline fetches each
URL, embeds, and writes to OpenSearch with `policy: OVERWRITE` (so
re-runs are idempotent — same content/URL → same doc id → in-place
replace).

The indexer pipeline YAML is inlined below to keep this file
self-contained. It's a copy of
`tedsws-assistant/haystack/indexes/ted-open-data-assistant-queries.indexer.yaml`
— keep the two in sync if you change either.

Required env:
    HAYSTACK_API_KEY    deepset Cloud Service Key (workspace editor)
    HAYSTACK_WORKSPACE  e.g. OP_C3_PLAYGROUND

Optional env (defaults shown):
    HAYSTACK_API_BASE   https://api.cloud.deepset.ai
    GITHUB_REPOSITORY   OP-TED/ted-open-data-examples   (set by Actions)
    GITHUB_REF_NAME     main                            (set by Actions)
"""

from __future__ import annotations

import json
import os
import pathlib
import sys
import urllib.request

try:
    import yaml
except ImportError:
    sys.stderr.write("ERROR: PyYAML not installed. pip install pyyaml\n")
    sys.exit(2)


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
LIBRARY_YAML = REPO_ROOT / "web-library.yaml"

INDEXER_PIPELINE = """\
components:

  fetcher:
    type: haystack.components.fetchers.link_content.LinkContentFetcher
    init_parameters:
      retry_attempts: 2
      timeout: 30

  converter:
    type: haystack.components.converters.txt.TextFileToDocument
    init_parameters:
      encoding: utf-8

  document_embedder:
    type: deepset_cloud_custom_nodes.embedders.nvidia.document_embedder.DeepsetNvidiaDocumentEmbedder
    init_parameters:
      normalize_embeddings: true
      model: intfloat/e5-base-v2

  writer:
    type: haystack.components.writers.document_writer.DocumentWriter
    init_parameters:
      document_store:
        type: haystack_integrations.document_stores.opensearch.document_store.OpenSearchDocumentStore
        init_parameters:
          embedding_dim: 768
          index: ted-open-data-assistant-queries
          create_index: true
          settings:
            index.knn: true
      policy: OVERWRITE

connections:
  - sender: fetcher.streams
    receiver: converter.sources
  - sender: converter.documents
    receiver: document_embedder.documents
  - sender: document_embedder.documents
    receiver: writer.documents

inputs:
  urls:
    - fetcher.urls
  meta:
    - converter.meta

outputs:
  documents_written: writer.documents_written

max_runs_per_component: 100
"""

BATCH_SIZE = 50


def http_post_json(url: str, body: dict, headers: dict) -> tuple[int, dict | str]:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    for k, v in headers.items():
        req.add_header(k, v)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            text = resp.read().decode("utf-8")
            return resp.status, json.loads(text) if text else {}
    except urllib.error.HTTPError as e:  # type: ignore[attr-defined]
        body_text = e.read().decode("utf-8", errors="replace")
        try:
            return e.code, json.loads(body_text)
        except Exception:
            return e.code, body_text


def chunked(seq: list, n: int):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def main() -> int:
    api_key = os.environ.get("HAYSTACK_API_KEY")
    api_base = os.environ.get("HAYSTACK_API_BASE", "https://api.cloud.deepset.ai")
    workspace = os.environ.get("HAYSTACK_WORKSPACE")
    repo = os.environ.get("GITHUB_REPOSITORY", "OP-TED/ted-open-data-examples")
    ref = os.environ.get("GITHUB_REF_NAME", "main")

    if not api_key or not workspace:
        sys.stderr.write(
            "ERROR: HAYSTACK_API_KEY and HAYSTACK_WORKSPACE must be set.\n"
        )
        return 2

    if not LIBRARY_YAML.is_file():
        sys.stderr.write(f"ERROR: {LIBRARY_YAML} not found.\n")
        return 2

    library = yaml.safe_load(LIBRARY_YAML.read_text(encoding="utf-8")) or {}
    queries = library.get("queries") or []

    raw_base = f"https://raw.githubusercontent.com/{repo}/{ref}/"
    entries: list[tuple[str, dict]] = []
    skipped = 0
    for q in queries:
        sparql_rel = (q.get("sparql") or "").strip()
        if not sparql_rel:
            skipped += 1
            continue
        meta = {
            "title": (q.get("title") or "").strip(),
            "description": (q.get("description") or "").strip(),
            "category": (q.get("category") or "").strip(),
            "sparql_path": sparql_rel,
            "source": "web-library.yaml",
        }
        entries.append((raw_base + sparql_rel, meta))

    print(f"==> Repo:      {repo}@{ref}")
    print(f"==> Workspace: {workspace}")
    print(f"==> Entries:   {len(entries)} (skipped {skipped} with empty sparql)")

    if not entries:
        print("==> Nothing to index.")
        return 0

    pipeline_config = yaml.safe_load(INDEXER_PIPELINE)
    run_url = f"{api_base}/api/v1/workspaces/{workspace}/haystack/pipelines/run"
    headers = {"Authorization": f"Bearer {api_key}"}

    total_written = 0
    total_failed = 0
    batches = list(chunked(entries, BATCH_SIZE))

    for i, batch in enumerate(batches, start=1):
        urls = [u for u, _ in batch]
        metas = [m for _, m in batch]
        body = {
            "pipeline_config": pipeline_config,
            "inputs": {
                "fetcher": {"urls": urls},
                "converter": {"meta": metas},
            },
            "include_outputs_from": ["writer"],
        }
        status, resp = http_post_json(run_url, body, headers)
        if status != 200:
            sys.stderr.write(
                f"    batch {i}/{len(batches)} FAILED (HTTP {status}): "
                f"{json.dumps(resp)[:400]}\n"
            )
            total_failed += len(batch)
            continue
        written = (
            resp.get("writer", {}).get("documents_written")
            or resp.get("result", {}).get("writer", {}).get("documents_written")
            or 0
        )
        total_written += written
        print(
            f"    batch {i}/{len(batches)}: "
            f"{len(batch)} URLs → {written} documents written"
        )

    print()
    print(f"==> Done. {total_written} document(s) written, {total_failed} failed.")
    return 0 if total_failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())