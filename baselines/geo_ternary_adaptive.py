"""Geometry-adaptive ternary-tree encoding, submitted for 7x7."""

import numpy as np


def encode(spec: dict) -> dict:
    m = spec["M"]
    coords, edges = spec["coords"], spec["edges"]
    terms = []
    for i, j in edges:
        terms += [(2*i, 2*j+1), (2*i+1, 2*j), (2*i, 2*j), (2*i+1, 2*j+1)]
    for i in range(m):
        terms.append((2*i, 2*i+1))
    for i, j in edges:
        terms += [(2*i, 2*i+1), (2*j, 2*j+1), (2*i, 2*i+1, 2*j, 2*j+1)]

    def pack(x, z):
        xi = zi = 0
        for q, (xb, zb) in enumerate(zip(x, z)):
            xi |= int(xb) << q
            zi |= int(zb) << q
        return xi, zi

    def spatial_order():
        def visit(sites):
            if len(sites) < 2:
                return list(sites)
            xs = [coords[i][0] for i in sites]
            ys = [coords[i][1] for i in sites]
            axis = 0 if max(xs) - min(xs) >= max(ys) - min(ys) else 1
            sites = sorted(sites, key=lambda i: coords[i][axis])
            base, rem = divmod(len(sites), 3)
            out, start = [], 0
            for child in range(3):
                size = base + (child < rem)
                out.extend(visit(sites[start:start + size]))
                start += size
            return out
        return visit(sorted(coords))

    def heap_pairs():
        def leaf(leaf_index):
            x, z = np.zeros(m, dtype=np.uint8), np.zeros(m, dtype=np.uint8)
            node = leaf_index
            while node:
                parent, label = (node - 1) // 3, (node - 1) % 3
                if label in (0, 1): x[parent] = 1
                if label in (1, 2): z[parent] = 1
                node = parent
            return x, z
        return [(leaf(a), leaf(a + 1)) for a in range(m, 3*m, 2)]

    def geometry_pairs(fraction):
        leaves, next_router = [], 0
        def visit(sites, x, z):
            nonlocal next_router
            if not sites:
                leaves.append((x, z)); return
            router, next_router = next_router, next_router + 1
            xs = [coords[i][0] for i in sites]
            ys = [coords[i][1] for i in sites]
            axis = 0 if max(xs) - min(xs) >= max(ys) - min(ys) else 1
            ordered = sorted(sites, key=lambda i: (coords[i][axis], coords[i][1-axis]))
            pivot = min(len(ordered)-1, int(fraction * len(ordered)))
            rest = ordered[:pivot] + ordered[pivot+1:]
            base, rem = divmod(len(rest), 3)
            start = 0
            for child in range(3):
                size = base + (child < rem)
                cx, cz = x.copy(), z.copy()
                if child in (0, 1): cx[router] = 1
                if child in (1, 2): cz[router] = 1
                visit(rest[start:start+size], cx, cz)
                start += size
        visit(sorted(coords), np.zeros(m, dtype=np.uint8), np.zeros(m, dtype=np.uint8))
        return [(leaves[2*k], leaves[2*k+1]) for k in range(m)]

    def anneal_pairs(pairs, start_order, seed):
        slots = [(pack(*a), pack(*b)) for a, b in pairs]
        pos = [0] * m
        for slot, mode in enumerate(start_order): pos[mode] = slot
        involved = [[] for _ in range(m)]
        for ti, term in enumerate(terms):
            for mode in {v >> 1 for v in term}: involved[mode].append(ti)
        def weight(term):
            x = z = 0
            for majorana in term:
                a, b = slots[pos[majorana >> 1]][majorana & 1]
                x ^= a; z ^= b
            return (x | z).bit_count()
        weights = [weight(term) for term in terms]
        total = sum(weights); best_total, best_pos = total, list(pos)
        rng = np.random.default_rng(seed)
        steps = max(100_000, 2_500*m)
        hot, cold = max(1.0, total*.2), max(.01, total*.0001)
        for step in range(steps):
            left, right = (int(v) for v in rng.choice(m, 2, replace=False))
            temperature = hot * (cold/hot) ** (step/steps)
            pos[left], pos[right] = pos[right], pos[left]
            changed, delta = {}, 0
            for ti in set(involved[left]) | set(involved[right]):
                nw = weight(terms[ti]); changed[ti] = nw; delta += nw - weights[ti]
            if delta <= 0 or rng.random() < np.exp(-delta/temperature):
                total += delta
                for ti, nw in changed.items(): weights[ti] = nw
                if total < best_total: best_total, best_pos = total, list(pos)
            else:
                pos[left], pos[right] = pos[right], pos[left]
        out = [None] * m
        for mode, slot in enumerate(best_pos): out[slot] = mode
        return out, best_total

    initial = spatial_order()
    candidates = [heap_pairs(), geometry_pairs(1/3), geometry_pairs(1/2), geometry_pairs(2/3)]
    pairs, order, score = candidates[0], None, None
    for candidate_index, candidate in enumerate(candidates):
        runs = range(5) if candidate_index == 0 else range(1)
        for run in runs:
            seed = m + run if candidate_index == 0 else 31*m + len(candidates)
            candidate_order, candidate_score = anneal_pairs(candidate, initial, seed)
            if score is None or candidate_score < score:
                pairs, order, score = candidate, candidate_order, candidate_score

    leaves = [pack(*operator) for pair in pairs for operator in pair]
    assignment = [None] * (2*m)
    for slot, mode in enumerate(order): assignment[2*mode], assignment[2*mode+1] = 2*slot, 2*slot+1
    involved = [[] for _ in range(2*m)]
    for ti, term in enumerate(terms):
        for majorana in term: involved[majorana].append(ti)
    def leaf_weight(term):
        x = z = 0
        for majorana in term:
            a, b = leaves[assignment[majorana]]
            x ^= a; z ^= b
        return (x | z).bit_count()
    weights = [leaf_weight(term) for term in terms]
    total = sum(weights); best_total, best_assignment = total, list(assignment)
    rng = np.random.default_rng(1_009*m + 7)
    hot, cold = max(1.0, total*.15), max(.01, total*.0001)
    for step in range(100_000):
        left, right = (int(v) for v in rng.choice(2*m, 2, replace=False))
        temperature = hot * (cold/hot) ** (step/100_000)
        assignment[left], assignment[right] = assignment[right], assignment[left]
        changed, delta = {}, 0
        for ti in set(involved[left]) | set(involved[right]):
            nw = leaf_weight(terms[ti]); changed[ti] = nw; delta += nw - weights[ti]
        if delta <= 0 or rng.random() < np.exp(-delta/temperature):
            total += delta
            for ti, nw in changed.items(): weights[ti] = nw
            if total < best_total: best_total, best_assignment = total, list(assignment)
        else:
            assignment[left], assignment[right] = assignment[right], assignment[left]

    def pauli(x, z):
        return "".join("Y" if (x>>q)&1 and (z>>q)&1 else "X" if (x>>q)&1 else "Z" if (z>>q)&1 else "I" for q in range(m))
    return {"n_qubits": m, "majoranas": [pauli(*leaves[k]) for k in best_assignment], "stabilizers": []}
