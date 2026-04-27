## imports
from __future__ import annotations
from functools import lru_cache
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

        return self._build_tiled_puzzle(rows, cols, min_length, max_length, rng)

    def _build_tiled_puzzle(
        self,
        rows: int,
        cols: int,
        min_length: int,
        max_length: int,
        rng: random.Random,
    ) -> tuple[Board, list[Arrow]]:
        board = Board(rows, cols)
        solution: list[Arrow] = []

        r = 0
        band_index = 0
        while r < rows:
            band_height = self._pick_band_height(rows - r, rng)
            max_width = max(2, max_length // band_height)
            widths = self._partition_widths(cols, max_width, rng)
            exit_dir = (
                Direction.LEFT
                if (band_index + rng.randint(0, 1)) % 2 == 0
                else Direction.RIGHT
            )

            c = 0
            band_arrows: list[Arrow] = []
            for width in widths:
                # keep escape arrows from advertising the solution on the border.
                inset_exit = (
                    (exit_dir == Direction.LEFT and c == 0)
                    or (exit_dir == Direction.RIGHT and c + width == cols)
                )
                cells = self._serpentine_cells(
                    r, band_height, c, width, exit_dir, inset_exit
                )
                direction = self._direction_of(cells[-2], cells[-1])
                if direction is None:
                    direction = exit_dir
                arrow = Arrow(cells=cells, direction=direction)
                board.place_arrow(arrow)
                band_arrows.append(arrow)
                c += width

            if exit_dir == Direction.LEFT:
                solution.extend(band_arrows)
            else:
                solution.extend(reversed(band_arrows))

            r += band_height
            band_index += 1

        return board, solution

    def _pick_band_height(self, remaining_rows: int, rng: random.Random) -> int:
        if remaining_rows <= 2:
            return remaining_rows
        if remaining_rows == 3:
            return 3
        band_height = 4 if rng.random() < 0.35 else 2
        if remaining_rows - band_height == 1:
            return 2
        return min(band_height, remaining_rows)

    def _partition_widths(
        self, cols: int, max_width: int, rng: random.Random
    ) -> list[int]:
        if max_width >= 3 and cols >= 6:
            middle_total = cols - 6
            if middle_total == 1 and max_width >= 4:
                return [4, 3]
            if middle_total != 1:
                return [3] + self._partition_inner_widths(
                    middle_total, max_width, rng
                ) + [3]

        return self._partition_inner_widths(cols, max_width, rng)

    def _partition_inner_widths(
        self, cols: int, max_width: int, rng: random.Random
    ) -> list[int]:
        widths: list[int] = []
        remaining = cols
        max_width = max(2, max_width)

        while remaining:
            if remaining <= max_width:
                if remaining == 1 and widths:
                    widths[-1] -= 1
                    widths.append(2)
                else:
                    widths.append(remaining)
                break

            high = min(max_width, remaining - 2)
            width = rng.randint(2, high)
            if remaining - width == 1:
                width += 1
            widths.append(width)
            remaining -= width

        return widths

    def _serpentine_cells(
        self,
        row: int,
        height: int,
        col: int,
        width: int,
        exit_dir: Direction,
        inset_exit: bool = False,
    ) -> list[tuple[int, int]]:
        if inset_exit and height >= 2 and width >= 3:
            shape = self._inset_exit_shape(height, width, exit_dir)
            if shape:
                return [(row + r, col + c) for r, c in shape]

        exit_left = exit_dir == Direction.LEFT
        left_to_right = exit_left if height % 2 == 0 else not exit_left
        cells: list[tuple[int, int]] = []

        for r in range(row, row + height):
            if left_to_right:
                cells.extend((r, c) for c in range(col, col + width))
            else:
                cells.extend((r, c) for c in range(col + width - 1, col - 1, -1))
            left_to_right = not left_to_right

        return cells

    def _inset_exit_shape(
        self, height: int, width: int, exit_dir: Direction
    ) -> tuple[tuple[int, int], ...]:
        left_shape = self._inset_left_shape(height, width)
        if exit_dir == Direction.LEFT:
            return left_shape
        return tuple((r, width - 1 - c) for r, c in left_shape)

    def _inset_left_shape(
        self, height: int, width: int
    ) -> tuple[tuple[int, int], ...]:
        if height % 2 == 0:
            cells: list[tuple[int, int]] = [
                (r, 0) for r in range(height - 1, -1, -1)
            ]
            left_to_right = True
            for r in range(height):
                if left_to_right:
                    cells.extend((r, c) for c in range(1, width))
                else:
                    cells.extend((r, c) for c in range(width - 1, 0, -1))
                left_to_right = not left_to_right
            return tuple(cells)

        return self._searched_inset_left_shape(height, width)

    @staticmethod
    @lru_cache(maxsize=None)
    def _searched_inset_left_shape(
        height: int, width: int
    ) -> tuple[tuple[int, int], ...]:
        cells = {(r, c) for r in range(height) for c in range(width)}
        dirs = [(-1, 0), (1, 0), (0, -1), (0, 1)]

        def neighbours(
            cell: tuple[int, int], unvisited: set[tuple[int, int]]
        ) -> list[tuple[int, int]]:
            r, c = cell
            result = [
                (r + dr, c + dc)
                for dr, dc in dirs
                if (r + dr, c + dc) in unvisited
            ]
            result.sort(
                key=lambda n: sum(
                    (n[0] + dr, n[1] + dc) in unvisited for dr, dc in dirs
                )
            )
            return result

        for end_row in range(height):
            end = (end_row, 1)
            prev = (end_row, 2)
            for start in sorted(cells):
                if start in (end, prev):
                    continue
                path = [start]
                unvisited = set(cells)
                unvisited.remove(start)

                def dfs(cur: tuple[int, int]) -> bool:
                    if len(path) == height * width:
                        return cur == end and path[-2] == prev

                    for nxt in neighbours(cur, unvisited):
                        if nxt == end and len(path) != height * width - 1:
                            continue
                        if nxt == prev and len(path) != height * width - 2:
                            continue
                        unvisited.remove(nxt)
                        path.append(nxt)
                        if dfs(nxt):
                            return True
                        path.pop()
                        unvisited.add(nxt)
                    return False

                if dfs(start):
                    return tuple(path)

        return ()

    def _generate_attempted_walk_puzzle(
        self,
        rows: int,
        cols: int,
        min_length: int,
        max_length: int,
        rng: random.Random,
    ) -> tuple[Board, list[Arrow]]:
        for _ in range(MAX_ATTEMPTS):
            result = self._build_puzzle(rows, cols, min_length, max_length, rng)
            if result is not None:
                return result

        return self._fallback(rows, cols)

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

        center_r, center_c = rows / 2.0, cols / 2.0
        all_cells = [(r, c) for r in range(rows) for c in range(cols)]
        bands: dict[int, list[tuple[int, int]]] = {}
        for r, c in all_cells:
            d = int(max(abs(r - center_r), abs(c - center_c)))
            bands.setdefault(d, []).append((r, c))
        ordered: list[tuple[int, int]] = []
        for d in sorted(bands):
            g = bands[d]
            rng.shuffle(g)
            ordered.extend(g)

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

        self._fill_remaining(board, rows, cols)
        all_arrows = list(board.living_arrows())
        solver_order = self._solve(board)
        if (
            solver_order is not None
            and len(solver_order) == len(all_arrows)
            and self._is_fully_covered(board, rows, cols)
        ):
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

        if not self._is_fully_covered(board, rows, cols):
            return None

        return board, list(reversed(placement))

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
                        and self._extend_safe_head(adj, (r, c))
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

        if uncovered:
            still3 = []
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
                    if self._insert_safe_spur_cell(adj, (r, c)):
                        board._grid[r][c] = adj
                        merged = True
                        break
                if not merged:
                    still3.append((r, c))
            uncovered = still3

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
                        or self._extend_safe_head(adj, (r, c))
                        or self._splice_cell(adj, (r, c))
                        or self._insert_safe_spur_cell(adj, (r, c))
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
            if self._extend_head(adj, cell):
                board._grid[r][c] = adj
                return True

        for adj in candidates:
            if self._splice_cell(adj, cell):
                board._grid[r][c] = adj
                return True

        for adj in candidates:
            if self._insert_spur_cell(adj, cell):
                board._grid[r][c] = adj
                return True

        return False

    def _extend_tail(self, arrow: Arrow, cell: tuple[int, int]) -> bool:
        if self._are_adjacent(cell, arrow.cells[0]):
            arrow.cells.insert(0, cell)
            return True
        return False

    def _extend_head(self, arrow: Arrow, cell: tuple[int, int]) -> bool:
        if not self._are_adjacent(arrow.cells[-1], cell):
            return False
        new_dir = self._direction_of(arrow.cells[-1], cell)
        if new_dir is None:
            return False
        arrow.cells.append(cell)
        arrow.direction = new_dir
        return True

    def _extend_safe_head(self, arrow: Arrow, cell: tuple[int, int]) -> bool:
        if not self._are_adjacent(arrow.cells[-1], cell):
            return False
        new_dir = self._direction_of(arrow.cells[-1], cell)
        if new_dir != arrow.direction:
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

    def _insert_spur_cell(self, arrow: Arrow, cell: tuple[int, int]) -> bool:
        for i, anchor in enumerate(arrow.cells):
            if not self._are_adjacent(anchor, cell):
                continue
            arrow.cells[i + 1:i + 1] = [cell, anchor]
            if i == len(arrow.cells) - 3:
                new_dir = self._direction_of(cell, anchor)
                if new_dir is not None:
                    arrow.direction = new_dir
            return True
        return False

    def _insert_safe_spur_cell(
        self, arrow: Arrow, cell: tuple[int, int]
    ) -> bool:
        for i, anchor in enumerate(arrow.cells[:-1]):
            if not self._are_adjacent(anchor, cell):
                continue
            arrow.cells[i + 1:i + 1] = [cell, anchor]
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
