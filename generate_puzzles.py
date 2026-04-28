"""Pre-generate all puzzle levels to disk for instant loading."""
from __future__ import annotations
import json
import sys
import time
import random
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from game.level_config import get_level_config, get_max_level
from game.puzzle_generator import PuzzleGenerator
from game.puzzle_data import save_puzzle
from game.direction import DIRECTION_VECTORS


MAX_GENERATED_LEVEL = 20


def save_web_json(level: int, board, solution, dest_dir: Path) -> Path:
    arrows_data = []
    arrow_id_map = {}
    for i, arrow in enumerate(board.living_arrows()):
        arrows_data.append({"cells": arrow.cells, "dir": arrow.direction.value})
        arrow_id_map[id(arrow)] = i
    data = {
        "rows": board.rows,
        "cols": board.cols,
        "arrows": arrows_data,
        "solution": [arrow_id_map[id(a)] for a in solution],
    }
    path = dest_dir / f"level_{level:03d}.json"
    path.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    return path


def verify_solution(board, solution) -> bool:
    from game.board import Board
    b = Board(board.rows, board.cols)
    all_arrows = list(board.living_arrows())
    for a in all_arrows:
        a.alive = True
        b.place_arrow(a)
    result = True
    for arrow in solution:
        if not arrow.alive:
            result = False
            break
        dr, dc = DIRECTION_VECTORS[arrow.direction]
        r, c = arrow.cells[-1]
        r += dr
        c += dc
        while 0 <= r < b.rows and 0 <= c < b.cols:
            occ = b._grid[r][c]
            if occ is not None and occ is not arrow and occ.alive:
                result = False
                break
            r += dr
            c += dc
        if not result:
            break
        b.remove_arrow(arrow)
    for a in all_arrows:
        a.alive = True
    return result


def main() -> None:
    root = Path(__file__).resolve().parent
    dest_gz = root / "puzzles"
    dest_web = root / "docs" / "puzzles"
    dest_gz.mkdir(parents=True, exist_ok=True)
    dest_web.mkdir(parents=True, exist_ok=True)

    gen = PuzzleGenerator()
    max_level = min(get_max_level(), MAX_GENERATED_LEVEL)
    total_time = 0.0

    for level in range(1, max_level + 1):
        config = get_level_config(level)
        seed = 1000 + level
        rng = random.Random(seed)

        t0 = time.time()
        board, solution = gen.generate(
            config.grid_rows,
            config.grid_cols,
            config.min_arrow_length,
            config.max_arrow_length,
            rng=rng,
        )
        elapsed = time.time() - t0
        total_time += elapsed

        ok = verify_solution(board, solution)
        save_puzzle(level, board, solution, dest_dir=dest_gz)
        web_path = save_web_json(level, board, solution, dest_web)

        arrow_count = len(board.living_arrows())
        total_cells = len(
            {
                cell
                for arrow in board.living_arrows()
                for cell in arrow.cells
            }
        )
        grid_cells = config.grid_rows * config.grid_cols
        coverage = 100 * total_cells / grid_cells
        size_kb = web_path.stat().st_size / 1024

        print(
            f"Level {level:2d}: {config.grid_rows}x{config.grid_cols} "
            f"| {arrow_count:5d} arrows | cov={coverage:5.1f}% "
            f"| {'OK' if ok else 'FAIL'} | {elapsed:6.1f}s | {size_kb:.0f}KB"
        )

    print(f"\nDone. {max_level} levels generated in {total_time:.1f}s")
    print(f"Output: {dest_gz} + {dest_web}")


if __name__ == "__main__":
    main()
