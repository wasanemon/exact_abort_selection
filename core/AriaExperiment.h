#pragma once

#include <chrono>
#include <cstdint>
#include <memory>
#include <vector>

namespace aria {
class AriaTransaction;

// Optional, single-node experiment observer. The default Context has no hook.
// Only the manager calls phase callbacks; each worker owns one metrics slot.
struct AriaExperiment {
  struct WorkerTimes {
    uint64_t read_begin = 0, read_end = 0, commit_begin = 0, commit_end = 0;
    uint64_t reservation = 0, dependency = 0, apply = 0;
  };
  static uint64_t now() {
    return std::chrono::duration_cast<std::chrono::nanoseconds>(
        std::chrono::steady_clock::now().time_since_epoch()).count();
  }
  virtual ~AriaExperiment() = default;
  virtual void before_read(uint32_t epoch) = 0;
  virtual void after_read(uint32_t epoch,
      const std::vector<std::unique_ptr<AriaTransaction>> &transactions) = 0;
  virtual bool after_commit(uint32_t epoch,
      const std::vector<std::unique_ptr<AriaTransaction>> &transactions) = 0;
  bool use_decisions = false;
  std::vector<uint8_t> decisions, committed;
  std::vector<WorkerTimes> worker_times;
};
} // namespace aria
