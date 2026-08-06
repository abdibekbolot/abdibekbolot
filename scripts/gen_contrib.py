#!/usr/bin/env python3
"""Render a GitHub contribution graph as a terminal-styled SVG."""
import json, os, sys, datetime, urllib.request

USER  = os.environ.get("GH_USER", "abdibekbolot")
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
OUT   = os.environ.get("OUT", "contrib.svg")

QUERY = """
query($login:String!){
  user(login:$login){
    contributionsCollection{
      contributionCalendar{
        totalContributions
        weeks{ contributionDays{ date contributionCount } }
      }
    }
  }
}"""

def fetch():
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": USER}}).encode(),
        headers={"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json",
                 "User-Agent": USER},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    if "errors" in data:
        sys.exit(f"GraphQL error: {data['errors']}")
    return data["data"]["user"]["contributionsCollection"]["contributionCalendar"]

def streaks(days):
    """longest run of consecutive active days, and the current run"""
    longest = run = 0
    for d in days:
        run = run + 1 if d["contributionCount"] > 0 else 0
        longest = max(longest, run)
    tail = list(reversed(days))
    if tail and tail[0]["contributionCount"] == 0:
        tail = tail[1:]                     # today may not have started yet
    cur = 0
    for d in tail:
        if d["contributionCount"] == 0:
            break
        cur += 1
    return cur, longest

# ---------- layout ----------
CELL, GAP = 11, 3
PITCH = CELL + GAP
PAD_L = 20

def build(cal):
    weeks = cal["weeks"]
    days  = [d for w in weeks for d in w["contributionDays"]]
    total = cal["totalContributions"]
    cur, longest = streaks(days)
    peak = max((d["contributionCount"] for d in days), default=0)
    active = sum(1 for d in days if d["contributionCount"] > 0)

    grid_x = PAD_L + 26
    grid_y = 118
    n = len(weeks)
    grid_w = n * PITCH
    W = grid_x + grid_w + 20

    # month labels
    months, seen = [], set()
    for wi, w in enumerate(weeks):
        d0 = w["contributionDays"][0]["date"]
        y, m, _ = d0.split("-")
        key = (y, m)
        if key not in seen and int(d0.split("-")[2]) <= 7:
            seen.add(key)
            months.append((wi, datetime.date(int(y), int(m), 1).strftime("%b")))

    def level(c):
        if c == 0: return 0
        if peak <= 1: return 4
        r = c / peak
        return 1 if r <= .15 else 2 if r <= .35 else 3 if r <= .65 else 4

    cells = []
    for wi, w in enumerate(weeks):
        for d in w["contributionDays"]:
            di = datetime.date.fromisoformat(d["date"]).isoweekday() % 7
            x = grid_x + wi*PITCH
            yy = grid_y + di*PITCH
            lv = level(d["contributionCount"])
            delay = 0.6 + wi * 0.012
            cells.append(
                f'<rect x="{x}" y="{yy}" width="{CELL}" height="{CELL}" rx="2.5" class="l{lv}">'
                f'<animate attributeName="opacity" values="0;0;1;1" keyTimes="0;{delay/14:.4f};{(delay+0.25)/14:.4f};1" dur="14s" repeatCount="indefinite"/>'
                f'</rect>')

    mlabels = "".join(
        f'<text x="{grid_x + wi*PITCH}" y="{grid_y-8}" class="ax">{name}</text>'
        for wi, name in months)
    dlabels = "".join(
        f'<text x="{grid_x-9}" y="{grid_y + i*PITCH + 9}" class="ax" text-anchor="end">{lbl}</text>'
        for i, lbl in [(1,"Mon"),(3,"Wed"),(5,"Fri")])

    legend_x = grid_x + grid_w - 150
    legend_y = grid_y + 7*PITCH + 20
    legend = f'<text x="{legend_x-8}" y="{legend_y+9}" class="ax" text-anchor="end">less</text>' + "".join(
        f'<rect x="{legend_x + k*15}" y="{legend_y}" width="{CELL}" height="{CELL}" rx="2.5" class="l{k}"/>'
        for k in range(5)) + f'<text x="{legend_x + 5*15 + 2}" y="{legend_y+9}" class="ax">more</text>'

    stats_y = legend_y + 40
    stats = [
        ("total",   f"{total:,} contributions"),
        ("streak",  f"{longest} days longest · {cur} current"),
        ("active",  f"{active}/{len(days)} days with commits"),
    ]
    srows = "".join(
        f'<text x="{PAD_L}" y="{stats_y + k*22}" class="p">$</text>'
        f'<text x="{PAD_L+16}" y="{stats_y + k*22}" class="cmd">{lbl}</text>'
        f'<text x="{PAD_L+96}" y="{stats_y + k*22}" class="out">{val}</text>'
        for k,(lbl,val) in enumerate(stats))

    H = stats_y + len(stats)*22 + 14
    cmd = "git log --graph --all --since='1 year ago'"

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" font-family="JetBrains Mono, Fira Code, DejaVu Sans Mono, Consolas, monospace">
<defs>
<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#0d1117"/><stop offset="100%" stop-color="#161b22"/></linearGradient>
<linearGradient id="bar" x1="0" y1="0" x2="1" y2="0"><stop offset="0%" stop-color="#1f6feb" stop-opacity="0.32"/><stop offset="55%" stop-color="#8957e5" stop-opacity="0.26"/><stop offset="100%" stop-color="#3fb950" stop-opacity="0.2"/></linearGradient>
<clipPath id="typ"><rect x="{PAD_L}" y="46" height="20" width="{len(cmd)*7.6+30:.0f}">
<animate attributeName="width" values="0;0;{len(cmd)*7.6+30:.0f};{len(cmd)*7.6+30:.0f}" keyTimes="0;0.01;0.05;1" dur="14s" repeatCount="indefinite"/></rect></clipPath>
</defs>
<style>
.p{{fill:#3fb950;font-size:13px;font-weight:700}}
.cmd{{fill:#58a6ff;font-size:13px}}
.out{{fill:#c9d1d9;font-size:13px}}
.ax{{fill:#6e7681;font-size:10px}}
.ttl{{fill:#8b949e;font-size:11.5px}}
.l0{{fill:#161b22;stroke:#21262d;stroke-width:1}}
.l1{{fill:#1f3d63}}.l2{{fill:#2f5fa8}}.l3{{fill:#58a6ff}}.l4{{fill:#8957e5}}
</style>
<rect x="1" y="1" width="{W-2}" height="{H-2}" rx="11" fill="url(#bg)" stroke="#30363d"/>
<path d="M1 12 a11 11 0 0 1 11 -11 h{W-24} a11 11 0 0 1 11 11 v24 h-{W-2} z" fill="url(#bar)"/>
<line x1="1" y1="36" x2="{W-1}" y2="36" stroke="#30363d"/>
<circle cx="21" cy="18.5" r="5.5" fill="#ff5f57"/><circle cx="39" cy="18.5" r="5.5" fill="#febc2e"/><circle cx="57" cy="18.5" r="5.5" fill="#28c840"/>
<text x="{W/2}" y="22.5" text-anchor="middle" class="ttl">{USER}@github: ~/contributions</text>
<g clip-path="url(#typ)"><text x="{PAD_L}" y="60" class="p">$</text><text x="{PAD_L+16}" y="60" class="cmd">{cmd}</text></g>
{mlabels}{dlabels}
{"".join(cells)}
{legend}
{srows}
</svg>'''

if __name__ == "__main__":
    if not TOKEN:
        sys.exit("Set GH_TOKEN (needs read:user scope to include private contributions).")
    open(OUT, "w").write(build(fetch()))
    print(f"wrote {OUT}")