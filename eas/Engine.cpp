#include "eas/Engine.h"
#include "core/AriaExperiment.h"
#include "common/Random.h"
#include "core/Table.h"
#include "protocol/Aria/AriaManager.h"

#include <fstream>
#include <iomanip>
#include <limits>
#include <sstream>
#include <sys/resource.h>
#include <thread>

namespace eas {
namespace {
uint64_t unsigned_number(const std::string &s) {
  if (s.empty() || s.find_first_not_of("0123456789") != std::string::npos)
    throw Unsupported("expected unsigned decimal integer");
  size_t pos = 0;
  uint64_t value = std::stoull(s, &pos);
  if (pos != s.size()) throw Unsupported("invalid integer");
  return value;
}
struct EngineContext : aria::Context { size_t key_count = 0; };
struct Storage {
  // Read/write logical keys deliberately have distinct, stable addresses.
  std::vector<uint64_t> read_keys, write_keys;
  std::vector<Value> reads, writes;
};
struct Database {
  using ContextType = EngineContext;
  using RandomType = aria::Random;
  using StorageType = Storage;
  aria::Table<9973, uint64_t, Value> table{0, 0};
  size_t key_count;
  explicit Database(size_t count) : key_count(count) {
    for (uint64_t k = 0; k < count; ++k) {
      Value value;
      for (size_t lane = 0; lane < 4; ++lane)
        value.words[lane] = (k + 1) * 0x9e3779b97f4a7c15ULL + (lane + 1) * 0x100000001b3ULL;
      table.insert(&k, &value);
    }
  }
  aria::ITable *find_table(size_t table_id, size_t partition_id) {
    if (table_id || partition_id) throw Unsupported("experimental database has only local table 0 / partition 0");
    return &table;
  }
  std::vector<Value> state() {
    std::vector<Value> out(key_count);
    for (uint64_t k = 0; k < key_count; ++k)
      out[k] = *static_cast<Value *>(table.search_value(&k));
    return out;
  }
};
class Transaction : public aria::AriaTransaction {
public:
  Storage &storage;
  Transaction(aria::Partitioner &partitioner, Storage &s)
      : AriaTransaction(0, 0, partitioner), storage(s) {}
  aria::TransactionResult execute(size_t worker) override {
    for (size_t j = 0; j < storage.read_keys.size(); ++j)
      search_for_update(0, 0, storage.read_keys[j], storage.reads[j]);
    process_requests(worker);
    if (execution_phase) {
      uint64_t sum = 0;
      for (size_t j = 0; j < storage.reads.size(); ++j)
        for (size_t lane = 0; lane < 4; ++lane)
          sum += storage.reads[j].words[lane] * (j + lane + 1);
      for (size_t j = 0; j < storage.writes.size(); ++j)
        for (size_t lane = 0; lane < 4; ++lane)
          storage.writes[j].words[lane] =
              storage.reads[j].words[lane] * 0xd6e8feb86659fd93ULL ^
              (sum + id * 0xa0761d6478bd642fULL + storage.write_keys[j] + lane);
    }
    for (size_t j = 0; j < storage.write_keys.size(); ++j)
      update(0, 0, storage.write_keys[j], storage.writes[j]);
    return aria::TransactionResult::READY_TO_COMMIT;
  }
  void reset_query() override {} // finite saved trace; no retry generator
};
struct Workload {
  using TransactionType = aria::AriaTransaction;
  using DatabaseType = Database;
  using StorageType = Storage;
  aria::Partitioner &partitioner;
  Workload(size_t, Database &, aria::Random &, aria::Partitioner &p) : partitioner(p) {}
  std::unique_ptr<TransactionType> next_transaction(const EngineContext &, size_t, Storage &storage) {
    return std::unique_ptr<TransactionType>(new Transaction(partitioner, storage));
  }
};

class Hook : public aria::AriaExperiment {
public:
  Database &db;
  const std::vector<Trace> &traces;
  const Options &options;
  std::vector<Storage> &storages;
  std::vector<Measurement> measurements;
  std::vector<Value> initial;
  uint64_t begin = 0, commit_begin = 0;
  std::exception_ptr failure;
  Hook(Database &db, const std::vector<Trace> &traces, const Options &o,
       std::vector<Storage> &storages, size_t workers)
      : db(db), traces(traces), options(o), storages(storages) {
    use_decisions = o.mode != "native";
    worker_times.resize(workers);
    decisions.resize(traces.front().input.size());
    committed.resize(decisions.size());
  }
  void before_read(uint32_t epoch) override {
    const auto &trace = traces.at(epoch - 1);
    // These preparations are deliberately outside the snapshot-to-commit interval.
    initial = db.state();
    for (size_t t = 0; t < trace.input.size(); ++t) {
      auto &s = storages[t];
      s.read_keys.clear();
      for (const auto &key : trace.input[t].reads) s.read_keys.push_back(key.value);
      std::sort(s.read_keys.begin(), s.read_keys.end());
      s.read_keys.erase(std::unique(s.read_keys.begin(), s.read_keys.end()), s.read_keys.end());
      s.write_keys = s.read_keys;
      s.reads.assign(s.read_keys.size(), Value{});
      s.writes.assign(s.read_keys.size(), Value{});
    }
    std::fill(decisions.begin(), decisions.end(), 0);
    std::fill(committed.begin(), committed.end(), 0);
    std::fill(worker_times.begin(), worker_times.end(), WorkerTimes{});
    measurements.emplace_back();
    begin = now();
  }
  void after_read(uint32_t,
      const std::vector<std::unique_ptr<aria::AriaTransaction>> &txns) override {
    auto &m = measurements.back();
    m.read_wall_ms = (now() - begin) / 1e6;
    try {
      if (use_decisions) {
        const auto extract_begin = now();
        {
          const auto input = extract_transactions(txns, db.key_count);
          auto batch = normalize(input, options);
          m.extract_ms = (now() - extract_begin) / 1e6;
          m.result = select(batch, options);
          decisions = m.result.commit;
        } // Include extraction-buffer release and decision publication copy.
        m.result.stats.normalize_ms = m.extract_ms;
        m.selector_ms = (now() - extract_begin) / 1e6;
        m.result.stats.total_ms = m.selector_ms;
      }
    } catch (...) {
      // Finish both real phases so workers can exit even after a capacity error.
      failure = std::current_exception(); use_decisions = true;
      std::fill(decisions.begin(), decisions.end(), 0);
    }
    commit_begin = now();
  }
  bool after_commit(uint32_t epoch,
      const std::vector<std::unique_ptr<aria::AriaTransaction>> &txns) override {
    const auto end = now();
    auto &m = measurements.back();
    m.batch_ms = (end - begin) / 1e6;
    m.commit_wall_ms = (end - commit_begin) / 1e6;
    double max_read = 0, max_commit = 0;
    for (const auto &w : worker_times) {
      const double read = (w.read_end - w.read_begin) / 1e6;
      const double commit = (w.commit_end - w.commit_begin) / 1e6;
      max_read = std::max(max_read, read); max_commit = std::max(max_commit, commit);
      m.read_worker_ms += read; m.commit_worker_ms += commit;
      m.reservation_worker_ms += w.reservation / 1e6;
      m.dependency_worker_ms += w.dependency / 1e6;
      m.apply_worker_ms += w.apply / 1e6;
    }
    // Residual wall time includes launch skew, barrier handshakes and idle workers;
    // it is NOT a sum of each worker's blocked CPU time.
    m.sync_wait_ms = std::max(0.0, m.read_wall_ms - max_read) +
                     std::max(0.0, m.commit_wall_ms - max_commit);
    if (failure) return true;
    try {
      if (!use_decisions) {
        m.result.commit = committed;
        for (size_t t = 0; t < committed.size(); ++t)
          if (committed[t]) m.result.certificate.push_back(txns[t]->id);
      } else if (committed != decisions) throw std::logic_error("published decision/application mismatch");
      verify(txns, traces.at(epoch - 1), m);
    } catch (...) { failure = std::current_exception(); return true; }
    return epoch == traces.size();
  }
  void verify(const std::vector<std::unique_ptr<aria::AriaTransaction>> &txns,
              const Trace &trace, Measurement &m) {
    // This method is entirely outside all measured time intervals.
    auto actual = extract_transactions(txns, db.key_count);
    Options validate = options; if (validate.mode == "native") validate.mode = "graph";
    auto actual_batch = normalize(actual, validate);
    if (!same_logical_inputs(actual, trace.input))
      throw std::logic_error("executed R/W sets differ from trace");
    if (!use_decisions) {
      // Descriptive native input statistic, collected outside its validation time.
      std::vector<size_t> counts(actual_batch.key_count);
      for (const auto &keys : actual_batch.keys) for (auto key : keys) ++counts[key];
      for (const auto &keys : actual_batch.keys)
        for (auto key : keys) if (counts[key] > 1) { ++m.result.stats.initial_core_size; break; }
    }
    if (use_decisions && txns.size() <= 64 && !same_decisions(m.result, oracle(actual, options.k)))
      throw std::logic_error("engine decisions differ from independent oracle");
    auto sequential = initial;
    std::vector<uint8_t> touched(db.key_count);
    for (size_t t = 0; t < txns.size(); ++t) {
      const auto &txn = *txns[t];
      if (txn.epoch != measurements.size() || txn.id != t + 1 || txn.tid_offset != t)
        throw std::logic_error("epoch/ID state leaked across batches");
      const auto &s = storages[t];
      // Independent scalar re-execution: never invoke Transaction::execute or its transform.
      uint64_t checksum = 0;
      for (size_t j = 0; j < s.read_keys.size(); ++j) {
        auto key = s.read_keys[j];
        if (s.reads[j] != initial[key]) throw std::logic_error("snapshot value mismatch");
        for (size_t lane = 0; lane != 4; ++lane)
          checksum = checksum + initial[key].words[lane] * uint64_t(j + lane + 1);
      }
      for (size_t j = 0; j < s.read_keys.size(); ++j) {
        const auto key = s.read_keys[j];
        Value expected;
        for (size_t lane = 0; lane != 4; ++lane) {
          const uint64_t product = initial[key].words[lane] * UINT64_C(0xd6e8feb86659fd93);
          const uint64_t tag = checksum + txn.id * UINT64_C(0xa0761d6478bd642f) + key + lane;
          expected.words[lane] = product ^ tag;
        }
        const auto &read = txn.readSet[j]; const auto &write = txn.writeSet[j];
        if (read.get_key() == write.get_key()) throw std::logic_error("alias-address test not exercised");
        if (*static_cast<const Value *>(write.get_value()) != expected || s.writes[j] != expected)
          throw std::logic_error("private write value mismatch");
        if (m.result.commit[t]) {
          if (touched[key]++) throw std::logic_error("committed complete RMW sets intersect");
          if (sequential[key] != s.reads[j]) throw std::logic_error("serial re-execution read mismatch");
          sequential[key] = expected;
        }
      }
    }
    m.final_state = db.state();
    if (m.final_state != sequential) throw std::logic_error("full final database differs from serial execution");
  }
};
} // namespace

Trace read_trace(const std::string &path) {
  std::ifstream in(path);
  if (!in) throw Unsupported("cannot read trace: " + path);
  Trace trace;
  std::string line;
  if (!std::getline(in, line)) throw Unsupported("missing trace header");
  std::istringstream header(line);
  std::string magic, count, seed, batch, extra;
  if (!(header >> magic >> count >> seed >> batch) || header >> extra || magic != "EAS_TRACE_V1")
    throw Unsupported("invalid EAS_TRACE_V1 header");
  trace.key_count = unsigned_number(count); trace.seed = unsigned_number(seed); trace.batch_id = unsigned_number(batch);
  if (!trace.key_count || trace.key_count > 1000000) throw Unsupported("key_count must be 1..1000000");
  while (std::getline(in, line)) {
    if (!line.empty() && line.back() == '\r') line.pop_back();
    auto tab = line.find('\t');
    if (tab == std::string::npos) throw Unsupported("trace row must be ID TAB keys");
    Input t; t.id = unsigned_number(line.substr(0, tab));
    std::string list = line.substr(tab + 1);
    if (!list.empty()) {
      if (list.back() == ',') throw Unsupported("trailing comma in trace");
      std::istringstream keys(list); std::string key;
      while (std::getline(keys, key, ',')) {
        const auto k = unsigned_number(key);
        if (k >= trace.key_count) throw Unsupported("trace key outside declared domain");
        t.reads.push_back({0, 0, k});
      }
    }
    t.writes = t.reads; trace.input.push_back(std::move(t));
    if (trace.input.size() >= (1u << 20)) throw Unsupported("Aria 20-bit transaction ID capacity exceeded");
  }
  return trace;
}
bool same_logical_inputs(const std::vector<Input> &a, const std::vector<Input> &b) {
  if (a.size() != b.size()) return false;
  auto canonical = [](std::vector<Key> keys) {
    std::sort(keys.begin(), keys.end());
    keys.erase(std::unique(keys.begin(), keys.end()), keys.end());
    return keys;
  };
  for (size_t t = 0; t < a.size(); ++t)
    if (a[t].id != b[t].id || a[t].remote != b[t].remote || a[t].range != b[t].range ||
        canonical(a[t].reads) != canonical(b[t].reads) ||
        canonical(a[t].writes) != canonical(b[t].writes)) return false;
  return true;
}
std::vector<Input> extract_transactions(
    const std::vector<std::unique_ptr<aria::AriaTransaction>> &txns, size_t key_count) {
  std::vector<Input> result;
  result.reserve(txns.size());
  for (const auto &ptr : txns) {
    if (!ptr) throw Unsupported("missing executed transaction");
    const auto &t = *ptr;
    if (t.coordinator_id || t.partition_id || t.distributed_transaction || t.pendingResponses || t.abort_no_retry)
      throw Unsupported("requires successfully executed local snapshot transaction");
    Input input; input.id = t.id;
    auto copy = [&](const std::vector<aria::AriaRWKey> &set, std::vector<Key> &out) {
      for (const auto &key : set) {
        if (key.get_table_id() || key.get_partition_id() || !key.get_key() || !key.get_value() ||
            key.get_local_index_read_bit()) throw Unsupported("unsupported record identity / local-index operation");
        const uint64_t logical = *static_cast<const uint64_t *>(key.get_key());
        if (logical >= key_count) throw Unsupported("logical key outside database");
        out.push_back({key.get_table_id(), key.get_partition_id(), logical});
      }
    };
    copy(t.readSet, input.reads); copy(t.writeSet, input.writes);
    result.push_back(std::move(input));
  }
  return result;
}
std::vector<Measurement> run_engine(const std::vector<Trace> &traces,
                                    const Options &options, size_t workers) {
  if (traces.empty() || traces.size() >= (1u << 24) || !workers || workers > 256)
    throw Unsupported("invalid batch count / worker count");
  if (options.max_arity > 8) throw Unsupported("selector arity cap exceeds 8");
  const size_t n = traces.front().input.size(), key_count = traces.front().key_count;
  if (n >= (1u << 20) || !key_count || key_count > 1000000) throw Unsupported("Aria ID / database capacity");
  Options validate = options; if (validate.mode == "native") validate.mode = "graph";
  for (const auto &trace : traces) {
    if (trace.input.size() != n || trace.key_count != key_count) throw Unsupported("smoke batches must share n/domain");
    auto b = normalize(trace.input, validate);
    if (b.arity > 4) throw Unsupported("real-engine workload supports at most 4 keys; use selector-only for 6/8");
    for (size_t t = 0; t < n; ++t) {
      if (trace.input[t].id != t + 1) throw Unsupported("Aria trace IDs must be contiguous 1..n in order");
      for (const auto &key : trace.input[t].reads)
        if (key.table || key.partition || key.value >= key_count) throw Unsupported("only table 0 / partition 0 local keys");
    }
  }
  EngineContext context;
  context.protocol = "Aria"; context.coordinator_num = 1; context.coordinator_id = 0;
  context.partition_num = 1; context.worker_num = workers; context.batch_size = n;
  context.partitioner = "hash"; context.key_count = key_count;
  context.aria_snapshot_isolation = false; context.aria_reordering_optmization = true;
  Database db(key_count);
  std::atomic<bool> stop{false};
  aria::AriaManager<Workload> manager(0, workers, db, context, stop);
  Hook hook(db, traces, options, manager.storages, workers);
  context.aria_experiment = &hook;
  std::vector<std::unique_ptr<aria::AriaExecutor<Workload>>> executors;
  std::vector<std::thread> threads;
  for (size_t worker = 0; worker < workers; ++worker) {
    executors.emplace_back(new aria::AriaExecutor<Workload>(0, worker, db, context,
        manager.transactions, manager.storages, manager.epoch, manager.worker_status,
        manager.total_abort, manager.n_completed_workers, manager.n_started_workers));
  }
  for (auto &executor : executors) {
    auto *worker = executor.get();
    threads.emplace_back([worker] { worker->start(); });
  }
  manager.coordinator_start();
  for (auto &thread : threads) thread.join();
  if (hook.failure) std::rethrow_exception(hook.failure);
  return std::move(hook.measurements);
}

std::string measurement_json(const Measurement &m, const Trace &trace,
    const Options &o, size_t workers, bool selector_only) {
  std::ostringstream out; out << std::setprecision(12);
  size_t commits = 0, min_arity = trace.input.empty() ? 0 : 8, max_arity = 0, access = 0;
  for (auto c : m.result.commit) commits += c;
  for (const auto &t : trace.input) {
    auto keys = t.reads; std::sort(keys.begin(), keys.end());
    keys.erase(std::unique(keys.begin(), keys.end()), keys.end());
    min_arity = std::min(min_arity, keys.size()); max_arity = std::max(max_arity, keys.size()); access += keys.size();
  }
  struct rusage usage{}; getrusage(RUSAGE_SELF, &usage);
  out << "{\"status\":\"ok\",\"verification\":\"passed\",\"mode\":\"" << o.mode
      << "\",\"policy_k\":" << o.k << ",\"seed\":" << trace.seed << ",\"batch_id\":" << trace.batch_id
      << ",\"n\":" << trace.input.size() << ",\"actual_arity\":" << (trace.input.empty() ? 0 : double(access) / trace.input.size())
      << ",\"arity_min\":" << min_arity << ",\"arity_max\":" << max_arity << ",\"key_count\":" << trace.key_count
      << ",\"workers\":" << workers << ",\"selector_only\":" << (selector_only ? "true" : "false")
      << ",\"initial_core_size\":" << m.result.stats.initial_core_size
      << ",\"commit_count\":" << commits << ",\"abort_count\":" << (trace.input.size() - commits)
      << ",\"round_count\":" << m.result.abort_rounds.size()
      << ",\"peak_rss_kib\":" << usage.ru_maxrss << ",\"value_bytes\":32"
      << ",\"aria_snapshot_isolation\":false,\"aria_reordering_optmization\":true"
      << ",\"batch_ms\":";
  if (selector_only) out << "null"; else out << m.batch_ms;
#define FIELD(name) out << ",\"" #name "\":" << m.name
  FIELD(read_wall_ms); FIELD(commit_wall_ms); FIELD(read_worker_ms); FIELD(commit_worker_ms);
  FIELD(reservation_worker_ms); FIELD(dependency_worker_ms); FIELD(apply_worker_ms);
  FIELD(sync_wait_ms); FIELD(extract_ms); FIELD(selector_ms);
#undef FIELD
  out << ",\"selector\":{";
  const auto &s = m.result.stats;
  out << "\"initial_core_size\":" << s.initial_core_size;
#define STAT(name) out << ",\"" #name "\":" << s.name
  STAT(subsets); STAT(incidences); STAT(profiles); STAT(heavy_subsets); STAT(profile_links); STAT(B);
  STAT(degree_queries); STAT(light_scans); STAT(heavy_updates); STAT(tree_updates); STAT(trim_key_visits);
  STAT(switches); STAT(switch_round); STAT(switch_remaining); STAT(switch_queries);
  STAT(graph_bytes); STAT(index_payload_bytes); STAT(normalize_ms); STAT(build_ms); STAT(trim_ms);
  STAT(select_ms); STAT(switch_ms); STAT(certificate_ms); STAT(kernel_ms); STAT(total_ms);
#undef STAT
  out << "},\"decisions\":{\"abort_rounds\":[";
  for (size_t i = 0; i < m.result.abort_rounds.size(); ++i) {
    if (i) out << ',';
    out << '[';
    for (size_t j = 0; j < m.result.abort_rounds[i].size(); ++j) {
      if (j) out << ',';
      out << m.result.abort_rounds[i][j];
    }
    out << ']';
  }
  out << "],\"commit\":[";
  for (size_t i = 0; i < m.result.commit.size(); ++i) { if (i) out << ','; out << unsigned(m.result.commit[i]); }
  out << "],\"certificate\":[";
  for (size_t i = 0; i < m.result.certificate.size(); ++i) { if (i) out << ','; out << m.result.certificate[i]; }
  out << "]}}";
  return out.str();
}
} // namespace eas
