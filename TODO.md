# TODO

## Future milestones

### API completeness

- [ ] **Tenant API** — `fdb_database_open_tenant`, `fdb_tenant_create_transaction`, etc.
  Tenants are already enabled in CI; the Python surface is missing.
- [ ] **Locality API** — `fdb_get_boundary_keys`, complement to the already-present
  `get_range_split_points`

## New extensions

- [ ] **`qstore` — transactional queue** — versionstamp-keyed FIFO with
  at-least-once delivery, visibility timeout, and dead-letter support.
  Primary use case: enqueue a background job in the same transaction that
  mutates data — either both happen or neither does. Also covers in-process
  message passing, multi-worker task distribution, and event-log-with-replay.
  Eliminates the need for a separate broker (Redis, RabbitMQ, SQS) for small
  teams.

- [ ] **`tsstore` — time-series store** — `(metric, timestamp) → value` with
  efficient range scans over time windows. Covers metrics, audit logs, and
  high-frequency append-only event streams. Complements `vnstore` (which
  versions tuples) for write-heavy time-ordered data.

- [ ] **`zstore` — spatial index (Z-order curve)** — point data indexed via
  Z-ordering (Morton code). Coordinates (e.g. WGS84 lat/lon) are interleaved
  bitwise into a single binary key; prefix scans over Z-keys find all points
  in a bounding box cheaply. Binary geohashes are a special case.
  Reference: https://forums.foundationdb.org/t/data-modeling-efficient-encoding-for-wgs84-coordinate-key-ids/354

- [ ] **`xzstore` — spatial index (XZ-order curve)** — extends `zstore` to
  objects with *spatial extension* (ranges, polygons, variable-depth paths),
  not just points. XZ-ordering maps bounding regions to 1D keys while
  preserving locality. Trades scan selectivity for generality: queries that
  bind fewer dimensions produce larger extents and more false positives.
  Best suited for datasets where most queries bind most dimensions.

- [ ] **`lstore` — lease / distributed lock store** — TTL-aware locks using
  versionstamps as expiry tokens. Lets small teams drop Redis as a
  coordination dependency entirely.

- [ ] **`rlayer` — [record layer](https://foundationdb.github.io/fdb-record-layer/)** —
  a primary-record store with declarative secondary indices. The primary
  representation stores typed, structured records under a stable primary key
  (like an RDBMS table). Secondary indices are declared alongside the record
  definition and maintained automatically via the `on_transaction_commit`
  hook — the application never writes index keys directly. Sits above the
  existing stores in the abstraction hierarchy: `eavstore` and `nstore` are
  building blocks; `rlayer` is the higher-level layer for teams that want
  schema, query planning, and index maintenance without leaving Python.
  Notably different from eavstore (which fixes its index permutations for
  lower write amplification) and nstore (which covers all patterns at
  minimal-but-still-amplified write cost): rlayer lets the developer choose
  which access patterns to pay for.

- [ ] **`rstore` — order-statistic / ranked store** — extends the sorted-set idea
  of `zstore` with O(log n) `rank(item)` and `item_at_rank(n)` queries.
  A naive `(score, item) → ""` layout answers range-by-score in one scan but
  requires counting all lower-scored keys to determine rank (O(n)). `rstore`
  maintains an auxiliary Fenwick tree (binary indexed tree) or equivalent
  structure alongside the score index to answer rank queries in O(log n) while
  keeping concurrent writes consistent. `zstore` (simple sorted set, no rank
  queries) remains worthwhile as a lighter alternative when rank is not needed.

- [ ] **`gstore` — graph traversal layer** — BFS/DFS/shortest-path helpers built
  on top of `nstore` rather than a separate storage layout. The triple layout
  `(subject, predicate, object)` already encodes edges and properties; what is
  missing is iterative traversal: multi-hop queries, reachability, neighbour
  expansion. Each hop issues the right `nstore.select` calls, with a reverse
  index `(object, predicate, subject)` for incoming-edge lookups. A standalone
  store layout is not needed — the value is in the traversal API over the
  existing nstore structure.
