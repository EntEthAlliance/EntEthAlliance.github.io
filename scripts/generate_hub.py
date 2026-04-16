#!/usr/bin/env python3
"""Generate entethalliance.github.io index.html from live GitHub org data.

Design goal: keep https://entethalliance.github.io/ up to date automatically (no manual edits).

- Lists org repos with GitHub Pages enabled
- Splits into Active vs Inactive by pushed_at recency
- Excludes this repo (EntEthAlliance/EntEthAlliance.github.io)
- Excludes wg-ethereum-institute (requested)

Run:
  python3 scripts/generate_hub.py > index.html
"""

import os
import json
import datetime as dt
import urllib.request

ORG = os.environ.get("ORG", "EntEthAlliance")
SELF_REPO = os.environ.get("SELF_REPO", f"{ORG}/{ORG}.github.io")
EXCLUDE = set(filter(None, os.environ.get("EXCLUDE_REPOS", "").split(",")))
EXCLUDE.add(SELF_REPO)
# per request
EXCLUDE.add(f"{ORG}/wg-ethereum-institute")

DAYS_ACTIVE = int(os.environ.get("DAYS_ACTIVE", "183"))

# Optional overrides for nicer display and correct landing URLs
OVERRIDES = {
    f"{ORG}/ops-finance": {
        "title": "Ops Finance (Education Hub)",
        "desc": "The EEA’s central education hub: finance class, Ethereum 101, and builder-ready resources.",
    },
    f"{ORG}/rnd-rwa-erc3643-eas": {
        "title": "Shibui (RWA Identity Bridge)",
        "desc": "Docs and demo for bridging EAS attestations into ERC-3643 token compliance (RWA identity enforcement).",
    },
    f"{ORG}/wg-crosschain": {
        "title": "Crosschain WG",
        "desc": "Working group hub for crosschain interoperability specs, drafts, and supporting artifacts.",
        "wg": True,
    },
    f"{ORG}/wg-privacy": {
        "title": "Privacy WG",
        "desc": "Interactive publication and materials from the EEA Privacy Working Group.",
        "wg": True,
    },
    f"{ORG}/trusted-computing": {
        "pages_url": "https://entethalliance.github.io/trusted-computing/spec.html",
        "desc": "Off-chain Trusted Compute specification (see spec.html).",
    },
}


def gh_json(url: str):
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def paginate(url: str):
    out = []
    page = 1
    while True:
        data = gh_json(f"{url}{'&' if '?' in url else '?'}per_page=100&page={page}")
        if not isinstance(data, list) or not data:
            break
        out.extend(data)
        if len(data) < 100:
            break
        page += 1
    return out


def pages_url(full_name: str) -> str:
    # Prefer the pages endpoint when accessible
    try:
        d = gh_json(f"https://api.github.com/repos/{full_name}/pages")
        return d.get("html_url") or ""
    except Exception:
        org, repo = full_name.split("/", 1)
        if repo.endswith(".github.io"):
            return f"https://{org.lower()}.github.io/"
        return f"https://{org.lower()}.github.io/{repo}/"


def esc(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def main() -> None:
    now = dt.datetime.now(dt.timezone.utc)
    cutoff = now - dt.timedelta(days=DAYS_ACTIVE)

    repos = paginate(f"https://api.github.com/orgs/{ORG}/repos")

    rows = []
    for r in repos:
        if not r.get("has_pages"):
            continue
        full = r.get("full_name")
        if not full or full in EXCLUDE:
            continue

        pushed_at = r.get("pushed_at")
        pushed_dt = dt.datetime.fromisoformat(pushed_at.replace("Z", "+00:00")) if pushed_at else None
        is_active = bool(pushed_dt and pushed_dt >= cutoff)

        url = pages_url(full)
        ov = OVERRIDES.get(full, {})
        url = ov.get("pages_url", url)

        title = ov.get("title") or r.get("name") or full.split("/", 1)[1]
        desc = ov.get("desc") or (r.get("description") or "—")
        is_wg = bool(ov.get("wg")) or (r.get("name", "").startswith("wg-"))

        rows.append({
            "active": is_active,
            "wg": is_wg,
            "title": title,
            "name": r.get("name"),
            "full": full,
            "pages": url,
            "repo": r.get("html_url"),
            "desc": desc,
            "pushed": (pushed_at or "")[:10] or "—",
        })

    rows.sort(key=lambda x: (not x["active"], x["title"].lower()))

    def li(x):
        li_cls = "wg" if x["wg"] and x["active"] else ""
        return (
            f"<li{(' class=\"'+li_cls+'\"') if li_cls else ''}>"
            f"<div class=\"row\"><a class=\"name\" href=\"{esc(x['pages'])}\">{esc(x['title'])}</a>"
            f"<span class=\"meta\">Last update: {esc(x['pushed'])}</span></div>"
            f"<div class=\"desc\">{esc(x['desc'])}</div>"
            f"<div class=\"links\"><a href=\"{esc(x['pages'])}\">Pages</a> · <a href=\"{esc(x['repo'])}\">Repo</a></div>"
            f"</li>"
        )

    active = [x for x in rows if x["active"]]
    inactive = [x for x in rows if not x["active"]]

    html = f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>EEA GitHub Pages</title>
  <style>
    body{{margin:0;font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;background:#0b1220;color:#e7eaf0;}}
    .wrap{{max-width:980px;margin:0 auto;padding:28px 18px 60px;}}
    h1{{margin:0 0 6px;font-size:28px;}}
    .sub{{margin:0 0 12px;color:rgba(231,234,240,.85);}}
    .toplinks{{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 20px;}}
    .toplinks a{{color:rgba(231,234,240,.92);text-decoration:none;font-weight:700;font-size:12px;padding:8px 10px;border-radius:999px;border:1px solid rgba(255,255,255,.14);background:rgba(255,255,255,.04);}}
    .toplinks a:hover{{border-color:rgba(122,162,255,.45);box-shadow:0 0 0 1px rgba(122,162,255,.08) inset;}}

    h2{{margin:26px 0 10px;font-size:18px;}}
    .note{{margin:0 0 12px;color:rgba(231,234,240,.85);}}

    .grid{{list-style:none;padding:0;margin:0;display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px;}}
    .grid li{{position:relative;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.12);border-radius:18px;padding:16px 16px 14px;min-height:140px;}}

    .active-grid li{{border-color:rgba(122,162,255,.40);box-shadow:0 0 0 1px rgba(122,162,255,.10) inset, 0 18px 45px rgba(0,0,0,.35), 0 0 30px rgba(122,162,255,.24);}}
    .active-grid li::before{{content:"ACTIVE";position:absolute;top:14px;left:50%;transform:translateX(-50%);padding:6px 10px;border-radius:999px;display:flex;align-items:center;justify-content:center;background:linear-gradient(180deg, rgba(140,170,255,1), rgba(112,128,255,1));color:#0b1220;font-weight:950;font-size:11px;letter-spacing:.6px;}}

    .active-grid li.wg{{border-color:rgba(64,220,160,.45);box-shadow:0 0 0 1px rgba(64,220,160,.12) inset, 0 18px 45px rgba(0,0,0,.35), 0 0 34px rgba(64,220,160,.22);}}
    .active-grid li.wg::before{{content:"WG";background:linear-gradient(180deg, rgba(90,255,190,1), rgba(34,200,140,1));}}

    .inactive-grid{{grid-template-columns:1fr;}}
    .inactive-grid li{{min-height:auto;background:transparent;border-style:dashed;opacity:.75;}}
    .inactive-grid li::before{{display:none;}}
    .inactive-grid .desc{{display:none;}}

    .row{{display:flex;gap:10px;align-items:baseline;justify-content:space-between;flex-wrap:wrap;margin-top:0;}}
    .active-grid .row{{margin-top:42px;}}

    .name{{color:#9ad1ff;text-decoration:none;font-weight:900;}}
    .name:hover{{text-decoration:underline;}}
    .meta{{color:rgba(231,234,240,.7);font-size:12px;}}
    .desc{{margin-top:6px;color:rgba(231,234,240,.9);}}
    .links{{margin-top:8px;font-size:12px;color:rgba(231,234,240,.75);}}
    .links a{{color:rgba(231,234,240,.9);}}

    .footer{{margin-top:26px;font-size:12px;color:rgba(231,234,240,.65);}}
    code{{font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,"Liberation Mono",monospace;}}
  </style>
</head>
<body>
  <div class=\"wrap\">
    <h1>EEA GitHub Pages</h1>
    <p class=\"sub\">Active pages from the Enterprise Ethereum Alliance — specs, working group outputs, and operational resources.</p>
    <div class=\"toplinks\">
      <a href=\"https://entethalliance.org/\">Website</a>
      <a href=\"https://github.com/EntEthAlliance/\">GitHub</a>
      <a href=\"https://lu.ma/eea.eth\">Luma</a>
      <a href=\"https://www.linkedin.com/company/enterpriseethereumalliance/\">LinkedIn</a>
      <a href=\"https://x.com/EntEthAlliance\">X (Twitter)</a>
    </div>

    <h2>Active Pages</h2>
    <p class=\"note\">Recently updated (last {DAYS_ACTIVE} days).</p>
    <ul class=\"grid active-grid\">{''.join(li(x) for x in active)}</ul>

    <h2>Inactive Pages</h2>
    <p class=\"note\">No updates in the last {DAYS_ACTIVE} days (banner added; repos archived).</p>
    <ul class=\"grid inactive-grid\">{''.join(li(x) for x in inactive)}</ul>

    <div class=\"footer\">
      <div>Notes: Active = updated in the last ~6 months. Inactive repos are archived and include an on-site banner pointing to the EEA GitHub org.</div>
      <div>Some repo links may be members-only (private repos can appear as 404 to unauthenticated visitors).</div>
      <div>Last updated: {now.date().isoformat()}.</div>
    </div>
  </div>
</body>
</html>
"""

    print(html)


if __name__ == "__main__":
    main()
