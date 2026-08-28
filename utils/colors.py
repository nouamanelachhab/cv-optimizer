# -*- coding: utf-8 -*-
"""Recherche automatique du logo d'une societe et extraction des couleurs.

Strategie (gratuite, sans cle API) :
  1. deviner le(s) domaine(s) probable(s) a partir du nom de la societe ;
  2. recuperer le logo via l'API Logo de Clearbit (https://logo.clearbit.com),
     avec repli sur le service de favicon de Google ;
  3. extraire la palette dominante avec Pillow et en deduire une couleur
     primaire (foncee) et une couleur secondaire (accent).

Si l'utilisateur fournit directement une URL de site, on l'utilise en priorite.
"""

import io
import re
import unicodedata

import requests
from PIL import Image

TIMEOUT = 8
HEADERS = {"User-Agent": "Mozilla/5.0 (CV-ATS-Optimizer)"}


def _slug(company):
    s = unicodedata.normalize("NFD", company.lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"\b(group|groupe|sa|sas|sarl|inc|ltd|business|services)\b", "", s)
    s = re.sub(r"[^a-z0-9]", "", s)
    return s


def _domain_from_url(text):
    m = re.search(r"(?:https?://)?(?:www\.)?([a-z0-9.-]+\.[a-z]{2,})", text.lower())
    return m.group(1) if m else None


def candidate_domains(company_or_url):
    """Retourne une liste de domaines candidats a tester."""
    domain = _domain_from_url(company_or_url)
    if domain:
        return [domain]
    slug = _slug(company_or_url)
    if not slug:
        return []
    return [f"{slug}.com", f"{slug}.fr", f"{slug}.io", f"{slug}.net"]


def _download(url):
    try:
        r = requests.get(url, timeout=TIMEOUT, headers=HEADERS)
        if r.status_code == 200 and r.content and len(r.content) > 200:
            return r.content
    except requests.RequestException:
        return None
    return None


def fetch_logo(company_or_url):
    """Telecharge le meilleur logo trouve. Retourne (image_bytes, source_url)."""
    for domain in candidate_domains(company_or_url):
        # 1) Clearbit : logos de marque de bonne qualite.
        content = _download(f"https://logo.clearbit.com/{domain}?size=256")
        if content:
            return content, f"Clearbit ({domain})"
        # 2) Repli : favicon haute resolution via Google.
        content = _download(
            f"https://www.google.com/s2/favicons?domain={domain}&sz=128"
        )
        if content:
            return content, f"Favicon Google ({domain})"
    return None, None


def _is_meaningful(rgb):
    """Ecarte le blanc, le noir et les gris peu satures."""
    r, g, b = rgb
    mx, mn = max(rgb), min(rgb)
    if mx > 235 and mn > 235:      # quasi blanc
        return False
    if mx < 45:                    # quasi noir
        return False
    if mx - mn < 22:               # gris
        return False
    return True


def _luminance(rgb):
    r, g, b = rgb
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _hex(rgb):
    return "{:02X}{:02X}{:02X}".format(*rgb)


def extract_palette(image_bytes, max_colors=10):
    """Retourne une liste de (hex, rgb, count) triee par frequence."""
    im = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
    im = Image.alpha_composite(bg, im).convert("RGB")
    im = im.resize((120, 120))
    quant = im.quantize(colors=16, method=Image.Quantize.FASTOCTREE)
    palette = quant.getpalette()
    counts = sorted(quant.getcolors(), reverse=True)  # (count, index)

    result = []
    for count, idx in counts:
        rgb = tuple(palette[idx * 3: idx * 3 + 3])
        result.append((_hex(rgb), rgb, count))
    return result[:max_colors]


def brand_colors(image_bytes):
    """Deduit (primaire, secondaire) en hex depuis le logo.

    Primaire = couleur de marque la plus dominante et la plus foncee
    (ideale pour les titres). Secondaire = seconde couleur de marque distincte
    (accent). Repli sur un bleu corporate si rien d'exploitable.
    """
    palette = extract_palette(image_bytes)
    meaningful = [(hx, rgb, c) for (hx, rgb, c) in palette if _is_meaningful(rgb)]

    if not meaningful:
        return "25305F", "5487C6", palette

    meaningful.sort(key=lambda x: x[2], reverse=True)
    top = meaningful[:5]

    primary = min(top, key=lambda x: _luminance(x[1]))

    secondary = None
    for hx, rgb, c in top:
        if hx == primary[0]:
            continue
        if abs(_luminance(rgb) - _luminance(primary[1])) > 30:
            secondary = (hx, rgb, c)
            break
    if secondary is None:
        secondary = max(top, key=lambda x: _luminance(x[1]))
        if secondary[0] == primary[0]:
            secondary = (primary[0], primary[1], primary[2])

    return primary[0], secondary[0], palette


# --------------------------------------------------------------------------- #
# Construction d'une palette coherente (harmonies de designer)
# --------------------------------------------------------------------------- #
# Palettes professionnelles concues par des graphistes (primaire + accent).
# Elles servent de reference d'harmonie : on repere celle dont la teinte
# primaire est la plus proche du logo, puis on applique le meme ecart de teinte
# accent/primaire au logo pour rester coherent tout en collant a la marque.
DESIGNER_PALETTES = [
    {"name": "Navy & Gold", "primary": "1B2A4A", "accent": "C9A227"},
    {"name": "Royal Blue & Sky", "primary": "25305F", "accent": "5487C6"},
    {"name": "Teal & Coral", "primary": "12664F", "accent": "E76F51"},
    {"name": "Charcoal & Teal", "primary": "22333B", "accent": "5E8B7E"},
    {"name": "Burgundy & Slate", "primary": "6E2338", "accent": "8896AB"},
    {"name": "Forest & Amber", "primary": "2C5F2D", "accent": "D9A404"},
    {"name": "Slate & Sky", "primary": "2F4858", "accent": "3A86FF"},
    {"name": "Plum & Rose", "primary": "4A2545", "accent": "C96480"},
    {"name": "Petrol & Orange", "primary": "003844", "accent": "F08700"},
    {"name": "Indigo & Cyan", "primary": "312E81", "accent": "06B6D4"},
    {"name": "Graphite & Emerald", "primary": "1F2937", "accent": "10B981"},
    {"name": "Wine & Sand", "primary": "5B2333", "accent": "C69F89"},
]


def _hex_to_rgb(hx):
    hx = hx.lstrip("#")
    return tuple(int(hx[i:i + 2], 16) for i in (0, 2, 4))


def _rgb_to_hex(rgb):
    r, g, b = (max(0, min(255, int(round(v)))) for v in rgb)
    return "{:02X}{:02X}{:02X}".format(r, g, b)


def _rgb_to_hsl(rgb):
    r, g, b = (v / 255.0 for v in rgb)
    mx, mn = max(r, g, b), min(r, g, b)
    l = (mx + mn) / 2
    if mx == mn:
        return 0.0, 0.0, l
    d = mx - mn
    s = d / (2 - mx - mn) if l > 0.5 else d / (mx + mn)
    if mx == r:
        h = (g - b) / d + (6 if g < b else 0)
    elif mx == g:
        h = (b - r) / d + 2
    else:
        h = (r - g) / d + 4
    return (h / 6) * 360, s, l


def _hsl_to_rgb(h, s, l):
    h = (h % 360) / 360.0
    if s == 0:
        v = l * 255
        return (v, v, v)

    def hue2rgb(p, q, t):
        if t < 0:
            t += 1
        if t > 1:
            t -= 1
        if t < 1 / 6:
            return p + (q - p) * 6 * t
        if t < 1 / 2:
            return q
        if t < 2 / 3:
            return p + (q - p) * (2 / 3 - t) * 6
        return p

    q = l * (1 + s) if l < 0.5 else l + s - l * s
    p = 2 * l - q
    r = hue2rgb(p, q, h + 1 / 3)
    g = hue2rgb(p, q, h)
    b = hue2rgb(p, q, h - 1 / 3)
    return (r * 255, g * 255, b * 255)


def _rel_luminance(rgb):
    def chan(c):
        c = c / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (chan(v) for v in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(hex1, hex2):
    """Ratio de contraste WCAG entre deux couleurs (1 a 21)."""
    l1 = _rel_luminance(_hex_to_rgb(hex1))
    l2 = _rel_luminance(_hex_to_rgb(hex2))
    hi, lo = max(l1, l2), min(l1, l2)
    return round((hi + 0.05) / (lo + 0.05), 2)


def _ensure_contrast_on_white(hx, min_ratio=4.5):
    """Assombrit la couleur jusqu'a atteindre le contraste vise sur blanc."""
    h, s, l = _rgb_to_hsl(_hex_to_rgb(hx))
    for _ in range(40):
        if contrast_ratio(hx, "FFFFFF") >= min_ratio:
            return hx
        l = max(0.0, l - 0.03)
        hx = _rgb_to_hex(_hsl_to_rgb(h, s, l))
    return hx


def _hue_distance(h1, h2):
    d = abs(h1 - h2) % 360
    return min(d, 360 - d)


def nearest_designer_palette(primary_hex):
    """Retourne la palette de designer dont la teinte primaire est la plus proche."""
    ph, _ps, _pl = _rgb_to_hsl(_hex_to_rgb(primary_hex))
    best, best_d = None, 1e9
    for pal in DESIGNER_PALETTES:
        dh, _s, _l = _rgb_to_hsl(_hex_to_rgb(pal["primary"]))
        d = _hue_distance(ph, dh)
        if d < best_d:
            best, best_d = pal, d
    return best


def build_palette(primary_hex, secondary_hex=None):
    """Construit une palette complete, coherente et contrastee.

    Part de la couleur primaire du logo, s'appuie sur l'harmonie d'une palette
    de designer proche, et garantit un bon contraste (WCAG). Retourne un dict :
      - heading   : couleur des titres (foncee, lisible sur blanc)
      - accent    : couleur d'accent (dates, puces) vive et distincte
      - text      : couleur du corps de texte
      - muted     : gris de support
      - tint      : fond tres clair derive de la marque
      - name      : nom de l'harmonie de reference
      - contrast  : ratios de controle
    """
    primary_hex = primary_hex.lstrip("#").upper()
    ph, ps, pl = _rgb_to_hsl(_hex_to_rgb(primary_hex))

    # Teinte primaire -> titre : foncee et suffisamment saturee, lisible.
    heading_s = min(0.85, max(0.30, ps))
    heading_l = min(pl, 0.30)
    heading = _rgb_to_hex(_hsl_to_rgb(ph, heading_s, heading_l))
    heading = _ensure_contrast_on_white(heading, 6.0)

    ref = nearest_designer_palette(primary_hex)
    rp_h, _rp_s, _rp_l = _rgb_to_hsl(_hex_to_rgb(ref["primary"]))
    ra_h, ra_s, ra_l = _rgb_to_hsl(_hex_to_rgb(ref["accent"]))
    hue_offset = (ra_h - rp_h)  # ecart accent/primaire choisi par le designer

    # Accent : couleur du logo si distincte et harmonieuse, sinon derivee.
    accent = None
    if secondary_hex:
        sh, ss, sl = _rgb_to_hsl(_hex_to_rgb(secondary_hex.lstrip("#")))
        if _hue_distance(sh, ph) > 20 and ss > 0.18:
            accent = _rgb_to_hex(_hsl_to_rgb(sh, min(0.90, max(0.45, ss)),
                                             min(0.60, max(0.40, sl))))
    if accent is None:
        accent_h = ph + hue_offset
        accent = _rgb_to_hex(_hsl_to_rgb(accent_h, min(0.90, max(0.45, ra_s)),
                                         min(0.62, max(0.42, ra_l))))
    accent = _ensure_contrast_on_white(accent, 3.0)

    # Corps de texte : quasi noir legerement teinte de la marque.
    text = _rgb_to_hex(_hsl_to_rgb(ph, 0.15, 0.12))
    # Gris de support.
    muted = _rgb_to_hex(_hsl_to_rgb(ph, 0.10, 0.45))
    # Fond tres clair (bandeaux, encadres).
    tint = _rgb_to_hex(_hsl_to_rgb(ph, min(0.35, ps), 0.96))

    return {
        "heading": heading,
        "accent": accent,
        "text": text,
        "muted": muted,
        "tint": tint,
        "name": ref["name"],
        "contrast": {
            "heading_on_white": contrast_ratio(heading, "FFFFFF"),
            "accent_on_white": contrast_ratio(accent, "FFFFFF"),
            "heading_vs_accent": contrast_ratio(heading, accent),
        },
    }
