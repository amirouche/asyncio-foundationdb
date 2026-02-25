/*
 * fdb_c2.h
 *
 * This source file is part of the FoundationDB open source project
 *
 * Copyright 2013-2022 Apple Inc. and the FoundationDB project authors
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

/*
 * Cleaned-up subset of fdb_c.h for CFFI's cdef() parser.
 * No preprocessor directives — CFFI does not run the C preprocessor.
 *
 * Matches FoundationDB 7.3 (API version 730).
 */

typedef enum {
    FDB_NET_OPTION_LOCAL_ADDRESS=10,
    FDB_NET_OPTION_CLUSTER_FILE=20,
    FDB_NET_OPTION_TRACE_ENABLE=30,
    FDB_NET_OPTION_TRACE_ROLL_SIZE=31,
    FDB_NET_OPTION_TRACE_MAX_LOGS_SIZE=32,
    FDB_NET_OPTION_TRACE_LOG_GROUP=33,
    FDB_NET_OPTION_TRACE_FORMAT=34,
    FDB_NET_OPTION_TRACE_CLOCK_SOURCE=35,
    FDB_NET_OPTION_TRACE_FILE_IDENTIFIER=36,
    FDB_NET_OPTION_TRACE_SHARE_AMONG_CLIENT_THREADS=37,
    FDB_NET_OPTION_TRACE_INITIALIZE_ON_SETUP=38,
    FDB_NET_OPTION_TRACE_PARTIAL_FILE_SUFFIX=39,
    FDB_NET_OPTION_KNOB=40,
    FDB_NET_OPTION_TLS_PLUGIN=41,
    FDB_NET_OPTION_TLS_CERT_BYTES=42,
    FDB_NET_OPTION_TLS_CERT_PATH=43,
    FDB_NET_OPTION_TLS_KEY_BYTES=45,
    FDB_NET_OPTION_TLS_KEY_PATH=46,
    FDB_NET_OPTION_TLS_VERIFY_PEERS=47,
    FDB_NET_OPTION_BUGGIFY_ENABLE=48,
    FDB_NET_OPTION_BUGGIFY_DISABLE=49,
    FDB_NET_OPTION_BUGGIFY_SECTION_ACTIVATED_PROBABILITY=50,
    FDB_NET_OPTION_BUGGIFY_SECTION_FIRED_PROBABILITY=51,
    FDB_NET_OPTION_TLS_CA_BYTES=52,
    FDB_NET_OPTION_TLS_CA_PATH=53,
    FDB_NET_OPTION_TLS_PASSWORD=54,
    FDB_NET_OPTION_DISABLE_MULTI_VERSION_CLIENT_API=60,
    FDB_NET_OPTION_CALLBACKS_ON_EXTERNAL_THREADS=61,
    FDB_NET_OPTION_EXTERNAL_CLIENT_LIBRARY=62,
    FDB_NET_OPTION_EXTERNAL_CLIENT_DIRECTORY=63,
    FDB_NET_OPTION_DISABLE_LOCAL_CLIENT=64,
    FDB_NET_OPTION_CLIENT_THREADS_PER_VERSION=65,
    FDB_NET_OPTION_FUTURE_VERSION_CLIENT_LIBRARY=66,
    FDB_NET_OPTION_RETAIN_CLIENT_LIBRARY_COPIES=67,
    FDB_NET_OPTION_IGNORE_EXTERNAL_CLIENT_FAILURES=68,
    FDB_NET_OPTION_FAIL_INCOMPATIBLE_CLIENT=69,
    FDB_NET_OPTION_DISABLE_CLIENT_STATISTICS_LOGGING=70,
    FDB_NET_OPTION_ENABLE_RUN_LOOP_PROFILING=71,
    FDB_NET_OPTION_DISABLE_CLIENT_BYPASS=72,
    FDB_NET_OPTION_CLIENT_BUGGIFY_ENABLE=80,
    FDB_NET_OPTION_CLIENT_BUGGIFY_DISABLE=81,
    FDB_NET_OPTION_CLIENT_BUGGIFY_SECTION_ACTIVATED_PROBABILITY=82,
    FDB_NET_OPTION_CLIENT_BUGGIFY_SECTION_FIRED_PROBABILITY=83,
    FDB_NET_OPTION_DISTRIBUTED_CLIENT_TRACER=90,
    FDB_NET_OPTION_CLIENT_TMP_DIR=91
} FDBNetworkOption;

typedef enum {
    FDB_DB_OPTION_LOCATION_CACHE_SIZE=10,
    FDB_DB_OPTION_MAX_WATCHES=20,
    FDB_DB_OPTION_MACHINE_ID=21,
    FDB_DB_OPTION_DATACENTER_ID=22,
    FDB_DB_OPTION_SNAPSHOT_RYW_ENABLE=26,
    FDB_DB_OPTION_SNAPSHOT_RYW_DISABLE=27,
    FDB_DB_OPTION_TRANSACTION_LOGGING_MAX_FIELD_LENGTH=405,
    FDB_DB_OPTION_TRANSACTION_TIMEOUT=500,
    FDB_DB_OPTION_TRANSACTION_RETRY_LIMIT=501,
    FDB_DB_OPTION_TRANSACTION_MAX_RETRY_DELAY=502,
    FDB_DB_OPTION_TRANSACTION_SIZE_LIMIT=503,
    FDB_DB_OPTION_TRANSACTION_CAUSAL_READ_RISKY=504,
    FDB_DB_OPTION_TRANSACTION_INCLUDE_PORT_IN_ADDRESS=505,
    FDB_DB_OPTION_TRANSACTION_AUTOMATIC_IDEMPOTENCY=506,
    FDB_DB_OPTION_TRANSACTION_BYPASS_UNREADABLE=700,
    FDB_DB_OPTION_TRANSACTION_USED_DURING_COMMIT_PROTECTION_DISABLE=701,
    FDB_DB_OPTION_TRANSACTION_REPORT_CONFLICTING_KEYS=702,
    FDB_DB_OPTION_USE_CONFIG_DATABASE=800,
    FDB_DB_OPTION_TEST_CAUSAL_READ_RISKY=900
} FDBDatabaseOption;

typedef enum {
    FDB_TR_OPTION_CAUSAL_WRITE_RISKY=10,
    FDB_TR_OPTION_CAUSAL_READ_RISKY=20,
    FDB_TR_OPTION_CAUSAL_READ_DISABLE=21,
    FDB_TR_OPTION_INCLUDE_PORT_IN_ADDRESS=23,
    FDB_TR_OPTION_NEXT_WRITE_NO_WRITE_CONFLICT_RANGE=30,
    FDB_TR_OPTION_COMMIT_ON_FIRST_PROXY=40,
    FDB_TR_OPTION_READ_YOUR_WRITES_DISABLE=51,
    FDB_TR_OPTION_READ_AHEAD_DISABLE=52,
    FDB_TR_OPTION_DURABILITY_DATACENTER=110,
    FDB_TR_OPTION_DURABILITY_RISKY=120,
    FDB_TR_OPTION_DURABILITY_DEV_NULL_IS_WEB_SCALE=130,
    FDB_TR_OPTION_PRIORITY_SYSTEM_IMMEDIATE=200,
    FDB_TR_OPTION_PRIORITY_BATCH=201,
    FDB_TR_OPTION_INITIALIZE_NEW_DATABASE=300,
    FDB_TR_OPTION_ACCESS_SYSTEM_KEYS=301,
    FDB_TR_OPTION_READ_SYSTEM_KEYS=302,
    FDB_TR_OPTION_RAW_ACCESS=303,
    FDB_TR_OPTION_BYPASS_STORAGE_QUOTA=304,
    FDB_TR_OPTION_DEBUG_RETRY_LOGGING=401,
    FDB_TR_OPTION_TRANSACTION_LOGGING_ENABLE=402,
    FDB_TR_OPTION_DEBUG_TRANSACTION_IDENTIFIER=403,
    FDB_TR_OPTION_LOG_TRANSACTION=404,
    FDB_TR_OPTION_TRANSACTION_LOGGING_MAX_FIELD_LENGTH=405,
    FDB_TR_OPTION_SERVER_REQUEST_TRACING=406,
    FDB_TR_OPTION_TIMEOUT=500,
    FDB_TR_OPTION_RETRY_LIMIT=501,
    FDB_TR_OPTION_MAX_RETRY_DELAY=502,
    FDB_TR_OPTION_SIZE_LIMIT=503,
    FDB_TR_OPTION_AUTOMATIC_IDEMPOTENCY=505,
    FDB_TR_OPTION_READ_SERVER_SIDE_CACHE_ENABLE=507,
    FDB_TR_OPTION_READ_SERVER_SIDE_CACHE_DISABLE=508,
    FDB_TR_OPTION_READ_PRIORITY_NORMAL=509,
    FDB_TR_OPTION_READ_PRIORITY_LOW=510,
    FDB_TR_OPTION_READ_PRIORITY_HIGH=511,
    FDB_TR_OPTION_SNAPSHOT_RYW_ENABLE=600,
    FDB_TR_OPTION_SNAPSHOT_RYW_DISABLE=601,
    FDB_TR_OPTION_LOCK_AWARE=700,
    FDB_TR_OPTION_USED_DURING_COMMIT_PROTECTION_DISABLE=701,
    FDB_TR_OPTION_READ_LOCK_AWARE=702,
    FDB_TR_OPTION_REPORT_CONFLICTING_KEYS=712,
    FDB_TR_OPTION_USE_PROVISIONAL_PROXIES=711,
    FDB_TR_OPTION_BYPASS_UNREADABLE=1100
} FDBTransactionOption;

typedef enum {
    FDB_STREAMING_MODE_WANT_ALL=-2,
    FDB_STREAMING_MODE_ITERATOR=-1,
    FDB_STREAMING_MODE_EXACT=0,
    FDB_STREAMING_MODE_SMALL=1,
    FDB_STREAMING_MODE_MEDIUM=2,
    FDB_STREAMING_MODE_LARGE=3,
    FDB_STREAMING_MODE_SERIAL=4
} FDBStreamingMode;

typedef enum {
    FDB_MUTATION_TYPE_ADD=2,
    FDB_MUTATION_TYPE_AND=6,
    FDB_MUTATION_TYPE_BIT_AND=6,
    FDB_MUTATION_TYPE_OR=7,
    FDB_MUTATION_TYPE_BIT_OR=7,
    FDB_MUTATION_TYPE_XOR=8,
    FDB_MUTATION_TYPE_BIT_XOR=8,
    FDB_MUTATION_TYPE_APPEND_IF_FITS=9,
    FDB_MUTATION_TYPE_MAX=12,
    FDB_MUTATION_TYPE_MIN=13,
    FDB_MUTATION_TYPE_SET_VERSIONSTAMPED_KEY=14,
    FDB_MUTATION_TYPE_SET_VERSIONSTAMPED_VALUE=15,
    FDB_MUTATION_TYPE_BYTE_MIN=16,
    FDB_MUTATION_TYPE_BYTE_MAX=17,
    FDB_MUTATION_TYPE_COMPARE_AND_CLEAR=20
} FDBMutationType;

typedef enum {
    FDB_CONFLICT_RANGE_TYPE_READ=0,
    FDB_CONFLICT_RANGE_TYPE_WRITE=1
} FDBConflictRangeType;

typedef enum {
    FDB_ERROR_PREDICATE_RETRYABLE=50000,
    FDB_ERROR_PREDICATE_MAYBE_COMMITTED=50001,
    FDB_ERROR_PREDICATE_RETRYABLE_NOT_COMMITTED=50002
} FDBErrorPredicate;

/* Pointers to these opaque types represent objects in the FDB API */
typedef struct FDB_future FDBFuture;
typedef struct FDB_result FDBResult;
typedef struct FDB_database FDBDatabase;
typedef struct FDB_tenant FDBTenant;
typedef struct FDB_transaction FDBTransaction;

typedef int fdb_error_t;
typedef int fdb_bool_t;

typedef struct keyvalue {
    ...;
} FDBKeyValue;

/* --- new types from upstream --- */

typedef struct key {
    const uint8_t* key;
    int key_length;
} FDBKey;

typedef struct keyselector {
    ...;
} FDBKeySelector;

typedef struct getrangereqandresult {
    ...;
} FDBGetRangeReqAndResult;

typedef struct mappedkeyvalue {
    ...;
} FDBMappedKeyValue;

typedef struct keyrange {
    const uint8_t* begin_key;
    int begin_key_length;
    const uint8_t* end_key;
    int end_key_length;
} FDBKeyRange;

typedef struct granulesummary {
    FDBKeyRange key_range;
    int64_t snapshot_version;
    int64_t snapshot_size;
    int64_t delta_version;
    int64_t delta_size;
} FDBGranuleSummary;

const char*
fdb_get_error( fdb_error_t code );

fdb_bool_t
fdb_error_predicate( int predicate_test, fdb_error_t code );

fdb_error_t
fdb_network_set_option( FDBNetworkOption option, uint8_t const* value,
                        int value_length );

fdb_error_t fdb_setup_network();

fdb_error_t fdb_run_network();

fdb_error_t fdb_stop_network();

fdb_error_t fdb_add_network_thread_completion_hook(void (*hook)(void*), void *hook_parameter);

void fdb_future_cancel( FDBFuture* f );

void fdb_future_release_memory( FDBFuture* f );

void fdb_future_destroy( FDBFuture* f );

fdb_error_t fdb_future_block_until_ready( FDBFuture* f );

fdb_bool_t fdb_future_is_ready( FDBFuture* f );

typedef void (*FDBCallback)(FDBFuture* future, void* callback_parameter);

fdb_error_t
fdb_future_set_callback( FDBFuture* f, FDBCallback callback,
                         void* callback_parameter );

fdb_error_t
fdb_future_get_error( FDBFuture* f );

fdb_error_t
fdb_future_get_int64( FDBFuture* f, int64_t* out );

fdb_error_t
fdb_future_get_key( FDBFuture* f, uint8_t const** out_key,
                    int* out_key_length );

fdb_error_t
fdb_future_get_value( FDBFuture* f, fdb_bool_t *out_present,
                      uint8_t const** out_value,
                      int* out_value_length );

fdb_error_t
fdb_future_get_keyvalue_array( FDBFuture* f, FDBKeyValue const** out_kv,
                               int* out_count, fdb_bool_t* out_more );

fdb_error_t fdb_future_get_string_array(FDBFuture* f,
                                        const char*** out_strings, int* out_count);

fdb_error_t fdb_future_get_bool(FDBFuture* f, fdb_bool_t* out);
fdb_error_t fdb_future_get_uint64(FDBFuture* f, uint64_t* out);
fdb_error_t fdb_future_get_double(FDBFuture* f, double* out);
fdb_error_t fdb_future_get_key_array(FDBFuture* f, FDBKey const** out_key_array, int* out_count);
fdb_error_t fdb_future_get_mappedkeyvalue_array(FDBFuture* f, FDBMappedKeyValue const** out_kv, int* out_count, fdb_bool_t* out_more);
fdb_error_t fdb_future_get_keyrange_array(FDBFuture* f, FDBKeyRange const** out_ranges, int* out_count);
fdb_error_t fdb_future_get_granule_summary_array(FDBFuture* f, FDBGranuleSummary const** out_summaries, int* out_count);

fdb_error_t
fdb_create_database( const char* cluster_file_path, FDBDatabase** out_database );

void fdb_database_destroy( FDBDatabase* d );

fdb_error_t
fdb_database_set_option( FDBDatabase* d, FDBDatabaseOption option,
                         uint8_t const* value, int value_length );

fdb_error_t
fdb_database_create_transaction( FDBDatabase* d,
                                 FDBTransaction** out_transaction );

fdb_error_t fdb_create_database_from_connection_string(const char* connection_string, FDBDatabase** out_database);
fdb_error_t fdb_database_open_tenant(FDBDatabase* d, uint8_t const* tenant_name, int tenant_name_length, FDBTenant** out_tenant);
FDBFuture* fdb_database_reboot_worker(FDBDatabase* db, uint8_t const* address, int address_length, fdb_bool_t check, int duration);
FDBFuture* fdb_database_force_recovery_with_data_loss(FDBDatabase* db, uint8_t const* dcid, int dcid_length);
FDBFuture* fdb_database_create_snapshot(FDBDatabase* db, uint8_t const* uid, int uid_length, uint8_t const* snap_command, int snap_command_length);
double fdb_database_get_main_thread_busyness(FDBDatabase* db);
FDBFuture* fdb_database_get_server_protocol(FDBDatabase* db, uint64_t expected_version);
FDBFuture* fdb_database_get_client_status(FDBDatabase* db);

fdb_error_t fdb_tenant_create_transaction(FDBTenant* tenant, FDBTransaction** out_transaction);
void fdb_tenant_destroy(FDBTenant* tenant);
FDBFuture* fdb_tenant_get_id(FDBTenant* tenant);

void fdb_transaction_destroy( FDBTransaction* tr);

void fdb_transaction_cancel( FDBTransaction* tr);

fdb_error_t
fdb_transaction_set_option( FDBTransaction* tr, FDBTransactionOption option,
                            uint8_t const* value, int value_length );

void
fdb_transaction_set_read_version( FDBTransaction* tr, int64_t version );

FDBFuture* fdb_transaction_get_read_version( FDBTransaction* tr );

FDBFuture*
fdb_transaction_get( FDBTransaction* tr, uint8_t const* key_name,
                     int key_name_length, fdb_bool_t snapshot );

FDBFuture*
fdb_transaction_get_key( FDBTransaction* tr, uint8_t const* key_name,
                         int key_name_length, fdb_bool_t or_equal,
                         int offset, fdb_bool_t snapshot );

FDBFuture*
fdb_transaction_get_addresses_for_key(FDBTransaction* tr, uint8_t const* key_name,
                                      int key_name_length);

FDBFuture* fdb_transaction_get_range(
    FDBTransaction* tr, uint8_t const* begin_key_name,
    int begin_key_name_length, fdb_bool_t begin_or_equal, int begin_offset,
    uint8_t const* end_key_name, int end_key_name_length,
    fdb_bool_t end_or_equal, int end_offset, int limit, int target_bytes,
    FDBStreamingMode mode, int iteration, fdb_bool_t snapshot,
    fdb_bool_t reverse );

void
fdb_transaction_set( FDBTransaction* tr, uint8_t const* key_name,
                     int key_name_length, uint8_t const* value,
                     int value_length );

void
fdb_transaction_atomic_op( FDBTransaction* tr, uint8_t const* key_name,
                           int key_name_length, uint8_t const* param,
                           int param_length, FDBMutationType operation_type );

void
fdb_transaction_clear( FDBTransaction* tr, uint8_t const* key_name,
                       int key_name_length );

void fdb_transaction_clear_range(
    FDBTransaction* tr, uint8_t const* begin_key_name,
    int begin_key_name_length, uint8_t const* end_key_name,
    int end_key_name_length );

FDBFuture* fdb_transaction_watch( FDBTransaction *tr,
                                  uint8_t const* key_name,
                                  int key_name_length);

FDBFuture* fdb_transaction_commit( FDBTransaction* tr );

fdb_error_t
fdb_transaction_get_committed_version( FDBTransaction* tr,
                                       int64_t* out_version );

FDBFuture*
fdb_transaction_get_approximate_size(FDBTransaction* tr);

FDBFuture* fdb_transaction_get_versionstamp( FDBTransaction* tr );

FDBFuture*
fdb_transaction_on_error( FDBTransaction* tr, fdb_error_t error );

void fdb_transaction_reset( FDBTransaction* tr );

fdb_error_t
fdb_transaction_add_conflict_range(FDBTransaction *tr,
                                   uint8_t const* begin_key_name,
                                   int begin_key_name_length,
                                   uint8_t const* end_key_name,
                                   int end_key_name_length,
                                   FDBConflictRangeType type);

FDBFuture*
fdb_transaction_get_estimated_range_size_bytes(FDBTransaction* tr,
                                               uint8_t const* begin_key_name,
                                               int begin_key_name_length,
                                               uint8_t const* end_key_name,
                                               int end_key_name_length);

FDBFuture*
fdb_transaction_get_range_split_points(FDBTransaction* tr,
                                       uint8_t const* begin_key_name,
                                       int begin_key_name_length,
                                       uint8_t const* end_key_name,
                                       int end_key_name_length,
                                       int64_t chunk_size);

FDBFuture* fdb_transaction_get_mapped_range(
    FDBTransaction* tr,
    uint8_t const* begin_key_name, int begin_key_name_length, fdb_bool_t begin_or_equal, int begin_offset,
    uint8_t const* end_key_name,   int end_key_name_length,   fdb_bool_t end_or_equal,   int end_offset,
    uint8_t const* mapper_name, int mapper_name_length,
    int limit, int target_bytes, FDBStreamingMode mode, int iteration,
    fdb_bool_t snapshot, fdb_bool_t reverse);

FDBFuture* fdb_transaction_get_tag_throttled_duration(FDBTransaction* tr);
FDBFuture* fdb_transaction_get_total_cost(FDBTransaction* tr);

FDBFuture* fdb_transaction_get_blob_granule_ranges(FDBTransaction* tr,
    uint8_t const* begin_key_name, int begin_key_name_length,
    uint8_t const* end_key_name,   int end_key_name_length, int rangeLimit);

FDBFuture* fdb_transaction_summarize_blob_granules(FDBTransaction* tr,
    uint8_t const* begin_key_name, int begin_key_name_length,
    uint8_t const* end_key_name,   int end_key_name_length,
    int64_t summaryVersion, int rangeLimit);

fdb_error_t
fdb_select_api_version_impl( int runtime_version, int header_version );

int fdb_get_max_api_version();
const char* fdb_get_client_version();
