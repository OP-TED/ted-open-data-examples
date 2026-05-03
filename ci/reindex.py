#!/usr/bin/env python3
"""Refresh the ted-open-data-assistant-queries index in deepset Cloud
from this repo's web-library.yaml.

Indexing strategy
-----------------

Each query becomes one Haystack Document with a **stable ID derived from
its `sparql_path`**. We pre-fetch each .sparql file's text from GitHub
raw in Python, build Document dicts with explicit `id`, `content`, and
`meta`, then submit them to a small embed→write pipeline on deepset
Cloud via `POST /haystack/pipelines/run` (workspace-scoped form).

Stable IDs make `policy: OVERWRITE` actually idempotent across content
or metadata edits — the same `.sparql` always lands at the same OpenSearch
document ID, replacing the previous version in place.

The remaining failure mode is **renames and removals from
web-library.yaml**: those produce a new ID (rename) or no ID (removal)
for the new state, leaving the old document orphaned. deepset Cloud
exposes no document-delete or query-delete endpoint at the time of
writing, and we cannot delete + recreate the Index resource because the
deployed assistant pipeline references it. Treat orphans as a rare,
low-impact issue and clear them with an out-of-band manual recreate
(undeploy assistant → delete index resource → recreate → redeploy)
when needed. Track such cleanups via the project's ops runbook.

Required env:
    HAYSTACK_API_KEY    deepset Cloud Service Key (workspace editor)
    HAYSTACK_WORKSPACE  e.g. OP_C3_PLAYGROUND

Optional env (defaults shown):
    HAYSTACK_API_BASE   https://api.cloud.deepset.ai
    GITHUB_REPOSITORY   OP-TED/ted-open-data-examples   (set by Actions)
    INDEX_REF           the ref/SHA to fetch raw URLs from. Should match
                        whatever was checked out. Falls back to GITHUB_SHA,
                        then GITHUB_REF_NAME, then 'main'.

Endpoint note: deepset Cloud exposes both
`/api/v1/haystack/pipelines/run` (global) and
`/api/v1/workspaces/{ws}/haystack/pipelines/run` (workspace-scoped).
We use the workspace-scoped form to match every other v1 endpoint.
"""

from __future__ import annotations

import json
import os
import pathlib
import sys
import urllib.error
import urllib.request

try:
    import yaml
except ImportError:
    sys.stderr.write("ERROR: PyYAML not installed. pip install pyyaml\n")
    sys.exit(2)


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
LIBRARY_YAML = REPO_ROOT / "web-library.yaml"

INDEX_NAME = "ted-open-data-assistant-queries"
BATCH_SIZE = 50

# Embed-then-write pipeline. The input shape is a list of Document dicts
# directly (no fetcher/converter); the embedder produces embeddings and
# the writer persists with policy: OVERWRITE on the explicit IDs we set.
INDEXER_PIPELINE = """\
components:

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
  - sender: document_embedder.documents
    receiver: writer.documents

inputs:
  documents:
    - document_embedder.documents

outputs:
  documents_written: writer.documents_written

max_runs_per_component: 100
"""


def _request(method: str, url: str, headers: dict, body: dict | None = None) -> tuple[int, dict | str]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    for k, v in headers.items():
        req.add_header(k, v)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            text = resp.read().decode("utf-8")
            return resp.status, (json.loads(text) if text else {})
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8", errors="replace")
        try:
            return e.code, json.loads(body_text)
        except Exception:
            return e.code, body_text


def fetch_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"Accept": "text/plain"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8")


def chunked(seq: list, n: int):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def build_documents(library: dict, raw_base: str) -> list[dict]:
    """Fetch each query's text and build a list of Document dicts with
    explicit IDs derived from `sparql_path`."""
    queries = library.get("queries") or []
    docs: list[dict] = []
    skipped = 0
    for q in queries:
        sparql_rel = (q.get("sparql") or "").strip()
        if not sparql_rel:
            skipped += 1
            continue
        url = raw_base + sparql_rel
        text = fetch_text(url)
        meta = {
            "title": (q.get("title") or "").strip(),
            "description": (q.get("description") or "").strip(),
            "category": (q.get("category") or "").strip(),
            "sparql_path": sparql_rel,
            "source_url": url,
            "source": "web-library.yaml",
        }
        # Stable id: path within the repo. Same path → same OpenSearch _id
        # → policy: OVERWRITE replaces in place.
        docs.append({
            "id": sparql_rel,
            "content": text,
            "meta": meta,
        })
    if skipped:
        print(f"    note: skipped {skipped} entries with empty sparql field")
    return docs


def run_indexer(
    api_base: str, workspace: str, headers: dict, documents: list[dict]
) -> tuple[int, int]:
    pipeline_config = yaml.safe_load(INDEXER_PIPELINE)
    run_url = f"{api_base}/api/v1/workspaces/{workspace}/haystack/pipelines/run"
    total_written = 0
    total_failed = 0
    batches = list(chunked(documents, BATCH_SIZE))

    for i, batch in enumerate(batches, start=1):
        body = {
            "pipeline_config": pipeline_config,
            "inputs": {"document_embedder": {"documents": batch}},
            "include_outputs_from": ["writer"],
        }
        status, resp = _request("POST", run_url, headers, body)
        if status != 200:
            sys.stderr.write(
                f"    batch {i}/{len(batches)} FAILED (HTTP {status}): "
                f"{json.dumps(resp)[:400]}\n"
            )
            total_failed += len(batch)
            continue
        written = (
            (resp.get("writer") or {}).get("documents_written")
            or ((resp.get("result") or {}).get("writer") or {}).get("documents_written")
            or 0
        )
        total_written += written
        print(
            f"    batch {i}/{len(batches)}: "
            f"{len(batch)} docs → {written} written"
        )
    return total_written, total_failed


def main() -> int:
    api_key = os.environ.get("HAYSTACK_API_KEY")
    api_base = os.environ.get("HAYSTACK_API_BASE", "https://api.cloud.deepset.ai")
    workspace = os.environ.get("HAYSTACK_WORKSPACE")
    repo = os.environ.get("GITHUB_REPOSITORY", "OP-TED/ted-open-data-examples")
    # Prefer an explicit ref/SHA the workflow has captured after checkout.
    # On workflow_dispatch with `inputs.ref` overridden, the workflow MUST
    # set INDEX_REF to the actually-checked-out SHA so that the local YAML
    # we read and the .sparql files we fetch come from the same ref.
    ref = (
        os.environ.get("INDEX_REF")
        or os.environ.get("GITHUB_SHA")
        or os.environ.get("GITHUB_REF_NAME")
        or "main"
    )

    if not api_key or not workspace:
        sys.stderr.write(
            "ERROR: HAYSTACK_API_KEY and HAYSTACK_WORKSPACE must be set.\n"
        )
        return 2

    if not LIBRARY_YAML.is_file():
        sys.stderr.write(f"ERROR: {LIBRARY_YAML} not found.\n")
        return 2

    library = yaml.safe_load(LIBRARY_YAML.read_text(encoding="utf-8")) or {}
    raw_base = f"https://raw.githubusercontent.com/{repo}/{ref}/"

    print(f"==> Repo:      {repo}")
    print(f"==> Ref:       {ref}")
    print(f"==> Workspace: {workspace}")
    print(f"==> Index:     {INDEX_NAME}")

    print(f"==> Fetching .sparql sources from {raw_base}")
    documents = build_documents(library, raw_base)
    print(f"==> Documents: {len(documents)}")
    if not documents:
        print("==> Nothing to index.")
        return 0

    headers = {"Authorization": f"Bearer {api_key}"}
    print(f"==> Indexing (batch size {BATCH_SIZE})")
    total_written, total_failed = run_indexer(api_base, workspace, headers, documents)

    print()
    print(f"==> Done. {total_written} document(s) written, {total_failed} failed.")
    return 0 if total_failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())