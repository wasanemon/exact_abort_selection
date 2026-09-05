#include "eas/Selector.h"

#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <map>
#include <memory>
#include <numeric>
#include <queue>
#include <set>
#include <unordered_map>
#include <unordered_set>

namespace eas {
namespace {
using Clock = std::chrono::steady_clock;
double ms(Clock::time_point start) {
  return std::chrono::duration<double, std::milli>(Clock::now() - start).count();
}
uint64_t mix(uint64_t x) {
  x ^= x >> 30; x *= 0xbf58476d1ce4e5b9ULL;
  x ^= x >> 27; x *= 0x94d049bb133111ebULL;
  return x ^ (x >> 31);
}
struct KeyHash {
  size_t operator()(const Key &k) const {
    return mix(k.value) ^ mix(k.table + 17) ^ mix(k.partition + 31);
  }
};
void check_options(const Options &o) {
  if (!is_acceptance(o.mode) && !o.k) throw Unsupported("k=0");
  if (!o.max_arity || (o.mode != "accept_id" && o.max_arity > 8))
    throw Unsupported("max_arity must be 1..8 for subset-based policies");
  if (!is_acceptance(o.mode) && o.mode != "graph" && o.mode != "lazy" && o.mode != "profile" && o.mode != "adaptive")
    throw Unsupported("unknown selector mode: " + o.mode);
}
void check_batch(const Batch &b, const Options &o) {
  check_options(o);
  if (b.ids.size() != b.keys.size() || b.ids.size() > 1048576 || b.key_count > 8388608)
    throw Unsupported("batch size/key capacity");
  std::set<uint64_t> ids;
  size_t incidences = 0, arity = 0, accesses = 0;
  for (size_t t = 0; t < b.ids.size(); ++t) {
    if (!ids.insert(b.ids[t]).second) throw Unsupported("duplicate transaction ID");
    const auto &keys = b.keys[t];
    if (keys.size() > o.max_arity) throw Unsupported("arity exceeds limit");
    arity = std::max(arity, keys.size());
    const size_t add = o.mode == "accept_id" ? 0 : (size_t(1) << keys.size()) - 1;
    if (add > o.max_incidence || incidences > o.max_incidence - add)
      throw Unsupported("subset incidence budget exceeded before allocation");
    incidences += add;
    accesses += keys.size();
    for (size_t j = 0; j < keys.size(); ++j)
      if (keys[j] >= b.key_count || (j && keys[j-1] >= keys[j]))
        throw Unsupported("non-normalized dense keys");
  }
  if (b.arity != arity || b.incidences != incidences || b.accesses != accesses ||
      b.key_count > accesses)
    throw Unsupported("invalid batch metadata");
  // Allocate from the independently checked access count, then ensure that
  // callers of select() supplied a dense universe without unused key IDs.
  std::vector<uint8_t> used(b.key_count);
  size_t used_count = 0;
  for (const auto &keys : b.keys) for (auto key : keys)
    if (!used[key]) { used[key] = 1; ++used_count; }
  if (used_count != b.key_count) throw Unsupported("non-dense key universe");
}
bool intersects(const std::vector<uint32_t> &a, const std::vector<uint32_t> &b) {
  size_t i = 0, j = 0;
  while (i < a.size() && j < b.size()) {
    if (a[i] == b[j]) return true;
    if (a[i] < b[j]) ++i; else ++j;
  }
  return false;
}

// Counts include frozen candidates until the entire round has been selected.
struct State {
  const Batch &b;
  Stats &stats;
  std::vector<uint8_t> alive, eligible;
  std::vector<size_t> count, xors, support;
  std::queue<size_t> isolated;
  size_t remaining;
  State(const Batch &batch, Stats &s) : b(batch), stats(s),
      alive(b.ids.size(), 1), eligible(b.ids.size(), 1), count(b.key_count),
      xors(b.key_count), support(b.ids.size()), remaining(b.ids.size()) {
    for (size_t t = 0; t < b.ids.size(); ++t)
      for (auto key : b.keys[t]) { ++count[key]; xors[key] ^= t; ++stats.trim_key_visits; }
    for (size_t t = 0; t < b.ids.size(); ++t) {
      for (auto key : b.keys[t]) { support[t] += count[key] > 1; ++stats.trim_key_visits; }
      if (!support[t]) isolated.push(t);
    }
  }
  void erase(size_t t) {
    if (!alive[t]) throw std::logic_error("double deletion");
    alive[t] = eligible[t] = 0;
    --remaining;
    for (auto key : b.keys[t]) {
      --count[key]; xors[key] ^= t; ++stats.trim_key_visits;
      if (count[key] == 1) {
        auto survivor = xors[key];
        if (!--support[survivor]) isolated.push(survivor);
      }
    }
  }
};
struct Scheduler {
  State &s;
  Stats &stats;
  Scheduler(State &state) : s(state), stats(state.stats) {}
  virtual ~Scheduler() = default;
  virtual size_t pop() = 0; // excludes candidate, does NOT delete it
  virtual void erase(size_t t) = 0;
  virtual int64_t degree(size_t t) const = 0;
  virtual void end_round() {}
};
void trim(State &s, Result &r, Scheduler *scheduler) {
  const auto start = Clock::now();
  while (!s.isolated.empty()) {
    auto t = s.isolated.front(); s.isolated.pop();
    if (!s.alive[t]) continue;
    if (s.support[t] || !s.eligible[t]) throw std::logic_error("invalid trim state");
    r.commit[t] = 1;
    if (scheduler) scheduler->erase(t);
    s.erase(t);
  }
  r.stats.trim_ms += ms(start);
}
using Rank = std::tuple<int64_t, uint64_t, size_t>;

struct Graph : Scheduler {
  size_t words;
  std::vector<size_t> core, position;
  std::vector<uint64_t> bits, live_bits;
  std::vector<int64_t> degrees;
  std::set<Rank> ranks;
  Graph(State &s, const Options &o) : Scheduler(s), words((s.remaining + 63) / 64),
      position(s.b.ids.size()), degrees(s.b.ids.size()) {
    for (size_t t = 0; t < s.alive.size(); ++t) if (s.alive[t]) {
      position[t] = core.size(); core.push_back(t);
    }
    if (words && core.size() > o.max_graph_bytes / sizeof(uint64_t) / words)
      throw Unsupported("graph byte budget exceeded before allocation");
    bits.resize(core.size() * words);
    stats.graph_bytes = bits.size() * sizeof(uint64_t);
    live_bits.resize(words, ~uint64_t(0));
    std::vector<std::vector<size_t>> posting(s.b.key_count);
    for (size_t p = 0; p < core.size(); ++p)
      for (auto key : s.b.keys[core[p]]) posting[key].push_back(p);
    std::vector<uint64_t> key_bits(words);
    for (const auto &list : posting) {
      if (list.size() < 2) continue;
      std::fill(key_bits.begin(), key_bits.end(), 0);
      for (auto p : list) key_bits[p / 64] |= uint64_t(1) << (p % 64);
      for (auto p : list)
        for (size_t w = 0; w < words; ++w) bits[p * words + w] |= key_bits[w];
    }
    for (size_t p = 0; p < core.size(); ++p) {
      bits[p * words + p / 64] &= ~(uint64_t(1) << (p % 64));
      auto t = core[p];
      for (size_t w = 0; w < words; ++w) degrees[t] += __builtin_popcountll(bits[p * words + w]);
      ranks.emplace(degrees[t], s.b.ids[t], t); ++stats.tree_updates;
    }
  }
  size_t pop() override {
    if (ranks.empty()) throw std::logic_error("empty graph ranks");
    auto it = std::prev(ranks.end());
    size_t t = std::get<2>(*it); ranks.erase(it); ++stats.tree_updates;
    return t;
  }
  void erase(size_t t) override {
    if (s.eligible[t]) { ranks.erase(Rank(degrees[t], s.b.ids[t], t)); ++stats.tree_updates; }
    auto p = position[t];
    live_bits[p / 64] &= ~(uint64_t(1) << (p % 64));
    for (size_t w = 0; w < words; ++w) {
      auto neighbors = bits[p * words + w] & live_bits[w];
      while (neighbors) {
        size_t u = core[w * 64 + __builtin_ctzll(neighbors)];
        neighbors &= neighbors - 1;
        if (s.eligible[u]) { ranks.erase(Rank(degrees[u], s.b.ids[u], u)); ++stats.tree_updates; }
        --degrees[u];
        if (s.eligible[u]) { ranks.emplace(degrees[u], s.b.ids[u], u); ++stats.tree_updates; }
      }
    }
  }
  int64_t degree(size_t t) const override { return degrees[t]; }
};

struct Subset {
  std::array<uint32_t, 8> keys{};
  uint8_t size = 0;
  bool operator==(const Subset &o) const { return size == o.size && keys == o.keys; }
  bool operator<(const Subset &o) const {
    return size != o.size ? size < o.size : keys < o.keys;
  }
};
template <class F> void subsets(const std::vector<uint32_t> &keys, F f) {
  for (size_t mask = 1; mask < (size_t(1) << keys.size()); ++mask) {
    Subset q;
    for (size_t j = 0; j < keys.size(); ++j) if (mask & (size_t(1) << j)) q.keys[q.size++] = keys[j];
    f(q);
  }
}
struct Node {
  Subset key;
  int64_t count = 0;
  int sign = 1;
  bool heavy = false;
  std::vector<size_t> posting, profiles;
};
struct Index {
  State &s;
  std::map<Subset, size_t> ids;
  std::vector<Node> nodes;
  std::vector<std::vector<size_t>> incidence;
  Index(State &s) : s(s), incidence(s.b.ids.size()) {
    size_t total = 0;
    for (size_t t = 0; t < s.alive.size(); ++t) if (s.alive[t]) {
      incidence[t].reserve((size_t(1) << s.b.keys[t].size()) - 1);
      subsets(s.b.keys[t], [&](const Subset &q) {
        auto found = ids.emplace(q, nodes.size());
        if (found.second) {
          Node node; node.key = q; node.sign = (q.size % 2) ? 1 : -1;
          nodes.push_back(std::move(node));
        }
        size_t i = found.first->second;
        ++nodes[i].count; nodes[i].posting.push_back(t); incidence[t].push_back(i); ++total;
      });
    }
    s.stats.subsets = std::max(s.stats.subsets, nodes.size());
    s.stats.incidences = std::max(s.stats.incidences, total);
    // Payload estimate only: excludes allocator/map nodes and State/Batch.
    uint64_t bytes = nodes.capacity() * sizeof(Node) + incidence.capacity() * sizeof(std::vector<size_t>);
    for (const auto &q : nodes) bytes += q.posting.capacity() * sizeof(size_t);
    for (const auto &list : incidence) bytes += list.capacity() * sizeof(size_t);
    s.stats.index_payload_bytes = std::max(s.stats.index_payload_bytes, bytes);
  }
  int64_t degree(size_t t) const {
    int64_t d = -1;
    for (auto q : incidence[t]) d += nodes[q].sign * nodes[q].count;
    return d;
  }
};
struct Entry {
  int64_t degree;
  uint64_t id, generation;
  size_t t;
  bool operator<(const Entry &o) const { return std::tie(degree, id) < std::tie(o.degree, o.id); }
};
struct Lazy : Scheduler {
  Index index;
  std::priority_queue<Entry> heap;
  uint64_t generation = 0;
  Lazy(State &s) : Scheduler(s), index(s) {
    std::vector<Entry> entries;
    entries.reserve(s.remaining);
    for (size_t t = 0; t < s.alive.size(); ++t) if (s.alive[t]) {
      entries.push_back({index.degree(t), s.b.ids[t], generation, t}); ++stats.degree_queries;
    }
    heap = decltype(heap)(std::less<Entry>(), std::move(entries));
  }
  size_t pop() override {
    for (;;) {
      if (heap.empty()) throw std::logic_error("empty lazy heap");
      auto top = heap.top(); heap.pop();
      if (!s.eligible[top.t]) continue;
      if (top.generation != generation) {
        top.degree = index.degree(top.t); top.generation = generation; ++stats.degree_queries;
        // Full (degree, ID) comparison, not just degree.
        if (!heap.empty() && top < heap.top()) { heap.push(top); continue; }
      }
      return top.t;
    }
  }
  void erase(size_t t) override {
    for (auto q : index.incidence[t]) --index.nodes[q].count;
  }
  void end_round() override { ++generation; }
  int64_t degree(size_t t) const override { return index.degree(t); }
};

struct Profile : Scheduler {
  struct Group { int64_t common = 0; std::set<Rank> local; };
  Index index;
  std::vector<Group> groups;
  std::vector<size_t> group_of;
  std::vector<int64_t> local;
  std::set<Rank> representatives; // degree, representative ID, profile index
  Profile(State &s, const Options &o) : Scheduler(s), index(s),
      group_of(s.b.ids.size()), local(s.b.ids.size()) {
    const size_t ell = std::max<size_t>(1, s.b.arity);
    const size_t B = o.profile_B ? o.profile_B : std::max<size_t>(1, static_cast<size_t>(
        std::ceil(std::pow(double(s.remaining), double(ell - 1) / ell))));
    stats.B = B;
    size_t heavy_count = 0;
    for (auto &q : index.nodes) { q.heavy = size_t(q.count) >= B; heavy_count += q.heavy; }
    stats.heavy_subsets = std::max(stats.heavy_subsets, heavy_count);
    std::map<Subset, size_t> group_ids;
    std::vector<Subset> profiles;
    for (size_t t = 0; t < s.alive.size(); ++t) if (s.alive[t]) {
      Subset p;
      for (auto key : s.b.keys[t]) if (s.count[key] >= B) p.keys[p.size++] = key;
      auto found = group_ids.emplace(p, groups.size());
      if (found.second) { groups.emplace_back(); profiles.push_back(p); }
      const size_t g = group_of[t] = found.first->second;
      for (auto q : index.incidence[t]) if (!index.nodes[q].heavy)
        local[t] += index.nodes[q].sign * index.nodes[q].count;
      groups[g].local.emplace(local[t], s.b.ids[t], t); ++stats.tree_updates;
    }
    size_t links = 0;
    // Enumerate subsets of each PRESENT profile once, never all key combinations.
    for (size_t p = 0; p < groups.size(); ++p) {
      const auto &sig = profiles[p];
      std::vector<uint32_t> keys(sig.keys.begin(), sig.keys.begin() + sig.size);
      subsets(keys, [&](const Subset &q) {
        auto it = index.ids.find(q);
        if (it != index.ids.end() && index.nodes[it->second].heavy) {
          auto &node = index.nodes[it->second];
          node.profiles.push_back(p); ++links;
          groups[p].common += node.sign * node.count;
        }
      });
      add_rep(p);
    }
    stats.profiles = std::max(stats.profiles, groups.size());
    stats.profile_links = std::max(stats.profile_links, links);
    stats.index_payload_bytes += links * sizeof(size_t); // bounded connection payload
  }
  Rank rep(size_t p) const {
    const auto &g = groups[p]; const auto &top = *g.local.rbegin();
    return Rank(std::get<0>(top) + g.common - 1, std::get<1>(top), p);
  }
  void drop_rep(size_t p) {
    if (!groups[p].local.empty()) { representatives.erase(rep(p)); ++stats.tree_updates; }
  }
  void add_rep(size_t p) {
    if (!groups[p].local.empty()) { representatives.insert(rep(p)); ++stats.tree_updates; }
  }
  void exclude(size_t t) {
    auto p = group_of[t]; drop_rep(p);
    groups[p].local.erase(Rank(local[t], s.b.ids[t], t)); ++stats.tree_updates;
    add_rep(p);
  }
  size_t pop() override {
    if (representatives.empty()) throw std::logic_error("empty profile representatives");
    auto p = std::get<2>(*representatives.rbegin());
    auto t = std::get<2>(*groups[p].local.rbegin());
    exclude(t);
    return t;
  }
  void erase(size_t t) override {
    if (s.eligible[t]) exclude(t);
    for (auto qi : index.incidence[t]) {
      auto &q = index.nodes[qi]; --q.count;
      if (q.heavy) {
        for (auto p : q.profiles) {
          drop_rep(p); groups[p].common -= q.sign; add_rep(p); ++stats.heavy_updates;
        }
      } else {
        for (auto u : q.posting) {
          ++stats.light_scans;
          if (!s.eligible[u] || u == t) continue;
          auto p = group_of[u]; drop_rep(p);
          groups[p].local.erase(Rank(local[u], s.b.ids[u], u)); ++stats.tree_updates;
          local[u] -= q.sign;
          groups[p].local.emplace(local[u], s.b.ids[u], u); ++stats.tree_updates;
          add_rep(p);
        }
      }
    }
  }
  int64_t degree(size_t t) const override {
    const auto d = index.degree(t);
    // Called only by the opt-in audit. Check the profile representation as
    // well as the subset-count identity against independent intersections.
    if (s.eligible[t] && local[t] + groups[group_of[t]].common - 1 != d)
      throw std::logic_error("profile local/common audit mismatch");
    return d;
  }
};
void audit(const State &s, const Scheduler &scheduler) {
  for (size_t t = 0; t < s.alive.size(); ++t) if (s.alive[t]) {
    int64_t d = 0;
    for (size_t u = 0; u < s.alive.size(); ++u)
      if (t != u && s.alive[u] && intersects(s.b.keys[t], s.b.keys[u])) ++d;
    if (d != scheduler.degree(t)) throw std::logic_error("degree audit mismatch");
  }
}
} // namespace

bool is_acceptance(const std::string &mode) {
  return mode == "accept_id" || mode == "accept_static_degree";
}
Batch normalize(const std::vector<Input> &input, const Options &o) {
  check_options(o);
  if (input.size() > 1048576) throw Unsupported("transaction capacity exceeded");
  Batch b;
  std::unordered_map<Key, uint32_t, KeyHash> keys;
  std::unordered_set<uint64_t> ids;
  for (const auto &t : input) {
    if (t.remote || t.range) throw Unsupported("only local point operations supported");
    if (!ids.insert(t.id).second) throw Unsupported("duplicate transaction ID");
    auto r = t.reads, w = t.writes;
    std::sort(r.begin(), r.end()); r.erase(std::unique(r.begin(), r.end()), r.end());
    std::sort(w.begin(), w.end()); w.erase(std::unique(w.begin(), w.end()), w.end());
    if (r != w) throw Unsupported("requires R=W=S (complete RMW)");
    if (r.size() > o.max_arity) throw Unsupported("arity exceeds limit");
    const size_t add = o.mode == "accept_id" ? 0 : (size_t(1) << r.size()) - 1;
    if (add > o.max_incidence || b.incidences > o.max_incidence - add)
      throw Unsupported("subset incidence budget exceeded before allocation");
    b.incidences += add; b.accesses += r.size(); b.arity = std::max(b.arity, r.size());
    b.ids.push_back(t.id); b.keys.emplace_back();
    for (const auto &key : r) {
      if (keys.size() >= 8388608) throw Unsupported("dense key capacity exceeded");
      auto found = keys.emplace(key, static_cast<uint32_t>(keys.size()));
      b.keys.back().push_back(found.first->second);
    }
    std::sort(b.keys.back().begin(), b.keys.back().end());
  }
  b.key_count = keys.size();
  return b;
}
namespace {
Result accept(const Batch &b, const Options &o) {
  Result r;
  r.commit.resize(b.ids.size());
  std::vector<size_t> order(b.ids.size());
  std::iota(order.begin(), order.end(), 0);
  if (o.mode == "accept_static_degree") {
    const auto start = Clock::now();
    r.initial_degrees.resize(b.ids.size());
    if (b.arity <= 2) {
      // Exact singleton/pair counts: duplicate signatures are distinct people.
      std::vector<int64_t> single(b.key_count);
      std::unordered_map<uint64_t, int64_t> pairs;
      auto pair_key = [](const std::vector<uint32_t> &s) {
        return (uint64_t(s[0]) << 32) | s[1];
      };
      for (const auto &s : b.keys) {
        for (auto key : s) ++single[key];
        if (s.size() == 2) ++pairs[pair_key(s)];
      }
      for (size_t t = 0; t < b.keys.size(); ++t) {
        const auto &s = b.keys[t];
        int64_t d = s.empty() ? 0 : -1;
        for (auto key : s) d += single[key];
        if (s.size() == 2) d -= pairs.at(pair_key(s));
        r.initial_degrees[t] = d;
      }
      r.stats.subsets = b.key_count + pairs.size();
      r.stats.index_payload_bytes = single.capacity() * sizeof(int64_t) +
          pairs.size() * sizeof(std::pair<const uint64_t, int64_t>);
    } else {
      // One immutable inclusion-exclusion count map; no postings or profile.
      std::map<Subset, int64_t> counts;
      for (const auto &s : b.keys) subsets(s, [&](const Subset &q) { ++counts[q]; });
      for (size_t t = 0; t < b.keys.size(); ++t) {
        int64_t d = b.keys[t].empty() ? 0 : -1;
        subsets(b.keys[t], [&](const Subset &q) { d += (q.size % 2 ? 1 : -1) * counts.at(q); });
        r.initial_degrees[t] = d;
      }
      r.stats.subsets = counts.size();
      r.stats.index_payload_bytes = counts.size() * sizeof(std::pair<const Subset, int64_t>);
    } // count storage release is included
    r.stats.incidences = b.incidences;
    r.stats.initial_degree_evaluations = b.ids.size();
    r.stats.count_ms = ms(start);
    if (o.audit_degrees) for (size_t t = 0; t < b.ids.size(); ++t) {
      int64_t d = 0;
      for (size_t u = 0; u < b.ids.size(); ++u)
        d += t != u && intersects(b.keys[t], b.keys[u]);
      if (d != r.initial_degrees[t]) throw std::logic_error("static initial degree audit mismatch");
    }
  }
  auto start = Clock::now();
  auto less = [&](size_t t, size_t u) {
    if (!r.initial_degrees.empty() && r.initial_degrees[t] != r.initial_degrees[u])
      return r.initial_degrees[t] < r.initial_degrees[u];
    return b.ids[t] < b.ids[u];
  };
  // Engine IDs are already ascending; do not charge accept_id an unnecessary sort.
  if (!std::is_sorted(order.begin(), order.end(), less)) std::sort(order.begin(), order.end(), less);
  r.stats.sort_ms = ms(start);
  start = Clock::now();
  std::vector<uint8_t> used(b.key_count);
  for (auto t : order) {
    r.consideration_order.push_back(b.ids[t]);
    bool conflict = false;
    for (auto key : b.keys[t]) {
      ++r.stats.acceptance_key_visits;
      if (used[key]) { conflict = true; break; }
    }
    if (conflict) r.rejected_ids.push_back(b.ids[t]);
    else {
      r.commit[t] = 1;
      for (auto key : b.keys[t]) { used[key] = 1; ++r.stats.acceptance_key_visits; }
    }
  }
  r.stats.select_ms = ms(start);
  start = Clock::now();
  for (size_t t = 0; t < b.ids.size(); ++t) if (r.commit[t]) r.certificate.push_back(b.ids[t]);
  std::sort(r.certificate.begin(), r.certificate.end());
  r.stats.certificate_ms = ms(start);
  return r; // all scratch destruction included by select()'s outer interval
}
Result select_impl(const Batch &b, const Options &o) {
  check_batch(b, o);
  if (is_acceptance(o.mode)) return accept(b, o);
  Result r; r.commit.resize(b.ids.size());
  const auto trim_start = Clock::now();
  State state(b, r.stats);
  r.stats.trim_ms += ms(trim_start);
  trim(state, r, nullptr);
  const size_t n0 = state.remaining;
  r.stats.initial_core_size = n0;
  std::unique_ptr<Scheduler> scheduler;
  bool profile = o.mode == "profile" || (o.mode == "adaptive" && b.arity <= 1);
  uint64_t budget = o.adaptive_budget;
  if (budget == std::numeric_limits<uint64_t>::max())
    budget = uint64_t(n0) * static_cast<uint64_t>(std::ceil(std::sqrt(double(n0))));
  if (n0) {
    auto build_start = Clock::now();
    if (o.mode == "graph") scheduler.reset(new Graph(state, o));
    else if (profile) scheduler.reset(new Profile(state, o));
    else scheduler.reset(new Lazy(state));
    r.stats.build_ms += ms(build_start);
  }
  size_t k = o.k;
  while (state.remaining) {
    if (o.audit_degrees) audit(state, *scheduler);
    auto selection_start = Clock::now();
    if (state.remaining < k) k = 1;
    std::vector<size_t> selected;
    selected.reserve(k);
    r.abort_rounds.emplace_back();
    for (size_t j = 0; j < k; ++j) {
      const size_t t = scheduler->pop();
      if (!state.eligible[t]) throw std::logic_error("candidate selected twice");
      state.eligible[t] = 0;
      selected.push_back(t); r.abort_rounds.back().push_back(b.ids[t]);
    }
    // All frozen candidates are excluded before any counts change.
    for (auto t : selected) { scheduler->erase(t); state.erase(t); }
    scheduler->end_round();
    r.stats.select_ms += ms(selection_start);
    trim(state, r, scheduler.get());
    if (o.mode == "adaptive" && !profile && state.remaining && r.stats.degree_queries >= budget) {
      const auto switch_start = Clock::now();
      // Release old heap, postings and subset map before reconstruction.
      scheduler.reset();
      scheduler.reset(new Profile(state, o)); profile = true;
      ++r.stats.switches;
      r.stats.switch_round = r.abort_rounds.size(); r.stats.switch_remaining = state.remaining;
      r.stats.switch_queries = r.stats.degree_queries;
      r.stats.switch_ms += ms(switch_start);
    }
  }
  auto certificate_start = Clock::now();
  for (size_t t = 0; t < b.ids.size(); ++t) if (r.commit[t]) r.certificate.push_back(b.ids[t]);
  std::sort(r.certificate.begin(), r.certificate.end());
  scheduler.reset(); // Include release of the final selector in the measured interval.
  r.stats.certificate_ms = ms(certificate_start);
  return r;
}
} // namespace
Result select(const Batch &b, const Options &o) {
  const auto start = Clock::now();
  Result r = select_impl(b, o);
  // The implementation's State arrays and all other local scratch storage
  // have been released before ending the kernel interval.
  r.stats.kernel_ms = r.stats.total_ms = ms(start);
  return r;
}
Result run(const std::vector<Input> &input, const Options &o) {
  Result r;
  auto start = Clock::now();
  {
    Batch batch = normalize(input, o);
    double normalization = ms(start);
    r = select(batch, o);
    r.stats.normalize_ms = normalization;
  } // Include release of normalized IDs/keys in the full selector interval.
  r.stats.total_ms = ms(start);
  return r;
}
bool same_decisions(const Result &a, const Result &b) {
  return a.abort_rounds == b.abort_rounds && a.commit == b.commit && a.certificate == b.certificate &&
      a.consideration_order == b.consideration_order && a.rejected_ids == b.rejected_ids &&
      a.initial_degrees == b.initial_degrees;
}
} // namespace eas
