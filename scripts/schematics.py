"""Multiblock schematics, built from the formation rules in the mods' source code.

Each schematic is a minimal structure that passes the mod's validator, returned
as horizontal layers (bottom first) of one-letter block codes, plus a legend.
The rules each builder follows are quoted from the validator it mirrors, so a
change in the mod can be checked against the same file.

Rendering to SVG lives here too, so guides only reference a schematic by name.
"""
import html

# Mekanism wall grids for the fixed-size multiblocks (0 = may be missing, 1 = frame casing, 2 = casing or port).
# Source: SPSValidator.ALLOWED_GRID and FusionReactorValidator.ALLOWED_GRID, Mekanism 10.7.19.
SPS_GRID = [
    [0, 0, 1, 1, 1, 0, 0],
    [0, 1, 2, 2, 2, 1, 0],
    [1, 2, 2, 2, 2, 2, 1],
    [1, 2, 2, 2, 2, 2, 1],
    [1, 2, 2, 2, 2, 2, 1],
    [0, 1, 2, 2, 2, 1, 0],
    [0, 0, 1, 1, 1, 0, 0],
]
FUSION_GRID = [
    [0, 0, 1, 0, 0],
    [0, 1, 2, 1, 0],
    [1, 2, 2, 2, 1],
    [0, 1, 2, 1, 0],
    [0, 0, 1, 0, 0],
]

# Block codes shared by every schematic: (colour, {lang: name})
BLOCKS = {
    ".": ("transparent", {"en": "Air / empty", "fr": "Air / vide"}),
    "C": ("#8a8f9c", {"en": "Casing", "fr": "Boîtier (casing)"}),
    "G": ("#7fc8e8", {"en": "Glass (reactor or structural)", "fr": "Verre (de réacteur ou structurel)"}),
    "P": ("#e0a33a", {"en": "Port / valve", "fr": "Port / valve"}),
    "L": ("#c45dd6", {"en": "Logic adapter", "fr": "Adaptateur logique"}),
    "F": ("#56c26a", {"en": "Fission fuel assembly", "fr": "Assemblage de combustible"}),
    "R": ("#d8d23a", {"en": "Control rod assembly", "fr": "Barre de contrôle"}),
    "K": ("#5aa0ff", {"en": "Supercharged coil", "fr": "Bobine supercharged"}),
    "X": ("#ff6b5a", {"en": "Controller", "fr": "Contrôleur"}),
    "D": ("#b8b8c8", {"en": "Pressure disperser", "fr": "Disperseur de pression"}),
    "H": ("#ff8a3d", {"en": "Superheating element", "fr": "Élément de surchauffe"}),
    "T": ("#c9a46a", {"en": "Turbine rotor (with blades)", "fr": "Rotor de turbine (avec pales)"}),
    "O": ("#e8e8e8", {"en": "Rotational complex", "fr": "Complexe rotatif"}),
    "E": ("#e05a9a", {"en": "Electromagnetic coil", "fr": "Bobine électromagnétique"}),
    "V": ("#9ad1a0", {"en": "Turbine vent", "fr": "Évent de turbine"}),
    "I": ("#4fd2c2", {"en": "Induction cell / provider", "fr": "Cellule / fournisseur d'induction"}),
    "M": ("#a46cff", {"en": "Laser focus matrix", "fr": "Matrice de focalisation laser"}),
    "S": ("#3c78b4", {"en": "Solar panel (optional)", "fr": "Panneau solaire (optionnel)"}),
}


def cuboid(w, h, d, wall="C", inner="."):
    """Hollow box: edges are frame casing, faces get `wall`, inside gets `inner`. Layers are lists of rows (z) of chars (x)."""
    layers = []
    for y in range(h):
        rows = []
        for z in range(d):
            row = ""
            for x in range(w):
                on = [x in (0, w - 1), y in (0, h - 1), z in (0, d - 1)]
                if sum(on) >= 2:
                    row += "C"  # CuboidStructureValidator: positions on an edge require a frame
                elif sum(on) == 1:
                    row += wall
                else:
                    row += inner
            rows.append(row)
        layers.append(rows)
    return layers


def put(layers, x, y, z, code):
    row = layers[y][z]
    layers[y][z] = row[:x] + code + row[x + 1:]


def grid_shell(size, grid, frame="C", other="C"):
    """Fixed-size Mekanism multiblock whose faces follow a 0/1/2 grid (SPS, fusion reactor)."""
    layers = [[["."] * size for _ in range(size)] for _ in range(size)]
    n = size - 1
    for y in range(size):
        for z in range(size):
            for x in range(size):
                faces = []
                if x in (0, n): faces.append(grid[z][y])
                if z in (0, n): faces.append(grid[x][y])
                if y in (0, n): faces.append(grid[x][z])
                if not faces:
                    continue
                v = min(faces)  # a position shared by two faces must satisfy both
                layers[y][z][x] = "." if v == 0 else frame if v == 1 else other
    return [["".join(r) for r in layer] for layer in layers]


def fission():
    # 5x5x5 reactor. FissionReactorValidator: inside may only hold air, fuel assemblies and control rods;
    # every column of fuel assemblies is contiguous and has exactly one control rod right on top.
    s = cuboid(5, 5, 5, wall="G")
    for x, z in [(1, 1), (3, 1), (1, 3), (3, 3)]:
        put(s, x, 1, z, "F")
        put(s, x, 2, z, "F")
        put(s, x, 3, z, "R")
    # Ports on the faces (not the edges): fuel in, coolant in, heated coolant out, waste out
    put(s, 2, 2, 0, "P"); put(s, 0, 2, 2, "P"); put(s, 4, 2, 2, "P"); put(s, 2, 2, 4, "P")
    put(s, 2, 0, 2, "L")
    return s


def turbine():
    # 5x7x5 turbine. TurbineValidator: odd length and width, rotational complex in the centre column,
    # contiguous rotors below it, a full layer of pressure dispersers at the complex's height,
    # electromagnetic coils connected above the complex, vents only at or above the complex.
    s = cuboid(5, 7, 5, wall="C")
    for y in (1, 2, 3):
        put(s, 2, y, 2, "T")
    for x in (1, 2, 3):
        for z in (1, 2, 3):
            put(s, x, 4, z, "D")
    put(s, 2, 4, 2, "O")
    put(s, 2, 5, 2, "E")
    for x in (1, 2, 3):
        for z in (1, 2, 3):
            put(s, x, 6, z, "V")
    put(s, 2, 1, 0, "P")
    return s


def boiler():
    # 5x6x5 boiler. BoilerValidator: one full horizontal layer of pressure dispersers, at least one
    # superheating element below it (all connected), no air pockets cut off from the water part.
    s = cuboid(5, 6, 5, wall="G")
    for x in (1, 2, 3):
        for z in (1, 2, 3):
            put(s, x, 3, z, "D")
    put(s, 2, 1, 2, "H")
    put(s, 2, 1, 0, "P")   # water in
    put(s, 2, 4, 0, "P")   # steam out
    return s


def evaporation():
    # 4x4 base, 3 to 18 high. EvaporationValidator: top layer corners may be missing, its 2x2 centre stays open,
    # exactly one controller somewhere on the walls (not on an edge).
    s = cuboid(4, 4, 4, wall="C")
    s[3] = [".CC.", "C..C", "C..C", ".CC."]
    put(s, 1, 1, 0, "X")
    put(s, 2, 1, 0, "P")
    put(s, 0, 1, 1, "P")
    return s


def matrix():
    # 5x5x5 induction matrix. MatrixValidator: inside holds induction cells/providers (or air).
    s = cuboid(5, 5, 5, wall="G", inner="I")
    put(s, 2, 2, 0, "P"); put(s, 2, 2, 4, "P")
    return s


def sps():
    # Exactly 7x7x7. SPSValidator: faces follow SPS_GRID; inside, supercharged coils are only allowed
    # directly behind a port, and every coil must touch one.
    s = grid_shell(7, SPS_GRID)
    put(s, 3, 3, 0, "P"); put(s, 3, 3, 1, "K")
    put(s, 0, 3, 3, "P")
    put(s, 6, 3, 3, "P")
    put(s, 3, 6, 3, "P"); put(s, 3, 5, 3, "K")
    return s


def fusion():
    # Exactly 5x5x5. FusionReactorValidator: faces follow FUSION_GRID, the controller sits in the middle of the top face,
    # inside stays empty. Ports, logic adapters and laser focus matrices go on the "2" spots.
    s = grid_shell(5, FUSION_GRID)
    put(s, 2, 4, 2, "X")
    put(s, 2, 2, 0, "M")
    put(s, 0, 2, 2, "P"); put(s, 4, 2, 2, "P"); put(s, 2, 2, 4, "P")
    return s


SCHEMATICS = {
    "mekanism_fission": fission,
    "mekanism_turbine": turbine,
    "mekanism_boiler": boiler,
    "mekanism_evaporation": evaporation,
    "mekanism_matrix": matrix,
    "mekanism_sps": sps,
    "mekanism_fusion": fusion,
}

LAYER_WORD = {"en": "Layer {n}", "fr": "Couche {n}"}
BOTTOM = {"en": "bottom", "fr": "bas"}
TOP = {"en": "top", "fr": "haut"}


def render(name, lang):
    """Every layer seen from above, bottom first, then a legend of the codes actually used."""
    layers = SCHEMATICS[name]()
    cell = 22
    used = []
    out = ['<div class="schem">']
    for i, layer in enumerate(layers):
        w, d = len(layer[0]), len(layer)
        label = LAYER_WORD[lang].format(n=i + 1)
        if i == 0:
            label += f" ({BOTTOM[lang]})"
        elif i == len(layers) - 1:
            label += f" ({TOP[lang]})"
        svg = [f'<svg viewBox="0 0 {w * cell} {d * cell}" width="{w * cell}" height="{d * cell}" role="img" aria-label="{html.escape(label)}">']
        for z, row in enumerate(layer):
            for x, code in enumerate(row):
                if code not in used:
                    used.append(code)
                colour = BLOCKS[code][0]
                cls = ' class="air"' if code == "." else ""
                svg.append(f'<rect{cls} x="{x * cell + 1}" y="{z * cell + 1}" width="{cell - 2}" height="{cell - 2}" rx="3" fill="{colour}"><title>{html.escape(BLOCKS[code][1][lang])}</title></rect>')
                if code not in ".C":
                    svg.append(f'<text x="{x * cell + cell / 2}" y="{z * cell + cell / 2 + 4}" text-anchor="middle">{code}</text>')
        svg.append("</svg>")
        out.append(f'<figure class="layer">{"".join(svg)}<figcaption>{html.escape(label)}</figcaption></figure>')
    out.append("</div>")
    legend = "".join(
        f'<li><i style="background:{BLOCKS[c][0]}"{" class=air" if c == "." else ""}>{c if c not in ".C" else ""}</i>{html.escape(BLOCKS[c][1][lang])}</li>'
        for c in sorted(used, key=list(BLOCKS).index)
    )
    out.append(f'<ul class="legend-list">{legend}</ul>')
    return "".join(out)
