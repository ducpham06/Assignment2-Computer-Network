"""
Tiny diagram engine: one scene description -> (a) SVG for the report, and
(b) a draw.io (.drawio) file with Cisco stencils that opens/edits in
diagrams.net with the same layout.
"""
import html
import math
from xml.sax.saxutils import escape

PALETTE = {
    "router": "#1d5d9b", "l3switch": "#1d5d9b", "l2switch": "#2e8b8b", "server": "#555f6d",
    "pc": "#555f6d", "cloud": "#8a96a3", "user": "#555f6d", "iot": "#b35c00", "ap": "#2e8b8b",
}
DRAWIO_STYLE = {
    "router": "shape=mxgraph.cisco.routers.router;fillColor=#036897;strokeColor=#ffffff;",
    "l3switch": "shape=mxgraph.cisco.switches.layer_3_switch;fillColor=#036897;strokeColor=#ffffff;",
    "l2switch": "shape=mxgraph.cisco.switches.workgroup_switch;fillColor=#036897;strokeColor=#ffffff;",
    "server": "shape=mxgraph.cisco.servers.fileserver;fillColor=#036897;strokeColor=#ffffff;",
    "pc": "shape=mxgraph.cisco.computers_and_peripherals.pc;fillColor=#036897;strokeColor=#ffffff;",
    "user": "shape=mxgraph.cisco.people.standing_man;fillColor=#036897;strokeColor=#ffffff;",
    "iot": "shape=mxgraph.cisco.misc.sensor;fillColor=#FF9900;strokeColor=#ffffff;",
    "ap": "shape=mxgraph.cisco.wireless.wireless_transport;fillColor=#036897;strokeColor=#ffffff;",
    "cloud": "ellipse;shape=cloud;fillColor=#f5f5f5;strokeColor=#666666;",
}
SIZE = {"router": (46, 32), "l3switch": (46, 40), "l2switch": (54, 30), "server": (30, 44), "pc": (36, 34),
        "user": (26, 44), "iot": (34, 30), "ap": (34, 30), "cloud": (150, 80)}
FONT = "Helvetica, Arial, sans-serif"


class Scene:
    def __init__(self, w, h, title=""):
        self.w, self.h, self.title = w, h, title
        self.nodes, self.groups, self.links, self.texts = {}, [], [], []

    def node(self, nid, kind, x, y, label=None, sub=None, size=None, label_pos="below"):
        w, h = size or SIZE[kind]
        self.nodes[nid] = dict(id=nid, kind=kind, x=x, y=y, w=w, h=h, label=nid if label is None else label,
                               sub=sub or [], label_pos=label_pos)

    def group(self, x, y, w, h, label, fill="#eef4fb", stroke="#7a9cc6", dashed=True, sub=None):
        self.groups.append(dict(x=x, y=y, w=w, h=h, label=label, fill=fill, stroke=stroke, dashed=dashed, sub=sub))

    def link(self, a, b, color="#333333", width=1.6, dash=None, la=None, lb=None, mid=None, double=False,
             points=None, mid_t=0.5, font=9, la_t=0.2, lb_t=0.8):
        self.links.append(dict(a=a, b=b, color=color, width=width, dash=dash, la=la, lb=lb, mid=mid,
                               double=double, points=points or [], mid_t=mid_t, font=font, la_t=la_t, lb_t=lb_t))

    def text(self, x, y, s, size=11, color="#222", bold=False, anchor="start", box=None, italic=False):
        self.texts.append(dict(x=x, y=y, s=s, size=size, color=color, bold=bold, anchor=anchor, box=box,
                               italic=italic))

    # ------------------------------------------------------------------ geometry
    def _path(self, L):
        a, b = self.nodes[L["a"]], self.nodes[L["b"]]
        return [(a["x"], a["y"])] + list(L["points"]) + [(b["x"], b["y"])]

    @staticmethod
    def _at(pts, t):
        segs = [(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
        lens = [math.dist(p, q) for p, q in segs]
        tot = sum(lens) or 1
        d = t * tot
        for (p, q), l in zip(segs, lens):
            if d <= l or l == lens[-1]:
                f = 0 if l == 0 else min(d / l, 1)
                return p[0] + (q[0] - p[0]) * f, p[1] + (q[1] - p[1]) * f
            d -= l
        return pts[-1]

    # ------------------------------------------------------------------ SVG
    def _icon(self, n):
        k, x, y, w, h = n["kind"], n["x"], n["y"], n["w"], n["h"]
        c = PALETTE[k]
        s = []
        if k == "router":
            s.append(f'<ellipse cx="{x}" cy="{y}" rx="{w/2}" ry="{h/2}" fill="{c}" stroke="#fff" stroke-width="1.5"/>')
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                x1, y1 = x + dx * 3, y + dy * 2
                x2, y2 = x + dx * (w / 2 - 7), y + dy * (h / 2 - 5)
                s.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#fff" stroke-width="2.2"/>')
            s.append(f'<circle cx="{x}" cy="{y}" r="2.5" fill="#fff"/>')
        elif k in ("l3switch", "l2switch"):
            s.append(f'<rect x="{x-w/2}" y="{y-h/2}" width="{w}" height="{h}" rx="4" fill="{c}" stroke="#fff" stroke-width="1.5"/>')
            if k == "l3switch":
                for dx, dy in ((1, 1), (-1, -1), (1, -1), (-1, 1)):
                    s.append(f'<line x1="{x}" y1="{y}" x2="{x+dx*(w/2-9)}" y2="{y+dy*(h/2-8)}" stroke="#fff" stroke-width="2"/>')
            else:
                for yy, d in ((y - 5, 1), (y + 5, -1)):
                    s.append(f'<line x1="{x-w/2+9}" y1="{yy}" x2="{x+w/2-9}" y2="{yy}" stroke="#fff" stroke-width="2"/>')
                    tip = x + d * (w / 2 - 9)
                    s.append(f'<path d="M{tip},{yy} l{-d*6},-4 l0,8 z" fill="#fff"/>')
        elif k == "server":
            s.append(f'<rect x="{x-w/2}" y="{y-h/2}" width="{w}" height="{h}" rx="3" fill="{c}"/>')
            for i in range(3):
                yy = y - h / 2 + 9 + i * 10
                s.append(f'<line x1="{x-w/2+5}" y1="{yy}" x2="{x+w/2-5}" y2="{yy}" stroke="#fff" stroke-width="2"/>')
        elif k == "pc":
            s.append(f'<rect x="{x-w/2}" y="{y-h/2}" width="{w}" height="{h*0.68}" rx="2" fill="{c}"/>')
            s.append(f'<rect x="{x-w/2+4}" y="{y-h/2+4}" width="{w-8}" height="{h*0.68-8}" fill="#cfe3f5"/>')
            s.append(f'<rect x="{x-4}" y="{y+h*0.18}" width="8" height="{h*0.18}" fill="{c}"/>')
            s.append(f'<rect x="{x-w/3}" y="{y+h*0.34}" width="{2*w/3}" height="4" fill="{c}"/>')
        elif k == "user":
            s.append(f'<circle cx="{x}" cy="{y-h/2+7}" r="7" fill="{c}"/>')
            s.append(f'<path d="M{x-w/2},{y+h/2} q0,-{h*0.6} {w/2},-{h*0.6} q{w/2},0 {w/2},{h*0.6} z" fill="{c}"/>')
        elif k in ("iot", "ap"):
            s.append(f'<rect x="{x-w/2}" y="{y-h/2+8}" width="{w}" height="{h-8}" rx="4" fill="{c}"/>')
            for r in (6, 11):
                s.append(f'<path d="M{x-r},{y-h/2+8} a{r},{r} 0 0 1 {2*r},0" fill="none" stroke="{c}" stroke-width="2"/>')
        elif k == "cloud":
            sx, sy = w / 150, h / 80
            d = (f"M{x-55*sx},{y+30*sy} C{x-85*sx},{y+30*sy} {x-85*sx},{y-5*sy} {x-58*sx},{y-8*sy} "
                 f"C{x-60*sx},{y-35*sy} {x-20*sx},{y-45*sy} {x-5*sx},{y-25*sy} "
                 f"C{x+5*sx},{y-48*sy} {x+50*sx},{y-45*sy} {x+50*sx},{y-15*sy} "
                 f"C{x+80*sx},{y-18*sy} {x+85*sx},{y+30*sy} {x+55*sx},{y+30*sy} Z")
            s.append(f'<path d="{d}" fill="{n.get("fill", "#f3f5f7")}" stroke="#8a96a3" stroke-width="1.5"/>')
        return s

    def _label(self, n):
        out = []
        if n["kind"] == "cloud":
            ys = n["y"] - 6 * (len(n["sub"]))
            out.append(self._t(n["x"], ys + 4, n["label"], 12, "#1f2d3d", True, "middle"))
            for i, t in enumerate(n["sub"]):
                out.append(self._t(n["x"], ys + 19 + i * 13, t, 9.5, "#333", False, "middle"))
            return out
        if n["label_pos"] == "right":
            x0, y0, anc = n["x"] + n["w"] / 2 + 6, n["y"] - 2, "start"
        elif n["label_pos"] == "left":
            x0, y0, anc = n["x"] - n["w"] / 2 - 6, n["y"] - 2, "end"
        elif n["label_pos"] == "above":
            x0, y0, anc = n["x"], n["y"] - n["h"] / 2 - 6 - 12 * len(n["sub"]), "middle"
        else:
            x0, y0, anc = n["x"], n["y"] + n["h"] / 2 + 13, "middle"
        if n["label"]:
            out.append(self._t(x0, y0, n["label"], 11, "#111", True, anc))
        for i, t in enumerate(n["sub"]):
            out.append(self._t(x0, y0 + 12 * (i + 1), t, 9, "#444", False, anc))
        return out

    @staticmethod
    def _t(x, y, s, size, color, bold, anchor, italic=False):
        return (f'<text x="{x:.1f}" y="{y:.1f}" font-family="{FONT}" font-size="{size}" fill="{color}" '
                f'text-anchor="{anchor}"{" font-weight=\"bold\"" if bold else ""}'
                f'{" font-style=\"italic\"" if italic else ""}>{escape(s)}</text>')

    def _boxed(self, x, y, s, size, color="#222", bg="#ffffff", border=None):
        lines = s.split("\n")
        w = max(len(l) for l in lines) * size * 0.56 + 6
        h = len(lines) * (size + 2) + 3
        out = [f'<rect x="{x-w/2:.1f}" y="{y-h/2:.1f}" width="{w:.1f}" height="{h:.1f}" rx="2" fill="{bg}" '
               f'fill-opacity="0.93"{f" stroke={chr(34)}{border}{chr(34)} stroke-width={chr(34)}0.8{chr(34)}" if border else ""}/>']
        for i, l in enumerate(lines):
            out.append(self._t(x, y - h / 2 + size + 1 + i * (size + 2), l, size, color, False, "middle"))
        return out

    def svg(self):
        o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" viewBox="0 0 {self.w} {self.h}">',
             f'<rect width="{self.w}" height="{self.h}" fill="#ffffff"/>']
        for g in self.groups:
            o.append(f'<rect x="{g["x"]}" y="{g["y"]}" width="{g["w"]}" height="{g["h"]}" rx="10" fill="{g["fill"]}" '
                     f'stroke="{g["stroke"]}" stroke-width="1.5"{" stroke-dasharray=\"6 4\"" if g["dashed"] else ""}/>')
            o.append(self._t(g["x"] + 10, g["y"] + 18, g["label"], 12.5, "#1f2d3d", True, "start"))
            if g["sub"]:
                o.append(self._t(g["x"] + 10, g["y"] + 32, g["sub"], 9.5, "#3d4f63", False, "start", True))
        for L in self.links:
            pts = self._path(L)
            d = " ".join(f"{p[0]:.1f},{p[1]:.1f}" for p in pts)
            dash = f' stroke-dasharray="{L["dash"]}"' if L["dash"] else ""
            if L["double"]:
                (x1, y1), (x2, y2) = pts[0], pts[-1]
                ln = math.dist(pts[0], pts[-1]) or 1
                nx, ny = -(y2 - y1) / ln * 3.5, (x2 - x1) / ln * 3.5
                for sgn in (1, -1):
                    o.append(f'<line x1="{x1+sgn*nx:.1f}" y1="{y1+sgn*ny:.1f}" x2="{x2+sgn*nx:.1f}" y2="{y2+sgn*ny:.1f}" '
                             f'stroke="{L["color"]}" stroke-width="{L["width"]}"/>')
            else:
                o.append(f'<polyline points="{d}" fill="none" stroke="{L["color"]}" stroke-width="{L["width"]}"{dash}/>')
        for n in self.nodes.values():
            o += self._icon(n)
        for L in self.links:
            pts = self._path(L)
            for key, t in (("la", L["la_t"]), ("lb", L["lb_t"]), ("mid", L["mid_t"])):
                if L[key]:
                    x, y = self._at(pts, t)
                    o += self._boxed(x, y, L[key], L["font"] if key != "mid" else L["font"] + 0.5,
                                     "#000" if key != "mid" else L["color"],
                                     border=None if key != "mid" else L["color"])
        for n in self.nodes.values():
            o += self._label(n)
        for t in self.texts:
            if t["box"]:
                o += self._boxed(t["x"], t["y"], t["s"], t["size"], t["color"], t["box"], "#9aa7b5")
            else:
                for i, line in enumerate(t["s"].split("\n")):
                    o.append(self._t(t["x"], t["y"] + i * (t["size"] + 3), line, t["size"], t["color"], t["bold"],
                                     t["anchor"], t["italic"]))
        o.append("</svg>")
        return "\n".join(o)

    # ------------------------------------------------------------------ draw.io
    def drawio(self, name):
        cells = ['<mxCell id="0"/>', '<mxCell id="1" parent="0"/>']
        k = 0

        def nid():
            nonlocal k
            k += 1
            return f"c{k}"

        for g in self.groups:
            lab = html.escape(g["label"] + (f"<br><i style='font-weight:normal;font-size:9px'>{g['sub']}</i>" if g["sub"] else ""))
            st = (f"rounded=1;arcSize=4;whiteSpace=wrap;html=1;fillColor={g['fill']};strokeColor={g['stroke']};"
                  f"{'dashed=1;' if g['dashed'] else ''}verticalAlign=top;align=left;spacingLeft=8;fontStyle=1;fontSize=12;")
            cells.append(f'<mxCell id="{nid()}" value="{lab}" style="{st}" vertex="1" parent="1">'
                         f'<mxGeometry x="{g["x"]}" y="{g["y"]}" width="{g["w"]}" height="{g["h"]}" as="geometry"/></mxCell>')
        ids = {}
        for n in self.nodes.values():
            i = nid()
            ids[n["id"]] = i
            lab = html.escape("<b>" + n["label"] + "</b>" + "".join(f"<br><span style='font-size:9px'>{s}</span>" for s in n["sub"]))
            pos = {"below": "verticalLabelPosition=bottom;verticalAlign=top;",
                   "right": "labelPosition=right;align=left;verticalAlign=middle;",
                   "left": "labelPosition=left;align=right;verticalAlign=middle;",
                   "above": "verticalLabelPosition=top;verticalAlign=bottom;"}[n["label_pos"]]
            if n["kind"] == "cloud":
                pos = "verticalAlign=middle;"
            st = DRAWIO_STYLE[n["kind"]] + "html=1;whiteSpace=wrap;fontSize=11;" + pos
            cells.append(f'<mxCell id="{i}" value="{lab}" style="{st}" vertex="1" parent="1">'
                         f'<mxGeometry x="{n["x"]-n["w"]/2}" y="{n["y"]-n["h"]/2}" width="{n["w"]}" height="{n["h"]}" as="geometry"/></mxCell>')
        for L in self.links:
            i = nid()
            st = (f"endArrow=none;html=1;rounded=0;strokeWidth={L['width']};strokeColor={L['color']};"
                  + ("dashed=1;" if L["dash"] else "") + ("shape=link;width=5;" if L["double"] else ""))
            pts = "".join(f'<mxPoint x="{p[0]}" y="{p[1]}"/>' for p in L["points"])
            geo = (f'<mxGeometry relative="1" as="geometry">'
                   + (f'<Array as="points">{pts}</Array>' if pts else "") + "</mxGeometry>")
            cells.append(f'<mxCell id="{i}" style="{st}" edge="1" parent="1" source="{ids[L["a"]]}" target="{ids[L["b"]]}">{geo}</mxCell>')
            for key, t in (("la", L["la_t"]), ("lb", L["lb_t"]), ("mid", L["mid_t"])):
                if L[key]:
                    v = html.escape(L[key].replace("\n", "<br>"))
                    color = L["color"] if key == "mid" else "#000000"
                    cells.append(f'<mxCell id="{nid()}" value="{v}" style="edgeLabel;html=1;align=center;verticalAlign=middle;'
                                 f'resizable=0;points=[];fontSize={L["font"]};fontColor={color};labelBackgroundColor=#ffffff;" '
                                 f'vertex="1" connectable="0" parent="{i}"><mxGeometry x="{(t*2-1):.2f}" relative="1" as="geometry">'
                                 f'<mxPoint as="offset"/></mxGeometry></mxCell>')
        for t in self.texts:
            lines = t["s"].split("\n")
            w = max(len(l) for l in lines) * t["size"] * 0.6 + 10
            h = len(lines) * (t["size"] + 4) + 6
            x = t["x"] - (w / 2 if t["anchor"] == "middle" or t["box"] else 0)
            y = t["y"] - (h / 2 if t["box"] else t["size"])
            v = html.escape("<br>".join(lines))
            st = (f"text;html=1;whiteSpace=wrap;fontSize={t['size']};fontColor={t['color']};"
                  + ("fontStyle=1;" if t["bold"] else "") + ("fontStyle=2;" if t["italic"] else "")
                  + (f"fillColor={t['box']};strokeColor=#9aa7b5;align=center;" if t["box"] else
                     f"align={'center' if t['anchor'] == 'middle' else 'left'};"))
            cells.append(f'<mxCell id="{nid()}" value="{v}" style="{st}" vertex="1" parent="1">'
                         f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>')
        return (f'<mxfile host="tvi-network-tools"><diagram id="{escape(name)}" name="{escape(name)}">'
                f'<mxGraphModel dx="{self.w}" dy="{self.h}" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" '
                f'arrows="1" fold="1" page="1" pageScale="1" pageWidth="{self.w}" pageHeight="{self.h}" math="0" shadow="0">'
                f'<root>{"".join(cells)}</root></mxGraphModel></diagram></mxfile>')
