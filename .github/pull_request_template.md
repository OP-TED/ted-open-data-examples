<!--
Thanks for contributing! Most PRs here add or fix a query example.
Pick the section(s) that apply and delete the rest.
-->

## Summary

<!-- One or two sentences: what does this PR do? -->

## What's in this PR

- [ ] New `.sparql` file(s) added under `queries/`
- [ ] Existing `.sparql` file(s) edited
- [ ] `web-library.yaml` updated (entries added / edited / removed)
- [ ] `llm-knowledge.yaml` updated (entries added / edited / removed)
- [ ] Documentation only (`README.md`, `CONTRIBUTING.md`, …)

## For new or edited queries

- [ ] The `.sparql` file follows the [writing guidelines](../CONTRIBUTING.md#writing-guidelines): top-level summary comment, only-used PREFIXes, explicit joins, parameterised with a real example value
- [ ] The query has been run against the live SPARQL endpoint (`https://publications.europa.eu/webapi/rdf/sparql`) and returns sensible results
- [ ] `sparql:` paths in the index entries are relative to the repo root (e.g. `queries/your-query.sparql`)
- [ ] If the query is in `web-library.yaml`: a clear `title` and `description`, and an appropriate `category`
- [ ] If the query is in `llm-knowledge.yaml`: `intent` populated with one or more user-question phrasings; `epo_terms` and `tags` filled where useful

## Notes for reviewers

<!-- Anything specific you'd like the reviewer to look at, or context that
helps explain a non-obvious choice (e.g. why a particular ePO predicate,
why a particular FILTER, etc.). Delete if not needed. -->
