#pragma once
#include "eas/Selector.h"
#include <array>
#include <memory>

namespace aria { class AriaTransaction; }
namespace eas {
struct Value {
  std::array<uint64_t, 4> words{};
  bool operator==(const Value &o) const { return words == o.words; }
  bool operator!=(const Value &o) const { return !(*this == o); }
};
struct Trace {
  size_t key_count = 0;
  uint64_t seed = 0, batch_id = 0;
  std::vector<Input> input;
};
struct Measurement {
  Result result;
  double batch_ms = 0, read_wall_ms = 0, commit_wall_ms = 0;
  double read_worker_ms = 0, commit_worker_ms = 0;
  double reservation_worker_ms = 0, dependency_worker_ms = 0, apply_worker_ms = 0;
  double sync_wait_ms = 0, extract_ms = 0, selector_ms = 0;
  std::vector<Value> final_state; // retained for direct integration-test comparisons
};
Trace read_trace(const std::string &path);
bool same_logical_inputs(const std::vector<Input> &a, const std::vector<Input> &b);
std::vector<Input> extract_transactions(
    const std::vector<std::unique_ptr<aria::AriaTransaction>> &transactions,
    size_t key_count);
// Runs real AriaManager/AriaExecutor phase transitions. No retries.
std::vector<Measurement> run_engine(const std::vector<Trace> &traces,
                                    const Options &options, size_t workers);
std::string measurement_json(const Measurement &m, const Trace &trace,
    const Options &options, size_t workers, bool selector_only);
} // namespace eas
