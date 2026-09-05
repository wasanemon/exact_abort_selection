#include "eas/Selector.h"

#include <algorithm>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <limits>
#include <random>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
using eas::Input;
using eas::Key;
using eas::Options;
using eas::Result;
struct Counts {
  uint64_t exhaustive_batches = 0, random_batches = 0, targeted_batches = 0;
  uint64_t oracle_runs = 0, selector_runs = 0, audited_rounds = 0;
  uint64_t rejection_checks = 0, observed_switches = 0;
} counts;
std::string failure_dir = "experiments/eas/validation";
const uint64_t seeds[] = {1, 7, 20260905, 0x9e3779b97f4a7c15ULL};

void require(bool condition, const std::string &message) {
  if (!condition) throw std::runtime_error(message);
}
std::string quote(const std::string &value) {
  std::ostringstream out; out << '"';
  for (char c : value) {
    if (c == '\\' || c == '"') out << '\\';
    if (c == '\n') out << "\\n"; else out << c;
  }
  out << '"'; return out.str();
}
template <typename T> void array(std::ostream &out, const std::vector<T> &values) {
  out << '[';
  for (size_t i = 0; i < values.size(); ++i) { if (i) out << ','; out << +values[i]; }
  out << ']';
}
void result_json(std::ostream &out, const Result &r) {
  out << "{\"abort_rounds\":[";
  for (size_t i = 0; i < r.abort_rounds.size(); ++i) { if (i) out << ','; array(out, r.abort_rounds[i]); }
  out << "],\"commit\":"; array(out, r.commit);
  out << ",\"certificate\":"; array(out, r.certificate); out << '}';
}
void save_failure(const std::string &label, const std::vector<Input> &input,
                  const Options &o, const Result &expected,
                  const Result &actual, const std::string &error) {
  std::ofstream out(failure_dir + "/selector_failure.json");
  out << "{\"label\":" << quote(label) << ",\"error\":" << quote(error)
      << ",\"mode\":" << quote(o.mode) << ",\"k\":" << o.k
      << ",\"profile_B\":" << o.profile_B << ",\"adaptive_budget\":" << o.adaptive_budget
      << ",\"input\":[";
  for (size_t t = 0; t < input.size(); ++t) {
    if (t) out << ',';
    out << "{\"id\":" << input[t].id << ",\"keys\":[";
    for (size_t j = 0; j < input[t].reads.size(); ++j) {
      if (j) out << ',';
      auto key = input[t].reads[j];
      out << '[' << key.table << ',' << key.partition << ',' << key.value << ']';
    }
    out << "]}";
  }
  out << "],\"expected\":"; result_json(out, expected);
  out << ",\"actual\":"; result_json(out, actual); out << "}\n";
}
Input txn(uint64_t id, std::vector<Key> keys) {
  Input t; t.id = id; t.reads = keys; t.writes = std::move(keys); return t;
}
Input txn(uint64_t id, std::initializer_list<uint64_t> values) {
  std::vector<Key> keys;
  for (auto value : values) keys.push_back(Key{0, 0, value});
  return txn(id, keys);
}
// This certificate check uses the original logical keys, independently of dense
// normalization, subset incidences, profile ranks, and the reference oracle.
void verify_certificate(const std::vector<Input> &input, const Result &r) {
  require(r.commit.size() == input.size(), "commit mask length");
  std::set<uint64_t> seen;
  for (const auto &round : r.abort_rounds) {
    require(!round.empty(), "empty abort round");
    for (auto id : round) require(seen.insert(id).second, "duplicate aborted ID");
  }
  std::vector<uint64_t> committed;
  std::set<Key> used;
  for (size_t t = 0; t < input.size(); ++t) {
    if (r.commit[t]) {
      require(seen.insert(input[t].id).second, "both commit and abort");
      committed.push_back(input[t].id);
      std::set<Key> distinct(input[t].reads.begin(), input[t].reads.end());
      for (const auto &key : distinct) require(used.insert(key).second, "committed transactions overlap");
    } else require(seen.count(input[t].id), "unclassified input transaction");
  }
  require(seen.size() == input.size(), "output has unknown transaction ID");
  std::sort(committed.begin(), committed.end());
  require(committed == r.certificate, "noncanonical certificate");
}
std::vector<Options> configurations(size_t k) {
  std::vector<Options> all;
  for (const std::string mode : {"graph", "lazy", "profile", "adaptive"}) {
    Options o; o.mode = mode; o.k = k; o.audit_degrees = true;
    all.push_back(o);
    if (mode == "profile") {
      o.profile_B = 1; all.push_back(o);
      o.profile_B = 2; all.push_back(o);
    }
    if (mode == "adaptive") {
      o.adaptive_budget = 0; all.push_back(o);
      o.adaptive_budget = 1; all.push_back(o);
    }
  }
  return all;
}
void check_case(const std::vector<Input> &input, const std::string &label) {
  for (auto k : {size_t(1), size_t(2), size_t(3), input.size() + 1}) {
    Result expected = eas::oracle(input, k); ++counts.oracle_runs;
    verify_certificate(input, expected);
    for (const auto &o : configurations(k)) {
      Result actual;
      try {
        actual = eas::run(input, o); ++counts.selector_runs;
        require(eas::same_decisions(expected, actual), "oracle and selector decisions differ");
        require(actual.stats.switches <= 1, "adaptive switched more than once");
        require(o.mode == "adaptive" || actual.stats.switches == 0, "nonadaptive switch");
        const auto normalized = eas::normalize(input, o);
        require(actual.stats.trim_key_visits == 3 * normalized.accesses,
                "trim must visit each incidence twice on construction and once on deletion");
        if (actual.stats.switches) {
          require(actual.stats.switch_round > 0 && actual.stats.switch_round < actual.abort_rounds.size(),
                  "switch must happen between nonempty rounds");
          require(actual.stats.switch_remaining > 0, "switch on an empty core");
          require(normalized.arity >= 2, "ell=1 should start in profile");
        }
        if (o.mode == "profile" && o.profile_B && actual.stats.initial_core_size)
          require(actual.stats.B == o.profile_B, "forced B ignored");
        counts.audited_rounds += actual.abort_rounds.size();
        counts.observed_switches += actual.stats.switches;
      } catch (const std::exception &e) {
        save_failure(label, input, o, expected, actual, e.what());
        throw std::runtime_error(label + ": " + e.what());
      }
    }
  }
}
void exhaustive() {
  // Every ordered batch, including empty sets, duplicate signatures and all
  // component/tie patterns. Deliberately nonmonotone IDs check ID tie breaks.
  for (size_t universe : {size_t(3), size_t(4)}) {
    const size_t max_n = universe == 3 ? 4 : 3;
    const size_t alphabet = size_t(1) << universe;
    uint64_t combinations = 1;
    for (size_t n = 0; n <= max_n; ++n) {
      for (uint64_t code = 0; code < combinations; ++code) {
        auto rest = code; std::vector<Input> input;
        for (size_t t = 0; t < n; ++t) {
          const size_t mask = rest % alphabet; rest /= alphabet;
          std::vector<Key> keys;
          for (size_t bit = 0; bit < universe; ++bit)
            if (mask & (size_t(1) << bit)) keys.push_back(Key{0, 0, bit});
          const uint64_t id = (t % 2 == 0) ? 1000 - t : t;
          input.push_back(txn(id, keys));
        }
        check_case(input, "exhaustive/u=" + std::to_string(universe) + "/n=" +
                   std::to_string(n) + "/code=" + std::to_string(code));
        ++counts.exhaustive_batches;
      }
      combinations *= alphabet;
    }
  }
}
void randomized() {
  for (uint64_t seed : seeds) for (size_t ell = 1; ell <= 4; ++ell) {
    std::mt19937_64 rng(seed ^ (ell * 0x517cc1b727220a95ULL));
    for (size_t case_id = 0; case_id < 64; ++case_id) {
      const size_t n = 1 + rng() % 48;
      const size_t universe = 1 + rng() % 32;
      std::vector<Input> input;
      for (size_t t = 0; t < n; ++t) {
        std::vector<Key> keys;
        const size_t arity = (case_id % 4 == 0) ? ell : rng() % (ell + 1);
        for (size_t j = 0; j < arity; ++j) {
          const uint64_t value = (case_id % 4 == 1) ? rng() % 3 : rng() % universe;
          keys.push_back(Key{0, 0, value});
          if (rng() % 5 == 0) keys.push_back(keys.back());
        }
        auto tr = txn(std::numeric_limits<uint64_t>::max() - t, keys);
        std::shuffle(tr.reads.begin(), tr.reads.end(), rng);
        std::shuffle(tr.writes.begin(), tr.writes.end(), rng);
        input.push_back(std::move(tr));
      }
      std::shuffle(input.begin(), input.end(), rng);
      check_case(input, "random/seed=" + std::to_string(seed) + "/ell=" +
                 std::to_string(ell) + "/case=" + std::to_string(case_id));
      ++counts.random_batches;
    }
  }
}
void targeted() {
  auto check = [](const std::vector<Input> &input, const std::string &label) {
    check_case(input, label); ++counts.targeted_batches;
  };
  const std::vector<Input> wedge{txn(1, {1, 2}), txn(2, {1, 3}), txn(3, {2, 4})};
  check(wedge, "required-wedge");
  auto r = eas::oracle(wedge, 1);
  require(r.abort_rounds == std::vector<std::vector<uint64_t>>{{1}} &&
          r.certificate == std::vector<uint64_t>({2, 3}), "wedge semantics");
  std::vector<Input> frozen;
  for (uint64_t id = 1; id <= 7; ++id) frozen.push_back(txn(id, {id <= 4 ? 1ULL : 2ULL}));
  check(frozen, "frozen-top2-counterexample");
  require(eas::oracle(frozen, 2).abort_rounds.front() == std::vector<uint64_t>({4, 3}), "frozen top-2");
  auto sequential = eas::oracle(frozen, 1);
  require(sequential.abort_rounds[0][0] == 4 && sequential.abort_rounds[1][0] == 7,
          "sequential top-1 counterexample");
  const std::vector<Input> pair{txn(1, {42}), txn(2, {42})};
  check(pair, "zero-commits");
  require(eas::oracle(pair, 1).certificate == std::vector<uint64_t>{1}, "k=1 same-key pair");
  require(eas::oracle(pair, 2).certificate.empty(), "k=2 must allow zero commits");
  const uint64_t max = std::numeric_limits<uint64_t>::max();
  check({txn(0, std::vector<Key>{{0, 0, 0}, {0, 0, max}, {0, 0, max}}),
         txn(max, std::vector<Key>{{0, 0, max}, {max, 0, 0}}),
         txn(1, std::vector<Key>{{0, max, 0}, {0, 0, 65536}}),
         txn(65536, std::vector<Key>{{0, 0, 65536}, {0, 0, 0x100000000ULL}})},
        "large-logical-key-identities-and-duplicate-operations");
  for (size_t ell : {size_t(1), size_t(2), size_t(3), size_t(4), size_t(6), size_t(8)}) {
    for (size_t pattern = 0; pattern < 4; ++pattern) {
      std::vector<Input> input;
      for (size_t t = 0; t < 24; ++t) {
        std::vector<Key> keys;
        for (size_t j = 0; j < ell; ++j) {
          const uint64_t value = pattern == 0 ? j : pattern == 1 ? t * ell + j :
            pattern == 2 ? (t % 4) * ell + j : (t + j) % (2 * ell + 1);
          keys.push_back(Key{0, 0, value});
        }
        input.push_back(txn(t + 1, keys));
      }
      check(input, "arity=" + std::to_string(ell) + "/pattern=" + std::to_string(pattern));
    }
  }
  std::vector<Input> clique;
  for (uint64_t id = 1; id <= 96; ++id) clique.push_back(txn(id, {1, 2}));
  check(clique, "adaptive-default-actually-switches");
  Options o; o.mode = "adaptive"; o.k = 1;
  auto switched = eas::run(clique, o);
  require(switched.stats.switches == 1, "default budget failed to switch on clique");
  require(switched.stats.switch_queries >= 96 * 10 && switched.stats.switch_queries < 96 * 11,
          "default budget or per-round overshoot differs from specification");
}
template <typename F> void reject(F f, const std::string &label) {
  bool rejected = false;
  try { f(); } catch (const eas::Unsupported &) { rejected = true; }
  require(rejected, "expected explicit Unsupported: " + label); ++counts.rejection_checks;
}
void invalid_inputs() {
  const std::vector<Input> pair{txn(1, {1, 2}), txn(2, {1, 2})};
  Options o;
  o.k = 0; reject([&] { eas::run(pair, o); }, "k=0");
  o = Options{}; o.mode = "native"; reject([&] { eas::run(pair, o); }, "native is outside selector API");
  o = Options{}; o.max_arity = 0; reject([&] { eas::run(pair, o); }, "zero max arity");
  o.max_arity = 9; reject([&] { eas::run(pair, o); }, "unsafe max arity");
  o = Options{}; o.max_arity = 1; reject([&] { eas::run(pair, o); }, "actual arity limit");
  o = Options{}; o.max_incidence = 5; reject([&] { eas::run(pair, o); }, "incidence cumulative overflow");
  o.max_incidence = 2; reject([&] { eas::run(pair, o); }, "single transaction incidence overflow");
  o.max_incidence = 0; reject([&] { eas::run(pair, o); }, "zero incidence budget");
  o = Options{}; o.mode = "graph"; o.max_graph_bytes = 15;
  reject([&] { eas::run(pair, o); }, "graph bytes before allocation");
  o.max_graph_bytes = 16; require(eas::same_decisions(eas::run(pair, o), eas::oracle(pair, 2)), "exact graph budget");
  o = Options{}; o.max_incidence = 6;
  require(eas::same_decisions(eas::run(pair, o), eas::oracle(pair, 2)), "exact incidence budget");
  o = Options{};
  for (int shape = 0; shape < 5; ++shape) {
    auto bad = pair;
    if (shape == 0) bad[0].remote = true;
    if (shape == 1) bad[0].range = true;
    if (shape == 2) bad[0].reads.clear();
    if (shape == 3) bad[0].writes.clear();
    if (shape == 4) bad[1].id = bad[0].id;
    reject([&] { eas::run(bad, o); }, "input shape " + std::to_string(shape));
    reject([&] { eas::oracle(bad, 2); }, "oracle shape " + std::to_string(shape));
  }
  std::vector<Key> nine;
  for (uint64_t j = 0; j < 9; ++j) nine.push_back(Key{0, 0, j});
  reject([&] { eas::run({txn(1, nine)}, o); }, "arity 9 before subset shift");
  reject([&] { eas::oracle({}, 0); }, "oracle k=0");
  std::vector<Input> too_many(257);
  for (size_t i = 0; i < too_many.size(); ++i) too_many[i].id = i;
  reject([&] { eas::oracle(too_many, 1); }, "oracle explicit small-input cap");
  const auto normal = eas::normalize(pair, o);
  for (int kind = 0; kind < 13; ++kind) {
    auto bad = normal;
    if (kind == 0) bad.ids.pop_back();
    if (kind == 1) bad.ids[1] = bad.ids[0];
    if (kind == 2) std::reverse(bad.keys[0].begin(), bad.keys[0].end());
    if (kind == 3) bad.keys[0][1] = bad.keys[0][0];
    if (kind == 4) bad.keys[0][1] = bad.key_count;
    if (kind == 5) ++bad.arity;
    if (kind == 6) ++bad.incidences;
    if (kind == 7) ++bad.accesses;
    if (kind == 8) bad.key_count = 8388609;
    if (kind == 9) { bad.ids.resize(1048577); bad.keys.resize(1048577); }
    if (kind == 10) bad.key_count = bad.accesses + 1;
    if (kind == 11) ++bad.key_count;
    if (kind == 12) { ++bad.key_count; for (auto &keys : bad.keys) for (auto &key : keys) ++key; }
    reject([&] { eas::select(bad, o); }, "malformed normalized batch " + std::to_string(kind));
  }
  // Repeated keys at distinct vector addresses normalize to the same identity;
  // table and partition dimensions remain part of that identity.
  require(pair[0].reads.data() != pair[0].writes.data() &&
          pair[0].reads.data() != pair[1].reads.data(), "test needs different key addresses");
  require(normal.key_count == 2 && normal.keys[0] == normal.keys[1], "logical identity normalization");
  auto isolated = eas::run({txn(1, std::vector<Key>{{0, 0, 1}}),
                            txn(2, std::vector<Key>{{1, 0, 1}}),
                            txn(3, std::vector<Key>{{0, 1, 1}})}, o);
  require(isolated.certificate.size() == 3, "table/partition key alias");
}
} // namespace

int main(int argc, char **argv) {
  if (argc == 3 && std::string(argv[1]) == "--failure-dir") failure_dir = argv[2];
  else if (argc != 1) { std::cerr << "usage: eas_selector_test [--failure-dir DIR]\n"; return 2; }
  try {
    exhaustive(); randomized(); targeted(); invalid_inputs();
    std::cout << "{\"status\":\"passed\",\"suite\":\"independent_selector\","
              << "\"exhaustive_universes\":[{\"keys\":3,\"n_max\":4},{\"keys\":4,\"n_max\":3}],"
              << "\"exhaustive_batches\":" << counts.exhaustive_batches
              << ",\"random_batches\":" << counts.random_batches
              << ",\"targeted_batches\":" << counts.targeted_batches
              << ",\"generated_batches\":" << counts.exhaustive_batches + counts.random_batches + counts.targeted_batches
              << ",\"oracle_runs\":" << counts.oracle_runs
              << ",\"selector_runs\":" << counts.selector_runs
              << ",\"audited_rounds\":" << counts.audited_rounds
              << ",\"observed_switches\":" << counts.observed_switches
              << ",\"rejection_checks\":" << counts.rejection_checks
              << ",\"random_seeds\":[1,7,20260905,11400714819323198485],"
              << "\"random_arity\":[1,2,3,4],\"extra_arity\":[6,8],"
              << "\"k\":[1,2,3,\"n+1\"],\"profile_B\":[1,2,\"default\"],"
              << "\"adaptive_budget\":[0,1,\"default\"],\"degree_audit\":true}\n";
  } catch (const std::exception &e) {
    std::cout << "{\"status\":\"failed\",\"error\":" << quote(e.what()) << "}\n";
    return 1;
  }
}
