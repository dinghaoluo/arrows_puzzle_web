"""Pre-generate all puzzle levels to disk for instant loading."""
from __future__ import annotations
from dataclasses import dataclass
import json
import sys
import time
import random
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from game.puzzle_generator import PuzzleGenerator
from game.puzzle_data import save_puzzle
from game.direction import DIRECTION_VECTORS


MAX_GENERATED_LEVEL = 50


@dataclass
class LevelConfig:
    grid_rows: int
    grid_cols: int
    min_arrow_length: int
    max_arrow_length: int


LEVEL_CONFIGS = [
    (60, 80, 2, 15), (70, 90, 2, 15), (80, 80, 2, 18),
    (90, 110, 2, 18), (100, 100, 2, 20), (100, 120, 2, 20),
    (110, 110, 2, 22), (120, 140, 2, 22), (130, 130, 2, 25),
    (140, 140, 2, 25), (140, 170, 2, 25), (150, 150, 2, 25),
    (160, 190, 2, 28), (170, 170, 2, 28), (180, 180, 2, 28),
    (180, 220, 2, 30), (200, 200, 2, 30), (200, 240, 2, 30),
    (220, 220, 2, 30), (230, 230, 2, 30), (232, 232, 2, 31),
    (235, 235, 2, 31), (238, 238, 2, 32), (240, 240, 2, 32),
    (242, 248, 2, 32), (245, 245, 2, 33), (248, 248, 2, 33),
    (250, 255, 2, 33), (252, 252, 2, 34), (255, 255, 2, 34),
    (258, 258, 2, 34), (260, 265, 2, 35), (262, 262, 2, 35),
    (265, 265, 2, 35), (268, 268, 2, 36), (270, 275, 2, 36),
    (272, 272, 2, 36), (275, 275, 2, 37), (278, 278, 2, 37),
    (280, 285, 2, 37), (282, 282, 2, 38), (285, 285, 2, 38),
    (288, 288, 2, 38), (290, 295, 2, 39), (292, 292, 2, 39),
    (295, 295, 2, 39), (296, 300, 2, 40), (298, 298, 2, 40),
    (300, 300, 2, 40), (300, 300, 2, 40),
]


def get_max_level() -> int:
    return len(LEVEL_CONFIGS)


def get_level_config(level: int) -> LevelConfig:
    rows, cols, min_len, max_len = LEVEL_CONFIGS[level - 1]
    return LevelConfig(rows, cols, min_len, max_len)


DIR_CODES = {
    'up': 0,
    'down': 1,
    'left': 2,
    'right': 3,
}

MOVE_CODES = {
    (-1, 0): 'U',
    (1, 0): 'D',
    (0, -1): 'L',
    (0, 1): 'R',
}


def save_web_json(level: int, board, solution, dest_dir: Path) -> Path:
    arrows_data = []
    for arrow in board.living_arrows():
        cells = arrow.cells
        start_r, start_c = cells[0]
        moves = []
        for prev, cur in zip(cells, cells[1:]):
            moves.append(MOVE_CODES[(cur[0] - prev[0], cur[1] - prev[1])])
        arrows_data.append(
            [
                DIR_CODES[arrow.direction.value],
                start_r * board.cols + start_c,
                ''.join(moves),
            ]
        )
    data = {
        'v': 2,
        'rows': board.rows,
        'cols': board.cols,
        'arrows': arrows_data,
    }
    path = dest_dir / f"level_{level:03d}.json"
    path.write_text(json.dumps(data, separators=(',', ':')), encoding='utf-8')
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
