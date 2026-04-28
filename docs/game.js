// Arrows - Puzzle Escape: HTML5 Canvas port
"use strict";

// Constants
const BG_COLOR = "#fafafc";
const GRID_DOT_COLOR = "#d2d2d7";
const ARROW_COLOR = "#2d3446";
const ARROW_ERROR_COLOR = "#dc3737";
const ARROW_FLY_COLOR = "#b4b9c3";
const HEART_COLOR = "#dc3741";
const HEART_EMPTY_COLOR = "#d7d7dc";
const HUD_TEXT_COLOR = "#646973";
const LEVEL_COMPLETE_COLOR = "#37b45a";
const LEVEL_COMPLETED_BTN = "#37b45a";
const LEVEL_UNLOCKED_BTN = "#505a6e";
const LEVEL_LOCKED_BTN = "#b4b4b9";
const FUN_BUTTON_COLOR = "#8a4dd8";
const FUN_PARTICLE_GRAVITY = 42;

const ARROW_HEAD_SIZE = 0.5;
const ARROW_CORNER_RADIUS_RATIO = 0.22;
const HUD_HEIGHT = 54;
const CELL_SIZE_WORLD = 8;
const DRAG_THRESHOLD = 5;
const TOUCH_DRAG_THRESHOLD = 15;
const MIN_ZOOM = 0.05;
const MAX_ZOOM = 5.0;
const ZOOM_STEP = 1.15;
const ERROR_FLASH_DURATION = 0.5;
const FLY_OFF_DURATION = 0.6;
const GRID_DOT_REVEAL_DURATION = 0.45;
const MAX_LEVEL = 54;
const EASY_LIVES = 5;
const HARD_LIVES = 3;
const EASY_MISTAKE_PENALTY = 5;
const HARD_MISTAKE_PENALTY = 12;
const HARD_PAR_MULTIPLIER = 0.7;

const LEVEL_BTN_SIZE = 52;
const LEVEL_BTN_GAP = 14;
const LEVEL_BTN_COLS = 6;
const LEVEL_SELECT_TOP = 90;

const DIRECTION_VECTORS = { up: [-1, 0], down: [1, 0], left: [0, -1], right: [0, 1] };
const DIRECTION_NAMES = ["up", "down", "left", "right"];
const DIRECTION_ANGLES = { right: 0, up: -Math.PI / 2, left: Math.PI, down: Math.PI / 2 };
const MOVE_DELTAS = { U: [-1, 0], D: [1, 0], L: [0, -1], R: [0, 1] };
const PUZZLE_CACHE = new Map();
const FUN_COLORS = ["#2f78d4", "#00856f", "#d85c34", "#b63f78", "#6c55cf", "#12829a", "#a46414"];

const LEVEL_CONFIGS = [
  null, // index 0 unused
  [60,80],[70,90],[80,80],[90,110],[100,100],
  [100,120],[110,110],[120,140],[130,130],[140,140],
  [140,170],[150,150],[160,190],[170,170],[180,180],
  [180,220],[200,200],[200,240],[220,220],[230,230],
  [232,232],[235,235],[238,238],[240,240],[242,248],
  [245,245],[248,248],[250,255],[252,252],[255,255],
  [258,258],[260,265],[262,262],[265,265],[268,268],
  [270,275],[272,272],[275,275],[278,278],[280,285],
  [282,282],[285,285],[288,288],[290,295],[292,292],
  [295,295],[296,300],[298,298],[300,300],[300,300],
  [300,300],[300,300],[300,300],[300,300],
];

function funColorForArrow(cells, direction) {
  const tail = cells[0] || [0, 0];
  const mid = cells[Math.floor(cells.length / 2)] || tail;
  const head = cells[cells.length - 1] || tail;
  const dir = DIRECTION_NAMES.indexOf(direction) + 1;
  const hash = (
    cells.length * 131 +
    tail[0] * 17 + tail[1] * 29 +
    mid[0] * 41 + mid[1] * 47 +
    head[0] * 59 + head[1] * 67 +
    dir * 83
  );
  return FUN_COLORS[Math.abs(hash) % FUN_COLORS.length];
}

// Phase enum
const Phase = {
  MAIN_MENU: 0,
  LEVEL_SELECT: 1,
  PLAYING: 2,
  ANIMATING: 3,
  LEVEL_COMPLETE: 4,
  GAME_OVER: 5,
};

// Arrow
class Arrow {
  constructor(cells, direction) {
    this.cells = cells;
    this.direction = direction;
    this.alive = true;
    this.errorTimer = 0;
    this.flyProgress = 0;
    this.animatingFlyOff = false;
    this._smoothWorld = null;
    this.funColor = funColorForArrow(cells, direction);
  }
  get head() { return this.cells[this.cells.length - 1]; }
  get tail() { return this.cells[0]; }
  smoothWorld(cr) {
    if (this._smoothWorld) return this._smoothWorld;
    const cs = CELL_SIZE_WORLD;
    const centers = this.cells.map(([r, c]) => [c * cs + cs / 2, r * cs + cs / 2]);
    this._smoothWorld = cr > 0 ? smoothPolyline(centers, cr) : centers;
    return this._smoothWorld;
  }
}

// Board
class Board {
  constructor(rows, cols) {
    this.rows = rows;
    this.cols = cols;
    this._grid = Array.from({ length: rows }, () => new Array(cols).fill(null));
    this._arrows = [];
    this._aliveCount = 0;
  }

  placeArrow(arrow) {
    this._arrows.push(arrow);
    this._aliveCount++;
    for (const [r, c] of arrow.cells) {
      this._grid[r][c] = arrow;
    }
  }

  removeArrow(arrow) {
    if (!arrow.alive) return;
    arrow.alive = false;
    this._aliveCount--;
    for (const [r, c] of arrow.cells) {
      if (this._grid[r][c] === arrow) this._grid[r][c] = null;
    }
  }

  getArrowAt(row, col) {
    if (row < 0 || row >= this.rows || col < 0 || col >= this.cols) return null;
    const a = this._grid[row][col];
    return (a && a.alive) ? a : null;
  }

  livingArrows() { return this._arrows.filter(a => a.alive); }
  isEmpty() { return this._aliveCount === 0; }

  arrowsInRegion(minR, maxR, minC, maxC) {
    const seen = new Set();
    const result = [];
    const r0 = Math.max(0, minR), r1 = Math.min(this.rows, maxR);
    const c0 = Math.max(0, minC), c1 = Math.min(this.cols, maxC);
    for (let r = r0; r < r1; r++) {
      for (let c = c0; c < c1; c++) {
        const a = this._grid[r][c];
        if (a && a.alive && !seen.has(a)) {
          seen.add(a);
          result.push(a);
        }
      }
    }
    return result;
  }

  isPathClear(arrow) {
    const [dr, dc] = DIRECTION_VECTORS[arrow.direction];
    let [r, c] = arrow.head;
    r += dr; c += dc;
    while (r >= 0 && r < this.rows && c >= 0 && c < this.cols) {
      const occ = this._grid[r][c];
      if (occ && occ.alive && !occ.animatingFlyOff) return false;
      r += dr; c += dc;
    }
    return true;
  }
}

function decodeArrows(data) {
  if (data.v === 2) {
    const arrows = new Array(data.arrows.length);
    for (let i = 0; i < data.arrows.length; i++) {
      const [dirCode, start, moves] = data.arrows[i];
      const cells = new Array(moves.length + 1);
      let r = Math.floor(start / data.cols);
      let c = start - r * data.cols;
      cells[0] = [r, c];
      for (let j = 0; j < moves.length; j++) {
        const [dr, dc] = MOVE_DELTAS[moves[j]];
        r += dr; c += dc;
        cells[j + 1] = [r, c];
      }
      arrows[i] = new Arrow(cells, DIRECTION_NAMES[dirCode]);
    }
    return arrows;
  }

  return data.arrows.map(ad => new Arrow(ad.cells.map(c => [c[0], c[1]]), ad.dir));
}

function puzzleUrl(level) {
  const pad = String(level).padStart(3, "0");
  return `puzzles/level_${pad}.json`;
}

async function loadPuzzleData(level) {
  if (PUZZLE_CACHE.has(level)) return PUZZLE_CACHE.get(level);
  const resp = await fetch(puzzleUrl(level));
  const data = await resp.json();
  PUZZLE_CACHE.set(level, data);
  return data;
}

function prefetchLevel(level) {
  if (level > MAX_LEVEL || PUZZLE_CACHE.has(level)) return;
  loadPuzzleData(level).catch(() => {});
}

// Camera
class Camera {
  constructor() { this.reset(); }

  reset() {
    this.ox = 0; this.oy = 0; this.zoom = 1;
    this._dragging = false;
    this._dragStart = [0, 0];
    this._dragOfs = [0, 0];
    this._dragMoved = 0;
  }

  centerOnGrid(rows, cols, sw, sh) {
    const gw = cols * CELL_SIZE_WORLD;
    const gh = rows * CELL_SIZE_WORLD;
    const availH = sh - HUD_HEIGHT;
    const fit = Math.min(sw / gw, availH / gh) * 0.92;
    this.zoom = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, fit));
    this.ox = (sw - gw * this.zoom) / 2;
    this.oy = HUD_HEIGHT + (availH - gh * this.zoom) / 2;
  }

  w2s(wx, wy) { return [wx * this.zoom + this.ox, wy * this.zoom + this.oy]; }
  s2w(sx, sy) { return [(sx - this.ox) / this.zoom, (sy - this.oy) / this.zoom]; }

  startDrag(x, y) {
    this._dragging = true;
    this._dragStart = [x, y];
    this._dragOfs = [this.ox, this.oy];
    this._dragMoved = 0;
  }

  updateDrag(x, y) {
    if (!this._dragging) return;
    const dx = x - this._dragStart[0], dy = y - this._dragStart[1];
    this._dragMoved = Math.hypot(dx, dy);
    this.ox = this._dragOfs[0] + dx;
    this.oy = this._dragOfs[1] + dy;
  }

  endDrag() {
    this._dragging = false;
    return this._dragMoved < DRAG_THRESHOLD;
  }

  get isDragging() { return this._dragging; }

  applyZoom(dir, mx, my) {
    const old = this.zoom;
    this.zoom = dir > 0
      ? Math.min(MAX_ZOOM, this.zoom * ZOOM_STEP)
      : Math.max(MIN_ZOOM, this.zoom / ZOOM_STEP);
    const r = this.zoom / old;
    this.ox = mx - (mx - this.ox) * r;
    this.oy = my - (my - this.oy) * r;
  }

  visibleRange(rows, cols, sw, sh) {
    const [wx0, wy0] = this.s2w(0, 0);
    const [wx1, wy1] = this.s2w(sw, sh);
    const cs = CELL_SIZE_WORLD;
    const m = 2;
    return [
      Math.max(0, Math.floor(wy0 / cs) - m),
      Math.min(rows, Math.ceil(wy1 / cs) + m),
      Math.max(0, Math.floor(wx0 / cs) - m),
      Math.min(cols, Math.ceil(wx1 / cs) + m),
    ];
  }
}

// Game Controller
class GameController {
  constructor() {
    this.phase = Phase.MAIN_MENU;
    this.currentLevel = 1;
    this.hardMode = localStorage.getItem("arrows_mode") === "hard";
    this.funMode = localStorage.getItem("arrows_fun") === "on";
    this.maxLives = this.hardMode ? HARD_LIVES : EASY_LIVES;
    this.lives = this.maxLives;
    this.totalMistakes = 0;
    this.board = null;
    this.completedLevels = new Set();
    this.maxLevelUnlocked = MAX_LEVEL;
    this.elapsedTime = 0;
    this.score = 0;
    this.combo = 0;
    this.totalArrows = 0;
    this.removedArrows = 0;
    this.funBursts = [];
    this.revealingDots = new Map();
    this.levelStars = {};
    this._loadProgress();
  }

  _progressKey() {
    return this.hardMode ? "arrows_save_hard" : "arrows_save_easy";
  }

  _loadProgress() {
    try {
      const d = JSON.parse(localStorage.getItem(this._progressKey()) || "{}");
      if (d.completed_levels) d.completed_levels.forEach(l => this.completedLevels.add(l));
      if (d.max_level_unlocked) this.maxLevelUnlocked = Math.max(this.maxLevelUnlocked, d.max_level_unlocked);
      if (d.level_stars) this.levelStars = d.level_stars;
    } catch (e) { /* ignore */ }
  }

  _saveProgress() {
    try {
      localStorage.setItem(this._progressKey(), JSON.stringify({
        completed_levels: [...this.completedLevels].sort((a, b) => a - b),
        max_level_unlocked: this.maxLevelUnlocked,
        level_stars: this.levelStars,
      }));
    } catch (e) { /* ignore */ }
  }

  toggleMode() {
    this._saveProgress();
    this.hardMode = !this.hardMode;
    localStorage.setItem("arrows_mode", this.hardMode ? "hard" : "easy");
    this.maxLives = this.hardMode ? HARD_LIVES : EASY_LIVES;
    this.lives = this.maxLives;
    this.completedLevels = new Set();
    this.maxLevelUnlocked = MAX_LEVEL;
    this.levelStars = {};
    this._loadProgress();
  }

  toggleFun() {
    this.funMode = !this.funMode;
    localStorage.setItem("arrows_fun", this.funMode ? "on" : "off");
  }

  async startLevel(level) {
    this.currentLevel = level;
    this.lives = this.maxLives;
    this.elapsedTime = 0;
    this.score = 0;
    this.combo = 0;
    this.removedArrows = 0;
    this.funBursts = [];
    this.revealingDots.clear();
    this.phase = Phase.PLAYING;

    try {
      const data = await loadPuzzleData(level);
      this.board = new Board(data.rows, data.cols);
      const arrows = decodeArrows(data);
      for (const a of arrows) {
        this.board.placeArrow(a);
      }
      this.totalArrows = arrows.length;
      prefetchLevel(level + 1);
    } catch (e) {
      console.error("Failed to load level", level, e);
    }
  }

  handleClick(row, col) {
    if ((this.phase !== Phase.PLAYING && this.phase !== Phase.ANIMATING) || !this.board) return;
    const arrow = this.board.getArrowAt(row, col);
    if (!arrow || !arrow.alive || arrow.animatingFlyOff) return;

    if (this.board.isPathClear(arrow)) {
      arrow.animatingFlyOff = true;
      arrow.flyProgress = 0;
      this.combo++;
      const multiplier = Math.min(this.combo, 5);
      this.score += 100 * multiplier;
      this.removedArrows++;
      this._spawnArrowBurst(arrow);
      this.phase = Phase.ANIMATING;
    } else {
      arrow.errorTimer = ERROR_FLASH_DURATION;
      this.lives--;
      this.totalMistakes++;
      this.combo = 0;
      this.elapsedTime += this.hardMode ? HARD_MISTAKE_PENALTY : EASY_MISTAKE_PENALTY;
      if (this.lives <= 0) this.phase = Phase.GAME_OVER;
    }
  }

  _parTime() {
    const cfg = LEVEL_CONFIGS[this.currentLevel];
    if (!cfg) return 120;
    return Math.round((cfg[0] * cfg[1]) / 40);
  }

  _computeStars() {
    const par = this._parTime();
    const target = this.hardMode ? par * HARD_PAR_MULTIPLIER : par;
    if (this.elapsedTime <= target) return 3;
    if (this.elapsedTime <= target * 2) return 2;
    return 1;
  }

  _spawnArrowBurst(arrow) {
    if (!this.funMode) return;
    const [dr, dc] = DIRECTION_VECTORS[arrow.direction];
    const [r, c] = arrow.head;
    const x = (c + 0.5) * CELL_SIZE_WORLD;
    const y = (r + 0.5) * CELL_SIZE_WORLD;
    for (let i = 0; i < 12; i++) {
      const angle = Math.random() * Math.PI * 2;
      const speed = 18 + Math.random() * 44;
      this.funBursts.push({
        x, y,
        vx: Math.cos(angle) * speed + dc * 18,
        vy: Math.sin(angle) * speed + dr * 18,
        age: 0,
        ttl: 0.38 + Math.random() * 0.28,
        size: 1.8 + Math.random() * 1.8,
        color: FUN_COLORS[(i + this.removedArrows) % FUN_COLORS.length],
      });
    }
  }

  _spawnLevelBurst() {
    if (!this.funMode || !this.board) return;
    const cx = this.board.cols * CELL_SIZE_WORLD / 2;
    const cy = this.board.rows * CELL_SIZE_WORLD / 2;
    const spreadX = Math.min(this.board.cols * CELL_SIZE_WORLD * 0.22, 180);
    const spreadY = Math.min(this.board.rows * CELL_SIZE_WORLD * 0.22, 180);
    for (let i = 0; i < 70; i++) {
      const angle = Math.random() * Math.PI * 2;
      const speed = 42 + Math.random() * 92;
      this.funBursts.push({
        x: cx + (Math.random() - 0.5) * spreadX,
        y: cy + (Math.random() - 0.5) * spreadY,
        vx: Math.cos(angle) * speed,
        vy: Math.sin(angle) * speed - 36,
        age: 0,
        ttl: 0.85 + Math.random() * 0.45,
        size: 2.4 + Math.random() * 2.2,
        color: FUN_COLORS[i % FUN_COLORS.length],
      });
    }
  }

  _updateFunBursts(dt) {
    if (this.funBursts.length === 0) return false;
    const kept = [];
    for (const p of this.funBursts) {
      p.age += dt;
      if (p.age >= p.ttl) continue;
      p.vy += FUN_PARTICLE_GRAVITY * dt;
      p.x += p.vx * dt;
      p.y += p.vy * dt;
      kept.push(p);
    }
    this.funBursts = kept;
    return this.funBursts.length > 0;
  }

  _queueDotReveal(arrow) {
    for (const [r, c] of arrow.cells) {
      this.revealingDots.set(`${r},${c}`, { r, c, age: 0 });
    }
  }

  _updateDotReveals(dt) {
    if (this.revealingDots.size === 0) return false;
    for (const [key, dot] of this.revealingDots) {
      dot.age += dt;
      if (dot.age >= GRID_DOT_REVEAL_DURATION) {
        this.revealingDots.delete(key);
      }
    }
    return this.revealingDots.size > 0;
  }

  update(dt) {
    if (!this.board) return false;
    const timerActive = this.phase === Phase.PLAYING || this.phase === Phase.ANIMATING;
    if (timerActive) this.elapsedTime += dt;
    let anyAnim = false;
    for (const a of this.board._arrows) {
      if (!a.alive) continue;
      if (a.errorTimer > 0) { a.errorTimer = Math.max(0, a.errorTimer - dt); anyAnim = true; }
      if (a.animatingFlyOff) {
        a.flyProgress += dt / FLY_OFF_DURATION;
        if (a.flyProgress >= 1) {
          a.animatingFlyOff = false;
          this._queueDotReveal(a);
          this.board.removeArrow(a);
        }
        anyAnim = true;
      }
    }
    const visualAnim = this._updateFunBursts(dt);
    const dotAnim = this._updateDotReveals(dt);
    if (this.phase === Phase.ANIMATING && !anyAnim) {
      if (this.board.isEmpty()) {
        this.phase = Phase.LEVEL_COMPLETE;
        this._spawnLevelBurst();
      } else {
        this.phase = Phase.PLAYING;
      }
    }
    return anyAnim || visualAnim || dotAnim || timerActive;
  }

  advanceLevel() {
    this.completedLevels.add(this.currentLevel);
    const stars = this._computeStars();
    const prev = this.levelStars[this.currentLevel] || 0;
    if (stars > prev) this.levelStars[this.currentLevel] = stars;
    const next = Math.min(this.currentLevel + 1, MAX_LEVEL);
    this.maxLevelUnlocked = Math.max(this.maxLevelUnlocked, next);
    this._saveProgress();
    this.phase = Phase.LEVEL_SELECT;
  }

  restartLevel() { this.startLevel(this.currentLevel); }
  goToLevelSelect() { this.phase = Phase.LEVEL_SELECT; prefetchLevel(this.currentLevel); }
  goHome() { this.phase = Phase.MAIN_MENU; }
}

// Drawing helpers
function lerpColor(c1, c2, t) {
  const p = (s) => parseInt(s, 16);
  const h1 = c1.replace("#", ""), h2 = c2.replace("#", "");
  const r = Math.round(p(h1.slice(0, 2)) + (p(h2.slice(0, 2)) - p(h1.slice(0, 2))) * t);
  const g = Math.round(p(h1.slice(2, 4)) + (p(h2.slice(2, 4)) - p(h1.slice(2, 4))) * t);
  const b = Math.round(p(h1.slice(4, 6)) + (p(h2.slice(4, 6)) - p(h1.slice(4, 6))) * t);
  return `rgb(${r},${g},${b})`;
}

function smoothPolyline(centers, cr) {
  if (centers.length <= 2 || cr <= 0) return centers;
  const result = [centers[0]];
  for (let i = 1; i < centers.length - 1; i++) {
    const [px, py] = centers[i - 1];
    const [cx, cy] = centers[i];
    const [nx, ny] = centers[i + 1];
    const dxi = cx - px, dyi = cy - py;
    const dxo = nx - cx, dyo = ny - cy;
    const inLen = Math.hypot(dxi, dyi), outLen = Math.hypot(dxo, dyo);
    if (inLen < 1e-9 || outLen < 1e-9) { result.push([cx, cy]); continue; }
    const cross = dxi * dyo - dyi * dxo;
    if (Math.abs(cross) < 1e-6 * inLen * outLen) { result.push([cx, cy]); continue; }
    const r = Math.min(cr, inLen * 0.45, outLen * 0.45);
    const bx0 = cx - (dxi / inLen) * r, by0 = cy - (dyi / inLen) * r;
    const bx2 = cx + (dxo / outLen) * r, by2 = cy + (dyo / outLen) * r;
    const n = Math.max(6, Math.floor(r / 2));
    for (let s = 0; s <= n; s++) {
      const t = s / n, u = 1 - t;
      result.push([u * u * bx0 + 2 * u * t * cx + t * t * bx2,
                    u * u * by0 + 2 * u * t * cy + t * t * by2]);
    }
  }
  result.push(centers[centers.length - 1]);
  return result;
}

function drawArrowBody(ctx, points, color, width, alpha, cr) {
  if (points.length < 2) return;
  const pts = cr > 0 ? smoothPolyline(points, cr) : points;
  ctx.save();
  ctx.globalAlpha = alpha;
  ctx.strokeStyle = color;
  ctx.lineWidth = width;
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  ctx.beginPath();
  ctx.moveTo(pts[0][0], pts[0][1]);
  for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i][0], pts[i][1]);
  ctx.stroke();
  ctx.restore();
}

function drawArrowhead(ctx, cx, cy, size, direction, color, alpha) {
  if (size < 2) return;
  const angle = DIRECTION_ANGLES[direction];
  const s = size;
  const raw = [[s * 0.48, 0], [-s * 0.30, -s * 0.36], [-s * 0.10, 0], [-s * 0.30, s * 0.36]];
  ctx.save();
  ctx.globalAlpha = alpha;
  ctx.fillStyle = color;
  ctx.beginPath();
  for (let i = 0; i < raw.length; i++) {
    const [px, py] = raw[i];
    const rx = px * Math.cos(angle) - py * Math.sin(angle);
    const ry = px * Math.sin(angle) + py * Math.cos(angle);
    if (i === 0) ctx.moveTo(cx + rx, cy + ry);
    else ctx.lineTo(cx + rx, cy + ry);
  }
  ctx.closePath();
  ctx.fill();
  ctx.restore();
}

function drawHeart(ctx, cx, cy, size, color) {
  const r = size * 0.28;
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.arc(cx - r * 0.7, cy - r * 0.15, r, 0, Math.PI * 2);
  ctx.fill();
  ctx.beginPath();
  ctx.arc(cx + r * 0.7, cy - r * 0.15, r, 0, Math.PI * 2);
  ctx.fill();
  ctx.beginPath();
  ctx.moveTo(cx - size * 0.42, cy + size * 0.05);
  ctx.lineTo(cx + size * 0.42, cy + size * 0.05);
  ctx.lineTo(cx, cy + size * 0.48);
  ctx.closePath();
  ctx.fill();
}

// Arc-length utils for fly-off
function arcLengths(wp) {
  const a = [0];
  for (let i = 1; i < wp.length; i++) {
    a.push(a[i - 1] + Math.hypot(wp[i][0] - wp[i - 1][0], wp[i][1] - wp[i - 1][1]));
  }
  return a;
}

function pointAtDist(wp, arc, dist) {
  if (dist <= 0) return wp[0];
  if (dist >= arc[arc.length - 1]) return wp[wp.length - 1];
  let lo = 0, hi = arc.length - 1;
  while (lo < hi - 1) {
    const mid = (lo + hi) >> 1;
    if (arc[mid] <= dist) lo = mid; else hi = mid;
  }
  const seg = arc[hi] - arc[lo];
  const t = seg > 0 ? (dist - arc[lo]) / seg : 0;
  return [
    wp[lo][0] + (wp[hi][0] - wp[lo][0]) * t,
    wp[lo][1] + (wp[hi][1] - wp[lo][1]) * t,
  ];
}

// Renderer
class Renderer {
  constructor(canvas) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.camera = new Camera();
    this._cameraLevel = -1;
    this._levelScrollY = 0;
    this._dpr = 1;
    this._w = 0;
    this._h = 0;
    this._resize();
    window.addEventListener("resize", () => { this._resize(); if (typeof markDirty === "function") markDirty(); });
  }

  _resize() {
    this._dpr = window.devicePixelRatio || 1;
    this._w = window.innerWidth;
    this._h = window.innerHeight;
    this.canvas.width = this._w * this._dpr;
    this.canvas.height = this._h * this._dpr;
    this.ctx.setTransform(this._dpr, 0, 0, this._dpr, 0, 0);
  }

  get width() { return this._w; }
  get height() { return this._h; }

  cellSize() {
    return Math.max(1, CELL_SIZE_WORLD * this.camera.zoom);
  }

  cellCenter(row, col) {
    const cs = CELL_SIZE_WORLD;
    return this.camera.w2s(col * cs + cs / 2, row * cs + cs / 2);
  }

  screenToCell(x, y, board) {
    if (!board) return null;
    const [wx, wy] = this.camera.s2w(x, y);
    const col = Math.floor(wx / CELL_SIZE_WORLD);
    const row = Math.floor(wy / CELL_SIZE_WORLD);

    if (row >= 0 && row < board.rows && col >= 0 && col < board.cols) {
      if (board.getArrowAt(row, col)) return [row, col];
    }

    const cs = this.cellSize();
    let bestDist = (cs * 0.6) ** 2;
    let best = null;
    for (let dr = -1; dr <= 1; dr++) {
      for (let dc = -1; dc <= 1; dc++) {
        const nr = row + dr, nc = col + dc;
        if (nr >= 0 && nr < board.rows && nc >= 0 && nc < board.cols && board.getArrowAt(nr, nc)) {
          const [ccx, ccy] = this.cellCenter(nr, nc);
          const d2 = (x - ccx) ** 2 + (y - ccy) ** 2;
          if (d2 < bestDist) { bestDist = d2; best = [nr, nc]; }
        }
      }
    }
    return best;
  }

  ensureCamera(ctrl) {
    if (ctrl.phase === Phase.MAIN_MENU || ctrl.phase === Phase.LEVEL_SELECT) {
      this._cameraLevel = -1;
      return;
    }
    if (ctrl.currentLevel !== this._cameraLevel && ctrl.board) {
      this._cameraLevel = ctrl.currentLevel;
      this.camera.centerOnGrid(ctrl.board.rows, ctrl.board.cols, this._w, this._h);
    }
  }

  render(ctrl) {
    const ctx = this.ctx;
    ctx.setTransform(this._dpr, 0, 0, this._dpr, 0, 0);
    ctx.fillStyle = BG_COLOR;
    ctx.fillRect(0, 0, this._w, this._h);

    this.ensureCamera(ctrl);

    if (ctrl.phase === Phase.MAIN_MENU) {
      this._drawMainMenu(ctx, ctrl);
    } else if (ctrl.phase === Phase.LEVEL_SELECT) {
      this._drawLevelSelect(ctx, ctrl);
    } else {
      this._drawHUD(ctx, ctrl);
      if (ctrl.board) {
        this._drawGridDots(ctx, ctrl);
        this._drawArrows(ctx, ctrl);
      }
      if (ctrl.phase === Phase.LEVEL_COMPLETE) {
        this._drawLevelComplete(ctx, ctrl);
      } else if (ctrl.phase === Phase.GAME_OVER) {
        this._drawOverlay(ctx, "Game Over", ARROW_ERROR_COLOR, "Tap to retry");
      }
      if (ctrl.funMode) this._drawFunBursts(ctx, ctrl);
    }
  }

  _drawMainMenu(ctx, ctrl) {
    ctx.fillStyle = ARROW_COLOR;
    ctx.textAlign = "center";
    ctx.font = "bold 38px Arial, sans-serif";
    ctx.fillText("Arrows", this._w / 2, this._h / 2 - 30);
    ctx.font = "20px Arial, sans-serif";
    ctx.fillStyle = HUD_TEXT_COLOR;
    ctx.fillText("Puzzle Escape", this._w / 2, this._h / 2 + 10);
    ctx.font = "15px Arial, sans-serif";
    ctx.fillText("Tap to start", this._w / 2, this._h / 2 + 50);

    const btn = this.modeButtonRect();
    ctx.fillStyle = ctrl.hardMode ? ARROW_ERROR_COLOR : LEVEL_UNLOCKED_BTN;
    ctx.beginPath();
    ctx.roundRect(btn.x, btn.y, btn.w, btn.h, 8);
    ctx.fill();
    ctx.fillStyle = "#fff";
    ctx.font = "bold 15px Arial, sans-serif";
    ctx.textBaseline = "middle";
    ctx.fillText(ctrl.hardMode ? "Easy Mode" : "Hard Mode", btn.x + btn.w / 2, btn.y + btn.h / 2);

    const funBtn = this.funButtonRect();
    ctx.fillStyle = ctrl.funMode ? FUN_BUTTON_COLOR : LEVEL_UNLOCKED_BTN;
    ctx.beginPath();
    ctx.roundRect(funBtn.x, funBtn.y, funBtn.w, funBtn.h, 8);
    ctx.fill();
    ctx.fillStyle = "#fff";
    ctx.fillText(ctrl.funMode ? "Calm" : "Fun!", funBtn.x + funBtn.w / 2, funBtn.y + funBtn.h / 2);
    ctx.textBaseline = "alphabetic";
  }

  modeButtonRect() {
    const w = 156, h = 42, gap = 10;
    return { x: (this._w - w) / 2, y: this._h - h * 2 - gap - 28, w, h };
  }

  funButtonRect() {
    const btn = this.modeButtonRect();
    return { x: btn.x, y: btn.y + btn.h + 10, w: btn.w, h: btn.h };
  }

  modeHitTest(x, y) {
    const btn = this.modeButtonRect();
    return x >= btn.x && x <= btn.x + btn.w && y >= btn.y && y <= btn.y + btn.h;
  }

  funHitTest(x, y) {
    const btn = this.funButtonRect();
    return x >= btn.x && x <= btn.x + btn.w && y >= btn.y && y <= btn.y + btn.h;
  }

  _drawLevelSelect(ctx, ctrl) {
    ctx.fillStyle = ARROW_COLOR;
    ctx.textAlign = "center";
    ctx.font = "bold 28px Arial, sans-serif";
    ctx.fillText(ctrl.hardMode ? "Hard Mode" : "Select Level", this._w / 2, 50);
    this._drawTextButton(ctx, this.homeButtonRect(), "Home", LEVEL_UNLOCKED_BTN);

    const totalW = LEVEL_BTN_COLS * LEVEL_BTN_SIZE + (LEVEL_BTN_COLS - 1) * LEVEL_BTN_GAP;
    const startX = (this._w - totalW) / 2;

    for (let lvl = 1; lvl <= MAX_LEVEL; lvl++) {
      const idx = lvl - 1;
      const col = idx % LEVEL_BTN_COLS;
      const row = Math.floor(idx / LEVEL_BTN_COLS);
      const x = startX + col * (LEVEL_BTN_SIZE + LEVEL_BTN_GAP);
      const y = LEVEL_SELECT_TOP + row * (LEVEL_BTN_SIZE + LEVEL_BTN_GAP) - this._levelScrollY;

      if (y + LEVEL_BTN_SIZE < 0 || y > this._h) continue;

      let color;
      if (ctrl.completedLevels.has(lvl)) color = LEVEL_COMPLETED_BTN;
      else if (lvl <= ctrl.maxLevelUnlocked) color = LEVEL_UNLOCKED_BTN;
      else color = LEVEL_LOCKED_BTN;

      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.roundRect(x, y, LEVEL_BTN_SIZE, LEVEL_BTN_SIZE, 8);
      ctx.fill();

      ctx.fillStyle = "#fff";
      ctx.font = "bold 18px Arial, sans-serif";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(String(lvl), x + LEVEL_BTN_SIZE / 2, y + LEVEL_BTN_SIZE / 2 - 4);

      const s = ctrl.levelStars[lvl] || 0;
      if (s > 0) {
        ctx.font = "10px Arial, sans-serif";
        let starStr = "";
        for (let si = 0; si < 3; si++) starStr += si < s ? "★" : "☆";
        ctx.fillStyle = "#e8a735";
        ctx.fillText(starStr, x + LEVEL_BTN_SIZE / 2, y + LEVEL_BTN_SIZE - 8);
      }
    }
    ctx.textBaseline = "alphabetic";
  }

  levelHitTest(x, y, ctrl) {
    const totalW = LEVEL_BTN_COLS * LEVEL_BTN_SIZE + (LEVEL_BTN_COLS - 1) * LEVEL_BTN_GAP;
    const startX = (this._w - totalW) / 2;

    for (let lvl = 1; lvl <= MAX_LEVEL; lvl++) {
      const idx = lvl - 1;
      const col = idx % LEVEL_BTN_COLS;
      const row = Math.floor(idx / LEVEL_BTN_COLS);
      const bx = startX + col * (LEVEL_BTN_SIZE + LEVEL_BTN_GAP);
      const by = LEVEL_SELECT_TOP + row * (LEVEL_BTN_SIZE + LEVEL_BTN_GAP) - this._levelScrollY;
      if (x >= bx && x <= bx + LEVEL_BTN_SIZE && y >= by && y <= by + LEVEL_BTN_SIZE) {
        return lvl;
      }
    }
    return null;
  }

  homeButtonRect() {
    return { x: 14, y: 18, w: 78, h: 34 };
  }

  homeHitTest(x, y) {
    const btn = this.homeButtonRect();
    return x >= btn.x && x <= btn.x + btn.w && y >= btn.y && y <= btn.y + btn.h;
  }

  _drawHUD(ctx, ctrl) {
    ctx.fillStyle = HUD_TEXT_COLOR;
    ctx.font = "18px Arial, sans-serif";

    ctx.textAlign = "left";
    const mins = Math.floor(ctrl.elapsedTime / 60);
    const secs = Math.floor(ctrl.elapsedTime % 60);
    ctx.fillText(`${mins}:${secs < 10 ? "0" : ""}${secs}`, 16, 32);

    ctx.textAlign = "right";
    ctx.fillText(`Level ${ctrl.currentLevel}`, this._w - 92, 32);
    this._drawTextButton(ctx, this.exitButtonRect(), "Exit", LEVEL_UNLOCKED_BTN);

    const hs = 18, spacing = 26;
    const total = ctrl.maxLives * spacing;
    const sx = (this._w - total) / 2 + spacing / 2;
    for (let i = 0; i < ctrl.maxLives; i++) {
      drawHeart(ctx, sx + i * spacing, 24, hs, i < ctrl.lives ? HEART_COLOR : HEART_EMPTY_COLOR);
    }

    ctx.textAlign = "left";
    ctx.font = "14px Arial, sans-serif";
    ctx.fillText(`Score: ${ctrl.score}`, 16, 52);
    if (ctrl.combo > 1) {
      ctx.fillStyle = "#e8a735";
      ctx.fillText(`x${Math.min(ctrl.combo, 5)} combo`, 120, 52);
    }
  }

  exitButtonRect() {
    return { x: this._w - 74, y: 12, w: 60, h: 30 };
  }

  exitHitTest(x, y) {
    const btn = this.exitButtonRect();
    return x >= btn.x && x <= btn.x + btn.w && y >= btn.y && y <= btn.y + btn.h;
  }

  _drawTextButton(ctx, btn, label, color) {
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.roundRect(btn.x, btn.y, btn.w, btn.h, 8);
    ctx.fill();
    ctx.fillStyle = "#fff";
    ctx.font = "bold 14px Arial, sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(label, btn.x + btn.w / 2, btn.y + btn.h / 2);
    ctx.textBaseline = "alphabetic";
  }

  _drawGridDots(ctx, ctrl) {
    const cs = this.cellSize();
    if (cs < 3) return;
    const [minR, maxR, minC, maxC] = this.camera.visibleRange(
      ctrl.board.rows, ctrl.board.cols, this._w, this._h
    );
    const visibleCells = (maxR - minR) * (maxC - minC);
    if (visibleCells > 40000) return;
    const dotR = Math.max(0.45, cs * 0.055);
    const csW = CELL_SIZE_WORLD;
    const z = this.camera.zoom, ox = this.camera.ox, oy = this.camera.oy;
    const hcs = csW / 2;
    const revealDots = ctrl.revealingDots;
    const hasReveals = revealDots.size > 0;
    ctx.fillStyle = GRID_DOT_COLOR;
    ctx.beginPath();
    for (let r = minR; r < maxR; r++) {
      for (let c = minC; c < maxC; c++) {
        if (ctrl.board._grid[r][c]) continue;
        if (hasReveals && revealDots.has(`${r},${c}`)) continue;
        const sx = (c * csW + hcs) * z + ox;
        const sy = (r * csW + hcs) * z + oy;
        ctx.moveTo(sx + dotR, sy);
        ctx.arc(sx, sy, dotR, 0, Math.PI * 2);
      }
    }
    ctx.fill();

    if (!hasReveals) return;
    ctx.save();
    ctx.fillStyle = GRID_DOT_COLOR;
    for (const dot of revealDots.values()) {
      const { r, c } = dot;
      if (r < minR || r >= maxR || c < minC || c >= maxC) continue;
      if (ctrl.board._grid[r][c]) continue;
      const t = Math.min(1, dot.age / GRID_DOT_REVEAL_DURATION);
      const eased = t * t * (3 - 2 * t);
      const rr = dotR * (0.25 + 0.75 * eased);
      const sx = (c * csW + hcs) * z + ox;
      const sy = (r * csW + hcs) * z + oy;
      ctx.globalAlpha = eased;
      ctx.beginPath();
      ctx.arc(sx, sy, rr, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.restore();
  }

  _drawArrows(ctx, ctrl) {
    const cs = this.cellSize();
    const headSize = cs * ARROW_HEAD_SIZE;
    const crWorld = CELL_SIZE_WORLD * ARROW_CORNER_RADIUS_RATIO;
    const bw = Math.max(1, Math.round(cs * 0.2));
    const cam = this.camera;
    const csW = CELL_SIZE_WORLD;
    const z = cam.zoom, oox = cam.ox, ooy = cam.oy;
    const hcs = csW / 2;

    const [minR, maxR, minC, maxC] = cam.visibleRange(
      ctrl.board.rows, ctrl.board.cols, this._w, this._h
    );
    const arrows = ctrl.board.arrowsInRegion(minR, maxR, minC, maxC);

    const useSmooth = cs >= 8;
    const drawHeads = headSize >= 3;
    const CHUNK = 500;
    const errorArrows = [];
    const flyArrows = [];
    const normalArrows = [];
    const funGroups = ctrl.funMode ? new Map() : null;

    for (const arrow of arrows) {
      if (arrow.animatingFlyOff) { flyArrows.push(arrow); continue; }
      if (arrow.errorTimer > 0) { errorArrows.push(arrow); continue; }
      if (funGroups) {
        const color = arrow.funColor || ARROW_COLOR;
        if (!funGroups.has(color)) funGroups.set(color, []);
        funGroups.get(color).push(arrow);
      } else {
        normalArrows.push(arrow);
      }
    }

    const drawNormalBatch = (batch, color) => {
      ctx.strokeStyle = color;
      ctx.lineWidth = bw;
      ctx.lineCap = "round";
      ctx.lineJoin = "round";
      let pathCount = 0;
      let headBuf = drawHeads ? [] : null;
      ctx.beginPath();
      for (const arrow of batch) {
        const [hx, hy] = this._addArrowBodyPath(ctx, arrow, useSmooth, crWorld, z, oox, ooy, hcs, csW);
        if (drawHeads) headBuf.push(hx, hy, arrow.direction);

        if (++pathCount >= CHUNK) {
          ctx.stroke();
          ctx.beginPath();
          pathCount = 0;
        }
      }
      if (pathCount > 0) ctx.stroke();

      if (drawHeads && headBuf.length > 0) {
        ctx.fillStyle = color;
        ctx.beginPath();
        let hc = 0;
        for (let i = 0; i < headBuf.length; i += 3) {
          this._addHeadPath(ctx, headBuf[i], headBuf[i + 1], headSize, headBuf[i + 2]);
          if (++hc >= CHUNK) {
            ctx.fill();
            ctx.beginPath();
            hc = 0;
          }
        }
        if (hc > 0) ctx.fill();
      }
    };

    if (funGroups) {
      for (const [color, batch] of funGroups) drawNormalBatch(batch, color);
    } else {
      drawNormalBatch(normalArrows, ARROW_COLOR);
    }

    for (const arrow of errorArrows) {
      const t = arrow.errorTimer / ERROR_FLASH_DURATION;
      const shake = Math.sin(t * Math.PI * 8) * Math.max(1, cs * 0.08);
      ctx.strokeStyle = ARROW_ERROR_COLOR;
      ctx.lineWidth = bw;
      ctx.lineCap = "round";
      ctx.lineJoin = "round";
      ctx.beginPath();
      const cells = arrow.cells;
      if (useSmooth) {
        const wpts = arrow.smoothWorld(crWorld);
        ctx.moveTo(wpts[0][0] * z + oox + shake, wpts[0][1] * z + ooy);
        for (let i = 1; i < wpts.length; i++) {
          ctx.lineTo(wpts[i][0] * z + oox + shake, wpts[i][1] * z + ooy);
        }
      } else {
        ctx.moveTo((cells[0][1] * csW + hcs) * z + oox + shake, (cells[0][0] * csW + hcs) * z + ooy);
        for (let i = 1; i < cells.length; i++) {
          ctx.lineTo((cells[i][1] * csW + hcs) * z + oox + shake, (cells[i][0] * csW + hcs) * z + ooy);
        }
      }
      ctx.stroke();
      if (drawHeads) {
        let lhx, lhy;
        if (useSmooth) {
          const wpts = arrow.smoothWorld(crWorld);
          const last = wpts[wpts.length - 1];
          lhx = last[0] * z + oox + shake; lhy = last[1] * z + ooy;
        } else {
          const lc = cells[cells.length - 1];
          lhx = (lc[1] * csW + hcs) * z + oox + shake; lhy = (lc[0] * csW + hcs) * z + ooy;
        }
        ctx.fillStyle = ARROW_ERROR_COLOR;
        ctx.beginPath();
        this._addHeadPath(ctx, lhx, lhy, headSize, arrow.direction);
        ctx.fill();
      }
    }

    for (const arrow of flyArrows) {
      const centers = arrow.cells.map(([r, c]) => this.cellCenter(r, c));
      const cr = cs * ARROW_CORNER_RADIUS_RATIO;
      this._drawArrowFlying(ctx, arrow, centers, cs, headSize, cr, bw, ctrl.funMode);
    }
  }

  _addArrowBodyPath(ctx, arrow, useSmooth, crWorld, z, oox, ooy, hcs, csW) {
    const cells = arrow.cells;
    if (useSmooth) {
      const wpts = arrow.smoothWorld(crWorld);
      ctx.moveTo(wpts[0][0] * z + oox, wpts[0][1] * z + ooy);
      for (let i = 1; i < wpts.length; i++) {
        ctx.lineTo(wpts[i][0] * z + oox, wpts[i][1] * z + ooy);
      }
      const last = wpts[wpts.length - 1];
      return [last[0] * z + oox, last[1] * z + ooy];
    }

    let sx = (cells[0][1] * csW + hcs) * z + oox;
    let sy = (cells[0][0] * csW + hcs) * z + ooy;
    ctx.moveTo(sx, sy);
    for (let i = 1; i < cells.length; i++) {
      sx = (cells[i][1] * csW + hcs) * z + oox;
      sy = (cells[i][0] * csW + hcs) * z + ooy;
      ctx.lineTo(sx, sy);
    }
    return [sx, sy];
  }

  _addHeadPath(ctx, cx, cy, size, direction) {
    const angle = DIRECTION_ANGLES[direction];
    const s = size;
    const cos = Math.cos(angle), sin = Math.sin(angle);
    const raw = [[s * 0.48, 0], [-s * 0.30, -s * 0.36], [-s * 0.10, 0], [-s * 0.30, s * 0.36]];
    const rx0 = raw[0][0] * cos - raw[0][1] * sin;
    const ry0 = raw[0][0] * sin + raw[0][1] * cos;
    ctx.moveTo(cx + rx0, cy + ry0);
    for (let i = 1; i < 4; i++) {
      const rx = raw[i][0] * cos - raw[i][1] * sin;
      const ry = raw[i][0] * sin + raw[i][1] * cos;
      ctx.lineTo(cx + rx, cy + ry);
    }
    ctx.closePath();
  }

  _drawArrowFlying(ctx, arrow, centers, cs, headSize, cr, bw, funMode) {
    const progress = arrow.flyProgress;
    const eased = 1 - (1 - progress) ** 2.5;
    const [dr, dc] = DIRECTION_VECTORS[arrow.direction];
    const n = centers.length;
    const extra = n + 5;

    const rawWp = [...centers];
    const [hx, hy] = centers[n - 1];
    for (let k = 1; k <= extra; k++) {
      rawWp.push([hx + dc * cs * k, hy + dr * cs * k]);
    }

    const waypoints = cr > 0 ? smoothPolyline(rawWp, cr) : rawWp;
    const arc = arcLengths(waypoints);
    const rawArc = arcLengths(rawWp);
    const advanceDist = eased * extra * cs;

    const cellPos = [];
    const cellDists = [];
    for (let i = 0; i < n; i++) {
      const d = rawArc[i] + advanceDist;
      cellDists.push(d);
      cellPos.push(pointAtDist(waypoints, arc, d));
    }

    const dense = [];
    for (let i = 0; i < n; i++) {
      if (i > 0) {
        for (let j = 0; j < arc.length; j++) {
          if (cellDists[i - 1] < arc[j] && arc[j] < cellDists[i]) {
            dense.push(waypoints[j]);
          }
        }
      }
      dense.push(cellPos[i]);
    }

    const alpha = Math.max(0, 1 - eased * 0.8);
    const baseColor = funMode ? (arrow.funColor || ARROW_COLOR) : ARROW_COLOR;
    const color = lerpColor(baseColor, ARROW_FLY_COLOR, eased * 0.6);
    drawArrowBody(ctx, dense, color, bw, alpha, 0);
    const [fx, fy] = cellPos[cellPos.length - 1];
    drawArrowhead(ctx, fx, fy, headSize, arrow.direction, color, alpha);
  }

  _drawFunBursts(ctx, ctrl) {
    if (!ctrl.funBursts || ctrl.funBursts.length === 0) return;
    const cam = this.camera;
    const particleZoom = Math.max(0.85, Math.min(1.6, cam.zoom));
    ctx.save();
    for (const p of ctrl.funBursts) {
      const t = p.age / p.ttl;
      const alpha = Math.max(0, (1 - t) ** 1.4);
      const x = p.x * cam.zoom + cam.ox;
      const y = p.y * cam.zoom + cam.oy;
      const s = p.size * particleZoom;
      ctx.globalAlpha = alpha;
      ctx.fillStyle = p.color;
      ctx.beginPath();
      ctx.moveTo(x, y - s);
      ctx.lineTo(x + s, y);
      ctx.lineTo(x, y + s);
      ctx.lineTo(x - s, y);
      ctx.closePath();
      ctx.fill();
    }
    ctx.restore();
  }

  _drawLevelComplete(ctx, ctrl) {
    ctx.save();
    ctx.fillStyle = "rgba(255,255,255,0.85)";
    ctx.fillRect(0, 0, this._w, this._h);
    const cx = this._w / 2;
    let y = this._h / 2 - 80;

    ctx.fillStyle = LEVEL_COMPLETE_COLOR;
    ctx.textAlign = "center";
    ctx.font = "bold 36px Arial, sans-serif";
    ctx.fillText("Level Complete!", cx, y);
    y += 44;

    const stars = ctrl._computeStars();
    const starSize = 28;
    for (let i = 0; i < 3; i++) {
      const sx = cx - 50 + i * 50;
      ctx.font = `${starSize}px Arial, sans-serif`;
      ctx.fillStyle = i < stars ? "#e8a735" : "#ccc";
      ctx.fillText(i < stars ? "★" : "☆", sx, y);
    }
    y += 36;

    ctx.fillStyle = HUD_TEXT_COLOR;
    ctx.font = "18px Arial, sans-serif";
    const mins = Math.floor(ctrl.elapsedTime / 60);
    const secs = Math.floor(ctrl.elapsedTime % 60);
    ctx.fillText(`Time: ${mins}:${secs < 10 ? "0" : ""}${secs}`, cx, y);
    y += 28;
    ctx.fillText(`Score: ${ctrl.score}`, cx, y);
    y += 28;
    ctx.fillText(`Mistakes: ${ctrl.totalMistakes}`, cx, y);
    y += 36;

    ctx.fillStyle = HUD_TEXT_COLOR;
    ctx.font = "16px Arial, sans-serif";
    ctx.fillText("Tap to continue", cx, y);
    ctx.restore();
  }

  _drawOverlay(ctx, title, color, hint) {
    ctx.save();
    ctx.fillStyle = "rgba(255,255,255,0.82)";
    ctx.fillRect(0, 0, this._w, this._h);
    ctx.fillStyle = color;
    ctx.textAlign = "center";
    ctx.font = "bold 36px Arial, sans-serif";
    ctx.fillText(title, this._w / 2, this._h / 2 - 10);
    ctx.fillStyle = HUD_TEXT_COLOR;
    ctx.font = "16px Arial, sans-serif";
    ctx.fillText(hint, this._w / 2, this._h / 2 + 30);
    ctx.restore();
  }
}

// Input Handling
function setupInput(canvas, renderer, ctrl) {
  let touchId = null;
  let pinchDist0 = null;
  let pinchZoom0 = null;
  let touchGestureCancelled = false;

  function handlePointerDown(x, y) {
    const phase = ctrl.phase;
    if (phase === Phase.MAIN_MENU) {
      if (renderer.modeHitTest(x, y)) {
        ctrl.toggleMode();
        return;
      }
      if (renderer.funHitTest(x, y)) {
        ctrl.toggleFun();
        return;
      }
      ctrl.goToLevelSelect();
      return;
    }
    if (phase === Phase.LEVEL_SELECT) {
      if (renderer.homeHitTest(x, y)) {
        ctrl.goHome();
        renderer._levelScrollY = 0;
        return;
      }
      const lvl = renderer.levelHitTest(x, y, ctrl);
      if (lvl !== null && lvl <= ctrl.maxLevelUnlocked) {
        ctrl.startLevel(lvl);
      }
      return;
    }
    if (phase === Phase.LEVEL_COMPLETE) {
      ctrl.advanceLevel();
      return;
    }
    if (phase === Phase.GAME_OVER) {
      ctrl.restartLevel();
      return;
    }
    if ((phase === Phase.PLAYING || phase === Phase.ANIMATING) && renderer.exitHitTest(x, y)) {
      ctrl.goToLevelSelect();
      renderer._cameraLevel = -1;
      return;
    }
    if (phase === Phase.PLAYING || phase === Phase.ANIMATING) {
      renderer.camera.startDrag(x, y);
    }
  }

  let isTouch = false;

  function handlePointerUp(x, y) {
    if (renderer.camera.isDragging) {
      const threshold = isTouch ? TOUCH_DRAG_THRESHOLD : DRAG_THRESHOLD;
      const wasDrag = renderer.camera._dragMoved >= threshold;
      renderer.camera.endDrag();
      if (!wasDrag && (ctrl.phase === Phase.PLAYING || ctrl.phase === Phase.ANIMATING) && ctrl.board) {
        const cell = renderer.screenToCell(x, y, ctrl.board);
        if (cell) ctrl.handleClick(cell[0], cell[1]);
      }
    }
  }

  function handlePointerMove(x, y) {
    if (renderer.camera.isDragging) {
      renderer.camera.updateDrag(x, y);
    }
  }

  // Mouse
  canvas.addEventListener("mousedown", (e) => {
    isTouch = false; handlePointerDown(e.clientX, e.clientY); markDirty();
  });
  canvas.addEventListener("mousemove", (e) => {
    handlePointerMove(e.clientX, e.clientY); if (renderer.camera.isDragging) markDirty();
  });
  canvas.addEventListener("mouseup", (e) => {
    handlePointerUp(e.clientX, e.clientY); markDirty();
  });

  // Wheel zoom
  canvas.addEventListener("wheel", (e) => {
    e.preventDefault();
    if (ctrl.phase === Phase.LEVEL_SELECT) {
      renderer._levelScrollY += e.deltaY * 0.5;
      renderer._levelScrollY = Math.max(0, renderer._levelScrollY);
      const maxRows = Math.ceil(MAX_LEVEL / LEVEL_BTN_COLS);
      const maxScroll = Math.max(0, maxRows * (LEVEL_BTN_SIZE + LEVEL_BTN_GAP) + LEVEL_SELECT_TOP - renderer.height + 40);
      renderer._levelScrollY = Math.min(renderer._levelScrollY, maxScroll);
    } else if (ctrl.phase === Phase.PLAYING || ctrl.phase === Phase.ANIMATING) {
      renderer.camera.applyZoom(e.deltaY < 0 ? 1 : -1, e.clientX, e.clientY);
    }
    markDirty();
  }, { passive: false });

  // Touch
  canvas.addEventListener("touchstart", (e) => {
    e.preventDefault();
    isTouch = true;
    if (e.touches.length >= 2) {
      touchGestureCancelled = true;
      if (renderer.camera.isDragging) renderer.camera.endDrag();
      const dx = e.touches[1].clientX - e.touches[0].clientX;
      const dy = e.touches[1].clientY - e.touches[0].clientY;
      pinchDist0 = Math.hypot(dx, dy);
      pinchZoom0 = renderer.camera.zoom;
      return;
    }
    if (e.touches.length === 1) {
      touchId = e.touches[0].identifier;
      handlePointerDown(e.touches[0].clientX, e.touches[0].clientY);
    }
    markDirty();
  }, { passive: false });

  canvas.addEventListener("touchmove", (e) => {
    e.preventDefault();
    if (e.touches.length >= 2) {
      touchGestureCancelled = true;
      const dx = e.touches[1].clientX - e.touches[0].clientX;
      const dy = e.touches[1].clientY - e.touches[0].clientY;
      const dist = Math.hypot(dx, dy);
      if (dist <= 0) return;
      if (pinchDist0 === null || pinchDist0 <= 0) {
        pinchDist0 = dist;
        pinchZoom0 = renderer.camera.zoom;
      }
      const mx = (e.touches[0].clientX + e.touches[1].clientX) / 2;
      const my = (e.touches[0].clientY + e.touches[1].clientY) / 2;
      const oldZoom = renderer.camera.zoom;
      renderer.camera.zoom = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, pinchZoom0 * (dist / pinchDist0)));
      const ratio = renderer.camera.zoom / oldZoom;
      renderer.camera.ox = mx - (mx - renderer.camera.ox) * ratio;
      renderer.camera.oy = my - (my - renderer.camera.oy) * ratio;
      markDirty();
      return;
    }
    if (e.touches.length === 1 && !touchGestureCancelled) {
      handlePointerMove(e.touches[0].clientX, e.touches[0].clientY);
      if (renderer.camera.isDragging) markDirty();
    }
  }, { passive: false });

  canvas.addEventListener("touchend", (e) => {
    e.preventDefault();
    pinchDist0 = null;
    if (touchGestureCancelled) {
      if (renderer.camera.isDragging) renderer.camera.endDrag();
      if (e.touches.length === 0) {
        touchGestureCancelled = false;
        touchId = null;
      }
      markDirty();
      return;
    }
    if (e.changedTouches.length > 0) {
      const t = e.changedTouches[0];
      if (t.identifier === touchId) {
        handlePointerUp(t.clientX, t.clientY);
        touchId = null;
      }
    }
    markDirty();
  }, { passive: false });

  canvas.addEventListener("touchcancel", (e) => {
    e.preventDefault();
    pinchDist0 = null;
    touchGestureCancelled = false;
    touchId = null;
    if (renderer.camera.isDragging) renderer.camera.endDrag();
    markDirty();
  }, { passive: false });

  // Keyboard
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      if (ctrl.phase === Phase.PLAYING || ctrl.phase === Phase.ANIMATING) {
        ctrl.goToLevelSelect();
        renderer._cameraLevel = -1;
      }
    }
    if (e.key === " ") {
      e.preventDefault();
      if (ctrl.phase === Phase.LEVEL_COMPLETE) ctrl.advanceLevel();
      else if (ctrl.phase === Phase.MAIN_MENU) ctrl.goToLevelSelect();
      else if (ctrl.phase === Phase.GAME_OVER) ctrl.restartLevel();
    }
    markDirty();
  });
}

// Game Loop
const canvas = document.getElementById("game");
const ctrl = new GameController();
const renderer = new Renderer(canvas);
let needsRender = true;
function markDirty() { needsRender = true; }

setupInput(canvas, renderer, ctrl);

let lastTime = 0;
function gameLoop(timestamp) {
  const dt = Math.min((timestamp - lastTime) / 1000, 0.1);
  lastTime = timestamp;
  const hasAnim = ctrl.update(dt);
  if (hasAnim) needsRender = true;
  if (needsRender) {
    renderer.render(ctrl);
    needsRender = false;
  }
  requestAnimationFrame(gameLoop);
}
requestAnimationFrame(gameLoop);
