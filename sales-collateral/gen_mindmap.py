# Generates a one-page landscape mindmap of the BDM first-meeting brief.
import html

W, H = 1700, 1180
CENTER = (850, 590)

branches = [
    # (title, color, side, y_top, lines)
    ("THREE PLAYS", "#2f80ed", "L", 40, [
        "Data Centres — AI CCTV, intrusion,",
        "   ANPR, access (via contractor / M&E)",
        "Developers — preferred-vendor framework",
        "   → recurring tenant deals",
        "Specifiers (M&E) — get designed-in",
        "   before tender",
        "Mfg & FM — retrofit to AI analytics",
        "   + maintenance contracts",
    ]),
    ("PRIORITY TARGETS  (JB Tracker)", "#8e44ad", "L", 415, [
        "STACK Infrastructure — DC, Iskandar Puteri",
        "AirTrunk JHB1 — DC, Sedenak",
        "YTL Green DC Park — DC, Kulai",
        "AME Elite — Developer, Senai",
        "Eco World — Developer, Senai",
        "Megapower M&E — Specifier, JB City",
    ]),
    ("QUICK WIN", "#16a085", "L", 850, [
        "AME Elite & EcoWorld run multiple parks",
        "Week-1: preferred-vendor framework talk",
        "One “yes” = recurring tenant deals",
    ]),
    ("30 / 60 / 90 PLAN", "#e67e22", "R", 40, [
        "0–30  Learn & map: product, win/loss,",
        "   audit accounts, finalise target list",
        "31–60  Activate: book meetings, 2–3",
        "   partnerships, first proposals out",
        "61–90  Convert: close deals, repeatable",
        "   motion, commit monthly forecast",
    ]),
    ("QUESTIONS FOR BOSS", "#c0392b", "R", 415, [
        "Ideal customer? size / margin / sector",
        "Year-1 target & typical sales cycle?",
        "Existing accounts to protect (not cold)?",
        "Pricing flexibility for big DC tenders?",
        "What = success at 90 days, to you?",
    ]),
    ("SYSTEM & COMMITMENTS", "#34495e", "R", 850, [
        "CRM: stage tracking + weighted forecast",
        "   + mobile follow-up alerts",
        "Clean numbers — nothing dropped",
        "Close: restate priorities → 3 actions",
        "   → report-back date",
    ]),
]

CARD_W = 470
LINE_H = 26
HEAD_H = 46
PAD = 16

def esc(s): return html.escape(s)

svg = []
svg.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="Segoe UI, Helvetica, Arial, sans-serif">')
svg.append(f'<rect width="{W}" height="{H}" fill="#f4f6fb"/>')
# title strip
svg.append(f'<text x="{W/2}" y="40" text-anchor="middle" font-size="22" font-weight="700" fill="#0b1f3a">A2 Automation Sdn Bhd — Johor Business Development · First-Meeting Mind Map</text>')

cards = []
for (title, color, side, y_top, lines) in branches:
    h = HEAD_H + len(lines)*LINE_H + PAD
    if side == "L":
        x = 70
        anchor = (x + CARD_W, y_top + h/2)   # right edge -> center
    else:
        x = W - 70 - CARD_W
        anchor = (x, y_top + h/2)            # left edge -> center
    cards.append((title, color, side, x, y_top, h, lines, anchor))

# connectors first (under cards)
cx, cy = CENTER
for (title, color, side, x, y_top, h, lines, anchor) in cards:
    ax, ay = anchor
    edge_x = cx - 215 if side == "L" else cx + 215
    mx = (edge_x + ax)/2
    svg.append(f'<path d="M {ax} {ay} C {mx} {ay}, {mx} {cy}, {edge_x} {cy}" stroke="{color}" stroke-width="3" fill="none" opacity="0.55"/>')
    svg.append(f'<circle cx="{ax}" cy="{ay}" r="5" fill="{color}"/>')

# center node
svg.append(f'<rect x="{cx-215}" y="{cy-58}" width="430" height="116" rx="16" fill="#0b1f3a"/>')
svg.append(f'<text x="{cx}" y="{cy-18}" text-anchor="middle" font-size="20" font-weight="700" fill="#ffffff">First Draft — Approaches</text>')
svg.append(f'<text x="{cx}" y="{cy+10}" text-anchor="middle" font-size="14" fill="#8fb6f0">A2 Automation · Johor BD</text>')
svg.append(f'<text x="{cx}" y="{cy+32}" text-anchor="middle" font-size="14" fill="#8fb6f0">go-to-market plays v1 — for discussion</text>')

# cards
for (title, color, side, x, y_top, h, lines, anchor) in cards:
    svg.append(f'<rect x="{x}" y="{y_top}" width="{CARD_W}" height="{h}" rx="14" fill="#ffffff" stroke="{color}" stroke-width="2"/>')
    svg.append(f'<rect x="{x}" y="{y_top}" width="{CARD_W}" height="{HEAD_H}" rx="14" fill="{color}"/>')
    svg.append(f'<rect x="{x}" y="{y_top+HEAD_H-14}" width="{CARD_W}" height="14" fill="{color}"/>')
    svg.append(f'<text x="{x+18}" y="{y_top+30}" font-size="16" font-weight="700" fill="#ffffff">{esc(title)}</text>')
    ty = y_top + HEAD_H + 24
    for ln in lines:
        bullet = "" if ln.startswith("   ") else "• "
        svg.append(f'<text x="{x+18}" y="{ty}" font-size="13.5" fill="#1a2030">{esc(bullet+ln.strip()) if bullet else "&#160;&#160;&#160;"+esc(ln.strip())}</text>')
        ty += LINE_H

svg.append(f'<text x="{W/2}" y="{H-16}" text-anchor="middle" font-size="12" fill="#6b7689">Listen 60% · speak to revenue &amp; risk · close on commitments — source: JB Prospect Tracker + First Meeting Brief</text>')
svg.append('</svg>')

import os
_out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bdm_mindmap.svg")
open(_out, "w").write("\n".join(svg))
print("SVG written")
