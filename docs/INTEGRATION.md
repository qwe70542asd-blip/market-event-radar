# v11.3.0 Integration

This is a complete repository, not a patch package.

## Integrated interface decisions

- The crypto sidebar is replaced with a Taiwan market focus panel.
- Calendar cells show major events plus grouped company/dividend counts.
- The day dialog separates major events, company information and dividends.
- Taipei date keys are used instead of UTC date slicing.
- Duplicate event and ex-dividend records are collapsed.
- Event updates fall back to recent major information when no date changed today.
- News text is sanitized and homepage/listing links are removed.
- News cards include deterministic category, impact, direction and outline fields.
- Taiwan market pages show four top-15 rankings and search-only full-universe results.
- Institutional pages show search-only detail plus daily hot stock/ETF rankings.
- Missing chip values are never converted to zero.
