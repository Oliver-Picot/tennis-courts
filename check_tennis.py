#!/usr/bin/env python3
"""
Tennis court availability checker.
Checks: Queens Park (ClubSpark) and Kilburn Grange (Camden Active).

Generates tennis.html in the same folder — open that in any browser.

Shows only slots you'd want:
  - Weekdays: 5:30pm onwards (17:30)
  - Weekends: all day
"""

import json
import os
import re
import urllib.request
from datetime import date, datetime, timedelta

DAYS_AHEAD = 7
HERE = os.path.dirname(os.path.abspath(__file__))
OUTPUT_HTML = os.path.join(HERE, "index.html")

# ── Queens Park (ClubSpark JSON API) ──────────────────────────────────────────

QUEENS_PARK_API = (
    "https://clubspark.lta.org.uk/v0/VenueBooking/QueensParkTennisCourts"
    "/GetVenueSessions?resourceID=&startDate={date}&endDate={date}&roleId="
)
QUEENS_PARK_BOOKING_URL = (
    "https://clubspark.lta.org.uk/QueensParkTennisCourts/Booking/BookByDate#?date={date}"
)

# ── Kilburn Grange (Camden Active HTML pages) ─────────────────────────────────

KILBURN_COURTS = [
    {
        "name": "Court 1",
        "url": "https://camdenactive.camden.gov.uk/courses/detail/178/kilburn-grange-tennis-court-1/",
    },
    {
        "name": "Court 2",
        "url": "https://camdenactive.camden.gov.uk/courses/detail/179/kilburn-grange-tennis-court-2/",
    },
    {
        "name": "Court 3",
        "url": "https://camdenactive.camden.gov.uk/courses/detail/183/kilburn-grange-tennis-court-3/",
    },
]
KILBURN_BASE_URL = "https://camdenactive.camden.gov.uk"

# ── Fetching ───────────────────────────────────────────────────────────────────

def fetch_text(url, accept="text/html", referer=None):
    headers = {"User-Agent": "Mozilla/5.0", "Accept": accept}
    if referer:
        headers["Referer"] = referer
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read().decode("utf-8", errors="replace")


def fetch_json(url):
    return json.loads(fetch_text(
        url,
        accept="application/json",
        referer="https://clubspark.lta.org.uk/QueensParkTennisCourts/Booking/BookByDate",
    ))


# ── Filtering ──────────────────────────────────────────────────────────────────

def slot_passes_filter(hour, check_date):
    """Weekdays: show from 17:00 (covers 17:00–18:00, i.e. a 5pm start).
    Weekends: show everything."""
    if check_date.weekday() >= 5:  # Saturday or Sunday
        return True
    return hour >= 17


def minutes_to_time(minutes):
    h, m = divmod(minutes, 60)
    return f"{h:02d}:{m:02d}"


# ── Queens Park ────────────────────────────────────────────────────────────────

def get_queens_park_slots(check_date):
    date_str = check_date.strftime("%Y-%m-%d")
    url = QUEENS_PARK_API.format(date=date_str)
    try:
        data = fetch_json(url)
    except Exception as e:
        return None, str(e)

    slots = []
    for resource in data.get("Resources", []):
        court_name = resource["Name"]
        for day in resource.get("Days", []):
            for session in day.get("Sessions", []):
                if session["Capacity"] > 0 and session["Category"] != 8000:
                    start_min = session["StartTime"]
                    end_min = session["EndTime"]
                    if slot_passes_filter(start_min // 60, check_date):
                        slots.append({
                            "court": court_name,
                            "start": minutes_to_time(start_min),
                            "end": minutes_to_time(end_min),
                            "booking_url": QUEENS_PARK_BOOKING_URL.format(date=date_str),
                        })
    return slots, None


# ── Kilburn Grange ─────────────────────────────────────────────────────────────

def get_kilburn_slots():
    all_slots = {}  # "DD/MM/YYYY" -> [slot, ...]
    for court in KILBURN_COURTS:
        try:
            html = fetch_text(court["url"])
        except Exception as e:
            print(f"  [Warning] Could not fetch {court['name']}: {e}")
            continue

        matches = re.findall(
            r'<a class="facility-book" href="(/courses/book\.aspx\?[^"]+)">'
            r'.*?<span class="facility-hour">(\d+):\d+\s*</span>',
            html, re.DOTALL,
        )
        for href, hour_str in matches:
            date_m = re.search(r"fdDate=(\d+/\d+/\d+)", href)
            if not date_m:
                continue
            date_str = date_m.group(1)
            hour = int(hour_str)
            d, m, y = (int(x) for x in date_str.split("/"))
            slot_date = date(y, m, d)
            if not slot_passes_filter(hour, slot_date):
                continue
            all_slots.setdefault(date_str, []).append({
                "court": court["name"],
                "start": f"{hour:02d}:00",
                "end": f"{hour + 1:02d}:00",
                "booking_url": KILBURN_BASE_URL + href,
            })
    return all_slots


def kilburn_date_key(check_date):
    return check_date.strftime("%d/%m/%Y")


# ── HTML generation ────────────────────────────────────────────────────────────

CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    background: #f0f4f8;
    color: #1a202c;
    padding: 16px;
    max-width: 600px;
    margin: 0 auto;
}
h1 {
    font-size: 1.25rem;
    font-weight: 700;
    margin-bottom: 4px;
    color: #1a202c;
}
.subtitle {
    font-size: 0.8rem;
    color: #718096;
    margin-bottom: 20px;
}
.venue-section {
    margin-bottom: 28px;
}
.venue-header {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 12px;
}
.venue-dot {
    width: 12px;
    height: 12px;
    border-radius: 50%;
    flex-shrink: 0;
}
.venue-qp  .venue-dot { background: #3182ce; }
.venue-kg  .venue-dot { background: #38a169; }
.venue-name {
    font-size: 1rem;
    font-weight: 700;
    letter-spacing: 0.02em;
    text-transform: uppercase;
    color: #2d3748;
}
.day-block {
    background: white;
    border-radius: 12px;
    overflow: hidden;
    margin-bottom: 10px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}
.day-header {
    padding: 10px 14px;
    font-size: 0.85rem;
    font-weight: 600;
    color: #4a5568;
    background: #f7fafc;
    border-bottom: 1px solid #e2e8f0;
}
.day-header .today-badge {
    display: inline-block;
    background: #ebf8ff;
    color: #2b6cb0;
    font-size: 0.7rem;
    font-weight: 700;
    padding: 1px 7px;
    border-radius: 999px;
    margin-left: 6px;
    vertical-align: middle;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}
.slot-row {
    display: flex;
    align-items: center;
    padding: 11px 14px;
    border-bottom: 1px solid #f0f4f8;
    gap: 10px;
}
.slot-row:last-child { border-bottom: none; }
.slot-time {
    font-size: 0.95rem;
    font-weight: 600;
    color: #2d3748;
    min-width: 105px;
    white-space: nowrap;
}
.slot-court {
    flex: 1;
    font-size: 0.8rem;
    color: #718096;
}
.book-btn {
    display: inline-block;
    padding: 7px 14px;
    border-radius: 8px;
    font-size: 0.8rem;
    font-weight: 600;
    text-decoration: none;
    white-space: nowrap;
    color: white;
}
.venue-qp  .book-btn { background: #3182ce; }
.venue-kg  .book-btn { background: #38a169; }
.empty {
    text-align: center;
    color: #a0aec0;
    font-size: 0.85rem;
    padding: 20px 0;
}
footer {
    text-align: center;
    font-size: 0.75rem;
    color: #a0aec0;
    margin-top: 24px;
    padding-bottom: 12px;
}
"""

def html_day_rows(slots, venue_class):
    """Build <div class='slot-row'>…</div> entries for a list of slots."""
    # Group by (start, end, url) so courts sharing a URL are merged on one line
    by_key = {}
    for s in slots:
        key = (s["start"], s["end"], s["booking_url"])
        by_key.setdefault(key, []).append(s)

    rows = []
    for (start, end, url), group in sorted(by_key.items()):
        courts = ", ".join(s["court"] for s in group)
        rows.append(
            f'<div class="slot-row">'
            f'<span class="slot-time">{start}–{end}</span>'
            f'<span class="slot-court">{courts}</span>'
            f'<a class="book-btn" href="{url}" target="_blank" rel="noopener">Book</a>'
            f'</div>'
        )
    return "\n".join(rows)


def build_html(qp_data, kg_data, today):
    now_str = datetime.now().strftime("%-d %B %Y at %H:%M")

    venues = [
        {
            "label": "Queens Park",
            "class": "venue-qp",
            "get_slots": lambda i: qp_data[i],
        },
        {
            "label": "Kilburn Grange",
            "class": "venue-kg",
            "get_slots": lambda i: kg_data[i],
        },
    ]

    venue_blocks = []
    for v in venues:
        day_blocks = []
        for i in range(DAYS_AHEAD):
            check_date = today + timedelta(days=i)
            slots = v["get_slots"](i)
            if not slots:
                continue
            label = check_date.strftime("%A %-d %B")
            today_badge = '<span class="today-badge">Today</span>' if i == 0 else ""
            rows = html_day_rows(slots, v["class"])
            day_blocks.append(
                f'<div class="day-block">'
                f'<div class="day-header">{label}{today_badge}</div>'
                f'{rows}'
                f'</div>'
            )

        if not day_blocks:
            day_blocks = ['<p class="empty">No slots found in the next 7 days.</p>']

        venue_blocks.append(
            f'<section class="venue-section {v["class"]}">'
            f'<div class="venue-header">'
            f'<div class="venue-dot"></div>'
            f'<span class="venue-name">{v["label"]}</span>'
            f'</div>'
            + "\n".join(day_blocks)
            + "</section>"
        )

    body = "\n".join(venue_blocks)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Tennis Courts — Available Slots</title>
<style>{CSS}</style>
</head>
<body>
<h1>🎾 Available Courts</h1>
<p class="subtitle">Weekdays from 17:00 &nbsp;|&nbsp; Weekends all day &nbsp;|&nbsp; Updated {now_str}</p>
{body}
<footer>Tap a slot to open the booking page &nbsp;·&nbsp; <a href="https://clubspark.lta.org.uk/QueensParkTennisCourts/Booking/BookByDate">Queens Park</a> &nbsp;·&nbsp; <a href="https://camdenactive.camden.gov.uk/courses/detail/178/kilburn-grange-tennis-court-1/">Kilburn Grange</a></footer>
</body>
</html>"""


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    today = date.today()
    print(f"Checking courts for {today.strftime('%-d %B %Y')}…")

    # Collect Queens Park data (one API call per day)
    print("  Fetching Queens Park…")
    qp_by_index = []
    for i in range(DAYS_AHEAD):
        check_date = today + timedelta(days=i)
        slots, error = get_queens_park_slots(check_date)
        if error:
            print(f"    Warning ({check_date}): {error}")
            slots = []
        qp_by_index.append(slots or [])

    # Collect Kilburn Grange data (three HTML pages, covers the whole week)
    print("  Fetching Kilburn Grange (3 courts)…")
    kilburn_raw = get_kilburn_slots()
    kg_by_index = []
    for i in range(DAYS_AHEAD):
        check_date = today + timedelta(days=i)
        kg_by_index.append(kilburn_raw.get(kilburn_date_key(check_date), []))

    # Build and save HTML
    html = build_html(qp_by_index, kg_by_index, today)
    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)

    total_qp = sum(len(s) for s in qp_by_index)
    total_kg = sum(len(s) for s in kg_by_index)
    print(f"\nDone! Found {total_qp} Queens Park slots and {total_kg} Kilburn Grange slots.")
    print(f"Open this file in your browser:\n  {OUTPUT_HTML}")


if __name__ == "__main__":
    main()
