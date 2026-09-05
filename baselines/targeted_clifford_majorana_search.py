"""Uniform targeted Clifford search, no ancillas.

Self-contained relative to the frozen harness; requires NumPy and C++17.
The native source is embedded so the inbox single-file promotion remains valid.
"""

import math

import numpy as np

from harness.constructors import from_linear_encoding, transitive_closure
from harness.lattice import hamiltonian
from harness.paulis import string_to_xz, xz_to_string

_LABELS = "XYZ"  # child offset 0, 1, 2 (i.e. (node-1) % 3) -> edge label


def _leaf_xz(leaf, m):
    """(x, z) bit vectors, length m, for a single tree leaf: walk leaf ->
    root, and at each ancestor router qubit set the label of the edge taken
    toward the next node on the path.
    """
    x = np.zeros(m, dtype=np.uint8)
    z = np.zeros(m, dtype=np.uint8)
    node = leaf
    while node != 0:
        parent = (node - 1) // 3
        label = _LABELS[(node - 1) % 3]
        if label in ("X", "Y"):
            x[parent] = 1
        if label in ("Y", "Z"):
            z[parent] = 1
        node = parent
    return x, z


def _tree_mode_pairs(m):
    """m tree "slots", each a pair of (x, z) bit vectors -- the two
    Majorana operators for that slot, drawn from consecutive leaves of a
    perfect ternary tree's 2m (of 2m+1) used leaves.

    Ancilla-free (N = M): M "router" qubits, one per internal node of a
    perfect ternary tree built in breadth-first (heap) order -- node k's
    three children sit at indices 3k+1, 3k+2, 3k+3, labelled X, Y, Z
    respectively. A tree with M internal nodes has exactly 2M+1 leaf
    slots; 2M of them become the Majorana operators (one is left unused,
    the deepest one -- consecutive pairs starting at leaf index m). A
    leaf's Pauli string is built by walking from the leaf to the root:
    every ancestor router qubit contributes the X/Y/Z label of the edge
    taken toward the next node on the path, and weight = leaf depth. This
    is Jordan-Wigner's linear Z-chain generalised to branching factor 3
    (JW is the degenerate case where every router only ever uses one of
    its three children), so weight grows like log_3(M) instead of M.

    Correctness sketch: take two distinct leaves. Their root-to-leaf paths
    agree down to their deepest common ancestor A, then diverge into two
    different, and therefore node-disjoint, subtrees of A.
      - Above A: both operators carry the same label at each shared
        ancestor qubit, which never contributes to the symplectic pairing
        (a Pauli always "commutes" with itself qubit-by-qubit).
      - At A: the two paths leave via two different children of A, so
        they carry two distinct labels drawn from {X, Y, Z} -- any two
        distinct single-qubit Paulis among X, Y, Z anticommute,
        contributing 1.
      - Below A: the two operators act on disjoint qubit sets (disjoint
        subtrees), contributing 0.
      Total parity is always odd, so every pair of leaves anticommutes,
      independent of M or tree shape.

    A leaf's parent contributes 1, 2, or 3 leaves (only the bottom tier of
    routers contributes 3; higher routers contribute 0), so consecutive
    leaves aren't always siblings, and a pair straddling two different
    parents has weight > 1. That looks fixable by pairing within each
    parent first and only matching leftovers across parents -- tried,
    including recursive escalation of an unmatched leftover to its
    parent's own parent. Neither changed the *multiset* of pair weights
    at all (verified by direct comparison, M=169): it's a structural
    invariant of the tree's shape at a given m, fixed regardless of which
    valid pairing strategy assigns it to which specific leaves, and the
    fancier strategies broke the leaf-index locality the spatial ordering
    below relies on. Flat consecutive pairing came out ahead in practice
    for that reason, so it's what's kept.
    """
    if m == 0:
        return []
    return [(_leaf_xz(a, m), _leaf_xz(a + 1, m)) for a in range(m, 3 * m, 2)]


def _spatial_order(spec):
    """Permutation of spec's mode indices: order[k] is the mode assigned to
    tree leaf-pair k. Recursively splits the lattice into three roughly
    equal groups along its longer axis, mirroring a ternary tree's own
    branching, so physically adjacent sites tend to share long common tree
    ancestries -- shared as the starting point for both topologies'
    search below, not just geo_ternary's own tree.

    Group sizes are spread as evenly as possible (any leftover from n not
    dividing by 3 goes to the first groups, not dumped entirely into the
    last one) -- dumping the remainder at the end compounds over recursion
    levels into a systematically lopsided partition at sizes that don't
    divide cleanly by 3.
    """
    coords = spec["coords"]
    sites = sorted(coords.keys())

    def recurse(indices):
        if len(indices) <= 1:
            return list(indices)
        xs = [coords[i][0] for i in indices]
        ys = [coords[i][1] for i in indices]
        axis = 0 if (max(xs) - min(xs)) >= (max(ys) - min(ys)) else 1
        indices = sorted(indices, key=lambda i: coords[i][axis])
        n = len(indices)
        base, rem = divmod(n, 3)
        sizes = [base + (1 if i < rem else 0) for i in range(3)]
        groups, start = [], 0
        for size in sizes:
            if size:
                groups.append(indices[start:start + size])
            start += size
        result = []
        for g in groups:
            result += recurse(g)
        return result

    return recurse(sites)


def _sierpinski_edges(u, c, r):
    """Recursive Sierpinski-tree edge construction, arXiv 2504.21636's own
    ternary tree (reimplemented in plain numpy; see module docstring for
    why this is a self-contained copy rather than importing
    baselines/ternary.py). Pads to the next power of 3, recursively
    connects the middle third's midpoint to the midpoints of the other two
    thirds, preserving the reference's float-arithmetic midpoints (the
    range doesn't always split evenly into thirds).
    """
    if c == r:
        return

    def mid(a, b):
        return int((a + b) // 2)

    third = (r - c + 1) / 3
    l = c + third
    rr = c + 2 * third
    if mid(l, rr - 1) < u.shape[0] and mid(c, l - 1) < u.shape[1]:
        u[mid(l, rr - 1), mid(c, l - 1)] = 1
    if mid(l, rr - 1) < u.shape[0] and mid(rr, r) < u.shape[1]:
        u[mid(l, rr - 1), mid(rr, r)] = 1
    _sierpinski_edges(u, c, l - 1)
    _sierpinski_edges(u, l, rr - 1)
    _sierpinski_edges(u, rr, r)


def _sierpinski_matrix(n):
    padded = 3 ** math.ceil(math.log(n, 3)) if n > 1 else 1
    u = np.zeros((n, n), dtype=np.uint8)
    _sierpinski_edges(u, 0, padded - 1)
    u = transitive_closure(u)
    return (u + np.eye(n, dtype=np.uint8)) % 2


def _matrix_tree_pairs(matrix):
    """A linear-encoding matrix -> the same tree_pairs shape
    `_tree_mode_pairs` produces (a list of per-slot ((x, z), (x, z)) pairs),
    so `_optimize_order` can search over it identically -- it never looks
    at where a tree_pairs list came from, only at the (x, z) content.
    """
    n = matrix.shape[0]
    mapping = from_linear_encoding(matrix)
    pairs = []
    for i in range(n):
        pairs.append((string_to_xz(mapping["majoranas"][2 * i]), string_to_xz(mapping["majoranas"][2 * i + 1])))
    return pairs


def _pack(x, z):
    """(x, z) numpy bit vectors -> a pair of Python ints (bitmasks). XOR and
    popcount on plain ints (via int.bit_count()) are far cheaper than numpy
    array ops at the sizes _optimize_order calls this for -- thousands of
    small, single-term recomputations per search, not one bulk computation.
    """
    xi = zi = 0
    for i, (xb, zb) in enumerate(zip(x, z)):
        if xb:
            xi |= 1 << i
        if zb:
            zi |= 1 << i
    return xi, zi


_MAX_TRACKED_WEIGHT = 64  # weight cannot exceed n_qubits <= a few hundred at
                          # any size this harness's leaderboard covers, and in
                          # practice never gets close to this.


def _optimize_order(spec, tree_pairs, order, seed):
    """Local search over which spec mode gets which tree slot, hill-climbing
    on (max_weight, total_weight) lexicographically. Every candidate here is
    already a valid encoding -- relabelling which mode owns which of the 2M
    operators can't break the Majorana algebra, which is a property of the
    operator *set*, not of the labelling -- so this can only improve score,
    never validity.

    Algorithm: repeatedly take a mode `a` implicated in a current
    worst-weight term, try swapping its tree slot with every other mode
    `b` (a random sample of 80 when there are more candidates than that),
    and commit whichever swap most improves (max, total); if none improves,
    make a random swap anyway (seeded, so still deterministic) to escape a
    local optimum, tracking the best (order, max, total) seen so far to
    return even if later exploration wanders away from it.

    This is the max-weight-focused search from the registered baseline
    geo_ternary_opt (previously the only tree it ran on); unchanged here.
    Simulated annealing -- the lever that worked for *total* weight
    (accepting temporarily worse moves to escape a bad basin) -- was tried
    on this objective too and made things worse at every size tested, not
    better: max is a min-max objective this greedy search already explores
    exhaustively at each step (every candidate swap, every iteration), so
    there's no "stuck in a bad basin" problem annealing's randomness fixes
    -- it just adds noise. Likewise, more restarts and 10x the iteration
    budget move total weight (a few percent) but never move max weight at
    all, at every size tested -- the plateau is the *tree's* structural
    floor, not a search-budget problem, which is why `encode` runs this
    same search on a second, differently-shaped tree instead of running it
    longer on one. Full comparison in
    solution/memory/max_weight_search_topology.md.

    Bookkeeping for speed: each term's current weight is cached, and a
    swap only needs to recompute the (few) terms touching modes `a` or `b`,
    not the full term list; a fixed-size histogram of weight -> count of
    terms at that weight (bounded by _MAX_TRACKED_WEIGHT, comfortably above
    anything reachable here) gives the new max after a candidate swap in
    O(_MAX_TRACKED_WEIGHT) rather than O(number of terms).

    Iteration budget scales with m (20*m, floor 200) rather than being
    fixed, so it stays a size-driven formula, not a lookup keyed to specific
    Lx/Ly values (CLAUDE.md's "one uniform rule" requirement).
    """
    m = spec["M"]
    if m < 2:
        return order, 0, 0

    terms = hamiltonian(spec, model="full")
    slot_ops = [(_pack(*a), _pack(*b)) for a, b in tree_pairs]  # slot -> ((x,z)_gamma, (x,z)_gammabar), packed
    pos = [0] * m
    for k, mode in enumerate(order):
        pos[mode] = k

    def term_weight(term):
        x = z = 0
        for idx in term:
            xi, zi = slot_ops[pos[idx >> 1]][idx & 1]
            x ^= xi
            z ^= zi
        return (x | z).bit_count()

    weights = [term_weight(t) for t in terms]
    counts = [0] * _MAX_TRACKED_WEIGHT
    for w in weights:
        counts[w] += 1
    cur_max = max(w for w in range(_MAX_TRACKED_WEIGHT) if counts[w])
    cur_total = sum(weights)

    involves = [[] for _ in range(m)]
    for ti, term in enumerate(terms):
        for mode in {idx >> 1 for idx in term}:
            involves[mode].append(ti)

    best_pos, best_max, best_total = list(pos), cur_max, cur_total

    rng = np.random.default_rng(seed)
    max_iters = max(200, 20 * m)
    stall_limit = max(150, 3 * m)
    stall = 0
    for _ in range(max_iters):
        if stall >= stall_limit:
            break
        worst = [ti for ti, w in enumerate(weights) if w == cur_max]
        a = int(rng.choice(sorted({idx >> 1 for idx in terms[worst[int(rng.integers(len(worst)))]]})))

        candidates = range(m) if m <= 80 else rng.choice(m, size=80, replace=False)
        best_choice, best_key = None, (cur_max, cur_total)
        for b in candidates:
            b = int(b)
            if b == a:
                continue
            affected = list(set(involves[a]) | set(involves[b]))
            pos[a], pos[b] = pos[b], pos[a]
            new_weights, delta = {}, {}
            for ti in affected:
                w_old, w_new = weights[ti], term_weight(terms[ti])
                new_weights[ti] = w_new
                delta[w_old] = delta.get(w_old, 0) - 1
                delta[w_new] = delta.get(w_new, 0) + 1
            pos[a], pos[b] = pos[b], pos[a]

            tentative_max = max(w for w in range(_MAX_TRACKED_WEIGHT) if counts[w] + delta.get(w, 0) > 0)
            tentative_total = cur_total + sum(w * d for w, d in delta.items())
            key = (tentative_max, tentative_total)
            if key < best_key:
                best_key, best_choice = key, (b, new_weights, delta, tentative_max, tentative_total)

        if best_choice is None:
            stall += 1
            b = int(rng.integers(m))
            if b == a:
                continue
            affected = list(set(involves[a]) | set(involves[b]))
            pos[a], pos[b] = pos[b], pos[a]
            for ti in affected:
                w_old, w_new = weights[ti], term_weight(terms[ti])
                counts[w_old] -= 1
                counts[w_new] += 1
                cur_total += w_new - w_old
                weights[ti] = w_new
            cur_max = max(w for w in range(_MAX_TRACKED_WEIGHT) if counts[w])
            continue

        stall = 0
        b, new_weights, delta, cur_max, cur_total = best_choice
        pos[a], pos[b] = pos[b], pos[a]
        for ti, w in new_weights.items():
            weights[ti] = w
        for w, d in delta.items():
            counts[w] += d
        if (cur_max, cur_total) < (best_max, best_total):
            best_max, best_total, best_pos = cur_max, cur_total, list(pos)

    new_order = [None] * m
    for mode, k in enumerate(best_pos):
        new_order[k] = mode
    return new_order, best_max, best_total


def _emit(tree_pairs, order, m):
    majoranas = [None] * (2 * m)
    for k, mode in enumerate(order):
        (xa, za), (xb, zb) = tree_pairs[k]
        majoranas[2 * mode] = xz_to_string(xa, za)
        majoranas[2 * mode + 1] = xz_to_string(xb, zb)
    return {"n_qubits": m, "majoranas": majoranas, "stabilizers": []}


def _seed_encode(spec):
    m = spec["M"]
    start_order = _spatial_order(spec)

    geo_pairs = _tree_mode_pairs(m)
    geo_order, geo_max, geo_total = _optimize_order(spec, geo_pairs, start_order, seed=m)

    sierpinski_pairs = _matrix_tree_pairs(_sierpinski_matrix(m))
    sierpinski_order, sierpinski_max, sierpinski_total = _optimize_order(spec, sierpinski_pairs, start_order, seed=m)

    if (geo_max, geo_total) <= (sierpinski_max, sierpinski_total):
        return _emit(geo_pairs, geo_order, m)
    return _emit(sierpinski_pairs, sierpinski_order, m)

import functools
import shutil
import subprocess
import tempfile
from pathlib import Path

_NATIVE_SOURCE = r'''
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <iostream>
#include <random>
#include <stdexcept>
#include <tuple>
#include <vector>
using namespace std;
#ifndef PAULI_BLOCKS
#define PAULI_BLOCKS 4
#endif
int blocks;
struct P {
    array<uint64_t,PAULI_BLOCKS> x{}, z{};
    P operator^(const P& b) const { P c; for(int k=0;k<blocks;k++){c.x[k]=x[k]^b.x[k];c.z[k]=z[k]^b.z[k];}return c; }
    bool anti(const P& b) const {uint64_t t=0;for(int k=0;k<blocks;k++)t^=(x[k]&b.z[k])^(z[k]&b.x[k]);return __builtin_parityll(t);}
    int weight() const {int w=0;for(int k=0;k<blocks;k++)w+=__builtin_popcountll(x[k]|z[k]);return w;}
    int at(int q) const {return ((x[q/64]>>(q%64))&1)+2*((z[q/64]>>(q%64))&1);}
    void set(int q,int a){uint64_t bit=1ULL<<(q%64);x[q/64]=(x[q/64]&~bit)|((a&1)?bit:0);z[q/64]=(z[q/64]&~bit)|((a&2)?bit:0);}
};
int main(){
    int n,target,T,adaptive;long long steps;uint64_t seed;
    cin>>n>>target>>steps>>seed>>adaptive; if(n<1||n>64*PAULI_BLOCKS)return 2;blocks=(n+63)/64;
    vector<P> ops(2*n);string s;for(auto& p:ops){cin>>s;if(s.size()!=n)return 3;for(int q=0;q<n;q++)p.set(q,s[q]=='X'?1:s[q]=='Z'?2:s[q]=='Y'?3:0);}
    cin>>T;vector<vector<int>> terms(T),involved(2*n);
    for(int t=0;t<T;t++){int k;cin>>k;while(k--){int a;cin>>a;terms[t].push_back(a);involved[a].push_back(t);}}
    auto product=[&](int t){P p;for(int a:terms[t])p=p^ops[a];return p;};
    vector<P> rows(T);vector<int>w(T);for(int t=0;t<T;t++){rows[t]=product(t);w[t]=rows[t].weight();}
    auto score=[&](){int pen=0,bad=0,mx=0,total=0;for(int v:w){pen+=max(0,v-target)*max(0,v-target);bad+=v>target;mx=max(mx,v);total+=v;}return make_tuple(pen,bad,mx,total);};
    auto best=score();vector<P> bestops=ops;
    mt19937_64 rng(seed);auto pick=[&](int m){return int(rng()%m);};auto unit=[&](){return (rng()>>11)*0x1.0p-53;};
    vector<double>lambda(T,1.0);vector<int>bad;
    auto loss=[&](int t,int v){double ex=max(0,v-target);return lambda[t]*ex*ex+0.00002*v;};
    long long beststep=0;
    cerr<<"initial "<<get<0>(best)<<" "<<get<1>(best)<<" "<<get<2>(best)<<" "<<get<3>(best)<<endl;
    for(long long it=0;it<steps && get<0>(best)>0;it++){
        bad.clear();for(int t=0;t<T;t++)if(w[t]>target)bad.push_back(t);
        int t=bad.empty()?pick(T):bad[pick(bad.size())];
        int a=-1,b=-1;P axis; vector<int>affected;vector<P>changed;vector<int>nw;
        vector<pair<int,int>> swaps;vector<P> axes;
        bool swapmove=pick(100)<75;
        if(swapmove){
            int length=(adaptive>1 && unit()<0.25)?2+pick(3):1;
            for(int j=0;j<length;j++){
                a=unit()<0.90?terms[t][pick(terms[t].size())]:pick(2*n);b=pick(2*n);if(a==b)continue;
                swaps.push_back({a,b});swap(ops[a],ops[b]);
                affected.insert(affected.end(),involved[a].begin(),involved[a].end());affected.insert(affected.end(),involved[b].begin(),involved[b].end());
            }
            if(swaps.empty())continue;
            sort(affected.begin(),affected.end());affected.erase(unique(affected.begin(),affected.end()),affected.end());
            for(int u:affected)changed.push_back(product(u));
        }else{
            int kind=pick(100);
            if(adaptive>=4 && unit()<0.50){
                // Even Majorana products commute with every generator outside
                // their selected labels. Quartet moves change only four columns.
                int first=terms[t][pick(terms[t].size())];
                int second=unit()<0.5?terms[t][pick(terms[t].size())]:pick(2*n);
                int third=pick(2*n);
                int fourth=unit()<0.5?(third^1):pick(2*n);
                axis=ops[first]^ops[second]^ops[third]^ops[fourth];
            }else if(kind<65){
                // Cancel a chosen subset of the offending support, and use
                // one differing local label to force anticommutation.
                vector<int>support;for(int q=0;q<n;q++)if(rows[t].at(q))support.push_back(q);
                shuffle(support.begin(),support.end(),rng);int k=1+pick(support.size());
                for(int j=0;j<k;j++)axis.set(support[j],rows[t].at(support[j]));
                int q=support[0],v=rows[t].at(q);axis.set(q,1+(v+pick(2))%3);
                if(unit()<0.12)axis.set(pick(n),1+pick(3));
            }else if(kind<90){int k=2+pick(4);for(int j=0;j<k;j++)axis.set(pick(n),1+pick(3));
            }else if(kind<98){axis=rows[t]^rows[pick(T)];if(unit()<0.5)axis.set(pick(n),1+pick(3));
            }else{
                // Swap one Majorana with the omitted chirality generator.
                for(auto p:ops)axis=axis^p;axis=axis^ops[pick(2*n)];
            }
            axes.push_back(axis);
            if(adaptive>=3 && unit()<0.30){
                P transformed=rows[t].anti(axis)?rows[t]^axis:rows[t];
                vector<int>support;for(int q=0;q<n;q++)if(transformed.at(q))support.push_back(q);
                if(!support.empty()){
                    shuffle(support.begin(),support.end(),rng);P axis2;
                    int k=1+pick(support.size());for(int j=0;j<k;j++)axis2.set(support[j],transformed.at(support[j]));
                    int q=support[0],v=transformed.at(q);axis2.set(q,1+(v+pick(2))%3);
                    axes.push_back(axis2);
                }
            }
            for(int u=0;u<T;u++){
                P p=rows[u];for(auto ax:axes)if(p.anti(ax))p=p^ax;
                if(p.x!=rows[u].x||p.z!=rows[u].z){affected.push_back(u);changed.push_back(p);}
            }
        }
        double delta=0;for(int j=0;j<affected.size();j++){int u=affected[j],v=changed[j].weight();nw.push_back(v);delta+=loss(u,v)-loss(u,w[u]);}
        double phase=(it%100000)/99999.0;
        double temp=0.75*pow(0.006/0.75,phase);
        bool accept=delta<=0 || unit()<exp(-delta/temp);
        if(accept){
            for(int j=0;j<affected.size();j++){rows[affected[j]]=changed[j];w[affected[j]]=nw[j];}
            if(!swapmove)for(auto ax:axes)for(auto& p:ops)if(p.anti(ax))p=p^ax;
            auto sc=score();if(sc<best){best=sc;bestops=ops;beststep=it;cerr<<"best "<<it<<" "<<get<0>(best)<<" "<<get<1>(best)<<" "<<get<2>(best)<<" "<<get<3>(best)<<endl;}
        }else if(swapmove)for(auto it=swaps.rbegin();it!=swaps.rend();++it)swap(ops[it->first],ops[it->second]);
        if((it+1)%10000==0){
            // Different constraints acquire pressure as they remain unsatisfied.
            if(adaptive)for(int u=0;u<T;u++)lambda[u]=1+0.98*(lambda[u]-1)+(w[u]>target?0.3:0);
            for(int u=0;u<T;u++){auto p=product(u);if(p.x!=rows[u].x||p.z!=rows[u].z||p.weight()!=w[u])throw runtime_error("cache mismatch");}
        }
        if((it+1)%1000000==0){cerr<<"checkpoint "<<it+1<<" bestpen="<<get<0>(best)<<" lastbest="<<beststep<<endl;
            if(it-beststep>500000){ops=bestops;for(int u=0;u<T;u++){rows[u]=product(u);w[u]=rows[u].weight();}fill(lambda.begin(),lambda.end(),1.0);}
        }
    }
    for(auto p:bestops){for(int q=0;q<n;q++)cout<<"IXZY"[p.at(q)];cout<<'\n';}
    cerr<<"final "<<get<0>(best)<<" "<<get<1>(best)<<" "<<get<2>(best)<<" "<<get<3>(best)<<endl;
}
'''

def weights(mapping, terms):
    packed = []
    for s in mapping['majoranas']:
        x, z = string_to_xz(s)
        packed.append((sum(int(b) << q for q, b in enumerate(x)),
                       sum(int(b) << q for q, b in enumerate(z))))
    answer = []
    for term in terms:
        x = z = 0
        for a in term:
            px, pz = packed[a]
            x ^= px
            z ^= pz
        answer.append((x | z).bit_count())
    return answer


@functools.lru_cache(maxsize=None)
def _build_native(block_capacity):
    """Compile once per capacity and module lifetime, entirely in a temp folder."""
    compiler = (shutil.which("clang++") or shutil.which("g++")
                or shutil.which("c++"))
    if compiler is None:
        raise RuntimeError("This submission needs a C++17 compiler: clang++ or g++.")
    workspace = tempfile.TemporaryDirectory(prefix="fermion-targeted-")
    folder = Path(workspace.name)
    source = folder / "search.cpp"
    executable = folder / "search"
    source.write_text(_NATIVE_SOURCE)
    command = [compiler, "-O3", "-std=c++17",
               f"-DPAULI_BLOCKS={block_capacity}", str(source), "-o", str(executable)]
    compiled = subprocess.run(command, text=True, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, timeout=120)
    if compiled.returncode:
        workspace.cleanup()
        raise RuntimeError("C++ compilation failed:\n" + compiled.stderr[-8000:])
    # Keeping the TemporaryDirectory alive retains the executable for later sizes.
    return workspace, executable


def native_search(spec, mapping, terms, target, seed, steps, adaptive=1):
    _, executable = _build_native(max(4, (spec["M"] + 63) // 64))
    lines = [f"{spec['M']} {target} {steps} {seed} {adaptive}",
             *mapping["majoranas"], str(len(terms))]
    lines += [" ".join(map(str, [len(t), *t])) for t in terms]
    run = subprocess.run([str(executable)], input="\n".join(lines) + "\n",
                         text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if run.returncode:
        raise RuntimeError(f"Native search failed ({run.returncode}):\n"
                           + run.stderr[-8000:])
    strings = run.stdout.splitlines()
    if (len(strings) != 2 * spec["M"]
            or any(len(s) != spec["M"] or set(s) - set("IXYZ") for s in strings)):
        raise RuntimeError("Native search returned malformed Majoranas.")
    return dict(n_qubits=spec["M"], majoranas=strings, stabilizers=[])

def encode(spec):
    """Same proposal budget formula, restart seeds and rule at every size."""
    terms = hamiltonian(spec, model='full')
    best = _seed_encode(spec)
    ww = weights(best, terms)
    best_key = max(ww), sum(ww)
    frontier = best
    target = best_key[0] - 1
    steps = max(100_000, int(5_000_000 * 637 / len(terms)))
    # A failed target retains its best partial candidate for the next restart.
    # Only a mapping no worse in actual (max,total) may be returned.
    for seed in (101, 103, 107, 109):
        if target < 1:
            break
        frontier = native_search(spec, frontier, terms, target, seed, steps)
        ww = weights(frontier, terms)
        key = max(ww), sum(ww)
        if key < best_key:
            best, best_key = frontier, key
        if key[0] <= target:
            target = key[0] - 1
    return best
