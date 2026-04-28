## imports
from __future__ import annotations
import random
from game.board import Board
from game.arrow import Arrow
from game.direction import Direction, DIRECTION_VECTORS


MAX_ATTEMPTS = 20


class PuzzleGenerator:
    def generate(
        self,
        rows: int,
        cols: int,
        min_length: int = 2,
        max_length: int = 15,
        rng: random.Random | None = None,
    ) -> tuple[Board, list[Arrow]]:
        if rng is None:
            rng = random.Random()

        for _ in range(MAX_ATTEMPTS):
            result = self._build_ranked_random_puzzle(
                rows, cols, min_length, max_length, rng
            )
            if result is not None:
                return result

        raise RuntimeError(
            f'could not generate a full solvable puzzle for {rows}x{cols}'
        )

    def _build_ranked_random_puzzle(
        self,
        rows: int,
        cols: int,
        min_length: int,
        max_length: int,
        rng: random.Random,
    ) -> tuple[Board, list[Arrow]] | None:
        rank, clear_dirs = self._visibility_peel(rows, cols, rng)
        paths = self._ranked_random_paths(
            rows, cols, min_length, max_length, rank, clear_dirs, rng
        )
        if not paths:
            return None

        board = Board(rows, cols)
        for cells, direction in paths:
            if len(cells) < 2:
                return None
            if self._direction_of(cells[-2], cells[-1]) != direction:
                return None
            board.place_arrow(Arrow(cells=cells, direction=direction))

        self._fill_remaining(board, rows, cols)
        self._cover_remaining_by_endpoint_steal(board, rows, cols)
        if not self._is_fully_covered(board, rows, cols):
            return None

        solution = self._solve(board)
        if solution is None or len(solution) != len(board.living_arrows()):
            return None

        return board, solution

    def _visibility_peel(
        self, rows: int, cols: int, rng: random.Random
    ) -> tuple[
        dict[tuple[int, int], int],
        dict[tuple[int, int], list[Direction]],
    ]:
        removed = [[False] * cols for _ in range(rows)]
        rank: dict[tuple[int, int], int] = {}
        clear_dirs: dict[tuple[int, int], list[Direction]] = {}
        left = [0] * rows
        right = [cols - 1] * rows
        top = [0] * cols
        bottom = [rows - 1] * cols
        entries: list[tuple[int, int, Direction]] = []

        def add_entry(r: int, c: int, direction: Direction) -> None:
            if 0 <= r < rows and 0 <= c < cols and not removed[r][c]:
                entries.append((r, c, direction))

        add_entry(0, 0, Direction.UP)
        add_entry(0, 0, Direction.LEFT)
        add_entry(0, cols - 1, Direction.UP)
        add_entry(0, cols - 1, Direction.RIGHT)
        add_entry(rows - 1, 0, Direction.DOWN)
        add_entry(rows - 1, 0, Direction.LEFT)
        add_entry(rows - 1, cols - 1, Direction.DOWN)
        add_entry(rows - 1, cols - 1, Direction.RIGHT)

        step = 0
        while step < rows * cols:
            if not entries:
                return {}, {}

            i = rng.randrange(len(entries))
            r, c, direction = entries[i]
            entries[i] = entries[-1]
            entries.pop()
            if removed[r][c]:
                continue

            valid: list[Direction] = []
            if c == left[r]:
                valid.append(Direction.LEFT)
            if c == right[r]:
                valid.append(Direction.RIGHT)
            if r == top[c]:
                valid.append(Direction.UP)
            if r == bottom[c]:
                valid.append(Direction.DOWN)
            if direction not in valid and not valid:
                continue

            rng.shuffle(valid)
            removed[r][c] = True
            rank[(r, c)] = step
            clear_dirs[(r, c)] = valid
            step += 1

            while left[r] < cols and removed[r][left[r]]:
                left[r] += 1
            while right[r] >= 0 and removed[r][right[r]]:
                right[r] -= 1
            while top[c] < rows and removed[top[c]][c]:
                top[c] += 1
            while bottom[c] >= 0 and removed[bottom[c]][c]:
                bottom[c] -= 1

            if left[r] < cols:
                add_entry(r, left[r], Direction.LEFT)
            if right[r] >= 0:
                add_entry(r, right[r], Direction.RIGHT)
            if top[c] < rows:
                add_entry(top[c], c, Direction.UP)
            if bottom[c] >= 0:
                add_entry(bottom[c], c, Direction.DOWN)

        return rank, clear_dirs

    def _ranked_random_paths(
        self,
        rows: int,
        cols: int,
        min_length: int,
        max_length: int,
        rank: dict[tuple[int, int], int],
        clear_dirs: dict[tuple[int, int], list[Direction]],
        rng: random.Random,
    ) -> list[tuple[list[tuple[int, int]], Direction]]:
        paths, unassigned = self._ranked_matching_paths(
            rows, cols, rank, clear_dirs, rng
        )
        self._absorb_ranked_leftovers(paths, unassigned, rank, rng)
        self._merge_ranked_paths(paths, min_length, max_length, rank, rng)
        self._repair_ranked_head_leftovers(
            paths, unassigned, rank, clear_dirs, rng
        )
        self._absorb_ranked_leftovers(paths, unassigned, rank, rng)
        self._merge_ranked_paths(paths, min_length, max_length, rank, rng)
        self._merge_ranked_outliers(paths, max_length, rank, rng)
        return paths

    def _ranked_matching_paths(
        self,
        rows: int,
        cols: int,
        rank: dict[tuple[int, int], int],
        clear_dirs: dict[tuple[int, int], list[Direction]],
        rng: random.Random,
    ) -> tuple[
        list[tuple[list[tuple[int, int]], Direction]],
        set[tuple[int, int]],
    ]:
        left_cells = [
            (r, c)
            for r in range(rows)
            for c in range(cols)
            if (r + c) % 2 == 0
        ]
        edges: dict[tuple[int, int], list[tuple[int, int]]] = {}
        directed: dict[
            tuple[tuple[int, int], tuple[int, int]],
            tuple[tuple[int, int], tuple[int, int], Direction],
        ] = {}

        for head in rank:
            hr, hc = head
            for direction in clear_dirs.get(head, []):
                dr, dc = DIRECTION_VECTORS[direction]
                previous = (hr - dr, hc - dc)
                if previous not in rank or rank[previous] <= rank[head]:
                    continue
                left, right = (
                    (head, previous)
                    if (head[0] + head[1]) % 2 == 0
                    else (previous, head)
                )
                edges.setdefault(left, []).append(right)
                directed[(left, right)] = (head, previous, direction)

        for options in edges.values():
            rng.shuffle(options)

        matched = self._hopcroft_karp(left_cells, edges)
        paths: list[tuple[list[tuple[int, int]], Direction]] = []
        used: set[tuple[int, int]] = set()
        for left, right in matched.items():
            if right is None:
                continue
            head, previous, direction = directed[(left, right)]
            paths.append(([previous, head], direction))
            used.add(head)
            used.add(previous)

        return paths, set(rank) - used

    def _hopcroft_karp(
        self,
        left_cells: list[tuple[int, int]],
        edges: dict[tuple[int, int], list[tuple[int, int]]],
    ) -> dict[tuple[int, int], tuple[int, int] | None]:
        from collections import deque

        pair_left: dict[tuple[int, int], tuple[int, int] | None] = {
            cell: None for cell in left_cells
        }
        pair_right: dict[tuple[int, int], tuple[int, int]] = {}
        dist: dict[tuple[int, int], int] = {}

        def bfs() -> bool:
            queue: deque[tuple[int, int]] = deque()
            found = False
            for cell in left_cells:
                if pair_left[cell] is None:
                    dist[cell] = 0
                    queue.append(cell)
                else:
                    dist[cell] = 10**9

            while queue:
                cell = queue.popleft()
                for neighbour in edges.get(cell, []):
                    paired = pair_right.get(neighbour)
                    if paired is None:
                        found = True
                    elif dist[paired] == 10**9:
                        dist[paired] = dist[cell] + 1
                        queue.append(paired)
            return found

        def dfs(cell: tuple[int, int]) -> bool:
            for neighbour in edges.get(cell, []):
                paired = pair_right.get(neighbour)
                if paired is None or (
                    dist[paired] == dist[cell] + 1 and dfs(paired)
                ):
                    pair_left[cell] = neighbour
                    pair_right[neighbour] = cell
                    return True
            dist[cell] = 10**9
            return False

        while bfs():
            for cell in left_cells:
                if pair_left[cell] is None:
                    dfs(cell)

        return pair_left

    def _ranked_head_candidates(
        self,
        head: tuple[int, int],
        unassigned: set[tuple[int, int]],
        rank: dict[tuple[int, int], int],
        clear_dirs: dict[tuple[int, int], list[Direction]],
    ) -> list[tuple[Direction, tuple[int, int]]]:
        hr, hc = head
        candidates: list[tuple[Direction, tuple[int, int]]] = []
        for direction in clear_dirs.get(head, []):
            dr, dc = DIRECTION_VECTORS[direction]
            previous = (hr - dr, hc - dc)
            if previous in unassigned and rank[previous] > rank[head]:
                candidates.append((direction, previous))
        return candidates

    def _ranked_tail_step(
        self,
        path: list[tuple[int, int]],
        unassigned: set[tuple[int, int]],
        head_rank: int,
        rank: dict[tuple[int, int], int],
        rng: random.Random,
    ) -> tuple[int, int] | None:
        r, c = path[-1]
        neighbours = [
            (r + dr, c + dc)
            for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1))
            if (r + dr, c + dc) in unassigned
            and rank[(r + dr, c + dc)] > head_rank
        ]
        if not neighbours:
            return None

        rng.shuffle(neighbours)
        if len(path) >= 2 and rng.random() < 0.65:
            last_step = (
                path[-1][0] - path[-2][0],
                path[-1][1] - path[-2][1],
            )
            turning = [
                n
                for n in neighbours
                if (n[0] - r, n[1] - c) != last_step
            ]
            if turning:
                neighbours = turning

        neighbours.sort(
            key=lambda n: sum(
                (n[0] + dr, n[1] + dc) in unassigned
                for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1))
            )
        )
        return rng.choice(neighbours[: min(4, len(neighbours))])

    def _absorb_ranked_leftovers(
        self,
        paths: list[tuple[list[tuple[int, int]], Direction]],
        unassigned: set[tuple[int, int]],
        rank: dict[tuple[int, int], int],
        rng: random.Random,
    ) -> None:
        cell_to_path: dict[tuple[int, int], int] = {}
        for i, (cells, _) in enumerate(paths):
            for cell in cells:
                cell_to_path[cell] = i

        changed = True
        while changed and unassigned:
            changed = False
            for cell in sorted(list(unassigned), key=rank.get, reverse=True):
                options: list[tuple[int, int]] = []
                r, c = cell
                for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    neighbour = (r + dr, c + dc)
                    path_index = cell_to_path.get(neighbour)
                    if path_index is None:
                        continue
                    cells, _ = paths[path_index]
                    if cells[0] == neighbour and rank[cell] > rank[cells[-1]]:
                        options.append((path_index, 0))

                    if rank[cell] <= rank[cells[-1]]:
                        continue
                    for insert_at in range(1, len(cells)):
                        if not (
                            self._are_adjacent(cells[insert_at - 1], cell)
                            and self._are_adjacent(cell, cells[insert_at])
                        ):
                            continue
                        if insert_at == len(cells) - 1:
                            _, direction = paths[path_index]
                            if self._direction_of(cell, cells[-1]) != direction:
                                continue
                        options.append((path_index, insert_at))

                if not options:
                    continue

                path_index, insert_at = rng.choice(options)
                cells, direction = paths[path_index]
                cells.insert(insert_at, cell)
                paths[path_index] = (cells, direction)
                cell_to_path[cell] = path_index
                unassigned.remove(cell)
                changed = True

    def _repair_ranked_head_leftovers(
        self,
        paths: list[tuple[list[tuple[int, int]], Direction]],
        unassigned: set[tuple[int, int]],
        rank: dict[tuple[int, int], int],
        clear_dirs: dict[tuple[int, int], list[Direction]],
        rng: random.Random,
    ) -> None:
        changed = True
        while changed and unassigned:
            changed = False
            cell_to_path = {
                cell: i
                for i, (cells, _) in enumerate(paths)
                for cell in cells
            }

            for head in sorted(list(unassigned), key=rank.get):
                options: list[
                    tuple[int, Direction, tuple[int, int], str, int]
                ] = []
                hr, hc = head
                for direction in clear_dirs.get(head, []):
                    dr, dc = DIRECTION_VECTORS[direction]
                    previous = (hr - dr, hc - dc)
                    path_index = cell_to_path.get(previous)
                    if path_index is None or rank[previous] <= rank[head]:
                        continue

                    cells, _ = paths[path_index]
                    previous_index = cells.index(previous)
                    if previous_index == 0 and len(cells) > 2:
                        options.append(
                            (path_index, direction, previous, 'steal_tail', 0)
                        )
                    elif (
                        previous_index == 0
                        and len(cells) == 2
                        and rank[cells[-1]] > rank[head]
                    ):
                        options.append(
                            (path_index, direction, previous, 'replace_pair', 0)
                        )
                    elif (
                        previous_index < len(cells) - 2
                        and all(rank[cell] > rank[head] for cell in cells[:previous_index + 1])
                    ):
                        options.append(
                            (
                                path_index,
                                direction,
                                previous,
                                'split_prefix',
                                previous_index,
                            )
                        )
                    elif previous_index == len(cells) - 1 and all(
                        rank[cell] > rank[head] for cell in cells
                    ):
                        options.append(
                            (
                                path_index,
                                direction,
                                previous,
                                'replace_path',
                                previous_index,
                            )
                        )

                if not options:
                    continue

                path_index, direction, previous, mode, previous_index = rng.choice(
                    options
                )
                cells, old_direction = paths[path_index]
                if mode == 'replace_pair':
                    paths[path_index] = ([cells[-1], previous, head], direction)
                elif mode == 'replace_path':
                    paths[path_index] = (cells + [head], direction)
                elif mode == 'steal_tail':
                    cells.pop(0)
                    paths[path_index] = (cells, old_direction)
                    paths.append(([previous, head], direction))
                else:
                    new_cells = cells[: previous_index + 1] + [head]
                    old_cells = cells[previous_index + 1:]
                    paths[path_index] = (old_cells, old_direction)
                    paths.append((new_cells, direction))
                unassigned.remove(head)
                changed = True
                break

    def _merge_ranked_paths(
        self,
        paths: list[tuple[list[tuple[int, int]], Direction]],
        min_length: int,
        max_length: int,
        rank: dict[tuple[int, int], int],
        rng: random.Random,
    ) -> None:
        active = [True] * len(paths)
        cell_to_path = {
            cell: i
            for i, (cells, _) in enumerate(paths)
            for cell in cells
        }
        order = list(range(len(paths)))
        rng.shuffle(order)

        for path_index in order:
            if not active[path_index]:
                continue
            while len(paths[path_index][0]) < max(min_length + 2, max_length // 2):
                match = self._find_ranked_merge(
                    path_index,
                    paths,
                    active,
                    cell_to_path,
                    max_length,
                    rank,
                    rng,
                )
                if match is None:
                    break
                other_index, reverse_other = match
                cells, direction = paths[path_index]
                other_cells, _ = paths[other_index]
                if reverse_other:
                    other_cells = list(reversed(other_cells))
                paths[path_index] = (other_cells + cells, direction)
                for cell in other_cells:
                    cell_to_path[cell] = path_index
                active[other_index] = False

        live = [path for i, path in enumerate(paths) if active[i]]
        paths[:] = live

    def _find_ranked_merge(
        self,
        path_index: int,
        paths: list[tuple[list[tuple[int, int]], Direction]],
        active: list[bool],
        cell_to_path: dict[tuple[int, int], int],
        max_length: int,
        rank: dict[tuple[int, int], int],
        rng: random.Random,
        prefer_long: bool = False,
    ) -> tuple[int, bool] | None:
        cells, _ = paths[path_index]
        head_rank = rank[cells[-1]]
        tail = cells[0]
        candidates: list[tuple[int, bool]] = []

        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            neighbour = (tail[0] + dr, tail[1] + dc)
            other_index = cell_to_path.get(neighbour)
            if (
                other_index is None
                or other_index == path_index
                or not active[other_index]
            ):
                continue
            other_cells, _ = paths[other_index]
            if len(cells) + len(other_cells) > max_length:
                continue
            if rank[other_cells[-1]] <= head_rank:
                continue
            if other_cells[-1] == neighbour:
                candidates.append((other_index, False))
            if other_cells[0] == neighbour:
                candidates.append((other_index, True))

        if not candidates:
            return None
        if prefer_long:
            rng.shuffle(candidates)
            candidates.sort(
                key=lambda item: len(paths[item[0]][0]), reverse=True
            )
            return candidates[0]
        return rng.choice(candidates)

    def _merge_ranked_outliers(
        self,
        paths: list[tuple[list[tuple[int, int]], Direction]],
        max_length: int,
        rank: dict[tuple[int, int], int],
        rng: random.Random,
    ) -> None:
        if not paths:
            return

        desired = 1 if len(rank) < 12000 else 2
        min_target = max(max_length + 12, max_length * 2)
        long_limit = max(min_target, min(max_length * 4, 120))
        active = [True] * len(paths)
        cell_to_path = {
            cell: i
            for i, (cells, _) in enumerate(paths)
            for cell in cells
        }
        made = 0

        while made < desired:
            candidates = [
                i
                for i, (cells, _) in enumerate(paths)
                if active[i] and len(cells) < long_limit
            ]
            if not candidates:
                break

            rng.shuffle(candidates)
            candidates.sort(key=lambda i: len(paths[i][0]), reverse=True)
            candidates = candidates[:240]
            estimates = {
                i: self._estimate_ranked_outlier_len(
                    i, paths, active, cell_to_path, long_limit, rank
                )
                for i in candidates
            }
            candidates = [
                i for i in candidates if estimates[i] > len(paths[i][0])
            ]
            if not candidates:
                break

            rng.shuffle(candidates)
            candidates.sort(
                key=lambda i: (estimates[i], len(paths[i][0])),
                reverse=True,
            )
            grew = False
            for path_index in candidates:
                if not active[path_index]:
                    continue

                start_len = len(paths[path_index][0])
                while len(paths[path_index][0]) < long_limit:
                    match = self._find_ranked_merge(
                        path_index,
                        paths,
                        active,
                        cell_to_path,
                        long_limit,
                        rank,
                        rng,
                        prefer_long=True,
                    )
                    if match is None:
                        break

                    other_index, reverse_other = match
                    cells, direction = paths[path_index]
                    other_cells, _ = paths[other_index]
                    if reverse_other:
                        other_cells = list(reversed(other_cells))
                    paths[path_index] = (other_cells + cells, direction)
                    for cell in other_cells:
                        cell_to_path[cell] = path_index
                    active[other_index] = False

                if len(paths[path_index][0]) > start_len:
                    made += 1
                    grew = True
                    break

            if not grew:
                break

        live = [path for i, path in enumerate(paths) if active[i]]
        paths[:] = live

    def _estimate_ranked_outlier_len(
        self,
        path_index: int,
        paths: list[tuple[list[tuple[int, int]], Direction]],
        active: list[bool],
        cell_to_path: dict[tuple[int, int], int],
        long_limit: int,
        rank: dict[tuple[int, int], int],
    ) -> int:
        cells, _ = paths[path_index]
        head_rank = rank[cells[-1]]
        tail = cells[0]
        total = len(cells)
        used = {path_index}

        while total < long_limit:
            options: list[tuple[int, tuple[int, int]]] = []
            for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                neighbour = (tail[0] + dr, tail[1] + dc)
                other_index = cell_to_path.get(neighbour)
                if (
                    other_index is None
                    or other_index in used
                    or not active[other_index]
                ):
                    continue

                other_cells, _ = paths[other_index]
                if total + len(other_cells) > long_limit:
                    continue
                if rank[other_cells[-1]] <= head_rank:
                    continue
                if other_cells[-1] == neighbour:
                    options.append((other_index, other_cells[0]))
                if other_cells[0] == neighbour:
                    options.append((other_index, other_cells[-1]))

            if not options:
                break

            options.sort(
                key=lambda item: len(paths[item[0]][0]), reverse=True
            )
            other_index, next_tail = options[0]
            used.add(other_index)
            total += len(paths[other_index][0])
            tail = next_tail

        return total

    def _build_random_cover_puzzle(
        self,
        rows: int,
        cols: int,
        min_length: int,
        max_length: int,
        rng: random.Random,
    ) -> tuple[Board, list[Arrow]] | None:
        paths = self._random_path_cover(rows, cols, min_length, max_length, rng)
        paths = self._repair_single_cell_paths(paths)
        if any(len(path) < 2 for path in paths):
            return None
        if rows * cols / len(paths) < 5.5:
            return None

        covered = {cell for path in paths for cell in path}
        if len(covered) != rows * cols:
            return None

        board = Board(rows, cols)
        for path in paths:
            direction = self._direction_of(path[-2], path[-1])
            if direction is None:
                return None
            board.place_arrow(Arrow(cells=path, direction=direction))

        solution = self._solve(board)
        if solution is None or len(solution) != len(board.living_arrows()):
            return None

        return board, solution

    def _random_path_cover(
        self,
        rows: int,
        cols: int,
        min_length: int,
        max_length: int,
        rng: random.Random,
    ) -> list[list[tuple[int, int]]]:
        cells = [(r, c) for r in range(rows) for c in range(cols)]
        unvisited = set(cells)
        paths: list[list[tuple[int, int]]] = []

        while unvisited:
            start = rng.choice(cells)
            while start not in unvisited:
                start = rng.choice(cells)
            path = [start]
            unvisited.remove(start)
            target = self._pick_length(min_length, max_length, rng)

            while len(path) < target:
                r, c = path[-1]
                neighbours = [
                    (r + dr, c + dc)
                    for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1))
                    if (r + dr, c + dc) in unvisited
                ]
                if not neighbours:
                    break

                rng.shuffle(neighbours)
                neighbours.sort(
                    key=lambda n: sum(
                        (n[0] + dr, n[1] + dc) in unvisited
                        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1))
                    )
                )
                if len(path) >= 2 and rng.random() < 0.65:
                    last_step = (
                        path[-1][0] - path[-2][0],
                        path[-1][1] - path[-2][1],
                    )
                    turning = [
                        n
                        for n in neighbours
                        if (n[0] - r, n[1] - c) != last_step
                    ]
                    if turning:
                        neighbours = turning

                path.append(rng.choice(neighbours[: min(3, len(neighbours))]))
                unvisited.remove(path[-1])

            paths.append(path)

        return [path for path in paths if path]

    def _repair_single_cell_paths(
        self, paths: list[list[tuple[int, int]]]
    ) -> list[list[tuple[int, int]]]:
        paths = [list(path) for path in paths if path]
        cell_to_path = {cell: i for i, path in enumerate(paths) for cell in path}

        progress = True
        while progress:
            progress = False
            for i, path in enumerate(paths):
                if len(path) != 1:
                    continue
                cell = path[0]
                if self._attach_single_cell_path(paths, cell_to_path, i, cell):
                    progress = True

        progress = True
        while progress:
            progress = False
            for i, path in enumerate(paths):
                if len(path) != 1:
                    continue
                cell = path[0]
                if self._steal_cell_for_single_path(paths, cell_to_path, i, cell):
                    progress = True

        return [path for path in paths if path]

    def _attach_single_cell_path(
        self,
        paths: list[list[tuple[int, int]]],
        cell_to_path: dict[tuple[int, int], int],
        path_index: int,
        cell: tuple[int, int],
    ) -> bool:
        r, c = cell
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            neighbour = (r + dr, c + dc)
            other_index = cell_to_path.get(neighbour)
            if other_index is None or other_index == path_index:
                continue
            other = paths[other_index]
            if other[0] == neighbour:
                other.insert(0, cell)
                paths[path_index] = []
                cell_to_path[cell] = other_index
                return True
            if other[-1] == neighbour:
                other.append(cell)
                paths[path_index] = []
                cell_to_path[cell] = other_index
                return True
            for insert_at in range(1, len(other)):
                if (
                    other[insert_at] == neighbour
                    and self._are_adjacent(cell, other[insert_at - 1])
                ):
                    other.insert(insert_at, cell)
                    paths[path_index] = []
                    cell_to_path[cell] = other_index
                    return True
        return False

    def _steal_cell_for_single_path(
        self,
        paths: list[list[tuple[int, int]]],
        cell_to_path: dict[tuple[int, int], int],
        path_index: int,
        cell: tuple[int, int],
    ) -> bool:
        r, c = cell
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            neighbour = (r + dr, c + dc)
            other_index = cell_to_path.get(neighbour)
            if other_index is None or other_index == path_index:
                continue
            other = paths[other_index]
            for steal_at, stolen in enumerate(other):
                if stolen != neighbour:
                    continue
                left = other[:steal_at]
                right = other[steal_at + 1:]
                if len(left) == 1 and len(right) == 1:
                    continue
                stolen_path = [cell, stolen]
                if len(left) == 1:
                    stolen_path = [left[0], stolen, cell]
                    left = []
                elif len(right) == 1:
                    stolen_path = [cell, stolen, right[0]]
                    right = []
                new_paths: list[list[tuple[int, int]]] = []
                if left:
                    new_paths.append(left)
                if right:
                    new_paths.append(right)
                new_paths.append(stolen_path)
                paths[path_index] = []
                paths[other_index] = []
                start_index = len(paths)
                paths.extend(new_paths)
                for offset, path in enumerate(new_paths):
                    for path_cell in path:
                        cell_to_path[path_cell] = start_index + offset
                return True
        return False

    def _solve_with_free_directions(self, board: Board) -> list[Arrow] | None:
        sb = Board(board.rows, board.cols)
        arrows = list(board.living_arrows())
        for arrow in arrows:
            arrow.alive = True
            sb.place_arrow(arrow)

        def orientations(arrow: Arrow) -> list[tuple[list[tuple[int, int]], Direction]]:
            opts: list[tuple[list[tuple[int, int]], Direction]] = []
            for cells in (list(arrow.cells), list(reversed(arrow.cells))):
                aligned = self._direction_of(cells[-2], cells[-1])
                directions: list[Direction] = []
                if (
                    aligned is not None
                    and not self._is_border_exit(cells[-1], aligned, board.rows, board.cols)
                ):
                    directions.append(aligned)
                for direction in Direction:
                    if (
                        direction not in directions
                        and not self._is_border_exit(
                            cells[-1], direction, board.rows, board.cols
                        )
                    ):
                        directions.append(direction)
                opts.extend((cells, direction) for direction in directions)
            return opts

        def find_blocker(
            cells: list[tuple[int, int]], direction: Direction, arrow: Arrow
        ) -> Arrow | None:
            dr, dc = DIRECTION_VECTORS[direction]
            r, c = cells[-1]
            r += dr
            c += dc
            while 0 <= r < sb.rows and 0 <= c < sb.cols:
                occ = sb._grid[r][c]
                if occ is not None and occ is not arrow and occ.alive:
                    return occ
                r += dr
                c += dc
            return None

        blocked_by: dict[int, list[tuple[Arrow, list[tuple[int, int]], Direction]]] = {}
        freed: dict[int, tuple[list[tuple[int, int]], Direction]] = {}
        queue: deque[Arrow] = deque()

        for arrow in arrows:
            for cells, direction in orientations(arrow):
                blocker = find_blocker(cells, direction, arrow)
                if blocker is None:
                    if id(arrow) not in freed:
                        freed[id(arrow)] = (cells, direction)
                        queue.append(arrow)
                else:
                    blocked_by.setdefault(id(blocker), []).append(
                        (arrow, cells, direction)
                    )

        order: list[Arrow] = []
        while queue:
            arrow = queue.popleft()
            if not arrow.alive:
                continue
            cells, direction = freed[id(arrow)]
            arrow.cells = cells
            arrow.direction = direction
            order.append(arrow)
            sb.remove_arrow(arrow)

            for blocked, cells, direction in blocked_by.pop(id(arrow), []):
                if not blocked.alive or id(blocked) in freed:
                    continue
                new_blocker = find_blocker(cells, direction, blocked)
                if new_blocker is None:
                    freed[id(blocked)] = (cells, direction)
                    queue.append(blocked)
                else:
                    blocked_by.setdefault(id(new_blocker), []).append(
                        (blocked, cells, direction)
                    )

        for arrow in arrows:
            arrow.alive = True
        return order if len(order) == len(arrows) else None

    def _build_puzzle(
        self,
        rows: int,
        cols: int,
        min_length: int,
        max_length: int,
        rng: random.Random,
    ) -> tuple[Board, list[Arrow]] | None:
        board = Board(rows, cols)
        placement: list[Arrow] = []

        ordered = self._growth_order(rows, cols, rng)

        for r, c in ordered:
            if board.is_cell_occupied(r, c):
                continue
            walk = self._random_walk(
                r, c, board, rows, cols, min_length, max_length, rng
            )
            if walk is None:
                continue
            arrow = self._clear_exit_orientation(walk, board, rows, cols)
            if arrow is None:
                continue
            board.place_arrow(arrow)
            placement.append(arrow)

        if not placement:
            return None

        self._fill_gaps(board, rows, cols, placement)

        saved = {id(a): (list(a.cells), a.direction) for a in placement}
        safe_coverage = self._covered_cell_count(board, rows, cols) / (rows * cols)

        self._fill_remaining(board, rows, cols)
        all_arrows = list(board.living_arrows())
        solver_order = self._solve(board)
        if solver_order is not None and len(solver_order) == len(all_arrows):
            coverage = self._covered_cell_count(board, rows, cols) / (rows * cols)
            if coverage >= self._target_coverage(rows, cols):
                return board, solver_order

        for a in placement:
            for r2, c2 in a.cells:
                if board._grid[r2][c2] is a:
                    board._grid[r2][c2] = None
            old_cells, old_dir = saved[id(a)]
            a.cells = old_cells
            a.direction = old_dir
            a.alive = True
            for r2, c2 in a.cells:
                board._grid[r2][c2] = a

        coverage = safe_coverage
        if coverage < self._target_coverage(rows, cols):
            return None

        return board, list(reversed(placement))

    def _growth_order(
        self, rows: int, cols: int, rng: random.Random
    ) -> list[tuple[int, int]]:
        seeds = [(rng.randrange(rows), rng.randrange(cols))]

        ordered: list[tuple[int, int]] = []
        frontier = list(seeds)
        rng.shuffle(frontier)
        visited = set(seeds)

        while frontier:
            i = rng.randrange(len(frontier))
            cell = frontier.pop(i)
            ordered.append(cell)
            r, c = cell
            neighbours = [(r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)]
            rng.shuffle(neighbours)
            for nr, nc in neighbours:
                if (
                    0 <= nr < rows
                    and 0 <= nc < cols
                    and (nr, nc) not in visited
                ):
                    visited.add((nr, nc))
                    frontier.append((nr, nc))

        return ordered

    def _target_coverage(self, rows: int, cols: int) -> float:
        cells = rows * cols
        if cells <= 12000:
            return 0.94
        if cells <= 50000:
            return 0.90
        if cells <= 120000:
            return 0.87
        return 0.84

    def _random_walk(
        self,
        sr: int,
        sc: int,
        board: Board,
        rows: int,
        cols: int,
        min_len: int,
        max_len: int,
        rng: random.Random,
    ) -> list[tuple[int, int]] | None:
        path = [(sr, sc)]
        visited = {(sr, sc)}
        target = self._pick_length(min_len, max_len, rng)

        while len(path) < target:
            r, c = path[-1]
            on_border = r == 0 or r == rows - 1 or c == 0 or c == cols - 1

            neighbors = []
            for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                nr, nc = r + dr, c + dc
                if (
                    0 <= nr < rows
                    and 0 <= nc < cols
                    and (nr, nc) not in visited
                    and not board.is_cell_occupied(nr, nc)
                ):
                    neighbors.append((nr, nc))
            if not neighbors:
                break

            if len(path) >= min_len and on_border:
                edge_neighbors = [
                    (nr, nc)
                    for nr, nc in neighbors
                    if nr == 0 or nr == rows - 1 or nc == 0 or nc == cols - 1
                ]
                if edge_neighbors:
                    neighbors = edge_neighbors
                elif rng.random() < 0.20:
                    break

            if len(path) + 1 >= target:
                interior_neighbors = [
                    (nr, nc)
                    for nr, nc in neighbors
                    if not (
                        nr == 0
                        or nr == rows - 1
                        or nc == 0
                        or nc == cols - 1
                    )
                ]
                if interior_neighbors:
                    neighbors = interior_neighbors

            # Force turns: prefer changing direction from last step
            if len(path) >= 2:
                last_dr = r - path[-2][0]
                last_dc = c - path[-2][1]
                turning = [
                    (nr, nc)
                    for nr, nc in neighbors
                    if (nr - r, nc - c) != (last_dr, last_dc)
                ]
                if turning and rng.random() < 0.55:
                    neighbors = turning

            # After reaching half the target, bias toward the nearest edge
            if len(path) >= target // 2 and rng.random() < 0.4:
                edge_dist = min(r, rows - 1 - r, c, cols - 1 - c)
                if edge_dist > 0:
                    closer = [
                        (nr, nc)
                        for nr, nc in neighbors
                        if min(nr, rows - 1 - nr, nc, cols - 1 - nc) < edge_dist
                    ]
                    if closer:
                        neighbors = closer

            # Prefer neighbors about to become isolated
            urgent = []
            for nr, nc in neighbors:
                exits = 0
                for dr2, dc2 in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    nnr, nnc = nr + dr2, nc + dc2
                    if (
                        0 <= nnr < rows
                        and 0 <= nnc < cols
                        and (nnr, nnc) not in visited
                        and not board.is_cell_occupied(nnr, nnc)
                    ):
                        exits += 1
                if exits <= 1:
                    urgent.append((nr, nc))

            if urgent:
                path.append(rng.choice(urgent))
            else:
                path.append(rng.choice(neighbors))
            visited.add(path[-1])

        if len(path) < min_len:
            return None
        return path

    def _solve(self, board: Board) -> list[Arrow] | None:
        """Flexible solver: choose arrow orientation (either end as head) to find a solvable ordering."""
        from collections import deque

        sb = Board(board.rows, board.cols)
        arrows = list(board.living_arrows())
        for a in arrows:
            a.alive = True
            sb.place_arrow(a)

        n = len(arrows)

        def orientations(a: Arrow) -> list[tuple[list[tuple[int, int]], Direction]]:
            opts = []
            if len(a.cells) >= 2:
                d_fwd = self._direction_of(a.cells[-2], a.cells[-1])
                if d_fwd is not None:
                    opts.append((list(a.cells), d_fwd))
                rev = list(reversed(a.cells))
                d_rev = self._direction_of(rev[-2], rev[-1])
                if d_rev is not None:
                    opts.append((rev, d_rev))
            opts.sort(
                key=lambda item: self._is_border_exit(
                    item[0][-1], item[1], board.rows, board.cols
                )
            )
            return opts

        def find_blocker(
            cells: list[tuple[int, int]], d: Direction, arrow: Arrow
        ) -> Arrow | None:
            dr, dc = DIRECTION_VECTORS[d]
            r, c = cells[-1]
            r += dr
            c += dc
            while 0 <= r < sb.rows and 0 <= c < sb.cols:
                occ = sb._grid[r][c]
                if occ is not None and occ is not arrow and occ.alive:
                    return occ
                r += dr
                c += dc
            return None

        blocked_by: dict[int, list[tuple[Arrow, list[tuple[int, int]], Direction]]] = {}
        freed: dict[int, tuple[list[tuple[int, int]], Direction]] = {}
        queue: deque[Arrow] = deque()

        for a in arrows:
            for cells, d in orientations(a):
                blocker = find_blocker(cells, d, a)
                if blocker is None:
                    if id(a) not in freed:
                        freed[id(a)] = (cells, d)
                        queue.append(a)
                else:
                    blocked_by.setdefault(id(blocker), []).append((a, cells, d))

        order: list[Arrow] = []
        while queue:
            a = queue.popleft()
            if not a.alive:
                continue
            cells, d = freed[id(a)]
            a.cells = cells
            a.direction = d
            order.append(a)
            sb.remove_arrow(a)

            for b, bcells, bd in blocked_by.pop(id(a), []):
                if not b.alive or id(b) in freed:
                    continue
                new_blocker = find_blocker(bcells, bd, b)
                if new_blocker is None:
                    freed[id(b)] = (bcells, bd)
                    queue.append(b)
                else:
                    blocked_by.setdefault(id(new_blocker), []).append(
                        (b, bcells, bd)
                    )

        for a in arrows:
            a.alive = True
        return order if order else None

    def _fill_gaps(
        self,
        board: Board,
        rows: int,
        cols: int,
        placement: list[Arrow] | None = None,
    ) -> None:
        """Merge uncovered cells into arrows without blocking any exit ray.

        Uses placement order to allow merges that the conservative
        full-ray approach would reject.  Cell X can be merged into
        arrow at placement-position j only if no arrow placed AFTER j
        has X on its exit ray.
        """
        pos_of: dict[int, int] = {}
        if placement is not None:
            for i, a in enumerate(placement):
                pos_of[id(a)] = i

        max_blocker: dict[tuple[int, int], int] = {}
        for arrow in board.living_arrows():
            p = pos_of.get(id(arrow), len(pos_of))
            dr, dc = DIRECTION_VECTORS[arrow.direction]
            r, c = arrow.cells[-1]
            r += dr
            c += dc
            while 0 <= r < rows and 0 <= c < cols:
                if not board.is_cell_occupied(r, c):
                    prev = max_blocker.get((r, c), -1)
                    if p > prev:
                        max_blocker[(r, c)] = p
                r += dr
                c += dc

        def can_merge(cell: tuple[int, int], target: Arrow) -> bool:
            mb = max_blocker.get(cell, -1)
            if mb < 0:
                return True
            tp = pos_of.get(id(target), -1)
            return tp >= mb

        uncovered = [
            (r, c)
            for r in range(rows)
            for c in range(cols)
            if not board.is_cell_occupied(r, c)
        ]

        changed = True
        while changed and uncovered:
            changed = False
            still = []
            for r, c in uncovered:
                if board.is_cell_occupied(r, c):
                    continue
                merged = False
                for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    nr, nc = r + dr, c + dc
                    if not (0 <= nr < rows and 0 <= nc < cols):
                        continue
                    adj = board.get_arrow_at(nr, nc)
                    if adj is None:
                        continue
                    if adj.cells[0] == (nr, nc) and can_merge((r, c), adj):
                        adj.cells.insert(0, (r, c))
                        board._grid[r][c] = adj
                        merged = True
                        changed = True
                        break
                    if (
                        adj.cells[-1] == (nr, nc)
                        and can_merge((r, c), adj)
                        and self._extend_safe_head(adj, (r, c), rows, cols)
                    ):
                        board._grid[r][c] = adj
                        merged = True
                        changed = True
                        break
                if not merged:
                    still.append((r, c))
            uncovered = still

        if uncovered:
            still2 = []
            for r, c in uncovered:
                if board.is_cell_occupied(r, c):
                    continue
                merged = False
                for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    nr, nc = r + dr, c + dc
                    if not (0 <= nr < rows and 0 <= nc < cols):
                        continue
                    adj = board.get_arrow_at(nr, nc)
                    if adj is None:
                        continue
                    if not can_merge((r, c), adj):
                        continue
                    try:
                        k = adj.cells.index((nr, nc))
                    except ValueError:
                        continue
                    if k > 0:
                        pr, pc = adj.cells[k - 1]
                        if abs(r - pr) + abs(c - pc) == 1:
                            adj.cells.insert(k, (r, c))
                            board._grid[r][c] = adj
                            merged = True
                            break
                    if k < len(adj.cells) - 1:
                        xr, xc = adj.cells[k + 1]
                        if abs(r - xr) + abs(c - xc) == 1:
                            adj.cells.insert(k + 1, (r, c))
                            board._grid[r][c] = adj
                            merged = True
                            break
                if not merged:
                    still2.append((r, c))
            uncovered = still2

        changed = True
        while changed and uncovered:
            changed = False
            still4 = []
            for r, c in uncovered:
                if board.is_cell_occupied(r, c):
                    continue
                merged = False
                for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    nr, nc = r + dr, c + dc
                    if not (0 <= nr < rows and 0 <= nc < cols):
                        continue
                    adj = board.get_arrow_at(nr, nc)
                    if adj is None or not can_merge((r, c), adj):
                        continue
                    if (
                        self._extend_tail(adj, (r, c))
                        or self._extend_safe_head(adj, (r, c), rows, cols)
                        or self._splice_cell(adj, (r, c))
                    ):
                        board._grid[r][c] = adj
                        merged = True
                        changed = True
                        break
                if not merged:
                    still4.append((r, c))
            uncovered = still4

    def _fill_remaining(self, board: Board, rows: int, cols: int) -> None:
        """aggressively merge remaining uncovered cells (may break solvability)."""
        uncovered = [
            (r, c)
            for r in range(rows)
            for c in range(cols)
            if not board.is_cell_occupied(r, c)
        ]
        changed = True
        while changed and uncovered:
            changed = False
            still = []
            for r, c in uncovered:
                if board.is_cell_occupied(r, c):
                    continue
                if self._merge_remaining_cell(board, rows, cols, (r, c)):
                    changed = True
                else:
                    still.append((r, c))
            uncovered = still

    def _cover_remaining_by_endpoint_steal(
        self, board: Board, rows: int, cols: int
    ) -> None:
        changed = True
        while changed:
            changed = False
            uncovered = [
                (r, c)
                for r in range(rows)
                for c in range(cols)
                if not board.is_cell_occupied(r, c)
            ]
            for cell in uncovered:
                if board.is_cell_occupied(*cell):
                    continue
                if (
                    self._steal_endpoint_for_cell(board, rows, cols, cell)
                    or self._split_arrow_for_cell(board, rows, cols, cell)
                ):
                    changed = True

    def _steal_endpoint_for_cell(
        self,
        board: Board,
        rows: int,
        cols: int,
        cell: tuple[int, int],
    ) -> bool:
        r, c = cell
        candidates: list[tuple[Arrow, tuple[int, int], str]] = []
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            neighbour = (r + dr, c + dc)
            nr, nc = neighbour
            if not (0 <= nr < rows and 0 <= nc < cols):
                continue
            arrow = board.get_arrow_at(nr, nc)
            if arrow is None or len(arrow.cells) <= 2:
                continue
            if arrow.cells[0] == neighbour:
                candidates.append((arrow, neighbour, 'tail'))
            elif arrow.cells[-1] == neighbour:
                candidates.append((arrow, neighbour, 'head'))

        for arrow, stolen, endpoint in candidates:
            direction = self._direction_of(stolen, cell)
            if direction is None:
                continue

            new_head_dir = None
            if endpoint == 'head':
                new_head_dir = self._direction_of(arrow.cells[-3], arrow.cells[-2])
                if new_head_dir is None:
                    continue

            if endpoint == 'tail':
                arrow.cells.pop(0)
            else:
                arrow.cells.pop()
                arrow.direction = new_head_dir

            new_arrow = Arrow(cells=[stolen, cell], direction=direction)
            board._grid[stolen[0]][stolen[1]] = new_arrow
            board._grid[cell[0]][cell[1]] = new_arrow
            board._arrows.append(new_arrow)
            return True

        return False

    def _split_arrow_for_cell(
        self,
        board: Board,
        rows: int,
        cols: int,
        cell: tuple[int, int],
    ) -> bool:
        r, c = cell
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            stolen = (r + dr, c + dc)
            sr, sc = stolen
            if not (0 <= sr < rows and 0 <= sc < cols):
                continue
            arrow = board.get_arrow_at(sr, sc)
            if arrow is None or len(arrow.cells) <= 4:
                continue

            try:
                index = arrow.cells.index(stolen)
            except ValueError:
                continue
            if index == 0 or index == len(arrow.cells) - 1:
                continue

            left = arrow.cells[:index]
            right = arrow.cells[index + 1:]
            if len(left) == 1 or len(right) == 1:
                continue

            new_direction = self._direction_of(stolen, cell)
            if new_direction is None:
                continue

            replacements: list[Arrow] = []
            for segment in (left, right):
                if len(segment) < 2:
                    continue
                direction = self._direction_of(segment[-2], segment[-1])
                if direction is None:
                    replacements = []
                    break
                replacements.append(Arrow(cells=list(segment), direction=direction))
            if not replacements:
                continue

            arrow.alive = False
            for old_cell in arrow.cells:
                if board._grid[old_cell[0]][old_cell[1]] is arrow:
                    board._grid[old_cell[0]][old_cell[1]] = None

            for replacement in replacements:
                board.place_arrow(replacement)
            board.place_arrow(Arrow(cells=[stolen, cell], direction=new_direction))
            return True

        return False

    def _merge_remaining_cell(
        self,
        board: Board,
        rows: int,
        cols: int,
        cell: tuple[int, int],
    ) -> bool:
        r, c = cell
        candidates: list[Arrow] = []
        seen: set[int] = set()
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nr, nc = r + dr, c + dc
            if not (0 <= nr < rows and 0 <= nc < cols):
                continue
            adj = board.get_arrow_at(nr, nc)
            if adj is not None and id(adj) not in seen:
                candidates.append(adj)
                seen.add(id(adj))

        for adj in candidates:
            if self._extend_tail(adj, cell):
                board._grid[r][c] = adj
                return True

        for adj in candidates:
            if self._extend_head(adj, cell, rows, cols):
                board._grid[r][c] = adj
                return True

        for adj in candidates:
            if self._splice_cell(adj, cell):
                board._grid[r][c] = adj
                return True

        return False

    def _extend_tail(self, arrow: Arrow, cell: tuple[int, int]) -> bool:
        if self._are_adjacent(cell, arrow.cells[0]):
            arrow.cells.insert(0, cell)
            return True
        return False

    def _extend_head(
        self, arrow: Arrow, cell: tuple[int, int], rows: int, cols: int
    ) -> bool:
        if not self._are_adjacent(arrow.cells[-1], cell):
            return False
        new_dir = self._direction_of(arrow.cells[-1], cell)
        if new_dir is None:
            return False
        if self._is_border_exit(cell, new_dir, rows, cols):
            return False
        arrow.cells.append(cell)
        arrow.direction = new_dir
        return True

    def _extend_safe_head(
        self, arrow: Arrow, cell: tuple[int, int], rows: int, cols: int
    ) -> bool:
        if not self._are_adjacent(arrow.cells[-1], cell):
            return False
        new_dir = self._direction_of(arrow.cells[-1], cell)
        if new_dir != arrow.direction:
            return False
        if self._is_border_exit(cell, new_dir, rows, cols):
            return False
        arrow.cells.append(cell)
        return True

    def _splice_cell(self, arrow: Arrow, cell: tuple[int, int]) -> bool:
        for i in range(1, len(arrow.cells)):
            if (
                self._are_adjacent(arrow.cells[i - 1], cell)
                and self._are_adjacent(cell, arrow.cells[i])
            ):
                arrow.cells.insert(i, cell)
                return True
        return False

    def _are_adjacent(
        self, a: tuple[int, int], b: tuple[int, int]
    ) -> bool:
        return abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1

    def _clear_exit_orientation(
        self,
        walk: list[tuple[int, int]],
        board: Board,
        rows: int,
        cols: int,
    ) -> Arrow | None:
        best: tuple[bool, int, list[tuple[int, int]], Direction] | None = None
        for cells in (walk, list(reversed(walk))):
            d = self._direction_of(cells[-2], cells[-1])
            if d is None:
                continue
            dr, dc = DIRECTION_VECTORS[d]
            hr, hc = cells[-1]
            r, c = hr + dr, hc + dc
            clear = True
            dist = 0
            while 0 <= r < rows and 0 <= c < cols:
                if board.is_cell_occupied(r, c):
                    clear = False
                    break
                dist += 1
                r += dr
                c += dc
            if clear:
                border_exit = self._is_border_exit(cells[-1], d, rows, cols)
                option = (border_exit, dist, cells, d)
                if best is None or option[:2] < best[:2]:
                    best = option
        if best is None:
            return None
        _, _, cells, d = best
        if self._is_border_exit(cells[-1], d, rows, cols):
            return None
        return Arrow(cells=list(cells), direction=d)

    def _best_orientation(
        self,
        walk: list[tuple[int, int]],
        board: Board,
        rows: int,
        cols: int,
    ) -> Arrow | None:
        best_clear: tuple[int, list[tuple[int, int]], Direction] | None = None
        fallback: tuple[list[tuple[int, int]], Direction] | None = None
        for cells in (walk, list(reversed(walk))):
            d = self._direction_of(cells[-2], cells[-1])
            if d is None:
                continue
            if fallback is None:
                fallback = (cells, d)
            dr, dc = DIRECTION_VECTORS[d]
            hr, hc = cells[-1]
            r, c = hr + dr, hc + dc
            clear = True
            dist = 0
            while 0 <= r < rows and 0 <= c < cols:
                if board.is_cell_occupied(r, c):
                    clear = False
                    break
                dist += 1
                r += dr
                c += dc
            if clear:
                if best_clear is None or dist < best_clear[0]:
                    best_clear = (dist, cells, d)
        if best_clear is not None:
            _, cells, d = best_clear
            return Arrow(cells=list(cells), direction=d)
        if fallback is not None:
            cells, d = fallback
            return Arrow(cells=list(cells), direction=d)
        return None

    def _direction_of(
        self, prev: tuple[int, int], cur: tuple[int, int]
    ) -> Direction | None:
        dr = cur[0] - prev[0]
        dc = cur[1] - prev[1]
        for d, (vr, vc) in DIRECTION_VECTORS.items():
            if vr == dr and vc == dc:
                return d
        return None

    def _is_border_exit(
        self,
        head: tuple[int, int],
        direction: Direction,
        rows: int,
        cols: int,
    ) -> bool:
        dr, dc = DIRECTION_VECTORS[direction]
        r, c = head
        return not (0 <= r + dr < rows and 0 <= c + dc < cols)

    def _is_fully_covered(self, board: Board, rows: int, cols: int) -> bool:
        return self._covered_cell_count(board, rows, cols) == rows * cols

    def _covered_cell_count(self, board: Board, rows: int, cols: int) -> int:
        return sum(
            1
            for r in range(rows)
            for c in range(cols)
            if board._grid[r][c] is not None
        )

    def _pick_length(self, lo: int, hi: int, rng: random.Random) -> int:
        lo = max(lo, 2)
        if hi < lo:
            return lo
        if lo == hi:
            return lo
        if rng.random() < 0.20:
            return rng.randint(lo, hi)
        center = (lo + hi * 2) // 3
        center = max(center, lo + 2)
        center = min(center, hi)
        spread = max(4, (hi - lo) // 3)
        for _ in range(50):
            length = int(rng.gauss(center, spread) + 0.5)
            if lo <= length <= hi:
                return length
        return rng.randint(lo, hi)

    def _fallback(self, rows: int, cols: int) -> tuple[Board, list[Arrow]]:
        board = Board(rows, cols)
        arrows: list[Arrow] = []
        for r in range(rows):
            c = 0
            while c < cols:
                end = min(c + 3, cols)
                if end - c < 2:
                    end = c + 2
                end = min(end, cols)
                if end - c < 2:
                    if arrows:
                        prev = arrows[-1]
                        prev.cells.append((r, c))
                        board._grid[r][c] = prev
                    c = end
                    continue
                cells = [(r, ci) for ci in range(c, end)]
                arrow = Arrow(cells=cells, direction=Direction.RIGHT)
                board.place_arrow(arrow)
                arrows.append(arrow)
                c = end
        order = list(reversed(arrows))
        return board, order
