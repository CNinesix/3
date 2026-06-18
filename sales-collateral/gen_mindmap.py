# Generates a one-page landscape mindmap of the BDM first-meeting brief.
# Layout is computed dynamically: a title band on top, three cards per side
# stacked with fixed gaps and vertically centred, so nothing overlaps.
import html
import os

W = 1760
TITLE_BAND = 86
FOOTER_BAND = 44
CARD_W = 486
LINE_H = 26
HEAD_H = 46
PAD_BOTTOM = 18
GAP = 38          # vertical gap between cards in a column
COL_LEFT_X = 60
COL_RIGHT_X = W - 60 - CARD_W

branches = [
    # (title, color, side, lines)
    ("THREE PLAYS", "#2f80ed", "L", [
        "Data Centres — AI CCTV, intrusion,",
        "   ANPR, access (via contractor / M&E)",
        "Developers — preferred-vendor framework",
        "   → recurring tenant deals",
        "Specifiers (M&E) — get designed-in",
        "   before tender",
        "Mfg & FM — retrofit to AI analytics",
        "   + maintenance contracts",
    ]),
    ("PRIORITY TARGETS  (JB Tracker)", "#8e44ad", "L", [
        "STACK Infrastructure — DC, Iskandar Puteri",
        "AirTrunk JHB1 — DC, Sedenak",
        "YTL Green DC Park — DC, Kulai",
        "AME Elite — Developer, Senai",
        "Eco World — Developer, Senai",
        "Megapower M&E — Specifier, JB City",
    ]),
    ("QUICK WIN", "#16a085", "L", [
        "AME Elite & EcoWorld run multiple parks",
        "Week-1: preferred-vendor framework talk",
        "One “yes” = recurring tenant deals",
    ]),
    ("30 / 60 / 90 PLAN", "#e67e22", "R", [
        "0–30  Learn & map: product, win/loss,",
        "   audit accounts, finalise target list",
        "31–60  Activate: book meetings, 2–3",
        "   partnerships, first proposals out",
        "61–90  Convert: close deals, repeatable",
        "   motion, commit monthly forecast",
    ]),
    ("QUESTIONS FOR BOSS", "#c0392b", "R", [
        "Ideal customer? size / margin / sector",
        "Year-1 target & typical sales cycle?",
        "Existing accounts to protect (not cold)?",
        "Pricing flexibility for big DC tenders?",
        "What = success at 90 days, to you?",
    ]),
    ("SYSTEM & COMMITMENTS", "#34495e", "R", [
        "CRM: stage tracking + weighted forecast",
        "   + mobile follow-up alerts",
        "Clean numbers — nothing dropped",
        "Close: restate priorities → 3 actions",
        "   → report-back date",
    ]),
]


def card_height(lines):
    return HEAD_H + len(lines) * LINE_H + PAD_BOTTOM


def esc(s):
    return html.escape(s)


# --- compute per-column stacks ---
left = [b for b in branches if b[2] == "L"]
right = [b for b in branches if b[2] == "R"]


def stack_total(col):
    return sum(card_height(b[3]) for b in col) + GAP * (len(col) - 1)


content_top = TITLE_BAND
content_h_needed = max(stack_total(left), stack_total(right))
# Page height: content + bands + a little breathing room.
H = content_top + content_h_needed + FOOTER_BAND + 80
available = H - content_top - FOOTER_BAND
CENTER = (W / 2, content_top + available / 2)
CN_W, CN_H = 452, 120


def place(col, x):
    total = stack_total(col)
    y = content_top + (available - total) / 2
    placed = []
    for (title, color, side, lines) in col:
        h = card_height(lines)
        anchor_x = x + CARD_W if side == "L" else x
        placed.append((title, color, side, x, y, h, lines, (anchor_x, y + h / 2)))
        y += h + GAP
    return placed


cards = place(left, COL_LEFT_X) + place(right, COL_RIGHT_X)

svg = []
svg.append(
    f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
    f'viewBox="0 0 {W} {H}" font-family="Segoe UI, Helvetica, Arial, sans-serif">'
)
svg.append(f'<rect width="{W}" height="{H}" fill="#f4f6fb"/>')

# title band (its own strip so it never overlaps cards)
svg.append(f'<rect x="0" y="0" width="{W}" height="{TITLE_BAND}" fill="#0b1f3a"/>')
svg.append(
    f'<text x="{W/2}" y="38" text-anchor="middle" font-size="23" font-weight="700" '
    f'fill="#ffffff">A2 Automation Sdn Bhd — Johor Business Development</text>'
)
svg.append(
    f'<text x="{W/2}" y="66" text-anchor="middle" font-size="15" '
    f'fill="#8fb6f0">First-Meeting Mind Map · Senior BDM</text>'
)

cx, cy = CENTER
# connectors (under cards)
for (title, color, side, x, y_top, h, lines, anchor) in cards:
    ax, ay = anchor
    edge_x = cx - CN_W / 2 if side == "L" else cx + CN_W / 2
    mx = (edge_x + ax) / 2
    svg.append(
        f'<path d="M {ax:.0f} {ay:.0f} C {mx:.0f} {ay:.0f}, {mx:.0f} {cy:.0f}, '
        f'{edge_x:.0f} {cy:.0f}" stroke="{color}" stroke-width="3" fill="none" opacity="0.5"/>'
    )
    svg.append(f'<circle cx="{ax:.0f}" cy="{ay:.0f}" r="5" fill="{color}"/>')

# center node
svg.append(
    f'<rect x="{cx-CN_W/2:.0f}" y="{cy-CN_H/2:.0f}" width="{CN_W}" height="{CN_H}" rx="16" fill="#0b1f3a"/>'
)
svg.append(f'<text x="{cx:.0f}" y="{cy-20:.0f}" text-anchor="middle" font-size="21" font-weight="700" fill="#ffffff">First Draft — Approaches</text>')
svg.append(f'<text x="{cx:.0f}" y="{cy+10:.0f}" text-anchor="middle" font-size="14" fill="#8fb6f0">A2 Automation · Johor BD</text>')
svg.append(f'<text x="{cx:.0f}" y="{cy+34:.0f}" text-anchor="middle" font-size="14" fill="#8fb6f0">go-to-market plays v1 — for discussion</text>')

# cards
for (title, color, side, x, y_top, h, lines, anchor) in cards:
    svg.append(f'<rect x="{x}" y="{y_top:.0f}" width="{CARD_W}" height="{h}" rx="14" fill="#ffffff" stroke="{color}" stroke-width="2"/>')
    svg.append(f'<rect x="{x}" y="{y_top:.0f}" width="{CARD_W}" height="{HEAD_H}" rx="14" fill="{color}"/>')
    svg.append(f'<rect x="{x}" y="{y_top+HEAD_H-14:.0f}" width="{CARD_W}" height="14" fill="{color}"/>')
    svg.append(f'<text x="{x+18}" y="{y_top+30:.0f}" font-size="16" font-weight="700" fill="#ffffff">{esc(title)}</text>')
    ty = y_top + HEAD_H + 24
    for ln in lines:
        is_cont = ln.startswith("   ")
        text = ln.strip()
        if is_cont:
            svg.append(f'<text x="{x+30}" y="{ty:.0f}" font-size="13.5" fill="#41506b">{esc(text)}</text>')
        else:
            svg.append(f'<text x="{x+18}" y="{ty:.0f}" font-size="13.5" fill="#1a2030">&#8226; {esc(text)}</text>')
        ty += LINE_H

svg.append(
    f'<text x="{W/2}" y="{H-16}" text-anchor="middle" font-size="12" fill="#6b7689">'
    f'Listen 60% · speak to revenue &amp; risk · close on commitments — '
    f'source: JB Prospect Tracker + First Meeting Brief</text>'
)
svg.append('</svg>')

_out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bdm_mindmap.svg")
open(_out, "w").write("\n".join(svg))
print(f"SVG written: {W}x{H}")
