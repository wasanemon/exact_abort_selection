#include "eas/Selector.h"
#include <algorithm>
#include <array>
#include <fstream>
#include <iostream>
#include <numeric>
#include <random>
#include <set>

namespace {
using Input = std::vector<eas::Input>;
uint64_t cases = 0, optimal_subsets = 0, witness_cases = 0;
void require(bool ok, const char *why) { if (!ok) throw std::runtime_error(why); }
Input make(const std::vector<std::vector<uint64_t>> &sets) {
  Input in;
  for (const auto &s : sets) {
    eas::Input t; t.id = in.size()+1;
    for (auto k : s) t.reads.push_back({0,0,k});
    t.writes=t.reads; in.push_back(t);
  }
  return in;
}
std::vector<std::set<eas::Key>> keysets(const Input &in) {
  std::vector<std::set<eas::Key>> out;
  for (const auto &t : in) out.emplace_back(t.reads.begin(),t.reads.end());
  return out;
}
bool hit(const std::set<eas::Key> &a,const std::set<eas::Key> &b) {
  for (const auto &k : a) if (b.count(k)) return true;
  return false;
}
eas::Result native(const Input &in) {
  eas::Result r; r.commit.resize(in.size());
  auto sets = keysets(in);
  for (size_t t=0;t<in.size();++t) {
    bool keep=true;
    for (size_t u=0;u<in.size();++u) if (in[u].id<in[t].id && hit(sets[t],sets[u])) keep=false;
    if (keep) { r.commit[t]=1; r.certificate.push_back(in[t].id); }
  }
  std::sort(r.certificate.begin(),r.certificate.end()); return r;
}
void safety(const Input &in,const eas::Result &r,bool maximal) {
  require(r.commit.size()==in.size(),"mask length");
  auto sets=keysets(in);
  for (size_t t=0;t<in.size();++t) {
    bool blocked=false;
    for (size_t u=0;u<in.size();++u) if (r.commit[u] && u!=t && hit(sets[t],sets[u])) blocked=true;
    require(!r.commit[t] || !blocked,"non-disjoint commits");
    if (maximal) require(r.commit[t] || blocked,"nonmaximal acceptance");
  }
}
size_t maximum(const Input &in) {
  require(in.size()<=18,"maximum budget exceeded");
  auto sets=keysets(in);
  std::vector<uint32_t> neighbors(in.size());
  for (size_t t=0;t<in.size();++t) for (size_t u=0;u<in.size();++u)
    if(t!=u && hit(sets[t],sets[u])) neighbors[t]|=1u<<u;
  const uint32_t limit=1u<<in.size();
  std::vector<uint8_t> feasible(limit); feasible[0]=1;
  size_t best=0;
  for(uint32_t mask=1;mask<limit;++mask) {
    const auto t=__builtin_ctz(mask); const auto rest=mask&(mask-1);
    feasible[mask]=feasible[rest] && !(neighbors[t]&rest);
    if(feasible[mask]) best=std::max(best,size_t(__builtin_popcount(mask)));
  }
  optimal_subsets+=limit; return best;
}
template<class T> void array(std::ostream &out,const std::vector<T> &v) {
  out<<'['; for(size_t i=0;i<v.size();++i) { if(i) out<<','; out<<+v[i]; } out<<']';
}
void input_json(std::ostream &out,const Input &in) {
  out<<'[';
  for(size_t t=0;t<in.size();++t) {
    if(t)out<<',';
    out<<"{\"id\":"<<in[t].id<<",\"keys\":[";
    for(size_t j=0;j<in[t].reads.size();++j) {if(j)out<<',';out<<in[t].reads[j].value;} out<<"]}";
  }
  out<<']';
}
std::array<eas::Result,5> evaluate(const Input &in) {
  std::array<eas::Result,5> rs; rs[0]=native(in);
  for(size_t p=1;p<5;++p) {
    eas::Options o; o.mode=p==1?"accept_id":p==2?"accept_static_degree":"adaptive";o.k=p==4?2:1;
    o.audit_degrees=true;
    rs[p]=eas::run(in,o);
    const auto ref=p<3?eas::acceptance_oracle(in,p==2):eas::oracle(in,o.k);
    require(eas::same_decisions(rs[p],ref),"independent policy oracle mismatch");
    if(p<3)require(rs[p].abort_rounds.empty(),"acceptance fabricated abort rounds");
    if(p==1) require(rs[p].stats.subsets==0 && rs[p].stats.incidences==0 && rs[p].stats.initial_degree_evaluations==0,"accept_id built index");
  }
  for(size_t p=0;p<5;++p)safety(in,rs[p],p==1||p==2);
  return rs;
}
void quality_case(const Input &in,const char *suite,uint64_t code,std::ostream *out) {
  const auto rs=evaluate(in); const auto opt=maximum(in); ++cases;
  if(out) {
    *out<<"{\"suite\":\""<<suite<<"\",\"case\":"<<code<<",\"input\":";input_json(*out,in);
    *out<<",\"maximum\":"<<opt<<",\"commits\":[";
    for(size_t p=0;p<5;++p) {require(rs[p].certificate.size()<=opt,"exceeds optimum");if(p)*out<<',';*out<<rs[p].certificate.size();}
    *out<<"]}\n";
  }
}
void exhaustive(size_t universe,size_t max_n,bool pairs,std::ostream *out) {
  std::vector<std::vector<uint64_t>> alphabet;
  for(uint32_t mask=0;mask<(1u<<universe);++mask) {
    if(pairs && __builtin_popcount(mask)!=2)continue;
    std::vector<uint64_t>s;for(size_t k=0;k<universe;++k)if(mask&(1u<<k))s.push_back(k);
    alphabet.push_back(s);
  }
  uint64_t total=1;
  for(size_t n=0;n<=max_n;++n) {
    for(uint64_t code=0;code<total;++code) {
      uint64_t rest=code;std::vector<std::vector<uint64_t>>sets;
      for(size_t t=0;t<n;++t) {sets.push_back(alphabet[rest%alphabet.size()]);rest/=alphabet.size();}
      quality_case(make(sets),pairs?"ordered_pairs_u4":"all_subsets_u3",code,out);
    }
    total*=alphabet.size();
  }
}
void random_cases(std::ostream *out) {
  std::mt19937_64 rng(202609053);
  for(size_t code=0;code<1000;++code) {
    const size_t n=rng()%19,universe=1+rng()%10;
    std::vector<std::vector<uint64_t>>sets(n);
    for(auto &s:sets) {size_t arity=rng()%5;for(size_t j=0;j<arity;++j)s.push_back(rng()%universe);}
    auto in=make(sets);
    // Nonmonotone large IDs, separate key addresses and duplicate operations.
    for(auto &t:in)t.id=UINT64_MAX-t.id;
    std::shuffle(in.begin(),in.end(),rng);
    quality_case(in,"random",code,out);
  }
}
bool inequality(const Input &in,bool eas_wins) {
  const auto s=eas::acceptance_oracle(in,true).certificate.size(),e=eas::oracle(in,1).certificate.size();
  return eas_wins?e>s:s>e;
}
Input canonical(Input in) {
  std::set<uint64_t> keys;for(auto &t:in)for(auto k:t.reads)keys.insert(k.value);
  std::vector<uint64_t>sorted(keys.begin(),keys.end());
  for(size_t i=0;i<in.size();++i) {
    in[i].id=i+1;
    for(auto &k:in[i].reads)k.value=std::lower_bound(sorted.begin(),sorted.end(),k.value)-sorted.begin();
    std::sort(in[i].reads.begin(),in[i].reads.end());in[i].writes=in[i].reads;
  }
  return in;
}
Input minimize(Input in,bool direction) {
  for(;;) {
    bool changed=false;
    for(size_t t=0;t<in.size();++t) {
      auto trial=in;trial.erase(trial.begin()+t);trial=canonical(trial);
      if(inequality(trial,direction)) {in=trial;changed=true;break;}
    }
    if(changed)continue;
    std::set<uint64_t>keys;for(auto &t:in)for(auto k:t.reads)keys.insert(k.value);
    for(auto a:keys) {for(auto b:keys)if(a<b) {
      auto trial=in;bool valid=true;
      for(auto &t:trial) {
        for(auto &k:t.reads)if(k.value==b)k.value=a;
        if(t.reads[0]==t.reads[1])valid=false;
      }
      trial=canonical(trial);
      if(valid && inequality(trial,direction)) {in=trial;changed=true;break;}
    } if(changed)break;}
    if(!changed)return in;
  }
}
void witnesses(const std::string &dir) {
  std::mt19937_64 rng(202609054);std::array<Input,2> first;
  std::array<size_t,3> counts{};
  std::ofstream raw(dir+"/witness_search.jsonl");require(bool(raw),"open search raw");
  for(size_t sample=0;sample<20000;++sample) {
    const size_t n=5+rng()%14,u=4+rng()%7;std::vector<std::vector<uint64_t>>sets(n);
    for(auto &s:sets) {auto a=rng()%u,b=rng()%u;while(a==b)b=rng()%u;s={std::min(a,b),std::max(a,b)};}
    const auto in=make(sets);const auto rs=evaluate(in);++witness_cases;
    const auto e=rs[3].certificate.size(),s=rs[2].certificate.size();
    const size_t category=e>s?0:s>e?1:2;++counts[category];
    if(category<2 && first[category].empty())first[category]=in;
    raw<<"{\"case\":"<<sample<<",\"input\":";input_json(raw,in);raw<<",\"eas_k1\":"<<e<<",\"static\":"<<s<<"}\n";
  }
  std::ofstream out(dir+"/witnesses.json");out<<"{\"search_cases\":20000,\"eas_wins\":"<<counts[0]<<",\"static_wins\":"<<counts[1]<<",\"ties\":"<<counts[2]<<",\"examples\":[";
  for(size_t d=0;d<2;++d) {
    if(d)out<<',';
    out<<"{\"direction\":\""<<(d==0?"eas_gt_static":"static_gt_eas")<<"\",\"found\":"<<(!first[d].empty()?"true":"false");
    if(!first[d].empty()) {
      const auto in=minimize(first[d],d==0); const auto rs=evaluate(in);
      out<<",\"original\":";input_json(out,first[d]);out<<",\"minimal\":";input_json(out,in);
      out<<",\"maximum\":"<<maximum(in)<<",\"static_order\":";array(out,rs[2].consideration_order);
      out<<",\"static_degrees\":";array(out,rs[2].initial_degrees);
      out<<",\"static_commit\":";array(out,rs[2].certificate);out<<",\"eas_commit\":";array(out,rs[3].certificate);
      out<<",\"eas_rounds\":[";for(size_t j=0;j<rs[3].abort_rounds.size();++j){if(j)out<<',';array(out,rs[3].abort_rounds[j]);}out<<']';
      std::ofstream trace(dir+"/"+(d==0?"eas_gt_static":"static_gt_eas")+".tsv");trace<<"EAS_TRACE_V1 32 202609054 0\n";
      for(auto &t:in)trace<<t.id<<'\t'<<t.reads[0].value<<','<<t.reads[1].value<<'\n';
    }
    out<<'}';
  }
  out<<"]}\n";
}
void targeted() {
  auto in=make({{0,0,UINT64_MAX},{UINT64_MAX},{7},{}});
  in[0].reads.push_back({1,UINT64_MAX,0});in[0].writes=in[0].reads;
  evaluate(in);
  auto pair=make({{1,2},{1,2}});
  require(eas::oracle(pair,2).certificate.empty(),"k2 zero regression");
  require(eas::oracle(pair,1).certificate.size()==1,"k1 zero contrast");
  eas::Options o;o.mode="accept_id";o.max_incidence=0;o.max_graph_bytes=0;o.k=0;o.max_arity=100;
  std::vector<uint64_t>keys(80);std::iota(keys.begin(),keys.end(),0);
  require(eas::run(make({keys,keys,{}}),o).certificate.size()==2,"accept_id inherited EAS subset/shift limit");
  o.max_arity=8;
  for(const auto &mode:{"accept_id","accept_static_degree"}) {
    o.mode=mode;o.max_incidence=8000000;
    for(size_t kind=0;kind<5;++kind) {
      auto bad=pair;
      if(kind==0)bad[0].remote=true;
      if(kind==1)bad[0].range=true;
      if(kind==2)bad[0].writes.clear();
      if(kind==3)bad[1].id=bad[0].id;
      if(kind==4)bad[0].reads.clear();
      bool caught=false;try{eas::run(bad,o);}catch(const eas::Unsupported&){caught=true;}
      require(caught,"acceptance accepted invalid RMW");
    }
  }
}
}
int main(int argc,char **argv) {
  try {
    const bool full=argc==3 && std::string(argv[1])=="--quality-dir";
    if(argc!=1 && !full)throw std::runtime_error("usage: policy_comparison_test [--quality-dir EXISTING_DIR]");
    std::ofstream raw;if(full){raw.open(std::string(argv[2])+"/quality.jsonl");require(bool(raw),"open quality raw");}
    auto *out=full?&raw:nullptr;
    targeted();exhaustive(3,4,false,out);if(full)exhaustive(4,6,true,out);random_cases(out);
    if(full)witnesses(argv[2]);
    std::cout<<"{\"status\":\"passed\",\"quality_cases\":"<<cases<<",\"optimal_subsets_enumerated\":"<<optimal_subsets<<",\"witness_cases\":"<<witness_cases<<",\"policies\":[\"native\",\"accept_id\",\"accept_static_degree\",\"eas_k1\",\"eas_k2\"]}\n";
  }catch(const std::exception &e){std::cerr<<e.what()<<'\n';return 1;}
}
