# TODO

Unbound or incomplete FoundationDB C API bindings in `found/base.py`:

- [ ] `fdb_transaction_watch` — watch a key for changes
- [ ] `MUTATION_APPEND_IF_FITS`, `MUTATION_COMPARE_AND_CLEAR` — opcodes defined but no Python wrapper functions (`append_if_fits`, `compare_and_clear`)
- [ ] `fdb_get_client_version` — returns the FDB client library version string
- [ ] `fdb_transaction_get_addresses_for_key` — get storage server addresses for a key
  - Requires: `fdb_future_get_string_array` — decode string array results
- [ ] `fdb_database_set_option` — configure database-level options (max watches, location cache size, etc.)
- [ ] `fdb_add_network_thread_completion_hook` — register a callback when the network thread exits
- [ ] `fdb_network_set_option` — configure network-level options (TLS, tracing, external clients, etc.)
- [ ] `fdb_error_predicate` — test whether an error code matches a predicate (retryable, maybe-committed, retryable-not-committed)
