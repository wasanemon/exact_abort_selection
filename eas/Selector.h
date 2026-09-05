#pragma once

#include <cstdint>
#include <functional>
#include <limits>
#include <stdexcept>
#include <string>
#include <tuple>
#include <vector>

namespace eas {
struct Key {
  uint64_t table = 0, partition = 0, value = 0;
  bool operator==(const Key &o) const {
    return std::tie(table, partition, value) == std::tie(o.table, o.partition, o.value);
  }
  bool operator<(const Key &o) const {
    return std::tie(table, partition, value) < std::tie(o.table, o.partition, o.value);
  }
};
struct Input {
  uint64_t id = 0;
  std::vector<Key> reads, writes;
  bool remote = false, range = false;
};
struct Options {
  std::string mode = "adaptive";
  size_t k = 2;
  size_t max_arity = 8;
  size_t max_incidence = 8000000;
  size_t max_graph_bytes = 512ull * 1024 * 1024;
  size_t profile_B = 0; // 0: theorem's default. Nonzero is for tests only.
  uint64_t adaptive_budget = std::numeric_limits<uint64_t>::max(); // default
  // Testing only: independently inspect the graph at every frozen round.
  bool audit_degrees = false;
};
struct Batch {
  std::vector<uint64_t> ids;
  std::vector<std::vector<uint32_t>> keys;
  size_t key_count = 0, arity = 0, incidences = 0, accesses = 0;
};
struct Stats {
  size_t initial_core_size = 0, subsets = 0, incidences = 0;
  size_t profiles = 0, heavy_subsets = 0, profile_links = 0, B = 0;
  uint64_t degree_queries = 0, light_scans = 0, heavy_updates = 0;
  uint64_t tree_updates = 0, trim_key_visits = 0, switches = 0;
  uint64_t switch_round = 0, switch_remaining = 0, switch_queries = 0;
  uint64_t graph_bytes = 0, index_payload_bytes = 0;
  double normalize_ms = 0, build_ms = 0, trim_ms = 0;
  double select_ms = 0, switch_ms = 0, certificate_ms = 0;
  double kernel_ms = 0, total_ms = 0;
  double count_ms = 0, sort_ms = 0;
  uint64_t initial_degree_evaluations = 0, acceptance_key_visits = 0;
};
struct Result {
  std::vector<std::vector<uint64_t>> abort_rounds;
  std::vector<uint8_t> commit;
  std::vector<uint64_t> certificate;
  // Acceptance policies expose their own order/rejections, never fake EAS rounds.
  std::vector<uint64_t> consideration_order, rejected_ids;
  std::vector<int64_t> initial_degrees; // input order, static policy only
  Stats stats;
};
class Unsupported : public std::runtime_error {
public:
  using std::runtime_error::runtime_error;
};
Batch normalize(const std::vector<Input> &input, const Options &options);
Result select(const Batch &batch, const Options &options);
Result run(const std::vector<Input> &input, const Options &options);
// Deliberately separate, small-input all-pairs/all-rounds reference.
Result oracle(const std::vector<Input> &input, size_t k);
Result acceptance_oracle(const std::vector<Input> &input, bool static_degree);
bool is_acceptance(const std::string &mode);
bool same_decisions(const Result &a, const Result &b);
} // namespace eas
