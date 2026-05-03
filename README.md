# ted-open-data-examples

Curated SPARQL examples for querying the [**TED Open Data Service**](https://data.ted.europa.eu/) — the EU's public procurement data published as RDF.

This is a **knowledge product** consumed by multiple TED tools. Each consumer reads its own index file at the repo root; the `.sparql` files themselves are a shared pool.

| Consumer | Index file | Purpose |
|---|---|---|
| **TED Open Data Service** ([`OP-TED/ted-open-data`](https://github.com/OP-TED/ted-open-data)) | `web-library.yaml` | Populates the editor's "Query Library" tab |
| **TED Open Data Assistant** | `web-library.yaml` (today), evolving to `llm-knowledge.yaml` as it gets curated | Example-driven knowledge for natural-language SPARQL generation |

A query may appear in either index, both, or neither — the indexes are independent curated views over the same pool.

The assistant currently indexes the same examples that drive the web app (`web-library.yaml`) — this gets the assistant grounded in the curated examples immediately. As [`llm-knowledge.yaml`](llm-knowledge.yaml) gets populated with assistant-specific intent metadata and any LLM-only examples, the assistant will switch to it as its primary source.

## Layout

```
.
├── README.md
├── LICENSE                  # CC BY 4.0
├── CONTRIBUTING.md          # how to add or fix a query
├── web-library.yaml         # web app's Query Library tab + (today) assistant's RAG source
├── llm-knowledge.yaml       # assistant-specific overlay — planned/curated, not yet indexed
├── queries/                 # the .sparql pool — organise as you wish
│   └── *.sparql
├── ci/
│   └── reindex.py           # refreshes the assistant's RAG index from web-library.yaml
└── .github/workflows/
    └── reindex-queries.yml  # runs ci/reindex.py on every push to main
```

The data is modelled with the [**eProcurement Ontology (ePO)**](https://github.com/OP-TED/ePO) v4.x. The SPARQL endpoint is:

```
https://publications.europa.eu/webapi/rdf/sparql
```

## Consuming this from your tool

Pick the index that matches your use case and read it via the GitHub raw URL. Each entry's `sparql:` field is a path relative to the repo root.

```
https://raw.githubusercontent.com/OP-TED/ted-open-data-examples/main/web-library.yaml
https://raw.githubusercontent.com/OP-TED/ted-open-data-examples/main/llm-knowledge.yaml
https://raw.githubusercontent.com/OP-TED/ted-open-data-examples/main/<sparql-path>
```

A consumer typically:

1. Fetches its index file
2. For each entry, fetches the file at `sparql:`
3. Indexes / displays / processes them as needed

### `web-library.yaml` schema

```yaml
- category: Notices
  title: Information about notices published on a specific date
  description: This query retrieves information ... published on a specific date.
  sparql: queries/notices-per-day.sparql
```

### `llm-knowledge.yaml` schema

See the header comment in [`llm-knowledge.yaml`](llm-knowledge.yaml). Each entry describes the *intent* the example answers, the ePO terms used, and any gotchas worth grounding the assistant on.

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md). In short: open a PR against `develop`; entries are published when `develop` merges to `main`.

When `develop` merges to `main`, a GitHub Action ([reindex-queries.yml](.github/workflows/reindex-queries.yml)) automatically refreshes the TED Open Data Assistant's RAG index from `web-library.yaml` so newly added queries become available to the assistant. No manual reindexing step is needed.

## License

The query examples and documentation in this repository are licensed under [Creative Commons Attribution 4.0 (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/) — see [`LICENSE`](LICENSE).