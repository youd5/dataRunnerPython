# Publishing results to Sanity

After Filter3 finishes (web route `/algorithm-triggered` or `python src/filter3.py`), the day's result CSVs are pushed to Sanity by `src/upload_to_sanity.py`. The upload is skipped when Sanity is not configured, and a failed upload is logged without failing the run.

## Configuration (root `.env`)

```
SANITY_PROJECT_ID=your_project_id
SANITY_DATASET=production
SANITY_API_TOKEN=your_write_token      # Sanity manage > API > Tokens, "Editor" permission
SANITY_API_VERSION=2025-02-19          # optional
```

## Documents

Every CSV becomes `screenerSnapshot` documents, one per dataset per date, with a deterministic id `screenerSnapshot.<dataset>.<date>`. Uploads use `createOrReplace`, so re-running a day overwrites it.

| dataset | source CSV | one document per | replaces Google Sheet |
|---|---|---|---|
| `allStocks` | `<date>_ohlc-nse-other-instruments.csv` (Filter1) | candle date | ALL_STOCKS |
| `indices` | `<date>_ohlc-nse-indices.csv` (Filter1) | candle date | MARKET_OVERVIEW |
| `topStocks` | `<date>_filter2_minervini_filter_list.csv` (Filter2) | run date | TOP_STOCKS |
| `breakouts` | `<date>_filter3_above_pivot.csv` (Filter3) | run date | BREAKOUT_STOCKS |

Fields: `dataset`, `date` (YYYY-MM-DD), `runDate`, `generatedAt`, `rowCount`, and `rows`, an array with one object per CSV row. Row fields keep the CSV column names, except `52wh`/`52wl`, which become `week52High`/`week52Low` (Sanity field names cannot start with a digit). Row `date` values are trimmed to YYYY-MM-DD.

Filter1 fetches about 10 days of candles each run, so overlapping days are rewritten with the latest values and the `allStocks`/`indices` history builds up one document per trading day.

## Example GROQ queries

```groq
// Latest top stocks (Filter2)
*[_type == "screenerSnapshot" && dataset == "topStocks"] | order(date desc)[0].rows

// Latest day of all stocks
*[_type == "screenerSnapshot" && dataset == "allStocks"] | order(date desc)[0]{date, rows}

// Last 10 trading days of all stocks (for charts)
*[_type == "screenerSnapshot" && dataset == "allStocks"] | order(date desc)[0...10]{date, rows}
```

The dataset must allow public reads (or the website must use a read token) for the React site to query it.

## Optional Studio schema

Sanity accepts these documents without a schema. To browse them in Sanity Studio, add:

```js
export default {
  name: 'screenerSnapshot',
  title: 'Screener snapshot',
  type: 'document',
  readOnly: true,
  fields: [
    {name: 'dataset', type: 'string'},
    {name: 'date', type: 'date'},
    {name: 'runDate', type: 'date'},
    {name: 'generatedAt', type: 'datetime'},
    {name: 'rowCount', type: 'number'},
    {name: 'rows', type: 'array', of: [{type: 'object', name: 'row', fields: [
      {name: 'trading_symbol', type: 'string'},
    ]}]},
  ],
  preview: {select: {title: 'dataset', subtitle: 'date'}},
}
```
