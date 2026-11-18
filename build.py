"""Regenerate the static site (*.html, sitemap.xml, robots.txt, site.webmanifest)
from content/*.md and data/*.json.  Usage:  python3 build.py   (no dependencies)"""
import json, re, html, os, struct
from datetime import date
from functools import lru_cache

SITE = "https://rvti-mm.org"
TODAY = date.today().isoformat()
os.chdir(os.path.dirname(os.path.abspath(__file__)))

def J(name): return json.load(open(f"data/{name}.json", encoding="utf-8"))
site, contact, team = J("site"), J("contact"), J("team")
objectives, values, rules = J("objectives"), J("core-values"), J("ground-rules")
structure, roles, programs, activities = J("structure"), J("roles"), J("programs"), J("activities")
e = lambda s: html.escape(str(s), quote=True)
rel = lambda p: p.lstrip("/")

@lru_cache(None)
def dims(p):
    """Pixel size of a WebP or PNG file, read from its header (for width/height attributes)."""
    b = open(rel(p), "rb").read(32)
    if b[:4] == b"\x89PNG":
        return struct.unpack(">II", b[16:24])
    if b[:4] == b"RIFF" and b[8:12] == b"WEBP":
        kind = b[12:16]
        if kind == b"VP8 ":
            w, h = struct.unpack("<HH", b[26:30]); return w & 0x3FFF, h & 0x3FFF
        if kind == b"VP8L":
            v = int.from_bytes(b[21:25], "little"); return (v & 0x3FFF) + 1, ((v >> 14) & 0x3FFF) + 1
        if kind == b"VP8X":
            return int.from_bytes(b[24:27], "little") + 1, int.from_bytes(b[27:30], "little") + 1
    raise ValueError(f"Unsupported image (use .webp or .png): {p}")

def img(p, alt, cls="", lazy=True, extra=""):
    w, h = dims(p)
    load = 'loading="lazy" decoding="async"' if lazy else 'fetchpriority="high" decoding="async"'
    c = f' class="{cls}"' if cls else ""
    return f'<img src="{rel(p)}" alt="{e(alt)}" width="{w}" height="{h}" {load}{c}{extra}>'

def tel(n):
    d = re.sub(r"\D", "", n)
    return "+95" + d[1:] if d.startswith("0") else "+95" + d

def slug(s): return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")

# ---------- tiny markdown (covers our content files) ----------
def inline(s):
    s = e(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    return s

def md(text):
    meta, body = {}, text
    if text.startswith("---"):
        _, fm, body = text.split("---", 2)
        key = None
        for line in fm.strip().splitlines():
            if line.startswith("  - "): meta[key].append(line[4:].strip())
            else:
                key, _, val = line.partition(":")
                key = key.strip(); val = val.strip()
                meta[key] = val if val else []
    out, para, lst = [], [], None
    heads = []
    def flush():
        nonlocal para, lst
        if para: out.append(f"<p>{inline(' '.join(para))}</p>"); para = []
        if lst: out.append(f"</{lst}>"); lst = None
    for raw in body.strip().splitlines():
        line = raw.rstrip()
        if not line: flush(); continue
        m = re.match(r"^(#{2,4}) (.+)$", line)
        if m:
            flush(); lvl = len(m[1]); t = m[2]; i = slug(t)
            if lvl == 2: heads.append((i, t))
            out.append(f'<h{lvl} id="{i}">{inline(t)}</h{lvl}>'); continue
        m = re.match(r"^!\[(.*?)\]\((.+?)\)$", line)
        if m: flush(); out.append(img(m[2], m[1])); continue
        m = re.match(r"^(- |\d+\. )(.+)$", line)
        if m:
            kind = "ul" if m[1] == "- " else "ol"
            if para: out.append(f"<p>{inline(' '.join(para))}</p>"); para = []
            if lst != kind:
                if lst: out.append(f"</{lst}>")
                out.append(f"<{kind}>"); lst = kind
            out.append(f"<li>{inline(m[2])}</li>"); continue
        if lst: out.append(f"</{lst}>"); lst = None
        para.append(line)
    flush()
    return meta, "\n".join(out), heads

def md_sections(html_str):
    """split rendered markdown into {h2-id: html} keeping order"""
    parts = re.split(r'(?=<h2 id=")', html_str)
    return {re.match(r'<h2 id="([^"]+)"', p)[1]: p for p in parts if p.startswith("<h2")}

def page_md(name): return md(open(f"content/{name}.md", encoding="utf-8").read())

# ---------- shared chrome ----------
NAV = [("about.html", "About"), ("programs.html", "Programs"), ("where-we-work.html", "Where we work"),
       ("activities.html", "Activities"), ("team.html", "Team"), ("governance.html", "Governance"),
       ("policies.html", "Policies"), ("contact.html", "Contact")]
ORG_ID = f"{SITE}/#organization"
OG_IMAGE = f"{SITE}/images/og.jpg"
main_office = next(o for o in contact["offices"] if o["main"])

def org_ld():
    return {
        "@type": "NGO", "@id": ORG_ID, "name": site["name"],
        "alternateName": [site["shortName"], site["formerName"]],
        "url": SITE + "/", "logo": f"{SITE}/images/logo.png", "image": OG_IMAGE,
        "description": site["mission"], "slogan": site["tagline"],
        "foundingDate": str(site["founded"]["year"]),
        "foundingLocation": {"@type": "Place", "name": site["founded"]["place"] + ", Myanmar"},
        "email": contact["email"], "telephone": tel(main_office["phone"]),
        "nonprofitStatus": "Nonprofit", "knowsAbout": site["sectors"],
        "address": {"@type": "PostalAddress", "streetAddress": "20-A Yamuna Main Road, Patheinmyae Ward",
                    "addressLocality": "Dawbon Township", "addressRegion": "Yangon", "addressCountry": "MM"},
        "areaServed": [{"@type": "AdministrativeArea", "name": n} for n in
                       ["Rakhine State, Myanmar", "Ayeyarwady Region, Myanmar", "Tanintharyi Region, Myanmar"]],
        "location": [{"@type": "Place", "name": f"RVTI {o['name']}", "telephone": tel(o["phone"]),
                      "address": {"@type": "PostalAddress", "streetAddress": o["address"], "addressCountry": "MM"}}
                     for o in contact["offices"]],
        "contactPoint": {"@type": "ContactPoint", "contactType": "community outreach",
                         "name": contact["focalPerson"]["name"], "telephone": tel(contact["focalPerson"]["phone"]),
                         "email": contact["focalPerson"]["email"], "availableLanguage": ["English", "Burmese"]},
    }

def crumbs_ld(name, path):
    return {"@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "Home", "item": SITE + "/"},
        {"@type": "ListItem", "position": 2, "name": name, "item": f"{SITE}/{path}"}]}

def header(cur):
    links = "".join(f'<li><a href="{h}"{" aria-current=\"page\"" if h == cur else ""}>{l}</a></li>' for h, l in NAV)
    return f"""<a class="skip" href="#main">Skip to content</a>
<header class="site-header">
  <div class="wrap">
    <a class="brand" href="index.html" aria-label="{e(site['name'])} home">
      <img src="images/logo-160.png" alt="" width="160" height="155">
      <span class="brand-name"><strong>RVTI</strong><span>{e(site['name'])}</span></span>
    </a>
    <nav class="nav-desktop" aria-label="Main"><ul>{links}</ul></nav>
    <details class="nav-mobile">
      <summary aria-label="Open menu">Menu</summary>
      <nav aria-label="Main (mobile)"><ul>{links}</ul></nav>
    </details>
  </div>
</header>"""

def partner_band():
    collab = "We welcome partnerships with organizations and institutions that share our vision of enhancing education, healthcare, and resource governance. By working together, we can achieve greater impact and drive meaningful change in the communities we serve."
    fp = contact["focalPerson"]
    return f"""<section class="partner" aria-labelledby="partner-title">
  <div class="wrap">
    <div>
      <h2 id="partner-title">Partner with us</h2>
      <p>{collab}</p>
    </div>
    <div class="partner-links">
      <a class="btn btn-primary" href="mailto:{contact['email']}">Email {contact['email']}</a>
      <a href="tel:{tel(fp['phone'])}">Call {fp['name']}, {fp['phone']}</a>
    </div>
  </div>
</section>"""

def footer():
    offices = "".join(f"""<address><strong>{e(o['name'])}</strong><br>{e(o['address'])}<br><a href="tel:{tel(o['phone'])}">{e(o['phone'])}</a></address>""" for o in contact["offices"])
    links = "".join(f'<li><a href="{h}">{l}</a></li>' for h, l in NAV)
    return f"""<footer class="site-footer">
  <div class="wrap">
    <div class="footer-grid">
      <div class="footer-brand">
        <img src="images/logo-160.png" alt="RVTI logo" width="160" height="155" loading="lazy">
        <strong>{e(site['name'])}</strong>
        <p>{e(site['tagline'])}</p>
      </div>
      <div><h2>Offices</h2>{offices}</div>
      <div><h2>Explore</h2><ul>{links}</ul></div>
      <div><h2>Contact</h2><ul>
        <li><a href="mailto:{contact['email']}">{contact['email']}</a></li>
        <li><a href="tel:{tel(main_office['phone'])}">{main_office['phone']}</a></li>
      </ul></div>
    </div>
    <p class="footer-bottom">© 2026 {e(site['name'])} (RVTI). Founded as {e(site['formerName'])} in {site['founded']['year']}.</p>
  </div>
</footer>"""

def page(file, title, desc, body, ld=(), cur=None, noindex=False):
    graph = {"@context": "https://schema.org", "@graph": [org_ld(), *ld]}
    canonical = f"{SITE}/" if file == "index.html" else f"{SITE}/{file}"
    robots = "noindex" if noindex else "index, follow, max-image-preview:large"
    doc = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<meta name="robots" content="{robots}">
<link rel="canonical" href="{canonical}">
<meta name="theme-color" content="#151a4a">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{e(site['name'])}">
<meta property="og:locale" content="en_US">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{canonical}">
<meta property="og:image" content="{OG_IMAGE}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="Children and volunteers at an RVTI community event">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{e(title)}">
<meta name="twitter:description" content="{e(desc)}">
<meta name="twitter:image" content="{OG_IMAGE}">
<link rel="icon" href="favicon.ico" sizes="48x48">
<link rel="icon" href="favicon-512.png" type="image/png">
<link rel="apple-touch-icon" href="apple-touch-icon.png">
<link rel="manifest" href="site.webmanifest">
<link rel="preload" href="fonts/bricolage-grotesque-latin-wght-normal.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="fonts/source-sans-3-latin-wght-normal.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="css/style.css">
<script type="application/ld+json">{json.dumps(graph, ensure_ascii=False)}</script>
</head>
<body>
{header(cur)}
<main id="main">
{body}
</main>
{footer()}
</body>
</html>
"""
    open(file, "w", encoding="utf-8").write(doc)

def page_head(name, file, h1, lead):
    return f"""<div class="page-head">
  <div class="wrap">
    <nav class="crumbs" aria-label="Breadcrumb"><ol><li><a href="index.html">Home</a></li><li aria-current="page">{e(name)}</li></ol></nav>
    <h1>{e(h1)}</h1>
    <p>{e(lead)}</p>
  </div>
</div>"""

def terms(items):
    return '<dl class="terms">' + "".join(f"<div><dt>{e(i['title'])}</dt><dd>{e(i['description'])}</dd></div>" for i in items) + "</dl>"

TONE = {"education": "red", "healthcare": "yellow", "resource-governance-livelihood": "blue"}
initials = lambda n: "".join(w[0] for w in n.split()[:2])

def photo(m, cls=""):
    if m["image"]: return img(m["image"], f"Portrait of {m['name']}, {m['position']}")
    return f'<div class="initials" aria-hidden="true">{initials(m["name"])}</div>'

# ================= HOME =================
fa = programs["focusAreas"]
regions = [("Rakhine State", "Our home state and main focus. Founded in Sittway, where we have an office."),
           ("Ayeyarwady Region", "Myanmar's rice-growing delta, where fishers and smallholders face conflicts over resource access."),
           ("Tanintharyi Region", "The southernmost coast and the Mergui Archipelago, rich in fisheries and forests.")]
home = f"""<section class="hero" aria-labelledby="hero-title">
  {img(site['heroImage'], 'Children holding certificates with RVTI volunteers at a community learning event', lazy=False)}
  <div class="wrap">
    <h1 id="hero-title">Learning, health and fair use of resources for Myanmar's coastal communities</h1>
    <p class="hero-tagline">{e(site['tagline'])}.</p>
    <div class="hero-actions">
      <a class="btn btn-primary" href="programs.html">See our programs</a>
      <a class="btn btn-ghost" href="contact.html">Work with us</a>
    </div>
  </div>
</section>

<section class="section" aria-labelledby="who-title">
  <div class="wrap split">
    <div>
      <h2 id="who-title">A local initiative since 2009</h2>
      <p class="lead">Members of Renaissance Language Campus started {e(site['formerName'])} in Sittway in 2009, paying for school supplies out of their own pockets. Today RVTI works on education, public health and community-led resource governance across Myanmar's coast.</p>
      <p><a href="about.html">Read our story</a></p>
    </div>
    <dl class="vm">
      <dt>Our vision</dt><dd class="statement">{e(site['vision'])}</dd>
      <dt>Our mission</dt><dd>{e(site['mission'])}</dd>
    </dl>
  </div>
</section>

<section class="section section-tint" aria-labelledby="work-title">
  <div class="wrap">
    <div class="section-head">
      <h2 id="work-title">What we do</h2>
      <p>The three figures in our logo stand for the three areas we work in.</p>
    </div>
    <div class="sectors">
      {''.join(f'''<article class="sector tone-{TONE[f['id']]}">
        {img(f['image'], f['title'] + ' programme activity')}
        <h3><span class="dot" aria-hidden="true"></span>{e(f['title'])}</h3>
        <ul>{''.join(f'<li>{e(i)}</li>' for i in f['items'][:3])}</ul>
        <a class="more" href="programs.html#{f['id']}">More on {e(f['title'].lower())}</a>
      </article>''' for f in fa)}
    </div>
  </div>
</section>

<section class="section" aria-labelledby="where-title">
  <div class="wrap regions">
    <figure>{img('/images/regions/coastal-map.webp', 'Map of Myanmar highlighting the coastal states and regions where RVTI works')}</figure>
    <div>
      <h2 id="where-title">Where we work</h2>
      <ul class="region-list">
        {''.join(f'<li><h3>{n}</h3><p>{d}</p></li>' for n, d in regions)}
      </ul>
      <a href="where-we-work.html">About these regions</a>
    </div>
  </div>
</section>

<section class="section section-tint" aria-labelledby="field-title">
  <div class="wrap">
    <div class="section-head">
      <h2 id="field-title">From the field</h2>
      <p>Youth talks, community meetings, children's learning and exchange visits abroad.</p>
    </div>
    <ul class="mosaic">
      {''.join(f'''<li><a href="activities.html#{a['id']}"><figure>{img(a['images'][0], a['title'])}<figcaption>{e(a['title'])}</figcaption></figure></a></li>''' for a in activities)}
    </ul>
  </div>
</section>

<section class="section" aria-labelledby="team-title">
  <div class="wrap">
    <div class="section-head">
      <h2 id="team-title">The people behind RVTI</h2>
      <p><a href="team.html">Meet the whole team</a></p>
    </div>
    <ul class="people">
      {''.join(f'<li>{photo(m)}<strong>{e(m["name"])}</strong><span>{e(m["position"])}</span></li>' for m in team if m['image'])}
    </ul>
  </div>
</section>
{partner_band()}"""
page("index.html", "RVTI – Renaissance Visionary Thriving Initiative | Myanmar NGO",
     "RVTI is a local non-profit founded in Sittway in 2009, supporting education, public health and community-led resource governance in Rakhine, Ayeyarwady and Tanintharyi.",
     home, ld=[{"@type": "WebSite", "@id": f"{SITE}/#website", "url": SITE + "/", "name": site["name"],
                "alternateName": site["shortName"], "publisher": {"@id": ORG_ID}, "inLanguage": "en"}], cur=None)

# ================= ABOUT =================
meta, body, _ = page_md("about")
about = f"""{page_head('About', 'about.html', 'About RVTI', meta['description'])}
<section class="section"><div class="wrap split">
  <div><dl class="vm"><dt>Our vision</dt><dd class="statement">{e(site['vision'])}</dd><dt>Our mission</dt><dd>{e(site['mission'])}</dd></dl></div>
  <div class="prose">{body}</div>
</div></section>
<section class="section section-tint" aria-labelledby="values-title"><div class="wrap">
  <h2 id="values-title">Core values</h2>{terms(values)}
</div></section>
<section class="section" aria-labelledby="aims-title"><div class="wrap">
  <h2 id="aims-title">Aims and objectives</h2>{terms(objectives)}
</div></section>
<section class="section section-tint" aria-labelledby="rules-title"><div class="wrap">
  <h2 id="rules-title">How we work</h2>
  <p class="lead measure">Ground rules every member of RVTI follows.</p>{terms(rules)}
</div></section>
{partner_band()}"""
page("about.html", "About Us – History, Vision and Values | RVTI Myanmar",
     "From Renaissance Edu-Care in Sittway (2009) to RVTI: our history, vision, mission, core values and the aims that guide our work in Myanmar.",
     about, ld=[crumbs_ld("About", "about.html"), {"@type": "AboutPage", "url": f"{SITE}/about.html", "about": {"@id": ORG_ID}}], cur="about.html")

# ================= PROGRAMS =================
meta, body, _ = page_md("programs")
secs = md_sections(body)
progs = f"""{page_head('Programs', 'programs.html', 'Our programs', meta['description'])}
<section class="section"><div class="wrap">
  <div class="prose">{secs['project-scope']}</div>
  {''.join(f'''<article class="program tone-{TONE[f['id']]}" id="{f['id']}">
    {img(f['image'], f['title'] + ' programme activity')}
    <div><h2><span class="dot" aria-hidden="true"></span>{e(f['title'])}</h2>
    <ul>{''.join(f'<li>{e(i)}</li>' for i in f['items'])}</ul></div>
  </article>''' for f in fa)}
</div></section>
<section class="section section-tint" aria-labelledby="init-title"><div class="wrap">
  <h2 id="init-title">Programme initiatives</h2>{terms(programs['initiatives'])}
</div></section>
{partner_band()}"""
page("programs.html", "Programs – Education, Healthcare and Resource Governance | RVTI",
     "RVTI programs in Myanmar: free English and learning support for rural schools, community health and hygiene, and sustainable coastal resource governance and livelihoods.",
     progs, ld=[crumbs_ld("Programs", "programs.html"),
                {"@type": "ItemList", "name": "RVTI focus areas", "itemListElement": [
                    {"@type": "ListItem", "position": i + 1, "name": f["title"], "url": f"{SITE}/programs.html#{f['id']}"} for i, f in enumerate(fa)]}],
     cur="programs.html")

# ================= WHERE WE WORK =================
meta, body, heads = page_md("where-we-work")
toc = '<nav class="toc" aria-labelledby="toc-title"><h2 id="toc-title">On this page</h2><ol>' + "".join(f'<li><a href="#{i}">{e(t)}</a></li>' for i, t in heads) + "</ol></nav>"
www = f"""{page_head('Where we work', 'where-we-work.html', 'Where we work', meta['description'])}
<section class="section"><div class="wrap with-toc">{toc}<div class="prose">{body}</div></div></section>
{partner_band()}"""
page("where-we-work.html", "Where We Work – Rakhine, Ayeyarwady and Tanintharyi | RVTI",
     "RVTI works in Myanmar's coastal states and regions: Rakhine State, Ayeyarwady Region and Tanintharyi Region. Geography, economy and challenges of each.",
     www, ld=[crumbs_ld("Where we work", "where-we-work.html")], cur="where-we-work.html")

# ================= ACTIVITIES =================
acts = f"""{page_head('Activities', 'activities.html', 'Activities', 'Photos from youth talks, community meetings, support for children and learning exchanges with partners abroad.')}
<section class="section"><div class="wrap">
{''.join(f'''<article class="activity" id="{a['id']}">
  <h2>{e(a['title'])}</h2>
  {('<ul>' + ''.join(f'<li>{e(d)}</li>' for d in a['description']) + '</ul>') if a['description'] else ''}
  <ul class="mosaic wide">{''.join(f'<li><figure>{img(p, a["title"] + f" – photo {n}")}</figure></li>' for n, p in enumerate(a['images'], 1))}</ul>
</article>''' for a in activities)}
</div></section>
{partner_band()}"""
page("activities.html", "Activities and Photos – Youth Talks, Community Work | RVTI",
     "See RVTI in action: opportunity talks with youth, coordination with government agencies, support for community children in Rakhine and learning exchanges in Sweden and Cambodia.",
     acts, ld=[crumbs_ld("Activities", "activities.html"),
               {"@type": "ImageGallery", "name": "RVTI activities", "url": f"{SITE}/activities.html",
                "image": [f"{SITE}/{rel(p)}" for a in activities for p in a["images"]]}], cur="activities.html")

# ================= TEAM =================
members = "".join(f"""<li class="member" id="{m['id']}">
  <div class="photo">{photo(m)}</div>
  <h2>{e(m['name'])}</h2>
  <p class="role">{e(m['position'])}</p>
  {f'<p class="note">{e(m["note"])}</p>' if m.get('note') else ''}
  {f'<p class="summary">{e(m["summary"])}</p>' if m['summary'] else ''}
  {f'<details><summary><span class="closed-label">Read full bio</span><span class="open-label">Hide bio</span><span class="visually-hidden"> of {e(m["name"])}</span></summary><div class="bio">{"".join(f"<p>{e(p)}</p>" for p in m["bio"])}</div></details>' if m['bio'] else ''}
</li>""" for m in team)
person = lambda m: {"@type": "Person", "@id": f"{SITE}/team.html#{m['id']}", "name": m["name"], "jobTitle": m["position"],
                    "worksFor": {"@id": ORG_ID}, **({"image": f"{SITE}/{rel(m['image'])}"} if m["image"] else {}),
                    **({"description": m["summary"]} if m["summary"] else {})}
page("team.html", "Our Team – RVTI Staff and Volunteers | Myanmar NGO",
     "Meet the RVTI team: Director Aung Aung Naing and the staff and volunteers working on education, health and resource governance in Rakhine and beyond.",
     f"""{page_head('Team', 'team.html', 'Our team', 'Staff and volunteers from Rakhine and Yangon, many of them long-time members of Renaissance Language Campus.')}
<section class="section"><div class="wrap"><ul class="team-grid">{members}</ul></div></section>
{partner_band()}""", ld=[crumbs_ld("Team", "team.html"), *[person(m) for m in team]], cur="team.html")

# ================= GOVERNANCE =================
meta, body, _ = page_md("governance")
o = structure["organogram"]; ed = o["children"][0]
chart = f"""<div class="orgchart" role="img" aria-label="Organogram: Board of Patrons, then Director, then Budget and Finance Team, Operation Team and Program Team">
  <div class="node top">{e(o['title'])}<small>{e(o['note'])}</small></div><div class="stem"></div>
  <div class="node mid">{e(ed['title'])}</div><div class="stem"></div>
  <div class="row">{''.join(f'<div class="node">{e(c["title"])}</div>' for c in ed['children'])}</div>
</div>"""
def role_html(r):
    parts = [f"<p>{e(r['summary'])}</p>"] if r["summary"] else []
    if r["duties"]:
        parts.append("<h3>Duties</h3>" + "".join(f"<h4>{e(d['area'])}</h4><ul>{''.join(f'<li>{e(i)}</li>' for i in d['items'])}</ul>" for d in r["duties"]))
    if r["criteria"]: parts.append("<h3>Criteria</h3><ul>" + "".join(f"<li>{e(i)}</li>" for i in r["criteria"]) + "</ul>")
    if r["responsibilities"]: parts.append("<h3>Responsibilities</h3><ul>" + "".join(f"<li>{e(i)}</li>" for i in r["responsibilities"]) + "</ul>")
    return f'<details id="{r["id"]}"><summary>{e(r["title"])}</summary><div class="body">{"".join(parts)}</div></details>'
gov = f"""{page_head('Governance', 'governance.html', 'Governance', 'How RVTI is structured, who is responsible for what, and how every kyat is approved, spent and reported.')}
<section class="section"><div class="wrap">
  <h2>Organizational structure</h2>{chart}
  <h3>Office positions</h3>
  <ul class="positions">{''.join(f'<li><strong>{e(p["title"])}</strong><span>{e(p["description"])}</span></li>' for p in structure['positions'])}</ul>
</div></section>
<section class="section section-tint"><div class="wrap">
  <h2>Roles, criteria and responsibilities</h2>
  <div class="roles measure">{''.join(role_html(r) for r in roles)}</div>
</div></section>
<section class="section"><div class="wrap"><div class="prose">{body}</div></div></section>
{partner_band()}"""
page("governance.html", "Governance and Financial Management | RVTI Myanmar",
     "RVTI's organizational structure, board and staff responsibilities, and financial controls: three-signature withdrawals, approved budgets and M&E reporting.",
     gov, ld=[crumbs_ld("Governance", "governance.html")], cur="governance.html")

# ================= POLICIES =================
meta, body, heads = page_md("policy-statement")
toc = '<nav class="toc" aria-labelledby="toc-title"><h2 id="toc-title">Contents</h2><ol>' + "".join(f'<li><a href="#{i}">{e(t)}</a></li>' for i, t in heads) + "</ol></nav>"
page("policies.html", "Policy Statement – Safeguarding, Finance and Procurement | RVTI",
     "RVTI's policy statement: safeguarding, conflict of interest, procurement, financial, diversity and inclusion, community engagement and sustainability policies.",
     f"""{page_head('Policies', 'policies.html', 'Policy statement', meta['description'])}
<section class="section"><div class="wrap with-toc">{toc}<div class="prose">{body}</div></div></section>
{partner_band()}""", ld=[crumbs_ld("Policies", "policies.html")], cur="policies.html")

# ================= CONTACT =================
fp = contact["focalPerson"]
tones = ["red", "yellow", "blue"]
offices = "".join(f"""<div class="office tone-{tones[i]}" style="--tone: var(--{tones[i]})"><h3>{e(o['name'])}</h3><address>{e(o['address'])}</address><a href="tel:{tel(o['phone'])}">{e(o['phone'])}</a></div>""" for i, o in enumerate(contact["offices"]))
people = "".join(f"""<li><strong>{e(c['name'])}</strong> <span>{e(c['role'])}</span><br><a href="tel:{tel(c['phone'])}">{e(c['phone'])}</a>{''.join(f' · <a href="mailto:{m}">{m}</a>' for m in c['emails'])}</li>""" for c in contact["primaryContacts"])
page("contact.html", "Contact RVTI – Offices in Yangon and Sittway, Myanmar",
     f"Contact the Renaissance Visionary Thriving Initiative. Email {contact['email']} or visit our offices in Yangon and Sittway, Myanmar.",
     f"""{page_head('Contact', 'contact.html', 'Contact us', 'Questions, partnerships or volunteering: write to us or call one of our offices.')}
<section class="section"><div class="wrap split">
  <div class="focal">
    <h2>Main contact</h2>
    <p><strong>{e(fp['name'])}</strong>, {e(fp['role'])}</p>
    <p><a href="tel:{tel(fp['phone'])}">{e(fp['phone'])}</a></p>
    <p><a href="mailto:{fp['email']}">{e(fp['email'])}</a></p>
  </div>
  <div><h2>Primary contacts</h2><ul class="contact-list">{people}</ul></div>
</div></section>
<section class="section section-tint"><div class="wrap">
  <h2>Our offices</h2><div class="contact-grid">{offices}</div>
</div></section>""", ld=[crumbs_ld("Contact", "contact.html"), {"@type": "ContactPage", "url": f"{SITE}/contact.html", "about": {"@id": ORG_ID}}], cur="contact.html")

# ================= 404 =================
page("404.html", "Page not found | RVTI", "The page you asked for does not exist.",
     f"""{page_head('Not found', '404.html', 'Page not found', 'This address does not match any page. Use the menu, or go back to the home page.')}
<section class="section"><div class="wrap"><a class="btn btn-primary" href="index.html">Go to the home page</a></div></section>""", noindex=True)

# ================= sitemap / robots / manifest =================
urls = ["", "about.html", "programs.html", "where-we-work.html", "activities.html", "team.html", "governance.html", "policies.html", "contact.html"]
open("sitemap.xml", "w").write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' +
    "".join(f"  <url><loc>{SITE}/{u}</loc><lastmod>{TODAY}</lastmod></url>\n" for u in urls) + "</urlset>\n")
open("robots.txt", "w").write(f"User-agent: *\nAllow: /\n\nSitemap: {SITE}/sitemap.xml\n")
json.dump({"name": site["name"], "short_name": "RVTI", "start_url": "/", "display": "standalone",
           "background_color": "#ffffff", "theme_color": "#151a4a",
           "icons": [{"src": "/favicon-512.png", "sizes": "512x512", "type": "image/png"},
                     {"src": "/apple-touch-icon.png", "sizes": "180x180", "type": "image/png"}]},
          open("site.webmanifest", "w"), indent=2)
print("ok")
