# IAP Source Completeness

## Rule

An instrument-approach chart title is evidence for selecting a chart only after
the 424 database-coding pages provide a non-empty primary-approach segment.
It must not create a primary segment, join approach transitions into one, or
turn a missed approach into an approach.

This keeps the `NavModel` source-complete before any target adapter consumes
it. Default BGL, DFDv2, JSON, and future adapters therefore receive the same
explicit distinction between a complete approach and an incomplete source
group.

## 2608R1 Evidence

The following 424 database-coding groups have no `approach` segment:

| Airport | Label | Direct source page | Source sections present |
| --- | --- | --- | --- |
| ZBAD | R29R | `Terminal/ZBAD/ZBAD-0C-19.pdf` | approach transitions, missed |
| ZJSY | I08-X | `Terminal/ZJSY/ZJSY-0C-8.pdf` | missed |
| ZSNJ | I25 | `Terminal/ZSNJ/ZSNJ-4P.pdf` | missed |
| ZSOF | R15 | `Terminal/ZSOF/ZSOF-4M.pdf` | approach transitions |
| ZSOF | R33 | `Terminal/ZSOF/ZSOF-4P.pdf` | approach transitions |
| ZSWY | I03 | `Terminal/ZSWY/ZSWY-4Z03.pdf` | approach transitions |
| ZUAL | I15 | `Terminal/ZUAL/ZUAL-4Z03.pdf` | approach transitions |
| ZYDD | R01 | `Terminal/ZYDD/ZYDD-0C-2.pdf` | approach transitions |
| ZYDD | R01-Y | `Terminal/ZYDD/ZYDD-0C-2.pdf` | missed |
| ZYTL | R10 | `Terminal/ZYTL/ZYTL-4Z13.pdf` | approach transitions, missed |

`Charts.csv` directly names compatible chart identities such as `I08-X`,
`I25`, `I03`, `I15`, `R01`, and `R10`. Those titles do not change the source
sections above. Each group remains `no_unique_primary` in the coverage audit.

## Regression

`test_iap_coverage_does_not_create_a_primary_from_a_matching_chart_title`
uses the ZJSY `I08-X` form: its matching `RNP ILS/DME x RWY08(AR)` chart is
present, while the source has only an approach transition and missed section.
The audit must keep the group unresolved.
