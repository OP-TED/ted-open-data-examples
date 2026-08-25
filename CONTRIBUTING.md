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
3. Open a pull request against `develop` describing what you changed and why.

## Before opening a pull request

Check each query you have changed:

- it runs on the [TED Open Data Service](https://data.ted.europa.eu/) and returns results
- its dates are recent enough that a first-time reader sees something
- every variable you named appears as a field, and nothing else does
- the labels are plain English, not variable names: "Published on", not "publicationDate"

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

### Variable names

Use the same name for the same thing in every query: `?publicationDate`, not `?pubDate` in some of them. Readers move between these queries, and where no label is given the form falls back to the variable name.

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

Give every query a real value, so that it runs as published and returns something. Use a recent date, a publication number that exists, an identifier that resolves.

```sparql
FILTER (?publicationDate = "2024-11-04"^^xsd:date)
VALUES ?publicationNumber { "00676595-2024" }
```

Then name the variables a reader may change, in a comment:

```sparql
# ?publicationDate: Published on
```

The web app offers a field for each variable named this way, so a reader can change the value without editing SPARQL. You declare only the label; the rest comes from the query:

| What the form needs | Where it comes from |
|---|---|
| the kind of field | the datatype of the literal: `xsd:date` gives a date field, `xsd:boolean` a checkbox |
| the starting value | the literal already in the query |
| whether it is a range | one `&&` joining two bounds, or two variables on one line |

A query with no such comment gets no form, and is otherwise unchanged. Only the variables you name are offered, and only where the variable itself is compared with a literal. In `FILTER(lang(?country) = "en")` the comparison is with a function of `?country`, so `"en"` is never offered.

#### Ranges

Two bounds on one variable are a range when a single `&&` joins them:

```sparql
# ?publicationDate: Publication date
FILTER (?publicationDate >= "2025-01-01"^^xsd:date && ?publicationDate <= "2025-01-31"^^xsd:date)
```

> **Publication date range**
> Between `2025-01-01` and `2025-01-31`

`>=` and `<=` appear as *between … and …*, `>` and `<` as *after …* and *… before …*. The form refuses a range given the wrong way round, so keep the query's own values in order.

The `&&` is what makes it a range. Two separate `FILTER`s constrain the same variable just as well, but nothing in them says the two limits are the ends of one period, so each gets a field of its own and neither is checked against the other. Join them if you mean a range.

Where the two ends are separate variables, declare both on one line, the start first:

```sparql
# ?startDate, ?endDate: Publication date
VALUES (?startDate ?endDate) { ("2024-11-04"^^xsd:date "2024-11-05"^^xsd:date) }
FILTER (?publicationDate >= ?startDate && ?publicationDate <= ?endDate)
```

That line is a statement, not a guess: it says these two are the ends of one range, wherever the query puts them. Declared separately, on two lines, they stay two independent fields.

Everything else — bounds in different `FILTER`s, either side of a `||`, in opposite arms of a `UNION` — is offered as ordinary fields with no ordering check. That is deliberate: the app never refuses to run a query on the strength of a guess about what its bounds mean together.

#### What cannot be offered

Any literal can be offered; a datatype with no field of its own gets a plain text box.

IRIs cannot. A full IRI is not something anyone can type into a form, so a variable bound to one gets no field, even if you name it. Name only the parts a reader can sensibly fill in.

## Web library categories

`web-library.yaml` groups entries into categories that the web app uses for navigation. Current categories:

- **Notices** — queries about procurement notices and their metadata
- **Tenders** — queries about tender submissions and awarded amounts
- **Procedures** — queries about procurement procedures and their details
- **Organisations** — queries about buyers, winners, and other organisations
- **Advanced queries** — queries for power users (RDF retrieval, named graphs, etc.)
- **Stats** — aggregations and counts over the data

New categories can be added by simply using a new category name in `web-library.yaml`.