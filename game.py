import sys
import os
import json
import math
import random
import shutil
import copy
import atexit
import wave
import struct
import threading
import subprocess
import time as pytime
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(os.path.abspath(os.path.dirname(__file__)))
DATA_DIR = BASE_DIR / 'Data'
SAVE_DIR = DATA_DIR / 'Save Game'
SETTINGS_DIR = DATA_DIR / 'Settings'
FONT_DIR = DATA_DIR / 'Fonts'
SOUND_DIR = DATA_DIR / 'Sounds'
CUSTOM_DIR = DATA_DIR / 'Custom Seeds'
SETTINGS_FILE = SETTINGS_DIR / 'settings.json'

def run_splash():
    try:
        import tkinter as tk
        root = tk.Tk()
    except Exception:
        return
    root.overrideredirect(True)
    try:
        root.attributes('-topmost', True)
    except Exception:
        pass
    W, H = 520, 270
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    root.geometry('%dx%d+%d+%d' % (W, H, (sw - W) // 2, (sh - H) // 2))
    cv = tk.Canvas(root, width=W, height=H, bg='#555555', highlightthickness=0)
    cv.pack()
    st = {'p': 0.0, 'shown': 0.0, 'msg': 'Starting...', 'quit': False}

    def reader():
        try:
            for line in sys.stdin:
                line = line.strip()
                if line == 'quit':
                    break
                if line.startswith('p '):
                    parts = line.split(' ', 2)
                    try:
                        st['p'] = float(parts[1])
                    except ValueError:
                        pass
                    if len(parts) > 2:
                        st['msg'] = parts[2]
        except Exception:
            pass
        st['quit'] = True

    threading.Thread(target=reader, daemon=True).start()
    t0 = pytime.time()

    def tick():
        if st['quit'] or pytime.time() - t0 > 180:
            root.destroy()
            return
        st['shown'] += (st['p'] - st['shown']) * 0.15
        cv.delete('all')
        cv.create_rectangle(0, 0, W - 1, H - 1, fill='#555555', outline='black', width=6)
        cv.create_rectangle(0, 0, W, 70, fill='black', outline='black')
        cv.create_text(24, 36, text='LOW POLY EXPLORER', anchor='w', fill='white', font=('Consolas', 22, 'bold'))
        cx, cy, r = W // 2, 135, 30
        head = int((pytime.time() - t0) * 10) % 8
        for i in range(8):
            a = i * math.pi / 4
            x, y = cx + math.cos(a) * r, cy + math.sin(a) * r
            v = int(255 - ((head - i) % 8) * 26)
            s = 7
            cv.create_polygon(x, y - s, x + s, y, x, y + s, x - s, y, fill='#%02x%02x%02x' % (v, v, v), outline='black')
        bx0, bx1, by0, by1 = 60, 400, 195, 217
        cv.create_rectangle(bx0, by0, bx1, by1, fill='black', outline='black')
        frac = max(0.0, min(1.0, st['shown'] / 100.0))
        if frac > 0.01:
            cv.create_rectangle(bx0 + 3, by0 + 3, bx0 + 3 + (bx1 - bx0 - 6) * frac, by1 - 3, fill='#3c8cff', outline='')
        cv.create_text(430, (by0 + by1) // 2, text='%d%%' % int(st['shown']), anchor='w', fill='white',
                       font=('Consolas', 16, 'bold'))
        cv.create_text(bx0, 244, text=st['msg'], anchor='w', fill='white', font=('Consolas', 10))
        root.after(33, tick)

    tick()
    root.mainloop()


if '--splash' in sys.argv:
    run_splash()
    sys.exit(0)

_splash = None


def splash_send(line):
    global _splash
    if _splash is None:
        return
    try:
        _splash.stdin.write(line + '\n')
        _splash.stdin.flush()
    except Exception:
        _splash = None


def splash_report(pct, msg=''):
    splash_send('p %d %s' % (pct, msg))


def splash_close():
    splash_send('quit')


try:
    _splash = subprocess.Popen([sys.executable, os.path.abspath(__file__), '--splash'], stdin=subprocess.PIPE,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, universal_newlines=True,
                               bufsize=1)
except Exception:
    _splash = None
atexit.register(splash_close)
splash_report(5, 'Starting up')
splash_report(12, 'Importing engine (this is the slow part)')

from ursina import *  # noqa: E402,F401,F403
from panda3d.core import Filename  # noqa: E402

import math  # noqa: E402,F811
import random  # noqa: E402,F811
import copy  # noqa: E402,F811
import json  # noqa: E402,F811
import os  # noqa: E402,F811
import sys  # noqa: E402,F811
import shutil  # noqa: E402,F811
from datetime import datetime  # noqa: E402,F811
from pathlib import Path  # noqa: E402,F811

splash_report(32, 'Engine imported')
for _d in (DATA_DIR, SAVE_DIR, SETTINGS_DIR, FONT_DIR, SOUND_DIR, CUSTOM_DIR):
    try:
        _d.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

app = Ursina()
splash_report(40, 'Opening window')
window.title = 'Low Poly Explorer'
window.borderless = False
for _fn in (lambda: setattr(window.exit_button, 'visible', False),
            lambda: setattr(window.fps_counter, 'enabled', False),
            lambda: setattr(window.cog_button, 'visible', False),
            lambda: setattr(window.entity_counter, 'enabled', False),
            lambda: setattr(window.collider_counter, 'enabled', False)):
    try:
        _fn()
    except Exception:
        pass
try:
    camera.clip_plane_far = 320
    camera.clip_plane_near = 0.05
except Exception:
    pass

LOAD_START = 40.0
perf = pytime.perf_counter


def C(r, g, b, a=255):
    """0-255 colour helper (Ursina's color.rgb is 0-1 in newer versions)."""
    return Color(r / 255.0, g / 255.0, b / 255.0, a / 255.0)


# ==== WORLD BEGIN ============================================================
CELL = 2.0
CS = 16
CHUNK = CELL * CS
VIEW = 4
TAU = 6.283185307179586

ELEMENTS = ('oceans', 'rivers', 'trees', 'rocks', 'flowers', 'caves', 'structures')
STRUCTS = ('tent', 'camp', 'shed', 'cabin')
BIOME_KEYS = ('plains', 'forest', 'desert', 'tundra', 'jungle', 'savanna', 'swamp', 'mountains')


def default_custom():
    return {'biomes': {k: True for k in BIOME_KEYS}, 'water': True,
            'elements': {k: {'on': True, 'amt': 1.0} for k in ELEMENTS},
            'structs': {k: {'on': True, 'amt': 1.0} for k in STRUCTS},
            'sea_level': 0.0, 'height': 1.0, 'biome_size': 1.0, 'mountain_amt': 1.0}


CUSTOM_DEFAULT = default_custom()


def norm_custom(cu):
    c = default_custom()
    if not isinstance(cu, dict):
        return c
    for k, v in (cu.get('biomes') or {}).items():
        if k in c['biomes']:
            c['biomes'][k] = bool(v)
    if 'water' in cu:
        c['water'] = bool(cu['water'])
    for k in ('oceans', 'rivers', 'trees', 'rocks', 'flowers', 'caves'):   # legacy v2 keys
        if isinstance(cu.get(k), bool):
            c['elements'][k]['on'] = cu[k]
    if isinstance(cu.get('tree_density'), (int, float)):
        c['elements']['trees']['amt'] = float(cu['tree_density'])
    for k in ('sea_level', 'height', 'biome_size', 'mountain_amt'):
        if isinstance(cu.get(k), (int, float)) and not isinstance(cu.get(k), bool):
            c[k] = float(cu[k])
    for grp in ('elements', 'structs'):
        src = cu.get(grp)
        if isinstance(src, dict):
            for k, v in src.items():
                if k in c[grp] and isinstance(v, dict):
                    c[grp][k]['on'] = bool(v.get('on', True))
                    c[grp][k]['amt'] = float(v.get('amt', 1.0))
    return c


BIOME_NAMES = {0: 'Ocean', 1: 'Beach', 2: 'Plains', 3: 'Forest', 4: 'Desert', 5: 'Tundra', 6: 'Mountains',
               7: 'Jungle', 8: 'Savanna', 9: 'Swamp'}
CENTERS = {'plains': (0.0, -0.25, 2), 'forest': (0.0, 0.4, 3), 'desert': (0.65, -0.5, 4),
           'tundra': (-0.65, 0.0, 5), 'jungle': (0.6, 0.6, 7), 'savanna': (0.65, 0.0, 8), 'swamp': (0.1, 0.8, 9)}
TREE_KINDS = ('tree', 'spruce', 'cactus', 'acacia', 'jungle', 'dead', 'bush')
TABLE = {
    1: [('rock', 0.01)],
    2: [('tree', 0.05), ('bush', 0.02), ('rock', 0.03), ('flower', 0.30), ('tuft', 0.45)],
    3: [('tree', 0.50), ('bush', 0.05), ('rock', 0.03), ('flower', 0.06), ('tuft', 0.15)],
    4: [('cactus', 0.06), ('dead', 0.01), ('rock', 0.05)],
    5: [('spruce', 0.12), ('rock', 0.04)],
    6: [('spruce', 0.04), ('rock', 0.12)],
    7: [('jungle', 0.42), ('bush', 0.15), ('flower', 0.06), ('tuft', 0.2)],
    8: [('acacia', 0.04), ('bush', 0.04), ('rock', 0.03), ('tuft', 0.4)],
    9: [('dead', 0.05), ('tree', 0.04), ('tuft', 0.3), ('rock', 0.01)],
}
MAP_TH = math.radians(52)


def clampf(v, a=0.0, b=1.0):
    return a if v < a else (b if v > b else v)


def smooth(a, b, x):
    t = clampf((x - a) / (b - a))
    return t * t * (3 - 2 * t)


def hash01(a, b, s):
    return (((a * 73856093) ^ (b * 19349663) ^ (s * 83492791)) & 0xFFFF) / 65535.0


class Noise:
    def __init__(self, seed):
        r = random.Random(seed)
        p = list(range(256))
        r.shuffle(p)
        self.p = p + p
        ang = [r.random() * TAU for _ in range(256)]
        self.gx = [math.cos(a) for a in ang]
        self.gz = [math.sin(a) for a in ang]

    def n(self, x, z):
        xf = math.floor(x)
        zf = math.floor(z)
        fx = x - xf
        fz = z - zf
        xi = int(xf) & 255
        zi = int(zf) & 255
        p = self.p
        gx = self.gx
        gz = self.gz
        a = p[p[xi] + zi]
        b = p[p[xi + 1] + zi]
        c = p[p[xi] + zi + 1]
        d = p[p[xi + 1] + zi + 1]
        u = fx * fx * fx * (fx * (fx * 6 - 15) + 10)
        v = fz * fz * fz * (fz * (fz * 6 - 15) + 10)
        n00 = gx[a] * fx + gz[a] * fz
        n10 = gx[b] * (fx - 1) + gz[b] * fz
        n01 = gx[c] * fx + gz[c] * (fz - 1)
        n11 = gx[d] * (fx - 1) + gz[d] * (fz - 1)
        n0 = n00 + u * (n10 - n00)
        n1 = n01 + u * (n11 - n01)
        return (n0 + v * (n1 - n0)) * 1.41


def fbm(nz, x, z, octs):
    s = 0.0
    a = 1.0
    f = 1.0
    tot = 0.0
    n = nz.n
    for _ in range(octs):
        s += n(x * f, z * f) * a
        tot += a
        a *= 0.5
        f *= 2.0
    return s / tot


class WorldGen:
    """Pure terrain maths: same seed + same settings -> identical world, always."""

    def __init__(self, cfg):
        mode = cfg['mode']
        self.base = int(cfg.get('base', 0))
        c = norm_custom(cfg.get('custom'))
        self.flat = mode in ('Flat +', 'Flat')
        self.nothing = (mode == 'Flat +')
        self.mountains, self.mamt = True, 1.0
        self.ocean, self.oamt, self.rivers, self.ramt = True, 1.0, True, 1.0
        self.tdens = self.rdens = self.fdens = self.cdens = self.sdens = 1.0
        self.sdw = {k: 1.0 for k in STRUCTS}
        self.bsize, self.amp, sea, self.water = 1.0, 1.0, 0.0, True
        biomes = {'plains', 'forest', 'desert', 'tundra', 'jungle', 'savanna', 'swamp'}
        if mode == 'Flat +':
            self.water = False
            self.tdens = self.rdens = self.fdens = self.cdens = self.sdens = 0.0
        elif mode == 'Flat':
            sea, self.cdens, self.tdens, self.sdens = -0.6, 0.0, 3.0, 1.5
            biomes, self.mountains = {'plains'}, False
        elif mode == 'Custom':
            b, E = c['biomes'], c['elements']
            biomes = {k for k in BIOME_KEYS if k != 'mountains' and b.get(k)}
            self.mountains, self.mamt = bool(b.get('mountains')), float(c['mountain_amt'])
            self.water = bool(c['water'])
            self.ocean, self.oamt = E['oceans']['on'], E['oceans']['amt']
            self.rivers, self.ramt = E['rivers']['on'], E['rivers']['amt']
            self.tdens = E['trees']['amt'] if E['trees']['on'] else 0.0
            self.rdens = E['rocks']['amt'] if E['rocks']['on'] else 0.0
            self.fdens = E['flowers']['amt'] if E['flowers']['on'] else 0.0
            self.cdens = E['caves']['amt'] if E['caves']['on'] else 0.0
            self.sdens = E['structures']['amt'] if E['structures']['on'] else 0.0
            for k in STRUCTS:
                self.sdw[k] = c['structs'][k]['amt'] if c['structs'][k]['on'] else 0.0
            sea, self.amp, self.bsize = float(c['sea_level']), float(c['height']), float(c['biome_size'])
        if not biomes and not self.mountains:
            biomes = {'plains'}
        self.only_mtn = self.mountains and not biomes
        self.centers = [v for k, v in CENTERS.items() if k in biomes] or [(0.0, -0.25, 2)]
        self.sea = sea if self.water else -9999.0
        self.sea_raw = sea
        s = self.base * 10
        self.n_c, self.n_h, self.n_mm, self.n_r = Noise(s + 1), Noise(s + 2), Noise(s + 3), Noise(s + 4)
        self.n_t, self.n_m, self.n_rv = Noise(s + 5), Noise(s + 6), Noise(s + 7)
        self.n_p, self.n_d = Noise(s + 8), Noise(s + 9)

    def pick(self, h, t, m):
        sea = self.sea
        if h < sea:
            return 0
        if self.water and h < sea + 0.9:
            return 1
        if self.mountains and (self.only_mtn or h > 22 * self.amp):
            return 6
        best, bd = 2, 99.0
        for ct, cm, bid in self.centers:
            d = (t - ct) ** 2 + (m - cm) ** 2
            if d < bd:
                bd, best = d, bid
        return best

    def hb(self, x, z):
        if self.flat:
            if self.nothing:
                return 0.0, 2, 0.0, 0.0
            h = fbm(self.n_d, x * 0.05, z * 0.05, 2) * 0.3
            if self.water:
                pn = fbm(self.n_p, x * 0.022, z * 0.022, 2)
                if pn > 0.2:
                    h -= min(3.0, (pn - 0.2) * 12.0)
            b = 2
            if self.water:
                b = 0 if h < self.sea else (1 if h < self.sea + 0.35 else 2)
            return h, b, 0.0, 0.0
        s = self.bsize
        t = fbm(self.n_t, x * 0.0022 / s, z * 0.0026 / s, 2) * 1.7
        m = fbm(self.n_m, x * 0.0026 / s, z * 0.0022 / s, 2) * 1.7
        cont = fbm(self.n_c, x * 0.0032 / s, z * 0.0032 / s, 3)
        cont = cont + (1.0 - self.oamt) * 0.3 if self.ocean else abs(cont) + 0.18
        base = (cont + 0.1) * 38.0
        h = base + fbm(self.n_h, x * 0.017, z * 0.017, 3) * (2.2 if t > 0.4 else 5.5)
        if self.mountains:
            if self.only_mtn:
                mm = 1.0
            else:
                mm = smooth(0.05, 0.45, fbm(self.n_mm, x * 0.0026 / s, z * 0.0026 / s, 2) * 1.6)
            mm *= clampf(self.mamt, 0.0, 2.0)
            if mm > 0.0:
                rg = max(0.0, 1.0 - abs(fbm(self.n_r, x * 0.009, z * 0.009, 3) * 1.5))
                h += mm * (rg * rg * 62.0 + 8.0 * mm) * clampf((base + 3) / 10.0)
        if h > 0:
            h *= self.amp
        if self.rivers and self.water:
            wd = 0.06 * clampf(self.ramt, 0.2, 3.0)
            rv = abs(fbm(self.n_rv, x * 0.0042, z * 0.0042, 2) * 1.5)
            if rv < wd and h > self.sea - 3:
                f = 1.0 - rv / wd
                f = f * f * (3 - 2 * f)
                h += (self.sea - 1.5 - h) * f * clampf(1.0 - (h - 8.0) / 22.0)
        if not self.water and h < self.sea_raw + 1.0:
            h = self.sea_raw + 1.0
        b = self.pick(h, t, m)
        if b == 9:
            tgt = (self.sea if self.water else self.sea_raw) + 0.3 + fbm(self.n_d, x * 0.05, z * 0.05, 2) * 1.6
            h = tgt if self.water else max(tgt, self.sea_raw + 1.0)
        return h, b, t, m

    def base_color(self, h, b):
        if b == 0:
            d = clampf((self.sea - h) / 18.0) if self.water else 0.0
            return (78 - 40 * d, 120 - 50 * d, 150 - 40 * d)
        if b == 1:
            return (226, 210, 154)
        if b == 2:
            k = clampf(h / 30.0)
            return (104 - 14 * k, 176 - 20 * k, 76.0)
        if b == 3:
            return (60.0, 128.0, 62.0)
        if b == 4:
            return (228.0, 198.0, 124.0)
        if b == 5:
            return (216.0, 226.0, 234.0)
        if b == 7:
            return (34.0, 140.0, 56.0)
        if b == 8:
            return (190.0, 176.0, 92.0)
        if b == 9:
            return (66.0, 98.0, 62.0)
        lo = clampf((h - 14.0) / 14.0)
        r = 90 + (128 - 90) * lo
        g = 140 + (124 - 140) * lo
        bl = 78 + (122 - 78) * lo
        sn = clampf((h - 36.0 * self.amp) / 9.0)
        return (r + (244 - r) * sn, g + (247 - g) * sn, bl + (252 - bl) * sn)


# ---- mesh helpers (raw tuples, converted to Vec3/Color in one go) -------------
def p_cone(V, Cc, x, y, z, r, h, n, rgb, rot=0.0):
    ap = (x, y + h, z)
    for i in range(n):
        a0 = rot + TAU * i / n
        a1 = rot + TAU * (i + 1) / n
        sh = 0.68 + 0.32 * (0.5 + 0.5 * math.cos(a0 + 0.9))
        c = (rgb[0] * sh / 255.0, rgb[1] * sh / 255.0, rgb[2] * sh / 255.0)
        V += [ap, (x + math.cos(a0) * r, y, z + math.sin(a0) * r), (x + math.cos(a1) * r, y, z + math.sin(a1) * r)]
        Cc += [c, c, c]


def p_prism(V, Cc, x, y, z, r, h, n, rgb, rot=0.0):
    for i in range(n):
        a0 = rot + TAU * i / n
        a1 = rot + TAU * (i + 1) / n
        sh = 0.65 + 0.35 * (0.5 + 0.5 * math.cos(a0 + 0.5))
        c = (rgb[0] * sh / 255.0, rgb[1] * sh / 255.0, rgb[2] * sh / 255.0)
        b0 = (x + math.cos(a0) * r, y, z + math.sin(a0) * r)
        b1 = (x + math.cos(a1) * r, y, z + math.sin(a1) * r)
        t0 = (b0[0], y + h, b0[2])
        t1 = (b1[0], y + h, b1[2])
        V += [b0, b1, t1, b0, t1, t0]
        Cc += [c] * 6


def p_octa(V, Cc, x, y, z, sx, sy, sz, rgb):
    ring = [(x + sx, y, z), (x, y, z + sz), (x - sx, y, z), (x, y, z - sz)]
    top, bot = (x, y + sy, z), (x, y - sy * 0.6, z)
    for i in range(4):
        a, b = ring[i], ring[(i + 1) % 4]
        for apex, sh in ((top, 1.0 - 0.13 * i), (bot, 0.55)):
            c = (rgb[0] * sh / 255.0, rgb[1] * sh / 255.0, rgb[2] * sh / 255.0)
            V += [apex, a, b]
            Cc += [c, c, c]


def p_box(V, Cc, x, y, z, sx, sy, sz, rgb):
    p = [(x + a * sx, y + b * sy, z + c * sz) for a in (-1, 1) for b in (-1, 1) for c in (-1, 1)]
    faces = [((0, 1, 3, 2), 0.75), ((4, 6, 7, 5), 0.85), ((0, 4, 5, 1), 0.5), ((2, 3, 7, 6), 1.0),
             ((0, 2, 6, 4), 0.65), ((1, 5, 7, 3), 0.7)]
    for (a, b, c, d), sh in faces:
        col = (rgb[0] * sh / 255.0, rgb[1] * sh / 255.0, rgb[2] * sh / 255.0)
        V += [p[a], p[b], p[c], p[a], p[c], p[d]]
        Cc += [col] * 6


def p_tuft(V, Cc, x, y, z, h, rgb):
    for k in range(3):
        a = TAU * k / 3.0
        dx, dz = math.cos(a) * 0.09, math.sin(a) * 0.09
        sh = 0.8 + 0.2 * k / 2.0
        c = (rgb[0] * sh / 255.0, rgb[1] * sh / 255.0, rgb[2] * sh / 255.0)
        V += [(x + dx, y, z + dz), (x - dx, y, z - dz), (x + dz * 0.8, y + h, z - dx * 0.8)]
        Cc += [c, c, c]


def p_dome(V, Cc, x, y0, z, R, Hh, gap, rgb, segs=10, rings=3):
    step = TAU / segs
    for k in range(rings):
        p0, p1 = k * (math.pi / 2) / rings, (k + 1) * (math.pi / 2) / rings
        r0, r1 = R * math.cos(p0), R * math.cos(p1)
        y_0, y_1 = y0 + Hh * math.sin(p0), y0 + Hh * math.sin(p1)
        for i in range(segs):
            mid = (i + 0.5) * step
            dd = abs((mid - gap + math.pi) % TAU - math.pi)
            if k < 2 and dd < step * 1.05:
                continue
            a0, a1 = i * step, (i + 1) * step
            sh = 0.72 + 0.28 * (0.5 + 0.5 * math.cos(a0 * 2 + k))
            c = (rgb[0] * sh / 255.0, rgb[1] * sh / 255.0, rgb[2] * sh / 255.0)
            A = (x + math.cos(a0) * r0, y_0, z + math.sin(a0) * r0)
            B = (x + math.cos(a1) * r0, y_0, z + math.sin(a1) * r0)
            Cn = (x + math.cos(a1) * r1, y_1, z + math.sin(a1) * r1)
            D = (x + math.cos(a0) * r1, y_1, z + math.sin(a0) * r1)
            V += [A, B, Cn, A, Cn, D]
            Cc += [c] * 6


def to_mesh(V, Cc):
    return Mesh(vertices=[Vec3(*v) for v in V], colors=[Color(c[0], c[1], c[2], 1) for c in Cc], mode='triangle')


def p_quad(V, Cc, a, b, c, d, rgb, sh=1.0):
    col = (rgb[0] * sh / 255.0, rgb[1] * sh / 255.0, rgb[2] * sh / 255.0)
    V += [a, b, c, a, c, d]
    Cc += [col] * 6


def p_tri(V, Cc, a, b, c, rgb, sh=1.0):
    col = (rgb[0] * sh / 255.0, rgb[1] * sh / 255.0, rgb[2] * sh / 255.0)
    V += [a, b, c]
    Cc += [col] * 3


def seg_obst(obst, cx, cz, ax, az, bx, bz, step=0.55, r=0.3):
    n = max(1, int(math.hypot(bx - ax, bz - az) / step))
    for i in range(n + 1):
        t = i / float(n)
        obst.append((cx * CHUNK + ax + (bx - ax) * t, cz * CHUNK + az + (bz - az) * t, r, 99.0, 0))


def build_tent(V, Cc, x, y, z, hw, hd, hgt, rgb):
    r0, r1 = (x, y + hgt, z - hd), (x, y + hgt, z + hd)
    p_quad(V, Cc, (x - hw, y, z - hd), (x - hw, y, z + hd), r1, r0, rgb, 0.85)
    p_quad(V, Cc, (x + hw, y, z + hd), (x + hw, y, z - hd), r0, r1, rgb, 1.0)
    p_tri(V, Cc, (x - hw, y, z - hd), r0, (x + hw, y, z - hd), (36, 30, 28), 0.9)
    p_tri(V, Cc, (x + hw, y, z + hd), r1, (x - hw, y, z + hd), rgb, 0.7)


def build_hut(V, Cc, obst, cx, cz, x, y, z, hw, hd, hgt, wood, roof, dw=1.2):
    t = 0.2
    p_box(V, Cc, x, y - 0.8, z, hw + 0.15, 1.0, hd + 0.15, (112, 110, 106))
    lw = (hw - dw) / 2.0
    p_box(V, Cc, x - dw - lw, y + hgt / 2, z - hd, lw, hgt / 2, t, wood)
    p_box(V, Cc, x + dw + lw, y + hgt / 2, z - hd, lw, hgt / 2, t, wood)
    p_box(V, Cc, x, y + hgt - 0.35, z - hd, dw, 0.35, t, wood)
    p_box(V, Cc, x, y + hgt / 2, z + hd, hw, hgt / 2, t, wood)
    p_box(V, Cc, x - hw, y + hgt / 2, z, t, hgt / 2, hd, wood)
    p_box(V, Cc, x + hw, y + hgt / 2, z, t, hgt / 2, hd, wood)
    ov, rh = 0.35, 1.2
    p_quad(V, Cc, (x - hw - ov, y + hgt, z - hd - ov), (x + hw + ov, y + hgt, z - hd - ov),
           (x + hw + ov, y + hgt + rh, z), (x - hw - ov, y + hgt + rh, z), roof, 0.9)
    p_quad(V, Cc, (x + hw + ov, y + hgt, z + hd + ov), (x - hw - ov, y + hgt, z + hd + ov),
           (x - hw - ov, y + hgt + rh, z), (x + hw + ov, y + hgt + rh, z), roof, 0.75)
    p_tri(V, Cc, (x - hw, y + hgt, z - hd), (x - hw, y + hgt, z + hd), (x - hw, y + hgt + rh, z), wood, 0.8)
    p_tri(V, Cc, (x + hw, y + hgt, z + hd), (x + hw, y + hgt, z - hd), (x + hw, y + hgt + rh, z), wood, 0.8)
    seg_obst(obst, cx, cz, x - hw, z - hd, x - dw, z - hd)
    seg_obst(obst, cx, cz, x + dw, z - hd, x + hw, z - hd)
    seg_obst(obst, cx, cz, x - hw, z + hd, x + hw, z + hd)
    seg_obst(obst, cx, cz, x - hw, z - hd, x - hw, z + hd)
    seg_obst(obst, cx, cz, x + hw, z - hd, x + hw, z + hd)


def map_color(gen, h, b):
    if b == 0 and gen.water:
        d = clampf((gen.sea - h) / 20.0)
        return (int(60 - 30 * d), int(120 - 50 * d), int(200 - 60 * d))
    c = gen.base_color(h, b)
    k = 0.85 + 0.25 * clampf(h / 40.0)
    return (int(min(255, c[0] * k)), int(min(255, c[1] * k)), int(min(255, c[2] * k)))


def map2d_job(gen, cx, cz, span, N, Image):
    img = Image.new('RGB', (N, N))
    step = span / float(N)
    for j in range(N):
        for i in range(N):
            h, b, _, _ = gen.hb(cx + (i - N / 2.0 + 0.5) * step, cz + (j - N / 2.0 + 0.5) * step)
            img.putpixel((i, N - 1 - j), map_color(gen, h, b))
        if j % 3 == 2:
            yield None
    yield img


def proj3(X, Zr, yv):
    st, ct = math.sin(MAP_TH), math.cos(MAP_TH)
    return (X, Zr * st + yv * ct, Zr * ct - yv * st)


def map3d_job(gen, cx, cz, span, N):
    hk = 2.6 / span
    base_h = gen.sea if gen.water else -5.0
    rows = []
    for j in range(N + 1):
        rows.append([gen.hb(cx + (i / float(N) - 0.5) * span, cz + (j / float(N) - 0.5) * span)[:2]
                     for i in range(N + 1)])
        if j % 2 == 1:
            yield None
    V, Cc = [], []

    def pt(i, j):
        h = rows[j][i][0]
        return (i / float(N) - 0.5, (max(h, base_h) - base_h) * hk, j / float(N) - 0.5)
    for j in range(N):
        for i in range(N):
            a, b, c, d = pt(i, j), pt(i + 1, j), pt(i, j + 1), pt(i + 1, j + 1)
            for tri_ in ((a, b, d), (a, d, c)):
                p0, p1, p2 = tri_
                e1 = (p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2])
                e2 = (p2[0] - p0[0], p2[1] - p0[1], p2[2] - p0[2])
                ny = abs(e1[2] * e2[0] - e1[0] * e2[2])
                nx = e1[1] * e2[2] - e1[2] * e2[1]
                nz = e1[0] * e2[1] - e1[1] * e2[0]
                ln = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
                sh = 0.65 + 0.45 * max(0.0, (nx * 0.4 + ny * 0.8 + nz * 0.4) / ln)
                h, bb = rows[j][i]
                col = map_color(gen, h, bb)
                c3 = (min(1.0, col[0] * sh / 255.0), min(1.0, col[1] * sh / 255.0), min(1.0, col[2] * sh / 255.0))
                for p in tri_:
                    V.append(proj3(p[0], p[2], p[1]))
                    Cc.append(c3)
        if j % 3 == 2:
            yield None
    yield (V, Cc)


class World:
    def __init__(self, cfg, lowpoly=True, water_tex=None):
        self.cfg = cfg
        self.gen = WorldGen(cfg)
        self.sea = self.gen.sea
        self.hs = self.gen.base & 0xFFFFFF
        self.jit = 0.34 if lowpoly else 0.0
        self.lowpoly = lowpoly
        self.hcache, self.ents, self.obst, self.caves = {}, {}, {}, {}
        self.queue, self.job, self.last_pc = [], None, None
        self.water_ent = None
        if self.gen.water:
            self.water_ent = Entity(model='quad', rotation_x=90, scale=(520, 520, 1), y=self.sea,
                                    color=Color(0.30, 0.55, 0.88, 0.62), double_sided=True)
            if water_tex is not None:
                self.water_ent.texture = water_tex
                self.water_ent.texture_scale = (130, 130)
        self.spawn = self.find_spawn()

    # ---------------------------------------------------------------- spawn
    def find_spawn(self):
        g = self.gen
        for r in range(0, 900, 12):
            steps = 1 if r == 0 else 12
            for k in range(steps):
                a = TAU * k / steps
                x, z = math.cos(a) * r, math.sin(a) * r
                h, b, _, _ = g.hb(x, z)
                if b in (2, 3, 4, 5, 7, 8, 9) and h > g.sea + 1.5:
                    return (x, z)
        return (0.0, 0.0)

    # --------------------------------------------------------------- heights
    def _rows(self, cx, cz, H, B, j0, j1):
        n = CS + 1
        g = self.gen
        jit = self.jit
        hs = self.hs
        for j in range(j0, j1):
            gz = cz * CS + j
            wz = gz * CELL
            for i in range(n):
                gx = cx * CS + i
                h, b, _, _ = g.hb(gx * CELL, wz)
                if jit and not g.nothing:
                    h += (hash01(gx, gz, hs) - 0.5) * jit
                H[j * n + i] = h
                B[j * n + i] = b

    def heights(self, cx, cz):
        c = self.hcache.get((cx, cz))
        if c is None:
            n = CS + 1
            H, B = [0.0] * (n * n), [0] * (n * n)
            self._rows(cx, cz, H, B, 0, n)
            c = (H, B)
            self.hcache[(cx, cz)] = c
        return c

    @staticmethod
    def _lh(H, lx, lz):
        n = CS + 1
        lx /= CELL
        lz /= CELL
        i = max(0, min(int(lx), CS - 1))
        j = max(0, min(int(lz), CS - 1))
        fx, fz = lx - i, lz - j
        h00, h10, h01, h11 = H[j * n + i], H[j * n + i + 1], H[(j + 1) * n + i], H[(j + 1) * n + i + 1]
        if fx >= fz:
            return h00 + fx * (h10 - h00) + fz * (h11 - h10)
        return h00 + fz * (h01 - h00) + fx * (h11 - h01)

    def surface(self, x, z):
        cx, cz = int(math.floor(x / CHUNK)), int(math.floor(z / CHUNK))
        H = self.heights(cx, cz)[0]
        return self._lh(H, x - cx * CHUNK, z - cz * CHUNK)

    def biome_at(self, x, z):
        cx, cz = int(math.floor(x / CHUNK)), int(math.floor(z / CHUNK))
        B = self.heights(cx, cz)[1]
        i = max(0, min(CS, int(round((x - cx * CHUNK) / CELL))))
        j = max(0, min(CS, int(round((z - cz * CHUNK) / CELL))))
        return BIOME_NAMES.get(B[j * (CS + 1) + i], '?')

    @staticmethod
    def near(x, z, m=8.0):
        cx, cz = int(math.floor(x / CHUNK)), int(math.floor(z / CHUNK))
        lx, lz = x - cx * CHUNK, z - cz * CHUNK
        xs, zs = [cx], [cz]
        if lx < m:
            xs.append(cx - 1)
        if lx > CHUNK - m:
            xs.append(cx + 1)
        if lz < m:
            zs.append(cz - 1)
        if lz > CHUNK - m:
            zs.append(cz + 1)
        return [(a, b) for a in xs for b in zs]

    def ground(self, x, z):
        s = self.surface(x, z)
        for k in self.near(x, z, 3.0):
            for ox, oz, r, top, kind in self.obst.get(k, ()):
                if kind == 1 and (x - ox) ** 2 + (z - oz) ** 2 < (r * 0.85) ** 2 and top > s:
                    s = top
        return s

    def push(self, x, z, y):
        for k in self.near(x, z, 8.0):
            for ox, oz, r, top, kind in self.obst.get(k, ()):
                dx, dz = x - ox, z - oz
                rr = r + 0.5
                if dx * dx + dz * dz < rr * rr and y < top - 0.45:
                    d = math.sqrt(dx * dx + dz * dz) or 1e-4
                    x, z = ox + dx / d * rr, oz + dz / d * rr
            for ox, oz, R, gap in self.caves.get(k, ()):
                dx, dz = x - ox, z - oz
                d = math.sqrt(dx * dx + dz * dz) or 1e-4
                if R - 0.8 < d < R + 0.5:
                    ang = math.atan2(dz, dx)
                    if abs((ang - gap + math.pi) % TAU - math.pi) > 0.5:
                        t = R + 0.5 if d > R else R - 0.8
                        x, z = ox + dx / d * t, oz + dz / d * t
        return x, z

    # ------------------------------------------------------------ chunk build
    def chunk_job(self, key):
        cx, cz = key
        n = CS + 1
        c = self.hcache.get(key)
        if c is None:
            H, B = [0.0] * (n * n), [0] * (n * n)
            for j0 in range(0, n, 3):
                self._rows(cx, cz, H, B, j0, min(n, j0 + 3))
                yield
            self.hcache[key] = (H, B)
        else:
            H, B = c
        g = self.gen
        vc = [g.base_color(H[k], B[k]) for k in range(n * n)]
        yield
        V, Cl = [], []
        facets = self.lowpoly
        hs = self.hs
        for j in range(CS):
            for i in range(CS):
                a = j * n + i
                b, c2, d = a + 1, a + n, a + n + 1
                x0, x1, z0, z1 = i * CELL, i * CELL + CELL, j * CELL, j * CELL + CELL
                for (p0, p1, p2) in (((x0, H[a], z0, a), (x1, H[b], z0, b), (x1, H[d], z1, d)),
                                     ((x0, H[a], z0, a), (x1, H[d], z1, d), (x0, H[c2], z1, c2))):
                    e1 = (p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2])
                    e2 = (p2[0] - p0[0], p2[1] - p0[1], p2[2] - p0[2])
                    nx = e1[1] * e2[2] - e1[2] * e2[1]
                    ny = e1[2] * e2[0] - e1[0] * e2[2]
                    nz = e1[0] * e2[1] - e1[1] * e2[0]
                    if ny < 0:
                        nx, ny, nz = -nx, -ny, -nz
                    ln = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
                    nx, ny, nz = nx / ln, ny / ln, nz / ln
                    c0, c1, cc = vc[p0[3]], vc[p1[3]], vc[p2[3]]
                    r = (c0[0] + c1[0] + cc[0]) / 3.0
                    gg = (c0[1] + c1[1] + cc[1]) / 3.0
                    bb = (c0[2] + c1[2] + cc[2]) / 3.0
                    bid = B[p0[3]]
                    if ny < 0.74 and bid not in (0, 4):
                        k = clampf((0.74 - ny) * 4.0)
                        r, gg, bb = r + (118 - r) * k, gg + (112 - gg) * k, bb + (106 - bb) * k
                    sh = 0.66 + 0.46 * max(0.0, nx * 0.42 + ny * 0.8 + nz * 0.35)
                    if facets:
                        sh *= 0.94 + 0.12 * hash01(i + cx * CS, j + cz * CS, hs + p0[3] % 3)
                    col = Color(min(1.0, r * sh / 255.0), min(1.0, gg * sh / 255.0), min(1.0, bb * sh / 255.0), 1)
                    V += [Vec3(p0[0], p0[1], p0[2]), Vec3(p1[0], p1[1], p1[2]), Vec3(p2[0], p2[1], p2[2])]
                    Cl += [col, col, col]
            if j % 4 == 3:
                yield
        ox, oz = cx * CHUNK, cz * CHUNK
        terrain = Entity(model=Mesh(vertices=V, colors=Cl, mode='triangle'), position=(ox, 0, oz), double_sided=True)
        yield
        PV, PC, obst, caves = yield from self._props(key, H, B)
        props = None
        if PV:
            props = Entity(model=to_mesh(PV, PC), position=(ox, 0, oz), double_sided=True)
        self.obst[key] = obst
        self.caves[key] = caves
        self.ents[key] = [e for e in (terrain, props) if e is not None]
        yield

    def _structs(self, rng, H, B, PV, PC, obst, cx, cz):
        g = self.gen
        if g.nothing or g.sdens <= 0:
            return
        n, sea = CS + 1, g.sea
        for kind, pr, rx, rz in (('tent', 0.10, 1.8, 2.0), ('camp', 0.05, 5.0, 4.0), ('shed', 0.04, 2.6, 2.6),
                                 ('cabin', 0.03, 4.0, 3.4)):
            if rng.random() >= pr * g.sdens * g.sdw.get(kind, 1.0):
                continue
            for _ in range(6):
                lx, lz = rng.uniform(rx + 2, CHUNK - rx - 2), rng.uniform(rz + 2, CHUNK - rz - 2)
                hs = [self._lh(H, lx + a * rx, lz + b * rz) for a in (-1, 0, 1) for b in (-1, 0, 1)]
                i, j = int(round(lx / CELL)), int(round(lz / CELL))
                if max(hs) - min(hs) < 0.9 and min(hs) > sea + 1.2 and B[j * n + i] not in (0, 1, 6):
                    self._build_struct(kind, rng, lx, lz, max(hs), PV, PC, obst, cx, cz)
                    break

    def _build_struct(self, kind, rng, x, z, y, PV, PC, obst, cx, cz):
        wx, wz = cx * CHUNK + x, cz * CHUNK + z
        canvas = rng.choice([(200, 170, 110), (190, 70, 60), (70, 110, 170), (90, 140, 80)])
        if kind == 'tent':
            build_tent(PV, PC, x, y, z, 1.3, 1.5, 1.7, canvas)
            obst.append((wx, wz - 0.7, 1.0, 99.0, 0))
            obst.append((wx, wz + 0.7, 1.0, 99.0, 0))
        elif kind == 'camp':
            for q in range(7):
                a = TAU * q / 7
                p_octa(PV, PC, x + math.cos(a) * 0.9, y + 0.1, z + math.sin(a) * 0.9, 0.3, 0.2, 0.3, (130, 128, 124))
            p_octa(PV, PC, x, y + 0.2, z, 0.35, 0.35, 0.35, (255, 140, 30))
            p_octa(PV, PC, x, y + 0.1, z, 0.55, 0.12, 0.55, (50, 44, 40))
            for q in range(3):
                a = TAU * q / 3 + 0.6
                p_box(PV, PC, x + math.cos(a) * 2.3, y + 0.2, z + math.sin(a) * 2.3, 0.7, 0.2, 0.2, (120, 84, 52))
            build_tent(PV, PC, x + 3.4, y, z + 0.4, 1.3, 1.5, 1.7, canvas)
            obst.append((wx, wz, 0.7, 99.0, 0))
            obst.append((wx + 3.4, wz + 0.4 - 0.7, 1.0, 99.0, 0))
            obst.append((wx + 3.4, wz + 0.4 + 0.7, 1.0, 99.0, 0))
        elif kind == 'shed':
            build_hut(PV, PC, obst, cx, cz, x, y, z, 2.0, 2.0, 2.4, (132, 94, 58), (96, 60, 50))
            p_box(PV, PC, x + 1.2, y + 0.35, z + 1.2, 0.35, 0.35, 0.35, (150, 110, 60))
        else:
            build_hut(PV, PC, obst, cx, cz, x, y, z, 3.2, 2.6, 2.9, (150, 106, 64), (110, 56, 46), 1.3)
            p_box(PV, PC, x, y + 0.05, z - 2.6 - 1.0, 2.9, 0.1, 1.0, (126, 88, 54))
            p_box(PV, PC, x + 2.3, y + 4.2, z + 1.7, 0.35, 1.2, 0.35, (120, 118, 114))
            p_box(PV, PC, x - 2.2, y + 0.35, z + 1.6, 0.5, 0.25, 0.9, (170, 60, 60))
            p_box(PV, PC, x + 1.0, y + 0.45, z + 1.6, 0.5, 0.05, 0.4, (110, 76, 44))

    def _props(self, key, H, B):
        cx, cz = key
        g = self.gen
        PV, PC, obst, caves = [], [], [], []
        if g.nothing:
            return PV, PC, obst, caves
        rng = random.Random((g.base * 7919 + cx * 73856093 + cz * 19349663) & 0xFFFFFFFF)
        sea, n = g.sea, CS + 1
        for att in range(150):
            if att % 50 == 49:
                yield
            lx, lz = rng.uniform(1, CHUNK - 1), rng.uniform(1, CHUNK - 1)
            h = self._lh(H, lx, lz)
            i = max(0, min(CS, int(round(lx / CELL))))
            j = max(0, min(CS, int(round(lz / CELL))))
            b = B[j * n + i]
            plan = TABLE.get(b)
            if not plan or h < sea + 0.4:
                continue
            ii, jj = min(int(lx / CELL), CS - 1), min(int(lz / CELL), CS - 1)
            slope = max(abs(H[jj * n + ii + 1] - H[jj * n + ii]), abs(H[(jj + 1) * n + ii] - H[jj * n + ii])) / CELL
            r, acc, kind = rng.random(), 0.0, None
            for kd, pr in plan:
                if kd in TREE_KINDS:
                    pr *= g.tdens
                elif kd == 'rock':
                    pr *= g.rdens
                else:
                    pr *= g.fdens
                acc += pr
                if r < acc:
                    kind = kd
                    break
            if kind is None:
                continue
            wx, wz = cx * CHUNK + lx, cz * CHUNK + lz
            s = rng.uniform(0.8, 1.45)
            sw, sh = rng.uniform(0.8, 1.5), rng.uniform(0.9, 1.5)
            if kind in TREE_KINDS and kind != 'bush' and slope > 0.75:
                continue
            if kind == 'tree':
                p_prism(PV, PC, lx, h - 0.1, lz, 0.28 * sw, 2.7 * sh, 5, (104, 76, 48))
                gr = rng.randint(100, 160)
                crown = (50 + rng.randint(0, 40), gr, 55 + rng.randint(0, 25))
                if rng.random() < 0.3:
                    crown = (150 + rng.randint(0, 40), 110 + rng.randint(0, 30), 40)
                p_octa(PV, PC, lx, h + 3.5 * sh, lz, 2.0 * sw, 1.9 * sh, 2.0 * sw, crown)
                p_octa(PV, PC, lx + 0.5 * sw, h + 5.0 * sh, lz - 0.3 * sw, 1.3 * sw, 1.2 * sh, 1.3 * sw, crown)
                obst.append((wx, wz, 0.3 * sw, 99.0, 0))
            elif kind == 'spruce':
                p_prism(PV, PC, lx, h - 0.1, lz, 0.22 * sw, 1.6 * sh, 5, (92, 66, 44))
                snow = b in (5, 6)
                col = (52, 98, 74) if snow else (40, 104, 62)
                for q in range(3):
                    p_cone(PV, PC, lx, h + (1.2 + 1.8 * q) * sh, lz, (2.2 - 0.5 * q) * sw, 2.7 * sh, 6, col,
                           rng.uniform(0, 1))
                if snow:
                    p_cone(PV, PC, lx, h + 5.6 * sh, lz, 0.5 * sw, 1.2 * sh, 6, (240, 245, 250))
                obst.append((wx, wz, 0.3 * sw, 99.0, 0))
            elif kind == 'jungle':
                p_prism(PV, PC, lx, h - 0.1, lz, 0.32 * sw, 6.0 * sh, 5, (96, 74, 46))
                cr = (24 + rng.randint(0, 20), 120 + rng.randint(0, 50), 44 + rng.randint(0, 20))
                p_octa(PV, PC, lx, h + 6.4 * sh, lz, 2.8 * sw, 1.4 * sh, 2.8 * sw, cr)
                p_octa(PV, PC, lx + 0.8, h + 7.4 * sh, lz + 0.5, 1.6 * sw, 1.0 * sh, 1.6 * sw, cr)
                obst.append((wx, wz, 0.34 * sw, 99.0, 0))
            elif kind == 'acacia':
                p_prism(PV, PC, lx, h - 0.1, lz, 0.22 * sw, 3.6 * sh, 5, (120, 90, 56))
                p_octa(PV, PC, lx, h + 3.9 * sh, lz, 3.0 * sw, 0.55 * sh, 3.0 * sw, (110 + rng.randint(0, 30), 140, 60))
                obst.append((wx, wz, 0.25 * sw, 99.0, 0))
            elif kind == 'dead':
                p_prism(PV, PC, lx, h - 0.1, lz, 0.2 * sw, 3.0 * sh, 5, (84, 70, 58))
                p_prism(PV, PC, lx + 0.15, h + 2.0 * sh, lz, 0.1, 1.2 * sh, 4, (84, 70, 58))
                obst.append((wx, wz, 0.25 * sw, 99.0, 0))
            elif kind == 'bush':
                gr = rng.randint(90, 150)
                p_octa(PV, PC, lx, h + 0.4, lz, 0.9 * sw, 0.6 * sh, 0.9 * sw, (50 + rng.randint(0, 30), gr, 50))
            elif kind == 'cactus':
                p_prism(PV, PC, lx, h - 0.1, lz, 0.34 * sw, 3.2 * sh, 6, (74, 150, 84))
                p_prism(PV, PC, lx + 0.5 * sw, h + 1.4 * sh, lz, 0.2, 1.2 * sh, 5, (74, 150, 84))
                obst.append((wx, wz, 0.34 * sw, 99.0, 0))
            elif kind == 'rock':
                gc = rng.randint(100, 150)
                col = (gc + 70, gc + 40, gc - 10) if b in (4, 8) else (gc, gc, gc + 6)
                sy = 0.5 * s
                p_octa(PV, PC, lx, h + sy * 0.4, lz, 0.9 * s, sy, 0.8 * s, col)
                obst.append((wx, wz, 0.8 * s, h + sy * 1.3, 1))
            elif kind == 'flower':
                col = rng.choice([(235, 70, 70), (250, 220, 70), (245, 245, 245), (170, 90, 220), (250, 140, 60)])
                p_octa(PV, PC, lx, h + 0.22, lz, 0.1, 0.1, 0.1, col)
                p_tuft(PV, PC, lx, h - 0.02, lz, 0.25, (70, 140, 60))
            else:
                p_tuft(PV, PC, lx, h - 0.02, lz, rng.uniform(0.35, 0.6), (92 + rng.randint(0, 30), 160, 70))
        self._structs(rng, H, B, PV, PC, obst, cx, cz)
        yield
        if g.cdens > 0 and rng.random() < 0.2 * g.cdens:
            lx, lz = rng.uniform(9, CHUNK - 9), rng.uniform(9, CHUNK - 9)
            R = 5.5
            ring = [self._lh(H, lx + math.cos(TAU * q / 8) * R, lz + math.sin(TAU * q / 8) * R) for q in range(8)]
            i, j = int(round(lx / CELL)), int(round(lz / CELL))
            if max(ring) - min(ring) < 3.2 and min(ring) > sea + 2 and B[j * n + i] in (2, 3, 5, 6, 8):
                gap = rng.uniform(0, TAU)
                y0 = min(ring) - 1.0
                p_dome(PV, PC, lx, y0, lz, R, 7.5, gap, (128, 122, 116))
                p_dome(PV, PC, lx, y0, lz, R * 0.94, 7.0, gap, (46, 44, 48))
                caves.append((cx * CHUNK + lx, cz * CHUNK + lz, R, gap))
        yield
        return PV, PC, obst, caves

    # -------------------------------------------------------------- streaming
    def initial_job(self, center, radius):
        pcx, pcz = int(math.floor(center[0] / CHUNK)), int(math.floor(center[1] / CHUNK))
        keys = [(pcx + a, pcz + b) for a in range(-radius, radius + 1) for b in range(-radius, radius + 1)]
        keys.sort(key=lambda k: (k[0] - pcx) ** 2 + (k[1] - pcz) ** 2)
        total = float(len(keys))
        for idx, key in enumerate(keys):
            if key in self.ents:
                continue
            for _ in self.chunk_job(key):
                yield idx / total
        yield 1.0

    def _requeue(self, pcx, pcz):
        want = [(pcx + a, pcz + b) for a in range(-VIEW, VIEW + 1) for b in range(-VIEW, VIEW + 1)
                if a * a + b * b <= VIEW * VIEW + 1]
        want.sort(key=lambda k: (k[0] - pcx) ** 2 + (k[1] - pcz) ** 2)
        self.queue = [k for k in want if k not in self.ents]
        for k in list(self.ents):
            if (k[0] - pcx) ** 2 + (k[1] - pcz) ** 2 > (VIEW + 1.6) ** 2:
                for e in self.ents.pop(k):
                    destroy(e)
                self.obst.pop(k, None)
                self.caves.pop(k, None)
        for k in list(self.hcache):
            if (k[0] - pcx) ** 2 + (k[1] - pcz) ** 2 > (VIEW + 3) ** 2:
                self.hcache.pop(k, None)

    def update(self, px, pz, t, budget=0.006):
        pc = (int(math.floor(px / CHUNK)), int(math.floor(pz / CHUNK)))
        if pc != self.last_pc:
            self.last_pc = pc
            self._requeue(pc[0], pc[1])
        t0 = perf()
        while perf() - t0 < budget:
            if self.job is None:
                if not self.queue:
                    break
                key = self.queue.pop(0)
                if key in self.ents:
                    continue
                self.job = self.chunk_job(key)
            try:
                next(self.job)
            except StopIteration:
                self.job = None
        if self.water_ent is not None:
            self.water_ent.x = round(px / 4.0) * 4.0
            self.water_ent.z = round(pz / 4.0) * 4.0
            self.water_ent.y = self.sea + math.sin(t * 0.8) * 0.05
            try:
                self.water_ent.texture_offset = (t * 0.02, t * 0.013)
            except Exception:
                pass

    def destroy(self):
        for k in list(self.ents):
            for e in self.ents.pop(k):
                destroy(e)
        if self.water_ent is not None:
            destroy(self.water_ent)
            self.water_ent = None
# ==== WORLD END ==============================================================


# =============================================================================
#  THEME / UI HELPERS  (flat grey / black / white, like the reference images)
# =============================================================================
class T:
    GREY = C(85, 85, 85)
    GREY_D = C(74, 74, 74)
    GREY_L = C(112, 112, 112)
    BLACK = C(0, 0, 0)
    WHITE = C(255, 255, 255)
    DIM = C(190, 190, 190)
    GREEN = C(34, 177, 76)
    RED = C(237, 28, 36)
    BLUE = C(60, 140, 255)
    ORANGE = C(255, 176, 64)
    TEXT = C(255, 255, 255)


class G:
    ui_scale = 1.0
    game = None


_POLY = {}


def poly(w, h, cut=0.0, corners=(1, 1, 1, 1), cx=0.0, cy=0.0):
    key = (round(w, 5), round(h, 5), round(cut, 5), tuple(corners), round(cx, 5), round(cy, 5))
    data = _POLY.get(key)
    if data is None:
        hw, hh = w / 2.0, h / 2.0
        c = [max(0.0, min(cut * k, hw, hh)) for k in corners]
        pts = [(-hw + c[0], hh), (hw - c[1], hh), (hw, hh - c[1]), (hw, -hh + c[2]),
               (hw - c[2], -hh), (-hw + c[3], -hh), (-hw, -hh + c[3]), (-hw, hh - c[0])]
        data = ([Vec3(px + cx, py + cy, 0) for px, py in pts],
                [(0, 1, 2), (0, 2, 3), (0, 3, 4), (0, 4, 5), (0, 5, 6), (0, 6, 7)])
        _POLY[key] = data
    return Mesh(vertices=list(data[0]), triangles=list(data[1]), mode='triangle')


def rect(parent, x, y, w, h, col, z=0.0, ox=0.0, oy=0.0):
    return Entity(parent=parent, model=poly(w, h, 0, (0, 0, 0, 0), -ox * w, -oy * h), color=col,
                  position=(x, y, z), double_sided=True)


def tri(parent, pts, col, z=0):
    return Entity(parent=parent, model=Mesh(vertices=[Vec3(x, y, 0) for x, y in pts], triangles=[(0, 1, 2)],
                                            mode='triangle'), color=col, z=z, double_sided=True)


def hexa(parent, w, h, col, z=0.0):
    pts = [(0, h / 2), (w / 2, h / 4), (w / 2, -h / 4), (0, -h / 2), (-w / 2, -h / 4), (-w / 2, h / 4)]
    return Entity(parent=parent, model=Mesh(vertices=[Vec3(x, y, 0) for x, y in pts],
                                            triangles=[(0, 1, 2), (0, 2, 3), (0, 3, 4), (0, 4, 5)], mode='triangle'),
                  color=col, z=z, double_sided=True)


def frame(parent, w, h, title, header=0.085, footer=0.095, z=1.0):
    """Black window with a title bar, grey body and a black footer (see reference image)."""
    e = Entity(parent=parent, z=z)
    rect(e, 0, 0, w, h, T.BLACK, 0)
    rect(e, 0, (footer - header) / 2, w - 0.012, h - header - footer, T.GREY, -0.01)
    Text(text=title, parent=e, position=(-w / 2 + 0.028, h / 2 - header / 2, -0.2), origin=(-0.5, 0), scale=1.7,
         color=T.WHITE)
    return e


def corner_panel(parent, w, h, ox=0.0, oy=0.0, z=1.0, corners=(1, 1, 1, 1)):
    """Dark, rounded-polygon double-border panel."""
    e = Entity(parent=parent, z=z)
    cx, cy = -ox * w, -oy * h
    for ww, hh, col, cc, zz in ((w, h, T.BLACK, 0.034, 0), (w - 0.008, h - 0.008, C(104, 104, 114), 0.031, -0.01),
                                (w - 0.013, h - 0.013, T.BLACK, 0.029, -0.02), (w - 0.02, h - 0.02, C(38, 38, 44), 0.026, -0.03)):
        Entity(parent=e, model=poly(ww, hh, cc, corners, cx, cy), color=col, z=zz, double_sided=True)
    return e


def tuple_color(rgb):
    return C(rgb[0], rgb[1], rgb[2])


def outlined_text(parent, text, x, y, scale, col, outline):
    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, 1), (-1, 1), (1, -1)):
        Text(text=text, parent=parent, position=(x + dx * 0.004, y + dy * 0.004, -0.1), origin=(0, 0), scale=scale,
             color=outline)
    return Text(text=text, parent=parent, position=(x, y, -0.2), origin=(0, 0), scale=scale, color=col)


def fmt_time(sec):
    sec = int(max(0, sec))
    h, m, s = sec // 3600, (sec % 3600) // 60, sec % 60
    return '%dh %02dm' % (h, m) if h else '%dm %02ds' % (m, s)


MODS = ('shift', 'control', 'alt')
PRETTY = {'space': 'SPACE', 'control': 'CTRL', 'shift': 'SHIFT', 'alt': 'ALT', 'escape': 'ESC', 'enter': 'ENTER',
          'tab': 'TAB', 'backspace': 'BKSP', 'up arrow': 'UP', 'down arrow': 'DOWN', 'left arrow': 'LEFT',
          'right arrow': 'RIGHT'}


def pretty(k):
    return PRETTY.get(k, str(k).upper()) if k else 'NONE'


def norm_key(key):
    for m in MODS:
        if key in ('left ' + m, 'right ' + m):
            return m
    return key


def bindable(key):
    if not key or key.endswith(' up') or key.endswith(' hold'):
        return False
    return not ('mouse' in key or 'scroll' in key or 'gamepad' in key)


def held(k):
    if not k:
        return 0
    if k in MODS:
        return 1 if (held_keys[k] or held_keys['left ' + k] or held_keys['right ' + k]) else 0
    return 1 if held_keys[k] else 0


# =============================================================================
#  SETTINGS / SAVES / CUSTOM SEEDS
# =============================================================================
DEFAULT_BINDS = {'forward': 'w', 'back': 's', 'left': 'a', 'right': 'd', 'jump': 'space', 'sprint': 'shift',
                 'crouch': 'control', 'crouch_alt': 'c', 'zoom': 'q', 'respawn': 'r', 'mouse_lock': 'v',
                 'toggle_fps': 'f3', 'pause': 'escape', 'map': 'm', 'inventory': 'tab'}
BIND_LABELS = [('forward', 'Move Forward'), ('back', 'Move Back'), ('left', 'Move Left'), ('right', 'Move Right'),
               ('jump', 'Jump / Fly up'), ('sprint', 'Sprint'), ('crouch', 'Crouch / Fly down'),
               ('crouch_alt', 'Crouch (alt)'), ('zoom', 'Zoom'), ('respawn', 'Respawn'),
               ('mouse_lock', 'Free Mouse'), ('toggle_fps', 'Toggle FPS'), ('pause', 'Pause Menu'),
               ('map', 'Map'), ('inventory', 'Inventory')]
DEFAULTS = {
    'controls': {'toggle_sprint': False, 'toggle_crouch': False},
    'binds': dict(DEFAULT_BINDS),
    'graphics': {'ui_scale': 1.0, 'fov': 90, 'head_bob': True, 'jump_effects': True, 'effects': True,
                 'smooth_animations': True, 'screen_type': 'Windowed', 'low_poly': True, 'shader': 'None'},
    'audio': {'master': 0.8, 'player': 1.0, 'ambient': 1.0, 'creatures': 1.0, 'effects': 1.0},
    'general': {},
}


class Settings:
    def __init__(self):
        self.d = copy.deepcopy(DEFAULTS)
        self.dirty = False

    def load(self):
        try:
            if SETTINGS_FILE.exists():
                raw = json.loads(SETTINGS_FILE.read_text(encoding='utf-8'))
                for grp, defaults in DEFAULTS.items():
                    src = raw.get(grp)
                    if not isinstance(src, dict):
                        continue
                    for k, dv in defaults.items():
                        v = src.get(k)
                        if v is None:
                            continue
                        if isinstance(dv, bool):
                            ok = isinstance(v, bool)
                        elif isinstance(dv, (int, float)):
                            ok = isinstance(v, (int, float)) and not isinstance(v, bool)
                        else:
                            ok = isinstance(v, str)
                        if ok:
                            self.d[grp][k] = v
        except Exception:
            self.d = copy.deepcopy(DEFAULTS)
        g = self.d['graphics']
        g['ui_scale'] = max(0.7, min(1.25, float(g['ui_scale'])))
        g['fov'] = int(max(50, min(120, g['fov'])))
        if g['screen_type'] not in ('Windowed', 'Fullscreen'):
            g['screen_type'] = 'Windowed'
        for k in self.d['audio']:
            self.d['audio'][k] = max(0.0, min(1.0, float(self.d['audio'][k])))
        for k in DEFAULT_BINDS:
            if not bindable(self.d['binds'].get(k, '')):
                self.d['binds'][k] = DEFAULT_BINDS[k]

    def save(self):
        try:
            SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
            tmp = SETTINGS_FILE.with_suffix('.tmp')
            tmp.write_text(json.dumps(self.d, indent=2), encoding='utf-8')
            os.replace(str(tmp), str(SETTINGS_FILE))
            self.dirty = False
        except Exception as ex:
            print('[settings] save failed:', ex)

    def reset_group(self, grp):
        self.d[grp] = copy.deepcopy(DEFAULTS[grp])
        self.dirty = True


class WorldStore:
    """Worlds live in  Data/Save Game/<world_id>/world.json ; their saves in  <world_id>/saves/<slot>/save.json"""

    def _now(self):
        return datetime.now().strftime('%Y-%m-%d %H:%M')

    def worlds(self):
        out = []
        try:
            for d in SAVE_DIR.iterdir():
                f = d / 'world.json'
                if d.is_dir() and f.exists():
                    try:
                        j = json.loads(f.read_text(encoding='utf-8'))
                        j['id'] = d.name
                        out.append(j)
                    except Exception:
                        pass
        except Exception:
            pass
        out.sort(key=lambda j: j.get('last_played', ''), reverse=True)
        return out

    def new_id(self):
        i = 1
        while (SAVE_DIR / ('world_%03d' % i)).exists():
            i += 1
        return 'world_%03d' % i

    def read(self, wid):
        return json.loads((SAVE_DIR / wid / 'world.json').read_text(encoding='utf-8'))

    def write(self, wid, j):
        j = dict(j)
        j.pop('id', None)
        d = SAVE_DIR / wid
        (d / 'saves').mkdir(parents=True, exist_ok=True)
        tmp = d / 'world.tmp'
        tmp.write_text(json.dumps(j, indent=2), encoding='utf-8')
        os.replace(str(tmp), str(d / 'world.json'))

    def create(self, cfg):
        wid = self.new_id()
        self.write(wid, {'cfg': cfg, 'created': self._now(), 'last_played': self._now(), 'state': None,
                         'dead': False})
        return wid

    def update(self, wid, **kw):
        try:
            j = self.read(wid)
            j.update(kw)
            self.write(wid, j)
        except Exception as ex:
            print('[world] update failed:', ex)

    def set_state(self, wid, state):
        self.update(wid, state=state, last_played=self._now())

    def delete(self, wid):
        shutil.rmtree(str(SAVE_DIR / wid), ignore_errors=True)

    def saves(self, wid):
        out = []
        try:
            for d in (SAVE_DIR / wid / 'saves').iterdir():
                f = d / 'save.json'
                if d.is_dir() and f.exists():
                    try:
                        j = json.loads(f.read_text(encoding='utf-8'))
                    except Exception:
                        j = {'name': d.name + ' (damaged)', 'damaged': True}
                    j['slot'] = d.name
                    out.append(j)
        except Exception:
            pass
        out.sort(key=lambda j: j.get('modified', ''), reverse=True)
        return out

    def new_slot(self, wid):
        i = 1
        while (SAVE_DIR / wid / 'saves' / ('save_%03d' % i)).exists():
            i += 1
        return 'save_%03d' % i

    def save_read(self, wid, slot):
        return json.loads((SAVE_DIR / wid / 'saves' / slot / 'save.json').read_text(encoding='utf-8'))

    def save_write(self, wid, slot, name, state):
        d = SAVE_DIR / wid / 'saves' / slot
        d.mkdir(parents=True, exist_ok=True)
        created = self._now()
        try:
            created = self.save_read(wid, slot).get('created', created)
        except Exception:
            pass
        j = dict(state)
        j.update({'name': name, 'created': created, 'modified': self._now(), 'version': 3})
        tmp = d / 'save.tmp'
        tmp.write_text(json.dumps(j, indent=2), encoding='utf-8')
        os.replace(str(tmp), str(d / 'save.json'))

    def save_rename(self, wid, slot, name):
        j = self.save_read(wid, slot)
        j['name'] = name
        (SAVE_DIR / wid / 'saves' / slot / 'save.json').write_text(json.dumps(j, indent=2), encoding='utf-8')

    def save_delete(self, wid, slot):
        shutil.rmtree(str(SAVE_DIR / wid / 'saves' / slot), ignore_errors=True)

    # ---- stored seeds (favourites + every custom seed you actually played)
    def stored_seeds(self):
        try:
            return list(json.loads((SETTINGS_DIR / 'stored_seeds.json').read_text(encoding='utf-8')))
        except Exception:
            return []

    def store_seed(self, seed):
        lst = self.stored_seeds()
        if seed and seed not in lst:
            lst.insert(0, seed)
            try:
                (SETTINGS_DIR / 'stored_seeds.json').write_text(json.dumps(lst[:30]), encoding='utf-8')
            except Exception:
                pass
            return True
        return False


class CustomStore:
    """Every custom world recipe is stored as  USERCR.<11 digits>  (a json file)."""

    @staticmethod
    def save(custom, base):
        while True:
            cid = '%011d' % random.randrange(10 ** 11)
            f = CUSTOM_DIR / ('USERCR.%s.json' % cid)
            if not f.exists():
                break
        CUSTOM_DIR.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps({'base': base, 'custom': custom,
                                 'created': datetime.now().strftime('%Y-%m-%d %H:%M')}, indent=2), encoding='utf-8')
        return 'USERCR.' + cid

    @staticmethod
    def load(seed):
        try:
            s = seed.strip().upper()
            digits = s[7:]
            if not s.startswith('USERCR.') or len(digits) != 11 or not digits.isdigit():
                return None
            return json.loads((CUSTOM_DIR / ('USERCR.%s.json' % digits)).read_text(encoding='utf-8'))
        except Exception:
            return None


# ---------------------------------------------------------------- game data
ITEMS = {'meat': ('Raw Meat', (190, 70, 70), 2), 'cooked': ('Cooked Meat', (150, 90, 50), 8),
         'apple': ('Apple', (220, 50, 50), 3), 'bread': ('Bread', (210, 170, 100), 5),
         'bandage': ('Bandage', (235, 235, 235), 6), 'hide': ('Hide', (130, 95, 60), 0),
         'bone': ('Bone', (230, 230, 215), 0), 'torch': ('Torch', (255, 170, 50), 0)}
DIFFS = ['Peaceful', 'Easy', 'Normal', 'Hard', 'Hardcore']
DIFF_DMG = {'Peaceful': 0.0, 'Easy': 0.5, 'Normal': 1.0, 'Hard': 1.5, 'Hardcore': 2.0}
DIFF_DRAIN = {'Peaceful': 0.5, 'Easy': 0.7, 'Normal': 1.0, 'Hard': 1.3, 'Hardcore': 1.6}
DIFF_REGEN = {'Peaceful': 0.6, 'Easy': 0.35, 'Normal': 0.2, 'Hard': 0.1, 'Hardcore': 0.04}
LAND = ('Plains', 'Forest', 'Desert', 'Tundra', 'Mountains', 'Jungle', 'Savanna', 'Swamp')
MOBS = {
    'deer': dict(name='Deer', beh='peaceful', hp=10, walk=1.5, run=6.0, dmg=0, snd='snort', size=1.0,
                 biomes=('Plains', 'Forest', 'Savanna', 'Tundra'), drops=[('meat', 1, 2), ('hide', 0, 1)]),
    'rabbit': dict(name='Rabbit', beh='peaceful', hp=4, walk=1.2, run=7.0, dmg=0, snd='squeak', size=1.0,
                   biomes=('Plains', 'Forest', 'Tundra', 'Savanna'), drops=[('meat', 1, 1)]),
    'camel': dict(name='Camel', beh='peaceful', hp=18, walk=1.3, run=5.5, dmg=0, snd='snort', size=1.0,
                  biomes=('Desert', 'Savanna'), drops=[('meat', 1, 3), ('hide', 1, 1)]),
    'goat': dict(name='Goat', beh='neutral', hp=12, walk=1.6, run=6.5, dmg=3, snd='bleat', size=1.0,
                 biomes=('Mountains', 'Plains', 'Tundra'), drops=[('meat', 1, 2), ('hide', 0, 1)]),
    'boar': dict(name='Boar', beh='neutral', hp=14, walk=1.4, run=6.8, dmg=3, snd='grunt3', size=1.0,
                 biomes=('Forest', 'Jungle', 'Swamp', 'Savanna'), drops=[('meat', 1, 3)]),
    'bear': dict(name='Bear', beh='neutral', hp=30, walk=1.3, run=6.5, dmg=6, snd='growl', size=1.0,
                 biomes=('Forest', 'Tundra', 'Mountains', 'Jungle'), drops=[('meat', 2, 4), ('hide', 1, 2)]),
    'wolf': dict(name='Wolf', beh='aggressive', hp=12, walk=2.0, run=7.5, dmg=4, snd='growl', size=1.0,
                 biomes=('Tundra', 'Forest', 'Mountains', 'Plains'), drops=[('meat', 1, 2), ('bone', 0, 1)]),
    'human': dict(name='Wanderer', beh='aggressive', hp=20, walk=2.0, run=5.2, dmg=5, snd='grunt1', size=1.0,
                  biomes=LAND, drops=[('bread', 0, 2), ('bandage', 0, 1), ('bone', 0, 1)]),
}
MOB_ORDER = ['deer', 'rabbit', 'camel', 'goat', 'boar', 'bear', 'wolf', 'human']
SHADERS = ['None', 'Sun Rays', 'Golden Hour', 'Vivid', 'Retro']


def default_opts():
    return {'difficulty': 'Normal', 'mobs': {'enabled': True, 'types': {k: True for k in MOB_ORDER}},
            'day': {'cycle': True, 'len': 12.0, 'time': 9.0}}


def norm_cfg(cfg):
    c = dict(cfg)
    d = default_opts()
    c['difficulty'] = c.get('difficulty') if c.get('difficulty') in DIFFS else 'Normal'
    src = c.get('mobs')
    if isinstance(src, dict):
        d['mobs']['enabled'] = bool(src.get('enabled', True))
        for k, v in (src.get('types') or {}).items():
            if k in d['mobs']['types']:
                d['mobs']['types'][k] = bool(v)
    c['mobs'] = d['mobs']
    src = c.get('day')
    if isinstance(src, dict):
        d['day']['cycle'] = bool(src.get('cycle', True))
        d['day']['len'] = float(src.get('len', 12.0))
        d['day']['time'] = float(src.get('time', 9.0))
    c['day'] = d['day']
    c.setdefault('death', True)
    c.setdefault('life', True)
    c.setdefault('gamemode', 'Explorer')
    c.setdefault('cheats', False)
    c.setdefault('debug', False)
    return c


DEMO_CFG = norm_cfg({'name': 'demo', 'seed': '31415926535', 'mode': 'Normal', 'base': 31415926535, 'custom': None,
                     'demo': True, 'life': False, 'day': {'cycle': True, 'len': 20.0, 'time': 10.0}})


def copy_text(s):
    try:
        import pyperclip
        pyperclip.copy(s)
        return True
    except Exception:
        pass
    try:
        import tkinter as tk
        r = tk.Tk()
        r.withdraw()
        r.clipboard_clear()
        r.clipboard_append(s)
        r.update()
        r.destroy()
        return True
    except Exception:
        return False


# =============================================================================
#  SOUND  (all effects are synthesised into wav files on first start)
# =============================================================================
SOUNDS = {'step1': 'player', 'step2': 'player', 'step3': 'player', 'swim': 'player', 'splash': 'player',
          'thud': 'player', 'bird1': 'creatures', 'bird2': 'creatures', 'bird3': 'creatures', 'bird4': 'creatures',
          'grunt1': 'creatures', 'grunt2': 'creatures', 'grunt3': 'creatures', 'growl': 'creatures',
          'snort': 'creatures', 'squeak': 'creatures', 'bleat': 'creatures', 'cricket1': 'ambient',
          'cricket2': 'ambient', 'owl1': 'ambient', 'owl2': 'ambient', 'howl': 'ambient', 'water': 'ambient',
          'wind': 'ambient', 'hit': 'effects', 'punch': 'effects', 'hurt': 'effects', 'death': 'effects',
          'pickup': 'effects', 'eat': 'effects'}


class Sfx:
    RATE = 22050

    def __init__(self):
        self.snd = {}
        self.audio = {'master': 0.8, 'player': 1.0, 'ambient': 1.0, 'creatures': 1.0, 'effects': 1.0}
        try:
            SOUND_DIR.mkdir(parents=True, exist_ok=True)
            self._gen()
            for n in SOUNDS:
                try:
                    self.snd[n] = base.loader.loadSfx(Filename.fromOsSpecific(str(SOUND_DIR / (n + '.wav'))))
                except Exception as ex:
                    print('[sfx] could not load', n, ex)
            for n in ('water', 'wind'):
                s = self.snd.get(n)
                if s:
                    s.setLoop(True)
                    s.setVolume(0.0)
                    s.play()
        except Exception as ex:
            print('[sfx] disabled:', ex)

    def _vol(self, n, v):
        return max(0.0, min(1.0, v * self.audio['master'] * self.audio.get(SOUNDS.get(n, 'effects'), 1.0)))

    def _noise(self, dur, lp, decay, seed, thump=0.0, mod=0.0, modf=0.5):
        r = random.Random(seed)
        out, y = [], 0.0
        for i in range(int(dur * self.RATE)):
            t = i / float(self.RATE)
            y += (r.uniform(-1, 1) - y) * lp
            env = math.exp(-t * decay) * (1.0 + mod * math.sin(TAU * modf * t))
            out.append(y * env + thump * math.sin(TAU * 90 * t) * env)
        return out

    def _sweep(self, f0, f1, dur, vib=0.0, vibf=6.0, harm=0.3, saw=False, noise=0.0, seed=0):
        r = random.Random(seed)
        n = int(dur * self.RATE)
        out, ph = [], 0.0
        for i in range(n):
            u = i / float(n)
            ph += TAU * (f0 + (f1 - f0) * u + vib * math.sin(TAU * vibf * u * dur)) / self.RATE
            s = (((ph / TAU) % 1.0) * 2 - 1) if saw else (math.sin(ph) + harm * math.sin(2 * ph))
            out.append((s + noise * r.uniform(-1, 1)) * (math.sin(math.pi * u) ** 0.6))
        return out

    def _chirp(self, seed):
        r = random.Random(seed)
        out = []
        for _ in range(r.randint(2, 4)):
            f0 = r.uniform(2000, 3600)
            out += self._sweep(f0, f0 * r.uniform(0.75, 1.45), r.uniform(0.05, 0.1), 120, 38)
            out += [0.0] * int(0.045 * self.RATE)
        return out

    def _cricket(self, f, seed):
        out = []
        for _ in range(4):
            for _ in range(3):
                n = int(0.012 * self.RATE)
                out += [math.sin(TAU * f * i / self.RATE) * math.sin(math.pi * i / n) for i in range(n)]
                out += [0.0] * int(0.022 * self.RATE)
            out += [0.0] * int(0.09 * self.RATE)
        return out

    def _growl(self, seed):
        s = self._noise(0.7, 0.1, 1.5, seed)
        return [v * (0.6 + 0.4 * math.sin(TAU * 28 * i / self.RATE)) for i, v in enumerate(s)]

    def _write(self, name, samples):
        pk = max(0.001, max(abs(s) for s in samples))
        with wave.open(str(SOUND_DIR / (name + '.wav')), 'wb') as f:
            f.setnchannels(1)
            f.setsampwidth(2)
            f.setframerate(self.RATE)
            f.writeframes(b''.join(struct.pack('<h', int(max(-1.0, min(1.0, s / pk * 0.85)) * 32767))
                                   for s in samples))

    def _gen(self):
        sil = lambda d: [0.0] * int(d * self.RATE)
        T_ = {
            'step1': lambda: self._noise(0.13, 0.22, 26, 1, 0.5), 'step2': lambda: self._noise(0.13, 0.30, 24, 2, 0.4),
            'step3': lambda: self._noise(0.14, 0.18, 28, 3, 0.6), 'splash': lambda: self._noise(0.55, 0.28, 6, 4),
            'swim': lambda: self._noise(0.32, 0.16, 9, 5), 'thud': lambda: self._noise(0.2, 0.05, 20, 6, 1.0),
            'bird1': lambda: self._chirp(11), 'bird2': lambda: self._chirp(12), 'bird3': lambda: self._chirp(13),
            'bird4': lambda: self._chirp(14),
            'grunt1': lambda: self._sweep(150, 70, 0.4, 0, 0, 0, True, 0.3, 1),
            'grunt2': lambda: self._sweep(120, 60, 0.5, 6, 9, 0, True, 0.25, 2),
            'grunt3': lambda: self._sweep(180, 90, 0.3, 0, 0, 0, True, 0.4, 3),
            'growl': lambda: self._growl(9), 'snort': lambda: self._noise(0.25, 0.2, 8, 10, 0.2),
            'squeak': lambda: self._sweep(1800, 2600, 0.12, 0, 0, 0.2), 'bleat': lambda: self._sweep(380, 340, 0.5, 40, 12),
            'cricket1': lambda: self._cricket(3800, 1), 'cricket2': lambda: self._cricket(4400, 2),
            'owl1': lambda: self._sweep(420, 360, 0.4, 0, 0, 0.2) + sil(0.12) + self._sweep(380, 300, 0.6, 0, 0, 0.2),
            'owl2': lambda: self._sweep(330, 300, 0.5, 0, 0, 0.2) + sil(0.15) + self._sweep(330, 260, 0.7, 0, 0, 0.2),
            'howl': lambda: self._sweep(380, 760, 0.9, 12, 5) + self._sweep(760, 520, 1.0, 12, 5),
            'water': lambda: self._noise(2.0, 0.07, 0.0, 7, 0.0, 0.25, 0.5),
            'wind': lambda: self._noise(3.0, 0.02, 0.0, 31, 0.0, 0.35, 1.0 / 3.0),
            'hit': lambda: self._noise(0.12, 0.4, 35, 21, 0.6), 'punch': lambda: self._noise(0.1, 0.3, 40, 22, 1.0),
            'hurt': lambda: self._sweep(260, 150, 0.25), 'death': lambda: self._sweep(300, 60, 0.9, 0, 0, 0.3, True, 0.1),
            'pickup': lambda: self._sweep(600, 900, 0.08) + self._sweep(900, 1300, 0.1),
            'eat': lambda: self._noise(0.1, 0.3, 30, 41) + sil(0.08) + self._noise(0.1, 0.3, 30, 42) + sil(0.08)
            + self._noise(0.1, 0.3, 30, 43),
        }
        for name, fn in T_.items():
            if not (SOUND_DIR / (name + '.wav')).exists():
                self._write(name, fn())

    def play(self, n, vol=1.0, rate=1.0):
        s = self.snd.get(n)
        if s:
            try:
                s.setVolume(self._vol(n, vol))
                s.setPlayRate(rate)
                s.play()
            except Exception:
                pass

    def loop_vol(self, n, v):
        s = self.snd.get(n)
        if s:
            try:
                s.setVolume(self._vol(n, v))
            except Exception:
                pass

    def water_vol(self, v):
        self.loop_vol('water', v)


# =============================================================================
#  LIFE FORMS  (birds + mobs)
# =============================================================================
def mob_mesh(kind):
    V, Cc = [], []
    if kind == 'deer':
        b, d = (150, 105, 60), (110, 76, 44)
        p_box(V, Cc, 0, 0.85, 0, 0.25, 0.25, 0.55, b)
        p_box(V, Cc, 0, 1.3, 0.6, 0.12, 0.3, 0.12, b)
        p_box(V, Cc, 0, 1.6, 0.75, 0.13, 0.12, 0.2, d)
        for lx in (-0.16, 0.16):
            for lz in (-0.4, 0.4):
                p_box(V, Cc, lx, 0.3, lz, 0.05, 0.3, 0.05, d)
    elif kind == 'rabbit':
        b = (176, 156, 134)
        p_box(V, Cc, 0, 0.2, 0, 0.12, 0.1, 0.2, b)
        p_box(V, Cc, 0, 0.3, 0.22, 0.08, 0.08, 0.08, b)
        p_box(V, Cc, -0.04, 0.46, 0.2, 0.025, 0.1, 0.02, b)
        p_box(V, Cc, 0.04, 0.46, 0.2, 0.025, 0.1, 0.02, b)
    elif kind == 'camel':
        b = (200, 165, 100)
        p_box(V, Cc, 0, 1.4, 0, 0.35, 0.4, 0.8, b)
        p_box(V, Cc, 0, 2.0, 0, 0.2, 0.2, 0.25, (180, 145, 85))
        p_box(V, Cc, 0, 1.9, 0.85, 0.1, 0.5, 0.1, b)
        p_box(V, Cc, 0, 2.45, 1.0, 0.12, 0.12, 0.22, b)
        for lx in (-0.22, 0.22):
            for lz in (-0.55, 0.55):
                p_box(V, Cc, lx, 0.5, lz, 0.07, 0.5, 0.07, (170, 135, 80))
    elif kind == 'goat':
        b = (222, 220, 214)
        p_box(V, Cc, 0, 0.7, 0, 0.2, 0.22, 0.4, b)
        p_box(V, Cc, 0, 0.95, 0.45, 0.1, 0.12, 0.14, b)
        p_box(V, Cc, -0.07, 1.12, 0.45, 0.02, 0.1, 0.02, (90, 80, 70))
        p_box(V, Cc, 0.07, 1.12, 0.45, 0.02, 0.1, 0.02, (90, 80, 70))
        for lx in (-0.12, 0.12):
            for lz in (-0.3, 0.3):
                p_box(V, Cc, lx, 0.25, lz, 0.04, 0.25, 0.04, (150, 148, 142))
    elif kind == 'boar':
        b = (92, 66, 52)
        p_box(V, Cc, 0, 0.55, 0, 0.3, 0.28, 0.5, b)
        p_box(V, Cc, 0, 0.55, 0.62, 0.2, 0.2, 0.2, (80, 58, 46))
        p_box(V, Cc, -0.12, 0.45, 0.82, 0.02, 0.02, 0.06, (235, 232, 220))
        p_box(V, Cc, 0.12, 0.45, 0.82, 0.02, 0.02, 0.06, (235, 232, 220))
        for lx in (-0.18, 0.18):
            for lz in (-0.35, 0.35):
                p_box(V, Cc, lx, 0.15, lz, 0.05, 0.15, 0.05, (60, 44, 36))
    elif kind == 'bear':
        b = (82, 56, 40)
        p_box(V, Cc, 0, 1.0, 0, 0.5, 0.45, 0.75, b)
        p_box(V, Cc, 0, 1.25, 0.9, 0.28, 0.26, 0.28, b)
        p_box(V, Cc, -0.2, 1.55, 0.85, 0.07, 0.07, 0.05, b)
        p_box(V, Cc, 0.2, 1.55, 0.85, 0.07, 0.07, 0.05, b)
        for lx in (-0.3, 0.3):
            for lz in (-0.5, 0.5):
                p_box(V, Cc, lx, 0.3, lz, 0.14, 0.3, 0.14, (62, 42, 30))
    elif kind == 'wolf':
        b = (122, 122, 128)
        p_box(V, Cc, 0, 0.75, 0, 0.2, 0.2, 0.5, b)
        p_box(V, Cc, 0, 0.95, 0.6, 0.14, 0.14, 0.17, b)
        p_box(V, Cc, 0, 0.88, 0.8, 0.07, 0.06, 0.1, (90, 90, 96))
        p_box(V, Cc, 0, 0.9, -0.62, 0.05, 0.05, 0.25, (100, 100, 106))
        for lx in (-0.12, 0.12):
            for lz in (-0.35, 0.35):
                p_box(V, Cc, lx, 0.3, lz, 0.05, 0.3, 0.05, (96, 96, 102))
    else:  # human
        shirt = random.choice([(150, 40, 40), (40, 90, 50), (60, 60, 90), (90, 70, 40)])
        p_box(V, Cc, -0.15, 0.45, 0, 0.14, 0.45, 0.14, (50, 50, 60))
        p_box(V, Cc, 0.15, 0.45, 0, 0.14, 0.45, 0.14, (50, 50, 60))
        p_box(V, Cc, 0, 1.3, 0, 0.3, 0.4, 0.17, shirt)
        p_box(V, Cc, 0, 1.92, 0, 0.19, 0.19, 0.19, (222, 182, 142))
        p_box(V, Cc, 0, 2.1, -0.02, 0.2, 0.06, 0.2, (60, 44, 30))
        p_box(V, Cc, -0.1, 1.95, 0.2, 0.03, 0.03, 0.02, (240, 40, 40))
        p_box(V, Cc, 0.1, 1.95, 0.2, 0.03, 0.03, 0.02, (240, 40, 40))
        p_box(V, Cc, -0.42, 1.3, 0.25, 0.1, 0.4, 0.1, shirt)
        p_box(V, Cc, 0.42, 1.3, 0.25, 0.1, 0.4, 0.1, shirt)
    return to_mesh(V, Cc)


class Life:
    """Birds circling overhead."""

    def __init__(self, game):
        self.g = game
        self.birds = []
        self.t = 0.0
        self.cx = self.cz = 0.0

    def clear(self):
        for b in self.birds:
            destroy(b['e'])
        self.birds = []

    def _bird_mesh(self):
        V = [(0, 0, 0.3), (-0.9, 0.2, -0.1), (0, 0, -0.3), (0, 0, 0.3), (0.9, 0.2, -0.1), (0, 0, -0.3),
             (0, 0, 0.4), (0, 0.1, -0.1), (0, -0.05, -0.35)]
        return to_mesh(V, [(0.2, 0.18, 0.18)] * 6 + [(0.9, 0.9, 0.9)] * 3)

    def setup(self, cfg, pp):
        self.clear()
        if not cfg.get('life') or cfg.get('mode') == 'Flat +':
            return
        self.cx, self.cz = pp.x, pp.z
        for i in range(5):
            e = Entity(model=self._bird_mesh(), double_sided=True, scale=1.3)
            self.birds.append({'e': e, 'a': random.uniform(0, TAU), 'sp': random.uniform(0.25, 0.45),
                               'rad': random.uniform(14, 34), 'hy': random.uniform(14, 26), 'ph': random.uniform(0, 6)})

    def update(self, dt, pp):
        if not self.birds:
            return
        w = self.g.world
        self.t += dt
        self.cx += (pp.x - self.cx) * min(1.0, dt * 0.5)
        self.cz += (pp.z - self.cz) * min(1.0, dt * 0.5)
        for b in self.birds:
            b['a'] += b['sp'] * dt
            x, z = self.cx + math.cos(b['a']) * b['rad'], self.cz + math.sin(b['a']) * b['rad']
            e = b['e']
            e.position = Vec3(x, max(w.surface(x, z), w.sea) + b['hy'] + math.sin(self.t + b['ph']) * 1.2, z)
            e.rotation_y = math.degrees(math.atan2(-math.sin(b['a']), math.cos(b['a'])))
            e.scale_y = 1.3 * math.sin(self.t * 9 + b['ph'])


class Mobs:
    """Peaceful / neutral (peaceful-if-not-bothered) / aggressive creatures."""

    def __init__(self, game):
        self.g = game
        self.list = []
        self.spawn_t = 0.0
        self.snd_t = 0.0

    def clear(self):
        for m in self.list:
            destroy(m['e'])
        self.list = []

    def enabled_kinds(self):
        c = self.g.cfg
        if not c.get('life') or c.get('mode') == 'Flat +' or not c['mobs']['enabled']:
            return []
        return [k for k in MOB_ORDER if c['mobs']['types'].get(k, True)]

    def beh(self, kind):
        b = MOBS[kind]['beh']
        if b == 'peaceful' and self.g.cfg['difficulty'] in ('Hard', 'Hardcore'):
            return 'neutral'
        return b

    def spawn(self, kind, x, z):
        w = self.g.world
        e = Entity(model=mob_mesh(kind), double_sided=True, position=Vec3(x, w.ground(x, z), z))
        m = {'e': e, 'kind': kind, 'hp': MOBS[kind]['hp'], 'hd': random.uniform(0, TAU), 'sp': 0.0, 'tm': 0.0,
             'prov': 0.0, 'flee': 0.0, 'cd': 0.0, 'st': random.uniform(2, 6)}
        self.list.append(m)
        return m

    def remove(self, m):
        destroy(m['e'])
        if m in self.list:
            self.list.remove(m)

    def remove_kind(self, kind=None):
        n = 0
        for m in self.list[:]:
            if kind is None or m['kind'] == kind:
                self.remove(m)
                n += 1
        return n

    def nearest_in_front(self, p, maxd=3.6):
        best, bd = None, 999
        fx, fz = p.forward[0], p.forward[2]
        for m in self.list:
            dx, dz = m['e'].x - p.x, m['e'].z - p.z
            d = math.hypot(dx, dz)
            if d < maxd and d > 0.01 and (dx * fx + dz * fz) / d > 0.8 and d < bd:
                best, bd = m, d
        return best

    def hit(self, m, dmg, p):
        m['hp'] -= dmg
        m['prov'] = 25.0
        m['flee'] = 5.0 if self.beh(m['kind']) == 'peaceful' else 0.0
        dx, dz = m['e'].x - p.x, m['e'].z - p.z
        d = math.hypot(dx, dz) or 1.0
        m['e'].x += dx / d * 0.9
        m['e'].z += dz / d * 0.9
        self.g.sfx.play('hit', 0.8, random.uniform(0.9, 1.2))
        if m['hp'] <= 0:
            for item, lo, hi in MOBS[m['kind']]['drops']:
                n = random.randint(lo, hi)
                if n > 0:
                    self.g.inv_add(item, n)
            self.g.hud.toast('%s defeated' % MOBS[m['kind']]['name'], 1.0)
            self.remove(m)

    def update(self, dt, p):
        g, w = self.g, self.g.world
        kinds = self.enabled_kinds()
        if not kinds:
            if self.list:
                self.clear()
            return
        night = g.day_f < 0.3
        self.spawn_t -= dt
        if self.spawn_t <= 0:
            self.spawn_t = 1.5
            if len(self.list) < 12:
                k = random.choice(kinds)
                if MOBS[k]['beh'] != 'aggressive' or random.random() < (1.0 if night else 0.3):
                    a, r = random.uniform(0, TAU), random.uniform(28, 55)
                    x, z = p.x + math.cos(a) * r, p.z + math.sin(a) * r
                    if w.ground(x, z) > w.sea + 0.8 and w.biome_at(x, z) in MOBS[k]['biomes']:
                        self.spawn(k, x, z)
        self.snd_t -= dt
        for m in self.list[:]:
            e, spec, kind = m['e'], MOBS[m['kind']], m['kind']
            if m['kind'] not in kinds:
                self.remove(m)
                continue
            dx, dz = p.x - e.x, p.z - e.z
            d = math.hypot(dx, dz) or 0.01
            if d > 110 and m['prov'] <= 0:
                self.remove(m)
                continue
            beh = self.beh(kind)
            diff = g.cfg['difficulty']
            m['prov'] = max(0.0, m['prov'] - dt)
            m['flee'] = max(0.0, m['flee'] - dt)
            m['cd'] = max(0.0, m['cd'] - dt)
            speed, target = 0.0, None
            if m['flee'] > 0:
                target, speed = m['hd'], spec['run']
                m['hd'] = math.atan2(-dx, -dz)
            elif beh == 'aggressive' and diff != 'Peaceful' and d < (30 if night else 20):
                m['hd'], speed = math.atan2(dx, dz), spec['run']
            elif beh == 'neutral' and m['prov'] > 0 and d < 40 and diff != 'Peaceful':
                m['hd'], speed = math.atan2(dx, dz), spec['run']
            else:
                m['tm'] -= dt
                if m['tm'] <= 0:
                    m['tm'] = random.uniform(2, 6)
                    m['sp'] = random.choice([0.0, 0.0, spec['walk']])
                    m['hd'] += random.uniform(-1.5, 1.5)
                speed = m['sp']
            chasing = speed == spec['run'] and m['flee'] <= 0
            if chasing and d < 1.9 and m['cd'] <= 0 and spec['dmg'] > 0:
                m['cd'] = 1.2
                g.hurt_player(spec['dmg'], 'a ' + spec['name'])
            if chasing and d < 1.6:
                speed = 0.0
            nx, nz = e.x + math.sin(m['hd']) * speed * dt, e.z + math.cos(m['hd']) * speed * dt
            if w.ground(nx, nz) < w.sea + 0.4:
                m['hd'] += 2.4
            else:
                nx, nz = w.push(nx, nz, e.y)
                e.x, e.z = nx, nz
            e.y = w.ground(e.x, e.z) + (math.sin(g.t * 9 + id(m) % 7) * 0.04 if speed else 0)
            e.rotation_y = math.degrees(m['hd'])
            m['st'] -= dt
            if m['st'] <= 0 and d < 26:
                m['st'] = random.uniform(4, 9) if not chasing else random.uniform(2, 4)
                snd = spec['snd']
                if kind == 'human':
                    snd = 'grunt%d' % random.randint(1, 3)
                g.sfx.play(snd, max(0.1, 1.0 - d / 28.0) * 0.8, random.uniform(0.85, 1.15))


# =============================================================================
#  WIDGETS
# =============================================================================
class PWidget(Entity):
    def __init__(self, parent, x, y, w, h):
        super().__init__(parent=parent, position=(x, y, -0.1))
        self.w, self.h = w, h
        self.is_hot = False
        self.locked = False

    def contains(self, mx, my):
        s = G.ui_scale
        return abs(mx - self.x * s) <= self.w * 0.5 * s and abs(my - self.y * s) <= self.h * 0.5 * s

    def hover_at(self, mx, my):
        v = self.contains(mx, my)
        if v != self.is_hot:
            self.is_hot = v
            self.on_hot()

    def on_hot(self):
        pass

    def click(self, mx, my):
        return True

    def release(self):
        pass

    def refresh(self):
        pass


class PButton(PWidget):
    def __init__(self, parent, x, y, w, h, text, callback=None, accent=False, scale=1.0, danger=False, tab=False,
                 dark=False):
        super().__init__(parent, x, y, w, h)
        self.callback, self.accent, self.danger, self.tab, self.dark = callback, accent, danger, tab, dark
        if tab:
            self.border_e = Entity(parent=self, model=poly(w, h, 0.014, (1, 1, 0, 0)), color=T.WHITE,
                                   double_sided=True)
            self.fill_e = Entity(parent=self, model=poly(w - 0.008, h - 0.008, 0.011, (1, 1, 0, 0)), color=T.BLACK,
                                 double_sided=True, z=-0.01)
        else:
            self.border_e = rect(self, 0, 0, w, h, T.BLACK)
            self.fill_e = rect(self, 0, 0, w - 0.012, h - 0.012, T.GREY, -0.01)
            rect(self, 0, h / 2 - 0.0095, w - 0.02, 0.0025, C(255, 255, 255, 40), -0.02)
        self.label = Text(text=text, parent=self, position=(0, 0, -0.05), origin=(0, 0), scale=scale * 1.05,
                          color=T.WHITE)
        self.on_hot()

    def set_text(self, t):
        self.label.text = t

    def on_hot(self):
        hot = self.is_hot and not self.locked
        if self.tab:
            self.fill_e.color = C(48, 48, 48) if hot else T.BLACK
            self.border_e.color = T.WHITE if not self.locked else T.GREY_L
        elif self.danger:
            self.fill_e.color = C(150, 55, 55) if hot else C(112, 52, 52)
        elif self.accent:
            self.fill_e.color = C(60, 140, 82) if hot else C(52, 112, 70)
        else:
            self.fill_e.color = (C(98, 98, 108) if hot else C(58, 58, 64)) if self.dark else (T.GREY_L if hot else T.GREY)
        if self.locked:
            self.fill_e.color = C(62, 62, 62) if not self.tab else T.BLACK
        self.label.color = T.DIM if self.locked else T.WHITE

    def click(self, mx, my):
        if not self.locked and self.callback:
            self.callback()
        return True


def _row_label(w, label, desc, parent):
    Text(text=label, parent=parent, position=(-w / 2 + 0.012, 0.009 if desc else 0, -0.05), origin=(-0.5, 0),
         scale=0.98, color=T.WHITE)
    if desc:
        Text(text=desc, parent=parent, position=(-w / 2 + 0.012, -0.015, -0.05), origin=(-0.5, 0), scale=0.6,
             color=T.DIM)


class PToggle(PWidget):
    """Green / red switch with the grey double-bar knob (reference image)."""

    def __init__(self, parent, x, y, w, label, desc, getter, setter):
        super().__init__(parent, x, y, w, 0.054)
        self.getter, self.setter = getter, setter
        _row_label(w, label, desc, self)
        sx = w / 2 - 0.07
        self.sw = Entity(parent=self, position=(sx, 0, -0.04))
        rect(self.sw, 0, 0, 0.116, 0.044, T.BLACK)
        self.green = rect(self.sw, -0.055, 0, 0.06, 0.036, T.GREEN, -0.01, ox=-0.5)
        self.red = rect(self.sw, 0.055, 0, 0.01, 0.036, T.RED, -0.01, ox=0.5)
        self.knob = Entity(parent=self.sw, z=-0.03)
        for dx in (-0.007, 0.007):
            rect(self.knob, dx, 0, 0.007, 0.028, T.GREY_L)
        self.refresh()

    def on_hot(self):
        pass

    def refresh(self):
        on = bool(self.getter())
        gw, rw = (0.06, 0.006) if on else (0.006, 0.06)
        self.green.scale_x = gw / 0.06
        self.red.scale_x = rw / 0.01
        self.knob.x = -0.055 + gw + 0.016      # the grey bars always sit on the switch, right after the green part

    def click(self, mx, my):
        self.setter(not self.getter())
        self.refresh()
        return True


class PSlider(PWidget):
    def __init__(self, parent, x, y, w, label, desc, vmin, vmax, getter, setter, fmt, step=None):
        super().__init__(parent, x, y, w, 0.054)
        self.vmin, self.vmax, self.getter, self.setter, self.fmt, self.step = vmin, vmax, getter, setter, fmt, step
        self.track_w = min(0.27, w * 0.4)
        self.track_x = w / 2 - 0.075 - self.track_w / 2
        self.dragging = False
        _row_label(w, label, desc, self)
        rect(self, self.track_x, 0, self.track_w, 0.006, T.BLACK, -0.04)
        self.fill = rect(self, self.track_x - self.track_w / 2, 0, self.track_w, 0.003, T.WHITE, -0.05, ox=-0.5)
        self.handle = Entity(parent=self, position=(self.track_x, 0, -0.07))
        hexa(self.handle, 0.03, 0.044, T.BLACK)
        hexa(self.handle, 0.022, 0.034, T.GREY, -0.01)
        self.val_txt = Text(text='', parent=self, position=(w / 2 - 0.035, 0, -0.05), origin=(0, 0), scale=0.85,
                            color=T.WHITE)
        self.refresh()

    def refresh(self):
        v = max(self.vmin, min(self.vmax, self.getter()))
        f = (v - self.vmin) / float(self.vmax - self.vmin)
        self.fill.scale_x = max(f, 0.001)
        self.handle.x = self.track_x - self.track_w / 2 + self.track_w * f
        self.val_txt.text = self.fmt(v)

    def drag_to(self, mx):
        s = G.ui_scale
        left = (self.x + self.track_x - self.track_w / 2) * s
        f = max(0.0, min(1.0, (mx - left) / (self.track_w * s)))
        v = self.vmin + f * (self.vmax - self.vmin)
        if self.step:
            v = round(v / self.step) * self.step
        v = max(self.vmin, min(self.vmax, v))
        if abs(v - self.getter()) > 1e-9:
            self.setter(v)
        self.refresh()

    def click(self, mx, my):
        self.dragging = True
        self.drag_to(mx)
        return True

    def release(self):
        self.dragging = False


class PDropdown(PWidget):
    OPT_H = 0.042

    def __init__(self, parent, x, y, w, label, desc, options, getter, setter, fw=0.2):
        super().__init__(parent, x, y, w, 0.054)
        self.options, self.getter, self.setter = options, getter, setter
        self.is_open = False
        self.opt_hot = -1
        self.fw = fw
        self.bx = w / 2 - fw / 2
        _row_label(w, label, desc, self)
        self.line = rect(self, self.bx, -0.014, fw, 0.003, T.WHITE, -0.04)
        self.cur = Text(text='', parent=self, position=(self.bx - fw / 2 + 0.006, 0.006, -0.05), origin=(-0.5, 0),
                        scale=0.95, color=T.WHITE)
        ax = self.bx + fw / 2 - 0.015
        rect(self, ax, -0.002, 0.03, 0.03, T.WHITE, -0.04)
        rect(self, ax, -0.002, 0.024, 0.024, T.BLACK, -0.05)
        tri(self, [(ax - 0.008, 0.003), (ax + 0.008, 0.003), (ax, -0.009)], T.WHITE, z=-0.06)
        self.opt_ents = []
        for i, o in enumerate(options):
            e = Entity(parent=self, position=(self.bx, -(i + 1) * self.OPT_H - 0.006, -0.6))
            rect(e, 0, 0, fw, self.OPT_H - 0.004, T.WHITE)
            e.bg = rect(e, 0, 0, fw - 0.006, self.OPT_H - 0.01, T.BLACK, -0.01)
            Text(text=o, parent=e, position=(0, 0, -0.05), origin=(0, 0), scale=0.9, color=T.WHITE)
            e.enabled = False
            self.opt_ents.append(e)
        self.refresh()

    def _in(self, mx, my, cx, cy, w, h):
        s = G.ui_scale
        return abs(mx - cx * s) <= w * 0.5 * s and abs(my - cy * s) <= h * 0.5 * s

    def _opt_index(self, mx, my):
        if not self.is_open:
            return -1
        for i in range(len(self.options)):
            if self._in(mx, my, self.x + self.bx, self.y - (i + 1) * self.OPT_H - 0.006, self.fw, self.OPT_H):
                return i
        return -1

    def contains(self, mx, my):
        return PWidget.contains(self, mx, my) or self._opt_index(mx, my) >= 0

    def hover_at(self, mx, my):
        PWidget.hover_at(self, mx, my)
        if self.is_open:
            idx = self._opt_index(mx, my)
            if idx != self.opt_hot:
                self.opt_hot = idx
                for i, e in enumerate(self.opt_ents):
                    e.bg.color = C(60, 60, 60) if i == idx else T.BLACK

    def refresh(self):
        self.cur.text = str(self.getter())

    def close(self):
        self.is_open = False
        self.z = -0.1
        for e in self.opt_ents:
            e.enabled = False

    def click(self, mx, my):
        if self.is_open:
            idx = self._opt_index(mx, my)
            if idx >= 0:
                self.setter(self.options[idx])
            self.close()
            self.refresh()
            return True
        self.is_open = True
        self.z = -0.4
        for e in self.opt_ents:
            e.enabled = True
        return True


class PTextField(PWidget):
    def __init__(self, parent, x, y, w, label, getter, setter, max_len=22, allowed=None, upper=False, hint='',
                 fw=0.2):
        super().__init__(parent, x, y, w, 0.054)
        self.getter, self.setter, self.max_len, self.allowed, self.upper, self.hint = \
            getter, setter, max_len, allowed, upper, hint
        self.focused, self.caret = False, True
        _row_label(w, label, None, self)
        fx = w / 2 - fw / 2
        self.line = rect(self, fx, -0.014, fw, 0.003, T.WHITE, -0.04)
        self.txt = Text(text='', parent=self, position=(fx - fw / 2 + 0.006, 0.006, -0.05), origin=(-0.5, 0),
                        scale=0.95, color=T.WHITE)
        self.refresh()

    def refresh(self):
        v = self.getter()
        if not v and not self.focused:
            self.txt.text = self.hint
            self.txt.color = T.DIM
        else:
            self.txt.text = v + ('_' if (self.focused and self.caret) else '')
            self.txt.color = T.WHITE

    def click(self, mx, my):
        G.game.ui.set_focus(self)
        return True

    def key(self, k):
        v = self.getter()
        if k in ('enter', 'return', 'tab', 'escape'):
            G.game.ui.set_focus(None)
        elif k == 'backspace':
            self.setter(v[:-1])
        elif k == 'space':
            ch = ' '
        elif len(k) == 1:
            ch = k
        else:
            return True
        if k == 'space' or len(k) == 1:
            if self.upper or held('shift'):
                ch = ch.upper() if self.upper or ch.isalpha() else ch
            if (self.allowed is None or self.allowed(ch)) and len(v) < self.max_len:
                self.setter(v + ch)
        self.refresh()
        return True


# =============================================================================
#  PAGES / UI
# =============================================================================
class Page(Entity):
    def __init__(self, ui, name):
        super().__init__(parent=ui.root, enabled=False)
        self.ui, self.g, self.name = ui, ui.game, name
        self.widgets = []

    def add(self, w):
        self.widgets.append(w)
        return w

    def txt(self, text, x, y, scale=1.0, col=None, origin=(0, 0), z=-0.2):
        return Text(text=text, parent=self, position=(x, y, z), origin=origin, scale=scale,
                    color=T.WHITE if col is None else col)

    def on_show(self):
        pass

    def layout(self):
        pass


class CornerPage(Page):
    """Main / pause / death menu: dark double-border polygon panel, floating a little off the left edge."""
    PW = 0.42

    def __init__(self, ui, name):
        super().__init__(ui, name)
        self.off = 0.0
        self.btns = []
        self.panel = None
        self.title_txt = None

    def build(self, items, title=None):
        self.ph = 0.12 + len(items) * 0.105 + (0.07 if title else 0)
        self.panel = corner_panel(self, self.PW, self.ph, z=1)
        if title:
            self.title_txt = Text(text=title, parent=self.panel, position=(0, self.ph / 2 - 0.06, -0.2),
                                  origin=(0, 0), scale=1.5, color=T.WHITE)
        top = self.ph / 2 - 0.06 - (0.07 if title else 0) - 0.045
        for i, (t, cb, acc) in enumerate(items):
            self.btns.append(self.add(PButton(self, 0, top - i * 0.105, self.PW - 0.09, 0.085, t, cb, accent=acc,
                                              dark=True, scale=1.1)))
        self.layout()

    def layout(self):
        if self.panel is None:
            return
        ax = -(window.aspect_ratio / 2.0) / G.ui_scale + self.PW / 2 + 0.07 + self.off
        self.panel.x = ax
        for b in self.btns:
            b.x = ax


class UI:
    def __init__(self, game):
        self.game = game
        self.root = Entity(parent=camera.ui)
        self.root.scale = Vec3(G.ui_scale, G.ui_scale, 1)
        self.dim = Entity(parent=self.root, model='quad', scale=(5, 3), color=C(0, 0, 0, 130), z=3, enabled=False)
        self.pages, self.current, self.stack = {}, None, []
        self.dialog, self.capture, self.focus = None, None, None
        self.active_slider = None
        self.after_save = None
        self.blink = 0.0

    def build_steps(self):
        g = self.game
        main = CornerPage(self, 'main')
        main.build([('New Game', lambda: self.open('newworld'), True), ('Continue', lambda: self.open('continue'), False),
                    ('Settings', lambda: self.open('settings'), False), ('Quit', lambda: g.ask_quit('menu_quit'), False)])
        outlined_text(main, 'LOW POLY', 0.27, 0.2, 4.2, T.WHITE, C(255, 150, 40))
        outlined_text(main, 'EXPLORER', 0.27, 0.09, 4.2, C(210, 210, 215), C(255, 150, 40))
        Text(text='v3.0', parent=main, position=(0.0, -0.46, -0.2), origin=(0, 0), scale=0.7, color=T.DIM)
        self.pages['main'] = main
        yield
        pause = CornerPage(self, 'pause')
        pause.build([('Resume', lambda: g.resume_game(), True), ('Save', lambda: self.open_saves('save'), False),
                     ('Load', lambda: self.open_saves('load'), False), ('Settings', lambda: self.open('settings'), False),
                     ('Quit to menu', lambda: g.ask_quit('menu'), False), ('Quit game', lambda: g.ask_quit('game'), False)],
                    title='PAUSED')
        self.pages['pause'] = pause
        yield
        death = CornerPage(self, 'death')
        death.build([('Respawn', lambda: g.respawn_after_death(), True), ('Quit', lambda: g.quit_after_death(), False)],
                    title=' ')
        death.title_txt.scale = 1.1
        self.pages['death'] = death
        yield
        self.pages['settings'] = SettingsPage(self)
        yield
        self.pages['keybinds'] = KeybindsPage(self)
        yield
        self.pages['saves'] = SavesPage(self)
        yield
        self.pages['continue'] = ContinuePage(self)
        yield
        self.pages['newworld'] = NewWorldPage(self)
        yield
        self.pages['worldopts'] = WorldOptsPage(self)
        yield
        self.pages['custom'] = CustomPage(self)
        yield
        self.pages['items'] = ItemsPage(self)
        self.pages['map'] = MapPage(self)
        yield

    def relayout(self):
        for p in self.pages.values():
            p.layout()

    # ------------------------------------------------------------ navigation
    def open(self, name, push=True):
        if self.current is not None:
            if push:
                self.stack.append(self.current.name)
            self.current.enabled = False
        self.set_focus(None)
        pg = self.pages[name]
        pg.enabled = True
        self.current = pg
        pg.layout()
        pg.on_show()

    def back(self):
        if self.current is None:
            return
        if self.current.name == 'settings':
            self.game.settings.save()
        if self.stack:
            name = self.stack.pop()
            if self.current.name == 'saves':
                self.after_save = None
            self.open(name, push=False)
        elif self.game.state == 'paused':
            self.game.resume_game()

    def close_all(self):
        if self.current is not None:
            self.current.enabled = False
        self.current, self.stack = None, []
        self.dim.enabled = False
        self.dialog_close()
        self.capture = self.focus = None
        self.after_save = None

    def open_saves(self, mode):
        self.pages['saves'].mode = mode
        self.open('saves')

    def widgets(self):
        if self.dialog:
            return self.dialog['widgets']
        return self.current.widgets if self.current else []

    def set_focus(self, f):
        if self.focus is not None and self.focus is not f:
            self.focus.focused = False
            self.focus.refresh()
        self.focus = f
        if f is not None:
            f.focused = True
            f.refresh()

    # ----------------------------------------------------------------- mouse
    def update(self, dt):
        mx, my = mouse.x, mouse.y
        for w in self.widgets():
            w.hover_at(mx, my)
        if self.active_slider is not None:
            self.active_slider.drag_to(mx)
        self.blink += dt
        if self.focus is not None:
            c = int(self.blink * 2) % 2 == 0
            if c != self.focus.caret:
                self.focus.caret = c
                self.focus.refresh()
        if self.dialog and self.dialog.get('field') is not None:
            d = self.dialog
            d['field_txt'].text = d['text'] + ('_' if int(self.blink * 2) % 2 == 0 else ' ')

    def click(self, mx, my):
        if self.capture:
            return
        ws = self.widgets()
        if self.focus is not None and not self.focus.contains(mx, my):
            self.set_focus(None)
        for w in ws:
            if isinstance(w, PDropdown) and w.is_open and not w.contains(mx, my):
                w.close()
                return
        for w in reversed(ws):
            if w.contains(mx, my):
                if isinstance(w, PSlider):
                    self.active_slider = w
                w.click(mx, my)
                return

    def release(self):
        if self.active_slider is not None:
            self.active_slider.release()
            self.active_slider = None
            self.game.settings.save()
            self.game.apply_settings()

    # --------------------------------------------------------------- dialogs
    def dialog_close(self):
        if self.dialog:
            try:
                destroy(self.dialog['root'])
            except Exception:
                pass
            self.dialog = None

    def dialog_open(self, title, lines, buttons=None, field=None, on_submit=None, on_cancel=None):
        self.dialog_close()
        self.set_focus(None)
        root = Entity(parent=self.root, z=-8)
        Entity(parent=root, model='quad', scale=(5, 3), color=C(0, 0, 0, 150), z=0.5)
        if field is not None:
            buttons = [('Cancel', on_cancel, ''), ('OK', None, 'accent')]
        nb = len(buttons)
        bw = 0.17
        w = max(0.54, nb * (bw + 0.02) + 0.06)
        h = 0.07 + 0.085 + 0.1 + 0.04 * len(lines) + (0.075 if field is not None else 0)
        frame(root, w, h, title, header=0.07, footer=0.085)
        for i, ln in enumerate(lines):
            Text(text=ln, parent=root, position=(0, h / 2 - 0.07 - 0.05 - i * 0.04, -0.2), origin=(0, 0),
                 scale=0.95, color=T.WHITE)
        d = {'root': root, 'widgets': [], 'field': field, 'text': field or '', 'on_submit': on_submit,
             'on_cancel': on_cancel}
        self.dialog = d
        if field is not None:
            fy = -h / 2 + 0.085 + 0.045
            rect(root, 0, fy - 0.02, w - 0.14, 0.003, T.WHITE, -0.1)
            d['field_txt'] = Text(text=field, parent=root, position=(-(w - 0.14) / 2 + 0.005, fy, -0.3),
                                  origin=(-0.5, 0), scale=1.1, color=T.WHITE)
        x0 = -(nb * bw + (nb - 1) * 0.02) / 2 + bw / 2
        for i, (label, cb, style) in enumerate(buttons):
            action = self._submit_field if (field is not None and label == 'OK') else self._wrap(cb)
            d['widgets'].append(PButton(root, x0 + i * (bw + 0.02), -h / 2 + 0.04, bw, 0.065, label, action,
                                        accent=(style == 'accent'), danger=(style == 'danger'), scale=0.9,
                                        tab=True))

    def _wrap(self, cb):
        def run():
            self.dialog_close()
            if cb:
                cb()
        return run

    def _submit_field(self):
        d = self.dialog
        if not d:
            return
        text = d['text'].strip()
        if not text:
            return
        cb = d['on_submit']
        self.dialog_close()
        if cb:
            cb(text)

    def confirm(self, title, lines, on_yes, danger=False, yes='Yes', no='No'):
        self.dialog_open(title, lines, [(no, None, ''), (yes, on_yes, 'danger' if danger else 'accent')])

    def dialog_key(self, key):
        d = self.dialog
        if key == 'escape':
            cb = d.get('on_cancel')
            self.dialog_close()
            if cb and d.get('field') is not None:
                cb()
            return
        if d.get('field') is None:
            if key in ('enter', 'return') and d['widgets']:
                d['widgets'][-1].click(0, 0)
            return
        if key in ('enter', 'return'):
            self._submit_field()
        elif key == 'backspace':
            d['text'] = d['text'][:-1]
        elif key == 'space':
            if len(d['text']) < 22:
                d['text'] += ' '
        elif len(key) == 1 and (key.isalnum() or key in '-_.'):
            if len(d['text']) < 22:
                d['text'] += key.upper() if (key.isalpha() and held('shift')) else key


class SettingsPage(Page):
    TABS = ['Controls', 'Graphics', 'Audio', 'General']

    def __init__(self, ui):
        super().__init__(ui, 'settings')
        self.tab = 'Controls'
        frame(self, 0.9, 0.82, 'Settings')
        self.tab_btns = {t: PButton(self, -0.33 + i * 0.22, 0.272, 0.2, 0.05, t, (lambda tt=t: self.set_tab(tt)),
                                    scale=0.85) for i, t in enumerate(self.TABS)}
        self.static = list(self.tab_btns.values())
        self.static.append(PButton(self, -0.27, -0.365, 0.3, 0.07, 'Reset Settings', self.ask_reset, tab=True, scale=0.9))
        self.static.append(PButton(self, 0.3, -0.365, 0.24, 0.07, 'Back', ui.back, tab=True))
        self.tab_widgets, self.tab_extras = [], []
        self.build_tab()

    def on_show(self):
        self.build_tab()

    def set_tab(self, t):
        self.g.settings.save()
        self.tab = t
        self.build_tab()

    def build_tab(self):
        for e in self.tab_widgets + self.tab_extras:
            try:
                destroy(e)
            except Exception:
                pass
        self.tab_widgets, self.tab_extras = [], []
        for t, b in self.tab_btns.items():
            b.accent = (t == self.tab)
            b.on_hot()
        s = self.g.settings.d
        ctl, gfx, aud = s['controls'], s['graphics'], s['audio']
        W, y0, dy, rows = 0.8, 0.18, 0.058, []

        def setter(grp, key, after=None):
            def f(v):
                s[grp][key] = v
                self.g.settings.dirty = True
                if after:
                    after()
                if self.ui.active_slider is None:
                    self.g.settings.save()
            return f
        ap = self.g.apply_settings
        if self.tab == 'Controls':
            rows.append(PToggle(self, 0, y0, W, 'Toggle Sprint', 'Press once to start sprinting, again to stop',
                                lambda: ctl['toggle_sprint'], setter('controls', 'toggle_sprint')))
            rows.append(PToggle(self, 0, y0 - dy, W, 'Toggle Crouch', 'Press once to crouch, again to stand',
                                lambda: ctl['toggle_crouch'], setter('controls', 'toggle_crouch')))
            rows.append(PButton(self, 0, y0 - 2 * dy - 0.015, 0.5, 0.06, 'Key Binds', lambda: self.ui.open('keybinds'),
                                accent=True))
        elif self.tab == 'Graphics':
            dy = 0.054
            rows.append(PSlider(self, 0, y0, W, 'UI Scale', 'Size of menus and HUD', 0.7, 1.25, lambda: gfx['ui_scale'],
                                setter('graphics', 'ui_scale'), lambda v: '%d%%' % round(v * 100), step=0.05))
            rows.append(PSlider(self, 0, y0 - dy, W, 'FOV', 'Field of view (mouse wheel works too)', 50, 120,
                                lambda: gfx['fov'], setter('graphics', 'fov'), lambda v: str(int(v)), step=1))
            rows.append(PToggle(self, 0, y0 - 2 * dy, W, 'Head Bob', 'Camera sway when walking / standing',
                                lambda: gfx['head_bob'], setter('graphics', 'head_bob')))
            rows.append(PToggle(self, 0, y0 - 3 * dy, W, 'Sprint/Crouch/Jump Effects', 'FOV changes while moving',
                                lambda: gfx['jump_effects'], setter('graphics', 'jump_effects')))
            rows.append(PToggle(self, 0, y0 - 4 * dy, W, 'Effects', 'Dust trail and other particles',
                                lambda: gfx['effects'], setter('graphics', 'effects')))
            rows.append(PToggle(self, 0, y0 - 5 * dy, W, 'Smooth Animations', 'Smooth size change when crouching',
                                lambda: gfx['smooth_animations'], setter('graphics', 'smooth_animations')))
            rows.append(PToggle(self, 0, y0 - 6 * dy, W, 'Low Poly', 'Faceted terrain (applies to newly created worlds)',
                                lambda: gfx['low_poly'], setter('graphics', 'low_poly')))
            rows.append(PDropdown(self, 0, y0 - 7 * dy, W, 'Shader', 'Screen effect (sun rays, colour grading...)',
                                  SHADERS, lambda: gfx['shader'], setter('graphics', 'shader', ap), fw=0.22))
            rows.append(PDropdown(self, 0, y0 - 8 * dy, W, 'Screen Type', 'Fullscreen or windowed',
                                  ['Fullscreen', 'Windowed'], lambda: gfx['screen_type'],
                                  setter('graphics', 'screen_type', ap), fw=0.22))
        elif self.tab == 'Audio':
            for i, (k, name, desc) in enumerate([('master', 'Master Volume', 'Everything'),
                                                 ('player', 'Player', 'Footsteps, swimming, landing'),
                                                 ('ambient', 'Ambient', 'Water, wind, night sounds'),
                                                 ('creatures', 'Creatures', 'Birds, animals, wanderers'),
                                                 ('effects', 'Effects', 'Hits, damage, pickups')]):
                rows.append(PSlider(self, 0, y0 - i * dy, W, name, desc, 0.0, 1.0, (lambda kk=k: aud[kk]),
                                    setter('audio', k, ap), lambda v: '%d%%' % round(v * 100), step=0.05))
        else:
            self.tab_extras.append(Text(text='Nothing here yet.', parent=self, position=(0, 0.05, -0.2),
                                        origin=(0, 0), scale=1.3, color=T.DIM))
        self.tab_widgets = rows
        self.widgets = self.static + self.tab_widgets

    def ask_reset(self):
        def do():
            m = {'Controls': ['controls', 'binds'], 'Graphics': ['graphics'], 'Audio': ['audio'], 'General': []}
            for grp in m[self.tab]:
                self.g.settings.reset_group(grp)
            self.g.settings.save()
            self.g.apply_settings()
            self.build_tab()
            self.g.hud.toast('%s settings reset' % self.tab)
        self.ui.confirm('Reset Settings', ['Reset all %s settings' % self.tab, 'to their defaults?'], do, danger=True)


class KeybindsPage(Page):
    def __init__(self, ui):
        super().__init__(ui, 'keybinds')
        frame(self, 0.9, 0.82, 'Key Binds')
        self.txt('Click a key, then press the new one. ESC cancels.', 0, 0.285, 0.75, T.DIM)
        self.buttons = {}
        for i, (act, label) in enumerate(BIND_LABELS):
            col, row = (0, i) if i < 8 else (1, i - 8)
            x, y = (-0.215 if col == 0 else 0.215), 0.225 - row * 0.066
            self.txt(label, x - 0.2, y, 0.85, T.WHITE, (-0.5, 0))
            self.buttons[act] = self.add(PButton(self, x + 0.125, y, 0.14, 0.045, '', (lambda a=act: self.begin(a)),
                                                 scale=0.8))
        self.add(PButton(self, -0.27, -0.365, 0.3, 0.07, 'Reset Binds', self.ask_reset, tab=True, scale=0.9))
        self.add(PButton(self, 0.3, -0.365, 0.24, 0.07, 'Back', ui.back, tab=True))

    def on_show(self):
        self.refresh()

    def refresh(self):
        binds = self.g.settings.d['binds']
        for act, b in self.buttons.items():
            b.set_text(pretty(binds[act]))
            b.accent = False
            b.on_hot()

    def begin(self, act):
        self.ui.capture = act
        b = self.buttons[act]
        b.set_text('...')
        b.accent = True
        b.on_hot()

    def assign(self, key):
        act = self.ui.capture
        self.ui.capture = None
        if key != 'escape':
            binds = self.g.settings.d['binds']
            old = binds[act]
            for other, k in binds.items():
                if other != act and k == key:
                    binds[other] = old
            binds[act] = key
            self.g.settings.save()
        self.refresh()

    def ask_reset(self):
        def do():
            self.g.settings.reset_group('binds')
            self.g.settings.save()
            self.refresh()
            self.g.hud.toast('Key binds reset')
        self.ui.confirm('Reset Key Binds', ['Reset every key bind', 'to its default?'], do, danger=True)


class MapSurface(Entity):
    """Pannable / zoomable map (2D texture or projected low-poly 3D relief), generated progressively."""

    def __init__(self, parent, x, y, size, N=64):
        super().__init__(parent=parent, position=(x, y, -0.2))
        self.size, self.N, self.N3 = size, N, 36
        self.mode, self.gen = '2D', None
        self.cx = self.cz = 0.0
        self.span = 512.0
        rect(self, 0, 0, size + 0.014, size + 0.014, T.WHITE, 0.05)
        rect(self, 0, 0, size, size, T.BLACK, 0.04)
        self.img = Entity(parent=self, model='quad', scale=(size, size), z=-0.01, enabled=False)
        self.m3 = Entity(parent=self, z=-0.02, scale=size * 0.9, enabled=False, double_sided=True)
        self.marker = tri(self, [(0, 0.022), (-0.014, -0.014), (0.014, -0.014)], T.RED, z=-0.05)
        self.marker.enabled = False
        self.job, self.wait = None, 0.0

    def request(self):
        self.wait, self.job = 0.1, None

    def set_mode(self, m):
        self.mode = m
        self.request()

    def hit(self, mx, my):
        s = G.ui_scale
        return abs(mx - self.x * s) <= self.size * 0.5 * s and abs(my - self.y * s) <= self.size * 0.5 * s

    def pan(self, dmx, dmy):
        s = G.ui_scale
        k = self.span / (self.size * s)
        self.cx -= dmx * k
        self.cz -= dmy * k / (0.8 if self.mode == '3D' else 1.0)
        self.request()

    def zoom(self, f):
        self.span = max(64.0, min(4096.0, self.span * f))
        self.request()

    def tick(self, dt):
        if self.gen is None:
            return
        if self.wait > 0:
            self.wait -= dt
            if self.wait <= 0:
                from PIL import Image
                self.job = (map2d_job(self.gen, self.cx, self.cz, self.span, self.N, Image) if self.mode == '2D'
                            else map3d_job(self.gen, self.cx, self.cz, self.span, self.N3))
        if self.job is not None:
            t0 = perf()
            while perf() - t0 < 0.006:
                try:
                    r = next(self.job)
                except StopIteration:
                    self.job = None
                    break
                if r is not None:
                    self.job = None
                    if isinstance(r, tuple):
                        self.m3.model = to_mesh(r[0], r[1])
                        self.m3.enabled, self.img.enabled = True, False
                    else:
                        tex = Texture(r)
                        tex.filtering = None
                        self.img.texture = tex
                        self.img.enabled, self.m3.enabled = True, False
                    break

    def place(self, px, pz, yaw, h):
        if self.gen is None:
            self.marker.enabled = False
            return
        X, Zr = (px - self.cx) / self.span, (pz - self.cz) / self.span
        if self.mode == '2D':
            sx, sy, k = X, Zr, self.size
        else:
            bh = self.gen.sea if self.gen.water else -5.0
            p = proj3(X, Zr, (max(h, bh) - bh) * 2.6 / self.span)
            sx, sy, k = p[0], p[1], self.size * 0.9
        lim = self.size * 0.48
        self.marker.position = (max(-lim, min(lim, sx * k)), max(-lim, min(lim, sy * k)), -0.05)
        self.marker.rotation_z = -yaw
        self.marker.enabled = True


class SavesPage(Page):
    """Saves of the CURRENT world."""
    PER = 4

    def __init__(self, ui):
        super().__init__(ui, 'saves')
        self.mode, self.index, self.rows = 'save', 0, []
        frame(self, 0.9, 0.82, 'Saves')
        self.wname = self.txt('', -0.42, 0.285, 0.95, T.WHITE, (-0.5, 0))
        self.edit_btn = PButton(self, 0.3, 0.285, 0.24, 0.05, 'Edit World', self.edit_world, scale=0.8)
        self.new_btn = PButton(self, 0, 0.222, 0.4, 0.05, '+ New Save', self.new_save, accent=True, scale=0.85)
        self.prev_btn = PButton(self, -0.12, -0.282, 0.13, 0.045, '< Prev', lambda: self.go(-1), scale=0.75)
        self.next_btn = PButton(self, 0.02, -0.282, 0.13, 0.045, 'Next >', lambda: self.go(1), scale=0.75)
        self.back_btn = PButton(self, 0.3, -0.365, 0.24, 0.07, 'Back', ui.back, tab=True)
        self.page_txt = self.txt('', -0.4, -0.365, 0.8, T.WHITE, (-0.5, 0))

    def on_show(self):
        self.index = 0
        self.rebuild()

    def go(self, d):
        self.index += d
        self.rebuild()

    def edit_world(self):
        self.ui.pages['worldopts'].open_for(self.g.cfg, self.g.world_id)

    def rebuild(self):
        for e in self.rows:
            try:
                destroy(e)
            except Exception:
                pass
        self.rows = []
        saving = self.mode == 'save'
        wid = self.g.world_id
        self.wname.text = 'World: %s' % self.g.cfg.get('name', '?')
        self.new_btn.enabled = saving
        saves = self.g.store.saves(wid) if wid else []
        pages = max(1, int(math.ceil(len(saves) / float(self.PER))))
        self.index = max(0, min(self.index, pages - 1))
        self.page_txt.text = '%s  Page %d/%d' % ('SAVE' if saving else 'LOAD', self.index + 1, pages)
        self.prev_btn.locked, self.next_btn.locked = self.index <= 0, self.index >= pages - 1
        self.prev_btn.on_hot()
        self.next_btn.on_hot()
        widgets = [self.back_btn, self.prev_btn, self.next_btn, self.edit_btn] + ([self.new_btn] if saving else [])
        top = 0.12 if saving else 0.17
        if not saves:
            self.rows.append(Text(text='No saves in this world yet', parent=self, position=(0, 0.0, -0.2),
                                  origin=(0, 0), scale=1.2, color=T.DIM))
        for i, sv in enumerate(saves[self.index * self.PER:(self.index + 1) * self.PER]):
            y = top - i * 0.105
            r = Entity(parent=self, position=(0, y, 0.5))
            rect(r, 0, 0, 0.82, 0.092, T.BLACK)
            rect(r, 0, 0, 0.808, 0.08, T.GREY_D, -0.01)
            self.rows.append(r)
            name = str(sv.get('name', '?'))
            name = name if len(name) <= 20 else name[:19] + '~'
            self.rows.append(Text(text=name, parent=self, position=(-0.39, y + 0.02, -0.2), origin=(-0.5, 0),
                                  scale=1.1, color=T.WHITE))
            self.rows.append(Text(text='%s | %s played' % (sv.get('modified', '?'), fmt_time(sv.get('playtime', 0))),
                                  parent=self, position=(-0.39, y - 0.02, -0.2), origin=(-0.5, 0), scale=0.7,
                                  color=T.DIM))
            b1 = PButton(self, 0.1, y, 0.14, 0.052, 'Save' if saving else 'Load', (lambda s=sv: self.primary(s)),
                         accent=True, scale=0.8)
            b1.locked = bool(sv.get('damaged')) and not saving
            b1.on_hot()
            b2 = PButton(self, 0.235, y, 0.115, 0.052, 'Rename', (lambda s=sv: self.rename(s)), scale=0.7)
            b3 = PButton(self, 0.34, y, 0.085, 0.052, 'Del', (lambda s=sv: self.delete(s)), danger=True, scale=0.7)
            self.rows += [b1, b2, b3]
            widgets += [b1, b2, b3]
        self.widgets = widgets

    def new_save(self):
        n = len(self.g.store.saves(self.g.world_id)) + 1

        def ok(name):
            self.g.do_save(self.g.store.new_slot(self.g.world_id), name)
            self.after_saved()
        self.ui.dialog_open('New Save', ['Name your save:'], field='Save %d' % n, on_submit=ok)

    def primary(self, sv):
        if self.mode == 'save':
            def ok():
                self.g.do_save(sv['slot'], sv.get('name', 'Save'))
                self.after_saved()
            self.ui.confirm('Overwrite Save', ['Overwrite "%s"?' % sv.get('name', '?'), 'Old data will be replaced.'],
                            ok, danger=True, yes='Overwrite')
        else:
            self.ui.confirm('Load Save', ['Load "%s"?' % sv.get('name', '?'), 'Unsaved progress will be LOST!'],
                            lambda: self.g.load_save(self.g.world_id, sv['slot']), danger=True, yes='Load')

    def after_saved(self):
        cb = self.ui.after_save
        self.ui.after_save = None
        if cb:
            self.ui.close_all()
            cb()
        else:
            self.rebuild()

    def rename(self, sv):
        def ok(name):
            def really():
                try:
                    self.g.store.save_rename(self.g.world_id, sv['slot'], name)
                    self.g.hud.toast('Renamed to "%s"' % name)
                except Exception as ex:
                    self.g.hud.toast('Rename failed')
                    print('[save] rename failed:', ex)
                self.rebuild()
            self.ui.confirm('Rename Save', ['Rename "%s"' % sv.get('name', '?'), 'to "%s"?' % name], really, yes='Rename')
        self.ui.dialog_open('Rename Save', ['New name:'], field=str(sv.get('name', '')), on_submit=ok)

    def delete(self, sv):
        def ok():
            self.g.store.save_delete(self.g.world_id, sv['slot'])
            self.g.hud.toast('Save deleted')
            self.rebuild()
        self.ui.confirm('Delete Save', ['Delete "%s"?' % sv.get('name', '?'), 'This can NOT be undone.'], ok,
                        danger=True, yes='Delete')


class ContinuePage(Page):
    """All worlds; each one expands to show its saves."""
    PER = 5

    def __init__(self, ui):
        super().__init__(ui, 'continue')
        self.expanded, self.index, self.rows = set(), 0, []
        frame(self, 0.9, 0.82, 'Continue')
        self.prev_btn = PButton(self, -0.12, -0.262, 0.13, 0.045, '< Prev', lambda: self.go(-1), scale=0.75)
        self.next_btn = PButton(self, 0.02, -0.262, 0.13, 0.045, 'Next >', lambda: self.go(1), scale=0.75)
        self.back_btn = PButton(self, 0.3, -0.365, 0.24, 0.07, 'Back', ui.back, tab=True)
        self.page_txt = self.txt('', -0.4, -0.365, 0.8, T.WHITE, (-0.5, 0))

    def on_show(self):
        self.index = 0
        self.rebuild()

    def go(self, d):
        self.index += d
        self.rebuild()

    def toggle(self, wid):
        self.expanded.symmetric_difference_update({wid})
        self.rebuild()

    def rebuild(self):
        for e in self.rows:
            try:
                destroy(e)
            except Exception:
                pass
        self.rows = []
        st = self.g.store
        entries = []
        for w in st.worlds():
            entries.append(('w', w, None))
            if w['id'] in self.expanded:
                sv = st.saves(w['id'])
                entries += [('s', w, s) for s in sv] if sv else [('n', w, None)]
        pages = max(1, int(math.ceil(len(entries) / float(self.PER))))
        self.index = max(0, min(self.index, pages - 1))
        self.page_txt.text = 'Page %d/%d' % (self.index + 1, pages)
        self.prev_btn.locked, self.next_btn.locked = self.index <= 0, self.index >= pages - 1
        self.prev_btn.on_hot()
        self.next_btn.on_hot()
        widgets = [self.back_btn, self.prev_btn, self.next_btn]
        if not entries:
            self.rows.append(Text(text='No worlds yet - create one with New Game', parent=self,
                                  position=(0, 0.05, -0.2), origin=(0, 0), scale=1.1, color=T.DIM))
        for i, (kind, w, sv) in enumerate(entries[self.index * self.PER:(self.index + 1) * self.PER]):
            y = 0.255 - i * 0.1
            cfg = w.get('cfg', {})
            r = Entity(parent=self, position=(0, y, 0.5))
            ind = 0.0 if kind == 'w' else 0.07
            rect(r, ind / 2, 0, 0.82 - ind, 0.088, T.BLACK)
            rect(r, ind / 2, 0, 0.808 - ind, 0.076, T.GREY_D if kind == 'w' else C(66, 66, 66), -0.01)
            self.rows.append(r)
            if kind == 'w':
                b0 = PButton(self, -0.385, y, 0.05, 0.05, 'v' if w['id'] in self.expanded else '>',
                             (lambda wid=w['id']: self.toggle(wid)), scale=0.9)
                dead = bool(w.get('dead'))
                self.rows.append(Text(text=str(cfg.get('name', '?'))[:22], parent=self, position=(-0.345, y + 0.018, -0.2),
                                      origin=(-0.5, 0), scale=1.1, color=T.RED if dead else T.WHITE))
                info = '%s | %s | %s%s' % (cfg.get('mode', '?'), cfg.get('difficulty', 'Normal'),
                                         (w.get('last_played') or '?'), ' | DEAD' if dead else '')
                self.rows.append(Text(text=info, parent=self, position=(-0.345, y - 0.02, -0.2), origin=(-0.5, 0),
                                      scale=0.65, color=T.DIM))
                b1 = PButton(self, 0.1, y, 0.13, 0.05, 'Play', (lambda wid=w['id']: self.g.play_world(wid)),
                             accent=True, scale=0.8)
                b1.locked = dead
                b1.on_hot()
                b2 = PButton(self, 0.225, y, 0.1, 0.05, 'Edit', (lambda ww=w: self.ui.pages['worldopts'].open_for(
                    ww['cfg'], ww['id'])), scale=0.75)
                b3 = PButton(self, 0.325, y, 0.085, 0.05, 'Del', (lambda ww=w: self.delete_world(ww)), danger=True,
                             scale=0.7)
                self.rows += [b0, b1, b2, b3]
                widgets += [b0, b1, b2, b3]
            elif kind == 'n':
                self.rows.append(Text(text='(no saves in this world)', parent=self, position=(-0.3, y, -0.2),
                                      origin=(-0.5, 0), scale=0.8, color=T.DIM))
            else:
                self.rows.append(Text(text=str(sv.get('name', '?'))[:22], parent=self, position=(-0.31, y + 0.016, -0.2),
                                      origin=(-0.5, 0), scale=0.95, color=T.WHITE))
                self.rows.append(Text(text='%s | %s' % (sv.get('modified', '?'), fmt_time(sv.get('playtime', 0))),
                                      parent=self, position=(-0.31, y - 0.018, -0.2), origin=(-0.5, 0), scale=0.62,
                                      color=T.DIM))
                b1 = PButton(self, 0.1, y, 0.13, 0.05, 'Load', (lambda ww=w, ss=sv: self.confirm_load(ww, ss)),
                             accent=True, scale=0.8)
                b1.locked = bool(w.get('dead')) or bool(sv.get('damaged'))
                b1.on_hot()
                b2 = PButton(self, 0.225, y, 0.1, 0.05, 'Rename', (lambda ww=w, ss=sv: self.rename_save(ww, ss)),
                             scale=0.65)
                b3 = PButton(self, 0.325, y, 0.085, 0.05, 'Del', (lambda ww=w, ss=sv: self.delete_save(ww, ss)),
                             danger=True, scale=0.7)
                self.rows += [b1, b2, b3]
                widgets += [b1, b2, b3]
        self.widgets = widgets

    def confirm_load(self, w, sv):
        self.ui.confirm('Load Save', ['Load "%s"' % sv.get('name', '?'), 'from "%s"?' % w['cfg'].get('name', '?')],
                        lambda: self.g.load_save(w['id'], sv['slot']), yes='Load')

    def delete_world(self, w):
        def ok():
            self.g.store.delete(w['id'])
            self.g.hud.toast('World deleted')
            self.rebuild()
        self.ui.confirm('Delete World', ['Delete "%s"' % w['cfg'].get('name', '?'), 'and ALL of its saves?'], ok,
                        danger=True, yes='Delete')

    def delete_save(self, w, sv):
        def ok():
            self.g.store.save_delete(w['id'], sv['slot'])
            self.rebuild()
        self.ui.confirm('Delete Save', ['Delete "%s"?' % sv.get('name', '?')], ok, danger=True, yes='Delete')

    def rename_save(self, w, sv):
        def ok(name):
            self.g.store.save_rename(w['id'], sv['slot'], name)
            self.rebuild()
        self.ui.dialog_open('Rename Save', ['New name:'], field=str(sv.get('name', '')), on_submit=ok)


class NewWorldPage(Page):
    MODES = ['Flat +', 'Flat', 'Normal', 'Custom']
    GAMEMODES = ['Explorer', 'Creative']

    def __init__(self, ui):
        super().__init__(ui, 'newworld')
        g = self.g
        self.f = {'name': '', 'seed': '', 'mode': 'Normal', 'gamemode': 'Explorer', 'life': True, 'debug': False,
                  'cheats': False}
        f = self.f
        self.sig = None
        frame(self, 0.96, 0.74, 'New World')
        rect(self, 0.0, 0.005, 0.006, 0.56, T.BLACK, 0.5)
        rect(self, 0.243, -0.135, 0.46, 0.27, T.GREY_D, 0.4)
        self.surf = MapSurface(self, 0.243, 0.14, 0.26, N=56)
        self.txt('drag = move   wheel = zoom', 0.243, -0.022, 0.65, T.DIM)

        def sf(k):
            def s(v):
                f[k] = v
            return s
        rw, rx = 0.44, -0.245
        self.name_w = PTextField(self, rx, 0.235, rw, 'Name:', lambda: f['name'], sf('name'), 24,
                                 lambda ch: ch.isalnum() or ch in " -_.'", hint='(optional)')
        self.seed_w = PTextField(self, rx, 0.17, rw, 'Seed:', lambda: f['seed'], sf('seed'), 18,
                                 lambda ch: ch.isalnum() or ch == '.', upper=True, hint='11 digits')
        self.copy_b = PButton(self, -0.415, 0.122, 0.09, 0.04, 'Copy', self.copy_seed, tab=True, scale=0.6)
        self.regen_b = PButton(self, -0.31, 0.122, 0.15, 0.04, 'Regenerate', self.regen, tab=True, scale=0.6)
        self.store_b = PButton(self, -0.17, 0.122, 0.13, 0.04, 'Store seed', self.store_seed, tab=True, scale=0.6)
        self.stored_w = None
        self.terrain_w = PDropdown(self, rx, -0.005, rw, 'Terrain mode:', None, self.MODES, lambda: f['mode'],
                                   self.set_mode)
        self.game_w = PDropdown(self, rx, -0.075, rw, 'Gamemode:', None, self.GAMEMODES, lambda: f['gamemode'],
                                sf('gamemode'))
        self.life_w = PToggle(self, rx, -0.145, rw, 'Life Form Spawn:', None, lambda: f['life'], sf('life'))
        self.more_b = PButton(self, -0.37, -0.215, 0.2, 0.045, 'More options...', lambda: ui.pages['worldopts'].open_for(
            g.new_opts, None), scale=0.7)
        self.cust_b = PButton(self, -0.14, -0.215, 0.2, 0.045, 'Customize...', lambda: ui.open('custom'), accent=True,
                              scale=0.7)
        self.debug_w = PToggle(self, 0.243, -0.08, 0.42, 'Debug mode:', None, lambda: f['debug'], sf('debug'))
        self.cheat_w = PToggle(self, 0.243, -0.15, 0.42, 'Cheats:', None, lambda: f['cheats'], sf('cheats'))
        self.create_b = PButton(self, -0.33, -0.325, 0.24, 0.07, 'Create', self.create, tab=True)
        self.back_b = PButton(self, 0.33, -0.325, 0.24, 0.07, 'Back', ui.back, tab=True)
        self.rebuild_stored()
        self.set_mode(f['mode'])

    def rebuild_stored(self):
        if self.stored_w is not None:
            destroy(self.stored_w)
        st = self.g.store.stored_seeds() or ['(none)']

        def pick(v):
            if v != '(none)':
                self.f['seed'] = v
                self.seed_w.refresh()
        self.stored_w = PDropdown(self, -0.245, 0.065, 0.44, 'Stored:', None, st[:10], lambda: 'choose...', pick, fw=0.27)
        self.set_mode(self.f['mode'])

    def set_mode(self, m):
        self.f['mode'] = m
        custom = m == 'Custom'
        self.cust_b.enabled = custom
        self.widgets = [self.create_b, self.back_b, self.name_w, self.seed_w, self.copy_b, self.regen_b, self.store_b,
                        self.life_w, self.more_b, self.debug_w, self.cheat_w] + ([self.cust_b] if custom else []) + \
                       [self.game_w, self.terrain_w, self.stored_w]

    def on_show(self):
        if not self.f['seed'].strip():
            self.regen()
        for w in self.widgets:
            w.refresh()
        self.sig = None

    def regen(self):
        self.f['seed'] = '%011d' % random.randrange(10 ** 11)
        self.seed_w.refresh()

    def copy_seed(self):
        self.g.hud.toast('Seed copied' if copy_text(self.f['seed']) else 'Clipboard unavailable', 1.2)

    def store_seed(self):
        s = self.f['seed'].strip().upper()
        if s and self.g.store.store_seed(s):
            self.g.hud.toast('Seed stored')
            self.rebuild_stored()
        else:
            self.g.hud.toast('Nothing to store / already stored', 1.2)

    def _parse(self):
        s = self.f['seed'].strip().upper()
        if s.startswith('USERCR'):
            rec = CustomStore.load(s)
            return None if not rec else {'mode': 'Custom', 'custom': rec['custom'], 'base': int(rec['base'])}
        if s.isdigit() and len(s) <= 11:
            return {'mode': self.f['mode'], 'custom': copy.deepcopy(self.g.custom) if self.f['mode'] == 'Custom' else None,
                    'base': int(s)}
        return None

    def sync(self, dt):
        """Called every frame: live preview follows seed / mode / custom options."""
        sig = (self.f['seed'].strip().upper(), self.f['mode'], json.dumps(self.g.custom, sort_keys=True))
        if sig != self.sig:
            self.sig = sig
            c = self._parse()
            self.surf.gen = WorldGen(c) if c else None
            if c:
                self.surf.cx = self.surf.cz = 0.0
                self.surf.request()
        self.surf.tick(dt)

    def create(self):
        f, g = self.f, self.g
        s = f['seed'].strip().upper()
        mode, custom = f['mode'], None
        if s.startswith('USERCR'):
            rec = CustomStore.load(s)
            if not rec:
                g.hud.toast('Unknown USERCR seed')
                return
            mode, custom, base, seed = 'Custom', rec['custom'], int(rec['base']), s
        else:
            if s == '':
                base = random.randrange(10 ** 11)
            elif s.isdigit() and len(s) <= 11:
                base = int(s)
            else:
                g.hud.toast('Seed must be up to 11 digits')
                return
            if mode == 'Custom':
                custom = copy.deepcopy(g.custom)
                seed = CustomStore.save(custom, base)
                g.store.store_seed(seed)     # custom seeds are only stored once you actually play them
            else:
                seed = '%011d' % base
        name = f['name'].strip() or 'World %d' % (len(g.store.worlds()) + 1)
        o = copy.deepcopy(g.new_opts)
        cfg = norm_cfg({'name': name, 'seed': seed, 'mode': mode, 'base': base, 'custom': custom,
                        'gamemode': f['gamemode'], 'life': f['life'], 'debug': f['debug'], 'cheats': f['cheats'],
                        'difficulty': o['difficulty'], 'mobs': o['mobs'], 'day': o['day']})
        g.world_id = g.store.create(cfg)
        g.begin_generation(cfg, None, lambda: g.start_world(cfg))


class WorldOptsPage(Page):
    TABS = ['World', 'Mobs']

    def __init__(self, ui):
        super().__init__(ui, 'worldopts')
        frame(self, 0.9, 0.82, 'World Options')
        self.tab, self.target, self.wid = 'World', None, None
        self.tab_btns = {t: PButton(self, -0.12 + i * 0.24, 0.272, 0.22, 0.05, t, (lambda tt=t: self.set_tab(tt)),
                                    scale=0.85) for i, t in enumerate(self.TABS)}
        self.static = list(self.tab_btns.values()) + [PButton(self, 0.3, -0.365, 0.24, 0.07, 'Back', self.close, tab=True)]
        self.dyn, self.extras = [], []

    def open_for(self, target, wid=None):
        self.target, self.wid, self.tab = target, wid, 'World'
        self.ui.open('worldopts')

    def close(self):
        if self.wid is not None:
            self.g.store.update(self.wid, cfg=self.target)
            if self.wid == self.g.world_id:
                self.g.apply_cfg()
        self.ui.back()

    def on_show(self):
        self.build_tab()

    def set_tab(self, t):
        self.tab = t
        self.build_tab()

    def build_tab(self):
        for e in self.dyn + self.extras:
            try:
                destroy(e)
            except Exception:
                pass
        self.dyn, self.extras = [], []
        for t, b in self.tab_btns.items():
            b.accent = (t == self.tab)
            b.on_hot()
        T_, rows, W = self.target, [], 0.8
        if T_ is None:
            self.widgets = self.static
            return
        if self.tab == 'World':
            y = 0.19
            if self.wid is not None:
                rows.append(PTextField(self, 0, y, W, 'World name:', lambda: T_.get('name', ''),
                                       lambda v: T_.__setitem__('name', v), 24,
                                       lambda ch: ch.isalnum() or ch in " -_.'", fw=0.3))
                y -= 0.07
            rows.append(PToggle(self, 0, y - 0.07 * 3, W, 'Day / night cycle', 'Time passes by itself',
                                lambda: T_['day']['cycle'], self._set_cycle))
            if T_['day']['cycle']:
                rows.append(PSlider(self, 0, y - 0.07 * 4, W, 'Day length', 'Real minutes per full day', 1, 60,
                                    lambda: T_['day']['len'], lambda v: T_['day'].__setitem__('len', float(v)),
                                    lambda v: '%d min' % int(v), step=1))
            else:
                rows.append(PSlider(self, 0, y - 0.07 * 4, W, 'Time of day', 'Frozen at this hour (0-24)', 0, 24,
                                    lambda: T_['day']['time'], lambda v: T_['day'].__setitem__('time', float(v)),
                                    lambda v: '%02d:%02d' % (int(v), int((v % 1) * 60)), step=0.25))
            rows.append(PDropdown(self, 0, y, W, 'Difficulty', 'Harder = more mob damage, faster stat drain',
                                  DIFFS, lambda: T_['difficulty'], lambda v: T_.__setitem__('difficulty', v), fw=0.24))
            self.extras.append(Text(text='Hardcore: one life. Hard & Hardcore: peaceful animals fight back when bothered.',
                                    parent=self, position=(0, -0.26, -0.2), origin=(0, 0), scale=0.6, color=T.DIM))
        else:
            M = T_['mobs']
            rows.append(PToggle(self, 0, 0.19, W, 'Mobs', 'Master switch - off removes every creature',
                                lambda: M['enabled'], lambda v: M.__setitem__('enabled', v)))
            for i, k in enumerate(MOB_ORDER):
                col, r = i % 2, i // 2
                sp = MOBS[k]
                rows.append(PToggle(self, -0.2 + col * 0.4, 0.1 - r * 0.062, 0.38, '%s (%s)' % (sp['name'], sp['beh'][:5]),
                                    None, (lambda kk=k: M['types'][kk]), (lambda v, kk=k: M['types'].__setitem__(kk, v))))
        self.dyn = rows
        self.widgets = self.static + rows

    def _set_cycle(self, v):
        self.target['day']['cycle'] = v
        invoke(self.build_tab, delay=0.02)


class CustomPage(Page):
    TABS = ['Biomes', 'Elements', 'Terrain', 'Structures']
    EL = [('oceans', 'Oceans'), ('rivers', 'Rivers'), ('trees', 'Trees'), ('rocks', 'Rocks'),
          ('flowers', 'Flowers / grass'), ('caves', 'Caves'), ('structures', 'Structures')]
    ST = [('tent', 'Tents'), ('camp', 'Camps'), ('shed', 'Sheds'), ('cabin', 'Cabins')]

    def __init__(self, ui):
        super().__init__(ui, 'custom')
        frame(self, 0.96, 0.74, 'Custom World')
        self.tab = 'Biomes'
        self.tab_btns = {t: PButton(self, -0.33 + i * 0.22, 0.235, 0.2, 0.045, t, (lambda tt=t: self.set_tab(tt)),
                                    scale=0.8) for i, t in enumerate(self.TABS)}
        self.static = list(self.tab_btns.values()) + [
            PButton(self, -0.31, -0.325, 0.28, 0.07, 'Reset', self.ask_reset, tab=True, scale=0.9),
            PButton(self, 0.33, -0.325, 0.24, 0.07, 'Done', ui.back, tab=True)]
        self.dyn = []
        self.build_tab()

    def on_show(self):
        self.build_tab()

    def set_tab(self, t):
        self.tab = t
        self.build_tab()

    def _row(self, rows, x, y, label, node, w_t=0.34, w_s=0.54):
        rows.append(PToggle(self, x - 0.17, y, w_t, label, None, (lambda: node['on']), (lambda v: node.__setitem__('on', v))))
        rows.append(PSlider(self, x + 0.2, y, w_s, '', None, 0.0, 2.0, (lambda: node['amt']),
                            (lambda v: node.__setitem__('amt', float(v))), (lambda v: 'x%.1f' % v), step=0.1))

    def build_tab(self):
        for e in self.dyn:
            try:
                destroy(e)
            except Exception:
                pass
        for t, b in self.tab_btns.items():
            b.accent = (t == self.tab)
            b.on_hot()
        cu, rows = self.g.custom, []
        if self.tab == 'Biomes':
            for i, k in enumerate(BIOME_KEYS):
                col, r = i % 2, i // 2
                rows.append(PToggle(self, -0.235 + col * 0.47, 0.15 - r * 0.07, 0.44, k.capitalize(), None,
                                    (lambda kk=k: cu['biomes'][kk]), (lambda v, kk=k: cu['biomes'].__setitem__(kk, v))))
        elif self.tab == 'Elements':
            for i, (k, name) in enumerate(self.EL):
                self._row(rows, -0.12, 0.16 - i * 0.06, name, cu['elements'][k])
        elif self.tab == 'Terrain':
            rows.append(PToggle(self, 0, 0.17, 0.8, 'Water', None, lambda: cu['water'], lambda v: cu.__setitem__('water', v)))
            for i, (k, name, lo, hi, st, fm) in enumerate([('sea_level', 'Sea level', -6.0, 8.0, 0.5, '%.1f'),
                                                           ('height', 'Terrain height', 0.3, 2.0, 0.1, 'x%.1f'),
                                                           ('mountain_amt', 'Mountains', 0.0, 2.0, 0.1, 'x%.1f'),
                                                           ('biome_size', 'Biome size', 0.5, 2.0, 0.1, 'x%.1f')]):
                rows.append(PSlider(self, 0, 0.1 - i * 0.07, 0.8, name, None, lo, hi, (lambda kk=k: cu[kk]),
                                    (lambda v, kk=k: cu.__setitem__(kk, float(v))), (lambda v, ff=fm: ff % v), step=st))
        else:
            for i, (k, name) in enumerate(self.ST):
                self._row(rows, -0.12, 0.15 - i * 0.07, name, cu['structs'][k])
        self.dyn = rows
        self.widgets = self.static + rows

    def ask_reset(self):
        def do():
            self.g.custom.clear()
            self.g.custom.update(default_custom())
            self.build_tab()
        self.ui.confirm('Reset Custom World', ['Reset all custom options?'], do, danger=True)


class ItemsPage(Page):
    def __init__(self, ui):
        super().__init__(ui, 'items')
        frame(self, 0.9, 0.6, 'Items  (creative / cheats)', footer=0.095)
        self.txt('Click an item to add 16 to your inventory.', 0, 0.13, 0.8, T.DIM)
        for i, (k, v) in enumerate(ITEMS.items()):
            col, r = i % 4, i // 4
            b = self.add(PButton(self, -0.315 + col * 0.21, 0.04 - r * 0.11, 0.19, 0.09, v[0], (lambda kk=k: self.give(kk)),
                                 scale=0.8))
            rect(self, -0.315 + col * 0.21 - 0.07, 0.04 - r * 0.11, 0.026, 0.026, tuple_color(v[1]), -0.3)
        self.add(PButton(self, 0.3, -0.255, 0.24, 0.07, 'Close', lambda: self.g.close_items(), tab=True))

    def give(self, k):
        self.g.inv_add(k, 16)
        self.g.sfx.play('pickup', 0.6)


class MapPage(Page):
    def __init__(self, ui):
        super().__init__(ui, 'map')
        frame(self, 0.96, 0.82, 'Map')
        self.surf = MapSurface(self, -0.18, 0.0, 0.62, N=72)
        self.mode_b = self.add(PButton(self, 0.33, 0.2, 0.24, 0.06, 'View: 2D', self.flip, accent=True, scale=0.85))
        self.add(PButton(self, 0.33, 0.12, 0.24, 0.06, 'Zoom +', lambda: self.surf.zoom(0.7), scale=0.85))
        self.add(PButton(self, 0.33, 0.04, 0.24, 0.06, 'Zoom -', lambda: self.surf.zoom(1.4), scale=0.85))
        self.add(PButton(self, 0.33, -0.04, 0.24, 0.06, 'Center', self.center, scale=0.85))
        self.add(PButton(self, 0.33, -0.365, 0.24, 0.07, 'Close', lambda: self.g.resume_game(), tab=True))
        self.txt('drag = move\nwheel = zoom', 0.33, -0.15, 0.7, T.DIM)

    def flip(self):
        self.surf.set_mode('3D' if self.surf.mode == '2D' else '2D')
        self.mode_b.set_text('View: ' + self.surf.mode)

    def center(self):
        p = self.g.player
        self.surf.cx, self.surf.cz = p.x, p.z
        self.surf.request()

    def on_show(self):
        self.surf.gen = self.g.world.gen
        self.center()

    def sync(self, dt):
        p = self.g.player
        self.surf.tick(dt)
        self.surf.place(p.x, p.z, p.rotation_y, p.y)


# =============================================================================
#  LOADING SCREEN / HUD
# =============================================================================
class LoadingScreen(Entity):
    def __init__(self):
        super().__init__(parent=camera.ui)
        self.scale = Vec3(G.ui_scale, G.ui_scale, 1)
        Entity(parent=self, model='quad', scale=(5, 3), color=T.GREY, z=5)
        rect(self, 0, 0.39, 5, 0.22, T.BLACK, 4)
        Text(text='LOW POLY EXPLORER', parent=self, position=(0, 0.39, -1), origin=(0, 0), scale=3.0, color=T.WHITE)
        self.spin = []
        for i in range(8):
            a = i * math.pi / 4
            self.spin.append(Entity(parent=self, model=poly(0.02, 0.02, 0.0, (0, 0, 0, 0)), rotation_z=45,
                                    position=(math.cos(a) * 0.05, 0.02 + math.sin(a) * 0.05, -1), double_sided=True))
        self.bar_x, self.bar_w = -0.22, 0.4
        rect(self, self.bar_x + self.bar_w / 2, -0.15, self.bar_w + 0.012, 0.042, T.BLACK, -1)
        self.fill = rect(self, self.bar_x, -0.15, self.bar_w, 0.03, T.BLUE, -1.2, ox=-0.5)
        self.fill.scale_x = 0.001
        self.pct = Text(text='0%', parent=self, position=(self.bar_x + self.bar_w + 0.04, -0.15, -1.2),
                        origin=(-0.5, 0), scale=1.5, color=T.WHITE)
        self.msg = Text(text='', parent=self, position=(self.bar_x, -0.2, -1.2), origin=(-0.5, 0), scale=0.8,
                        color=T.WHITE)
        self.t = 0.0

    def set(self, pct, msg=None):
        self.fill.scale_x = max(0.001, min(1.0, pct / 100.0))
        self.pct.text = '%d%%' % int(pct)
        if msg is not None:
            self.msg.text = msg

    def tick(self, dt):
        self.t += dt
        head = int(self.t * 10) % 8
        for i, e in enumerate(self.spin):
            v = 1.0 - ((head - i) % 8) / 10.0
            e.color = Color(v, v, v, 1)


class HUD:
    FPS_W, FPS_H = 0.2, 0.07
    ST_W, ST_H = 0.34, 0.09

    def __init__(self, game):
        self.game = game
        self.fps_visible = self.st_visible = False
        self.inv_visible = True
        self._st_cache = None
        self.toast_t = self.flash_a = self.red_a = 0.0
        self.death = False
        self._red_c = -1.0
        w, h = self.FPS_W, self.FPS_H
        self.fps_root = Entity(parent=camera.ui, z=-2)
        corner_panel(self.fps_root, w, h, ox=0.5, oy=0.5, corners=(0, 0, 0, 1))
        self.fps_txt = Text(text='FPS: --', parent=self.fps_root, position=(-w / 2 + 0.006, -h / 2 + 0.003, -0.2),
                            origin=(0, 0), scale=0.95, color=T.WHITE)
        w, h = self.ST_W, self.ST_H
        self.st_root = Entity(parent=camera.ui, z=-2)
        corner_panel(self.st_root, w, h, ox=-0.5, oy=-0.5, corners=(1, 1, 0, 0))
        Text(text='STAMINA', parent=self.st_root, position=(0.032, h - 0.027, -0.2), origin=(-0.5, 0), scale=0.7,
             color=T.WHITE)
        self.st_pct = Text(text='100%', parent=self.st_root, position=(w - 0.032, h - 0.027, -0.2), origin=(0.5, 0),
                           scale=0.7, color=T.WHITE)
        self.bar_w = w - 0.064
        rect(self.st_root, 0.032, 0.024, self.bar_w, 0.03, T.BLACK, -0.1, ox=-0.5, oy=-0.5)
        self.st_fill = rect(self.st_root, 0.036, 0.028, self.bar_w - 0.008, 0.022, T.BLUE, -0.2, ox=-0.5, oy=-0.5)
        for k in (0.25, 0.5, 0.75):
            rect(self.st_root, 0.036 + (self.bar_w - 0.008) * k, 0.039, 0.002, 0.022, T.BLACK, -0.3)
        # toast
        self.toast_root = Entity(parent=camera.ui, z=-3, enabled=False)
        rect(self.toast_root, 0, 0, 0.56, 0.056, T.WHITE)
        rect(self.toast_root, 0, 0, 0.552, 0.048, T.BLACK, -0.01)
        self.toast_txt = Text(text='', parent=self.toast_root, position=(0, 0, -0.2), origin=(0, 0), scale=0.85,
                              color=T.WHITE)
        # debug
        self.debug_root = Entity(parent=camera.ui, z=-2, enabled=False)
        rect(self.debug_root, 0, 0, 0.52, 0.2, C(0, 0, 0, 170), 0, ox=-0.5, oy=0.5)
        self.debug_txt = Text(text='', parent=self.debug_root, position=(0.012, -0.012, -0.2), origin=(-0.5, 0.5),
                              scale=0.62, color=T.WHITE)
        # overlays
        self.water = Entity(parent=camera.ui, model='quad', scale=(5, 3), color=Color(0.1, 0.3, 0.65, 0.38), z=6,
                            enabled=False)
        self.red = Entity(parent=camera.ui, model='quad', scale=(5, 3), color=Color(0.8, 0.05, 0.05, 0.0), z=4.5)
        self.cross = Entity(parent=camera.ui, model='quad', scale=0.008, rotation_z=45, color=color.azure, z=-1,
                            enabled=False)
        # hotbar (9 slots + a '+' slot)
        self.hb = Entity(parent=camera.ui, z=-2)
        self.slots = []
        for i in range(10):
            e = Entity(parent=self.hb, position=((i - 4.5) * 0.074, 0, 0))
            e.edge = rect(e, 0, 0, 0.068, 0.068, T.BLACK)
            rect(e, 0, 0, 0.058, 0.058, C(52, 52, 58), -0.01)
            e.icon = rect(e, 0, 0.004, 0.032, 0.032, T.WHITE, -0.02)
            e.icon.enabled = False
            e.cnt = Text(text='', parent=e, position=(0.027, -0.022, -0.1), origin=(0.5, 0), scale=0.6, color=T.WHITE)
            Text(text=str((i + 1) % 10), parent=e, position=(-0.026, 0.023, -0.1), origin=(-0.5, 0), scale=0.45,
                 color=T.DIM)
            if i == 9:
                Text(text='+', parent=e, position=(0, 0, -0.1), origin=(0, 0), scale=2.2, color=T.WHITE)
            self.slots.append(e)
        self.hp = Entity(parent=camera.ui, z=-2)
        rect(self.hp, 0, 0, 0.4, 0.036, T.BLACK)
        rect(self.hp, -0.19, 0, 0.38, 0.024, C(70, 20, 22), -0.01, ox=-0.5)
        self.hp_fill = rect(self.hp, -0.19, 0, 0.38, 0.024, T.RED, -0.02, ox=-0.5)
        self.hp_txt = Text(text='', parent=self.hp, position=(0, 0, -0.2), origin=(0, 0), scale=0.55, color=T.WHITE)
        # command bar
        self.cmd = Entity(parent=camera.ui, z=-3, enabled=False)
        rect(self.cmd, 0, 0, 0.9, 0.05, C(0, 0, 0, 220))
        self.cmd_txt = Text(text='', parent=self.cmd, position=(-0.435, 0, -0.2), origin=(-0.5, 0), scale=0.9,
                            color=T.WHITE)
        self.hint_bg = rect(self.cmd, -0.45, 0.03, 0.9, 1.0, C(0, 0, 0, 190), 0, ox=-0.5, oy=-0.5)
        self.hint_txt = Text(text='', parent=self.cmd, position=(-0.44, 0.04, -0.2), origin=(-0.5, -0.5), scale=0.7,
                             color=T.WHITE)
        self.layout(animate=False)

    def layout(self, animate=True):
        ar, s = window.aspect_ratio, G.ui_scale
        for e in (self.fps_root, self.st_root, self.toast_root, self.debug_root, self.hb, self.hp, self.cmd):
            e.scale = Vec3(s, s, 1)
        self.fps_root.y = 0.5
        fx = ar / 2 + (0 if self.fps_visible else (self.FPS_W + 0.02) * s)
        sx = -ar / 2 if self.st_visible else -ar / 2 - (self.ST_W + 0.02) * s
        self.st_root.y = -0.5
        self.toast_root.position = (0, 0.4, -3)
        self.debug_root.position = (-ar / 2, 0.5, -2)
        self.cmd.position = (0, -0.5 + 0.2 * s, -3)
        hy = -0.5 + 0.045 * s if self.inv_visible else -0.5 - 0.06 * s
        py = -0.5 + 0.108 * s if self.inv_visible else -0.5 - 0.05 * s
        if animate:
            self.fps_root.animate_x(fx, duration=0.28, curve=curve.out_cubic)
            self.st_root.animate_x(sx, duration=0.25, curve=curve.out_cubic)
            self.hb.animate_y(hy, duration=0.3, curve=curve.out_cubic)
            self.hp.animate_y(py, duration=0.3, curve=curve.out_cubic)
        else:
            self.fps_root.x, self.st_root.x, self.hb.y, self.hp.y = fx, sx, hy, py

    def set_fps_visible(self, v):
        self.fps_visible = v
        self.layout(True)

    def set_stamina_visible(self, v):
        if v != self.st_visible:
            self.st_visible = v
            self.layout(True)

    def set_inv_visible(self, v):
        self.inv_visible = v
        self.layout(True)

    def set_fps(self, fps):
        self.fps_txt.text = 'FPS: %d' % fps

    def set_stamina(self, frac, exhausted):
        q = (int(frac * 200), exhausted)
        if q == self._st_cache:
            return
        self._st_cache = q
        self.st_fill.scale_x = max(frac, 0.001)
        self.st_pct.text = '%d%%' % int(round(frac * 100))
        self.st_fill.color = T.RED if exhausted else (T.ORANGE if frac < 0.25 else T.BLUE)

    def set_health(self, h, mx):
        self.hp_fill.scale_x = max(0.001, min(1.0, h / mx))
        self.hp_txt.text = 'HP %d / %d' % (math.ceil(h), mx)

    def set_inventory(self, inv, sel):
        for i, e in enumerate(self.slots):
            e.edge.color = T.WHITE if i == sel else T.BLACK
            s = inv[i] if i < 9 else None
            e.icon.enabled = bool(s)
            if s:
                e.icon.color = tuple_color(ITEMS[s[0]][1])
                e.cnt.text = str(s[1]) if s[1] > 1 else ''
            else:
                e.cnt.text = ''

    def flash(self):
        self.flash_a = 0.4

    def toast(self, msg, secs=2.0):
        self.toast_txt.text = msg
        self.toast_root.enabled = True
        self.toast_t = secs

    def show_cmd(self, text, hints):
        self.cmd.enabled = True
        self.cmd_txt.text = text + ('_' if int(pytime.time() * 2) % 2 == 0 else ' ')
        self.hint_txt.text = '\n'.join(reversed(hints)) if hints else ''
        self.hint_bg.scale_y = (len(hints) * 0.028 + 0.016) if hints else 0.0001

    def hide_cmd(self):
        self.cmd.enabled = False

    def tick(self, dt):
        if self.toast_t > 0:
            self.toast_t -= dt
            if self.toast_t <= 0:
                self.toast_root.enabled = False
        self.red_a += ((0.5 if self.death else 0.0) - self.red_a) * min(1.0, dt * 3)
        self.flash_a *= math.exp(-4 * dt)
        a = max(self.red_a, self.flash_a)
        if abs(a - self._red_c) > 0.004:
            self._red_c = a
            self.red.color = Color(0.8, 0.05, 0.05, a)


# =============================================================================
#  PLAYER
# =============================================================================
class Player(Entity):
    GRAVITY = 30.0

    def __init__(self):
        super().__init__(position=Vec3(0, 5, 0))
        self.camera_pivot = Entity(parent=self, y=2)
        self.height, self.vy, self.grounded = 2.0, 0.0, False
        self.jump_height, self.gmult = 2.8, 1.0
        self.sens = Vec2(52, 52)
        self.world = None
        self.swimming = False

    def look(self):
        if not mouse.locked:
            return
        mv = mouse.velocity
        self.rotation_y += mv[0] * self.sens[1]
        self.camera_pivot.rotation_x = max(-90, min(90, self.camera_pivot.rotation_x - mv[1] * self.sens[0]))

    def step(self, dt, wish, speed, jump, fly, vert, jump_held, crouch_held):
        """Returns (landing speed, entered_water)."""
        w = self.world
        R = 0.6                                   # collision field in front of the player
        if wish.length() > 0.001:
            sub = max(1, int(speed * dt / 0.25) + 1)
            dx, dz = wish[0], wish[2]
            for _ in range(sub):
                mvx, mvz = dx * speed * dt / sub, dz * speed * dt / sub
                nx, nz = self.x + mvx, self.z + mvz
                if not fly:
                    gy0 = w.ground(self.x, self.z)
                    ln = math.hypot(mvx, mvz)
                    rise = max(w.ground(nx + dx * R, nz + dz * R), w.ground(nx, nz)) - gy0
                    if rise > (ln + R) * 1.25 + 0.08 and self.y < gy0 + rise - 0.35:
                        nx, nz = self.x, self.z
                        for ax, az in ((mvx, 0.0), (0.0, mvz)):
                            l2 = math.hypot(ax, az)
                            if l2 < 1e-6:
                                continue
                            sx, sz = self.x + ax, self.z + az
                            r2 = max(w.ground(sx + ax / l2 * R, sz + az / l2 * R), w.ground(sx, sz)) - gy0
                            if r2 <= (l2 + R) * 1.25 + 0.08:
                                nx, nz = sx, sz
                                break
                nx, nz = w.push(nx, nz, self.y)
                self.x, self.z = nx, nz
        gy = w.ground(self.x, self.z)
        wl = w.sea
        landed, entered = 0.0, False
        G_ = self.GRAVITY * self.gmult
        deep = wl > -1000 and gy < wl - 1.1
        if fly:
            self.y = max(self.y + vert * dt, gy)
            self.vy = 0.0
            self.grounded = self.y <= gy + 0.02
            self.swimming = False
        elif deep and self.y < wl - 0.25:
            if not self.swimming:
                entered = True
            self.swimming = True
            fy = wl - 1.65
            tv = 3.2 if jump_held else (-3.2 if crouch_held else (fy - self.y) * 2.2)
            self.vy += (tv - self.vy) * min(1.0, 5 * dt)
            self.y = max(gy, min(self.y + self.vy * dt, wl - 0.9))
            self.grounded = False
        else:
            self.swimming = False
            if jump and self.grounded:
                self.vy = math.sqrt(2 * G_ * self.jump_height)
                self.grounded = False
                self.y += 0.02
            if self.vy <= 0 and (self.y + self.vy * dt <= gy + 0.02 or (self.grounded and self.y - gy < 0.6)):
                if not self.grounded:
                    landed = -self.vy
                self.grounded, self.vy, self.y = True, 0.0, gy
            else:
                self.grounded = False
                self.vy = max(self.vy - G_ * dt, -70.0)
                self.y += self.vy * dt
        return landed, entered


class DustPool:
    def __init__(self, n=28):
        self.items, self.active = [], []
        for _ in range(n):
            V, Cc = [], []
            p_octa(V, Cc, 0, 0, 0, 0.5, 0.5, 0.5, (165, 145, 105))
            e = Entity(model=to_mesh(V, Cc), double_sided=True, enabled=False)
            e.life = e.max_life = e.base = 0.0
            self.items.append(e)

    def spawn(self, pos):
        if not self.items:
            return
        e = self.items.pop()
        e.position = pos
        e.base = random.uniform(0.1, 0.2)
        e.max_life = e.life = random.uniform(0.35, 0.5)
        e.rotation = Vec3(random.uniform(0, 360), random.uniform(0, 360), random.uniform(0, 360))
        e.scale = e.base
        e.enabled = True
        self.active.append(e)

    def update(self, dt):
        for e in self.active[:]:
            e.life -= dt
            if e.life <= 0:
                e.enabled = False
                self.active.remove(e)
                self.items.append(e)
                continue
            e.scale = e.base * (e.life / e.max_life)
            e.y += 0.9 * dt
            e.rotation_y += 120 * dt

    def clear(self):
        for e in self.active[:]:
            e.enabled = False
            self.items.append(e)
        self.active = []


# =============================================================================
#  DIRECTOR
# =============================================================================
SHADER_VERT = '''
#version 140
uniform mat4 p3d_ModelViewProjectionMatrix;
in vec4 p3d_Vertex;
in vec2 p3d_MultiTexCoord0;
out vec2 uv;
void main() {
    gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
    uv = p3d_MultiTexCoord0;
}
'''
SHADER_FRAG = '''
#version 140
uniform sampler2D tex;
uniform vec2 sun_pos;
uniform float sunvis;
uniform float rays;
uniform float warm;
uniform float sat;
uniform float vig;
uniform float post;
in vec2 uv;
out vec4 color;
void main() {
    vec3 base = texture(tex, uv).rgb;
    vec3 acc = vec3(0.0);
    if (rays > 0.001 && sunvis > 0.001) {
        vec2 d = (sun_pos - uv) * 0.85 / 24.0;
        vec2 p = uv;
        float w = 1.0;
        for (int i = 0; i < 24; i++) {
            p += d;
            vec3 s = texture(tex, clamp(p, 0.0, 1.0)).rgb;
            float l = dot(s, vec3(0.333));
            acc += max(vec3(l - 0.62), vec3(0.0)) * w;
            w *= 0.94;
        }
        acc *= rays * sunvis / 6.0;
    }
    vec3 c = base + acc * vec3(1.0, 0.55, 0.18) * 3.0;
    c *= mix(vec3(1.0), vec3(1.08, 0.95, 0.8), warm);
    float g = dot(c, vec3(0.299, 0.587, 0.114));
    c = mix(vec3(g), c, sat);
    float v = smoothstep(0.95, 0.25, distance(uv, vec2(0.5)));
    c *= mix(1.0, v, vig);
    if (post > 1.0) { c = floor(c * post) / post; }
    color = vec4(c, 1.0);
}
'''
SHADER_PRESETS = {'Sun Rays': dict(rays=1.0, warm=0.6, sat=1.1, vig=0.25, post=0.0),
                  'Golden Hour': dict(rays=0.35, warm=1.0, sat=1.15, vig=0.45, post=0.0),
                  'Vivid': dict(rays=0.0, warm=0.0, sat=1.5, vig=0.15, post=0.0),
                  'Retro': dict(rays=0.0, warm=0.2, sat=1.2, vig=0.1, post=12.0)}


class ShaderFX:
    def __init__(self):
        self.sh, self.name, self.ok = None, 'None', True
        try:
            self.sh = Shader(language=Shader.GLSL, vertex=SHADER_VERT, fragment=SHADER_FRAG,
                             default_input={'sun_pos': Vec2(0.5, 0.5), 'sunvis': 0.0, 'rays': 0.0, 'warm': 0.0,
                                            'sat': 1.0, 'vig': 0.0, 'post': 0.0})
        except Exception as ex:
            print('[shader] unavailable:', ex)
            self.ok = False

    def set(self, name):
        if name == self.name:
            return
        self.name = name
        try:
            if name == 'None' or not self.ok or name not in SHADER_PRESETS:
                camera.shader = None
                self.name = 'None'
                return
            camera.shader = self.sh
            for k, v in SHADER_PRESETS[name].items():
                camera.set_shader_input(k, float(v))
        except Exception as ex:
            print('[shader] failed:', ex)
            self.ok = False
            self.name = 'None'

    def update(self, sdir, daylight):
        if self.name == 'None':
            return
        try:
            from panda3d.core import Point2, Point3
            cp = camera.world_position
            p3 = base.cam.getRelativePoint(base.render, Point3(cp[0] + sdir[0] * 200, cp[1] + sdir[1] * 200,
                                                         cp[2] + sdir[2] * 200))
            pt = Point2()
            vis = 0.0
            if base.camLens.project(p3, pt):
                camera.set_shader_input('sun_pos', Vec2(pt.x * 0.5 + 0.5, pt.y * 0.5 + 0.5))
                vis = 1.0
            else:
                camera.set_shader_input('sun_pos', Vec2(0.5, 1.4))
                vis = 0.35
            camera.set_shader_input('sunvis', float(vis * daylight))
        except Exception:
            pass


class Director(Entity):
    def __init__(self):
        super().__init__()
        G.game = self
        self.state = 'loading'
        self.settings = Settings()
        self.settings.load()
        G.ui_scale = self.settings.d['graphics']['ui_scale']
        self._find_font()
        self.store = WorldStore()
        self.ui = self.hud = self.player = self.dust = self.sfx = self.world = self.fx = None
        self.sky = self.sun = self.moon = None
        self.life, self.mobs = Life(self), Mobs(self)
        self.cfg = DEMO_CFG
        self.world_id = None
        self.custom, self.new_opts = default_custom(), default_opts()
        self.water_tex = None
        self._last = {}
        self.fps_acc, self.fps_frames, self.fps_val = 0.0, 0, 0
        self.fps_game, self.fps_menu = True, False
        self.last_aspect = window.aspect_ratio
        self.screen_wait, self.screen_tries = 0.0, 0
        self.spawn = Vec3(0, 3, 0)
        self.fov_cur, self.fov_kick, self.kick_v = 90.0, 0.0, 0.0
        self.eye_lag, self.prev_y = 0.0, 0.0
        self.is_sprinting = self.crouching = self.sprint_latch = self.crouch_latch = False
        self.flying = False
        self.stamina, self.max_stamina, self.exhausted = 100.0, 100.0, False
        self.health, self.max_health = 20.0, 20
        self.hurt_t, self.god = 99.0, False
        self.speed_mult = self.jump_mult = self.grav_mult = 1.0
        self.inv, self.sel = [None] * 9, 0
        self.bob_timer = self.bob_intensity = self.dust_timer = self.sprint_linger = 0.0
        self.jump_buffer, self.last_jump_t, self.atk_cd = 0.0, 0.0, 0.0
        self.skip_look = 0
        self.respawning, self.drag_speed = False, 0.0
        self.distance_traveled, self.jump_count, self.reset_count, self.playtime = 0.0, 0, 0, 0.0
        self.dirty = False
        self.last_pos = Vec3(0, 0, 0)
        self.menu_t, self.menu_par = 0.0, Vec2(0, 0)
        self.step_t = self.bird_t = self.amb_t = self.dbg_t = self.night_t = 0.0
        self.t, self.tod, self.day_f = 0.0, 9.0, 1.0
        self.death_t, self.death_eye, self.death_fwd, self.death_cause = 0.0, Vec3(0, 0, 0), Vec3(0, 0, 1), ''
        self.cmd_open, self.cmd_text, self.cmd_hist, self.cmd_hi = False, '', [], -1
        self.drag = None
        self.gen_job = self.gen_load = self.gen_done = None
        self.loading = LoadingScreen()
        self.load_gen = self.load_steps()
        self.load_shown = self.load_target = LOAD_START
        self.load_done, self.load_hold, self.splash_closed = False, 0.0, False
        self.loading.set(LOAD_START, 'Preparing')
        self.cmds, self.cmd_opts = self._build_cmds()
        mouse.visible = True

    # ------------------------------------------------------------- fonts
    def _find_font(self):
        cands = []
        try:
            fs = sorted([f for f in FONT_DIR.iterdir() if f.suffix.lower() in ('.ttf', '.otf')])
            cands += [f for f in fs if 'semibold' in f.name.lower() and 'cascadia' in f.name.lower()]
            cands += [f for f in fs if 'cascadia' in f.name.lower()] + fs
        except Exception:
            pass
        for d in ('C:/Windows/Fonts', os.path.expanduser('~/AppData/Local/Microsoft/Windows/Fonts')):
            for n in ('CascadiaMono-SemiBold.ttf', 'CascadiaMono.ttf', 'consolab.ttf', 'consola.ttf'):
                p = Path(d) / n
                if p.exists():
                    cands.append(p)
        for f in cands:
            old = Text.default_font
            Text.default_font = Path(f).as_posix()
            try:
                destroy(Text(text='test'))
                print('[font] using', Path(f).name)
                return
            except Exception:
                Text.default_font = old

    # ------------------------------------------------------------- loading
    def load_steps(self):
        yield 42, 'Generating sounds'
        self.sfx = Sfx()
        self.sfx.audio.update(self.settings.d['audio'])
        yield 46, 'Building sky'
        self.sky = Sky()
        self.sun = Entity(model='quad', color=Color(1, 0.88, 0.5, 1), scale=46, billboard=True, double_sided=True)
        self.moon = Entity(model='quad', color=Color(0.85, 0.9, 1, 1), scale=30, billboard=True, double_sided=True)
        self.fx = ShaderFX()
        try:
            from PIL import Image
            img = Image.new('RGBA', (32, 32))
            r = random.Random(5)
            for yy in range(32):
                for xx in range(32):
                    v = 200 + int(30 * math.sin(xx * 0.4 + yy * 0.2)) + r.randint(-10, 10)
                    img.putpixel((xx, yy), (min(255, v - 40), min(255, v - 10), 255, 255))
            self.water_tex = Texture(img)
            self.water_tex.filtering = None
        except Exception:
            self.water_tex = None
        yield 50, 'Creating the player'
        self.player = Player()
        self.dust = DustPool()
        yield 54, 'Building the HUD'
        self.hud = HUD(self)
        self.ui = UI(self)
        for _ in self.ui.build_steps():
            yield 62, 'Building menus'
        yield 70, 'Applying settings'
        self.apply_settings(initial=True)
        yield 74, 'Generating terrain'
        self.cfg = DEMO_CFG
        self.tod = DEMO_CFG['day']['time']
        self.world = World(DEMO_CFG, True, self.water_tex)
        self.player.world = self.world
        for p in self.world.initial_job(self.world.spawn, 2):
            yield 74 + 25 * p, 'Generating terrain'
        yield 100, 'Ready'

    def loader_tick(self, dt):
        t0 = perf()
        while not self.load_done and perf() - t0 < 0.02:
            try:
                pct, msg = next(self.load_gen)
                self.load_target = pct
                self.loading.msg.text = msg
                splash_report(min(99, pct), msg)
            except StopIteration:
                self.load_done = True
        self.load_shown += (self.load_target - self.load_shown) * min(1.0, 8 * dt)
        if self.load_done:
            self.load_shown = min(100.0, self.load_shown + 60 * dt)
        self.loading.set(self.load_shown)
        self.loading.tick(dt)
        if not self.splash_closed:
            splash_close()
            self.splash_closed = True
        if self.load_done and self.load_shown >= 99.5:
            self.load_hold += dt
            if self.load_hold > 0.25:
                destroy(self.loading)
                self.loading = None
                self.enter_main_menu()

    # --------------------------------------------------------- settings
    def apply_settings(self, initial=False):
        g = self.settings.d['graphics']
        G.ui_scale = g['ui_scale']
        if self.ui:
            self.ui.root.scale = Vec3(G.ui_scale, G.ui_scale, 1)
            self.ui.relayout()
        if self.hud:
            self.hud.layout(animate=False)
        if self.sfx:
            self.sfx.audio.update(self.settings.d['audio'])
        if self.fx:
            self.fx.set(g['shader'])
        self.screen_tries = 0
        self.screen_wait = 0.0

    def _screen_tick(self, dt):
        want = self.settings.d['graphics']['screen_type'] == 'Fullscreen'
        try:
            cur = bool(window.fullscreen)
        except Exception:
            return
        if cur == want:
            self.screen_tries = 0
            return
        self.screen_wait -= dt
        if self.screen_wait <= 0 and self.screen_tries < 8:
            self.screen_wait = 0.6
            self.screen_tries += 1
            try:
                window.fullscreen = want
            except Exception:
                pass

    def set_state(self, s):
        self.state = s
        if self.hud:
            grp = s in ('playing', 'paused', 'map', 'dead', 'items')
            self.hud.set_fps_visible(self.fps_game if grp else self.fps_menu)

    # ------------------------------------------------------------ states
    def _mouse_game(self):
        mouse.locked = True
        self.skip_look = 3

    def _mouse_menu(self):
        mouse.locked = False
        mouse.visible = True

    def _hide_play_hud(self):
        self.hud.cross.enabled = False
        self.hud.water.enabled = False
        self.hud.debug_root.enabled = False
        self.hud.hide_cmd()
        self.hud.death = False
        self.hud.set_stamina_visible(False)
        self.sfx.water_vol(0)
        self.sfx.loop_vol('wind', 0)

    def enter_main_menu(self):
        if self.world_id is not None:
            self.autosave()
        if self.world is None or not self.world.cfg.get('demo'):
            self.begin_generation(DEMO_CFG, None, self._show_menu)
            return
        self._show_menu()

    def _show_menu(self):
        self.set_state('menu')
        self.world_id = None
        self.ui.close_all()
        camera.parent = scene
        camera.fov = 70
        self._hide_play_hud()
        self.ui.open('main', push=False)
        self._mouse_menu()
        self.dust.clear()

    def begin_generation(self, cfg, center, on_done):
        self.set_state('generating')
        self.ui.close_all()
        self._hide_play_hud()
        self.cmd_open = False
        camera.parent = scene
        self.life.clear()
        self.mobs.clear()
        if self.world is not None:
            self.world.destroy()
        self.cfg = cfg = norm_cfg(cfg)
        self.world = World(cfg, self.settings.d['graphics']['low_poly'], self.water_tex)
        self.player.world = self.world
        self.tod = cfg['day']['time']
        self.gen_job = self.world.initial_job(center or self.world.spawn, 2)
        self.gen_done = on_done
        self.gen_load = LoadingScreen()
        self.gen_load.set(0, 'Generating terrain')

    def gen_tick(self, dt):
        t0, prog, finished = perf(), 0.0, False
        while perf() - t0 < 0.025:
            try:
                prog = next(self.gen_job)
            except StopIteration:
                finished = True
                break
        self.gen_load.set(100 if finished else prog * 100)
        self.gen_load.tick(dt)
        if finished:
            destroy(self.gen_load)
            self.gen_load = None
            cb, self.gen_done = self.gen_done, None
            cb()

    def start_world(self, cfg, state=None):
        w = self.world
        sx, sz = w.spawn
        self.spawn = Vec3(sx, w.ground(sx, sz) + 0.05, sz)
        self.reset_run()
        if state:
            self.apply_state(state)
        self.life.setup(cfg, self.player)
        self.hud.debug_root.enabled = bool(cfg.get('debug'))
        self.enter_play()

    def reset_run(self):
        p = self.player
        p.position = Vec3(self.spawn)
        p.rotation = Vec3(0, 0, 0)
        p.camera_pivot.rotation = Vec3(0, 0, 0)
        p.vy, p.grounded, p.height = 0.0, False, 2.0
        self.stamina, self.exhausted = self.max_stamina, False
        self.health, self.hurt_t, self.god = float(self.max_health), 99.0, False
        self.speed_mult = self.jump_mult = self.grav_mult = 1.0
        self.is_sprinting = self.crouching = self.sprint_latch = self.crouch_latch = self.flying = False
        self.respawning = False
        self.fov_kick = self.kick_v = self.eye_lag = 0.0
        self.fov_cur = self.settings.d['graphics']['fov']
        self.distance_traveled, self.jump_count, self.reset_count, self.playtime = 0.0, 0, 0, 0.0
        self.last_pos = Vec3(p.position)
        self.prev_y = p.y
        self.dirty = False
        self.inv, self.sel = [None] * 9, 0
        self.tod = self.cfg['day']['time']
        self.hud.set_stamina_visible(False)
        self.hud._st_cache = None
        self.hud.death = False
        self.hud.set_inventory(self.inv, self.sel)
        self.hud.set_health(self.health, self.max_health)

    def enter_play(self):
        self.set_state('playing')
        self.ui.close_all()
        camera.parent = self.player.camera_pivot
        camera.position = Vec3(0, 0, 0)
        camera.rotation = Vec3(0, 0, 0)
        camera.fov = self.fov_cur
        self.hud.cross.enabled = True
        self._mouse_game()

    def pause_game(self):
        self.set_state('paused')
        self._mouse_menu()
        self.hud.cross.enabled = False
        self.ui.open('pause', push=False)
        self.ui.dim.enabled = True
        self.sfx.water_vol(0)
        self.sfx.loop_vol('wind', 0)
        self.autosave()

    def resume_game(self):
        self.ui.close_all()
        self.set_state('playing')
        self.hud.cross.enabled = True
        self._mouse_game()

    def open_map(self):
        self.set_state('map')
        self._mouse_menu()
        self.hud.cross.enabled = False
        self.ui.open('map', push=False)

    def open_items(self):
        self.set_state('items')
        self._mouse_menu()
        self.hud.cross.enabled = False
        self.ui.open('items', push=False)

    def close_items(self):
        self.resume_game()

    # ------------------------------------------------------------ saving
    def collect_state(self):
        p = self.player
        return {'position': [p.x, p.y, p.z], 'rot_y': p.rotation_y, 'pitch': p.camera_pivot.rotation_x,
                'stamina': self.stamina, 'exhausted': self.exhausted, 'distance': self.distance_traveled,
                'jumps': self.jump_count, 'resets': self.reset_count, 'playtime': self.playtime,
                'health': self.health, 'inv': self.inv, 'sel': self.sel, 'tod': self.tod}

    def autosave(self):
        if self.world_id and self.player is not None and self.state in ('playing', 'paused', 'map', 'items'):
            try:
                self.store.set_state(self.world_id, self.collect_state())
            except Exception as ex:
                print('[autosave] failed:', ex)

    def do_save(self, slot, name):
        try:
            self.store.save_write(self.world_id, slot, name, self.collect_state())
            self.dirty = False
            self.hud.toast('Saved "%s"' % name)
        except Exception as ex:
            print('[save] failed:', ex)
            self.hud.toast('SAVE FAILED')

    def apply_state(self, d):
        p = self.player
        x, y, z = [float(v) for v in d.get('position', [self.spawn[0], self.spawn[1], self.spawn[2]])[:3]]
        p.position = Vec3(x, max(y, self.world.ground(x, z)), z)
        p.rotation_y = float(d.get('rot_y', 0))
        p.camera_pivot.rotation_x = max(-90, min(90, float(d.get('pitch', 0))))
        self.stamina = max(0.0, min(self.max_stamina, float(d.get('stamina', 100))))
        self.exhausted = bool(d.get('exhausted', False)) and self.stamina < self.max_stamina
        self.distance_traveled = float(d.get('distance', 0))
        self.jump_count, self.reset_count = int(d.get('jumps', 0)), int(d.get('resets', 0))
        self.playtime = float(d.get('playtime', 0))
        self.health = max(1.0, min(float(self.max_health), float(d.get('health', self.max_health))))
        inv = d.get('inv')
        if isinstance(inv, list) and len(inv) == 9:
            self.inv = [s if (isinstance(s, list) and len(s) == 2 and s[0] in ITEMS) else None for s in inv]
        self.sel = int(d.get('sel', 0)) % 9
        self.tod = float(d.get('tod', self.tod)) % 24.0
        self.last_pos = Vec3(p.position)
        self.prev_y = p.y
        self.hud.set_inventory(self.inv, self.sel)
        self.hud.set_health(self.health, self.max_health)

    def play_world(self, wid):
        try:
            j = self.store.read(wid)
            if j.get('dead'):
                self.hud.toast('This hardcore world has ended', 2.0)
                return
            cfg, st = norm_cfg(j['cfg']), j.get('state')
            pos = (st or {}).get('position', [0, 0, 0])
            self.world_id = wid
            self.begin_generation(cfg, (float(pos[0]), float(pos[2])) if st else None,
                                  lambda: self._after_load(cfg, st, None))
        except Exception as ex:
            print('[world] play failed:', ex)
            self.hud.toast('Could not open world')

    def load_save(self, wid, slot):
        try:
            d = self.store.save_read(wid, slot)
            cfg = norm_cfg(self.store.read(wid)['cfg'])
            pos = d.get('position', [0, 0, 0])
            self.world_id = wid
            self.begin_generation(cfg, (float(pos[0]), float(pos[2])), lambda: self._after_load(cfg, d, d.get('name')))
        except Exception as ex:
            print('[load] failed:', ex)
            self.hud.toast('LOAD FAILED (damaged save?)')

    def _after_load(self, cfg, st, name):
        self.start_world(cfg, st)
        if name:
            self.hud.toast('Loaded "%s"' % name)

    def apply_cfg(self):
        """World options were edited while that world is loaded."""
        self.cfg = norm_cfg(self.cfg)
        self.life.setup(self.cfg, self.player)
        self.hud.debug_root.enabled = bool(self.cfg.get('debug')) and self.state in ('playing', 'paused')
        if not self.cfg['day']['cycle']:
            self.tod = self.cfg['day']['time']

    # -------------------------------------------------------------- quit
    def ask_quit(self, kind):
        if kind == 'menu_quit':
            self.ui.confirm('Quit Game', ['Do you really want to quit?'], self.quit_game)
            return
        what = 'the main menu' if kind == 'menu' else 'the game'
        action = self.enter_main_menu if kind == 'menu' else self.quit_game

        def after_yes():
            if not self.dirty:
                action()
                return
            self.ui.dialog_open('Unsaved Progress', ['Do you want to save your', 'unsaved progress first?'], [
                ('Cancel', None, ''), ('Save and quit', lambda: self._save_then(action), 'accent'),
                ("Don't save", action, 'danger')])
        self.ui.confirm('Quit', ['Quit to %s?' % what], after_yes)

    def _save_then(self, action):
        self.ui.after_save = action
        self.ui.open_saves('save')

    def quit_game(self):
        self.autosave()
        try:
            self.settings.save()
        except Exception:
            pass
        application.quit()

    # --------------------------------------------------------- inventory
    def inv_add(self, item, n=1):
        left = n
        for s in self.inv:
            if s and s[0] == item and s[1] < 64 and left > 0:
                add = min(64 - s[1], left)
                s[1] += add
                left -= add
        for i in range(9):
            if left > 0 and self.inv[i] is None:
                add = min(64, left)
                self.inv[i] = [item, add]
                left -= add
        self.hud.set_inventory(self.inv, self.sel)
        if left < n:
            self.hud.toast('+%d %s' % (n - left, ITEMS[item][0]), 1.0)
            self.sfx.play('pickup', 0.5)
        return left == 0

    def use_item(self):
        s = self.inv[self.sel]
        if not s:
            return
        heal = ITEMS[s[0]][2]
        if heal > 0 and self.health < self.max_health:
            self.health = min(float(self.max_health), self.health + heal)
            s[1] -= 1
            if s[1] <= 0:
                self.inv[self.sel] = None
            self.sfx.play('eat', 0.7)
            self.hud.set_inventory(self.inv, self.sel)
            self.hud.set_health(self.health, self.max_health)
        else:
            self.hud.toast(ITEMS[s[0]][0], 0.8)

    # ------------------------------------------------------------ health
    def hurt_player(self, amount, cause):
        if self.state != 'playing' or self.god:
            return
        amount *= DIFF_DMG[self.cfg['difficulty']]
        if amount <= 0:
            return
        self.health -= amount
        self.hurt_t = 0.0
        self.hud.flash()
        self.sfx.play('hurt', 0.8, random.uniform(0.9, 1.1))
        self.hud.set_health(max(0.0, self.health), self.max_health)
        if self.health <= 0:
            if self.cfg.get('death', True):
                self.die(cause)
            else:
                self.health = 1.0
                self.hud.set_health(self.health, self.max_health)

    def die(self, cause):
        p = self.player
        self.set_state('dead')
        self.death_t = 0.0
        self.death_cause = cause
        self.death_eye = Vec3(p.x, p.y + p.camera_pivot.y, p.z)
        self.death_fwd = Vec3(p.forward[0], 0, p.forward[2])
        camera.parent = scene
        camera.position = Vec3(self.death_eye)
        camera.rotation = Vec3(p.camera_pivot.rotation_x, p.rotation_y, 0)
        self.hud.death = True
        self.hud.cross.enabled = False
        self.hud.hide_cmd()
        self.cmd_open = False
        self.is_sprinting = False
        self.hud.set_stamina_visible(False)
        self.sfx.play('death', 0.9)
        self._mouse_menu()
        pg = self.ui.pages['death']
        pg.title_txt.text = 'You died of\n%s' % cause
        hard = self.cfg['difficulty'] == 'Hardcore'
        pg.widgets = [pg.btns[1]] if hard else list(pg.btns)
        pg.btns[0].enabled = not hard
        pg.off = -0.9
        self.ui.open('death', push=False)

    def death_update(self, dt):
        self.death_t += dt
        k = min(1.0, self.death_t / 1.4)
        k = k * k * (3 - 2 * k)
        eye = self.death_eye
        cp = eye + Vec3(self.death_fwd[0] * -4.2 * k, 1.6 * k, self.death_fwd[2] * -4.2 * k)
        camera.position = cp
        d = eye - cp
        camera.rotation = Vec3(math.degrees(math.atan2(-d[1], math.hypot(d[0], d[2]))),
                               math.degrees(math.atan2(d[0], d[2])), 0)
        pg = self.ui.pages['death']
        e = clampf((self.death_t - 1.0) / 0.7)
        pg.off = -0.9 * (1 - e * e * (3 - 2 * e))
        pg.layout()
        self.world.update(self.death_eye[0], self.death_eye[2], self.t, 0.006)

    def respawn_after_death(self):
        p = self.player
        self.ui.close_all()
        self.ui.pages['death'].btns[0].enabled = True
        self.health, self.stamina, self.exhausted = float(self.max_health), self.max_stamina, False
        p.position = Vec3(self.spawn[0], self.world.ground(self.spawn[0], self.spawn[2]) + 0.05, self.spawn[2])
        p.vy, p.grounded = 0.0, False
        p.camera_pivot.rotation = Vec3(0, 0, 0)
        self.hud.death = False
        self.hud.set_health(self.health, self.max_health)
        self.prev_y, self.eye_lag = p.y, 0.0
        self.enter_play()

    def quit_after_death(self):
        if self.cfg['difficulty'] == 'Hardcore' and self.world_id:
            self.store.update(self.world_id, dead=True)
        self.ui.pages['death'].btns[0].enabled = True
        self.world_id_dead = None
        self.hud.death = False
        self.state = 'menu'
        self.world_id = None if self.cfg['difficulty'] == 'Hardcore' else self.world_id
        self.enter_main_menu()

    # --------------------------------------------------------- time of day
    def cam_world(self):
        if self.state in ('playing', 'paused', 'map', 'items', 'dead') and self.player is not None:
            return Vec3(self.player.x, self.player.y + 2, self.player.z)
        return Vec3(camera.world_position)

    def apply_tod(self, dt):
        day = self.cfg['day']
        if self.state in ('playing', 'menu'):
            if day['cycle']:
                self.tod = (self.tod + dt * 24.0 / (max(1.0, day['len']) * 60.0)) % 24.0
            else:
                self.tod = day['time']
        a = (self.tod - 6.0) / 24.0 * TAU
        e = math.sin(a)
        df = smooth(-0.12, 0.28, e)
        self.day_f = df
        warm = clampf(1.0 - abs(e) / 0.3) * 0.75 * min(1.0, df + 0.35)
        night, dusk = (0.3, 0.36, 0.62), (1.0, 0.72, 0.5)
        col = [night[i] + (1.0 - night[i]) * df for i in range(3)]
        col = [col[i] * (1 - warm) + dusk[i] * warm * (0.4 + 0.6 * df) for i in range(3)]
        try:
            base.render.setColorScale(col[0], col[1], col[2], 1.0)
        except Exception:
            try:
                scene.setColorScale(col[0], col[1], col[2], 1.0)
            except Exception:
                pass
        sd = Vec3(math.cos(a), math.sin(a), 0.35).normalized()
        self.sun_dir = sd
        cp = self.cam_world()
        self.sun.position = cp + sd * 280
        self.moon.position = cp - sd * 280
        self.sun.enabled = e > -0.1
        self.moon.enabled = e < 0.15
        self.fx.update(sd, df)

    # ----------------------------------------------------------- commands
    def _build_cmds(self):
        def tf(s):
            return s.lower() in ('true', 'on', '1', 'yes')

        def numarg(a, i, d=None):
            try:
                return float(a[i])
            except Exception:
                return d

        def c_health(a):
            v = self.max_health if (not a or a[0] == 'full') else numarg(a, 0, 20)
            self.health = max(0.0, min(float(self.max_health), v))
            self.hud.set_health(self.health, self.max_health)
            if self.health <= 0:
                self.die('a command')
            return 'Health = %d' % self.health

        def c_stamina(a):
            self.stamina = self.max_stamina if (not a or a[0] == 'full') else max(0.0, min(100.0, numarg(a, 0, 100)))
            self.exhausted = False
            return 'Stamina = %d' % self.stamina

        def c_fly(a):
            self.flying = not self.flying
            return 'Flying %s' % ('ON' if self.flying else 'OFF')

        def c_diff(a):
            for d in DIFFS:
                if a and d.lower() == a[0].lower():
                    self.cfg['difficulty'] = d
                    return 'Difficulty: %s' % d
            return 'Usage: difficulty <%s>' % '|'.join(x.lower() for x in DIFFS)

        def c_cheats(a):
            self.cfg['cheats'] = tf(a[0]) if a else not self.cfg.get('cheats')
            if not self.cfg['cheats']:
                self.flying = False
            return 'Cheats %s' % ('ON' if self.cfg['cheats'] else 'OFF')

        def c_speed(a):
            self.speed_mult = max(0.1, numarg(a, 0, 10.0) / 10.0)
            return 'Speed x%.1f' % self.speed_mult

        def c_jump(a):
            self.jump_mult = max(0.1, numarg(a, 0, 10.0) / 10.0)
            self.player.jump_height = 2.8 * self.jump_mult
            return 'Jump height x%.1f' % self.jump_mult

        def c_grav(a):
            self.grav_mult = max(0.05, numarg(a, 0, 10.0) / 10.0)
            self.player.gmult = self.grav_mult
            return 'Gravity x%.1f' % self.grav_mult

        def c_death(a):
            self.cfg['death'] = tf(a[0]) if a else True
            return 'Death %s' % ('enabled' if self.cfg['death'] else 'disabled')

        def c_god(a):
            self.god = tf(a[0]) if a else not self.god
            return 'God mode %s' % ('ON' if self.god else 'OFF')

        def c_gm(a):
            for m in ('Explorer', 'Creative'):
                if a and m.lower() == a[0].lower():
                    self.cfg['gamemode'] = m
                    if m == 'Explorer' and not self.cfg.get('cheats'):
                        self.flying = False
                    return 'Gamemode: %s' % m
            return 'Usage: gamemode <explorer|creative>'

        def c_time(a):
            presets = {'dawn': 6.0, 'day': 9.0, 'noon': 12.0, 'dusk': 18.0, 'night': 22.0, 'midnight': 0.0}
            if a and a[0] in presets:
                self.tod = presets[a[0]]
            elif numarg(a, 0) is not None:
                self.tod = numarg(a, 0) % 24.0
            else:
                return 'Usage: time <0-24|dawn|day|noon|dusk|night|midnight>'
            if not self.cfg['day']['cycle']:
                self.cfg['day']['time'] = self.tod
            return 'Time set to %02d:%02d' % (int(self.tod), int(self.tod % 1 * 60))

        def c_cycle(a):
            self.cfg['day']['cycle'] = tf(a[0]) if a else not self.cfg['day']['cycle']
            self.cfg['day']['time'] = self.tod
            return 'Day cycle %s' % ('ON' if self.cfg['day']['cycle'] else 'OFF')

        def c_daylen(a):
            self.cfg['day']['len'] = max(1.0, numarg(a, 0, 12.0))
            return 'Day length = %d min' % self.cfg['day']['len']

        def c_tp(a):
            p = self.player
            x, z = numarg(a, 0), numarg(a, 2)
            if x is None or z is None:
                return 'Usage: tp <x> <y|~> <z>'
            y = numarg(a, 1)
            gy = self.world.ground(x, z)
            p.position = Vec3(x, max(gy, y) if y is not None else gy + 0.05, z)
            p.vy = 0.0
            self.prev_y = p.y
            return 'Teleported to %.0f %.0f %.0f' % (p.x, p.y, p.z)

        def c_home(a):
            p = self.player
            p.position = Vec3(self.spawn)
            p.vy = 0.0
            return 'Back at spawn'

        def c_setspawn(a):
            p = self.player
            self.spawn = Vec3(p.x, p.y, p.z)
            return 'Spawn point set'

        def c_spawn(a):
            if not a or a[0] not in MOBS:
                return 'Usage: spawn <%s> [count]' % '|'.join(MOB_ORDER)
            n = int(numarg(a, 1, 1))
            p = self.player
            for i in range(max(1, min(n, 10))):
                ang = random.uniform(0, TAU)
                self.mobs.spawn(a[0], p.x + math.cos(ang) * 6, p.z + math.sin(ang) * 6)
            return 'Spawned %d %s' % (n, a[0])

        def c_killall(a):
            return 'Removed %d mobs' % self.mobs.remove_kind(a[0] if a and a[0] in MOBS else None)

        def c_mobs(a):
            self.cfg['mobs']['enabled'] = tf(a[0]) if a else not self.cfg['mobs']['enabled']
            if not self.cfg['mobs']['enabled']:
                self.mobs.clear()
            return 'Mobs %s' % ('ON' if self.cfg['mobs']['enabled'] else 'OFF')

        def c_mob(a):
            if len(a) < 2 or a[0] not in MOBS:
                return 'Usage: mob <%s> <true|false>' % '|'.join(MOB_ORDER)
            self.cfg['mobs']['types'][a[0]] = tf(a[1])
            return '%s %s' % (a[0], 'enabled' if tf(a[1]) else 'removed')

        def c_give(a):
            if not a or a[0] not in ITEMS:
                return 'Usage: give <%s> [count]' % '|'.join(ITEMS)
            self.inv_add(a[0], int(numarg(a, 1, 1)))
            return 'Given %s' % a[0]

        def c_clear(a):
            self.inv = [None] * 9
            self.hud.set_inventory(self.inv, self.sel)
            return 'Inventory cleared'

        def c_heal(a):
            self.health, self.stamina, self.exhausted = float(self.max_health), self.max_stamina, False
            self.hud.set_health(self.health, self.max_health)
            return 'Fully healed'

        def c_kill(a):
            self.health = 0.0
            self.die('a command')
            return ''

        def c_seed(a):
            return 'Seed: %s (%s)' % (self.cfg.get('seed'), self.cfg.get('mode'))

        def c_pos(a):
            p = self.player
            return 'XYZ %.1f %.1f %.1f' % (p.x, p.y, p.z)

        def c_biome(a):
            p = self.player
            return 'Biome: %s' % self.world.biome_at(p.x, p.z)

        def c_fov(a):
            self.settings.d['graphics']['fov'] = int(max(50, min(120, numarg(a, 0, 90))))
            return 'FOV = %d' % self.settings.d['graphics']['fov']

        def c_say(a):
            return ' '.join(a)

        def c_shader(a):
            for s in SHADERS:
                if a and ' '.join(a).lower() == s.lower():
                    self.settings.d['graphics']['shader'] = s
                    self.fx.set(s)
                    return 'Shader: %s' % s
            return 'Usage: shader <%s>' % '|'.join(x.lower() for x in SHADERS)

        def c_save(a):
            slot = self.store.new_slot(self.world_id)
            self.do_save(slot, ' '.join(a) or 'Quick save')
            return ''

        def c_help(a):
            names = sorted(self.cmds)
            if a and a[0] in self.cmds:
                u, d, _ = self.cmds[a[0]]
                return ';%s %s - %s' % (a[0], u, d)
            return 'Commands: ' + ' '.join(names)

        def c_respawn(a):
            self.begin_respawn()
            return ''

        def c_sprint(a):
            self.stamina = self.max_stamina
            return 'Stamina refilled'

        cmds = {
            'help': ('[command]', 'list commands', c_help), 'health': ('<number|full>', 'set health', c_health),
            'stamina': ('<number|full>', 'set stamina', c_stamina), 'heal': ('', 'full health + stamina', c_heal),
            'fly': ('', 'toggle flying', c_fly), 'difficulty': ('<difficulty>', 'change difficulty', c_diff),
            'cheats': ('<true|false>', 'toggle cheats', c_cheats),
            'speed': ('[number=10]', 'walk speed, 10 is normal', c_speed),
            'jumpheight': ('[number=10]', 'jump height, 10 is normal', c_jump),
            'gravity': ('[number=10]', 'gravity, 10 is normal', c_grav),
            'death': ('<true|false>', 'allow dying', c_death), 'god': ('[true|false]', 'invulnerable', c_god),
            'gamemode': ('<explorer|creative>', 'switch gamemode', c_gm),
            'time': ('<0-24|dawn|day|noon|dusk|night>', 'set time of day', c_time),
            'daycycle': ('<true|false>', 'day/night cycle on or off', c_cycle),
            'daylength': ('<minutes>', 'real minutes per day', c_daylen),
            'tp': ('<x> <y|~> <z>', 'teleport', c_tp), 'home': ('', 'go to spawn', c_home),
            'setspawn': ('', 'set spawn here', c_setspawn), 'spawn': ('<mob> [count]', 'spawn mobs', c_spawn),
            'killall': ('[mob]', 'remove mobs', c_killall), 'mobs': ('<true|false>', 'all mobs on/off', c_mobs),
            'mob': ('<mob> <true|false>', 'enable/remove one mob type', c_mob),
            'give': ('<item> [count]', 'give items', c_give), 'clear': ('', 'empty inventory', c_clear),
            'kill': ('', 'die', c_kill), 'seed': ('', 'show seed', c_seed), 'pos': ('', 'show position', c_pos),
            'biome': ('', 'current biome', c_biome), 'fov': ('<50-120>', 'set FOV', c_fov),
            'say': ('<text>', 'print a message', c_say), 'shader': ('<name>', 'switch shader', c_shader),
            'save': ('[name]', 'quick save', c_save), 'respawn': ('', 'return to spawn', c_respawn),
            'refill': ('', 'refill stamina', c_sprint),
        }
        bools = ['true', 'false']
        opts = {'difficulty': [d.lower() for d in DIFFS], 'cheats': bools, 'death': bools, 'god': bools,
                'daycycle': bools, 'mobs': bools, 'gamemode': ['explorer', 'creative'],
                'time': ['dawn', 'day', 'noon', 'dusk', 'night', 'midnight'], 'spawn': list(MOB_ORDER),
                'killall': list(MOB_ORDER), 'mob': list(MOB_ORDER), 'give': list(ITEMS),
                'shader': [s.lower() for s in SHADERS], 'health': ['full'], 'stamina': ['full'],
                'help': sorted(cmds)}
        return cmds, opts

    def cmd_hints(self, text):
        parts = text.split(' ')
        name = parts[0].lower()
        if len(parts) == 1:
            return [';%s %s' % (n, u) for n, (u, _, _) in sorted(self.cmds.items()) if n.startswith(name)][:7]
        if name in self.cmds:
            u, d, _ = self.cmds[name]
            out = [';%s %s  -  %s' % (name, u, d)]
            if len(parts) == 2:
                out += ['      ' + o for o in self.cmd_opts.get(name, []) if o.startswith(parts[1].lower())][:6]
            return out
        return []

    def cmd_complete(self):
        parts = self.cmd_text.split(' ')
        if len(parts) == 1:
            m = [n for n in sorted(self.cmds) if n.startswith(parts[0].lower())]
            if m:
                self.cmd_text = m[0] + ' '
        elif len(parts) == 2:
            m = [o for o in self.cmd_opts.get(parts[0].lower(), []) if o.startswith(parts[1].lower())]
            if m:
                self.cmd_text = parts[0] + ' ' + m[0]

    def run_cmd(self, text):
        parts = text.strip().split()
        if not parts:
            return
        name, args = parts[0].lower(), parts[1:]
        if name not in self.cmds:
            self.hud.toast('Unknown command "%s" - try ;help' % name, 2.5)
            return
        if name not in ('help', 'cheats', 'seed', 'pos', 'biome', 'say') and not self.cfg.get('cheats'):
            self.hud.toast('Cheats are off. Use ;cheats true', 2.5)
            return
        try:
            msg = self.cmds[name][2](args)
        except Exception as ex:
            msg = 'Command failed: %s' % ex
        if msg:
            self.hud.toast(msg[:70], 3.0)

    def open_cmd(self):
        self.cmd_open, self.cmd_text, self.cmd_hi = True, '', -1
        self.hud.show_cmd(';', self.cmd_hints(''))

    def close_cmd(self):
        self.cmd_open = False
        self.hud.hide_cmd()

    def cmd_key(self, k):
        PUNCT = {'semicolon': ';', 'slash': '/', 'period': '.', 'comma': ',', 'minus': '-', 'space': ' ',
                 'underscore': '_', 'tilde': '~'}
        if k == 'escape':
            self.close_cmd()
            return
        if k in ('enter', 'return'):
            t = self.cmd_text
            self.close_cmd()
            if t.strip():
                self.cmd_hist.append(t)
                self.run_cmd(t)
            return
        if k == 'tab':
            self.cmd_complete()
        elif k == 'backspace':
            self.cmd_text = self.cmd_text[:-1]
        elif k == 'up arrow' and self.cmd_hist:
            self.cmd_hi = min(len(self.cmd_hist) - 1, self.cmd_hi + 1)
            self.cmd_text = self.cmd_hist[-1 - self.cmd_hi]
        elif k == 'down arrow' and self.cmd_hist:
            self.cmd_hi = max(-1, self.cmd_hi - 1)
            self.cmd_text = self.cmd_hist[-1 - self.cmd_hi] if self.cmd_hi >= 0 else ''
        else:
            ch = PUNCT.get(k, k if len(k) == 1 else '')
            if ch and (ch.isalnum() or ch in ' .-_,~=') and len(self.cmd_text) < 60:
                self.cmd_text += ch.lower() if ch.isalpha() else ch
        self.hud.show_cmd(';' + self.cmd_text, self.cmd_hints(self.cmd_text))

    # ------------------------------------------------------------- input
    def once(self, name):
        t = pytime.time()
        if t - self._last.get(name, 0) < 0.08:
            return False
        self._last[name] = t
        return True

    def can_fly(self):
        return self.cfg.get('gamemode') == 'Creative' or bool(self.cfg.get('cheats'))

    def input(self, key):
        if self.state in ('loading', 'generating') or self.ui is None:
            return
        if key == 'left mouse down':
            if self.state == 'playing':
                if mouse.locked and not self.cmd_open:
                    self.attack()
                return
            pg = self.ui.current
            surf = getattr(pg, 'surf', None)
            if surf is not None and surf.hit(mouse.x, mouse.y) and not self.ui.dialog:
                self.drag = (surf, mouse.x, mouse.y)
            self.ui.click(mouse.x, mouse.y)
            return
        if key == 'right mouse down':
            if self.state == 'playing' and mouse.locked and not self.cmd_open:
                self.use_item()
            return
        if key == 'left mouse up':
            self.drag = None
            self.ui.release()
            return
        if key in ('scroll up', 'scroll down'):
            if self.state == 'playing' and not self.ui.dialog and not self.cmd_open:
                self.play_input(key, key, self.settings.d['binds'])
            else:
                surf = getattr(self.ui.current, 'surf', None)
                if surf is not None and surf.hit(mouse.x, mouse.y):
                    surf.zoom(0.8 if key == 'scroll up' else 1.25)
            return
        if key.endswith(' up') or key.endswith(' hold'):
            return
        k = norm_key(key)
        if self.ui.capture:
            if bindable(k) or k == 'escape':
                self.ui.pages['keybinds'].assign(k)
            return
        if self.ui.dialog:
            self.ui.dialog_key(k)
            return
        if self.ui.focus is not None:
            self.ui.focus.key(k)
            return
        if self.cmd_open:
            self.cmd_key(k)
            return
        b = self.settings.d['binds']
        if k == b['toggle_fps'] and self.once('fps'):
            if self.state in ('playing', 'paused', 'map', 'dead', 'items'):
                self.fps_game = not self.fps_game
            else:
                self.fps_menu = not self.fps_menu
            self.set_state(self.state)
            return
        if self.state == 'playing':
            self.play_input(key, k, b)
        elif self.state in ('map', 'items'):
            if k in ('escape', b['pause']) or (self.state == 'map' and k == b['map']):
                self.resume_game()
        elif k in ('escape', b['pause']):
            if self.state == 'paused' or (self.state == 'menu' and self.ui.stack):
                self.ui.back()

    def attack(self):
        if self.atk_cd > 0:
            return
        self.atk_cd = 0.4
        m = self.mobs.nearest_in_front(self.player)
        if m:
            self.mobs.hit(m, 3.0, self.player)
        else:
            self.sfx.play('punch', 0.25, random.uniform(1.1, 1.4))

    def play_input(self, key, k, b):
        g, ctl = self.settings.d['graphics'], self.settings.d['controls']
        if k in (';', 'semicolon', '/', 'slash'):
            self.open_cmd()
        elif k == b['pause']:
            self.pause_game()
        elif k == b['map']:
            self.open_map()
        elif k == b['inventory']:
            self.hud.set_inv_visible(not self.hud.inv_visible)
        elif len(k) == 1 and k in '123456789':
            self.sel = int(k) - 1
            self.hud.set_inventory(self.inv, self.sel)
        elif k == '0':
            if self.can_fly():
                self.open_items()
            else:
                self.hud.toast('The + slot needs Creative mode or cheats', 1.8)
        elif k == b['respawn'] and not self.respawning:
            self.begin_respawn()
        elif k == b['jump']:
            now = pytime.time()
            if self.can_fly() and now - self.last_jump_t < 0.3 and self.once('fly'):
                self.flying = not self.flying
                self.hud.toast('Flying: %s' % ('ON' if self.flying else 'OFF'), 1.0)
            self.last_jump_t = now
            self.jump_buffer = 0.12
        elif k == b['sprint'] and ctl['toggle_sprint'] and self.once('sprint'):
            self.sprint_latch = not self.sprint_latch
        elif k in (b['crouch'], b['crouch_alt']) and ctl['toggle_crouch'] and self.once('crouch'):
            self.crouch_latch = not self.crouch_latch
        elif k == b['mouse_lock']:
            mouse.locked = not mouse.locked
            self.hud.cross.enabled = mouse.locked
            if mouse.locked:
                self.skip_look = 3
            else:
                mouse.visible = True
        elif key in ('scroll up', 'scroll down'):
            g['fov'] = int(max(50, min(120, g['fov'] + (-3 if key == 'scroll up' else 3))))
            self.settings.dirty = True
            self.hud.toast('FOV: %d' % g['fov'], 0.8)

    # --------------------------------------------------------- respawn
    def begin_respawn(self):
        p = self.player
        self.reset_count += 1
        self.is_sprinting = self.crouching = self.sprint_latch = self.crouch_latch = self.flying = False
        p.vy = 0.0
        if (p.position - self.spawn).length() < 4.5:
            p.position = Vec3(self.spawn)
            p.grounded = False
            self.last_pos = Vec3(self.spawn)
            self.prev_y = p.y
            return
        self.respawning = True
        self.drag_speed = 8.0

    def respawn_update(self, dt):
        p = self.player
        p.vy = 0.0
        self.drag_speed = min(self.drag_speed + 35 * dt, 60)
        d = self.spawn - p.position
        dist = d.length()
        step = self.drag_speed * dt
        if dist <= max(step, 0.6):
            p.position = Vec3(self.spawn)
            p.vy, p.grounded, self.respawning = 0.0, False, False
            self.last_pos = Vec3(self.spawn)
            self.prev_y = p.y
            self.kick_v = -30.0
        else:
            p.position += d / dist * step

    # ------------------------------------------------------------ update
    def update(self):
        dt = min(time.dt, 0.1)
        self.t += dt
        self._screen_tick(dt)
        self.fps_acc += time.dt
        self.fps_frames += 1
        if self.fps_acc >= 1.0:
            self.fps_val = self.fps_frames / self.fps_acc
            if self.hud:
                self.hud.set_fps(self.fps_val)
            self.fps_acc, self.fps_frames = 0.0, 0
        if self.state == 'loading':
            self.loader_tick(dt)
            return
        if self.state == 'generating':
            self.gen_tick(dt)
            return
        ar = window.aspect_ratio
        if abs(ar - self.last_aspect) > 0.001:
            self.last_aspect = ar
            self.hud.layout(animate=False)
            self.ui.relayout()
        self.hud.tick(dt)
        self.apply_tod(dt)
        self.atk_cd = max(0.0, self.atk_cd - dt)
        if self.drag is not None:
            surf, lx, ly = self.drag
            if mouse.x != lx or mouse.y != ly:
                surf.pan(mouse.x - lx, mouse.y - ly)
                self.drag = (surf, mouse.x, mouse.y)
        pg = self.ui.current
        if pg is not None and hasattr(pg, 'sync'):
            pg.sync(dt)
        if self.state == 'menu':
            self.menu_update(dt)
            self.ui.update(dt)
        elif self.state in ('paused', 'map', 'items'):
            self.ui.update(dt)
        elif self.state == 'dead':
            self.ui.update(dt)
            self.mobs.update(dt, self.player)
            self.death_update(dt)
        elif self.state == 'playing':
            if self.ui.dialog:
                self.ui.update(dt)
            self.play_update(dt)

    def menu_update(self, dt):
        w = self.world
        cx, cz = w.spawn
        self.menu_t = (self.menu_t + dt * 0.06) % TAU
        ar = max(window.aspect_ratio, 0.1)
        nx, ny = max(-1.0, min(1.0, mouse.x / (ar / 2))), max(-1.0, min(1.0, mouse.y / 0.5))
        k = 1 - math.exp(-4 * dt)
        self.menu_par = Vec2(self.menu_par[0] + (nx - self.menu_par[0]) * k, self.menu_par[1] + (ny - self.menu_par[1]) * k)
        x, z = cx + math.cos(self.menu_t) * 26, cz + math.sin(self.menu_t) * 26
        y = max(w.ground(x, z), w.sea) + 9
        camera.position = Vec3(x, y, z)
        tx, ty, tz = cx + self.menu_par[0] * 3.5, w.ground(cx, cz) + 3 + self.menu_par[1] * 2.5, cz
        d = Vec3(tx - x, ty - y, tz - z)      # explicit yaw/pitch, roll is always 0 -> the view can never flip
        camera.rotation = Vec3(math.degrees(math.atan2(-d[1], math.hypot(d[0], d[2]))),
                               math.degrees(math.atan2(d[0], d[2])), 0)
        w.update(x, z, self.t, 0.008)

    def play_update(self, dt):
        p, w = self.player, self.world
        s = self.settings.d
        b, g, ctl = s['binds'], s['graphics'], s['controls']
        diff = self.cfg['difficulty']
        typing = self.cmd_open
        hk = (lambda k: 0) if typing else held
        if self.skip_look > 0:
            self.skip_look -= 1
        else:
            p.look()
        w.update(p.x, p.z, self.t, 0.006)
        self.life.update(dt, p)
        self.mobs.update(dt, p)
        if self.state != 'playing':
            return
        if typing:
            self.hud.show_cmd(';' + self.cmd_text, self.cmd_hints(self.cmd_text))
        if self.respawning:
            self.respawn_update(dt)
            self.camera_fx(dt, False, False, 0.0)
            self.stamina_hud(dt)
            return
        fwd = hk(b['forward']) - hk(b['back'])
        side = hk(b['right']) - hk(b['left'])
        moving, moving_forward = (fwd != 0 or side != 0), fwd > 0
        if self.flying and not self.can_fly():
            self.flying = False
        fly = self.flying
        in_water = p.swimming or (w.sea > -1000 and p.y < w.sea - 0.1)
        crouch_key = bool(hk(b['crouch']) or hk(b['crouch_alt']))
        if ctl['toggle_crouch']:
            want_crouch = self.crouch_latch
        else:
            self.crouch_latch = False
            want_crouch = crouch_key
        self.crouching = want_crouch and not fly and not in_water      # no crouching in water: crouch = dive
        can_sprint = (not self.exhausted) and self.stamina > 0
        if ctl['toggle_sprint']:
            want_sprint = self.sprint_latch
            if not moving_forward or self.crouching:
                self.sprint_latch = want_sprint = False
        else:
            self.sprint_latch = False
            want_sprint = bool(hk(b['sprint']))
        drain, regen = DIFF_DRAIN[diff], 1.0 / DIFF_DRAIN[diff]
        if fly:
            self.is_sprinting = False
            speed = 22.0 if hk(b['sprint']) else 11.0
        elif want_sprint and moving_forward and not self.crouching and can_sprint and not p.swimming:
            self.is_sprinting = True
            self.stamina = max(0.0, self.stamina - 28.0 * drain * dt)
            if self.stamina <= 0:
                self.exhausted, self.sprint_latch = True, False
            speed = 12.0
        else:
            self.is_sprinting = False
            if self.stamina < self.max_stamina:
                self.stamina = min(self.max_stamina, self.stamina + 22.0 * regen * dt)
                if self.exhausted and self.stamina >= self.max_stamina:
                    self.exhausted = False
            speed = 2.8 if self.crouching else 7.0
        speed *= self.speed_mult
        if not fly and in_water:
            speed *= 0.6
        target_h = 1.15 if self.crouching else 2.0
        p.height = p.height + (target_h - p.height) * min(1.0, 8 * dt) if g['smooth_animations'] else target_h
        wish = Vec3(0, 0, 0)
        if moving:
            wv = p.forward * fwd + p.right * side
            wish = Vec3(wv[0], 0, wv[2])
            if wish.length() > 0.001:
                wish = wish.normalized()
        self.jump_buffer = max(0.0, self.jump_buffer - dt)
        jump_held = bool(hk(b['jump']))
        want_jump = self.jump_buffer > 0 and p.grounded and not fly and not typing
        if want_jump:
            self.jump_buffer = 0.0
            self.jump_count += 1
            self.dirty = True
            if g['jump_effects']:
                self.kick_v += 30.0
        vert = (jump_held - (1 if crouch_key else 0)) * (2.0 if (fly and hk(b['sprint'])) else 1.0) * 9.0
        landed, entered = p.step(dt, wish, speed, want_jump, fly, vert, jump_held, crouch_key)
        if landed > 9 and g['jump_effects']:
            self.kick_v -= min(landed * 1.5, 40.0)
        if landed > 6:
            self.eye_lag -= min(landed * 0.02, 0.35)          # soft landing dip instead of a hard snap
            self.sfx.play('thud', min(1.0, landed / 18.0), 1.0)
        if landed > 20 and not fly:
            self.hurt_player((landed - 20) * 1.2, 'a fall')
        if entered:
            self.sfx.play('splash', 0.9, random.uniform(0.9, 1.1))
        self.camera_fx(dt, moving, True, landed)
        self.hud.water.enabled = w.sea > -1000 and (p.y + p.camera_pivot.y) < w.sea
        self.audio_tick(dt, moving, p)
        if self.is_sprinting and p.grounded and g['effects'] and not p.swimming:
            self.dust_timer -= dt
            if self.dust_timer <= 0:
                self.dust.spawn(p.position + p.back * 0.6 + Vec3(random.uniform(-0.3, 0.3), 0.1,
                                                                 random.uniform(-0.3, 0.3)))
                self.dust_timer = 0.07
        else:
            self.dust_timer = 0.0
        self.dust.update(dt)
        self.playtime += dt
        if p.grounded:
            d = (p.position - self.last_pos).length()
            if d > 0.02:
                self.distance_traveled += d
                self.dirty = True
        self.last_pos = Vec3(p.position)
        self.stamina_hud(dt)
        self.hurt_t += dt
        if self.health < self.max_health and self.hurt_t > 6.0:
            self.health = min(float(self.max_health), self.health + DIFF_REGEN[diff] * dt)
            self.hud.set_health(self.health, self.max_health)
        if self.cfg.get('debug'):
            self.dbg_t -= dt
            if self.dbg_t <= 0:
                self.dbg_t = 0.25
                self.hud.debug_txt.text = (
                    'SEED %s  MODE %s\nXYZ %.1f %.1f %.1f\nBIOME %s  CHUNKS %d  MOBS %d\nTIME %02d:%02d  FPS %d' %
                    (self.cfg.get('seed'), self.cfg.get('mode'), p.x, p.y, p.z, w.biome_at(p.x, p.z),
                     len(w.ents), len(self.mobs.list), int(self.tod), int(self.tod % 1 * 60), self.fps_val))
        if p.y < -80 or (w.sea > -1000 and p.y < w.sea - 60):
            self.begin_respawn()

    def audio_tick(self, dt, moving, p):
        sfx, w = self.sfx, self.world
        if moving and (p.grounded or p.swimming) and not self.flying:
            self.step_t -= dt
            if self.step_t <= 0:
                self.step_t = 0.32 if self.is_sprinting else (0.7 if self.crouching else 0.48)
                if p.swimming or p.y < w.sea - 0.1:
                    sfx.play('swim', 0.7, random.uniform(0.9, 1.1))
                else:
                    sfx.play('step%d' % random.randint(1, 3), 0.35 if self.crouching else 0.7,
                             random.uniform(0.9, 1.15))
        else:
            self.step_t = min(self.step_t, 0.1)
        self.amb_t -= dt
        if self.amb_t <= 0:
            self.amb_t = 0.4
            near = 0
            if w.sea > -1000:
                for r in (6.0, 14.0):
                    for q in range(8):
                        a = TAU * q / 8
                        if w.surface(p.x + math.cos(a) * r, p.z + math.sin(a) * r) < w.sea - 0.3:
                            near += 1
            sfx.water_vol(min(1.0, near / 6.0) * 0.55 + (0.4 if p.swimming else 0))
            sfx.loop_vol('wind', clampf((p.y - 15) / 35.0) * 0.5)
        night = self.day_f < 0.3
        self.night_t -= dt
        if self.night_t <= 0:
            self.night_t = random.uniform(4.0, 11.0)
            if night and not p.swimming:
                pick = random.choice(['cricket1', 'cricket2', 'cricket1', 'owl1', 'owl2'] +
                                     (['howl'] if self.cfg.get('life') else []))
                sfx.play(pick, random.uniform(0.25, 0.5), random.uniform(0.9, 1.1))
        self.bird_t -= dt
        if self.bird_t <= 0:
            self.bird_t = random.uniform(3.0, 9.0)
            if (not night and self.cfg.get('life') and self.cfg.get('mode') != 'Flat +' and not p.swimming and
                    w.biome_at(p.x, p.z) in ('Forest', 'Plains', 'Mountains', 'Tundra', 'Beach', 'Jungle', 'Savanna')):
                sfx.play('bird%d' % random.randint(1, 4), random.uniform(0.25, 0.6), random.uniform(0.85, 1.25))

    def stamina_hud(self, dt):
        self.sprint_linger = 0.25 if self.is_sprinting else max(0.0, self.sprint_linger - dt)
        self.hud.set_stamina_visible(self.is_sprinting or self.sprint_linger > 0)
        self.hud.set_stamina(self.stamina / self.max_stamina, self.exhausted)

    def camera_fx(self, dt, moving, normal, landed):
        p = self.player
        s = self.settings.d
        g, b = s['graphics'], s['binds']
        base = g['fov']
        target = base
        if held(b['zoom']) and not self.cmd_open:
            target = base * 0.47
        elif g['jump_effects']:
            if self.is_sprinting:
                target = base + 14
            elif self.crouching:
                target = base - 8
        self.fov_cur += (target - self.fov_cur) * (1 - math.exp(-7 * dt))
        # spring-damped FOV kick: smooth jump / landing punch, never an instant snap
        self.kick_v += (-60.0 * self.fov_kick - 11.0 * self.kick_v) * dt
        self.fov_kick += self.kick_v * dt
        camera.fov = max(30.0, min(130.0, self.fov_cur + self.fov_kick))
        gm = moving and p.grounded and normal
        self.bob_timer += dt * (12 if self.is_sprinting else (9 if gm else 2.5))
        want = 0.0
        if g['head_bob']:
            want = (0.06 if self.is_sprinting else 0.045) if gm else 0.012
        self.bob_intensity += (want - self.bob_intensity) * (1 - math.exp(-6 * dt))
        # eye smoothing: absorbs the tiny vertical steps of the faceted terrain
        dy = p.y - self.prev_y
        if p.grounded and abs(dy) < 0.9:
            self.eye_lag -= dy
        self.prev_y = p.y
        self.eye_lag = max(-0.8, min(0.8, self.eye_lag)) * math.exp(-12 * dt)
        p.camera_pivot.y = p.height + math.sin(self.bob_timer) * self.bob_intensity + self.eye_lag
        p.camera_pivot.x = math.cos(self.bob_timer * 0.5) * self.bob_intensity * 0.5


if __name__ == '__main__':
    director = Director()
    splash_report(42, 'Loading world')
    app.run()
