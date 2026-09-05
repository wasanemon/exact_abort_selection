#include "eas/Selector.h"
#include <algorithm>
#include <set>

namespace eas {
// No normalized dense keys, subset counters, trimming queue or optimized rank structure.
Result oracle(const std::vector<Input> &input, size_t k) {
  if (!k) throw Unsupported("oracle k=0");
  if (input.size() > 256) throw Unsupported("oracle limited to 256 transactions");
  std::vector<std::set<Key>> keys;
  std::set<uint64_t> ids;
  for (const auto &t : input) {
    if (t.remote || t.range || !ids.insert(t.id).second) throw Unsupported("invalid oracle input");
    std::set<Key> r(t.reads.begin(), t.reads.end()), w(t.writes.begin(), t.writes.end());
    if (r != w) throw Unsupported("oracle requires R=W");
    keys.push_back(std::move(r));
  }
  Result result; result.commit.resize(input.size());
  std::vector<bool> alive(input.size(), true);
  for (;;) {
    std::vector<size_t> degrees(input.size());
    for (size_t t = 0; t < input.size(); ++t) if (alive[t])
      for (size_t u = 0; u < input.size(); ++u) if (alive[u] && u != t) {
        bool hit = false;
        for (const auto &key : keys[t]) if (keys[u].count(key)) { hit = true; break; }
        degrees[t] += hit;
      }
    std::vector<size_t> candidates;
    for (size_t t = 0; t < input.size(); ++t) if (alive[t]) {
      if (!degrees[t]) { alive[t] = false; result.commit[t] = 1; }
      else candidates.push_back(t);
    }
    if (candidates.empty()) break;
    std::sort(candidates.begin(), candidates.end(), [&](size_t t, size_t u) {
      return degrees[t] != degrees[u] ? degrees[t] > degrees[u] : input[t].id > input[u].id;
    });
    if (candidates.size() < k) k = 1;
    result.abort_rounds.emplace_back();
    for (size_t i = 0; i < k; ++i) {
      auto t = candidates[i]; result.abort_rounds.back().push_back(input[t].id); alive[t] = false;
    }
  }
  for (size_t t = 0; t < input.size(); ++t) if (result.commit[t]) result.certificate.push_back(input[t].id);
  std::sort(result.certificate.begin(), result.certificate.end());
  return result;
}
} // namespace eas
