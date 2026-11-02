"""Woven ornaments for the Kurdistan AI Safety Hub site: the kilim band, the medallion
mark, the favicon and the woven attention pattern. Pure functions returning SVG markup."""
from urllib.parse import quote


def attention_svg():
    """A 12x12 causal attention pattern, drawn as woven cells (illustrative).
    Madder cells: attention weight. Indigo first column: the 'attention sink'.
    Saffron stripe: an induction head on a sequence that repeats halfway."""
    n, c, g = 12, 20, 2
    size = n * (c + g) - g
    cells = []
    for i in range(n):
        for j in range(n):
            x, y = j * (c + g), i * (c + g)
            if j > i:
                cells.append(
                    f'<rect x="{x + 0.5}" y="{y + 0.5}" width="{c - 1}" height="{c - 1}" '
                    f'style="fill:none;stroke:var(--rule);stroke-width:1"/>'
                )
                continue
            strong = i >= 6 and j == i - 5
            if i == 0:
                colour, w = "var(--indigo)", 1.0
            elif strong:
                colour, w = "var(--saffron)", 1.0
            elif j == 0:
                colour, w = "var(--indigo)", 0.7 if i < 6 else 0.4
            elif j == i:
                colour, w = "var(--madder)", 0.55 if i < 6 else 0.22
            else:
                colour, w = "var(--madder)", 0.1
            cells.append(
                f'<rect x="{x}" y="{y}" width="{c}" height="{c}" '
                f'style="fill:{colour};fill-opacity:{w:.2f}"/>'
            )
    return (
        f'<svg class="attn-svg" viewBox="0 0 {size} {size}" role="img" '
        f'aria-label="A 12 by 12 grid woven like a kilim. Cells below the diagonal are '
        f'shaded by how strongly each token attends to each earlier token; a saffron '
        f'stripe in the lower half shows an induction head.">'
        + "".join(cells)
        + "</svg>"
    )


def stepped_diamond(cx, cy, n, s, style):
    """A stepped (woven) diamond: 2n+1 rows of cells, as a kilim weaver would make it."""
    rects = []
    for i in range(-n, n + 1):
        cells = 2 * (n - abs(i)) + 1
        w = cells * s
        rects.append(
            f'<rect x="{cx - w / 2:g}" y="{cy + i * s - s / 2:g}" width="{w:g}" height="{s:g}" style="{style}"/>'
        )
    return "".join(rects)


def stepped_triangle(cx, y0, n, s, down, style):
    rects = []
    for k in range(n + 1):
        cells = 2 * (n - k) + 1
        w = cells * s
        y = y0 + k * s if down else y0 - (k + 1) * s
        rects.append(f'<rect x="{cx - w / 2:g}" y="{y:g}" width="{w:g}" height="{s:g}" style="{style}"/>')
    return "".join(rects)


def medallion(size, colours):
    """The Hub's mark: a kilim medallion of nested stepped diamonds."""
    s = 2
    n = 7
    span = (2 * n + 1) * s
    c = span / 2
    madder, paper, indigo, saffron = colours
    body = (
        stepped_diamond(c, c, 7, s, f"fill:{madder}")
        + stepped_diamond(c, c, 5, s, f"fill:{paper}")
        + stepped_diamond(c, c, 4, s, f"fill:{indigo}")
        + stepped_diamond(c, c, 2, s, f"fill:{paper}")
        + stepped_diamond(c, c, 1, s, f"fill:{saffron}")
    )
    return span, body


def mark_svg(size=40):
    span, body = medallion(size, ("var(--madder)", "var(--paper)", "var(--indigo)", "var(--saffron)"))
    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 {span} {span}" shape-rendering="crispEdges" '
        f'aria-hidden="true" focusable="false">{body}</svg>'
    )


def favicon():
    span, body = medallion(32, ("#8F2B1F", "#F2E9D8", "#24395E", "#C38B2A"))
    svg = (f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {span} {span}' shape-rendering='crispEdges'>"
           + body.replace('"', "'") + "</svg>")
    return "data:image/svg+xml," + quote(svg)


_KILIM_COUNT = [0]


def kilim_band():
    """A woven border: stepped diamonds with sawtooth edges, repeated across the page."""
    _KILIM_COUNT[0] += 1
    uid = f"kilim{_KILIM_COUNT[0]}"
    s, tw, th = 2, 48, 28
    cy = th / 2
    tile = (
        stepped_diamond(24, cy, 6, s, "fill:var(--madder)")
        + stepped_diamond(24, cy, 4, s, "fill:var(--paper)")
        + stepped_diamond(24, cy, 3, s, "fill:var(--indigo)")
        + stepped_diamond(24, cy, 1, s, "fill:var(--saffron)")
        + stepped_diamond(0, cy, 3, s, "fill:var(--indigo)")
        + stepped_diamond(48, cy, 3, s, "fill:var(--indigo)")
        + stepped_diamond(0, cy, 1, s, "fill:var(--saffron)")
        + stepped_diamond(48, cy, 1, s, "fill:var(--saffron)")
        + stepped_triangle(12, 0, 2, s, True, "fill:var(--saffron)")
        + stepped_triangle(36, 0, 2, s, True, "fill:var(--saffron)")
        + stepped_triangle(12, th, 2, s, False, "fill:var(--saffron)")
        + stepped_triangle(36, th, 2, s, False, "fill:var(--saffron)")
    )
    return (
        f'<svg class="kilim" aria-hidden="true" focusable="false" shape-rendering="crispEdges">'
        f'<defs><pattern id="{uid}" x="0" y="4" width="{tw}" height="{th}" patternUnits="userSpaceOnUse">'
        f"{tile}</pattern></defs>"
        f'<rect x="0" y="0.5" width="100%" height="1.5" style="fill:var(--madder)"/>'
        f'<rect x="0" y="4" width="100%" height="{th}" fill="url(#{uid})"/>'
        f'<rect x="0" y="34" width="100%" height="1.5" style="fill:var(--madder)"/>'
        f"</svg>"
    )


def corner_svg():
    """A carpet spandrel: a stepped quarter-medallion for the corners of a woven field."""
    s = 3
    layers = [(7, "var(--madder)"), (5, "var(--surface)"), (4, "var(--indigo)"), (2, "var(--saffron)")]
    rects = []
    for n, colour in layers:
        for k in range(n):
            rects.append(f'<rect x="0" y="{k * s}" width="{(n - k) * s}" height="{s}" style="fill:{colour}"/>')
    span = 7 * s
    return (f'<svg viewBox="0 0 {span} {span}" shape-rendering="crispEdges" aria-hidden="true" focusable="false">'
            + "".join(rects) + "</svg>")


def spandrels():
    svg = corner_svg()
    return "".join(f'<span class="spandrel sp-{c}" aria-hidden="true">{svg}</span>' for c in ("ts", "te", "bs", "be"))


_SUN = [".....#.....",
        ".#...#...#.",
        "..#.....#..",
        ".....#.....",
        "....###....",
        "##.#####.##",
        "....###....",
        ".....#.....",
        "..#.....#..",
        ".#...#...#.",
        ".....#....."]
_MOON = ["....#......",
         "..##.......",
         ".###.......",
         ".###.......",
         "####.......",
         "####.......",
         "#####......",
         ".#####.....",
         ".#########.",
         "..#######..",
         "....###...."]


def _pixels(rows, size):
    s = 2
    rects = "".join(f'<rect x="{x * s}" y="{y * s}" width="{s}" height="{s}"/>'
                    for y, row in enumerate(rows) for x, c in enumerate(row) if c == "#")
    span = len(rows) * s
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 {span} {span}" shape-rendering="crispEdges" '
            f'aria-hidden="true" focusable="false" style="fill:currentColor">{rects}</svg>')


def sun_svg(size=16):
    """A woven sun: a stepped diamond with rays, as on a kilim."""
    return _pixels(_SUN, size)


def moon_svg(size=16):
    return _pixels(_MOON, size)
