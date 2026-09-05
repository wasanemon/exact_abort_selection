#include "eas/Engine.h"
#include "protocol/Aria/AriaTransaction.h"
#include <iostream>
#include <random>
#include <glog/logging.h>

namespace {
size_t checks = 0, runs = 0, batches = 0;
void require(bool ok, const char *message) { ++checks; if (!ok) throw std::runtime_error(message); }
template<class F> void rejected(F f) {
  bool caught = false; try { f(); } catch (const eas::Unsupported &) { caught = true; }
  require(caught, "unsupported input was accepted");
}
eas::Trace trace(std::initializer_list<std::initializer_list<uint64_t>> sets) {
  eas::Trace result; result.key_count = 32;
  for (const auto &set : sets) {
    eas::Input t; t.id = result.input.size() + 1;
    for (auto key : set) t.reads.push_back({0, 0, key});
    t.writes = t.reads; result.input.push_back(t);
  }
  return result;
}
std::vector<eas::Measurement> execute(const std::vector<eas::Trace> &traces, eas::Options o, size_t workers) {
  ++runs; batches += traces.size(); return eas::run_engine(traces, o, workers);
}
struct Bare : aria::AriaTransaction {
  explicit Bare(aria::Partitioner &p) : AriaTransaction(0, 0, p) { set_id(1); set_epoch(1); set_tid_offset(0); }
  aria::TransactionResult execute(size_t) override { return aria::TransactionResult::READY_TO_COMMIT; }
  void reset_query() override {}
};
}
int main(int argc, char **argv) {
  google::InitGoogleLogging(argv[0]); FLAGS_logtostderr = true; FLAGS_minloglevel = 2;
  try {
    const auto example = trace({{0,1}, {0,2}, {1,3}});
    const auto frozen = trace({{0}, {0}, {0}, {0}, {1}, {1}, {1}});
    const auto zero = trace({{0}, {0}});
    const auto logical_a = trace({{0}}), logical_b = trace({{1}});
    eas::Options logical_options;
    require(eas::normalize(logical_a.input, logical_options).keys ==
            eas::normalize(logical_b.input, logical_options).keys, "dense relabeling counterexample setup");
    require(!eas::same_logical_inputs(logical_a.input, logical_b.input),
            "trace equality must compare original logical values, not separately dense labels");
    for (const auto &mode : {"native", "graph", "lazy", "profile", "adaptive", "accept_id", "accept_static_degree"}) {
      eas::Options o; o.mode = mode; o.k = 1;
      auto m = execute({example}, o, 1).front();
      require(m.result.certificate == ((o.mode == "native" || o.mode == "accept_id") ? std::vector<uint64_t>{1} : std::vector<uint64_t>{2,3}), "native vs EAS semantic example");
      o.k = 2;
      m = execute({zero}, o, 4).front();
      require(m.result.certificate.size() == (o.mode == "native" || eas::is_acceptance(o.mode) ? 1 : 0), "frozen top-2 zero commits");
      if (o.mode != "native" && !eas::is_acceptance(o.mode)) {
        m = execute({frozen}, o, 2).front();
        require(m.result.abort_rounds.front() == std::vector<uint64_t>({4,3}), "frozen candidates changed within round");
      }
    }
    std::mt19937_64 rng(20260905);
    for (size_t sample = 0; sample < 12; ++sample) {
      eas::Trace input; input.key_count = 40; input.seed = sample;
      const size_t n = 1 + rng() % 40;
      for (size_t t = 0; t < n; ++t) {
        eas::Input tx; tx.id = t + 1;
        const size_t arity = (sample % 4) + 1;
        for (size_t j = 0; j < arity; ++j) tx.reads.push_back({0,0,rng() % input.key_count});
        tx.writes = tx.reads; input.input.push_back(tx);
      }
      eas::Result reference;
      for (const auto &mode : {"native", "graph", "lazy", "profile", "adaptive", "accept_id", "accept_static_degree"}) {
        eas::Options o; o.mode = mode; o.k = sample % 4 == 3 ? n + 3 : sample % 3 + 1;
        if (o.mode == "adaptive" && sample % 2) o.adaptive_budget = sample % 3;
        auto one = execute({input}, o, 1).front();
        auto many = execute({input}, o, 4).front();
        require(eas::same_decisions(one.result, many.result), "worker-dependent decisions");
        require(one.final_state == many.final_state, "worker-dependent full DB state");
        if (o.mode == "graph") reference = one.result;
        if (o.mode != "native" && !eas::is_acceptance(o.mode)) require(eas::same_decisions(reference, one.result), "EAS mode-dependent decisions");
      }
    }
    auto a = trace({{0,1}, {0,2}, {1,3}});
    auto b = trace({{0,2}, {0,2}, {0,2}}); b.batch_id = 1;
    auto c = trace({{0,1}, {2,3}, {4,5}}); c.batch_id = 2;
    for (const auto &mode : {"native", "graph", "lazy", "profile", "adaptive", "accept_id", "accept_static_degree"}) {
      eas::Options o; o.mode = mode; o.k = 2; o.adaptive_budget = 0;
      auto single = execute({a,b,c}, o, 1);
      auto parallel = execute({a,b,c}, o, 4);
      auto two = execute({a,b,c}, o, 2);
      require(single.size() == 3 && parallel.size() == 3, "three real batches missing");
      for (size_t i = 0; i < 3; ++i) {
        require(eas::same_decisions(single[i].result, parallel[i].result), "multi-batch decision state leak");
        require(single[i].final_state == parallel[i].final_state, "multi-batch DB state leak");
        require(eas::same_decisions(single[i].result, two[i].result) && single[i].final_state == two[i].final_state, "worker=2 multi-batch leak");
      }
      require(parallel[2].result.certificate == std::vector<uint64_t>({1,2,3}), "mask leaked across epochs");
    }
    for (const auto &mode : {"native", "graph", "lazy", "profile", "adaptive", "accept_id", "accept_static_degree"}) {
      eas::Options o; o.mode = mode;
      require(execute({trace({})}, o, 2).front().result.commit.empty(), "empty batch");
      require(execute({trace({{}})}, o, 2).front().result.certificate == std::vector<uint64_t>{1}, "empty transaction");
    }
    // Native keeps reservations of later-rejected transactions; accept_id does not.
    const auto reservations = trace({{0}, {0,1}, {1,2}});
    for (const auto &mode : {"native", "accept_id", "accept_static_degree"}) {
      eas::Options o; o.mode = mode; o.max_incidence = mode == std::string("accept_id") ? 0 : 8000000;
      const auto r = execute({reservations}, o, 2).front().result;
      require(r.certificate == (o.mode == "native" ? std::vector<uint64_t>{1} : std::vector<uint64_t>{1,3}), "rejected reservation semantic distinction");
    }
    // Validate extraction using actual AriaRWKey objects and different addresses.
    aria::HashPartitioner partitioner(0, 1);
    std::vector<std::unique_ptr<aria::AriaTransaction>> txns;
    txns.emplace_back(new Bare(partitioner));
    uint64_t read_key = 5, write_key = 5;
    eas::Value read, write;
    txns[0]->search_for_update(0,0,read_key,read);
    txns[0]->search_for_update(0,0,read_key,read); // duplicate operation, one logical key
    txns[0]->update(0,0,write_key,write);
    eas::Options o;
    auto normalized = eas::normalize(eas::extract_transactions(txns, 32), o);
    require(normalized.keys[0].size() == 1, "logical key normalization uses pointers");
    write_key = 6;
    rejected([&] { eas::normalize(eas::extract_transactions(txns, 32), o); });
    write_key = 5; txns[0]->distributed_transaction = true;
    rejected([&] { eas::extract_transactions(txns, 32); });
    txns[0]->distributed_transaction = false;
    txns[0]->writeSet[0].set_partition_id(1);
    rejected([&] { eas::extract_transactions(txns, 32); });
    txns[0]->writeSet[0].set_partition_id(0); txns[0]->readSet[0].set_local_index_read_bit();
    rejected([&] { eas::extract_transactions(txns, 32); });
    rejected([&] { execute({example}, o, 0); });
    auto invalid = example; invalid.input[0].remote = true;
    rejected([&] { execute({invalid}, o, 1); });
    invalid = example; invalid.input[0].range = true;
    rejected([&] { execute({invalid}, o, 1); });
    invalid = example; invalid.input[0].id = 100;
    rejected([&] { execute({invalid}, o, 1); });
    invalid = trace({{0,1,2,3,4}});
    rejected([&] { execute({invalid}, o, 1); });
    o.max_graph_bytes = 0; o.mode = "graph";
    rejected([&] { execute({example}, o, 4); }); // failure path must join all waiting workers
    o.mode = "adaptive"; o.max_incidence = 1;
    rejected([&] { execute({example}, o, 1); });
    std::cout << "{\"status\":\"passed\",\"engine_invocations\":" << runs
              << ",\"requested_batches\":" << batches << ",\"assertions\":" << checks
              << ",\"workers\":[1,2,4],\"multi_batch_epochs\":3,\"direct_snapshot_private_write_full_state_checks\":true}\n";
    return 0;
  } catch (const std::exception &e) {
    std::cerr << "integration failure: " << e.what() << '\n'; return 1;
  }
}
