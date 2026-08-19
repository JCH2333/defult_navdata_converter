# Airway Connection Shape Results 2608R1

Date: 2026-08-19

## Scope

This experiment uses synthetic waypoints and routes only. It does not read the
reference package, does not change a conversion candidate, and does not deploy
to Community.

Inputs:

- MSFS 2024 SDK Package Tool: `C:\MSFS 2024 SDK\Tools\bin\fspackagetool.exe`
- Offline reader: Navdatareader 1.2.4
- Probe output: `diagnostics\airway-connection-shape-probe-r163-20260819`

## Results

The SDK emitted an `airway` row only when the same link was declared with both
`Route/Next` at its start waypoint and `Route/Previous` at its end waypoint.

| Synthetic form | Output rows | Result |
| --- | ---: | --- |
| `Next` plus `Previous` | 1 | One row with the declared endpoint and bounding-box geometry |
| `Next` only | 0 | No airway row |
| `Previous` only | 0 | No airway row |
| Two connected bidirectional links | 2 | One fragment with sequence numbers 1 and 2 |
| Two disconnected bidirectional links with the same name | 2 | Two fragments, each with sequence number 1 |

The reader reported 5 airway rows in total. All generated endpoint and
bounding-box values were IEEE-754 `float32`, consistent with the coordinate
precision experiment.

## Adapter Consequence

The default-navdata adapter must emit both `Next` and `Previous` for every
projected 424 airway segment. It must not map a source direction value to a
single Route child.

The current adapter already writes both children. This experiment therefore
rules out the source-direction-to-single-child hypothesis for the remaining
2608R1 airway geometry differences; it does not establish a new candidate
projection rule or reduce the byte-equality gate by itself.
