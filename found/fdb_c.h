/*
 * fdb_c.h
 *
 * This source file is part of the FoundationDB open source project
 *
 * Copyright 2013-2018 Apple Inc. and the FoundationDB project authors
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

/* #include "fdb_c_options.g.h" */

typedef enum {
    // Deprecated
    // Parameter: (String) IP:PORT
    FDB_NET_OPTION_LOCAL_ADDRESS=10,

    // Deprecated
    // Parameter: (String) path to cluster file
    FDB_NET_OPTION_CLUSTER_FILE=20,

    // Enables trace output to a file in a directory of the clients choosing
    // Parameter: (String) path to output directory (or NULL for current working directory)
    FDB_NET_OPTION_TRACE_ENABLE=30,

    // Sets the maximum size in bytes of a single trace output file. This value should be in the range ``[0, INT64_MAX]``. If the value is set to 0, there is no limit on individual file size. The default is a maximum size of 10,485,760 bytes.
    // Parameter: (Int) max size of a single trace output file
    FDB_NET_OPTION_TRACE_ROLL_SIZE=31,

    // Sets the maximum size of all the trace output files put together. This value should be in the range ``[0, INT64_MAX]``. If the value is set to 0, there is no limit on the total size of the files. The default is a maximum size of 104,857,600 bytes. If the default roll size is used, this means that a maximum of 10 trace files will be written at a time.
    // Parameter: (Int) max total size of trace files
    FDB_NET_OPTION_TRACE_MAX_LOGS_SIZE=32,

    // Sets the 'logGroup' attribute with the specified value for all events in the trace output files. The default log group is 'default'.
    // Parameter: (String) value of the logGroup attribute
    FDB_NET_OPTION_TRACE_LOG_GROUP=33,

    // Set internal tuning or debugging knobs
    // Parameter: (String) knob_name=knob_value
    FDB_NET_OPTION_KNOB=40,

    // Set the TLS plugin to load. This option, if used, must be set before any other TLS options
    // Parameter: (String) file path or linker-resolved name
    FDB_NET_OPTION_TLS_PLUGIN=41,

    // Set the certificate chain
    // Parameter: (Bytes) certificates
    FDB_NET_OPTION_TLS_CERT_BYTES=42,

    // Set the file from which to load the certificate chain
    // Parameter: (String) file path
    FDB_NET_OPTION_TLS_CERT_PATH=43,

    // Set the private key corresponding to your own certificate
    // Parameter: (Bytes) key
    FDB_NET_OPTION_TLS_KEY_BYTES=45,

    // Set the file from which to load the private key corresponding to your own certificate
    // Parameter: (String) file path
    FDB_NET_OPTION_TLS_KEY_PATH=46,

    // Set the peer certificate field verification criteria
    // Parameter: (Bytes) verification pattern
    FDB_NET_OPTION_TLS_VERIFY_PEERS=47,

    //
    // Parameter: Option takes no parameter
    FDB_NET_OPTION_BUGGIFY_ENABLE=48,

    //
    // Parameter: Option takes no parameter
    FDB_NET_OPTION_BUGGIFY_DISABLE=49,

    // Set the probability of a BUGGIFY section being active for the current execution.  Only applies to code paths first traversed AFTER this option is changed.
    // Parameter: (Int) probability expressed as a percentage between 0 and 100
    FDB_NET_OPTION_BUGGIFY_SECTION_ACTIVATED_PROBABILITY=50,

    // Set the probability of an active BUGGIFY section being fired
    // Parameter: (Int) probability expressed as a percentage between 0 and 100
    FDB_NET_OPTION_BUGGIFY_SECTION_FIRED_PROBABILITY=51,

    // Disables the multi-version client API and instead uses the local client directly. Must be set before setting up the network.
    // Parameter: Option takes no parameter
    FDB_NET_OPTION_DISABLE_MULTI_VERSION_CLIENT_API=60,

    // If set, callbacks from external client libraries can be called from threads created by the FoundationDB client library. Otherwise, callbacks will be called from either the thread used to add the callback or the network thread. Setting this option can improve performance when connected using an external client, but may not be safe to use in all environments. Must be set before setting up the network. WARNING: This feature is considered experimental at this time.
    // Parameter: Option takes no parameter
    FDB_NET_OPTION_CALLBACKS_ON_EXTERNAL_THREADS=61,

    // Adds an external client library for use by the multi-version client API. Must be set before setting up the network.
    // Parameter: (String) path to client library
    FDB_NET_OPTION_EXTERNAL_CLIENT_LIBRARY=62,

    // Searches the specified path for dynamic libraries and adds them to the list of client libraries for use by the multi-version client API. Must be set before setting up the network.
    // Parameter: (String) path to directory containing client libraries
    FDB_NET_OPTION_EXTERNAL_CLIENT_DIRECTORY=63,

    // Prevents connections through the local client, allowing only connections through externally loaded client libraries. Intended primarily for testing.
    // Parameter: Option takes no parameter
    FDB_NET_OPTION_DISABLE_LOCAL_CLIENT=64,

    // Disables logging of client statistics, such as sampled transaction activity.
    // Parameter: Option takes no parameter
    FDB_NET_OPTION_DISABLE_CLIENT_STATISTICS_LOGGING=70,

    // Enables debugging feature to perform slow task profiling. Requires trace logging to be enabled. WARNING: this feature is not recommended for use in production.
    // Parameter: Option takes no parameter
    FDB_NET_OPTION_ENABLE_SLOW_TASK_PROFILING=71
} FDBNetworkOption;

typedef enum {
    // This option is only a placeholder for C compatibility and should not be used
    // Parameter: Option takes no parameter
    FDB_CLUSTER_OPTION_DUMMY_DO_NOT_USE=-1
} FDBClusterOption;

typedef enum {
    // Set the size of the client location cache. Raising this value can boost performance in very large databases where clients access data in a near-random pattern. Defaults to 100000.
    // Parameter: (Int) Max location cache entries
    FDB_DB_OPTION_LOCATION_CACHE_SIZE=10,

    // Set the maximum number of watches allowed to be outstanding on a database connection. Increasing this number could result in increased resource usage. Reducing this number will not cancel any outstanding watches. Defaults to 10000 and cannot be larger than 1000000.
    // Parameter: (Int) Max outstanding watches
    FDB_DB_OPTION_MAX_WATCHES=20,

    // Specify the machine ID that was passed to fdbserver processes running on the same machine as this client, for better location-aware load balancing.
    // Parameter: (String) Hexadecimal ID
    FDB_DB_OPTION_MACHINE_ID=21,

    // Specify the datacenter ID that was passed to fdbserver processes running in the same datacenter as this client, for better location-aware load balancing.
    // Parameter: (String) Hexadecimal ID
    FDB_DB_OPTION_DATACENTER_ID=22
} FDBDatabaseOption;

typedef enum {
    // The transaction, if not self-conflicting, may be committed a second time after commit succeeds, in the event of a fault
    // Parameter: Option takes no parameter
    FDB_TR_OPTION_CAUSAL_WRITE_RISKY=10,

    // The read version will be committed, and usually will be the latest committed, but might not be the latest committed in the event of a fault or partition
    // Parameter: Option takes no parameter
    FDB_TR_OPTION_CAUSAL_READ_RISKY=20,

    //
    // Parameter: Option takes no parameter
    FDB_TR_OPTION_CAUSAL_READ_DISABLE=21,

    // The next write performed on this transaction will not generate a write conflict range. As a result, other transactions which read the key(s) being modified by the next write will not conflict with this transaction. Care needs to be taken when using this option on a transaction that is shared between multiple threads. When setting this option, write conflict ranges will be disabled on the next write operation, regardless of what thread it is on.
    // Parameter: Option takes no parameter
    FDB_TR_OPTION_NEXT_WRITE_NO_WRITE_CONFLICT_RANGE=30,

    // Committing this transaction will bypass the normal load balancing across proxies and go directly to the specifically nominated 'first proxy'.
    // Parameter: Option takes no parameter
    FDB_TR_OPTION_COMMIT_ON_FIRST_PROXY=40,

    //
    // Parameter: Option takes no parameter
    FDB_TR_OPTION_CHECK_WRITES_ENABLE=50,

    // Reads performed by a transaction will not see any prior mutations that occured in that transaction, instead seeing the value which was in the database at the transaction's read version. This option may provide a small performance benefit for the client, but also disables a number of client-side optimizations which are beneficial for transactions which tend to read and write the same keys within a single transaction.
    // Parameter: Option takes no parameter
    FDB_TR_OPTION_READ_YOUR_WRITES_DISABLE=51,

    // Disables read-ahead caching for range reads. Under normal operation, a transaction will read extra rows from the database into cache if range reads are used to page through a series of data one row at a time (i.e. if a range read with a one row limit is followed by another one row range read starting immediately after the result of the first).
    // Parameter: Option takes no parameter
    FDB_TR_OPTION_READ_AHEAD_DISABLE=52,

    //
    // Parameter: Option takes no parameter
    FDB_TR_OPTION_DURABILITY_DATACENTER=110,

    //
    // Parameter: Option takes no parameter
    FDB_TR_OPTION_DURABILITY_RISKY=120,

    //
    // Parameter: Option takes no parameter
    FDB_TR_OPTION_DURABILITY_DEV_NULL_IS_WEB_SCALE=130,

    // Specifies that this transaction should be treated as highest priority and that lower priority transactions should block behind this one. Use is discouraged outside of low-level tools
    // Parameter: Option takes no parameter
    FDB_TR_OPTION_PRIORITY_SYSTEM_IMMEDIATE=200,

    // Specifies that this transaction should be treated as low priority and that default priority transactions should be processed first. Useful for doing batch work simultaneously with latency-sensitive work
    // Parameter: Option takes no parameter
    FDB_TR_OPTION_PRIORITY_BATCH=201,

    // This is a write-only transaction which sets the initial configuration. This option is designed for use by database system tools only.
    // Parameter: Option takes no parameter
    FDB_TR_OPTION_INITIALIZE_NEW_DATABASE=300,

    // Allows this transaction to read and modify system keys (those that start with the byte 0xFF)
    // Parameter: Option takes no parameter
    FDB_TR_OPTION_ACCESS_SYSTEM_KEYS=301,

    // Allows this transaction to read system keys (those that start with the byte 0xFF)
    // Parameter: Option takes no parameter
    FDB_TR_OPTION_READ_SYSTEM_KEYS=302,

    //
    // Parameter: Option takes no parameter
    FDB_TR_OPTION_DEBUG_DUMP=400,

    //
    // Parameter: (String) Optional transaction name
    FDB_TR_OPTION_DEBUG_RETRY_LOGGING=401,

    // Enables tracing for this transaction and logs results to the client trace logs. Client trace logging must be enabled to get log output.
    // Parameter: (String) String identifier to be used in the logs when tracing this transaction. The identifier must not exceed 100 characters.
    FDB_TR_OPTION_TRANSACTION_LOGGING_ENABLE=402,

    // Set a timeout in milliseconds which, when elapsed, will cause the transaction automatically to be cancelled. Valid parameter values are ``[0, INT_MAX]``. If set to 0, will disable all timeouts. All pending and any future uses of the transaction will throw an exception. The transaction can be used again after it is reset. Like all transaction options, a timeout must be reset after a call to onError. This behavior allows the user to make the timeout dynamic.
    // Parameter: (Int) value in milliseconds of timeout
    FDB_TR_OPTION_TIMEOUT=500,

    // Set a maximum number of retries after which additional calls to onError will throw the most recently seen error code. Valid parameter values are ``[-1, INT_MAX]``. If set to -1, will disable the retry limit. Like all transaction options, the retry limit must be reset after a call to onError. This behavior allows the user to make the retry limit dynamic.
    // Parameter: (Int) number of times to retry
    FDB_TR_OPTION_RETRY_LIMIT=501,

    // Set the maximum amount of backoff delay incurred in the call to onError if the error is retryable. Defaults to 1000 ms. Valid parameter values are ``[0, INT_MAX]``. Like all transaction options, the maximum retry delay must be reset after a call to onError. If the maximum retry delay is less than the current retry delay of the transaction, then the current retry delay will be clamped to the maximum retry delay.
    // Parameter: (Int) value in milliseconds of maximum delay
    FDB_TR_OPTION_MAX_RETRY_DELAY=502,

    // Snapshot read operations will see the results of writes done in the same transaction.
    // Parameter: Option takes no parameter
    FDB_TR_OPTION_SNAPSHOT_RYW_ENABLE=600,

    // Snapshot read operations will not see the results of writes done in the same transaction.
    // Parameter: Option takes no parameter
    FDB_TR_OPTION_SNAPSHOT_RYW_DISABLE=601,

    // The transaction can read and write to locked databases, and is resposible for checking that it took the lock.
    // Parameter: Option takes no parameter
    FDB_TR_OPTION_LOCK_AWARE=700,

    // By default, operations that are performed on a transaction while it is being committed will not only fail themselves, but they will attempt to fail other in-flight operations (such as the commit) as well. This behavior is intended to help developers discover situations where operations could be unintentionally executed after the transaction has been reset. Setting this option removes that protection, causing only the offending operation to fail.
    // Parameter: Option takes no parameter
    FDB_TR_OPTION_USED_DURING_COMMIT_PROTECTION_DISABLE=701,

    // The transaction can read from locked databases.
    // Parameter: Option takes no parameter
    FDB_TR_OPTION_READ_LOCK_AWARE=702
} FDBTransactionOption;

typedef enum {
    // Client intends to consume the entire range and would like it all transferred as early as possible.
    FDB_STREAMING_MODE_WANT_ALL=-2,

    // The default. The client doesn't know how much of the range it is likely to used and wants different performance concerns to be balanced. Only a small portion of data is transferred to the client initially (in order to minimize costs if the client doesn't read the entire range), and as the caller iterates over more items in the range larger batches will be transferred in order to minimize latency.
    FDB_STREAMING_MODE_ITERATOR=-1,

    // Infrequently used. The client has passed a specific row limit and wants that many rows delivered in a single batch. Because of iterator operation in client drivers make request batches transparent to the user, consider ``WANT_ALL`` StreamingMode instead. A row limit must be specified if this mode is used.
    FDB_STREAMING_MODE_EXACT=0,

    // Infrequently used. Transfer data in batches small enough to not be much more expensive than reading individual rows, to minimize cost if iteration stops early.
    FDB_STREAMING_MODE_SMALL=1,

    // Infrequently used. Transfer data in batches sized in between small and large.
    FDB_STREAMING_MODE_MEDIUM=2,

    // Infrequently used. Transfer data in batches large enough to be, in a high-concurrency environment, nearly as efficient as possible. If the client stops iteration early, some disk and network bandwidth may be wasted. The batch size may still be too small to allow a single client to get high throughput from the database, so if that is what you need consider the SERIAL StreamingMode.
    FDB_STREAMING_MODE_LARGE=3,

    // Transfer data in batches large enough that an individual client can get reasonable read bandwidth from the database. If the client stops iteration early, considerable disk and network bandwidth may be wasted.
    FDB_STREAMING_MODE_SERIAL=4
} FDBStreamingMode;

typedef enum {
    // Performs an addition of little-endian integers. If the existing value in the database is not present or shorter than ``param``, it is first extended to the length of ``param`` with zero bytes.  If ``param`` is shorter than the existing value in the database, the existing value is truncated to match the length of ``param``. The integers to be added must be stored in a little-endian representation.  They can be signed in two's complement representation or unsigned. You can add to an integer at a known offset in the value by prepending the appropriate number of zero bytes to ``param`` and padding with zero bytes to match the length of the value. However, this offset technique requires that you know the addition will not cause the integer field within the value to overflow.
    FDB_MUTATION_TYPE_ADD=2,

    // Deprecated
    FDB_MUTATION_TYPE_AND=6,

    // Performs a bitwise ``and`` operation.  If the existing value in the database is not present, then ``param`` is stored in the database. If the existing value in the database is shorter than ``param``, it is first extended to the length of ``param`` with zero bytes.  If ``param`` is shorter than the existing value in the database, the existing value is truncated to match the length of ``param``.
    FDB_MUTATION_TYPE_BIT_AND=6,

    // Deprecated
    FDB_MUTATION_TYPE_OR=7,

    // Performs a bitwise ``or`` operation.  If the existing value in the database is not present or shorter than ``param``, it is first extended to the length of ``param`` with zero bytes.  If ``param`` is shorter than the existing value in the database, the existing value is truncated to match the length of ``param``.
    FDB_MUTATION_TYPE_BIT_OR=7,

    // Deprecated
    FDB_MUTATION_TYPE_XOR=8,

    // Performs a bitwise ``xor`` operation.  If the existing value in the database is not present or shorter than ``param``, it is first extended to the length of ``param`` with zero bytes.  If ``param`` is shorter than the existing value in the database, the existing value is truncated to match the length of ``param``.
    FDB_MUTATION_TYPE_BIT_XOR=8,

    // Performs a little-endian comparison of byte strings. If the existing value in the database is not present or shorter than ``param``, it is first extended to the length of ``param`` with zero bytes.  If ``param`` is shorter than the existing value in the database, the existing value is truncated to match the length of ``param``. The larger of the two values is then stored in the database.
    FDB_MUTATION_TYPE_MAX=12,

    // Performs a little-endian comparison of byte strings. If the existing value in the database is not present, then ``param`` is stored in the database. If the existing value in the database is shorter than ``param``, it is first extended to the length of ``param`` with zero bytes.  If ``param`` is shorter than the existing value in the database, the existing value is truncated to match the length of ``param``. The smaller of the two values is then stored in the database.
    FDB_MUTATION_TYPE_MIN=13,

    // Transforms ``key`` using a versionstamp for the transaction. Sets the transformed key in the database to ``param``. A versionstamp is a 10 byte, unique, monotonically (but not sequentially) increasing value for each committed transaction. The first 8 bytes are the committed version of the database. The last 2 bytes are monotonic in the serialization order for transactions. WARNING: At this time versionstamps are compatible with the Tuple layer only in the Java and Python bindings. Note that this implies versionstamped keys may not be used with the Subspace and Directory layers except in those languages.
    FDB_MUTATION_TYPE_SET_VERSIONSTAMPED_KEY=14,

    // Transforms ``param`` using a versionstamp for the transaction. Sets ``key`` in the database to the transformed parameter. A versionstamp is a 10 byte, unique, monotonically (but not sequentially) increasing value for each committed transaction. The first 8 bytes are the committed version of the database. The last 2 bytes are monotonic in the serialization order for transactions. WARNING: At this time versionstamped values are not compatible with the Tuple layer.
    FDB_MUTATION_TYPE_SET_VERSIONSTAMPED_VALUE=15,

    // Performs lexicographic comparison of byte strings. If the existing value in the database is not present, then ``param`` is stored. Otherwise the smaller of the two values is then stored in the database.
    FDB_MUTATION_TYPE_BYTE_MIN=16,

    // Performs lexicographic comparison of byte strings. If the existing value in the database is not present, then ``param`` is stored. Otherwise the larger of the two values is then stored in the database.
    FDB_MUTATION_TYPE_BYTE_MAX=17
} FDBMutationType;

typedef enum {
    // Used to add a read conflict range
    FDB_CONFLICT_RANGE_TYPE_READ=0,

    // Used to add a write conflict range
    FDB_CONFLICT_RANGE_TYPE_WRITE=1
} FDBConflictRangeType;

typedef enum {
    // Returns ``true`` if the error indicates the operations in the transactions should be retried because of transient error.
    FDB_ERROR_PREDICATE_RETRYABLE=50000,

    // Returns ``true`` if the error indicates the transaction may have succeeded, though not in a way the system can verify.
    FDB_ERROR_PREDICATE_MAYBE_COMMITTED=50001,

    // Returns ``true`` if the error indicates the transaction has not committed, though in a way that can be retried.
    FDB_ERROR_PREDICATE_RETRYABLE_NOT_COMMITTED=50002
} FDBErrorPredicate;

/* end of fdb_c_options.g.h */

/* Pointers to these opaque types represent objects in the FDB API */
typedef struct future FDBFuture;
typedef struct cluster FDBCluster;
typedef struct database FDBDatabase;
typedef struct transaction FDBTransaction;

typedef int fdb_error_t;
typedef int fdb_bool_t;

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

#pragma pack(push, 4)
typedef struct keyvalue {
  const void* key;
  int key_length;
  const void* value;
  int value_length;
} FDBKeyValue;
#pragma pack(pop)



void fdb_future_cancel( FDBFuture *f );

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
fdb_future_get_version( FDBFuture* f, int64_t* out_version );

fdb_error_t
fdb_future_get_key( FDBFuture* f, uint8_t const** out_key,
		    int* out_key_length );

fdb_error_t
fdb_future_get_cluster( FDBFuture* f, FDBCluster** out_cluster );

fdb_error_t
fdb_future_get_database( FDBFuture* f, FDBDatabase** out_database );

fdb_error_t
fdb_future_get_value( FDBFuture* f, fdb_bool_t *out_present,
		      uint8_t const** out_value,
		      int* out_value_length );

fdb_error_t
fdb_future_get_keyvalue_array( FDBFuture* f, FDBKeyValue const** out_kv,
			       int* out_count, fdb_bool_t* out_more );

fdb_error_t fdb_future_get_string_array(FDBFuture* f,
					const char*** out_strings, int* out_count);

FDBFuture* fdb_create_cluster( const char* cluster_file_path );

void fdb_cluster_destroy( FDBCluster* c );

fdb_error_t
fdb_cluster_set_option( FDBCluster* c, FDBClusterOption option,
			uint8_t const* value, int value_length );

FDBFuture*
fdb_cluster_create_database( FDBCluster* c, uint8_t const* db_name,
			     int db_name_length );

void fdb_database_destroy( FDBDatabase* d );

fdb_error_t
fdb_database_set_option( FDBDatabase* d, FDBDatabaseOption option,
			 uint8_t const* value, int value_length );

fdb_error_t
fdb_database_create_transaction( FDBDatabase* d,
				 FDBTransaction** out_transaction );

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

fdb_error_t
fdb_select_api_version_impl( int runtime_version, int header_version );

int fdb_get_max_api_version();
const char* fdb_get_client_version();