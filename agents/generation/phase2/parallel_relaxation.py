from __future__ import annotations

"""Small deterministic relaxations used by parallel admission search."""

from typing import Collection, Hashable, Mapping, Sequence


Score4 = tuple[int, int, int, int]
ResourceKey = tuple[int, int, int]
WeightedRow = tuple[int, int]
GroupedRow = tuple[int, int, Hashable]


def _prefix_value(values: Sequence[WeightedRow], count: int) -> tuple[int, int]:
    return (
        sum(value[0] for value in values[:count]),
        sum(value[1] for value in values[:count]),
    )


def resource_relaxed_value(
    values_by_class: Mapping[str, Mapping[str, Sequence[WeightedRow]]],
    *,
    slots: int,
    class_capacities: Mapping[str, int],
    class_counts: Mapping[str, int],
    forbidden_class: str,
    remaining_reserved_tokens: int,
    remaining_shared_tokens: int,
    minimum_grant_tokens: int,
) -> Score4:
    """Return a lexicographic upper bound under nested token constraints.

    ``reserved_eligible`` rows may use either pool, whereas ``shared_only``
    rows may use only the shared pool. Each positive-token row is charged the
    common minimum grant. Conflicts within the suffix remain relaxed.
    """

    total_positive_limit = min(
        slots,
        (remaining_reserved_tokens + remaining_shared_tokens)
        // minimum_grant_tokens,
    )
    shared_positive_limit = min(
        slots,
        remaining_shared_tokens // minimum_grant_tokens,
    )
    # The key records used slots, all positive-token rows, and rows confined
    # to the shared pool. The value is their best lexicographic score.
    dynamic_program: dict[ResourceKey, Score4] = {(0, 0, 0): (0, 0, 0, 0)}
    for capacity_class in sorted(values_by_class):
        groups = values_by_class[capacity_class]
        class_limit = min(
            slots,
            (
                max(
                    0,
                    int(class_capacities[capacity_class])
                    - class_counts.get(capacity_class, 0),
                )
                if capacity_class in class_capacities
                else slots
            ),
        )
        if capacity_class == forbidden_class:
            class_limit = 0
        free_values = groups.get("free", ())
        reserved_values = groups.get("reserved_eligible", ())
        shared_values = groups.get("shared_only", ())

        options: dict[ResourceKey, Score4] = {}
        for free_count in range(min(class_limit, len(free_values)) + 1):
            for reserved_count in range(
                min(
                    class_limit - free_count,
                    len(reserved_values),
                    total_positive_limit,
                )
                + 1
            ):
                for shared_count in range(
                    min(
                        class_limit - free_count - reserved_count,
                        len(shared_values),
                        shared_positive_limit,
                    )
                    + 1
                ):
                    count = free_count + reserved_count + shared_count
                    positive_count = reserved_count + shared_count
                    fair_free, priority_free = _prefix_value(
                        free_values, free_count
                    )
                    fair_reserved, priority_reserved = _prefix_value(
                        reserved_values, reserved_count
                    )
                    fair_shared, priority_shared = _prefix_value(
                        shared_values, shared_count
                    )
                    option_key = (count, positive_count, shared_count)
                    option_value = (
                        fair_free + fair_reserved + fair_shared,
                        priority_free + priority_reserved + priority_shared,
                        count,
                        -positive_count * minimum_grant_tokens,
                    )
                    if (
                        option_key not in options
                        or option_value > options[option_key]
                    ):
                        options[option_key] = option_value

        updated: dict[ResourceKey, Score4] = {}
        for (used, positive, shared), base_value in dynamic_program.items():
            for (
                option_count,
                option_positive,
                option_shared,
            ), option_value in options.items():
                destination = (
                    used + option_count,
                    positive + option_positive,
                    shared + option_shared,
                )
                if (
                    destination[0] > slots
                    or destination[1] > total_positive_limit
                    or destination[2] > shared_positive_limit
                ):
                    continue
                candidate = (
                    base_value[0] + option_value[0],
                    base_value[1] + option_value[1],
                    base_value[2] + option_value[2],
                    base_value[3] + option_value[3],
                )
                if destination not in updated or candidate > updated[destination]:
                    updated[destination] = candidate
        dynamic_program = updated
    return max(dynamic_program.values())


def grouped_suffix_values(
    rows: Sequence[GroupedRow | None],
    *,
    selection_limit: int,
) -> list[tuple[GroupedRow, ...]]:
    """Return bounded suffix representatives for a partition into cliques.

    At most one row from each group can occur in an independent set.  A suffix
    therefore needs only the lexicographically strongest row in each group.
    Retaining twice the selection limit is sufficient after excluding groups
    already occupied by a partial solution, which itself contains no more than
    ``selection_limit`` rows.
    """

    suffixes: list[tuple[GroupedRow, ...]] = [()] * (len(rows) + 1)
    retained_limit = max(0, 2 * selection_limit)
    if retained_limit == 0:
        return suffixes
    best_by_group: dict[Hashable, WeightedRow] = {}
    retained: dict[Hashable, WeightedRow] = {}
    ordered: tuple[GroupedRow, ...] = ()
    for position in range(len(rows) - 1, -1, -1):
        row = rows[position]
        changed = False
        if row is not None:
            fairness, priority, group = row
            value = (fairness, priority)
            previous = best_by_group.get(group)
            if previous is None or value > previous:
                best_by_group[group] = value
                if group in retained or len(retained) < retained_limit:
                    retained[group] = value
                    changed = True
                else:
                    weakest_group = min(
                        retained,
                        key=lambda key: retained[key],
                    )
                    if value > retained[weakest_group]:
                        del retained[weakest_group]
                        retained[group] = value
                        changed = True
        if changed:
            ordered = tuple(
                (
                    value[0],
                    value[1],
                    group,
                )
                for group, value in sorted(
                    retained.items(),
                    key=lambda item: item[1],
                    reverse=True,
                )
            )
        suffixes[position] = ordered
    return suffixes


def grouped_relaxed_value(
    values: Sequence[GroupedRow],
    *,
    slots: int,
    occupied_groups: Collection[Hashable],
) -> tuple[int, int, int]:
    """Bound an independent suffix by selecting one row per clique group."""

    selected = grouped_relaxed_rows(
        values,
        slots=slots,
        occupied_groups=occupied_groups,
    )
    return (
        sum(value[0] for value in selected),
        sum(value[1] for value in selected),
        len(selected),
    )


def grouped_relaxed_rows(
    values: Sequence[GroupedRow],
    *,
    slots: int,
    occupied_groups: Collection[Hashable],
) -> tuple[WeightedRow, ...]:
    """Return the strongest available representative rows from clique groups."""

    if slots <= 0:
        return ()
    selected: list[WeightedRow] = []
    for fairness, priority, group in values:
        if group in occupied_groups:
            continue
        selected.append((fairness, priority))
        if len(selected) >= slots:
            break
    return tuple(selected)
