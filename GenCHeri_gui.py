#!/usr/bin/env python3
"""tkinter front end for the CHERI header generator.

  1. "Generate headers"  -> writes general.h + cheri_utils.h into a staging folder (generate_headers)
  2. "Port & Build"      -> copies them into the riscv-vp tree (replacing the old ones) and runs
                            `cmake -D<option>=ON/OFF ..` + `make` in <vp>/build

Run:  python3 GenCHeri_gui.py          (needs python3-tk:  sudo apt install python3-tk)
Files needed next to it: gen_config.py gen_general.py gen_utils.py helper.py GenCHeri.py port_build.py
"""
import json
import os
import queue
import re
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter import font as tkfont

import gen_config as C
from GenCHeri import generate_headers
from port_build import port_to, run_build

#Sayak: places inside the riscv-vp tree (change here if the folder layout changes)
DEFAULT_VP_DIR = "~/Documents/riscv-vp/vp"
GEN_DIR_IN_VP = os.path.join("src", "core", "GenCHERI")   # general.h goes here
TEMPLATE_DIR_FMT = "Template{n}"                           # cheri_utils.h goes into GEN_DIR/Template<n>
BUILD_DIR_IN_VP = "build"
GENERAL_FILE, UTILS_FILE = "general.h", "cheri_utils.h"
DEFAULT_STAGING = "~/cheri_generated"
SETTINGS_FILE = os.path.expanduser("~/.cheri_gui.json")

#Sayak: used when <vp>/CMakeLists.txt cannot be parsed
FALLBACK_OPTIONS = [
    ("USE_SYSTEM_SYSTEMC", "Use the systemc library installed on the system", False),
    ("USE_PURE_CAPABILITY", "Use pure capability mode", False),
    ("USE_TESTRIG", "Use the testrig mode", False),
    ("USE_NOTAGROOT", "Use no tag root", False),
    ("USE_RISCV_VP", "Use the RISCV VP", False),
    ("USE_QEMU", "Use QEMU", False),
]
OPTION_RE = re.compile(r'option\(\s*([A-Za-z0-9_]+)\s+"([^"]*)"\s*(ON|OFF)?\s*\)')

HERE = os.path.dirname(os.path.abspath(__file__))
LOGO_FILE = os.path.join(HERE, "GenCHERI_logo.jpg")   #Sayak: logo shown in the header / window icon
LOGO_HEIGHT = 80


def logo_colours(img):
    """(accent, darker accent) taken from the most common saturated, not-too-light colour of the logo."""
    default = ("#2b6cb0", "#1e4e86")
    if img is None:
        return default
    try:
        import colorsys
        small = img.convert("RGB").resize((64, 64))
        best, score = None, 0
        for count, (r, g, b) in small.getcolors(4096):
            h, l, sat = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
            if 0.18 < l < 0.75 and sat > 0.25 and count * sat > score:
                best, score = (r, g, b, h, l, sat), count * sat
        if best is None:
            return default
        r, g, b, h, l, sat = best
        l = min(l, 0.5)    # white button text must stay readable
        c1 = colorsys.hls_to_rgb(h, l, sat)
        c2 = colorsys.hls_to_rgb(h, max(l - 0.12, 0.12), sat)
        hexc = lambda c: "#%02x%02x%02x" % tuple(int(x * 255) for x in c)
        return hexc(c1), hexc(c2)
    except Exception:
        return default



def parse_options(vp_dir):
    """option(NAME "text" ON|OFF) lines of <vp>/CMakeLists.txt (commented lines ignored)."""
    path = os.path.join(os.path.expanduser(vp_dir), "CMakeLists.txt")
    try:
        with open(path) as fh:
            text = "\n".join(l for l in fh if not l.lstrip().startswith("#"))
    except OSError:
        return None
    found = [(n, d, v == "ON") for n, d, v in OPTION_RE.findall(text)]
    return found or None


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CHERI header generator")
        self.minsize(820, 820)
        self.geometry("940x960")
        self.q = queue.Queue()
        self.busy = False
        self.generated = None          # (general_path, utils_path, template) of the last generation
        self.opt_vars = {}
        self.opt_desc = {}

        v = self.v = {
            "template": tk.StringVar(value="1"), "compressed": tk.BooleanVar(value=False),
            #Sayak: default values for the three templates are set here perms bits are now 1 less
            "p": tk.StringVar(value="11"), "o": tk.StringVar(value="3"), "f": tk.StringVar(value="1"),
            "bound": tk.StringVar(value="64"), "t": tk.StringVar(value="1"),
            "order": tk.StringVar(value=C.DEFAULT_ORDER),
            "staging": tk.StringVar(value=DEFAULT_STAGING),
            "vp": tk.StringVar(value=DEFAULT_VP_DIR),
            "backup": tk.BooleanVar(value=True), "jobs": tk.StringVar(value=str(os.cpu_count() or 1)),
        }
        self._load_settings()
        self._load_logo()
        self._theme()
        self._build_ui()
        for k in ("template", "p", "o", "f", "bound", "t"):
            v[k].trace_add("write", lambda *_: self.refresh())
        v["vp"].trace_add("write", lambda *_: self.refresh_vp())
        self.refresh()
        self.refresh_vp()
        self.after(100, self._poll)
        self.protocol("WM_DELETE_WINDOW", self._close)

    def _load_logo(self):
        """Needs Pillow for the .jpg (pip install pillow); without it the tool simply runs without the logo."""
        self.logo_img = self.logo_tk = None
        try:
            from PIL import Image, ImageTk
            img = Image.open(LOGO_FILE)
            self.logo_img = img
            w = max(1, round(img.width * LOGO_HEIGHT / img.height))
            self.logo_tk = ImageTk.PhotoImage(img.convert("RGBA").resize((w, LOGO_HEIGHT), Image.LANCZOS))
            self.iconphoto(True, ImageTk.PhotoImage(img.convert("RGBA").resize((64, 64), Image.LANCZOS)))
        except Exception:
            self.logo_img = self.logo_tk = None

    # ------------------------------------------------------------------ theme
    def _theme(self):
        """Colours come from the logo (dominant saturated colour), so the tool matches whatever logo is used."""
        self.accent, self.accent_dark = logo_colours(self.logo_img)
        self.BG, self.CARD, self.FG, self.MUTED, self.LINE = "#f3f5f9", "#ffffff", "#1d2433", "#6b7385", "#dfe3ec"
        fams = set(tkfont.families())
        fam = next((f for f in ("SF Pro Text", "Helvetica Neue", "Segoe UI", "Inter", "Ubuntu", "DejaVu Sans") if f in fams), "TkDefaultFont")
        self.F = (fam, 10); self.FB = (fam, 10, "bold"); self.FH = (fam, 20, "bold"); self.FS = (fam, 11, "bold")
        self.FM = ("Menlo" if "Menlo" in fams else "Consolas" if "Consolas" in fams else "DejaVu Sans Mono", 10)
        st = self.style = ttk.Style(self)
        st.theme_use("clam")
        self.configure(bg=self.BG)
        st.configure(".", font=self.F, background=self.CARD, foreground=self.FG, fieldbackground=self.CARD,
                     bordercolor=self.LINE, lightcolor=self.CARD, darkcolor=self.CARD, troughcolor=self.BG)
        st.configure("TFrame", background=self.CARD)
        st.configure("Page.TFrame", background=self.BG)
        st.configure("TLabel", background=self.CARD, foreground=self.FG)
        st.configure("Muted.TLabel", foreground=self.MUTED)
        st.configure("Info.TLabel", foreground=self.accent_dark, background=self.CARD)
        st.configure("Card.TLabelframe", background=self.CARD, bordercolor=self.LINE, relief="solid", borderwidth=1, padding=10)
        st.configure("Card.TLabelframe.Label", background=self.CARD, foreground=self.accent_dark, font=self.FS)
        st.configure("TEntry", padding=5, bordercolor=self.LINE)
        st.configure("TSpinbox", padding=4, arrowsize=12, bordercolor=self.LINE)
        st.configure("TCombobox", padding=4, arrowsize=12, bordercolor=self.LINE)
        st.map("TEntry", bordercolor=[("focus", self.accent)])
        st.map("TSpinbox", bordercolor=[("focus", self.accent)])
        st.map("TCombobox", bordercolor=[("focus", self.accent)], fieldbackground=[("readonly", self.CARD)])
        st.configure("TCheckbutton", background=self.CARD, focuscolor=self.CARD)
        st.map("TCheckbutton", background=[("active", self.CARD)])
        st.configure("TButton", padding=(12, 6), background="#eef0f6", bordercolor=self.LINE, focuscolor="#eef0f6")
        st.map("TButton", background=[("active", "#e2e6f0"), ("disabled", "#f3f4f8")], foreground=[("disabled", "#a0a6b5")])
        st.configure("Accent.TButton", background=self.accent, foreground="white", font=self.FB,
                     padding=(18, 8), bordercolor=self.accent, focuscolor=self.accent)
        st.map("Accent.TButton", background=[("active", self.accent_dark), ("disabled", "#b9bfce")],
               foreground=[("disabled", "white")], bordercolor=[("active", self.accent_dark)])
        st.configure("TMenubutton", padding=(10, 6), background=self.CARD, bordercolor=self.LINE, arrowcolor=self.accent_dark)
        st.map("TMenubutton", background=[("active", "#f3f5f9")])
        st.configure("Vertical.TScrollbar", background="#c9cedb", troughcolor="#1e2433", bordercolor="#1e2433", arrowcolor="white")

    def _header(self, parent):
        bar = tk.Frame(parent, bg="white", highlightthickness=0)
        bar.pack(fill="x")
        inner = tk.Frame(bar, bg="white")
        inner.pack(pady=10)
        if self.logo_img is not None:
            tk.Label(inner, image=self.logo_tk, bg="white", bd=0).pack(side="left", padx=(0, 14))
        txt = tk.Frame(inner, bg="white")
        txt.pack(side="left")
        tk.Label(txt, text="GenCHERI", font=self.FH, fg=self.accent_dark, bg="white").pack(anchor="center")
        tk.Label(txt, text="CHERI capability header generator  \u2022  port & build for riscv-vp",
                 font=self.F, fg=self.MUTED, bg="white").pack(anchor="center")
        tk.Frame(parent, bg=self.accent, height=3).pack(fill="x")

    def _text(self, parent, height):
        t = tk.Text(parent, height=height, width=28, font=self.FM, relief="flat", bd=0, highlightthickness=1,
                    highlightbackground=self.LINE, highlightcolor=self.accent, padx=6, pady=4, bg="white",
                    wrap="word")
        return t

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        pad = dict(padx=6, pady=4)
        self._header(self)
        root = ttk.Frame(self, padding=14, style="Page.TFrame")
        root.pack(fill="both", expand=True)

        g = ttk.LabelFrame(root, text="  1  Generate headers  ", padding=12, style="Card.TLabelframe")
        g.pack(fill="x")
        for c in (1, 3, 5):
            g.columnconfigure(c, weight=1, uniform="c")

        ttk.Label(g, text="Template").grid(row=0, column=0, sticky="w", **pad)
        ttk.Combobox(g, textvariable=self.v["template"], values=["1", "2", "3"], width=8,
                     state="readonly").grid(row=0, column=1, sticky="w", **pad)
        ttk.Checkbutton(g, text="Compressed instructions on", variable=self.v["compressed"]).grid(
            row=0, column=2, columnspan=2, sticky="w", **pad)
        ttk.Label(g, text="Field order (MSB\u2192LSB)").grid(row=0, column=4, sticky="e", **pad)
        ttk.Combobox(g, textvariable=self.v["order"], values=C.ORDERS, width=8, state="readonly").grid(
            row=0, column=5, sticky="w", **pad)

        self.spins = {}
        for i, (key, label) in enumerate((("p", "Perm bits"), ("o", "Otype bits"), ("f", "Flag bits"))):
            ttk.Label(g, text=label).grid(row=1, column=2 * i, sticky="w", **pad)
            sb = ttk.Spinbox(g, textvariable=self.v[key], width=8, from_=0, to=99)
            sb.grid(row=1, column=2 * i + 1, sticky="w", **pad)
            self.spins[key] = sb
        self.lbl_extra = ttk.Label(g, text="")
        self.lbl_extra.grid(row=2, column=0, sticky="w", **pad)
        self.sb_extra = ttk.Spinbox(g, textvariable=self.v["bound"], width=8, from_=1, to=64)
        self.sb_extra.grid(row=2, column=1, sticky="w", **pad)
        self.lbl_info = ttk.Label(g, text="", style="Info.TLabel")
        self.lbl_info.grid(row=2, column=2, columnspan=4, sticky="w", **pad)

        ttk.Label(g, text="User-defined perms").grid(row=3, column=0, sticky="nw", **pad)
        self.txt_perm = self._text(g, 3)
        self.txt_perm.grid(row=3, column=1, columnspan=2, sticky="ew", **pad)
        ttk.Label(g, text="User-defined otypes").grid(row=3, column=3, sticky="nw", **pad)
        self.txt_otype = self._text(g, 3)
        self.txt_otype.grid(row=3, column=4, columnspan=2, sticky="ew", **pad)
        self.lbl_names = ttk.Label(g, text="", style="Muted.TLabel")
        self.lbl_names.grid(row=4, column=0, columnspan=6, sticky="w", **pad)

        ttk.Label(g, text="Staging folder").grid(row=5, column=0, sticky="w", **pad)
        ttk.Entry(g, textvariable=self.v["staging"]).grid(row=5, column=1, columnspan=4, sticky="ew", **pad)
        ttk.Button(g, text="Browse\u2026", command=lambda: self._browse("staging")).grid(row=5, column=5, sticky="e", **pad)
        self.btn_gen = ttk.Button(g, text="\u2699  Generate headers", style="Accent.TButton", command=self.on_generate)
        self.btn_gen.grid(row=6, column=0, columnspan=2, sticky="w", padx=6, pady=(10, 2))
        self.lbl_gen = ttk.Label(g, text="Nothing generated yet.", style="Muted.TLabel")
        self.lbl_gen.grid(row=6, column=2, columnspan=4, sticky="w", padx=6, pady=(10, 2))

        b = ttk.LabelFrame(root, text="  2  Port into riscv-vp and build  ", padding=12, style="Card.TLabelframe")
        b.pack(fill="x", pady=(12, 0))
        b.columnconfigure(1, weight=1)
        ttk.Label(b, text="VP folder").grid(row=0, column=0, sticky="w", **pad)
        ttk.Entry(b, textvariable=self.v["vp"]).grid(row=0, column=1, sticky="ew", **pad)
        ttk.Button(b, text="Browse\u2026", command=lambda: self._browse("vp")).grid(row=0, column=2, **pad)
        self.lbl_dest = ttk.Label(b, text="", style="Muted.TLabel", justify="left", wraplength=0)
        self.lbl_dest.grid(row=1, column=0, columnspan=3, sticky="w", **pad)

        ttk.Label(b, text="CMake options").grid(row=2, column=0, sticky="w", **pad)
        self.mb = ttk.Menubutton(b, text="Select options \u25be", direction="below")
        self.mb.grid(row=2, column=1, sticky="w", **pad)
        self.menu = tk.Menu(self.mb, tearoff=False, font=self.F, activebackground=self.accent, activeforeground="white")
        self.mb["menu"] = self.menu
        self.lbl_optsrc = ttk.Label(b, text="", style="Muted.TLabel")
        self.lbl_optsrc.grid(row=2, column=2, sticky="e", **pad)

        ttk.Label(b, text="Command").grid(row=3, column=0, sticky="nw", **pad)
        self.lbl_cmd = tk.Label(b, text="", font=self.FM, bg="#f3f5f9", fg=self.FG, justify="left", anchor="w", padx=10, pady=6)
        self.lbl_cmd.grid(row=3, column=1, columnspan=2, sticky="ew", **pad)

        row = ttk.Frame(b)
        row.grid(row=4, column=0, columnspan=3, sticky="w", padx=6, pady=(8, 2))
        ttk.Checkbutton(row, text="Keep .bak of replaced files", variable=self.v["backup"]).pack(side="left", padx=(0, 16))
        ttk.Label(row, text="make -j").pack(side="left")
        ttk.Spinbox(row, textvariable=self.v["jobs"], from_=1, to=64, width=4).pack(side="left", padx=(4, 18))
        self.btn_build = ttk.Button(row, text="\u25b6  Port & Build", style="Accent.TButton", command=self.on_port_build)
        self.btn_build.pack(side="left")
        self.btn_port = ttk.Button(row, text="Port only", command=lambda: self.on_port_build(build=False))
        self.btn_port.pack(side="left", padx=8)

        lf = ttk.LabelFrame(root, text="  Log  ", padding=8, style="Card.TLabelframe")
        lf.pack(fill="both", expand=True, pady=(12, 0))
        self.log = tk.Text(lf, height=7, state="disabled", font=self.FM, wrap="none", bg="#1e2433", fg="#d7dcea",
                           insertbackground="white", relief="flat", bd=0, padx=10, pady=8)
        sy = ttk.Scrollbar(lf, command=self.log.yview)
        self.log.configure(yscrollcommand=sy.set)
        sy.pack(side="right", fill="y")
        self.log.pack(fill="both", expand=True)
        self.log.tag_configure("ok", foreground="#7ee2a8")
        self.log.tag_configure("err", foreground="#ff8b8b")
        self.log.tag_configure("cmd", foreground="#8ab4ff")

    # ------------------------------------------------------------------ helpers
    def _int(self, key):
        try:
            return int(self.v[key].get())
        except ValueError:
            return None

    def _set_spin(self, key, lo, hi):
        sb, val = self.spins.get(key, None) or {"bound": self.sb_extra, "t": self.sb_extra}[key], self._int(key)
        sb.configure(from_=lo, to=hi)
        if val is None or val < lo:
            self.v[key].set(str(lo))
        elif val > hi:
            self.v[key].set(str(hi))

    def _names(self, widget):
        return [n for n in re.split(r"[\s,;]+", widget.get("1.0", "end")) if n]

    def _browse(self, key):
        d = filedialog.askdirectory(initialdir=os.path.expanduser(self.v[key].get()) if os.path.isdir(
            os.path.expanduser(self.v[key].get())) else os.path.expanduser("~"))
        if d:
            self.v[key].set(d)

    def say(self, text):
        self.q.put(("log", text))

    def _append(self, text):
        self.log.configure(state="normal")
        tag = ("err" if text.startswith(("===  FAILED", "=== FAILED", "Port failed", "Generate failed")) or "failed" in text
               else "ok" if text.startswith(("=== Build", "=== Ported", "Wrote", "Ported")) else "cmd" if text.startswith("$ ") else "")
        self.log.insert("end", text + "\n", tag)
        self.log.see("end")
        self.log.configure(state="disabled")

    # ------------------------------------------------------------------ dynamic limits
    def refresh(self):
        """Recompute every allowed range from the current choices (same rules as the terminal version)."""
        if getattr(self, "_busy_refresh", False):
            return
        self._busy_refresh = True
        try:
            t = self._int("template")
            if t is None:
                return
            for _ in range(2):     # a change in P can shrink O and F; settle in two passes
                lo, hi = C.perm_range(t); self._set_spin("p", lo, hi)
                p = self._int("p")
                lo, hi = C.otype_range(t, p); self._set_spin("o", lo, hi)
                o = self._int("o")
                lo, hi = C.flag_range(t, p, o); self._set_spin("f", lo, hi)
            f = self._int("f")
            if t == 3:
                self.lbl_extra.configure(text="Bound bits (1-64)")
                self.sb_extra.configure(textvariable=self.v["bound"], from_=1, to=C.T3_BOUND_MAX)
                raw = self._int("bound")
                if raw is None or not 1 <= raw <= 64:
                    self.v["bound"].set("64"); raw = 64
                bw, mw, sizes = C.bound_and_meta(3, p, o, f, raw)
                self.lbl_info.configure(text=f"bound = {bw} bits (rounded up); storage P{sizes[0]}+O{sizes[1]}+F{sizes[2]}"
                                             f"+B{sizes[3]} = {mw} bits metadata")
            else:
                bw, mw, _ = C.bound_and_meta(t, p, o, f)
                spare, tmax = C.t_range(t, bw)
                self.lbl_extra.configure(text=f"T bits (1-{tmax})")
                self.sb_extra.configure(textvariable=self.v["t"], from_=1, to=tmax)
                tb = self._int("t")
                if tb is None or tb < 1: self.v["t"].set("1"); tb = 1
                if tb > tmax: self.v["t"].set(str(tmax)); tb = tmax
                x, bb, left = C.t_split(tb, spare)
                self.lbl_info.configure(text=f"bound = {bw} bits, metadata = {mw} bits, spare = {spare}; "
                                             f"T = {tb}, B = {bb}, {left} wasted")
            self.lbl_names.configure(
                text=(f"Perm names: up to {max(p - C.HW_PERM_COUNT, 0)}   |   Otype names: up to {(1 << o) - 3}"))
            for w, on in ((self.txt_perm, p > C.PERM_MIN), (self.txt_otype, o > C.OTYPE_MIN)):
                w.configure(state="normal" if on else "disabled", bg="white" if on else "#eef0f4")
        finally:
            self._busy_refresh = False

    # ------------------------------------------------------------------ stage 1
    def on_generate(self):
        try:
            t, p, o, f = (self._int(k) for k in ("template", "p", "o", "f"))
            cfg = C.build_cfg(
                t, self.v["compressed"].get(), p, o, f, self.v["order"].get(),
                perm_names=self._names(self.txt_perm) if p > C.PERM_MIN else [],
                otype_names=self._names(self.txt_otype) if o > C.OTYPE_MIN else [],
                bound_bits=self._int("bound") if t == 3 else None,
                t_bits=self._int("t") if t in (1, 2) else None,
                general_name=GENERAL_FILE)
            gp, up = generate_headers(cfg, self.v["staging"].get(), GENERAL_FILE, UTILS_FILE)
        except (ValueError, OSError) as e:
            messagebox.showerror("Generate failed", str(e))
            self._append(f"Generate failed: {e}")
            return
        self.generated = (gp, up, t)
        self.lbl_gen.configure(text=f"Generated Template {t} headers in {os.path.dirname(gp)}")
        self._append(f"Wrote {gp}\nWrote {up}")
        for k in cfg["order"]:
            self._append(f"  {k}: [{cfg['pos'][k][1]}:{cfg['pos'][k][0]}]")
        self.refresh_vp()

    # ------------------------------------------------------------------ stage 2
    def vp_paths(self):
        vp = os.path.abspath(os.path.expanduser(self.v["vp"].get()))
        gen = os.path.join(vp, GEN_DIR_IN_VP)
        t = self.generated[2] if self.generated else self._int("template")
        return vp, gen, os.path.join(gen, TEMPLATE_DIR_FMT.format(n=t)), os.path.join(vp, BUILD_DIR_IN_VP)

    def refresh_vp(self):
        vp, gen, tdir, bdir = self.vp_paths()
        short = lambda q: q.replace(os.path.expanduser("~"), "~", 1)
        self.lbl_dest.configure(text=f"{GENERAL_FILE}  →  {short(gen)}\n{UTILS_FILE}  →  {short(tdir)}\nbuild in  {short(bdir)}")
        opts = parse_options(vp)
        src = "from CMakeLists.txt" if opts else "built-in list (CMakeLists.txt not found)"
        self._set_options(opts or FALLBACK_OPTIONS, src)
        self.refresh_cmd()

    def _set_options(self, opts, src):
        old = dict(getattr(self, '_saved_opts', {}))
        old.update({n: v.get() for n, v in self.opt_vars.items()})
        self.menu.delete(0, "end")
        self.opt_vars, self.opt_desc = {}, {}
        for name, desc, default in opts:
            var = tk.BooleanVar(value=old.get(name, default))
            var.trace_add("write", lambda *_: self.refresh_cmd())
            self.opt_vars[name], self.opt_desc[name] = var, desc
            self.menu.add_checkbutton(label=f"{name}  -  {desc}", variable=var)
        self.lbl_optsrc.configure(text=f"options {src}")

    def cmake_args(self):
        # every option is passed explicitly, otherwise a value left in CMakeCache.txt from an earlier run sticks
        return [f"-D{n}={'ON' if v.get() else 'OFF'}" for n, v in self.opt_vars.items()]

    def refresh_cmd(self):
        on = [n for n, v in self.opt_vars.items() if v.get()]
        self.mb.configure(text=(", ".join(on) if on else "no option selected") + " ▾")
        self.lbl_cmd.configure(text="cmake " + " ".join(self.cmake_args()) + " ..\nmake")

    def on_port_build(self, build=True):
        if self.busy:
            return
        if not self.generated:
            messagebox.showinfo("Nothing to port", "Generate the headers first (step 1).")
            return
        gp, up, t = self.generated
        vp, gen, tdir, bdir = self.vp_paths()
        if not os.path.isdir(vp):
            messagebox.showerror("VP folder", f"Folder not found:\n{vp}")
            return
        if not messagebox.askyesno("Confirm", f"Replace {GENERAL_FILE} in\n{gen}\nand {UTILS_FILE} in\n{tdir}"
                                   + ("\n\nand then run cmake + make?" if build else "?")):
            return
        args, jobs, backup = self.cmake_args(), self._int("jobs"), self.v["backup"].get()
        self.busy = True
        for w in (self.btn_build, self.btn_port, self.btn_gen):
            w.state(["disabled"])
        threading.Thread(target=self._worker, args=(gp, up, gen, tdir, bdir, args, jobs, backup, build), daemon=True).start()

    def _worker(self, gp, up, gen, tdir, bdir, args, jobs, backup, build):
        ok = False
        try:
            copied, backups = port_to([(gp, gen), (up, tdir)], backup=backup)
            for c in copied:
                self.say(f"Ported {c}")
            for bk in backups:
                self.say(f"  (previous version saved as {bk})")
            ok = run_build(bdir, args, jobs, log=self.say) if build else True
        except OSError as e:
            self.say(f"Port failed: {e}")
        self.q.put(("done", ok if build else None))

    def _poll(self):
        try:
            while True:
                kind, val = self.q.get_nowait()
                if kind == "log":
                    self._append(val)
                else:
                    self.busy = False
                    for w in (self.btn_build, self.btn_port, self.btn_gen):
                        w.state(["!disabled"])
                    self._append({True: "=== Build finished ===", False: "=== FAILED ===", None: "=== Ported ==="}[val])
        except queue.Empty:
            pass
        self.after(100, self._poll)

    # ------------------------------------------------------------------ settings
    def _load_settings(self):
        try:
            with open(SETTINGS_FILE) as fh:
                d = json.load(fh)
            for k in ("staging", "vp", "jobs"):
                if k in d:
                    self.v[k].set(d[k])
            self.v["backup"].set(d.get("backup", True))
            self._saved_opts = d.get("options", {})
        except (OSError, ValueError):
            self._saved_opts = {}

    def _close(self):
        try:
            with open(SETTINGS_FILE, "w") as fh:
                json.dump({"staging": self.v["staging"].get(), "vp": self.v["vp"].get(), "jobs": self.v["jobs"].get(),
                           "backup": self.v["backup"].get(),
                           "options": {n: v.get() for n, v in self.opt_vars.items()}}, fh, indent=1)
        except OSError:
            pass
        self.destroy()


if __name__ == "__main__":
    App().mainloop()