#!/usr/bin/env python3
"""Convert Justice Laws (laws-lois.justice.gc.ca) consolidated XML to LawCodex Markdown.

Input:  a checkout of https://github.com/justicecanada/laws-lois-xml
        (eng/acts, eng/regulations, fra/lois, fra/reglements, lookup/*.xml)
Output: <out>/en/acts, <out>/en/regulations, <out>/fr/lois, <out>/fr/reglements

Usage:  python convert_xml.py <laws-lois-xml-dir> <repo-dir>
"""
import datetime
import glob
import html
import os
import re
import sys
from concurrent.futures import ProcessPoolExecutor

import yaml
from lxml import etree

SITE = "https://laws-lois.justice.gc.ca"
RETRIEVED = datetime.date.today()

LANG = {
    "en": {"src": "eng", "acts": "acts", "regs": "regulations", "section": "Section",
           "site_acts": "eng/acts", "site_regs": "eng/regulations"},
    "fr": {"src": "fra", "acts": "lois", "regs": "reglements", "section": "Article",
           "site_acts": "fra/lois", "site_regs": "fra/reglements"},
}

UNIT_TAGS = {"Subsection", "Paragraph", "Subparagraph", "Clause", "Subclause", "Subsubclause",
             "Item", "FormulaParagraph", "Definition"}
CONTINUED = {"ContinuedSectionSubsection", "ContinuedParagraph", "ContinuedSubparagraph",
             "ContinuedClause", "ContinuedSubclause", "ContinuedDefinition",
             "ContinuedFormulaParagraph"}
QUOTED = {"AmendedText", "ReadAsText", "AmendedContent", "QuotedText"}
TRANSPARENT = {"Body", "Schedule", "Introduction", "Preamble", "Enacts", "Order", "FormGroup",
               "DocumentInternal", "RelatedOrNotInForce", "SectionPiece", "BillPiece",
               "RegulationPiece", "ReadAsContent", "Keep", "ConventionAgreementTreaty"}
SKIP = {"Identification", "RecentAmendments", "PageBreak", "LeaderRightJustified", "Label",
        "MarginalNote", "colspec"}


def norm(s):
    return re.sub(r"\s+", " ", s or "")


def esc_md(s):
    s = s.replace("\\", "\\\\")
    s = re.sub(r"([*_`])", r"\\\1", s)
    s = re.sub(r"<(?=[A-Za-z/!?])", r"&lt;", s)
    return s


def esc_html(s):
    return html.escape(s, quote=False)


class Renderer:
    def __init__(self, lang):
        self.lang = lang
        self.out = []
        self.cur_h = 1
        self.base = 1          # heading level offset (1 in Body, 2 in schedules)
        self.quote = 0
        self.pending = []      # footnotes found inline

    # ---------- inline ----------
    def inline(self, e, mode="md", with_tail=False):
        esc = esc_md if mode == "md" else esc_html
        parts = [esc(norm(e.text))]
        for c in e:
            if isinstance(c.tag, str):
                parts.append(self.inline_el(c, mode))
            if c.tail:
                parts.append(esc(norm(c.tail)))
        s = "".join(parts)
        return s

    def inline_el(self, c, mode):
        t = c.tag
        md = mode == "md"
        inner = lambda: self.inline(c, mode).strip()
        if t == "Emphasis":
            s = inner()
            if not s:
                return ""
            st = c.get("style", "italic")
            if st == "bold":
                return f"**{s}**" if md else f"<strong>{s}</strong>"
            if st == "italic":
                return f"*{s}*" if md else f"<em>{s}</em>"
            return s
        if t in ("DefinedTermEn", "DefinedTermFr", "DefinitionEnOnly"):
            s = inner()
            return (f"***{s}***" if md else f"<strong><em>{s}</em></strong>") if s else ""
        if t == "DefinitionRef":
            s = inner()
            return (f"*{s}*" if md else f"<em>{s}</em>") if s else ""
        if t in ("Sup", "Superscript", "MSup", "FootnoteRef"):
            return f"<sup>{inner()}</sup>"
        if t in ("Sub", "Subscript", "MSub"):
            return f"<sub>{inner()}</sub>"
        if t in ("Leader", "LeaderRightJustified"):
            return " … "
        if t == "FormBlank":
            return "\\_\\_\\_\\_\\_\\_\\_\\_" if md else "________"
        if t == "LineBreak":
            return "<br>"
        if t == "Fraction":
            n = c.find("Numerator")
            d = c.find("Denominator")
            return f"{self.inline(n, mode).strip() if n is not None else ''}/" \
                   f"{self.inline(d, mode).strip() if d is not None else ''}"
        if t == "ImageGroup":
            return self.image_md(c) if md else self.image_html(c)
        if t == "Footnote":
            self.pending.append(c)
            return ""
        if t == "BilingualGroup":
            items = [self.inline(x, mode).strip() for x in c if isinstance(x.tag, str)]
            pairs = [" / ".join(items[i:i + 2]) for i in range(0, len(items), 2)]
            return "<br>".join(pairs)
        if t in ("Label",) and mode == "cell":
            return inner()
        # block-ish elements met in inline context: flatten
        if len(c) and any(isinstance(x.tag, str) and x.tag in BLOCKISH for x in c):
            return "<br>".join(filter(None, (self.flat(x, mode) for x in c if isinstance(x.tag, str))))
        return self.inline(c, mode)

    def flat(self, e, mode):
        """Flatten a block element to a single line (for table cells)."""
        if e.tag in SKIP and e.tag not in ("Label", "MarginalNote"):
            return ""
        if e.tag == "Label":
            return self.inline(e, mode).strip()
        if len(e) and any(isinstance(x.tag, str) and x.tag in BLOCKISH for x in e):
            parts = []
            lab = e.find("Label")
            for x in e:
                if not isinstance(x.tag, str):
                    continue
                if x.tag == "Label":
                    continue
                s = self.flat(x, mode)
                if s:
                    parts.append(s)
            if lab is not None and parts:
                parts[0] = self.inline(lab, mode).strip() + " " + parts[0]
            return "<br>".join(parts)
        lab = e.find("Label")
        txt = self.inline_el(e, mode).strip()
        return txt

    def image_md(self, g):
        alt = norm(g.findtext("AlternateText") or "").strip()
        imgs = [f"![{alt.replace(']', ')')}]({SITE}/images/{i.get('source')})" for i in g.iter("Image")]
        return " ".join(imgs)

    def image_html(self, g):
        alt = html.escape(norm(g.findtext("AlternateText") or "").strip())
        return " ".join(f'<img src="{SITE}/images/{i.get("source")}" alt="{alt}">' for i in g.iter("Image"))

    def text_of(self, e):
        return re.sub(r" {2,}", " ", self.inline(e).strip())

    # ---------- block output ----------
    def block(self, text, depth=-1, bullet=False):
        text = text.strip("\n")
        if not text.strip():
            return
        lines = text.split("\n")
        if not bullet and depth < 0:
            m = lines[0]
            if re.match(r"^(\d+)([.)])(\s|$)", m):
                lines[0] = re.sub(r"^(\d+)([.)])", r"\1\\\2", m)
            elif re.match(r"^([#>+\-=]|\d+\.)(\s|$)", m):
                lines[0] = "\\" + m
        if bullet:
            ind = "  " * depth
            out = [ind + "- " + lines[0]] + [ind + "  " + l if l else "" for l in lines[1:]]
        else:
            ind = "  " * (depth + 1) if depth >= 0 else ""
            out = [ind + l if l else "" for l in lines]
        if self.quote:
            q = "> " * self.quote
            out = [(q + l).rstrip() if l else q.rstrip() for l in out]
        self.out.append("\n".join(out))
        self.flush_footnotes(depth)

    def flush_footnotes(self, depth):
        while self.pending:
            fn = self.pending.pop(0)
            self.footnote(fn, depth)

    def footnote(self, fn, depth):
        lab = norm(fn.findtext("Label") or "").strip()
        body = " ".join(self.text_of(t) for t in fn if isinstance(t.tag, str) and t.tag != "Label")
        self.block(f"<sup>{lab}</sup> {body}".strip(), depth)

    def heading(self, level, text):
        text = text.strip()
        if not text:
            return
        if self.quote or level > 6:
            self.block(f"**{text}**")
            return
        self.out.append("#" * level + " " + text)
        self.cur_h = level

    # ---------- structure ----------
    def heading_text(self, e):
        parts = []
        for tag in ("Label", "TitleText"):
            for x in e.findall(tag):
                s = self.text_of(x)
                if s:
                    parts.append(s)
        s = " — ".join(parts)
        o = e.find("OriginatingRef")
        if o is not None and self.text_of(o):
            s += " " + self.text_of(o)
        return s

    def section(self, e):
        label = norm(e.findtext("Label") or "").strip()
        mn = e.find("MarginalNote")
        mn = self.text_of(mn) if mn is not None else ""
        lvl = min(self.cur_h + 1, 7) if self.cur_h >= self.base else self.base + 1
        if self.quote or lvl > 6:
            self.unit(e, -1)
            return
        title = LANG[self.lang]["section"] + (f" {label}" if label else "")
        if mn:
            title += f" — {mn}"
        saved = self.cur_h
        self.out.append("#" * lvl + " " + title)
        self.cur_h = saved   # sections do not deepen the heading context
        self.unit(e, -1, label_in_heading=True)

    def unit(self, e, depth, label_in_heading=False):
        label = e.find("Label")
        label = self.text_of(label) if label is not None else ""
        mn = e.find("MarginalNote") if not label_in_heading else None
        mn = self.text_of(mn) if mn is not None else ""
        first_text = None
        for c in e:
            if isinstance(c.tag, str) and c.tag == "Text":
                first_text = c
                break
        if e.tag == "FormulaDefinition":
            term = e.find("FormulaTerm")
            label = f"*{self.text_of(term)}*" if term is not None else ""
        main = self.text_of(first_text) if first_text is not None else ""
        lead = []
        if mn:
            lead.append(f"*{mn}*")
        line = ""
        if label and not label_in_heading:
            line = f"**{label}**" if e.tag != "FormulaDefinition" else label
        if main:
            line = f"{line} {main}".strip()
        if lead and line:
            text = lead[0] + "\\\n" + line
        else:
            text = (lead[0] if lead else "") + line
        bullet = depth >= 0
        if text:
            self.block(text, depth, bullet=bullet)
        elif bullet and label:
            # an item without own text: emit its label as the bullet
            self.block(f"**{label}**", depth, bullet=True)
            text = "x"
        child_depth = depth + 1
        cont_depth = depth
        if not text and bullet:
            # unlabelled container without text: children stay at the same level
            child_depth = depth
            cont_depth = depth - 1
        for c in e:
            if not isinstance(c.tag, str) or c is first_text:
                continue
            t = c.tag
            if t in ("Label", "MarginalNote", "FormulaTerm"):
                continue
            if t in UNIT_TAGS or t == "FormulaDefinition" or (t == "Provision" and c.find("Label") is not None):
                if t in ("Definition", "Subsection") and depth < 0:
                    self.unit(c, -1)
                else:
                    self.unit(c, child_depth)
            elif t in CONTINUED or t == "Text":
                self.render_children_as_text(c, cont_depth)
            else:
                self.block_el(c, cont_depth if (text or depth < 0) else depth)

    def render_children_as_text(self, c, depth):
        if any(isinstance(x.tag, str) and x.tag == "Text" for x in c) or c.tag != "Text" and len(c):
            for x in c:
                if isinstance(x.tag, str):
                    if x.tag == "Text":
                        self.block(self.text_of(x), depth)
                    else:
                        self.block_el(x, depth)
        else:
            self.block(self.text_of(c), depth)

    def block_el(self, c, depth=-1):
        t = c.tag
        if not isinstance(t, str) or t in SKIP:
            return
        if t == "Heading":
            txt = self.heading_text(c)
            if depth >= 0 or self.quote:
                self.block(f"**{txt}**", depth)
            else:
                lvl = int(c.get("level", "1") or 1) + self.base
                self.heading(min(lvl, 7), txt)
        elif t == "Section":
            if depth >= 0:
                self.unit(c, depth)
            else:
                self.section(c)
        elif t in UNIT_TAGS or t == "FormulaDefinition":
            self.unit(c, depth if t == "Definition" and depth < 0 else depth + 1 if depth >= 0 else 0
                      if t != "Subsection" else -1)
        elif t == "Provision":
            if c.find("Label") is not None:
                self.unit(c, depth + 1 if depth >= 0 else 0)
            else:
                self.unit(c, depth)
        elif t == "Text":
            self.block(self.text_of(c), depth)
        elif t == "Repealed" or t == "Oath" or t == "Note" or t == "FormulaConnector":
            self.block(self.text_of(c), depth)
        elif t == "ReaderNote":
            for x in c:
                self.block_el(x, depth)
        elif t == "HistoricalNote":
            items = [self.text_of(x) for x in c if isinstance(x.tag, str)]
            items = [i for i in items if i]
            if not items and self.text_of(c):
                items = [self.text_of(c)]
            if items:
                self.block("*" + "; ".join(items) + "*", depth)
        elif t == "Footnote":
            self.footnote(c, depth)
        elif t == "Formula":
            ft = c.find("FormulaText")
            self.block(self.text_of(ft if ft is not None else c), depth)
        elif t == "FormulaGroup":
            for x in c:
                if not isinstance(x.tag, str):
                    continue
                if x.tag == "FormulaDefinition" or x.tag == "FormulaParagraph":
                    self.unit(x, depth + 1 if depth >= 0 else 0)
                else:
                    self.block_el(x, depth)
        elif t in ("TableGroup", "table"):
            self.table_group(c, depth)
        elif t == "List":
            for x in c:
                if isinstance(x.tag, str):
                    if x.tag == "Item":
                        self.unit(x, depth + 1 if depth >= 0 else 0)
                    else:
                        self.block_el(x, depth)
        elif t == "ImageGroup":
            self.block(self.image_md(c), depth)
        elif t == "BilingualGroup":
            items = [self.text_of(x).replace("|", "\\|") for x in c if isinstance(x.tag, str)]
            rows = ["| | |", "|---|---|"]
            for i in range(0, len(items), 2):
                rows.append("| " + " | ".join((items[i:i + 2] + [""])[:2]) + " |")
            self.block("\n".join(rows), depth)
        elif t == "SignatureBlock":
            lines = [self.text_of(x) for x in c if isinstance(x.tag, str)]
            self.block("\\\n".join(l for l in lines if l), depth)
        elif t in ("GroupHeading", "ScheduleFormHeading") and (depth >= 0 or c.getparent().tag != "Schedule"):
            self.block(f"**{self.heading_text(c)}**", depth)
        elif t == "ScheduleFormHeading":
            self.heading(2, self.heading_text(c))
        elif t == "Group":
            for x in c:
                self.block_el(x, depth)
        elif t in QUOTED:
            self.quote += 1
            for x in c:
                self.block_el(x, depth if depth >= 0 else -1)
            self.quote -= 1
        elif t in TRANSPARENT:
            for x in c:
                self.block_el(x, depth)
        elif t in ("Caption", "title"):
            s = self.text_of(c)
            if s:
                self.block(f"**{s}**", depth)
        else:
            if len(c) and any(isinstance(x.tag, str) and x.tag in BLOCKISH for x in c):
                for x in c:
                    self.block_el(x, depth)
            else:
                self.block(self.text_of(c), depth)

    # ---------- tables ----------
    def table_group(self, tg, depth):
        tables = [tg] if tg.tag == "table" else []
        for x in tg:
            if not isinstance(x.tag, str):
                continue
            if x.tag == "table":
                tables.append(x)
            elif x.tag != "table" and tg.tag != "table":
                self.block_el(x, depth)
        for tb in tables:
            title = tb.find("title")
            if title is not None and self.text_of(title):
                self.block(f"**{self.text_of(title)}**", depth)
            for tgr in tb.findall("tgroup"):
                self.tgroup(tgr, depth)

    def tgroup(self, tg, depth):
        names = [cs.get("colname") for cs in tg.findall("colspec")]
        try:
            ncols = int(tg.get("cols") or len(names) or 1)
        except ValueError:
            ncols = len(names) or 1
        head = [r for th in tg.findall("thead") for r in th.findall("row")]
        body = [r for tb in tg.findall("tbody") for r in tb.findall("row")]
        spans = any(en.get("morerows") or en.get("namest") or en.get("spanname")
                    for r in head + body for en in r.findall("entry"))
        if not spans:
            n = max([ncols] + [len(r.findall("entry")) for r in head + body])
            ncols = n

            def rowcells(r):
                cs = [self.cell(en, "md").replace("|", "\\|").replace("\n", " ") for en in r.findall("entry")]
                return (cs + [""] * ncols)[:ncols]

            def cells(r):
                return "| " + " | ".join(rowcells(r)) + " |"
            if head:
                hc = [rowcells(r) for r in head]
                hdr = ["<br>".join(h[i] for h in hc if h[i]) for i in range(ncols)]
                hdr_line = "| " + " | ".join(hdr) + " |"
            else:
                hdr_line = "| " + " | ".join([" "] * ncols) + " |"
            lines = [hdr_line, "|" + "---|" * ncols]
            lines += [cells(r) for r in body]
            self.block("\n".join(lines), depth)
            return
        idx = {n: i for i, n in enumerate(names)}
        out = ["<table>"]
        for sect, rows, cell in (("thead", head, "th"), ("tbody", body, "td")):
            if not rows:
                continue
            out.append(f"<{sect}>")
            for r in rows:
                tds = []
                for en in r.findall("entry"):
                    attrs = ""
                    ns, ne = en.get("namest"), en.get("nameend")
                    if ns in idx and ne in idx and idx[ne] > idx[ns]:
                        attrs += f' colspan="{idx[ne] - idx[ns] + 1}"'
                    mr = en.get("morerows")
                    if mr and mr.isdigit() and int(mr) > 0:
                        attrs += f' rowspan="{int(mr) + 1}"'
                    tds.append(f"<{cell}{attrs}>{self.cell(en, 'html')}</{cell}>")
                out.append("<tr>" + "".join(tds) + "</tr>")
            out.append(f"</{sect}>")
        out.append("</table>")
        self.block("\n".join(out), depth)

    def cell(self, en, mode):
        if any(isinstance(x.tag, str) and x.tag in BLOCKISH for x in en):
            parts = []
            if norm(en.text).strip():
                parts.append((esc_md if mode == "md" else esc_html)(norm(en.text).strip()))
            for x in en:
                if not isinstance(x.tag, str):
                    continue
                s = self.flat(x, mode) if x.tag in BLOCKISH else self.inline_el(x, mode)
                if s:
                    parts.append(s.strip())
                if x.tail and norm(x.tail).strip():
                    parts.append((esc_md if mode == "md" else esc_html)(norm(x.tail).strip()))
            s = "<br>".join(parts)
        else:
            s = self.inline(en, mode)
        s = re.sub(r" {2,}", " ", s).strip()
        # inline footnotes inside tables: append text
        while self.pending:
            fn = self.pending.pop(0)
            s += " <sup>" + norm(fn.findtext("Label") or "") + "</sup> " + \
                 " ".join(self.inline(t, mode).strip() for t in fn if isinstance(t.tag, str) and t.tag != "Label")
        return s


BLOCKISH = UNIT_TAGS | CONTINUED | QUOTED | TRANSPARENT | {
    "Section", "Provision", "Text", "List", "TableGroup", "table", "Heading", "HistoricalNote",
    "Footnote", "FormulaGroup", "Formula", "FormulaDefinition", "SignatureBlock", "Group",
    "GroupHeading", "ScheduleFormHeading", "Note", "ReaderNote", "Oath", "BilingualGroup",
    "SignatureName", "SignatureTitle", "SignatureLine", "Caption", "title", "FormulaConnector"}


# ---------------------------------------------------------------------------
def ymd(d):
    if d is None:
        return None
    try:
        return datetime.date(int(d.findtext("YYYY")), int(d.findtext("MM") or 1), int(d.findtext("DD") or 1))
    except (TypeError, ValueError):
        return None


def isodate(s):
    try:
        return datetime.date.fromisoformat(s[:10]) if s else None
    except ValueError:
        return None


def act_slug(ch):
    return re.sub(r"[^a-z0-9]+", "-", ch.lower()).strip("-")


def reg_path(fname, lang):
    """Return relative dir + slug for a regulation file name (without .xml)."""
    base = fname[:-4]
    m = re.match(r"^(SOR|SI|DORS|TR)-(\d{2,4})-(\w+)$", base)
    if m:
        kind, yr = m.group(1).lower(), m.group(2)
        year = yr if len(yr) == 4 else "19" + yr
        return f"{kind}/{year}", f"{kind}-{yr}-{m.group(3).lower()}"
    m = re.match(r"^C\.R\.C\.,_(c|ch)\._(\d+\w*)$", base)
    if m:
        return "crc", f"crc-{m.group(1)}-{m.group(2).lower()}"
    return "other", act_slug(base)


def load_lookup(path):
    t = etree.parse(path)
    acts, regs = {}, {}
    for s in t.iter("Statute"):
        acts[(s.findtext("Language"), s.findtext("ChapterNumber"))] = {
            "official": s.findtext("OfficialNumber"), "title": s.findtext("ShortTitle")}
    for s in t.iter("Regulation"):
        regs[(s.findtext("Language"), s.findtext("AlphaNumber"))] = {"title": s.findtext("ShortTitle")}
    return acts, regs


LOOKUP = {}


def init_lookup(src):
    LOOKUP["cur"] = load_lookup(os.path.join(src, "lookup", "lookup.xml"))
    LOOKUP["full"] = load_lookup(os.path.join(src, "lookup", "lookupfull.xml"))


def convert(args):
    path, lang, kind, outroot, src = args
    if not LOOKUP:
        init_lookup(src)
    root = etree.parse(path).getroot()
    for el in root.iter():  # strip namespaces from tags
        if isinstance(el.tag, str) and "}" in el.tag:
            el.tag = el.tag.split("}", 1)[1]
    L = LANG[lang]
    fname = os.path.basename(path)
    ident = root.find("Identification")
    fm = {}
    if kind == "act":
        ch = norm(ident.findtext("Chapter/ConsolidatedNumber") or fname[:-4]).strip()
        lk = LOOKUP["cur"][0].get((lang, ch))
        lkf = LOOKUP["full"][0].get((lang, ch))
        st = ident.find("ShortTitle")
        lt = ident.find("LongTitle")
        title = norm(etree.tostring(st, method="text", encoding="unicode")).strip() if st is not None else ""
        long_title = norm(etree.tostring(lt, method="text", encoding="unicode")).strip() if lt is not None else ""
        if not title:
            title = (lk or lkf or {}).get("title") or long_title or ch
        status = "in_force" if lk else ("repealed" if lkf else "unknown")
        assent = None
        consol = None
        for stg in ident.iter("Stages"):
            if stg.get("stage") == "assented-to":
                assent = ymd(stg.find("Date"))
            elif stg.get("stage") == "consolidation":
                consol = ymd(stg.find("Date"))
        official = (lk or lkf or {}).get("official")
        fm = {"title": title, "identifier": ch}
        if official and official != ch:
            fm["citation"] = official
        if long_title and long_title != title:
            fm["long_title"] = long_title
        fm.update({"type": "act", "jurisdiction": "ca", "language": lang})
        if assent:
            fm["date"] = assent
        lam = isodate(root.get("{http://justice.gc.ca/lims}lastAmendedDate"))
        if lam:
            fm["last_amended"] = lam
        if consol:
            fm["consolidated"] = consol
        fm["status"] = status
        if root.get("in-force") == "no":
            fm["note"] = "not in force"
        fm["source"] = f"{SITE}/{L['site_acts']}/{fname[:-4]}/"
        rel = os.path.join(lang, L["acts"], act_slug(ch) + ".md")
    else:
        num = norm(ident.findtext("InstrumentNumber") or fname[:-4]).strip()
        lk = LOOKUP["cur"][1].get((lang, num))
        lkf = LOOKUP["full"][1].get((lang, num))
        lt = ident.find("LongTitle")
        long_title = norm(etree.tostring(lt, method="text", encoding="unicode")).strip() if lt is not None else ""
        st = ident.find("ShortTitle")
        title = norm(etree.tostring(st, method="text", encoding="unicode")).strip() if st is not None else ""
        title = title or long_title or (lk or lkf or {}).get("title") or num
        status = "in_force" if lk else ("repealed" if lkf else "unknown")
        fm = {"title": title, "identifier": num}
        if long_title and long_title != title:
            fm["long_title"] = long_title
        fm.update({"type": "regulation", "jurisdiction": "ca", "language": lang})
        reg = ymd(ident.find("RegistrationDate/Date"))
        if reg:
            fm["date"] = reg
        lam = isodate(root.get("{http://justice.gc.ca/lims}lastAmendedDate"))
        if lam:
            fm["last_amended"] = lam
        cd = ymd(ident.find("ConsolidationDate/Date"))
        if cd:
            fm["consolidated"] = cd
        fm["status"] = status
        ea = [norm(etree.tostring(x, method="text", encoding="unicode")).strip()
              for x in ident.findall("EnablingAuthority")]
        ea = [x for x in ea if x]
        if ea:
            fm["enabling_authority"] = ea if len(ea) > 1 else ea[0]
        fm["source"] = f"{SITE}/{L['site_regs']}/{fname[:-4]}/"
        d, slug = reg_path(fname, lang)
        rel = os.path.join(lang, L["regs"], d, slug + ".md")
    fm["retrieved"] = RETRIEVED

    r = Renderer(lang)
    r.out.append("# " + fm["title"].replace("\n", " "))
    if fm.get("long_title"):
        r.block(r.text_of(ident.find("LongTitle")))
    for c in root:
        if not isinstance(c.tag, str) or c.tag in ("Identification", "RecentAmendments"):
            continue
        if c.tag == "Schedule":
            r.base = 2
            r.cur_h = 1
            hd = c.find("ScheduleFormHeading")
            if hd is None:
                r.heading(2, "Schedule" if lang == "en" else "Annexe")
        elif c.tag == "Body":
            r.base = 1
            r.cur_h = 1
        r.block_el(c, -1)
    body = "\n\n".join(r.out).rstrip() + "\n"
    body = re.sub(r"[ \t]+\n", "\n", body)
    head = yaml.safe_dump(fm, allow_unicode=True, sort_keys=False, width=10000)
    dest = os.path.join(outroot, rel)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "w", encoding="utf-8", newline="\n") as f:
        f.write("---\n" + head + "---\n\n" + body)
    return rel, fm["status"], kind, lang


def main():
    src, out = sys.argv[1], sys.argv[2]
    only = sys.argv[3] if len(sys.argv) > 3 else None   # e.g. "en:act"
    jobs = []
    for lang in ("en", "fr"):
        L = LANG[lang]
        for kind, sub in (("act", L["acts"]), ("reg", L["regs"])):
            if only and only != f"{lang}:{kind}":
                continue
            for p in sorted(glob.glob(os.path.join(src, L["src"], sub, "*.xml"))):
                jobs.append((p, lang, kind, out, src))
    seen = {}
    errors = []
    with ProcessPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(convert, j): j for j in jobs}
        for fu, j in futs.items():
            try:
                rel, status, kind, lang = fu.result()
            except Exception as e:  # noqa
                errors.append((j[0], repr(e)))
                continue
            if rel in seen:
                errors.append((j[0], f"path collision with {seen[rel]}: {rel}"))
            seen[rel] = j[0]
    print(f"converted {len(seen)} files, {len(errors)} errors")
    for e in errors:
        print("ERROR", *e)


if __name__ == "__main__":
    main()
