"""
core.py — The Quiet Engine
MRJ3.0 | Mr. Jealousy Interior Intelligence System
"""

from typing import TypedDict, List, Dict, Any, Optional


class ProductColor(TypedDict):
    name: str
    hex: str
    material: str
    sampleUrl: str
    galleryUrls: Optional[List[str]]


class ColourPaletteEntry(TypedDict):
    hex_code: str
    extracted_source: str
    matched_catalog_color: str


class WindowCheck(TypedDict):
    obstacles: bool
    windowType: str
    detectedWindowCount: int
    recommendation: str
    reasoning: str
    specialConsiderations: str


class ProductSuggestion(TypedDict):
    productType: str
    material: str
    colorName: str
    colorHex: str
    suitabilityScore: int
    reasoning: str


class AnalysisResult(TypedDict):
    style: str
    styleSummary: str
    styleDescription: str
    roomMood: str
    lightingConditions: str
    colour_palette: List[ColourPaletteEntry]
    windowCheck: WindowCheck
    materialSuggestions: List[str]
    suggestions: List[ProductSuggestion]


class RenderInstruction(TypedDict):
    product_type: str
    color_name: str
    hex_code: str
    mount_type: str
    window_sections: int
    lighting_condition: str
    state: str
    slat_width: Optional[str]
    ladder_tape: bool
    scene_description: str
    negative_prompt: str
    camera_angle: str
    room_context: str


# ── SYSTEM CONSTANTS ───────────────────────────────────────────────────────────

PHASE_COUNT       = 9
ANALYSIS_MODEL    = "claude-opus-4-5"
FALLBACK_MODEL    = "claude-sonnet-4-5"
RENDER_MODEL      = "models/gemini-2.5-flash-preview-05-20"
UPLOAD_PATH       = "data/uploads"
JSON_CACHE_PATH   = "data/json_convert_to_text.txt"
ANALYSE_JSON_PATH = "data/analyse.json"
SUPABASE_BUCKET   = "uploads"


# ── PRODUCT RULES ──────────────────────────────────────────────────────────────

ALLOWED_PRODUCT_TYPES: List[str] = [
    "Aluminium Jaloezieën",
    "Houten Jaloezieën",
]

ALLOWED_WOODEN_SUBTYPES: List[str] = [
    "Paulownia",
    "Bamboo",
    "Abachi",
]

MOUNT_LABELS: Dict[str, str] = {
    "inside":  "in de dag",
    "outside": "op de dag",
}


# ── MR. JEALOUSY CATALOG ───────────────────────────────────────────────────────

MR_JEALOUSY_CATALOG: Dict[str, List[ProductColor]] = {
    "Aluminium Jaloezieën": [
        {"name": "Like RAL9002",      "hex": "#E9E5CE", "material": "Aluminium", "sampleUrl": "/media/Catalogus/COLOR%20SAMPLES/Like-RAL9002%20A.png"},
        {"name": "Like RAL9010",      "hex": "#F7F9EF", "material": "Aluminium", "sampleUrl": "/media/Catalogus/COLOR%20SAMPLES/Like-RAL9010%20A.png"},
        {"name": "Moody Munt",        "hex": "#98FF98", "material": "Aluminium", "sampleUrl": "/media/Catalogus/COLOR%20SAMPLES/Moody-Munt%20A.png"},
        {"name": "Naughty Aubergine", "hex": "#472C4C", "material": "Aluminium", "sampleUrl": "/media/Catalogus/COLOR%20SAMPLES/Naughty-Aubergine%20A.png"},
        {"name": "Oud Green",         "hex": "#8F9779", "material": "Aluminium", "sampleUrl": "/media/Catalogus/COLOR%20SAMPLES/Oud-Green%20A.png"},
        {"name": "Peachy Pink",       "hex": "#FFDAB9", "material": "Aluminium", "sampleUrl": "/media/Catalogus/COLOR%20SAMPLES/Peachy-Pink%20A.png"},
        {"name": "Poolside Blue",     "hex": "#00BFFF", "material": "Aluminium", "sampleUrl": "/media/Catalogus/COLOR%20SAMPLES/Poolside-Blue%20A.png"},
        {"name": "Purple Grey",       "hex": "#6D6875", "material": "Aluminium", "sampleUrl": "/media/Catalogus/COLOR%20SAMPLES/Purple-Grey%20A.png"},
        {"name": "Rocky Rood",        "hex": "#8B0000", "material": "Aluminium", "sampleUrl": "/media/Catalogus/COLOR%20SAMPLES/Rocky-Rood%20A.png"},
        {"name": "Rusty Retro",       "hex": "#B7410E", "material": "Aluminium", "sampleUrl": "/media/Catalogus/COLOR%20SAMPLES/Rusty-Retro%20A.png"},
        {"name": "Silk Zwart",        "hex": "#050505", "material": "Aluminium", "sampleUrl": "/media/Catalogus/COLOR%20SAMPLES/Silk-Zwart%20A.png"},
        {"name": "Skinny Dip",        "hex": "#F4C2C2", "material": "Aluminium", "sampleUrl": "/media/Catalogus/COLOR%20SAMPLES/Skinny-Dip%20A.png"},
        {"name": "Smokey Grey",       "hex": "#708090", "material": "Aluminium", "sampleUrl": "/media/Catalogus/COLOR%20SAMPLES/Smokey-Grey%20A.png"},
        {"name": "Soft Naakt",        "hex": "#E3BC9A", "material": "Aluminium", "sampleUrl": "/media/Catalogus/COLOR%20SAMPLES/Soft-Naakt%20A.png"},
        {"name": "Soft Terra",        "hex": "#E2725B", "material": "Aluminium", "sampleUrl": "/media/Catalogus/COLOR%20SAMPLES/Soft-Terra%20A.png"},
        {"name": "Stevig Taupe",      "hex": "#483C32", "material": "Aluminium", "sampleUrl": "/media/Catalogus/COLOR%20SAMPLES/Stevig-Taupe%20A.png"},
        {"name": "Stormy Taupe",      "hex": "#5C5552", "material": "Aluminium", "sampleUrl": "/media/Catalogus/COLOR%20SAMPLES/Stormy-Taupe%20A.png"},
        {"name": "Twijfel Taupe",     "hex": "#876C5E", "material": "Aluminium", "sampleUrl": "/media/Catalogus/COLOR%20SAMPLES/Twijfel-Taupe%20A.png"},
        {"name": "Velvet Brown",      "hex": "#4B3621", "material": "Aluminium", "sampleUrl": "/media/Catalogus/COLOR%20SAMPLES/Velvet-Brown%20A.png"},
        {"name": "Bold Bruin",        "hex": "#654321", "material": "Aluminium", "sampleUrl": "/media/Catalogus/COLOR%20SAMPLES/Bold-Bruin%20A.png"},
        {"name": "Butter Geel",       "hex": "#F3E5AB", "material": "Aluminium", "sampleUrl": "/media/Catalogus/COLOR%20SAMPLES/Butter-Geel%20A.png"},
        {"name": "Cherry Pop",        "hex": "#D2042D", "material": "Aluminium", "sampleUrl": "/media/Catalogus/COLOR%20SAMPLES/Cherry-Pop%20A.png"},
        {"name": "Cool Grey",         "hex": "#A9A9A9", "material": "Aluminium", "sampleUrl": "/media/Catalogus/COLOR%20SAMPLES/Cool-Grey%20A.png"},
        {"name": "Cosmic Blauw",      "hex": "#000080", "material": "Aluminium", "sampleUrl": "/media/Catalogus/COLOR%20SAMPLES/Cosmic-Blauw%20A.png"},
        {"name": "Crazy Karamel",     "hex": "#C68E17", "material": "Aluminium", "sampleUrl": "/media/Catalogus/COLOR%20SAMPLES/Crazy-Karamel%20A.png"},
        {"name": "Drop Zwart",        "hex": "#1A1A1A", "material": "Aluminium", "sampleUrl": "/media/Catalogus/COLOR%20SAMPLES/Drop-Zwart%20A.png"},
        {"name": "Fluffy Naakt",      "hex": "#F5DEB3", "material": "Aluminium", "sampleUrl": "/media/Catalogus/COLOR%20SAMPLES/Fluffy-Naakt%20A.png"},
        {"name": "Brushed Nikkel",    "hex": "#B0C4DE", "material": "Aluminium", "sampleUrl": "/media/Catalogus/COLOR%20SAMPLES/Geborsteld-Nikkel%20A.png"},
        {"name": "Koffie Koper",      "hex": "#B87333", "material": "Aluminium", "sampleUrl": "/media/Catalogus/COLOR%20SAMPLES/Koffie-Koper%20A.png"},
        {"name": "Glitter Gold",      "hex": "#FFD700", "material": "Aluminium", "sampleUrl": "/media/Catalogus/COLOR%20SAMPLES/Glitter-Gold%20A.png"},
        {"name": "Goed Grijs",        "hex": "#808080", "material": "Aluminium", "sampleUrl": "/media/Catalogus/COLOR%20SAMPLES/Goed-Grijs%20A.png"},
        {"name": "Jet Black",         "hex": "#050505", "material": "Aluminium", "sampleUrl": "/media/Catalogus/COLOR%20SAMPLES/Jet-Black%20A.png"},
        {"name": "Juicy Olive",       "hex": "#808000", "material": "Aluminium", "sampleUrl": "/media/Catalogus/COLOR%20SAMPLES/Juicy-Olive%20A.png"},
        {"name": "Koel Blue",         "hex": "#AEC6CF", "material": "Aluminium", "sampleUrl": "/media/Catalogus/COLOR%20SAMPLES/Koel-Blue%20A.png"},
        {"name": "Like RAL9001",      "hex": "#FDF4E3", "material": "Aluminium", "sampleUrl": "/media/Catalogus/COLOR%20SAMPLES/Like-RAL9001%20A.png"},
        {"name": "Cowboy Koper",      "hex": "#8B4513", "material": "Aluminium", "sampleUrl": "/media/Catalogus/ALUMINIUM%20JALOEZIE/COWBOY%20KOPER/ALU_7381_Cowboy-Koper_BRUSHED_DA.jpeg"},
    ],
    "Houten Jaloezieën": [
        {"name": "Like RAL9016",    "hex": "#F0F8FF", "material": "Hout", "sampleUrl": "/media/Catalogus/COLOR%20SAMPLES/Like-RAL9016%20A.png"},
        {"name": "Mister Sandman",  "hex": "#C2B280", "material": "Hout", "sampleUrl": "/media/Catalogus/COLOR%20SAMPLES/Mister-Sandman.png"},
        {"name": "Misty Bamboo",    "hex": "#DCC098", "material": "Hout", "sampleUrl": "/media/Catalogus/COLOR%20SAMPLES/Misty-Bamboo.png"},
        {"name": "Oak Mooi",        "hex": "#C3A376", "material": "Hout", "sampleUrl": "/media/Catalogus/COLOR%20SAMPLES/Oak-Mooi.png"},
        {"name": "Parel White",     "hex": "#F5F5F5", "material": "Hout", "sampleUrl": "/media/Catalogus/COLOR%20SAMPLES/Parel-White.png"},
        {"name": "Shades of Grey",  "hex": "#808080", "material": "Hout", "sampleUrl": "/media/Catalogus/COLOR%20SAMPLES/Shades-of-Grey.png"},
        {"name": "Smokey Taupe",    "hex": "#9E958C", "material": "Hout", "sampleUrl": "/media/Catalogus/COLOR%20SAMPLES/Smokey-Taupe.png"},
        {"name": "Teder Taupe",     "hex": "#D8CCBB", "material": "Hout", "sampleUrl": "/media/Catalogus/COLOR%20SAMPLES/Teder-Taupe.png"},
        {"name": "Tiki Taupe",      "hex": "#A69686", "material": "Hout", "sampleUrl": "/media/Catalogus/COLOR%20SAMPLES/Tiki-Taupe.png"},
        {"name": "BBQ Black",       "hex": "#111111", "material": "Hout", "sampleUrl": "/media/Catalogus/COLOR%20SAMPLES/BBQ-Black.png"},
        {"name": "Behoorlijk Black","hex": "#222222", "material": "Hout", "sampleUrl": "/media/Catalogus/COLOR%20SAMPLES/Behoorlijk-Black.png"},
        {"name": "Bonsai Bamboo",   "hex": "#6B8E23", "material": "Hout", "sampleUrl": "/media/Catalogus/COLOR%20SAMPLES/Bonsai_Bamboo.png"},
        {"name": "Bourbon Bamboo",  "hex": "#654321", "material": "Hout", "sampleUrl": "/media/Catalogus/COLOR%20SAMPLES/Bourbon-Bamboo.png"},
        {"name": "De Naturist",     "hex": "#D2B48C", "material": "Hout", "sampleUrl": "/media/Catalogus/COLOR%20SAMPLES/De-Naturist.png"},
        {"name": "Donker Brown",    "hex": "#3B2F2F", "material": "Hout", "sampleUrl": "/media/Catalogus/COLOR%20SAMPLES/Donker-Brown.png"},
        {"name": "Eigenlijk Eiken", "hex": "#A0785A", "material": "Hout", "sampleUrl": "/media/Catalogus/COLOR%20SAMPLES/Eigenlijk-Eiken.png"},
        {"name": "Flat White",      "hex": "#FFFAF0", "material": "Hout", "sampleUrl": "/media/Catalogus/COLOR%20SAMPLES/Flat-White.png"},
        {"name": "Gebroken White",  "hex": "#FDF5E6", "material": "Hout", "sampleUrl": "/media/Catalogus/COLOR%20SAMPLES/Gebroken-White.png"},
        {"name": "Haver Milk",      "hex": "#EFEBD8", "material": "Hout", "sampleUrl": "/media/Catalogus/COLOR%20SAMPLES/Haver-Milk.png"},
        {"name": "Smokey Bamboo",   "hex": "#4A4A4A", "material": "Hout", "sampleUrl": "/media/Catalogus/HOUTEN%20JALOEZIE/SMOKEY%20BAMBOO/BAMBOE-JALOEZIE_5077_GRANITE_0fc56d7f-.jpeg"},
        {"name": "Deep Zwart",      "hex": "#080808", "material": "Hout", "sampleUrl": "/media/Catalogus/HOUTEN%20JALOEZIE/DEEP%20ZWART/HOUTEN-JALOEZIE_BLACK_04686c36-330d-4935-.jpeg"},
    ],
}


# ── DESCRIPTOR MAPS ────────────────────────────────────────────────────────────

STATE_MAP: Dict[str, str] = {
    "Tot de helft": (
        "lowered exactly halfway. The bottom 50% of the window is clear glass. "
        "The top 50% is covered by the blind, casting slat shadows."
    ),
    "Geheel uitgerold": (
        "fully lowered, covering the entire window height from top to bottom. "
        "Light is filtered through the slats, creating soft striped shadow patterns."
    ),
}

MOUNTING_MAP: Dict[str, str] = {
    "in de dag": (
        "INSIDE MOUNT (in de dag): The blind is installed INSIDE the window recess. "
        "The headrail sits at the top of the recess. Width equals internal clear opening minus 2–5mm each side. "
        "The blind does NOT overlap the wall. Headrail flush with front edge of recess."
    ),
    "op de dag": (
        "OUTSIDE MOUNT (op de dag): The blind is mounted on the WALL SURFACE above the window frame. "
        "The headrail sits just above the kozijn, anchored to wall. "
        "Width extends 5–10cm past each side of the window frame. "
        "Blind stands proud of wall by bracket depth (4–6cm)."
    ),
    "Twee aparte jaloezieën voor hoekraam": "as two separate blinds for the corner window",
}

LIGHTING_MAP: Dict[str, str] = {
    "Ochtend (Koel)":      "MORNING LIGHT. Low angle East sun. 5500K. Long crisp shadows.",
    "Middag (Helder)":     "MID-DAY SUN. High overhead. 6000K. Short sharp high-contrast shadows.",
    "Zonsondergang (Warm)":"GOLDEN HOUR. Very low West sun. 3500K. Extremely long dramatic shadows, warm glow.",
    "Avond (Sfeervol)":    "EVENING. No direct sun. Artificial interior lamps 2700K. Soft multi-directional shadows.",
    "Bewolkt (Diffuus)":   "OVERCAST. Diffuse soft white 6500K. No hard shadows. Ambient only.",
}

PRODUCT_MAP: Dict[str, str] = {
    "Houten Jaloezieën":    "Premium Wooden Horizontal Venetian Blinds. Matte/Satin finish, visible wood grain, warm reflections.",
    "Aluminium Jaloezieën": "Sleek Aluminum Horizontal Venetian Blinds. Smooth metallic finish, specular highlights, cool reflections.",
}


# ── MASTER PROMPT ──────────────────────────────────────────────────────────────

MASTER_PROMPT = """\
You are a World-Class Interior Vision Architect, Window Treatment Surveyor, Product Configurator, \
and Lighting Physicist with elite computer vision precision.
You specialize exclusively in high-end horizontal Venetian blinds for Mr. Jealousy.

MISSION
Analyse the uploaded room image with forensic, pixel-level precision and return one technically \
correct, catalog-locked, installation-aware JSON object.

ABSOLUTE PRODUCT LOCK — ONLY use products that literally exist in the Mr. Jealousy catalog below.
ONLY ALLOWED: Houten Jaloezieën, Aluminium Jaloezieën (subtypes: Paulownia, Bamboo, Abachi)
STRICTLY FORBIDDEN: Invented products, materials, colors, or finish names not in the catalog.

GOLDEN RULE: A beautiful recommendation that cannot exist physically is a failed result.

PRIMARY PRIORITIES:
1. physical correctness  2. mounting correctness  3. catalog truth
4. window geometry       5. perspective realism    6. style harmony

MR. JEALOUSY CATALOG (AUTHORITATIVE):
[CATALOG]

OUTPUT: Return ONLY valid JSON in Dutch. No markdown. No code fences. No explanation.

FAIL CONDITIONS: non-catalog product, invented color, ignored handles/vents, invalid JSON, \
anything other than Dutch JSON, beauty over feasibility.
"""


# ── PHASE LAWS ─────────────────────────────────────────────────────────────────

PHASE_LAWS: Dict[int, Dict[str, Any]] = {
    1: {
        "name": "IMAGE_UPLOAD",
        "laws": [
            "Upload the image to Supabase simultaneously with triggering analyse_claude.py.",
            "The result is a temporary cached JSON file at data/json_convert_to_text.txt.",
            "The JSON must be read and interpreted as a fundamental law to obey.",
        ],
        "negative_seeds": [],
    },
    2: {
        "name": "IMAGE_QUALITY_COMPLIANCE",
        "laws": [
            "Check: Alignment — no extreme rotation.",
            "Check: Framing — window clearly visible, not cut off.",
            "Check: Lighting — not completely dark or overexposed.",
            "Check: Focus — not too blurry to read window details.",
            "Check: Resolution — sufficient for forensic window analysis.",
            "Check: Angle — allows forensic analysis.",
            "Check: Image Size — within accepted limits.",
            "Check: Unwanted content — no explicit or offensive content.",
            "Check: Format — PNG, JPG, or WEBP only.",
            "If any check fails: return error JSON with specific feedback.",
            "If all pass: return {\"quality_pass\": true}",
        ],
        "negative_seeds": [],
    },
    3: {
        "name": "EXTRACT_INTERIOR_THESIS",
        "laws": [
            "Determine: style (e.g. Japandi, Industrial, Hotel Chic, Scandinavisch).",
            "Determine: room mood, luxury level, warmth/coolness, material language, line language.",
            "Write: style — single label string.",
            "Write: styleSummary — max 2 sentences.",
            "Write: styleDescription — min 200 words in Dutch.",
        ],
        "negative_seeds": [],
    },
    4: {
        "name": "EXTRACT_COLOR_DNA",
        "laws": [
            "Extract exactly 5 real visible colors from the room.",
            "Each matched_catalog_color must literally exist in the MR. JEALOUSY catalog.",
            "Each color must come from a clearly visible room surface or object.",
            "For each return: hex_code, extracted_source, matched_catalog_color.",
        ],
        "negative_seeds": [],
    },
    5: {
        "name": "WINDOW_ARCHITECTURE",
        "laws": [
            "Determine: outer frame bounds, glass bounds, exact number of distinct glass sections.",
            "Determine: sash divisions, mullions/transoms, recess depth (cm), sill presence.",
            "Determine: frame material, handle presence/side, vent/grille/lock presence.",
            "Determine: opening mechanism, opening direction, fixed or operable.",
            "Determine: nearby collision risks, glazing type, stack height clearance.",
            "Classify window type: Tilt-turn / Fixed / Casement / Sliding / Pivot / French / Multi-pane.",
            "Count the EXACT number of distinct visible glass sections.",
        ],
        "negative_seeds": [],
    },
    6: {
        "name": "MOUNTING_STRATEGY",
        "laws": [
            "NEVER propose a physically impossible placement.",
            "RULE 1 — DEPTH: IF recess depth < 5cm → OUTSIDE MOUNT mandatory.",
            "RULE 2 — PROTRUSION: IF handle/vent exists AND protrusion > recess depth → OUTSIDE MOUNT.",
            "RULE 3 — KINEMATIC: IF tilt-turn window → check stack clearance. If insufficient → OUTSIDE MOUNT.",
            "RULE 4 — CORNER: IF side clearance < 3cm AND outside mount → FLAG ERROR.",
            "RULE 5 — DEFAULT: IF rules 1–4 all false → INSIDE MOUNT (in de dag).",
        ],
        "negative_seeds": [],
    },
    7: {
        "name": "LIGHTING_CONDITIONS",
        "laws": [
            "Determine: light direction, intensity (lux), softness, temperature (Kelvin).",
            "Determine: natural vs artificial % contribution.",
            "Determine: reflection on glass/frame, shadow behavior.",
            "Determine: whether wood or aluminium integrates more naturally with this light.",
        ],
        "negative_seeds": [],
    },
    8: {
        "name": "CATALOG_MATCH",
        "laws": [
            "ABSOLUTE PRODUCT LOCK: only products literally in the MR. JEALOUSY catalog.",
            "ONLY ALLOWED: Houten Jaloezieën, Aluminium Jaloezieën.",
            "Allowed wooden subtypes: Paulownia, Bamboo, Abachi.",
            "FORBIDDEN: invented products, materials, colors, finish names.",
        ],
        "negative_seeds": [],
    },
    9: {
        "name": "RENDER_PLANNING",
        "laws": [
            "Prepare exact render instructions for the visualization model.",
            "Output must conform to the RenderInstruction schema.",
            "scene_description must be minimum 200 words in Dutch.",
            "Mounting geometry from Phase 6 must be reflected verbatim.",
            "Lighting physics from Phase 7 must drive shadow/reflection specs.",
            "Product and color must exactly match Phase 8 catalog selection.",
            "Include negative_prompt listing all rendering artifacts to avoid.",
            "Specify camera_angle matching the original uploaded image perspective.",
        ],
        "negative_seeds": [],
    },
}


# ── HELPER FUNCTIONS ───────────────────────────────────────────────────────────

def get_phase_prompt(phase: int) -> str:
    """Build the complete system prompt for a given phase number."""
    if phase not in PHASE_LAWS:
        raise ValueError(f"Phase {phase} does not exist. Valid phases: 1–{PHASE_COUNT}.")

    base_prompt = MASTER_PROMPT.replace("[CATALOG]", get_catalog_as_text())
    entry = PHASE_LAWS[phase]
    laws_text = "\n".join(f"  - {law}" for law in entry["laws"])
    negative_text = ""
    if entry["negative_seeds"]:
        seeds = "\n".join(f"  - {seed}" for seed in entry["negative_seeds"])
        negative_text = f"\nNEGATIVE SEEDS (forbidden behaviors in this phase):\n{seeds}"

    return (
        f"{base_prompt}\n"
        f"{'─' * 60}\n"
        f"ACTIVE PHASE: {phase} — {entry['name']}\n"
        f"{'─' * 60}\n"
        f"LAWS FOR THIS PHASE (mandatory, in order):\n{laws_text}"
        f"{negative_text}"
    )


def get_catalog_as_text() -> str:
    """Format MR_JEALOUSY_CATALOG as plain readable text for prompt injection."""
    lines: List[str] = ["MR. JEALOUSY CATALOG (authoritative — only these products exist):"]
    for product_type, colors in MR_JEALOUSY_CATALOG.items():
        lines.append(f"\n{product_type}:")
        for color in colors:
            lines.append(f"  - {color['name']} | hex: {color['hex']} | material: {color['material']}")
    return "\n".join(lines)


def get_allowed_colors(product_type: str) -> List[ProductColor]:
    """Return the full color list for a given product type from the catalog."""
    if product_type not in MR_JEALOUSY_CATALOG:
        raise ValueError(f"Product type '{product_type}' not in catalog. Allowed: {ALLOWED_PRODUCT_TYPES}")
    return MR_JEALOUSY_CATALOG[product_type]


def validate_phase_order(current: int, expected: int) -> bool:
    """Enforce chronological phase execution."""
    return current == expected


def resolve_mounting(key: str) -> str:
    """Return full mounting description from MOUNTING_MAP."""
    return MOUNTING_MAP.get(key, MOUNTING_MAP["in de dag"])


def resolve_lighting(key: str) -> str:
    """Return full lighting description from LIGHTING_MAP."""
    return LIGHTING_MAP.get(key, LIGHTING_MAP["Middag (Helder)"])
