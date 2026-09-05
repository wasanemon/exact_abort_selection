#include "eas/Engine.h"
#include <algorithm>
#include <fstream>
#include <iostream>
#include <set>
#include <sstream>
#include <glog/logging.h>

namespace {
uint64_t number(const std::string &s) {
  if (s.empty() || s.find_first_not_of("0123456789") != std::string::npos)
    throw eas::Unsupported("invalid unsigned numeric argument");
  return std::stoull(s);
}
std::string escape(const std::string &s) {
  std::string out;
  for (char c : s) {
    if (c == '"' || c == '\\') out += '\\';
    if (c == '\n') out += "\\n"; else out += c;
  }
  return out;
}
void check_certificate(const eas::Trace &trace, const eas::Result &r) {
  // Linear-sized independent disjointness and complete partition checks;
  // never builds a hidden graph for large implicit-selector measurements.
  std::set<eas::Key> used;
  std::set<uint64_t> aborted;
  for (const auto &round : r.abort_rounds) for (auto id : round)
    if (!aborted.insert(id).second) throw std::logic_error("duplicate abort ID");
  std::vector<uint64_t> certificate;
  for (size_t t = 0; t < trace.input.size(); ++t) {
    const auto &input = trace.input[t];
    if (r.commit[t]) {
      if (aborted.count(input.id)) throw std::logic_error("committed abort ID");
      certificate.push_back(input.id);
      std::set<eas::Key> local(input.reads.begin(), input.reads.end());
      for (const auto &key : local) if (!used.insert(key).second) throw std::logic_error("intersecting certificate");
    } else if (!aborted.count(input.id)) throw std::logic_error("missing abort ID");
  }
  std::sort(certificate.begin(), certificate.end());
  if (certificate != r.certificate || aborted.size() + certificate.size() != trace.input.size())
    throw std::logic_error("invalid certificate partition");
}
}
int main(int argc, char **argv) {
  google::InitGoogleLogging(argv[0]); FLAGS_logtostderr = true; FLAGS_minloglevel = 2;
  std::string output_path;
  eas::Options options;
  size_t workers = 1;
  bool selector_only = false;
  std::vector<std::string> paths;
  try {
    for (int i = 1; i < argc; ++i) {
      std::string arg = argv[i];
      if (arg == "--selector-only") { selector_only = true; continue; }
      if (arg == "--help") {
        std::cout << "bench_eas --trace FILE [--trace NEXT_BATCH] --mode native|graph|lazy|profile|adaptive "
                     "[--k 2] [--workers 1] [--selector-only] [--max-incidence 8000000] "
                     "[--max-graph-bytes 536870912] [--output FILE]\n";
        return 0;
      }
      if (++i == argc) throw eas::Unsupported("missing argument value");
      std::string value = argv[i];
      if (arg == "--mode") options.mode = value;
      else if (arg == "--trace") paths.push_back(value);
      else if (arg == "--output") output_path = value;
      else if (arg == "--k") options.k = number(value);
      else if (arg == "--workers") workers = number(value);
      else if (arg == "--max-incidence") options.max_incidence = number(value);
      else if (arg == "--max-graph-bytes") options.max_graph_bytes = number(value);
      else if (arg == "--adaptive-budget") options.adaptive_budget = number(value);
      else if (arg == "--profile-B") options.profile_B = number(value);
      else throw eas::Unsupported("unknown option: " + arg);
    }
    if (paths.empty()) throw eas::Unsupported("--trace is required");
    std::vector<eas::Trace> traces;
    for (const auto &path : paths) traces.push_back(eas::read_trace(path));
    std::vector<eas::Measurement> measurements;
    if (selector_only) {
      if (options.mode == "native" || !workers) throw eas::Unsupported("native requires engine; workers must be positive");
      for (const auto &trace : traces) {
        eas::Measurement m; m.result = eas::run(trace.input, options);
        m.selector_ms = m.result.stats.total_ms; m.extract_ms = m.result.stats.normalize_ms;
        check_certificate(trace, m.result);
        if (trace.input.size() <= 64 && !eas::same_decisions(m.result, eas::oracle(trace.input, options.k)))
          throw std::logic_error("selector-only oracle mismatch");
        measurements.push_back(std::move(m));
      }
    } else measurements = eas::run_engine(traces, options, workers);
    std::ostringstream json;
    if (measurements.size() > 1) json << '[';
    for (size_t i = 0; i < measurements.size(); ++i) {
      if (i) json << ',';
      json << eas::measurement_json(measurements[i], traces[i], options, workers, selector_only);
    }
    if (measurements.size() > 1) json << ']';
    json << '\n';
    if (output_path.empty()) std::cout << json.str();
    else { std::ofstream out(output_path); if (!out) throw eas::Unsupported("cannot open output"); out << json.str(); }
    return 0;
  } catch (const std::exception &e) {
    std::string status = dynamic_cast<const eas::Unsupported *>(&e) ? "unsupported" : "error";
    const std::string json = "{\"status\":\"" + status + "\",\"error\":\"" + escape(e.what()) + "\"}\n";
    if (!output_path.empty()) { std::ofstream out(output_path); out << json; }
    std::cerr << json;
    return status == "unsupported" ? 2 : 1;
  }
}
