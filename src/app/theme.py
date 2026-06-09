"""Shared theme: an elegant true-black dashboard look + chart palette."""

from __future__ import annotations

# Palette — muted, professional "trading terminal" tones on deep black.
# Deeper/desaturated greens & reds read as finance, not cartoon.
ACCENT = "#7c6cf0"      # refined indigo
ACCENT_2 = "#3aa8c9"    # steel cyan
GOLD = "#d9a441"        # muted amber
OK = "#2fa37a"          # emerald (gains) — deep, not neon
BAD = "#c75d6a"         # rose (losses) — muted, not candy red
NEUTRAL = "#5b6577"     # slate (flat)
SERIES = ["#7c6cf0", "#3aa8c9", "#d9a441", "#2fa37a", "#b06ab3",
          "#5b8def", "#9b8cf5", "#c98a5e"]

CSS = """
<style>
/* ---- elegant true-black base ---- */
.stApp {
  background:
    radial-gradient(1100px 600px at 12% -10%, rgba(139,109,255,.10), transparent 60%),
    radial-gradient(900px 500px at 100% 0%, rgba(34,211,238,.07), transparent 55%),
    #08080c;
}
section.main > div { padding-top: .6rem; }
#MainMenu, footer, header { visibility: hidden; }
.block-container { max-width: 1520px; }

/* sidebar darker than canvas */
section[data-testid="stSidebar"] {
  background: #050507;
  border-right: 1px solid rgba(255,255,255,.06);
}

/* ---- hero ---- */
.hero {
  position: relative; overflow: hidden;
  background: linear-gradient(135deg, rgba(139,109,255,.16), rgba(34,211,238,.06) 60%, transparent);
  border: 1px solid rgba(139,109,255,.28);
  border-radius: 18px; padding: 22px 28px; margin-bottom: 16px;
  box-shadow: 0 0 0 1px rgba(0,0,0,.4), 0 18px 50px -25px rgba(139,109,255,.5);
}
.hero h1 { margin:0; font-size:27px; font-weight:800; letter-spacing:-.4px;
  color:#f8fafc; }
.hero p { margin:7px 0 0; color:#9aa4b2; font-size:13.5px; max-width: 760px; }
.hero .pill-row { display:flex; flex-wrap:wrap; gap:8px; margin-top:14px; }
.hero .pill { display:inline-flex; align-items:center; padding:4px 12px;
  border-radius:999px; font-size:11px; font-weight:700; letter-spacing:.3px;
  background: rgba(255,255,255,.04); color:#c7b8ff; border:1px solid rgba(139,109,255,.3); }
.hero .pill.live { background: rgba(52,211,153,.12); color:#6ee7b7;
  border-color: rgba(52,211,153,.4); }
.hero .pill.live .dot { display:inline-block; width:7px; height:7px; border-radius:50%;
  background:#34d399; margin-right:6px; box-shadow:0 0 0 0 rgba(52,211,153,.6);
  animation: pulse 1.8s infinite; }
@keyframes pulse {
  0% { box-shadow:0 0 0 0 rgba(52,211,153,.55); }
  70% { box-shadow:0 0 0 7px rgba(52,211,153,0); }
  100% { box-shadow:0 0 0 0 rgba(52,211,153,0); }
}

/* ---- KPI cards ---- */
.kpi {
  background: linear-gradient(180deg, rgba(255,255,255,.025), rgba(255,255,255,0));
  border: 1px solid rgba(255,255,255,.07);
  border-top: 2px solid var(--c, #8b6dff);
  border-radius: 14px; padding: 15px 17px; height: 100%;
  box-shadow: 0 10px 30px -22px rgba(0,0,0,.9);
}
.kpi .label { color:#7c8696; font-size:10.5px; font-weight:700; letter-spacing:.8px;
  text-transform:uppercase; }
.kpi .value { color:#f8fafc; font-size:26px; font-weight:800; margin-top:5px;
  line-height:1.05; font-variant-numeric: tabular-nums; }
.kpi .sub { color:#8b95a4; font-size:11.5px; margin-top:4px; }
.kpi .up { color:#3fb98c; } .kpi .down { color:#d4727e; }

/* ---- section titles ---- */
.sec { font-size:14.5px; font-weight:800; color:#eef2f7; margin:4px 0 6px;
  display:flex; align-items:center; gap:9px; }
.sec .tag { font-size:10px; font-weight:800; color:#0a0a0f; letter-spacing:.6px;
  text-transform:uppercase; background:#8b6dff; padding:2px 8px; border-radius:6px; }
.muted { color:#7c8696; font-size:12px; }

/* chart card container */
div[data-testid="stVerticalBlockBorderWrapper"] {
  background: rgba(255,255,255,.015);
  border-radius: 14px;
}

/* ---- tabs ---- */
button[data-baseweb="tab"] { font-weight:800; font-size:14px; color:#7c8696; }
button[data-baseweb="tab"][aria-selected="true"] { color:#c7b8ff; }
div[data-baseweb="tab-highlight"] { background:#8b6dff; }

/* primary button glow */
.stButton button[kind="primary"], .stFormSubmitButton button {
  background: linear-gradient(135deg, #8b6dff, #6d4dff);
  border: none; font-weight:700;
  box-shadow: 0 8px 24px -10px rgba(139,109,255,.8);
}
.stButton button[kind="primary"]:hover { filter: brightness(1.08); }

.stDataFrame { border-radius: 10px; }
[data-testid="stMetricValue"] { font-variant-numeric: tabular-nums; }
</style>
"""
