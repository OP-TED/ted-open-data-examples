# Contributing to TED Open Data Examples

This repository hosts SPARQL examples for the [TED Open Data Service](https://data.ted.europa.eu/). The examples are consumed by two tools, each via its own index file at the repo root:

| Index | Consumer | What it lists |
|---|---|---|
| `web-library.yaml` | TED Open Data Service web app | Queries shown in the editor's "Query Library" tab |
| `llm-knowledge.yaml` | TED Open Data Assistant | Examples used as RAG knowledge to ground SPARQL generation |

A query may appear in either index, both, or neither — they are independent curated views. The `.sparql` files themselves are a shared pool, organised under [`queries/`](queries/) (or any folder you prefer).

The live tools read from the `main` branch. Open pull requests against `develop`; entries are published when `develop` is merged to `main`.

## Adding a new query

1. **Write the `.sparql` file.** Place it under [`queries/`](queries/) or a sensible subfolder. Follow the [writing guidelines](#writing-guidelines) below.

2. **Add it to the index(es) that should expose it.** Each entry's `sparql:` field is a path relative to the repo root.

   - For the **web app**, add an entry to [`web-library.yaml`](web-library.yaml):

     ```yaml
     - category: Notices
       title: Your query title
       description: A clear description of what the query does and what results it returns.
       sparql: queries/your-query.sparql
     ```

   - For the **assistant**, add an entry to [`llm-knowledge.yaml`](llm-knowledge.yaml). The schema is documented in the file's header. The TED Open Data Assistant team curates this index — feel free to suggest entries; you are not required to populate it.

3. **Open a pull request against `develop`.** Your query will be published with the next release (when `develop` is merged to `main`).

## Fixing an existing query

1. Edit the `.sparql` file.
2. If the title or description need updating, edit the relevant index file too.
3. Test the query on the [TED Open Data Service](https://data.ted.europa.eu/) before submitting.
4. Open a pull request against `develop` describing what you changed and why.

## Writing guidelines

These apply to every query, regardless of which index lists it.

### Comments

Every query should include comments that explain:
- What the query does (brief summary at the top)
- What each major section of the WHERE clause is doing
- Any non-obvious joins or filters

```sparql
# Retrieves the amount awarded per tender for notices published on a specific date.
# Returns: publication number, tender identifier, awarded amount, and currency.

PREFIX epo: <http://data.europa.eu/a4g/ontology#>
...

WHERE {
  # Filter by publication date
  FILTER (?publicationDate = "2024-11-04"^^xsd:date)

  GRAPH ?g {
    # Get the notice and its publication details
    ?notice a epo:Notice ;
            epo:hasPublicationDate ?publicationDate ;
            epo:hasNoticePublicationNumber ?publicationNumber .

    # Link notice to procedure explicitly for performance
    ?notice epo:refersToProcedure ?procedure .

    # Get the tender and its awarded amount
    ?tender epo:isSubmittedForLot ?lot ;
            epo:hasFinancialOfferValue ?offerValue .
    ...
  }
}
```

### Explicit joins

Always include explicit links between entities, even when the named graph boundary makes the query work without them. For example, always link notices to procedures:

```sparql
# Good: explicit join
?notice epo:refersToProcedure ?procedure .
?procedure a epo:Procedure .

# Avoid: relying on named graph boundary alone
?procedure a epo:Procedure .
```

Explicit joins improve query performance and make the query logic clear to readers.

### Prefixes

Use the standard prefixes consistently:

```sparql
PREFIX epo: <http://data.europa.eu/a4g/ontology#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX adms: <http://www.w3.org/ns/adms#>
PREFIX dc: <http://purl.org/dc/elements/1.1/>
PREFIX dcterms: <http://purl.org/dc/terms/>
PREFIX org: <http://www.w3.org/ns/org#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
```

Only include prefixes that are actually used in the query.

### Parameterisation

Use date filters like `FILTER (?publicationDate = "2024-11-04"^^xsd:date)` with a recent date so users can see results immediately. Users will change the date to suit their needs.

For queries that filter by a specific identifier (e.g. publication number or procedure ID), use `VALUES` with a real example value and add a comment explaining what to change:

```sparql
# Change the publication number below to look up a different notice
VALUES ?publicationNumber { "00676595-2024" }
```

## Web library categories

`web-library.yaml` groups entries into categories that the web app uses for navigation. Current categories:

- **Notices** — queries about procurement notices and their metadata
- **Tenders** — queries about tender submissions and awarded amounts
- **Procedures** — queries about procurement procedures and their details
- **Organisations** — queries about buyers, winners, and other organisations
- **Advanced queries** — queries for power users (RDF retrieval, named graphs, etc.)
- **Stats** — aggregations and counts over the data

New categories can be added by simply using a new category name in `web-library.yaml`.