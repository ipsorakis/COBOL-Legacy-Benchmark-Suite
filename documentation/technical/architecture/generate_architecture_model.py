#!/usr/bin/env python3
"""Render the CLBS architecture model as an engineering-standard formatted PDF.

Reads architecture-model.yaml and produces CLBS-A-001-architecture-model.pdf
using the cover, header, footer, section, commentary-note and appendix layout of
the Saudi Aramco engineering standard template.

Usage:
    pip install reportlab pyyaml
    python generate_architecture_model.py
"""

from __future__ import annotations

import os
from typing import Callable

import yaml
from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas as pdfcanvas

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(HERE, "architecture-model.yaml")
OUT_PATH = os.path.join(HERE, "CLBS-A-001-architecture-model.pdf")

PAGE_W, PAGE_H = letter
LEFT = 72.0
RIGHT = 540.0
BODY_TOP = PAGE_H - 124.0
BODY_BOTTOM = PAGE_H - 700.0

BODY_FONT = ("Times-Roman", 12.0, 13.7)
ITALIC_FONT = ("Times-Italic", 12.0, 13.7)
HEAD_FONT = ("Helvetica-Bold", 12.0, 14.0)
NOTE_FONT = ("Helvetica-Oblique", 10.0, 12.0)
TABLE_FONT = ("Helvetica", 8.5, 10.5)
TABLE_HEAD_FONT = ("Helvetica-Bold", 8.5, 10.5)

RULE = HexColor("#7f7f7f")
SHADE = HexColor("#e8e8e8")


def wrap(text: str, font: str, size: float, width: float) -> list[str]:
    lines: list[str] = []
    for hard in text.split("\n"):
        cur = ""
        for word in hard.split():
            while stringWidth(word, font, size) > width:
                if cur:
                    lines.append(cur)
                    cur = ""
                cut = len(word)
                while cut > 1 and stringWidth(word[:cut], font, size) > width:
                    cut -= 1
                boundary = max(word.rfind(sep, 1, cut) for sep in "_.-")
                if boundary > 0:
                    cut = boundary + 1
                lines.append(word[:cut])
                word = word[cut:]
            trial = f"{cur} {word}".strip()
            if stringWidth(trial, font, size) <= width or not cur:
                cur = trial
            else:
                lines.append(cur)
                cur = word
        lines.append(cur)
    return lines


class Renderer:
    """Single-pass renderer; run twice to resolve page numbers and page count."""

    def __init__(self, doc: dict, total_pages: int | None):
        self.doc = doc
        self.total_pages = total_pages
        self.canvas = pdfcanvas.Canvas(OUT_PATH, pagesize=letter)
        self.page = 1
        self.y = BODY_TOP
        self.heading_pages: dict[str, int] = {}

    # -- page furniture ---------------------------------------------------
    def _page_label(self) -> str:
        total = self.total_pages if self.total_pages else "N"
        return f"Page {self.page} of {total}"

    def _footer(self) -> None:
        c = self.canvas
        c.setFont("Times-Roman", 8.5)
        c.drawCentredString(PAGE_W / 2, PAGE_H - 729, self.doc["classification"])
        c.setFont("Times-Roman", 10)
        c.drawCentredString(PAGE_W / 2, PAGE_H - 739, self._page_label())

    def _header(self) -> None:
        c = self.canvas
        c.setFont("Times-Roman", 10)
        y = PAGE_H - 67
        c.drawString(LEFT, y, f"Document Responsibility:  {self.doc['responsibility']}")
        c.drawRightString(RIGHT, y, self.doc["id"])
        c.drawString(LEFT, y - 11, f"Issue Date:  {self.doc['issue_date']}")
        c.drawString(LEFT, y - 23, f"Next Planned Update:  {self.doc['next_planned_update']}")
        c.drawRightString(RIGHT, y - 23, self.doc["title"])

    def new_page(self) -> None:
        self._footer()
        self.canvas.showPage()
        self.page += 1
        self._header()
        self.y = BODY_TOP

    def space(self, amount: float) -> None:
        self.y -= amount

    def need(self, amount: float) -> None:
        if self.y - amount < BODY_BOTTOM:
            self.new_page()

    # -- cover page ------------------------------------------------------
    def cover(self) -> None:
        c, d = self.canvas, self.doc
        logo = os.path.join(HERE, d["logo"])
        if os.path.exists(logo):
            c.drawImage(logo, 426.6, PAGE_H - 72.5, width=145, height=44, mask="auto")
        c.setFont("Helvetica-Bold", 26)
        c.drawString(LEFT, PAGE_H - 115, d["kind"])
        c.setFont("Helvetica", 14)
        c.drawString(LEFT, PAGE_H - 141, d["id"])
        c.drawRightString(RIGHT, PAGE_H - 141, d["issue_date"])
        for i, line in enumerate(wrap(d["title"], "Helvetica", 14, RIGHT - LEFT)):
            c.drawString(LEFT, PAGE_H - 162 - i * 18, line)
        c.setFont("Times-Roman", 14)
        c.drawString(LEFT, PAGE_H - 186, f"Document Responsibility:  {d['responsibility']}")

        project_logo = os.path.join(HERE, d["project_logo"])
        if os.path.exists(project_logo):
            c.drawImage(
                project_logo, PAGE_W / 2 - 55, PAGE_H - 300, width=110, height=90,
                preserveAspectRatio=True, mask="auto",
            )

        c.setFont("Helvetica-Bold", 12)
        c.drawCentredString(PAGE_W / 2 + 20, PAGE_H - 412, "Contents")
        c.setFont("Helvetica", 12)
        y = PAGE_H - 435
        for label, key in self.toc_entries():
            page = self.heading_pages.get(key, 0)
            self._toc_line(label, page, y)
            y -= 22.7
        y -= 8
        for label, key in self.appendix_entries():
            page = self.heading_pages.get(key, 0)
            self._toc_line(label, page, y)
            y -= 22.7

        c.setFont("Times-Roman", 10)
        c.drawString(LEFT, PAGE_H - 731, f"Previous Issue:  {self.doc['previous_issue']}")
        c.drawRightString(RIGHT, PAGE_H - 731, f"Next Planned Update:  {self.doc['next_planned_update']}")
        c.drawCentredString(PAGE_W / 2, PAGE_H - 743, self._page_label())
        c.setFont("Times-Roman", 8.5)
        c.drawCentredString(PAGE_W / 2, PAGE_H - 756, f"Contact: {self.doc['contact']}")
        c.drawCentredString(PAGE_W / 2, PAGE_H - 768, self.doc["copyright"])
        c.showPage()
        self.page += 1
        self._header()
        self.y = BODY_TOP

    def _toc_line(self, label: str, page: int, y: float) -> None:
        c = self.canvas
        x = 252.0
        num = str(page) if page else "-"
        label_w = stringWidth(label + " ", "Helvetica", 12)
        num_w = stringWidth(num, "Helvetica", 12)
        avail = (526.0 - num_w - 6) - (x + label_w)
        dots = "." * max(0, int(avail / stringWidth(".", "Helvetica", 12)))
        c.drawString(x, y, f"{label} {dots}" if dots else label)
        c.drawRightString(526.0, y, num)

    def toc_entries(self) -> list[tuple[str, str]]:
        entries = [
            (f"{s['number']}  {s['title']}", f"sec:{s['number']}")
            for s in self.model["sections"]
        ]
        entries.append(("Revision Summary", "sec:revision"))
        return entries

    def appendix_entries(self) -> list[tuple[str, str]]:
        return [(t, f"app:{i}") for i, (t, _) in enumerate(APPENDICES, start=1)]

    # -- text blocks -----------------------------------------------------
    def heading(self, key: str, number: str, title: str) -> None:
        self.space(11)
        self.need(40)
        self.heading_pages[key] = self.page
        font, size, _lead = HEAD_FONT
        self.canvas.setFont(font, size)
        text = f"{number}    {title}".strip() if number else title
        self.canvas.drawString(LEFT, self.y, text)
        self.space(25)

    def paragraph(self, text: str, x: float = 108.0, font=BODY_FONT, hanging: str = "") -> None:
        name, size, lead = font
        indent = x
        if hanging:
            indent = max(144.0, x + stringWidth(hanging, name, size) + 12)
        lines = wrap(text, name, size, RIGHT - indent)
        self.canvas.setFont(name, size)
        for i, line in enumerate(lines):
            self.need(lead)
            self.canvas.setFont(name, size)
            if i == 0 and hanging:
                self.canvas.drawString(x, self.y, hanging)
            self.canvas.drawString(indent if hanging else x, self.y, line)
            self.space(lead)
        self.space(11)

    def commentary(self, text: str) -> None:
        name, size, lead = NOTE_FONT
        self.space(6)
        self.need(3 * lead)
        self.canvas.setFont(name, size)
        self.canvas.drawString(108, self.y, "Commentary Note:")
        self.space(lead + 8)
        for line in wrap(text, name, size, RIGHT - 135):
            self.need(lead)
            self.canvas.setFont(name, size)
            self.canvas.drawString(135, self.y, line)
            self.space(lead)
        self.space(13)

    def reference_block(self, label: str, items: list[list[str]]) -> None:
        name, size, lead = BODY_FONT
        self.need(2 * lead)
        self.canvas.setFont(name, size)
        self.canvas.drawString(144, self.y, label)
        self.space(lead + 6)
        for tag, desc in items:
            lines = wrap(desc, "Times-Italic", size, RIGHT - 293)
            self.need(lead * (len(lines) + 1))
            self.canvas.setFont("Times-Italic", size)
            self.canvas.drawString(162, self.y, tag)
            if stringWidth(tag, "Times-Italic", size) > 293 - 162 - 8:
                self.space(lead)
            for line in lines:
                self.canvas.setFont("Times-Italic", size)
                self.canvas.drawString(293, self.y, line)
                self.space(lead)
            self.space(6)
        self.space(8)

    def table(self, headers: list[str], rows: list[list[str]], widths: list[float]) -> None:
        name, size, lead = TABLE_FONT
        hname, hsize, _ = TABLE_HEAD_FONT
        total = sum(widths)
        x0 = LEFT + (RIGHT - LEFT - total) / 2

        def draw_header() -> None:
            self.need(2 * lead + 6)
            c, y = self.canvas, self.y
            c.setFillColor(SHADE)
            c.rect(x0, y - 4, total, lead + 4, stroke=0, fill=1)
            c.setFillColor(black)
            c.setFont(hname, hsize)
            x = x0
            for head, w in zip(headers, widths):
                c.drawString(x + 3, y, wrap(head, hname, hsize, w - 6)[0])
                x += w
            self.space(lead + 4)
            c.setStrokeColor(RULE)
            c.setLineWidth(0.5)
            c.line(x0, self.y + lead - 3, x0 + total, self.y + lead - 3)

        draw_header()
        for row in rows:
            cells = [wrap(str(v), name, size, w - 6) for v, w in zip(row, widths)]
            height = max(len(cell) for cell in cells) * lead
            if self.y - height < BODY_BOTTOM:
                self.new_page()
                draw_header()
            c = self.canvas
            x = x0
            for cell, w in zip(cells, widths):
                yy = self.y
                for line in cell:
                    c.setFont(name, size)
                    c.drawString(x + 3, yy, line)
                    yy -= lead
                x += w
            self.space(height)
            c.setStrokeColor(RULE)
            c.setLineWidth(0.25)
            c.line(x0, self.y + lead - 3, x0 + total, self.y + lead - 3)
        self.space(14)

    # -- layered diagram -------------------------------------------------
    def layer_diagram(self) -> None:
        c = self.canvas
        model = self.model["model"]
        self.need(len(model["layers"]) * 70 + 30)
        for layer in model["layers"]:
            components = wrap(", ".join(layer["components"]), "Helvetica", 8.5, RIGHT - LEFT - 12)
            box_h = 22.0 + 10 * len(components)
            y = self.y - box_h
            c.setStrokeColor(RULE)
            c.setLineWidth(0.7)
            c.setFillColor(white)
            c.rect(LEFT, y, RIGHT - LEFT, box_h, stroke=1, fill=1)
            c.setFillColor(SHADE)
            c.rect(LEFT, y + box_h - 15, RIGHT - LEFT, 15, stroke=1, fill=1)
            c.setFillColor(black)
            c.setFont("Helvetica-Bold", 9)
            c.drawString(LEFT + 4, y + box_h - 11, f"{layer['name']} layer")
            c.setFont("Helvetica-Oblique", 8)
            c.drawRightString(RIGHT - 4, y + box_h - 11, layer["runtime"])
            c.setFont("Helvetica", 8.5)
            yy = y + box_h - 27
            for line in components:
                c.drawString(LEFT + 5, yy, line)
                yy -= 10
            self.space(box_h + 12)
        c.setFont("Helvetica-Oblique", 8.5)
        self.need(20)
        c.drawString(LEFT, self.y, "Data platforms: VSAM KSDS and sequential data sets; Db2 for z/OS database POSMVP.")
        self.space(18)

    # -- document ---------------------------------------------------------
    def render(self, model: dict) -> None:
        self.model = model
        self.doc = model["document"]
        self.cover()

        for section in model["sections"]:
            self.heading(f"sec:{section['number']}", section["number"], section["title"])
            for item in section["body"]:
                if isinstance(item, str):
                    self.paragraph(item)
                elif "commentary" in item:
                    self.commentary(item["commentary"])
                elif "subnumber" in item:
                    self.paragraph(item["text"], x=108, hanging=item["subnumber"])
                elif "label" in item:
                    self.reference_block(item["label"], item["items"])

        self.heading("sec:revision", "", "Revision Summary")
        for date, text in model["revision_summary"]:
            self.paragraph(text, x=162, hanging=date)

        for index, (title, builder) in enumerate(APPENDICES, start=1):
            self.new_page()
            self.heading_pages[f"app:{index}"] = self.page
            c = self.canvas
            c.setFont("Helvetica-Bold", 12)
            name, subtitle = title.split(" - ", 1)
            c.drawCentredString(PAGE_W / 2, self.y, name)
            self.space(22)
            c.setFont("Helvetica-Bold", 12)
            c.drawCentredString(PAGE_W / 2, self.y, subtitle)
            self.space(30)
            builder(self)

        self._footer()
        self.canvas.save()


def appendix_components(r: Renderer) -> None:
    model = r.model["model"]
    rows = []
    for layer in model["layers"]:
        for comp in layer["components"]:
            spec = model["components"][comp]
            rows.append([
                comp,
                layer["name"],
                spec["role"] + (" [not implemented]" if spec.get("status") == "not_implemented" else ""),
                ", ".join(spec["copybooks"]) or "-",
                ", ".join(spec["data"]) or "-",
            ])
    r.table(["Component", "Layer", "Responsibility", "Copybooks", "Data stores"], rows,
            [55, 62, 160, 90, 101])


def appendix_data(r: Renderer) -> None:
    model = r.model["model"]
    rows = [
        [name, f"{spec['platform']}, {spec['record']}", spec["dataset"], str(spec["key"]), spec["owner"]]
        for name, spec in model["data_stores"].items()
    ]
    r.table(["Data store", "Platform", "Data set / table", "Key", "Owner"], rows,
            [116, 68, 132, 90, 62])
    r.space(4)
    rows = [[j["job"], j["program"], j["jcl"], j["purpose"]] for j in model["batch_jobs"]]
    r.table(["Job", "Program", "JCL", "Purpose"], rows, [55, 58, 175, 180])
    rows = [[t["transaction"], t["program"], t["mapset"], t["group"], t["db2entry"], t["plan"], t["purpose"]]
            for t in model["online_transactions"]]
    r.table(["Tran", "Program", "Mapset", "Group", "DB2ENTRY", "Plan", "Purpose"], rows,
            [40, 55, 48, 50, 60, 55, 160])


def appendix_relationships(r: Renderer) -> None:
    rows = [[rel["from"], rel["type"], rel["to"], rel["detail"]] for rel in r.model["model"]["relationships"]]
    r.table(["Source", "Interface", "Target", "Detail"], rows, [92, 60, 108, 208])


def appendix_diagram(r: Renderer) -> None:
    r.layer_diagram()
    model = r.model["model"]
    rows = [[a["name"], a["type"], a["interacts_with"]] for a in model["actors"]]
    r.table(["External actor", "Type", "Interaction"], rows, [110, 55, 235])


def appendix_roles(r: Renderer) -> None:
    spec = r.model["model"]["responsibilities"]
    rows = [[row["task"], *row["values"]] for row in spec["rows"]]
    r.table(["Task", *spec["columns"]], rows, [188, 70, 60, 60, 90])
    r.canvas.setFont("Helvetica-Oblique", 9)
    r.canvas.drawString(LEFT, r.y, spec["legend"])


APPENDICES: list[tuple[str, Callable[[Renderer], None]]] = [
    ("Appendix-1 - Component Inventory Matrix", appendix_components),
    ("Appendix-2 - Data Stores, Jobs and Transactions", appendix_data),
    ("Appendix-3 - Interface and Dependency Matrix", appendix_relationships),
    ("Appendix-4 - Layer Diagram and External Actors", appendix_diagram),
    ("Appendix-5 - Roles and Responsibilities Matrix", appendix_roles),
]


def main() -> None:
    with open(MODEL_PATH) as handle:
        model = yaml.safe_load(handle)

    first = Renderer(model["document"], None)
    first.render(model)
    second = Renderer(model["document"], first.page)
    second.heading_pages = first.heading_pages
    second.render(model)
    print(f"wrote {OUT_PATH} ({second.page} pages)")


if __name__ == "__main__":
    main()
