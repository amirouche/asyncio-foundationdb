# TODO

Unbound or incomplete FoundationDB C API bindings in `found/base.py`:

1. `fdb_transaction_watch` — watch a key for changes
2. `get_range_split_points` — currently a stub; result keys from `fdb_future_get_key_array` are discarded, returns `None` instead of the split-point key list
3. `MUTATION_APPEND_IF_FITS`, `MUTATION_COMPARE_AND_CLEAR` — opcodes defined but no Python wrapper functions (`append_if_fits`, `compare_and_clear`)
4. `fdb_get_client_version` — returns the FDB client library version string
5. `fdb_transaction_get_addresses_for_key` — get storage server addresses for a key
6. `fdb_database_set_option` — configure database-level options (max watches, location cache size, etc.)
7. `fdb_future_get_string_array` — decode string array results (needed by item 5 only)
   `fdb_future_get_key_array` — decode key array results (needed by item 2)
8. `fdb_add_network_thread_completion_hook` — register a callback when the network thread exits
9. `fdb_network_set_option` — configure network-level options (TLS, tracing, external clients, etc.)
10. `fdb_error_predicate` — test whether an error code matches a predicate (retryable, maybe-committed, retryable-not-committed)
