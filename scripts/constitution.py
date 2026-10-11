#!/usr/bin/env python3
"""Fetch the consolidated Constitution Acts 1867 to 1982 from Justice Laws and convert to Markdown.

Source pages (official consolidation, HTML; no XML is published for this document):
  https://laws-lois.justice.gc.ca/eng/Const/FullText.html
  https://laws-lois.justice.gc.ca/fra/Const/TexteComplet.html

Output: <repo>/{en,fr}/constitution/{constitution-act-1867,canada-act-1982,constitution-act-1982}.md
Usage:  python constitution.py <raw-cache-dir> <repo-dir>
"""
import datetime
import os
import re
import sys
import time

import requests
import yaml
from bs4 import BeautifulSoup, NavigableString
from markdownify import markdownify

UA = "LawCodex/1.0 (+https://github.com/LawCodex)"
PAGES = {
    "en": "https://laws-lois.justice.gc.ca/eng/Const/FullText.html",
    "fr": "https://laws-lois.justice.gc.ca/fra/Const/TexteComplet.html",
}
DOCS = {
    # slug: (en title, fr title, date, identifier en, identifier fr)
    "constitution-act-1867": ("Constitution Act, 1867", "Loi constitutionnelle de 1867", datetime.date(1867, 3, 29),
                              "30 & 31 Victoria, c. 3 (U.K.)", "30 & 31 Victoria, ch. 3 (R.-U.)"),
    "canada-act-1982": ("Canada Act 1982", "Loi de 1982 sur le Canada", datetime.date(1982, 3, 29),
                        "1982, c. 11 (U.K.)", "1982, ch. 11 (R.-U.)"),
    "constitution-act-1982": ("Constitution Act, 1982", "Loi constitutionnelle de 1982", datetime.date(1982, 4, 17),
                              "Schedule B to the Canada Act 1982, 1982, c. 11 (U.K.)",
                              "Annexe B de la Loi de 1982 sur le Canada, 1982, ch. 11 (R.-U.)"),
}
SECTION_WORD = {"en": "Section", "fr": "Article"}


def fetch(url, dest):
    if os.path.exists(dest) and os.path.getsize(dest) > 10000:
        return open(dest, encoding="utf-8").read()
    for attempt in range(5):
        try:
            r = requests.get(url, headers={"User-Agent": UA}, timeout=120)
            r.raise_for_status()
            r.encoding = "utf-8"
            with open(dest, "w", encoding="utf-8") as f:
                f.write(r.text)
            return r.text
        except requests.RequestException:
            time.sleep(2 ** attempt * 5)
    raise RuntimeError(f"failed to fetch {url}")


def md(nodes):
    html = "".join(str(n) for n in nodes)
    out = markdownify(html, heading_style="ATX", bullets="-", strong_em_symbol="*",
                      escape_underscores=True, escape_asterisks=True)
    out = re.sub(r"\n{3,}", "\n\n", out)
    out = re.sub(r"[ \t]+\n", "\n", out)
    out = re.sub(r"(?m)^[ \u00a0]+(?=[^ \u00a0\-*+\d])", "", out)
    return out.strip()


def convert(lang, html, outdir, retrieved):
    soup = BeautifulSoup(html, "lxml")
    mod = soup.find("time", attrs={"property": "dateModified"})
    modified = None
    if mod:
        try:
            modified = datetime.date.fromisoformat(mod.get_text().strip().lstrip("﻿"))
        except ValueError:
            pass
    doc = soup.find("div", class_="docContents")
    for s in doc.select(".wb-invisible"):
        s.decompose()
    # endnote references -> markdown footnotes
    for a in doc.find_all("a", href=re.compile(r"#endf?\d+$")):
        n = re.search(r"endf?(\d+)$", a["href"]).group(1)
        a.replace_with(NavigableString(f"[^{n}]"))
    # collect endnotes
    endnotes = {}
    for p in doc.find_all("p", id=re.compile(r"^endf?\d+$")):
        n = re.sub(r"\D", "", p["id"])
        td = p.find_parent(["td", "th"])
        cell = td.find_next_sibling(["td", "th"]) if td is not None else None
        if cell is None:
            continue
        for st in cell.find_all("strong"):
            if st.find(class_="sectionLabel") is None and st.find_parent(class_="sectionLabel") is None:
                st.unwrap()
        endnotes[n] = md(cell.contents)
    ends = doc.find("span", class_="scheduleLabel", string=re.compile(r"ENDNOTES|NOTES"))
    end_section = ends.find_parent("section") if ends else None
    if end_section is not None:
        end_section.decompose()
    # act-title headings (classless h2) used to split the document
    body = doc.find("div", class_="wb-txthl") or doc
    splits = [h for h in body.find_all("h2") if not h.get("class")]
    for h in doc.find_all(["h2", "h3", "h4", "h5"]):
        lab = h.find("span", class_=re.compile(r"^HLabel"))
        if lab is not None and h.find("span", class_=re.compile(r"^HTitleText")) is not None:
            lab.append(NavigableString(" — "))
    # Sections: marginal note + section label -> heading
    level = 1
    for el in doc.find_all(["h2", "h3", "h4", "h5", "a"]):
        if el.name != "a":
            if el.get("class") and ("Title-of-Act" in el["class"]):
                level = 1
            elif el.name == "h2" and not el.get("class") or "generated" in (el.get("class") or []):
                if el.name == "h2" and not el.get("class"):
                    level = 1
                continue
            else:
                level = int(el.name[1])
            continue
        if "sectionLabel" not in (el.get("class") or []):
            continue
        label = el.get_text().strip()
        strong = el.find_parent("strong")
        p = el.find_parent("p")
        if not label or p is None:
            continue
        container = p
        if p.parent and p.parent.name == "li":
            ul = p.parent.parent
            if ul is not None and ul.name == "ul" and p.parent == ul.find("li"):
                container = ul
        mn = container.find_previous_sibling()
        note = ""
        if mn is not None and mn.name == "p" and "MarginalNote" in (mn.get("class") or []):
            note = mn.get_text(" ", strip=True)
            mn.decompose()
        h = soup.new_tag(f"h{min(level + 1, 6)}", attrs={"class": "generated"})
        h.string = f"{SECTION_WORD[lang]} {label}" + (f" — {note}" if note else "")
        container.insert_before(h)
        (strong or el).decompose()
    for p in doc.find_all("p", class_="MarginalNote"):
        em = soup.new_tag("em")
        em.string = p.get_text(" ", strip=True)
        p.clear()
        p.append(em)
    # split into documents
    container = splits[0].parent
    assert splits[1].parent is container
    chain = []
    el = container
    while el is not body:
        chain.append(el)
        el = el.parent
    top = chain[-1]
    def ix(seq, x):
        return next(i for i, y in enumerate(seq) if y is x)
    nodes = list(body.children)
    before = nodes[:ix(nodes, top)]
    after = nodes[ix(nodes, top) + 1:]
    kids = list(container.children)
    i0, i1 = ix(kids, splits[0]), ix(kids, splits[1])
    if container is not top:
        raise RuntimeError("unexpected nesting of act headings")
    parts = {
        "constitution-act-1867": before + kids[:i0],
        "canada-act-1982": kids[i0:i1],
        "constitution-act-1982": kids[i1:] + after,
    }
    os.makedirs(outdir, exist_ok=True)
    written = []
    for slug, ns in parts.items():
        en_t, fr_t, date, id_en, id_fr = DOCS[slug]
        title = en_t if lang == "en" else fr_t
        text = md(ns)
        # drop the act's own title heading (it becomes the H1)
        m = re.match(r"^#+ [^\n]*(CONSTITUTION ACT, 1867|LOI CONSTITUTIONNELLE DE 1867|CANADA ACT 1982|"
                     r"LOI DE 1982 SUR LE CANADA|CONSTITUTION ACT, 1982|LOI CONSTITUTIONNELLE DE 1982)[^\n]*\n", text)
        h1_refs = ""
        if m:
            h1_refs = "".join(re.findall(r"\[\^\d+\]", m.group(0)))
            text = text[m.end():]
        refs = sorted(set(re.findall(r"\[\^(\d+)\]", h1_refs + text)), key=int)
        notes = []
        for n in refs:
            body_n = endnotes.get(n, "")
            lines = body_n.split("\n")
            notes.append(f"[^{n}]: " + lines[0] + "".join("\n    " + l if l else "\n" for l in lines[1:]))
        fm = {
            "title": title,
            "identifier": id_en if lang == "en" else id_fr,
            "type": "constitution",
            "jurisdiction": "ca",
            "language": lang,
            "date": date,
        }
        if modified:
            fm["last_amended"] = modified
        fm["status"] = "in_force"
        fm["source"] = PAGES[lang]
        fm["retrieved"] = retrieved
        out = "---\n" + yaml.safe_dump(fm, allow_unicode=True, sort_keys=False, width=10000) + "---\n\n"
        out += f"# {title}{h1_refs}\n\n" + text.strip() + "\n"
        if notes:
            out += "\n## " + ("Endnotes" if lang == "en" else "Notes") + "\n\n" + "\n\n".join(notes) + "\n"
        path = os.path.join(outdir, slug + ".md")
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(out)
        written.append(path)
    return written


def main():
    raw, repo = sys.argv[1], sys.argv[2]
    os.makedirs(raw, exist_ok=True)
    retrieved = datetime.date.today()
    for lang, url in PAGES.items():
        html = fetch(url, os.path.join(raw, f"const-{lang}.html"))
        for p in convert(lang, html, os.path.join(repo, lang, "constitution"), retrieved):
            print(p)
        time.sleep(1)


if __name__ == "__main__":
    main()
