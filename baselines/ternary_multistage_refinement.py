"""Ternary mapping with a uniform multistage Clifford refiner."""

import itertools
import math
import random

import numpy as np


_AXES = (1, 2, 3)  # X, Z, Y in x | (z << 1) local coding.


def _delta_table():
    table = np.zeros((16, 9), dtype=np.int16)
    for local in range(16):
        left_code, right_code = divmod(local, 4)
        for axis_index, (left_axis, right_axis) in enumerate(
            (a, b) for a in _AXES for b in _AXES
        ):
            anti = ((left_code != 0) and (left_code != left_axis)) ^ (
                (right_code != 0) and (right_code != right_axis)
            )
            if anti:
                table[local, axis_index] = (
                    int((left_code ^ left_axis) != 0)
                    - int(left_code != 0)
                    + int((right_code ^ right_axis) != 0)
                    - int(right_code != 0)
                )
    return table


_DELTA_TABLE = _delta_table()

# Stable representatives of the ten distinct two-qubit support actions of
# Sp(4, 2).  A pattern is code(left) + 4*code(right).
_BLOCK_MAPS = np.asarray(
    [
        (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15),
        (0, 1, 6, 7, 4, 5, 2, 3, 9, 8, 15, 14, 13, 12, 11, 10),
        (0, 1, 6, 7, 9, 8, 15, 14, 4, 5, 2, 3, 13, 12, 11, 10),
        (0, 1, 6, 7, 9, 8, 15, 14, 13, 12, 11, 10, 4, 5, 2, 3),
        (0, 5, 2, 7, 4, 1, 6, 3, 10, 15, 8, 13, 14, 11, 12, 9),
        (0, 5, 2, 7, 10, 15, 8, 13, 4, 1, 6, 3, 14, 11, 12, 9),
        (0, 5, 2, 7, 10, 15, 8, 13, 14, 11, 12, 9, 4, 1, 6, 3),
        (0, 5, 6, 3, 4, 1, 2, 7, 11, 14, 13, 8, 15, 10, 9, 12),
        (0, 5, 6, 3, 11, 14, 13, 8, 4, 1, 2, 7, 15, 10, 9, 12),
        (0, 5, 6, 3, 11, 14, 13, 8, 15, 10, 9, 12, 4, 1, 2, 7),
    ],
    dtype=np.uint8,
)
_BLOCK_PROFILES = np.asarray(
    [
        (0, 1, 1, 1, 1, 2, 2, 2, 1, 2, 2, 2, 1, 2, 2, 2),
        (0, 1, 2, 2, 1, 2, 1, 1, 2, 1, 2, 2, 2, 1, 2, 2),
        (0, 1, 2, 2, 2, 1, 2, 2, 1, 2, 1, 1, 2, 1, 2, 2),
        (0, 1, 2, 2, 2, 1, 2, 2, 2, 1, 2, 2, 1, 2, 1, 1),
        (0, 2, 1, 2, 1, 1, 2, 1, 2, 2, 1, 2, 2, 2, 1, 2),
        (0, 2, 1, 2, 2, 2, 1, 2, 1, 1, 2, 1, 2, 2, 1, 2),
        (0, 2, 1, 2, 2, 2, 1, 2, 2, 2, 1, 2, 1, 1, 2, 1),
        (0, 2, 2, 1, 1, 1, 1, 2, 2, 2, 2, 1, 2, 2, 2, 1),
        (0, 2, 2, 1, 2, 2, 2, 1, 1, 1, 1, 2, 2, 2, 2, 1),
        (0, 2, 2, 1, 2, 2, 2, 1, 2, 2, 2, 1, 1, 1, 1, 2),
    ],
    dtype=np.int16,
)
_LOCAL_WEIGHTS = np.asarray(
    [int(bool(pattern & 3)) + int(bool(pattern & 12)) for pattern in range(16)],
    dtype=np.int16,
)


def _codes_from_operators(operators, n_qubits):
    codes = np.zeros((len(operators), n_qubits), dtype=np.uint8)
    for row, (x, z) in enumerate(operators):
        for qubit in range(n_qubits):
            codes[row, qubit] = ((x >> qubit) & 1) | (
                ((z >> qubit) & 1) << 1
            )
    return codes


def _operators_from_codes(codes):
    operators = []
    for row in codes:
        x = z = 0
        for qubit, code in enumerate(row):
            x |= (int(code) & 1) << qubit
            z |= ((int(code) >> 1) & 1) << qubit
        operators.append((x, z))
    return operators


def _products_from_codes(operator_codes, terms):
    products = np.zeros(
        (len(terms), operator_codes.shape[1]), dtype=np.uint8
    )
    for term_index, term in enumerate(terms):
        for majorana in term:
            products[term_index] ^= operator_codes[majorana]
    return products


def _score_operators(operators, terms, n_qubits):
    products = _products_from_codes(
        _codes_from_operators(operators, n_qubits), terms
    )
    weights = np.count_nonzero(products, axis=1)
    return int(weights.sum()), int(weights.max())


def _transform_operators(operators, pauli):
    px, pz = pauli
    transformed = []
    for x, z in operators:
        if ((x & pz).bit_count() + (z & px).bit_count()) & 1:
            transformed.append((x ^ px, z ^ pz))
        else:
            transformed.append((x, z))
    return transformed


def _ancestor_pairs(parents, radius=2):
    pairs = set()
    for descendant in range(len(parents)):
        ancestor = parents[descendant]
        for _ in range(radius):
            if ancestor is None:
                break
            pairs.add(tuple(sorted((ancestor, descendant))))
            ancestor = parents[ancestor]
    return sorted(pairs)


def _local_barrier_once(products, pairs, cap):
    """One deterministic width-64, depth-12 bounded beam search."""
    left = np.asarray([pair[0] for pair in pairs], dtype=np.intp)
    right = np.asarray([pair[1] for pair in pairs], dtype=np.intp)
    offsets = (16 * np.arange(len(pairs), dtype=np.int32))[None, :]
    weights = np.count_nonzero(products, axis=1).astype(np.int16)
    start = (
        products.copy(),
        weights,
        int(weights.sum()),
        int(weights.max()),
        (),
        tuple(products[:, q].tobytes() for q in range(products.shape[1])),
    )

    def decode(move_index):
        pair_index, axis_index = divmod(move_index, 9)
        left_axis, right_axis = divmod(axis_index, 3)
        return (
            int(left[pair_index]),
            int(right[pair_index]),
            _AXES[left_axis],
            _AXES[right_axis],
        )

    def effect(state, move_index):
        qleft, qright, left_axis, right_axis = decode(move_index)
        ql, qr = state[0][:, qleft], state[0][:, qright]
        anti = ((ql != 0) & (ql != left_axis)) ^ (
            (qr != 0) & (qr != right_axis)
        )
        local_delta = (
            ((ql ^ left_axis) != 0).astype(np.int16)
            - (ql != 0).astype(np.int16)
            + ((qr ^ right_axis) != 0).astype(np.int16)
            - (qr != 0).astype(np.int16)
        )
        delta_weights = np.where(anti, local_delta, 0).astype(np.int16)
        return anti, delta_weights, int(np.max(state[1] + delta_weights))

    def total_deltas(state):
        local = (
            state[0][:, left].astype(np.int32) * 4
            + state[0][:, right]
            + offsets
        )
        histograms = np.bincount(
            local.ravel(), minlength=16 * len(pairs)
        ).reshape(len(pairs), 16)
        return (histograms @ _DELTA_TABLE).reshape(-1)

    def signature(state, move_index):
        anti, _, _ = effect(state, move_index)
        qleft, qright, left_axis, right_axis = decode(move_index)
        left_column = state[0][:, qleft].copy()
        right_column = state[0][:, qright].copy()
        left_column[anti] ^= left_axis
        right_column[anti] ^= right_axis
        columns = list(state[5])
        columns[qleft] = left_column.tobytes()
        columns[qright] = right_column.tobytes()
        return tuple(columns)

    beam = [start]
    best = start
    seen = {start[5]}
    for _ in range(12):
        edges = []
        for parent_index, state in enumerate(beam):
            deltas = total_deltas(state)
            previous = state[4][-1] if state[4] else -1
            candidates = []
            for raw_index in np.flatnonzero(deltas <= 4):
                move_index = int(raw_index)
                if move_index == previous:
                    continue
                _, _, maximum = effect(state, move_index)
                if maximum > cap:
                    continue
                path = state[4] + (move_index,)
                candidates.append(
                    (
                        state[2] + int(deltas[move_index]),
                        maximum,
                        path,
                        parent_index,
                        move_index,
                    )
                )
            candidates.sort(key=lambda edge: edge[:3])
            for edge in candidates[:32]:
                child_signature = signature(state, edge[4])
                if child_signature in seen:
                    continue
                seen.add(child_signature)
                edges.append(edge + (child_signature,))
        edges.sort(key=lambda edge: edge[:3])
        next_beam = []
        for edge in edges[:64]:
            total, maximum, path, parent_index, move_index, child_signature = edge
            parent = beam[parent_index]
            anti, delta_weights, checked_maximum = effect(parent, move_index)
            if maximum != checked_maximum:
                raise AssertionError("inconsistent local beam maximum")
            child_products = parent[0].copy()
            qleft, qright, left_axis, right_axis = decode(move_index)
            child_products[anti, qleft] ^= left_axis
            child_products[anti, qright] ^= right_axis
            child_weights = parent[1] + delta_weights
            child = (
                child_products,
                child_weights,
                total,
                maximum,
                path,
                child_signature,
            )
            next_beam.append(child)
            if (child[2], child[3], child[4]) < (best[2], best[3], best[4]):
                best = child
        if not next_beam:
            break
        beam = next_beam
    return best, decode


def _local_barrier_refine(operators, terms, parents, cap):
    pairs = _ancestor_pairs(parents, 2)
    current = list(operators)
    for _ in range(8):
        codes = _codes_from_operators(current, len(parents))
        products = _products_from_codes(codes, terms)
        start_total = int(np.count_nonzero(products, axis=1).sum())
        best, decode = _local_barrier_once(products, pairs, cap)
        if best[2] >= start_total:
            break
        for move_index in best[4]:
            left, right, left_axis, right_axis = decode(move_index)
            px = ((left_axis & 1) << left) | ((right_axis & 1) << right)
            pz = (((left_axis >> 1) & 1) << left) | (
                ((right_axis >> 1) & 1) << right
            )
            current = _transform_operators(current, (px, pz))
    return current


def _tree_distance_pairs(parents, radius=2):
    adjacency = [set() for _ in parents]
    for child, parent in enumerate(parents):
        if parent is not None:
            adjacency[child].add(parent)
            adjacency[parent].add(child)
    pairs = set()
    for source in range(len(parents)):
        seen = {source}
        frontier = {source}
        for _ in range(radius):
            frontier = {
                neighbor
                for vertex in frontier
                for neighbor in adjacency[vertex]
                if neighbor not in seen
            }
            seen.update(frontier)
            for target in frontier:
                pairs.add(tuple(sorted((source, target))))
    return sorted(pairs)


def _block_refine(operators, terms, parents, cap):
    """Arbitrary radius-two two-qubit Clifford block refinement."""
    operator_codes = _codes_from_operators(operators, len(parents))
    products = _products_from_codes(operator_codes, terms)
    weights = np.count_nonzero(products, axis=1).astype(np.int16)
    pairs = _tree_distance_pairs(parents, 2)
    left = np.asarray([pair[0] for pair in pairs], dtype=np.intp)
    right = np.asarray([pair[1] for pair in pairs], dtype=np.intp)
    offsets = 16 * np.arange(len(pairs), dtype=np.int32)
    profile_delta = _BLOCK_PROFILES - _LOCAL_WEIGHTS
    trivial = np.all(_BLOCK_PROFILES == _LOCAL_WEIGHTS, axis=1)

    def score(state_products, state_weights):
        patterns = (
            state_products[:, left] + 4 * state_products[:, right]
        ).astype(np.int16)
        indexed = patterns.astype(np.int32) + offsets[None, :]
        histograms = np.bincount(
            indexed.ravel(), minlength=16 * len(pairs)
        ).reshape(len(pairs), 16)
        deltas = histograms @ profile_delta.T
        outside = state_weights[:, None] - _LOCAL_WEIGHTS[patterns]
        max_outside = np.full(16 * len(pairs), -100, dtype=np.int16)
        np.maximum.at(max_outside, indexed.ravel(), outside.ravel())
        max_outside = max_outside.reshape(len(pairs), 16)
        maxima = np.max(
            max_outside[:, None, :] + _BLOCK_PROFILES[None, :, :], axis=2
        )
        return deltas.astype(np.int32), maxima.astype(np.int16)

    def moves(state_products, state_weights, delta_max, exclude_trivial=False):
        deltas, maxima = score(state_products, state_weights)
        valid = (maxima <= cap) & (deltas <= delta_max)
        if exclude_trivial:
            valid &= ~(trivial[None, :] & (deltas == 0))
        pair_indices, profile_indices = np.nonzero(valid)
        result = [
            (
                int(deltas[pair_index, profile_index]),
                int(pair_index),
                int(profile_index),
            )
            for pair_index, profile_index in zip(pair_indices, profile_indices)
        ]
        result.sort()
        return result

    def apply(state_operators, state_products, pair_index, profile_index):
        qleft, qright = pairs[pair_index]
        permutation = _BLOCK_MAPS[profile_index]
        for codes in (state_operators, state_products):
            patterns = codes[:, qleft] + 4 * codes[:, qright]
            output = permutation[patterns]
            codes[:, qleft] = output & 3
            codes[:, qright] = output >> 2
        state_weights = np.count_nonzero(state_products, axis=1).astype(np.int16)
        return state_weights

    def plateau_descent():
        nonlocal weights, operator_codes, products
        for _ in range(100):
            improving = moves(products, weights, -1)
            if improving:
                _, pair_index, profile_index = improving[0]
                weights = apply(
                    operator_codes, products, pair_index, profile_index
                )
                continue
            neutral = [
                move
                for move in moves(products, weights, 0, True)
                if move[0] == 0
            ]
            escape = None
            for _, first_pair, first_profile in neutral:
                successor_operators = operator_codes.copy()
                successor_products = products.copy()
                successor_weights = apply(
                    successor_operators,
                    successor_products,
                    first_pair,
                    first_profile,
                )
                exits = moves(successor_products, successor_weights, -1)
                if exits:
                    second_delta, second_pair, second_profile = exits[0]
                    key = (
                        second_delta,
                        first_pair,
                        first_profile,
                        second_pair,
                        second_profile,
                    )
                    if escape is None or key < escape[0]:
                        escape = (
                            key,
                            successor_operators,
                            successor_products,
                            successor_weights,
                        )
            if escape is None:
                return
            key, operator_codes, products, weights = escape
            _, _, _, second_pair, second_profile = key
            weights = apply(
                operator_codes, products, second_pair, second_profile
            )

    def barrier_descent(barrier):
        nonlocal weights, operator_codes, products
        for _ in range(100):
            improving = moves(products, weights, -1)
            if improving:
                _, pair_index, profile_index = improving[0]
                weights = apply(
                    operator_codes, products, pair_index, profile_index
                )
                continue
            first_moves = moves(products, weights, barrier, True)
            escape = None
            for first_delta, first_pair, first_profile in first_moves:
                if first_delta < 0:
                    continue
                successor_operators = operator_codes.copy()
                successor_products = products.copy()
                successor_weights = apply(
                    successor_operators,
                    successor_products,
                    first_pair,
                    first_profile,
                )
                for second_delta, second_pair, second_profile in moves(
                    successor_products, successor_weights, -1
                ):
                    net_delta = first_delta + second_delta
                    if net_delta >= 0:
                        continue
                    key = (
                        net_delta,
                        first_delta,
                        first_pair,
                        first_profile,
                        second_pair,
                        second_profile,
                    )
                    if escape is None or key < escape[0]:
                        escape = (
                            key,
                            successor_operators,
                            successor_products,
                            successor_weights,
                        )
            if escape is None:
                return
            key, operator_codes, products, weights = escape
            _, _, _, _, second_pair, second_profile = key
            weights = apply(
                operator_codes, products, second_pair, second_profile
            )

    plateau_descent()
    barrier_descent(2)
    barrier_descent(4)
    return _operators_from_codes(operator_codes)


def _majorana_swap_refine(operators, terms, coords, cap, beam_width=200):
    """Best single swaps followed by exact depth-two radius-three exits."""
    operators = list(operators)
    involved = [[] for _ in operators]
    for term_index, term in enumerate(terms):
        for majorana in term:
            involved[majorana].append(term_index)

    def term_weight(term):
        x = z = 0
        for majorana in term:
            ox, oz = operators[majorana]
            x ^= ox
            z ^= oz
        return (x | z).bit_count()

    weights = [term_weight(term) for term in terms]
    total = sum(weights)
    pairs = []
    for left in range(len(operators) - 1):
        lx, ly = coords[left >> 1]
        for right in range(left + 1, len(operators)):
            rx, ry = coords[right >> 1]
            if abs(lx - rx) + abs(ly - ry) <= 3:
                pairs.append((left, right))

    def proposal(left, right):
        operators[left], operators[right] = operators[right], operators[left]
        changed, delta, affected_max = {}, 0, 0
        for term_index in set(involved[left]) | set(involved[right]):
            new_weight = term_weight(terms[term_index])
            changed[term_index] = new_weight
            delta += new_weight - weights[term_index]
            affected_max = max(affected_max, new_weight)
        operators[left], operators[right] = operators[right], operators[left]
        return delta, affected_max, changed

    def apply(left, right, delta, changed):
        nonlocal total
        operators[left], operators[right] = operators[right], operators[left]
        total += delta
        for term_index, new_weight in changed.items():
            weights[term_index] = new_weight

    while True:
        best = None
        for left, right in pairs:
            delta, affected_max, changed = proposal(left, right)
            if delta < 0 and affected_max <= cap:
                key = (delta, left, right)
                if best is None or key < best[0]:
                    best = (key, left, right, delta, changed)
        if best is None:
            break
        _, left, right, delta, changed = best
        apply(left, right, delta, changed)

    while True:
        first_moves = []
        for left, right in pairs:
            delta, _, changed = proposal(left, right)
            first_moves.append((delta, left, right, changed))
        first_moves.sort(key=lambda item: item[0])
        best = None
        base_total = total
        for first_delta, first_left, first_right, first_changed in first_moves[
            :beam_width
        ]:
            apply(first_left, first_right, first_delta, first_changed)
            overweight = {
                index for index, weight in enumerate(weights) if weight > cap
            }
            for second_left, second_right in pairs:
                second_delta, affected_max, second_changed = proposal(
                    second_left, second_right
                )
                candidate_total = total + second_delta
                if candidate_total >= base_total or affected_max > cap:
                    continue
                if not overweight.issubset(second_changed):
                    continue
                key = (candidate_total, first_delta + second_delta)
                if best is None or key < best[0]:
                    best = (
                        key,
                        first_left,
                        first_right,
                        first_delta,
                        dict(first_changed),
                        second_left,
                        second_right,
                    )
            undo_delta, _, undo_changed = proposal(first_left, first_right)
            apply(first_left, first_right, undo_delta, undo_changed)
            if total != base_total:
                raise AssertionError("Majorana-swap rollback failed")
        if best is None:
            break
        (
            _,
            first_left,
            first_right,
            first_delta,
            first_changed,
            second_left,
            second_right,
        ) = best
        apply(first_left, first_right, first_delta, first_changed)
        second_delta, _, second_changed = proposal(second_left, second_right)
        apply(second_left, second_right, second_delta, second_changed)
    return operators


def _logical_weight_four_refine(operators, terms, coords, cap):
    """Descent in radius-three weight-four logical transvections."""
    operators = list(operators)
    products = []
    for term in terms:
        x = z = 0
        for majorana in term:
            ox, oz = operators[majorana]
            x ^= ox
            z ^= oz
        products.append((x, z))
    weights = [(x | z).bit_count() for x, z in products]
    involved = [set() for _ in operators]
    for term_index, term in enumerate(terms):
        for majorana in term:
            involved[majorana].add(term_index)

    def candidates():
        for anchor in range(len(operators)):
            ax, ay = coords[anchor >> 1]
            eligible = [
                index
                for index in range(anchor + 1, len(operators))
                if abs(coords[index >> 1][0] - ax)
                + abs(coords[index >> 1][1] - ay)
                <= 3
            ]
            for rest in itertools.combinations(eligible, 3):
                subset = (anchor, *rest)
                sites = [coords[index >> 1] for index in subset]
                if all(
                    abs(a[0] - b[0]) + abs(a[1] - b[1]) <= 3
                    for a, b in itertools.combinations(sites, 2)
                ):
                    yield subset

    for _ in range(20):
        best = None
        for subset in candidates():
            px = pz = 0
            affected = set()
            for majorana in subset:
                ox, oz = operators[majorana]
                px ^= ox
                pz ^= oz
                affected.symmetric_difference_update(involved[majorana])
            delta = 0
            feasible = True
            for term_index in affected:
                x, z = products[term_index]
                new_weight = ((x ^ px) | (z ^ pz)).bit_count()
                if new_weight > cap:
                    feasible = False
                    break
                delta += new_weight - weights[term_index]
            if feasible and delta < 0:
                key = (delta, subset)
                if best is None or key < best[0]:
                    best = (key, subset, (px, pz), affected)
        if best is None:
            break
        (delta, _), subset, (px, pz), affected = best
        for majorana in subset:
            x, z = operators[majorana]
            operators[majorana] = x ^ px, z ^ pz
        for term_index in affected:
            x, z = products[term_index]
            products[term_index] = x ^ px, z ^ pz
            weights[term_index] = ((x ^ px) | (z ^ pz)).bit_count()
    return operators


def _clifford_anneal_refine(operators, terms, cap):
    """Repeat a deterministic 16-seed anneal until one pass is unchanged."""
    current_codes = _codes_from_operators(operators, len(operators) // 2)
    n_qubits = current_codes.shape[1]
    for _ in range(3):
        seed_codes = current_codes
        seed_products = _products_from_codes(seed_codes, terms)
        seed_weights = np.count_nonzero(seed_products, axis=1).astype(np.int16)
        start_total = int(seed_weights.sum())
        best_total = start_total
        best_maximum = int(seed_weights.max())
        best_codes = seed_codes.copy()

        for run in range(16):
            operator_codes = seed_codes.copy()
            products = seed_products.copy()
            weights = seed_weights.copy()
            total = int(weights.sum())
            rng = np.random.default_rng(1_000_003 * n_qubits + run)
            hot, cold = 4.0, 0.01
            steps = 100_000
            for step in range(steps):
                left, right = (
                    int(value)
                    for value in rng.choice(n_qubits, 2, replace=False)
                )
                left_axis = int(rng.integers(1, 4))
                right_axis = int(rng.integers(1, 4))
                ql, qr = products[:, left], products[:, right]
                anti = ((ql != 0) & (ql != left_axis)) ^ (
                    (qr != 0) & (qr != right_axis)
                )
                local_delta = (
                    ((ql ^ left_axis) != 0).astype(np.int16)
                    - (ql != 0).astype(np.int16)
                    + ((qr ^ right_axis) != 0).astype(np.int16)
                    - (qr != 0).astype(np.int16)
                )
                delta_weights = np.where(anti, local_delta, 0).astype(
                    np.int16
                )
                candidate_weights = weights + delta_weights
                if int(candidate_weights.max()) > cap:
                    continue
                delta = int(delta_weights.sum())
                temperature = hot * (cold / hot) ** (step / steps)
                if delta > 0 and rng.random() >= math.exp(
                    -delta / temperature
                ):
                    continue

                products[anti, left] ^= left_axis
                products[anti, right] ^= right_axis
                operator_left = operator_codes[:, left]
                operator_right = operator_codes[:, right]
                operator_anti = (
                    (operator_left != 0) & (operator_left != left_axis)
                ) ^ (
                    (operator_right != 0)
                    & (operator_right != right_axis)
                )
                operator_codes[operator_anti, left] ^= left_axis
                operator_codes[operator_anti, right] ^= right_axis
                weights = candidate_weights
                total += delta
                maximum = int(weights.max())
                if (total, maximum) < (best_total, best_maximum):
                    best_total, best_maximum = total, maximum
                    best_codes = operator_codes.copy()

        current_codes = best_codes
        if best_total >= start_total:
            break

    return _operators_from_codes(current_codes)


def _multistage_refine(operators, terms, coords, parents, cap):
    """One fixed, size-independent sequence of complementary neighborhoods."""
    current = _local_barrier_refine(operators, terms, parents, cap)
    current = _block_refine(current, terms, parents, cap)
    current = _majorana_swap_refine(current, terms, coords, cap, 200)
    current = _logical_weight_four_refine(current, terms, coords, cap)
    return _clifford_anneal_refine(current, terms, cap)


def encode(spec: dict) -> dict:
    m = spec["M"]
    coords, edges = spec["coords"], spec["edges"]

    terms = []
    for i, j in edges:
        terms += [
            (2 * i, 2 * j + 1),
            (2 * i + 1, 2 * j),
            (2 * i, 2 * j),
            (2 * i + 1, 2 * j + 1),
        ]
    for i in range(m):
        terms.append((2 * i, 2 * i + 1))
    for i, j in edges:
        terms += [
            (2 * i, 2 * i + 1),
            (2 * j, 2 * j + 1),
            (2 * i, 2 * i + 1, 2 * j, 2 * j + 1),
        ]

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
                out.extend(visit(sites[start : start + size]))
                start += size
            return out

        return visit(sorted(coords))

    def heap_topology():
        def leaf(leaf_index):
            x = z = 0
            node = leaf_index
            while node:
                parent, label = (node - 1) // 3, (node - 1) % 3
                if label in (0, 1):
                    x |= 1 << parent
                if label in (1, 2):
                    z |= 1 << parent
                node = parent
            return x, z

        pairs = [(leaf(a), leaf(a + 1)) for a in range(m, 3 * m, 2)]
        parents = [None] + [(router - 1) // 3 for router in range(1, m)]
        return pairs, parents

    def balanced_topology():
        # This is the genuinely distinct topology hidden in the earlier
        # geometry builder.  Its pivot fraction never entered a Pauli path:
        # only these recursively balanced subtree sizes did.
        leaves = []
        parents = [None] * m
        next_router = 0

        def visit(count, x, z, parent_router):
            nonlocal next_router
            if count == 0:
                leaves.append((x, z))
                return
            router = next_router
            next_router += 1
            parents[router] = parent_router
            base, rem = divmod(count - 1, 3)
            start_sizes = [base + (child < rem) for child in range(3)]
            for child, size in enumerate(start_sizes):
                cx, cz = x, z
                if child in (0, 1):
                    cx |= 1 << router
                if child in (1, 2):
                    cz |= 1 << router
                visit(size, cx, cz, router)

        visit(m, 0, 0, None)
        pairs = [(leaves[2 * k], leaves[2 * k + 1]) for k in range(m)]
        return pairs, parents

    def anneal_pairs(pairs, start_order, seed, steps):
        pos = [0] * m
        for slot, mode in enumerate(start_order):
            pos[mode] = slot
        involved = [[] for _ in range(m)]
        for ti, term in enumerate(terms):
            for mode in {majorana >> 1 for majorana in term}:
                involved[mode].append(ti)

        def weight(term):
            x = z = 0
            for majorana in term:
                ox, oz = pairs[pos[majorana >> 1]][majorana & 1]
                x ^= ox
                z ^= oz
            return (x | z).bit_count()

        weights = [weight(term) for term in terms]
        total = sum(weights)
        best_total, best_pos = total, list(pos)
        rng = np.random.default_rng(seed)
        hot, cold = max(1.0, total * 0.2), max(0.01, total * 0.0001)
        for step in range(steps):
            left, right = (int(v) for v in rng.choice(m, 2, replace=False))
            temperature = hot * (cold / hot) ** (step / steps)
            pos[left], pos[right] = pos[right], pos[left]
            changed, delta = {}, 0
            for ti in set(involved[left]) | set(involved[right]):
                new_weight = weight(terms[ti])
                changed[ti] = new_weight
                delta += new_weight - weights[ti]
            if delta <= 0 or rng.random() < np.exp(-delta / temperature):
                total += delta
                for ti, new_weight in changed.items():
                    weights[ti] = new_weight
                if total < best_total:
                    best_total, best_pos = total, list(pos)
            else:
                pos[left], pos[right] = pos[right], pos[left]

        order = [None] * m
        for mode, slot in enumerate(best_pos):
            order[slot] = mode
        return order

    def anneal_majoranas(pairs, order):
        leaves = [operator for pair in pairs for operator in pair]
        assignment = [None] * (2 * m)
        for slot, mode in enumerate(order):
            assignment[2 * mode] = 2 * slot
            assignment[2 * mode + 1] = 2 * slot + 1

        involved = [[] for _ in range(2 * m)]
        for ti, term in enumerate(terms):
            for majorana in term:
                involved[majorana].append(ti)

        def weight(term):
            x = z = 0
            for majorana in term:
                ox, oz = leaves[assignment[majorana]]
                x ^= ox
                z ^= oz
            return (x | z).bit_count()

        weights = [weight(term) for term in terms]
        total = sum(weights)
        best_total, best_assignment = total, list(assignment)
        rng = np.random.default_rng(1_009 * m + 7)
        hot, cold = max(1.0, total * 0.15), max(0.01, total * 0.0001)
        steps = 100_000
        for step in range(steps):
            left, right = (int(v) for v in rng.choice(2 * m, 2, replace=False))
            temperature = hot * (cold / hot) ** (step / steps)
            assignment[left], assignment[right] = assignment[right], assignment[left]
            changed, delta = {}, 0
            for ti in set(involved[left]) | set(involved[right]):
                new_weight = weight(terms[ti])
                changed[ti] = new_weight
                delta += new_weight - weights[ti]
            if delta <= 0 or rng.random() < np.exp(-delta / temperature):
                total += delta
                for ti, new_weight in changed.items():
                    weights[ti] = new_weight
                if total < best_total:
                    best_total, best_assignment = total, list(assignment)
            else:
                assignment[left], assignment[right] = assignment[right], assignment[left]
        return [leaves[leaf] for leaf in best_assignment]

    def rotations_for(parents):
        pair_set = set()
        for descendant in range(m):
            ancestor = parents[descendant]
            for _ in range(2):
                if ancestor is None:
                    break
                pair_set.add(tuple(sorted((ancestor, descendant))))
                ancestor = parents[ancestor]

        rotations = []
        for left, right in sorted(pair_set):
            for left_axis in range(3):
                for right_axis in range(3):
                    px = pz = 0
                    if left_axis in (0, 1):
                        px |= 1 << left
                    if left_axis in (1, 2):
                        pz |= 1 << left
                    if right_axis in (0, 1):
                        px |= 1 << right
                    if right_axis in (1, 2):
                        pz |= 1 << right
                    rotations.append((px, pz))
        return rotations

    def clifford_refine(operators, rotations):
        # Local code 0/1/2/3 means I/X/Z/Y.  For a weight-two Pauli
        # transvection, support can change only in its two columns, so all
        # candidate deltas can be scored vectorially without changing the
        # scalar search's move order or decisions.
        operator_codes = np.zeros((2 * m, m), dtype=np.uint8)
        for row, (x, z) in enumerate(operators):
            for q in range(m):
                operator_codes[row, q] = ((x >> q) & 1) | (((z >> q) & 1) << 1)

        product_codes = np.zeros((len(terms), m), dtype=np.uint8)
        for ti, term in enumerate(terms):
            for majorana in term:
                product_codes[ti] ^= operator_codes[majorana]
        weights = np.count_nonzero(product_codes, axis=1).astype(np.int16)
        max_cap = int(weights.max())

        decoded = []
        for px, pz in rotations:
            support = px | pz
            left_bit = support & -support
            right_bit = support ^ left_bit
            left = left_bit.bit_length() - 1
            right = right_bit.bit_length() - 1
            left_axis = ((px >> left) & 1) | (((pz >> left) & 1) << 1)
            right_axis = ((px >> right) & 1) | (((pz >> right) & 1) << 1)
            decoded.append((left, right, left_axis, right_axis))

        def effect(codes, left, right, left_axis, right_axis):
            ql, qr = codes[:, left], codes[:, right]
            anti = ((ql != 0) & (ql != left_axis)) ^ (
                (qr != 0) & (qr != right_axis)
            )
            local_delta = (
                ((ql ^ left_axis) != 0).astype(np.int16)
                - (ql != 0).astype(np.int16)
                + ((qr ^ right_axis) != 0).astype(np.int16)
                - (qr != 0).astype(np.int16)
            )
            return anti, np.where(anti, local_delta, 0)

        chooser = random.Random(3)
        while True:
            improving = []
            for rotation_index, (left, right, left_axis, right_axis) in enumerate(decoded):
                _, delta_weights = effect(
                    product_codes, left, right, left_axis, right_axis
                )
                delta = int(delta_weights.sum())
                if delta >= 0:
                    continue
                if int(np.max(weights + delta_weights)) <= max_cap:
                    improving.append(
                        (delta, rotation_index, left, right, left_axis, right_axis)
                    )
            if not improving:
                break
            # Stable sorting by delta reproduces the original rotation-order
            # tie break; do not include rotation_index in the sort key.
            improving.sort(key=lambda item: item[0])
            chosen = improving[chooser.randrange(min(2, len(improving)))]
            _, _, left, right, left_axis, right_axis = chosen
            product_anti, delta_weights = effect(
                product_codes, left, right, left_axis, right_axis
            )
            product_codes[product_anti, left] ^= left_axis
            product_codes[product_anti, right] ^= right_axis
            weights += delta_weights

            operator_anti, _ = effect(
                operator_codes, left, right, left_axis, right_axis
            )
            operator_codes[operator_anti, left] ^= left_axis
            operator_codes[operator_anti, right] ^= right_axis

        out = []
        for row in operator_codes:
            x = z = 0
            for q, code in enumerate(row):
                x |= (int(code) & 1) << q
                z |= ((int(code) >> 1) & 1) << q
            out.append((x, z))
        return out, int(weights.sum()), int(weights.max())

    initial = spatial_order()
    step_schedules = sorted({100_000, max(100_000, 2_500 * m)})
    topology_specs = [
        (*heap_topology(), tuple(m + run for run in range(5))),
        (*balanced_topology(), (31 * m + 4,)),
    ]

    best = None
    for pairs, parents, seeds in topology_specs:
        rotations = rotations_for(parents)
        # Identical pair placements lead to identical downstream searches;
        # de-duplicate them without changing the candidate family.
        seen_orders = set()
        for steps in step_schedules:
            for seed in seeds:
                order = anneal_pairs(pairs, initial, seed, steps)
                key = tuple(order)
                if key in seen_orders:
                    continue
                seen_orders.add(key)
                operators = anneal_majoranas(pairs, order)
                operators, total, maximum = clifford_refine(operators, rotations)
                candidate = (total, maximum, operators, list(parents))
                if best is None or candidate[:2] < best[:2]:
                    best = candidate

    operators = _multistage_refine(
        best[2], terms, coords, best[3], best[1]
    )

    def pauli_string(x, z):
        return "".join(
            "Y"
            if (x >> q) & 1 and (z >> q) & 1
            else "X"
            if (x >> q) & 1
            else "Z"
            if (z >> q) & 1
            else "I"
            for q in range(m)
        )

    return {
        "n_qubits": m,
        "majoranas": [pauli_string(x, z) for x, z in operators],
        "stabilizers": [],
    }
