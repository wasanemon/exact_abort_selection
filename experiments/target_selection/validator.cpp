// Independently written reproduction of Ding et al. Algorithm 2, prod policy.
// The paper does not specify ties: this experiment fixes descending unique ID.
// CLI inputs are complete point RMW; generic directed R/W is used only in tests.
#include "eas/Selector.h"
#include <algorithm>
#include <chrono>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <numeric>
#include <random>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>
#include <sys/resource.h>

namespace {
using Clock = std::chrono::steady_clock;
double elapsed(Clock::time_point start) {
  return std::chrono::duration<double, std::milli>(Clock::now() - start).count();
}
struct Hash {
  size_t operator()(const eas::Key &key) const {
    uint64_t h = key.table + 0x9e3779b97f4a7c15ULL;
    for (auto x : {key.partition, key.value}) {
      x += 0x9e3779b97f4a7c15ULL;
      x = (x ^ (x >> 30)) * 0xbf58476d1ce4e5b9ULL;
      x = (x ^ (x >> 27)) * 0x94d049bb133111ebULL;
      h ^= (x ^ (x >> 31)) + (h << 6) + (h >> 2);
    }
    return static_cast<size_t>(h);
  }
};
struct Measurement {
  eas::Result decision;
  uint64_t directed_edges = 0, graph_bytes = 0;
  uint64_t write_posting_count = 0, graph_probe_hits = 0;
  double total_ms = 0;
};
struct Budget {
  uint64_t used = 0, limit;
  explicit Budget(uint64_t b) : limit(b) {}
  void add(uint64_t bytes) {
    if (bytes > limit || used > limit - bytes)
      throw eas::Unsupported("paper explicit graph memory budget exceeded");
    used += bytes;
  }
};

Measurement paper_impl(const std::vector<eas::Input> &input, size_t k, uint64_t graph_limit) {
  if (!k) throw eas::Unsupported("paper k=0");
  if (input.size() > 1048576) throw eas::Unsupported("paper transaction capacity exceeded");
  Measurement m;
  const size_t n = input.size();
  auto start = Clock::now();
  // Independent normalization: no eas::normalize or selector/oracle call.
  std::vector<std::vector<eas::Key>> reads(n), writes(n);
  std::unordered_set<uint64_t> ids;
  for (size_t i = 0; i < n; ++i) {
    const auto &t = input[i];
    if (t.remote || t.range || !ids.insert(t.id).second)
      throw eas::Unsupported("paper invalid local point input or duplicate ID");
    reads[i] = t.reads; writes[i] = t.writes;
    for (auto *keys : {&reads[i], &writes[i]}) {
      std::sort(keys->begin(), keys->end());
      keys->erase(std::unique(keys->begin(), keys->end()), keys->end());
      if (keys->size() > 8) throw eas::Unsupported("paper arity exceeds limit 8");
    }
  }
  m.decision.stats.normalize_ms = elapsed(start);
  start = Clock::now();
  Budget budget(graph_limit);
  // Budget guards explicit adjacency backing allocations before growth. It is
  // not process RSS: normalization and hash allocator overhead are separate.
  budget.add(n * (2 * sizeof(std::vector<uint32_t>) + 3 * sizeof(uint32_t) + sizeof(uint8_t)));
  std::vector<std::vector<uint32_t>> outgoing(n), incoming(n);
  std::vector<uint32_t> indegree(n), outdegree(n), epoch(n, UINT32_MAX);
  std::vector<uint8_t> alive(n, 1);
  std::unordered_map<eas::Key, std::vector<uint32_t>, Hash> writers;
  for (size_t j = 0; j < n; ++j) for (const auto &key : writes[j]) {
    writers[key].push_back(static_cast<uint32_t>(j));
    ++m.write_posting_count;
  }
  auto append = [&](std::vector<uint32_t> &v, uint32_t value) {
    if (v.size() == v.capacity()) {
      const size_t next = v.capacity() ? 2 * v.capacity() : 1;
      // Account temporary old+new storage during vector reallocation too.
      if (next * sizeof(uint32_t) > budget.limit ||
          budget.used > budget.limit - next * sizeof(uint32_t))
        throw eas::Unsupported("paper explicit graph reallocation budget exceeded");
      budget.add((next - v.capacity()) * sizeof(uint32_t));
      v.reserve(next);
    }
    v.push_back(value);
  };
  for (size_t i = 0; i < n; ++i) for (const auto &key : reads[i]) {
    auto found = writers.find(key);
    if (found == writers.end()) continue;
    for (uint32_t j : found->second) {
      ++m.graph_probe_hits;
      if (j == i || epoch[j] == i) continue;
      epoch[j] = static_cast<uint32_t>(i);
      // Ding: reader i -> writer j. Multiple shared keys yield one edge.
      append(outgoing[i], j); append(incoming[j], static_cast<uint32_t>(i));
      ++outdegree[i]; ++indegree[j]; ++m.directed_edges;
    }
  }
  m.graph_bytes = budget.used;
  m.decision.stats.graph_bytes = budget.used;
  m.decision.stats.build_ms = elapsed(start);
  start = Clock::now();
  m.decision.commit.assign(n, 0);
  size_t remaining = n;
  std::vector<uint32_t> pending, candidates;
  pending.reserve(n); candidates.reserve(n);
  auto erase = [&](uint32_t v) {
    alive[v] = 0; --remaining;
    for (auto u : outgoing[v]) if (alive[u]) {
      if (!indegree[u]) throw std::logic_error("paper indegree underflow");
      if (--indegree[u] == 0) pending.push_back(u);
    }
    for (auto u : incoming[v]) if (alive[u]) {
      if (!outdegree[u]) throw std::logic_error("paper outdegree underflow");
      if (--outdegree[u] == 0) pending.push_back(u);
    }
  };
  auto trim = [&]() {
    for (size_t p = 0; p < pending.size(); ++p) {
      uint32_t v = pending[p];
      if (!alive[v] || (indegree[v] && outdegree[v])) continue;
      m.decision.commit[v] = 1; erase(v);
    }
    pending.clear();
  };
  for (uint32_t i = 0; i < n; ++i) if (!indegree[i] || !outdegree[i]) pending.push_back(i);
  trim();
  m.decision.stats.initial_core_size = remaining;
  auto ranked_before = [&](uint32_t a, uint32_t b) {
    uint64_t da = uint64_t(indegree[a]) * outdegree[a];
    uint64_t db = uint64_t(indegree[b]) * outdegree[b];
    return da != db ? da > db : input[a].id > input[b].id;
  };
  while (remaining) {
    if (remaining < k) k = 1; // Algorithm 2's strict fallback, not min(k,n).
    candidates.clear();
    for (uint32_t i = 0; i < n; ++i) if (alive[i]) candidates.push_back(i);
    if (k < candidates.size())
      std::nth_element(candidates.begin(), candidates.begin() + k, candidates.end(), ranked_before);
    candidates.resize(k);
    std::sort(candidates.begin(), candidates.end(), ranked_before);
    m.decision.abort_rounds.emplace_back();
    // All ranks and selected IDs are frozen before any graph mutation.
    for (auto v : candidates) m.decision.abort_rounds.back().push_back(input[v].id);
    for (auto v : candidates) erase(v);
    trim();
  }
  m.decision.stats.select_ms = elapsed(start);
  start = Clock::now();
  for (size_t i = 0; i < n; ++i) if (m.decision.commit[i]) m.decision.certificate.push_back(input[i].id);
  std::sort(m.decision.certificate.begin(), m.decision.certificate.end());
  m.decision.stats.certificate_ms = elapsed(start);
  return m; // caller stops timer after all local scratch is destroyed.
}
Measurement paper_run(const std::vector<eas::Input> &input, size_t k, uint64_t graph_limit) {
  const auto start = Clock::now();
  auto m = paper_impl(input, k, graph_limit);
  m.total_ms = elapsed(start);
  m.decision.stats.total_ms = m.total_ms;
  return m;
}

// Small-input directed oracle: all-pair logical set intersections, every-round
// full in/out-degree recomputation, repeated simultaneous trim. No writer index.
eas::Result directed_oracle(const std::vector<eas::Input> &input, size_t k) {
  if (!k || input.size() > 256) throw std::logic_error("directed oracle input limit");
  size_t n = input.size();
  std::vector<std::set<eas::Key>> reads, writes;
  for (const auto &t : input) {
    reads.emplace_back(t.reads.begin(), t.reads.end());
    writes.emplace_back(t.writes.begin(), t.writes.end());
  }
  std::vector<uint8_t> live(n, 1);
  eas::Result r; r.commit.assign(n, 0);
  for (;;) {
    std::vector<size_t> in(n), out(n), candidates;
    for (size_t i = 0; i < n; ++i) if (live[i])
      for (size_t j = 0; j < n; ++j) if (i != j && live[j]) {
        bool hit = false;
        for (const auto &key : reads[i]) if (writes[j].count(key)) { hit = true; break; }
        if (hit) { ++out[i]; ++in[j]; }
      }
    bool trimmed = false;
    for (size_t i = 0; i < n; ++i) if (live[i]) {
      if (!in[i] || !out[i]) { live[i] = 0; r.commit[i] = 1; trimmed = true; }
      else candidates.push_back(i);
    }
    if (trimmed) continue;
    if (candidates.empty()) break;
    if (candidates.size() < k) k = 1;
    std::sort(candidates.begin(), candidates.end(), [&](size_t i, size_t j) {
      auto a = in[i] * out[i], b = in[j] * out[j];
      return a != b ? a > b : input[i].id > input[j].id;
    });
    r.abort_rounds.emplace_back();
    for (size_t t = 0; t < k; ++t) {
      auto i = candidates[t]; live[i] = 0; r.abort_rounds.back().push_back(input[i].id);
    }
  }
  for (size_t i = 0; i < n; ++i) if (r.commit[i]) r.certificate.push_back(input[i].id);
  std::sort(r.certificate.begin(), r.certificate.end());
  return r;
}

void require(bool condition, const std::string &why) {
  if (!condition) throw std::logic_error(why);
}
bool same(const eas::Result &a, const eas::Result &b) {
  return a.abort_rounds == b.abort_rounds && a.commit == b.commit && a.certificate == b.certificate;
}
void verify_rmw(const std::vector<eas::Input> &input, const eas::Result &r) {
  require(r.commit.size() == input.size(), "commit mask length");
  std::set<eas::Key> occupied;
  std::set<uint64_t> known, rejected;
  std::vector<uint64_t> cert;
  for (const auto &t : input) require(known.insert(t.id).second, "duplicate input ID");
  for (const auto &round : r.abort_rounds) for (auto id : round)
    require(known.count(id) && rejected.insert(id).second, "invalid abort ID");
  for (auto id : r.rejected_ids)
    require(known.count(id) && rejected.insert(id).second, "invalid acceptance rejection");
  for (size_t i = 0; i < input.size(); ++i) {
    require(r.commit[i] <= 1, "nonbinary commit");
    require(bool(r.commit[i]) != bool(rejected.count(input[i].id)), "commit/rejection partition");
    if (!r.commit[i]) continue;
    cert.push_back(input[i].id);
    std::set<eas::Key> keys(input[i].reads.begin(), input[i].reads.end());
    for (const auto &key : keys) require(occupied.insert(key).second, "committed RMW conflict");
  }
  std::sort(cert.begin(), cert.end());
  require(cert == r.certificate, "certificate differs from mask");
}
eas::Input transaction(uint64_t id, std::initializer_list<uint64_t> reads,
                       std::initializer_list<uint64_t> writes) {
  eas::Input t; t.id = id;
  for (auto key : reads) t.reads.push_back(eas::Key{0, 0, key});
  for (auto key : writes) t.writes.push_back(eas::Key{0, 0, key});
  return t;
}
void self_test() {
  const uint64_t limit = 512ULL << 20;
  uint64_t comparisons = 0, exhaustive = 0, random_rmw = 0, random_directed = 0;
  auto check_rmw = [&](const std::vector<eas::Input> &input) {
    for (size_t k : {1, 2, 3}) {
      const auto expected = eas::oracle(input, k);
      const auto d = directed_oracle(input, k);
      require(same(expected, d), "RMW/directed oracle mismatch"); ++comparisons;
      auto paper = paper_run(input, k, limit);
      require(same(expected, paper.decision), "paper/RMW oracle mismatch"); ++comparisons;
      verify_rmw(input, paper.decision);
      for (const auto &mode : {"graph", "lazy", "profile", "adaptive"}) {
        eas::Options o; o.mode = mode; o.k = k;
        const auto result = eas::run(input, o);
        require(same(expected, result), "EAS/paper preservation mismatch"); ++comparisons;
      }
    }
  };
  for (size_t n = 0; n <= 4; ++n) {
    size_t count = size_t(1) << (3 * n);
    for (size_t code = 0; code < count; ++code) {
      std::vector<eas::Input> input(n);
      size_t rest = code;
      for (size_t i = 0; i < n; ++i) {
        input[i].id = i + 1;
        for (size_t key = 0; key < 3; ++key) if (rest & (size_t(1) << key))
          input[i].reads.push_back(eas::Key{0, 0, key});
        input[i].writes = input[i].reads; rest >>= 3;
      }
      check_rmw(input); ++exhaustive;
    }
  }
  std::mt19937_64 rng(202609054);
  for (size_t trial = 0; trial < 1000; ++trial) {
    size_t n = rng() % 19, universe = 1 + rng() % 10;
    std::vector<eas::Input> input(n);
    std::vector<uint64_t> ids(n);
    for (size_t i = 0; i < n; ++i) ids[i] = (uint64_t(1) << 50) + 17 * i;
    std::shuffle(ids.begin(), ids.end(), rng);
    for (size_t i = 0; i < n; ++i) {
      input[i].id = ids[i]; size_t arity = rng() % 5;
      for (size_t j = 0; j < arity; ++j) {
        eas::Key key{rng() % 2, rng() % 2, rng() % universe};
        input[i].reads.push_back(key);
        if (rng() % 3 == 0) input[i].reads.push_back(key);
      }
      input[i].writes = input[i].reads;
      std::shuffle(input[i].writes.begin(), input[i].writes.end(), rng);
    }
    check_rmw(input); ++random_rmw;
    // Same IDs, independent R/W to exercise non-symmetric graph construction.
    for (auto &t : input) {
      t.writes.clear(); size_t arity = rng() % 5;
      for (size_t j = 0; j < arity; ++j) {
        eas::Key key{rng() % 2, rng() % 2, rng() % universe};
        t.writes.push_back(key); if (rng() % 3 == 0) t.writes.push_back(key);
      }
    }
    for (size_t k : {1, 2, 3}) {
      require(same(directed_oracle(input, k), paper_run(input, k, limit).decision),
              "generic directed oracle mismatch"); ++comparisons;
    }
    ++random_directed;
  }
  size_t targeted = 0;
  auto pair = std::vector<eas::Input>{transaction(1,{9},{9}), transaction(2,{9},{9})};
  require(paper_run(pair, 2, limit).decision.certificate.empty(), "frozen k=2 zero commit"); ++targeted;
  auto p = paper_run(pair, 3, limit);
  require(p.decision.abort_rounds == std::vector<std::vector<uint64_t>>{{2}} &&
          p.decision.certificate == std::vector<uint64_t>{1}, "strict size<k fallback"); ++targeted;
  auto star = std::vector<eas::Input>{transaction(1,{0,1},{0,1}), transaction(2,{0},{0}),transaction(3,{1},{1})};
  require(paper_run(star, 2, limit).decision.abort_rounds ==
          std::vector<std::vector<uint64_t>>{{1,3}}, "frozen ranks before deletion"); ++targeted;
  auto duplicate = std::vector<eas::Input>{transaction(1,{0,0,1},{1,0,1}),transaction(2,{1,0},{0,1})};
  require(paper_run(duplicate, 1, limit).directed_edges == 2, "dedup shared-key edges and self edges"); ++targeted;
  auto chain = std::vector<eas::Input>{transaction(3,{0},{}),transaction(1,{1},{0}),transaction(2,{},{1})};
  auto c = paper_run(chain, 1, limit);
  require(c.directed_edges == 2 && c.decision.abort_rounds.empty() && c.decision.certificate.size() == 3,
          "directed chain must recursively trim, not form symmetric cycle"); ++targeted;
  auto cycle = std::vector<eas::Input>{transaction(1,{0},{2}),transaction(2,{1},{0}),transaction(3,{2},{1})};
  require(paper_run(cycle, 1, limit).decision.abort_rounds ==
          std::vector<std::vector<uint64_t>>{{3}}, "directed cycle prod and ID tie"); ++targeted;
  bool rejected = false;
  try { paper_run(pair, 1, 1); } catch (const eas::Unsupported &) { rejected = true; }
  require(rejected, "paper memory budget not enforced"); ++targeted;
  rejected = false;
  try { eas::Options o; eas::run(chain,o); } catch (const eas::Unsupported &) { rejected = true; }
  require(rejected, "EAS must reject generic R!=W"); ++targeted;
  auto dup_id = pair; dup_id[1].id = dup_id[0].id; rejected = false;
  try { paper_run(dup_id,1,limit); } catch (const eas::Unsupported &) { rejected = true; }
  require(rejected, "paper duplicate ID rejection"); ++targeted;
  std::cout << "{\"status\":\"ok\",\"verification\":\"passed\",\"exhaustive_inputs\":" << exhaustive
            << ",\"random_rmw_inputs\":" << random_rmw << ",\"random_directed_inputs\":" << random_directed
            << ",\"decision_comparisons\":" << comparisons << ",\"targeted_tests\":" << targeted << "}\n";
}

uint64_t number(const std::string &s) {
  if (s.empty() || s.find_first_not_of("0123456789") != std::string::npos)
    throw std::runtime_error("invalid unsigned integer");
  size_t end = 0; auto value = std::stoull(s, &end);
  if (end != s.size()) throw std::runtime_error("trailing integer data");
  return value;
}
std::vector<eas::Input> read_trace(const std::string &path) {
  std::ifstream stream(path);
  if (!stream) throw std::runtime_error("cannot open trace");
  std::vector<eas::Input> input;
  std::string line; bool header_seen = false;
  while (std::getline(stream, line)) {
    if (!line.empty() && line.back() == '\r') line.pop_back();
    if (line.empty() || line[0] == '#') continue;
    if (line.compare(0, 12, "EAS_TRACE_V1") == 0) {
      if (header_seen || !input.empty()) throw std::runtime_error("misplaced trace header");
      std::istringstream fields(line); std::string magic, keys, seed, batch, extra;
      if (!(fields >> magic >> keys >> seed >> batch) || fields >> extra || magic != "EAS_TRACE_V1")
        throw std::runtime_error("invalid trace header");
      number(keys); number(seed); number(batch); header_seen = true; continue;
    }
    size_t tab = line.find('\t');
    if (tab == std::string::npos) throw std::runtime_error("trace record requires tab");
    eas::Input t; t.id = number(line.substr(0,tab));
    std::string keys = line.substr(tab + 1);
    if (!keys.empty()) {
      size_t begin = 0;
      for (;;) {
        size_t comma = keys.find(',', begin);
        t.reads.push_back(eas::Key{0,0,number(keys.substr(begin, comma - begin))});
        if (comma == std::string::npos) break;
        begin = comma + 1;
      }
    }
    t.writes = t.reads; input.push_back(std::move(t));
    if (input.size() > 1048576) throw eas::Unsupported("trace transaction capacity exceeded");
  }
  return input;
}
std::string quote(const std::string &s) {
  std::ostringstream out; out << '"';
  for (unsigned char c : s) {
    if (c == '"' || c == '\\') out << '\\' << c;
    else if (c == '\n') out << "\\n";
    else if (c < 32) out << "\\u" << std::hex << std::setw(4) << std::setfill('0') << unsigned(c) << std::dec;
    else out << c;
  }
  out << '"'; return out.str();
}
template<class T> void array(std::ostream &out, const std::vector<T> &values) {
  out << '[';
  for (size_t i = 0; i < values.size(); ++i) { if(i) out << ','; out << +values[i]; }
  out << ']';
}
long rss() { struct rusage u{}; if (getrusage(RUSAGE_SELF,&u)) return -1; return u.ru_maxrss; }
void output(const Measurement &m, size_t n, const std::string &mode, size_t k, long peak) {
  const auto &r = m.decision; const auto &s = r.stats;
  std::cout << std::setprecision(12) << "{\"status\":\"ok\",\"verification\":\"passed\",\"n\":" << n
            << ",\"mode\":" << quote(mode) << ",\"k\":" << k << ",\"commit_count\":" << r.certificate.size()
            << ",\"fvs_size\":" << n-r.certificate.size() << ",\"total_ms\":" << m.total_ms
            << ",\"peak_rss_kib\":" << peak << ",\"stats\":{\"normalize_ms\":" << s.normalize_ms
            << ",\"build_ms\":" << s.build_ms << ",\"select_ms\":" << s.select_ms
            << ",\"trim_ms\":" << s.trim_ms << ",\"certificate_ms\":" << s.certificate_ms
            << ",\"count_ms\":" << s.count_ms << ",\"sort_ms\":" << s.sort_ms
            << ",\"switch_ms\":" << s.switch_ms << ",\"switches\":" << s.switches
            << ",\"degree_queries\":" << s.degree_queries << ",\"light_scans\":" << s.light_scans
            << ",\"heavy_updates\":" << s.heavy_updates << ",\"tree_updates\":" << s.tree_updates
            << ",\"initial_core_size\":" << s.initial_core_size << ",\"graph_bytes\":" << s.graph_bytes
            << ",\"index_payload_bytes\":" << s.index_payload_bytes
            << ",\"directed_edges\":";
  if (mode == "paper") std::cout << m.directed_edges; else std::cout << "null";
  std::cout << ",\"write_posting_count\":" << m.write_posting_count << ",\"graph_probe_hits\":" << m.graph_probe_hits
            << "},\"decisions\":{\"abort_rounds\":[";
  for (size_t i = 0; i < r.abort_rounds.size(); ++i) { if (i) std::cout << ','; array(std::cout,r.abort_rounds[i]); }
  std::cout << "],\"commit\":"; array(std::cout,r.commit);
  std::cout << ",\"certificate\":"; array(std::cout,r.certificate);
  std::cout << ",\"consideration_order\":"; array(std::cout,r.consideration_order);
  std::cout << ",\"rejected_ids\":"; array(std::cout,r.rejected_ids);
  std::cout << ",\"initial_degrees\":"; array(std::cout,r.initial_degrees);
  std::cout << "}}\n";
}
} // namespace
int main(int argc, char **argv) {
  std::string mode = "paper", path;
  size_t k = 2; uint64_t limit = 512ULL << 20;
  try {
    for (int i = 1; i < argc; ++i) {
      std::string arg = argv[i];
      if (arg == "--self-test") { self_test(); return 0; }
      if (i+1 >= argc) throw std::runtime_error("missing option value");
      std::string value = argv[++i];
      if (arg == "--trace") path = value;
      else if (arg == "--mode") mode = value;
      else if (arg == "--k") k = number(value);
      else if (arg == "--max-graph-bytes") limit = number(value);
      else throw std::runtime_error("unknown option");
    }
    if (path.empty()) throw std::runtime_error("--trace is required");
    if (!k) throw eas::Unsupported("k=0");
    const std::set<std::string> modes{"paper","graph","lazy","profile","adaptive","accept_id","accept_static_degree"};
    if (!modes.count(mode)) throw std::runtime_error("unknown mode");
    auto input = read_trace(path);
    Measurement m;
    if (mode == "paper") m = paper_run(input,k,limit);
    else {
      eas::Options o; o.mode = mode; o.k = k; o.max_graph_bytes = limit;
      const auto start = Clock::now();
      m.decision = eas::run(input,o); m.total_ms = elapsed(start);
    }
    const long peak = rss(); // capture before verification builds any sets.
    verify_rmw(input,m.decision);
    output(m,input.size(),mode,k,peak);
    return 0;
  } catch (const eas::Unsupported &e) {
    std::cout << "{\"status\":\"unsupported\",\"mode\":" << quote(mode) << ",\"k\":" << k
              << ",\"message\":" << quote(e.what()) << ",\"peak_rss_kib\":" << rss() << "}\n";
    return 0;
  } catch (const std::bad_alloc &) {
    std::cout << "{\"status\":\"memory_limit\",\"mode\":" << quote(mode) << "}\n"; return 0;
  } catch (const std::exception &e) {
    std::cout << "{\"status\":\"error\",\"mode\":" << quote(mode) << ",\"message\":" << quote(e.what()) << "}\n";
    return 1;
  }
}
