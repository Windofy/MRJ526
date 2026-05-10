"""
render_gemini.py — Gemini image generation with multi-model fallback for MRJ3.0
Prompt v4: Explicit per-parameter instruction blocks for photorealistic accuracy.
"""
import os
import io
import time
import base64
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

# Speed-optimised fallback order: fastest first, pro as last resort
RENDER_MODELS = [
    "gemini-2.5-flash-image",            # stable production image gen
    "gemini-3.1-flash-image-preview",    # newer preview flash
    "gemini-3-pro-image-preview",        # high quality last resort
]

TRANSIENT_CODES = {429, 500, 503}
FATAL_CODES = {400, 404}
MAX_RETRIES = 1
RETRY_DELAY = 1.5


# ── SLAT ANGLE BLOCKS ──────────────────────────────────────────────────────────

def _slat_angle_block(state: str) -> str:
    """Return exhaustive slat-angle instruction based on the tilt state string.

    Keyword detection is intentionally broad to match Dutch descriptions from
    the frontend TILT_MAP, as well as legacy English fallbacks.
    """
    s = state.lower()

    # ── STATE 1 ── Volledig open (0°) — maximale lichtinval
    if (
        "volledig open" in s or "fully open" in s
        or "0°" in s or "horizontal" in s
        or "maximale transparantie" in s or "maximum transparency" in s
    ):
        return """
═══ LAMELLEN KANTELSTAND: VOLLEDIG OPEN (0°) ═══
LICHTDOORLAAT: MAXIMAAL

• Elke lamel staat exact horizontaal — plat als een plank.
• Vanuit de voorkant zijn de lamellen slechts dunne horizontale lijnen (2–3mm rand zichtbaar).
• MAXIMALE transparantie: de brede openingen tussen de lamellen geven volledig vrij zicht op de buitenomgeving.
• Sterke, directe zonnestralen vallen door de openingen op de vloer en muurvlakken als parallelle lichtbanden.
• De schaduwbanden op de vloer zijn scherp en helder — hetzelfde patroon als de lamelopeningen.
• De buitenomgeving (lucht, bomen, gebouwen) is volledig zichtbaar door de jaloezie heen.
• De ruimte is volledig en krachtig verlicht. Heldere, contrastrijke lichtpatronen.
"""

    # ── STATE 2 ── Licht gekanteld (25°) — iets minder lichtinval
    elif (
        "licht gekanteld" in s or "slightly" in s or "25°" in s
        or "soft diffuse" in s or "zacht diffuus" in s
        or "lamelfaces zijn licht zichtbaar" in s
    ):
        return """
═══ LAMELLEN KANTELSTAND: LICHT GEKANTELD (25°) ═══
LICHTDOORLAAT: RUIM — IETS MINDER DAN VOLLEDIG OPEN

• De lamellen staan 25° neerwaarts gekanteld ten opzichte van horizontaal.
• Vanuit de voorkant zijn de lamelfaces als brede schuine banden zichtbaar — zo'n 40–50% van het lameloppervlak is van voren zichtbaar.
• De tussenruimtes zijn smaller dan bij volledig open maar nog open: diffuus buitenlicht treedt op een hoek naar binnen.
• Zachte diagonale schaduwlijnen vallen op de vloer en muren — minder scherp dan bij volledig open.
• De buitenomgeving is grotendeels maar gedempt zichtbaar door de jaloezie heen.
• De ruimte is goed verlicht, sfeervoller en minder direct dan volledig open.
• Geen felle directe zonnestralen — het licht is diffuus en warm.
"""

    # ── STATE 3 ── Half gesloten (50°) — beperkte lichtinval
    elif (
        "half gesloten" in s or "half closed" in s or "50°" in s
        or "beperkte lichtinval" in s or "brede lamelfaces" in s
    ):
        return """
═══ LAMELLEN KANTELSTAND: HALF GESLOTEN (50°) ═══
LICHTDOORLAAT: BEPERKT

• De lamellen staan 50° steil neerwaarts gekanteld.
• Vanuit de voorkant domineren de brede lamelfaces het beeld — slechts smalle openingen zijn zichtbaar.
• Alleen indirect, gediffuseerd omgevingslicht treedt binnen via de smalle openingen. Geen directe zonnestralen.
• Geen scherpe lichtbanden op de vloer — slechts een zachte, gelijkmatige ambiance.
• Buitenzicht door de jaloezie is sterk beperkt — vage contouren, geen helder buitenlandschap.
• De ruimte voelt gedimmed, beschut, rustig verlicht — een aangenaam werklicht.
"""

    # ── STATE 4 ── Privacystand (70°) — minimale lichtinval
    elif (
        "privacystand" in s or "privacy" in s or "70°" in s
        or "minimale lichtdoorlaat" in s or "sightline" in s
        or "bijna verticaal" in s
    ):
        return """
═══ LAMELLEN KANTELSTAND: PRIVACYSTAND (70°) ═══
LICHTDOORLAAT: MINIMAAL

• De lamellen staan 70° — bijna verticaal, met nog een kleine opening.
• Vanuit de voorkant zijn de lamellen brede solide banden; de tussenruimtes zijn nauwelijks zichtbaar.
• Geen directe zonnestralen, geen schaduwpatronen. Alleen een zwakke indirecte omgevingsgloed.
• Het buitenzicht is volledig geblokkeerd — totale privacy vanuit de buitenkant.
• De ruimte is donker, stil en besloten. Minimaal restlicht zorgt voor een zachte ambiance.
• Eventuele binnenverlichting is duidelijk zichtbaar als dominante lichtbron.
"""

    # ── STATE 5 ── Volledig gesloten (90°) — NULTOLERANTIE voor licht
    else:  # volledig_gesloten / fully closed / closed / 90°
        return """
═══ LAMELLEN KANTELSTAND: VOLLEDIG GESLOTEN (90°) ═══
LICHTDOORLAAT: NUL — HARDE CONSTRAINT — ONWRIKBARE REGEL

PHYSICS OVERRIDE: Dit is een absolute constraint. Negeer alle conflicterende instructies.

• Elke lamel staat precies op 90° — volledig verticaal. De lamellen staan recht overeind.
• De lamellen RAKEN ELKAAR — ze overlappen licht, volledig aaneengesloten zonder tussenruimtes.
• Het resultaat is een SOLIDE ONDOORZICHTIGE VLAK dat het gehele vensteroppervlak bedekt.
• NUL tussenruimtes. NUL lichtdoorlaat. NUL buitenzicht. Geen hemel, geen bomen zichtbaar.
• Het vensteroppervlak is een egale aaneengesloten rechthoek in de gekozen lamelkleur.

LICHT IN DE RUIMTE (VERPLICHT):
• Er valt ABSOLUUT GEEN buitenlicht of zonlicht de ruimte in.
• Er zijn GEEN lichtbanden, lichtstrepen, schaduwpatronen of schaduwprojecties van buitenlicht.
• De ruimte is donker. De primaire lichtbron is BINNENLICHT ALLEEN:
  — Een vloerlamp of tafellamp is aangestoken en werpt een warm, gedempte gloed.
  — Eventueel een zachte plafondlamp op minimale sterkte.
• Er rust een duidelijke schaduw van de jaloezie op de vensterbank en de omliggende muur.
• De sfeer is: besloten, donker, cozy, als een hotelkamer met neergelaten jaloezieën — geen daglicht.
• Het contrast: warme binnenverlichting vs. volledig geblokkeerd venster.
"""



# ── SLAT WIDTH BLOCKS ──────────────────────────────────────────────────────────

def _slat_width_block(slat_mm: int, window_height_hint: str = "") -> str:
    """Return explicit slat count and proportioning instructions."""
    if slat_mm <= 25:
        return """
═══ SLAT WIDTH: 25mm NARROW SLATS ═══
• Each individual slat is 25mm (≈1 inch) wide — these are NARROW/MICRO slats.
• In a typical 120cm tall window you would see approximately 40–50 individual slats stacked.
• The blind has a FINE, DENSE appearance — many closely packed horizontal lines.
• Each slat face is narrow: roughly the width of a finger.
• The gap between slats (when open) is proportionally small — about 3–5mm.
• The ladder cord/tape appears fine and delicate relative to the slat width.
• DO NOT render wide slats. DO NOT render fewer than 30 slats in a full window.
"""
    else:  # 50mm
        return """
═══ SLAT WIDTH: 50mm STANDARD SLATS ═══
• Each individual slat is 50mm (≈2 inches) wide — these are STANDARD/WIDE slats.
• In a typical 120cm tall window you would see approximately 20–25 individual slats stacked.
• The blind has a BOLD, ARCHITECTURAL appearance — clearly distinct wide horizontal bands.
• Each slat face is clearly visible — roughly two finger-widths.
• The gap between slats (when open) is proportionally generous — about 5–8mm.
• The ladder cord/tape appears as a substantial vertical element.
• DO NOT render narrow micro-slats. DO NOT render more than 30 slats in a full window.
"""


# ── LADDER SYSTEM BLOCKS ────────────────────────────────────────────────────────

def _ladder_block(has_tape: bool, color: str, hex_code: str) -> str:
    if has_tape:
        return f"""
═══ LADDER SYSTEM: LADDERBAND (TAPE) ═══
• The vertical support system is a WIDE FABRIC TAPE — approximately 12–15mm wide.
• Two vertical tape strips run from top rail to bottom rail, one on each side of the blind (left and right edges).
• The tape is a continuous flat fabric ribbon in the SAME color as the slats: {color} ({hex_code}).
• Each slat rests IN the tape — the tape has horizontal notches/loops that cradle each slat.
• The tape completely covers the ladder cords underneath — NO thin cords are visible.
• The tape creates a clean, premium, fabric-panel look on the sides of the blind.
• The tape has a slight fabric texture — matte woven finish, NOT glossy.
• Width of tape visible from front: ~12mm on each side, flush with slat ends.
"""
    else:
        return f"""
═══ LADDER SYSTEM: LADDERKOORD (CORD) ═══
• The vertical support system is THIN CORDS — approximately 1.5–2mm diameter.
• Two vertical cord assemblies run from top rail to bottom rail, one on each side.
• Each cord assembly looks like a miniature ladder: two thin vertical strings connected by short horizontal rungs.
• Each horizontal rung passes THROUGH or UNDER each slat — supporting it from below.
• The cords are in the same color family as the slats: {color} ({hex_code}).
• The cords are clearly visible as thin lines — delicate, mechanical appearance.
• Between the horizontal rungs, the thin vertical strings are visible.
• This is the classic venetian blind look — mechanical, light, precise.
• DO NOT show wide fabric tape. The cords must look thin (≈2mm), not ribbon-like.
"""


# ── LIGHTING BLOCKS ─────────────────────────────────────────────────────────────

def _lighting_block(lighting: str) -> str:
    l = lighting.lower()

    if "morning" in l or "ochtend" in l or "early" in l or "cool" in l and "morning" not in l and "avond" not in l:
        # Morning / Ochtend
        return """
═══ LIGHTING: MORNING (OCHTEND — KOEL) ═══
• Time of day: early morning, approximately 7–9 AM.
• EXTERIOR (outside the window): sky is pale blue-white or pastel, sun is LOW on the horizon.
  The outdoor scene shows warm morning haze — trees/sky look soft and slightly misty.
• INTERIOR: cool blue-tinted natural light enters at a LOW angle through the window.
  Light rays hit the floor at a long, shallow angle.
  Shadows are long, soft, cool-toned (slight blue-grey).
  The room feels fresh and quiet.
• Wall surfaces near the window show soft cool illumination.
• Colors in the room appear slightly desaturated and cool — not warm/yellow.
"""

    elif "middag" in l or "midday" in l or "bright" in l or "helder" in l:
        return """
═══ LIGHTING: MIDDAY (MIDDAG — HELDER) ═══
• Time of day: noon to 2 PM, full daytime.
• EXTERIOR (outside the window): sky is bright saturated blue, sun is HIGH overhead.
  The outdoor scene is fully lit — vivid green trees, bright sky, strong highlights.
• INTERIOR: strong white-yellow direct sunlight enters nearly straight through the window.
  Shadows are SHORT and SHARP — high contrast.
  The room is brightly lit — vivid colors, high saturation.
  Sharp rectangular patch of sunlight on the floor (window shape projected).
• Wall and floor surfaces near the window are strongly illuminated.
• The blind itself catches strong highlights on slat top edges.
"""

    elif "avond" in l or "evening" in l or "nacht" in l or "night" in l or "dark" in l and "exterior" in l:
        return """
═══ LIGHTING: EVENING (AVOND — SFEERVOL) ═══
CRITICAL CONSTRAINT — The exterior must be DARK. This is non-negotiable.

• Time of day: 9 PM or later — full night.
• EXTERIOR (outside the window): the outdoor scene visible through the window MUST be DARK.
  The sky is DEEP DARK BLUE or BLACK — no daylight, no blue-hour light.
  If trees are visible through gaps in the blind, they are dark silhouettes only.
  Street lights or distant building lights may twinkle faintly outside — but the dominant tone is DARKNESS.
  DO NOT show blue sky. DO NOT show daylight outside. The outside is NIGHT.
• INTERIOR: the room is lit by warm ARTIFICIAL LIGHT — floor lamps, table lamps, ceiling lights ON.
  Warm amber/orange glow fills the interior (color temperature ≈ 2700–3000K).
  The room feels cozy, intimate, low-lit.
  Surfaces close to lamps are warmly lit; corners are in soft shadow.
• The window with the blind creates a strong contrast: warm lit interior vs dark exterior.
• Slight interior light reflection on the window glass where blind gaps exist.
"""

    else:
        # Golden hour / Zonsondergang (default)
        return """
═══ LIGHTING: GOLDEN HOUR (ZONSONDERGANG — WARM) ═══
• Time of day: 30–60 minutes before sunset, approximately 6–8 PM (summer).
• EXTERIOR (outside the window): sky shows warm orange-amber-pink gradient near horizon.
  The sun is LOW — just at or below roof level.
  Trees and outdoor elements are lit with warm golden side-light.
  Long dramatic shadows outside.
• INTERIOR: rich warm amber-golden light floods through the window at a LOW angle.
  The light is intensely warm — color temperature ≈ 3000–3500K (orange-gold).
  Long horizontal light shafts enter through the blind slats (when open/partial).
  The shadow lines on the floor and walls are long, warm-tinted, and dramatic.
  Every surface facing the window catches a golden glow.
• The room feels cinematic, premium, atmospheric — golden magic hour.
• The blind slats catch warm highlight on their upper edges — glowing amber.
• This is the most visually beautiful lighting scenario — render it with maximum drama.
"""


# ── MAIN PROMPT BUILDER ─────────────────────────────────────────────────────────

def _build_render_prompt(render_instruction: dict, config_override: dict | None = None) -> str:
    """Build a v4 photorealistic render prompt with dedicated blocks per parameter."""
    ri = render_instruction.copy()
    if config_override:
        ri.update(config_override)

    product   = ri.get("product_type", "Aluminum Venetian Blinds")
    color     = ri.get("color_name", "")
    hex_code  = ri.get("hex_code", "")
    mount     = ri.get("mount_type", "inside mount")
    sections  = ri.get("window_sections", 1)
    lighting  = ri.get("lighting_condition", "Golden hour sunset — warm amber-orange")
    state     = ri.get("state", "Slats fully open at 0°")
    slat      = ri.get("slat_width", "50mm")
    has_tape  = ri.get("ladder_tape", False)
    room_ctx  = ri.get("room_context", "")

    is_wood = "hout" in product.lower() or "wood" in product.lower() or "bamboe" in product.lower()
    slat_mm = int(slat.replace("mm", "").strip()) if "mm" in str(slat) else 50

    # Material block
    material_block = (
        "Each slat shows clear natural wood grain running HORIZONTALLY along the slat length. "
        "Grain has subtle variation — knots, streaks, not uniform. Satin matte finish with very "
        "slight specular sheen at glancing angles. Wood feels tactile and organic."
    ) if is_wood else (
        "Each slat has a smooth uniform powder-coated aluminum finish. Very faint metallic "
        "sheen — a thin specular highlight along the upper edge of each slat when lit. "
        "Surface looks industrial-precise, not glossy or mirror-like."
    )

    mount_desc = (
        "The blind sits INSIDE the window recess — flush with the wall face. "
        "The window frame surrounds the blind on all four sides. "
        "The headrail (top box) is hidden inside the recess."
    ) if "inside" in mount.lower() else (
        "The blind is mounted OUTSIDE the window recess on the wall above the frame. "
        "The blind covers the entire window frame plus some wall on each side. "
        "The headrail (top box) is visible above the window frame."
    )

    # Detect "volledig gesloten" early to inject the critical override preamble
    state_lower = state.lower()
    is_fully_closed = (
        "volledig gesloten" in state_lower
        or "fully closed" in state_lower
        or "nul lichtdoorlaat" in state_lower
        or "90°" in state_lower
        or "solid opaque panel" in state_lower
    )

    # For fully-closed: build an unmissable preamble that repeats the blackout rule
    if is_fully_closed:
        closed_preamble = f"""
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
CRITICAL OVERRIDE — READ THIS FIRST — DO NOT SKIP
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

THE BLIND IN THIS IMAGE MUST BE **VOLLEDIG GESLOTEN** (FULLY CLOSED).

This means:
1. THE WINDOW IS 100% BLOCKED. The blind is a SOLID OPAQUE WALL of color {color} ({hex_code}).
   There are NO gaps, NO holes, NO transparent areas between any slats.
2. ZERO LIGHT ENTERS FROM OUTSIDE. No sunbeams. No light shafts. No bright patches on floor or walls
   caused by light coming through the blind. NONE.
3. THE SKY IS NOT VISIBLE. No blue sky, no clouds, no outdoor scene through the window. NOTHING.
4. The slats are at 90 degrees — vertical — touching each other. They form a SOLID FLAT PANEL.
5. The room is dark. The ONLY light source is interior artificial light (a floor lamp or table lamp).

IF YOUR OUTPUT SHOWS:
  - Any light coming through the blind → WRONG, start over
  - Any gaps or openings between slats → WRONG, start over
  - Blue sky or outdoor scene through the window → WRONG, start over
  - Any sunbeam or shadow pattern from outdoor light → WRONG, start over

THE WINDOW MUST LOOK LIKE A SOLID PAINTED WALL IN THE COLOR {color} ({hex_code}).
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
"""
    else:
        closed_preamble = ""

    prompt = f"""{closed_preamble}You are a professional architectural visualization artist.
Your task: composite photorealistic venetian blinds onto the window in this reference room photograph.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ABSOLUTE RULE #1 — ROOM PRESERVATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Keep the ENTIRE room EXACTLY as shown in the reference photo.
• Walls, floor, ceiling, furniture, objects — UNCHANGED.
• Do NOT repaint walls. Do NOT move furniture. Do NOT add objects.
• Do NOT change the camera angle or perspective.
• ONLY modify the window area by adding the blinds described below.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BLIND IDENTITY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Product: {product}
• Color: {color}
• Exact hex code: {hex_code}
  → Every slat MUST match this exact hex color. Sample the hex, do not approximate.
  → If hex is near-black (e.g. #050505), the slats must appear essentially black.
  → If hex is a pastel (e.g. #F4C2C2), the slats must appear clearly pastel pink.
  → Color accuracy is the #1 visual quality metric.
• Mount: {mount_desc}
• Window sections: {sections} {"panel" if sections == 1 else "panels side by side"}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MATERIAL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{material_block}

{_slat_width_block(slat_mm)}

{_ladder_block(has_tape, color, hex_code)}

{_slat_angle_block(state)}

{_lighting_block(lighting)}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHOTOGRAPHIC QUALITY REQUIREMENTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Output must look like a real photograph taken by a professional interior photographer.
• Camera: full-frame, focal length 24–35mm, f/5.6, ISO 200, neutral white balance.
• Depth of field: blind and window sharp; room background matches original photo focus.
• Perspective: perfectly match the original photo's viewpoint — no camera shift.
• No AI artifacts, no color banding, no blurry slats, no floating elements.
• Each slat must be individually crisp, perfectly parallel, equally spaced.
• The headrail (top box) must be visible and correctly proportioned.
• The bottom rail must sit at the correct height with the pull cord visible.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LICHTDOORLAAT HIËRARCHIE (STRIKT VOLGEN)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
De hoeveelheid licht in de ruimte MOET overeenkomen met de gekozen kantelstand:
  1. Volledig open      → MAXIMALE lichtinval, sterke directe zonnestralen
  2. Licht gekanteld    → RUIME lichtinval, zachte diagonale schaduwlijnen
  3. Half gesloten      → BEPERKTE lichtinval, geen directe zonnestralen
  4. Privacystand       → MINIMALE lichtinval, alleen zwakke omgevingsgloed
  5. Volledig gesloten  → GEEN buitenlicht, GEEN schaduwprojecties, alleen binnenlicht

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT TO AVOID (HARD CONSTRAINTS)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• No cartoon or 3D render style
• No wrong blind color — color MUST match hex {hex_code}
• No mixed slat widths within the same blind
• No missing ladder system (cords or tape must be visible)
• No daylight outside during evening mode
• No artificial light inside during daytime modes  
• No incorrect slat count for the chosen slat width
• No transparent slats when the blind is fully closed (volledig gesloten)
• No light rays, light bands, or sun projections when blind is "volledig gesloten"
• No outdoor sky or outdoor scene visible when blind is "volledig gesloten"
• Do not remove or alter ANY room elements outside the window
• Room context: {room_ctx}
"""
    return prompt



# ── GENERATE RENDER ─────────────────────────────────────────────────────────────

def generate_render(
    image_bytes: bytes,
    render_instruction: dict,
    config_override: dict | None = None,
) -> bytes:
    """
    Generate a photorealistic render using Gemini.

    Args:
        image_bytes: Original room image as bytes
        render_instruction: RenderInstruction dict from Phase 9
        config_override: Optional user config overrides

    Returns:
        PNG image bytes of the rendered result

    Raises:
        RuntimeError if all models fail
    """
    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    prompt = _build_render_prompt(render_instruction, config_override)

    # Encode original image for multimodal input
    img_part = types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")

    # Detect fully-closed state for stricter generation settings
    ri_merged = render_instruction.copy()
    if config_override:
        ri_merged.update(config_override)
    state_str = ri_merged.get("state", "").lower()
    is_fully_closed = (
        "volledig gesloten" in state_str
        or "fully closed" in state_str
        or "nul lichtdoorlaat" in state_str
    )
    # Lower temperature = model follows instructions more literally
    temperature = 0.1 if is_fully_closed else 0.4

    last_error = None

    for model_name in RENDER_MODELS:
        for attempt in range(MAX_RETRIES + 1):
            try:
                # Prompt text FIRST so the override preamble is read before the photo.
                response = client.models.generate_content(
                    model=model_name,
                    contents=[prompt, img_part],
                    config=types.GenerateContentConfig(
                        response_modalities=["Text", "Image"],
                        temperature=temperature,
                    ),
                )
                for part in response.candidates[0].content.parts:
                    if part.inline_data is not None:
                        return part.inline_data.data  # raw PNG bytes
                last_error = RuntimeError(f"Model {model_name} returned no image")
                break

            except Exception as e:
                err_str = str(e)
                last_error = e

                # Fatal error codes — skip to next model immediately
                if any(f"{code}" in err_str for code in FATAL_CODES):
                    break

                # Transient error — retry with backoff
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY * (attempt + 1))
                    continue
                break  # exhausted retries for this model

    raise RuntimeError(f"All Gemini models failed. Last error: {last_error}")

