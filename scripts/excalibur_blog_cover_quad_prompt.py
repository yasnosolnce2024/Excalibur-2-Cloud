#!/usr/bin/env python3
"""Build MCP prompt + batch for ONE quad canvas (4 panels) with hero i2i reference."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

from excalibur_blog_site_base import (
    REDACTED_LITERAL,
    SITE_BASE_PLACEHOLDER,
    SITE_HOST_PLACEHOLDER,
    expand_site_base,
    host_from_public_base,
    redact_site_base,
    resolve_public_base_from_env,
    to_git_safe_site_url,
)


# Stale Cover agents leave «pink «время»» in scene_hint after changing highlight —
# the model follows the leftover and repaints hollow TIME (B73 / INC-20260722-1525).
_PINK_WORD_IN_SCENE = re.compile(
    r"(pink\s*(?:ONLY\s*)?[«\"']\s*)([^»\"']+?)(\s*[»\"'])",
    re.IGNORECASE,
)


def sanitize_cover_scene_hint(scene: str, highlight: str) -> str:
    """Rewrite conflicting pink-word directives in scene_hint to match highlight."""
    hl = (highlight or "").strip()
    if not hl or not (scene or "").strip():
        return scene or ""

    def _repl(match: re.Match[str]) -> str:
        word = match.group(2).strip()
        if word.casefold() == hl.casefold():
            return match.group(0)
        return f"{match.group(1)}{hl}{match.group(3)}"

    return _PINK_WORD_IN_SCENE.sub(_repl, scene)


MAX_MCP_PROMPT_CHARS = 3500
# Compact limits leave headroom under 3500 after style boilerplate (INC-20260721-0837).
# Cover raw ≈80–140 (from blog-hero lock); inline ≈100–220. Long MUST/face essays
# starve host space (B80 / INC-20260724-0837) and bilingual essays blow MCP budget.
# After EXCALIBUR-stamp ban (INC-20260723-1223) shared locks ate most of the budget
# (B79 / INC-20260723-1626): keep one shared «Inline all» suffix (not ×3) and reclaim
# from shared negatives first — never force agents to empty scene_hint.
COVER_SCENE_HINT_COMPACT = 200
INLINE_SCENE_HINT_COMPACT = 180
COVER_SCENE_HINT_RAW_TARGET_MAX = 140
INLINE_SCENE_HINT_RAW_TARGET_MAX = 220
# Backward-compatible alias (inline / general budget messaging).
SCENE_HINT_RAW_TARGET_MAX = INLINE_SCENE_HINT_RAW_TARGET_MAX
# Minimum empty-base headroom so ≈100-char scene_hint ×4 still fits under 3500.
MIN_EMPTY_PROMPT_HEADROOM = 500
_COVER_FACE_ESSAY = re.compile(
    r"\bMUST\b|\bglasses\b|\bquiff\b|\bbeard\b|\bfacial\b",
    re.IGNORECASE,
)
# Live host for runtime URL checks only — never write this into git batch JSON.
# Prefer PUBLIC_SITE_URL hostname; fallback for offline validate when env empty.
_LEGACY_REFERENCE_HOST_FALLBACK = ""  # no personal default host
MCP_RESOLUTION = "2K"
KIE_IMAGE_MODEL = "gpt-image-2-image-to-image"


def required_reference_host_runtime() -> str:
    """Hostname accepted in live reference URLs (env or legacy fallback)."""
    return host_from_public_base() or _LEGACY_REFERENCE_HOST_FALLBACK


def project_root() -> Path:
    env_root = os.environ.get("EXCALIBUR_PROJECT_ROOT", "").strip()
    if env_root:
        return Path(env_root)
    return Path(__file__).resolve().parents[1]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def compact(value: object, limit: int) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def inline_panel_prompt(slot: dict, types_catalog: dict) -> str:
    type_id = slot.get("visual_type") or "infographic_card"
    type_def = (types_catalog.get("types") or {}).get(type_id) or {}
    label = type_def.get("label_ru", type_id)
    h2 = compact(slot.get("h2_anchor", ""), 95)
    scene = compact(slot.get("scene_hint", ""), INLINE_SCENE_HINT_COMPACT)
    base = f"{label}; H2: «{h2}»; scene: {scene}; no host face."
    labels = [str(x).strip() for x in (slot.get("labels") or []) if str(x).strip()]
    if labels:
        exact = ", ".join(f"«{x}»" for x in labels)
        base += (
            f" TEXT LOCK: render ONLY these exact Russian strings on this panel: "
            f"{exact}. Every letter in Cyrillic, exactly as written. "
            "No other words, no English, no invented headlines."
        )
    return base


def warn_long_scene_hints(manifest: dict) -> None:
    """Advisory: long raw scene_hint blows MCP budget; cover face essays omit host."""
    slots = manifest.get("slots") or {}
    for key in ("cover", "inline_1", "inline_2", "inline_3"):
        raw = " ".join(str((slots.get(key) or {}).get("scene_hint") or "").split())
        if not raw:
            continue
        if key == "cover":
            if len(raw) > COVER_SCENE_HINT_RAW_TARGET_MAX:
                print(
                    f"WARN cover.scene_hint is {len(raw)} chars "
                    f"(target ≈80–{COVER_SCENE_HINT_RAW_TARGET_MAX}; "
                    "prefer short hero lock from blog-hero — long hints omit host). "
                    "Shorten before --write-batch.",
                    file=sys.stderr,
                )
            elif _COVER_FACE_ESSAY.search(raw) and len(raw) > 100:
                print(
                    "WARN cover.scene_hint looks like a MUST/face-feature essay "
                    "(tenant visual_lock). Prefer short hero lock from blog-hero + "
                    "one object; face lock is already in i2i reference "
                    "(INC-20260724-0837).",
                    file=sys.stderr,
                )
            continue
        if len(raw) > INLINE_SCENE_HINT_RAW_TARGET_MAX:
            print(
                f"WARN {key}.scene_hint is {len(raw)} chars "
                f"(target ≤{INLINE_SCENE_HINT_RAW_TARGET_MAX}; "
                "bilingual essays blow MCP budget). "
                "Shorten to compact RU/EN labels before --write-batch.",
                file=sys.stderr,
            )


def _topic_blob(manifest: dict, article_dir: Path | None = None) -> str:
    parts = [
        str(manifest.get("topic_id") or ""),
        str(manifest.get("cover_hook") or ""),
        " ".join(str(x) for x in (manifest.get("cover_keys_ru") or [])),
    ]
    slots = manifest.get("slots") or {}
    for key in ("cover", "inline_1", "inline_2", "inline_3"):
        slot = slots.get(key) or {}
        parts.append(str(slot.get("h2_anchor") or ""))
        parts.append(str(slot.get("scene_hint") or ""))
        parts.append(str(slot.get("alt") or ""))
    if article_dir is not None:
        parts.append(article_dir.name)
    return " ".join(parts).lower()


def is_cursor_sdk_local_agent_topic(manifest: dict, article_dir: Path | None = None) -> bool:
    """Detect Cursor SDK / «локальный ai агент» covers (B72 fact lock)."""
    blob = _topic_blob(manifest, article_dir)
    has_sdk = any(
        marker in blob
        for marker in (
            "cursor sdk",
            "cursor-sdk",
            "@cursor/sdk",
            "agent.create",
            "composer-2",
        )
    )
    has_local = any(
        marker in blob
        for marker in ("локальн", "lokalnyy", "localnyy", "local agent", "local ai")
    )
    has_agent = any(
        marker in blob for marker in ("ai агент", "ai-agent", "ai agent", "агент")
    )
    return has_sdk or (has_local and has_agent)


def topic_fact_lock_lines(
    manifest: dict, article_dir: Path | None = None
) -> list[str]:
    """Short prompt lines that lock topic facts the model often invents wrong."""
    lines: list[str] = []
    if is_cursor_sdk_local_agent_topic(manifest, article_dir):
        # Keep short: full bilingual essays blow MCP 3500 (INC-20260721-0837).
        lines.append(
            "FACT LOCK SDK/local: local=files on disk not offline; "
            "Chat YES/Ollama NO/SDK YES net; never «интернет не нужен» on Chat/SDK; "
            "one hook — no «Ключевые темы»/keys list."
        )
    return lines


def validate_reference_url(ref_url: str) -> bool:
    """Accept live site host URL, {{SITE_BASE}}/… path, or reject [REDACTED]/tool masks."""
    value = (ref_url or "").strip()
    host = required_reference_host_runtime()
    if not value:
        return False
    if REDACTED_LITERAL in value:
        print(
            "❌ COVER HERO BLOCKER: reference_url_hosted contains [REDACTED]; "
            f"use {SITE_BASE_PLACEHOLDER}/wp-content/... or a live {host} URL",
            file=sys.stderr,
        )
        return False
    if value.startswith(SITE_BASE_PLACEHOLDER):
        path = value[len(SITE_BASE_PLACEHOLDER) :]
        if "/wp-content/" in path or path.startswith("/wp-content/"):
            return True
        print(
            f"❌ COVER HERO BLOCKER: {SITE_BASE_PLACEHOLDER} reference must point at /wp-content/... media",
            file=sys.stderr,
        )
        return False
    if host and host in value:
        return True
    # Also accept legacy fallback host if env host differs (offline / mixed artifacts).
    if _LEGACY_REFERENCE_HOST_FALLBACK in value and _LEGACY_REFERENCE_HOST_FALLBACK != host:
        return True
    print(
        f"❌ COVER HERO BLOCKER: reference_url_hosted must use stable {host} "
        f"WordPress media URL or {SITE_BASE_PLACEHOLDER}/wp-content/..., got: {value}",
        file=sys.stderr,
    )
    return False


def git_safe_reference_url(ref_url: str) -> str:
    """Write {{SITE_BASE}}/path into committed batch; keep non-site hosts as-is."""
    value = (ref_url or "").strip()
    if not value:
        return value
    if value.startswith(SITE_BASE_PLACEHOLDER):
        return value
    safe = to_git_safe_site_url(value)
    if safe.startswith(SITE_BASE_PLACEHOLDER):
        return safe
    host = required_reference_host_runtime()
    if host and host in value and "://" in value:
        path = urlparse(value).path or "/"
        return f"{SITE_BASE_PLACEHOLDER}{path}"
    if _LEGACY_REFERENCE_HOST_FALLBACK in value and "://" in value:
        path = urlparse(value).path or "/"
        return f"{SITE_BASE_PLACEHOLDER}{path}"
    return redact_site_base(value)


def validate_prompt_budget(prompt: str) -> bool:
    prompt_chars = len(prompt)
    if prompt_chars <= MAX_MCP_PROMPT_CHARS:
        return True
    print(
        f"❌ COVER PROMPT BLOCKER: MCP prompt is {prompt_chars} chars, max {MAX_MCP_PROMPT_CHARS}. "
        "Shorten cover scene_hint to ≈80–140 (blog-hero lock, no MUST/face essay) "
        "and each inline to ≈100–220 (compact RU/EN labels, not bilingual essays); "
        "do not duplicate style/negative blocks per panel (one shared «Inline all» lock). "
        "If hints are already short and budget still fails, reclaim chars from shared "
        "style/ban/Inline-all text in this script — do not empty scene_hint. "
        f"Script compact caps: cover≤{COVER_SCENE_HINT_COMPACT}, inline≤{INLINE_SCENE_HINT_COMPACT}.",
        file=sys.stderr,
    )
    return False


def style_allows_cat_stickers(style: dict) -> bool:
    """True when style preset explicitly allows funny cat sticker cutouts."""
    if style.get("allows_animal_stickers") is True:
        return True
    motif = str(style.get("allowed_animal_motif") or "").strip().casefold()
    return "cat" in motif


def style_is_situational_cat_hero(style: dict) -> bool:
    """Cat is the cover hero (not host+sticker cats)."""
    mode = str(style.get("cover_hero_mode") or "").strip().casefold()
    if mode in {"situational_cat", "cat_hero", "situational_cat_hero"}:
        return True
    if style.get("skip_human_host") is True and style_allows_cat_stickers(style):
        return True
    motif = str(style.get("allowed_animal_motif") or "").strip().casefold()
    return motif in {"situational_cat_hero", "cat_hero"}


def style_is_illustrative_no_host(style: dict, hero: dict | None = None) -> bool:
    """Kitchen/scene cover without a human host (tenant cover_mode=illustrative)."""
    mode = str(style.get("cover_hero_mode") or "").strip().casefold()
    if mode in {"illustrative_scene", "illustrative"}:
        return True
    cover_mode = str(
        (hero or {}).get("cover_mode") or style.get("cover_mode") or ""
    ).strip().casefold()
    if cover_mode == "illustrative":
        return True
    return bool(style.get("skip_human_host") is True and not style_allows_cat_stickers(style))


def build_prompt(
    manifest: dict,
    style: dict,
    hero: dict,
    types_catalog: dict,
    design_code: dict,
    article_dir: Path | None = None,
) -> str:
    slots = manifest.get("slots") or {}

    def slot(key: str) -> dict:
        return slots.get(key) or {}

    cover = slot("cover")
    i1, i2, i3 = slot("inline_1"), slot("inline_2"), slot("inline_3")
    fact_locks = topic_fact_lock_lines(manifest, article_dir)
    cat_ok = style_allows_cat_stickers(style)
    cat_hero = style_is_situational_cat_hero(style)
    illustrative = style_is_illustrative_no_host(style, hero)

    highlight = compact(manifest.get("cover_hook_highlight", ""), 24)
    accent = (
        str(style.get("accent") or "").strip()
        or str((design_code.get("color_palette") or {}).get("accent_primary") or "").strip()
        or "#C45C26"
    )
    highlight_rule = (
        f'paint ONLY the highlight word "{highlight}" in accent {accent}; '
        f'hook text must match exactly — do not substitute «время»/traffic markers'
        if highlight
        else f"paint at most ONE punch word in accent {accent}"
    )
    cover_scene = sanitize_cover_scene_hint(
        str(cover.get("scene_hint") or ""), highlight
    )
    cover_hook_text = compact(manifest.get("cover_hook", ""), 120)
    cover_sticky = compact(str(cover.get("sticky") or ""), 48)
    sticky_name = "terracotta" if illustrative else "pink"
    sticky_lock = (
        f" Small {sticky_name} sticky with EXACTLY «{cover_sticky}» in Cyrillic."
        if cover_sticky
        else ""
    )
    # Prefer style preset locks when present (cat digital collage vs editorial).
    style_prefix = compact(
        style.get("global_prompt_prefix")
        or design_code.get("cover_panel_prompt_block")
        or "",
        520,
    )
    if not style_prefix:
        style_prefix = (
            "Warm kitchen editorial, WHITE #FFFFFF, ink #2A2118 Cyrillic, "
            "terracotta #C45C26 one accent only. Cover: table/food/window-light, "
            "no host face. Inline: paper cards, tape, 3–6 RU labels. Not sterile."
        )
    if cat_hero:
        ban_line = (
            "Ban: ANY human face/host/bearded man/glasses portrait/white-hoodie person/"
            "Drake/facepalm/stock watermarks/keyword spam/«Ключевые темы»/"
            "Latin lookalike Cyrillic/pipeline stamps/EXCALIBUR badge. "
            "Cover hero MUST be ONE LARGE situational funny cat "
            "(anthropomorphic everyday scene unique to this article)."
        )
        cover_scene_tail = (
            "LARGE situational cat is the ONLY living hero; invent unique scene; "
            "pink banners/tape; NO human; no tiny corner-only stickers as hero."
        )
        reference_line = (
            "STYLE LOCK only (colors/collage language from reference plate). "
            "Do NOT copy any human face from reference. Cover subject = cat."
        )
        inline_suffix = (
            "Inline all: dense collage — BLACK heading, UI card, ≥2 stickers+tape/sticky; "
            "NO people/faces/host/Drake/EXCALIBUR badge; no cover-hook duplicate; "
            "cats optional tiny accent only. Neg: sterile white, human faces, watermark, 9:16."
        )
    elif cat_ok:
        ban_line = (
            "Ban: Drake/facepalm/human reaction cutouts/joke speech bubbles/"
            "stock watermarks/keyword spam/«Ключевые темы»/Latin lookalike Cyrillic/"
            "pipeline stamps/EXCALIBUR badge or sword. ALLOW funny cat sticker-cutouts "
            "with thick white outline (redraw; do not paste stock photos)."
        )
        cover_scene_tail = (
            "host+face LARGE left; 1–2 funny cat stickers (white outline) "
            "tiny/medium right; pink banners/tape; no sterile/Drake/canned EN filler."
        )
        reference_line = (
            "REFERENCE FACE only top-left when cover_mode=host_reference: use blog-hero visual_lock; "
            "expressive editorial pose; no headphones; no human meme reaction."
        )
        inline_suffix = (
            "Inline all: dense collage — BLACK heading, UI card, ≥2 stickers+tape/sticky; "
            "optional ONE tiny cat sticker; NO people/faces/host/Drake/EXCALIBUR badge; "
            "no cover-hook duplicate. Neg: sterile white, all-pink headline, keyword spam, "
            "watermark, logo, 9:16, unreadable text, extra faces."
        )
    elif illustrative:
        ban_line = (
            "Ban: ANY identifiable human face/host portrait/Elena likeness/white-hoodie person/"
            "anti-age before-after/stock happy pensioner/pink-cat collage/hot-pink #FF1493 brand/"
            "Drake/facepalm/stock watermarks/keyword spam/«Ключевые темы»/"
            "Latin lookalike Cyrillic/pipeline stamps/EXCALIBUR badge."
        )
        cover_scene_tail = (
            "NO host face; kitchen table/food/window-light scene; optional unidentifiable hands; "
            "terracotta/sage tape; dignity; no anti-age shame."
        )
        reference_line = (
            "NO reference face. cover_mode=illustrative: scene only from blog-hero prompt_fragment. "
            "Do not invent a portrait. Style from kitchen-warmth design-code."
        )
        inline_suffix = (
            "Inline all: paper-card infographic — warm ink heading, 3–6 RU labels, sage/terracotta tape; "
            "NO people/faces/host/cats/memes/EXCALIBUR badge; no cover-hook duplicate. "
            "Neg: sterile white, all-pink headline, anti-age shame, watermark, logo, 9:16."
        )
    else:
        ban_line = (
            "Ban: memes/reaction emoji/facepalm/animals/joke captions/silhouettes/"
            "keyword spam/«Ключевые темы»/Latin lookalike Cyrillic/pipeline stamps/"
            "EXCALIBUR badge or sword."
        )
        cover_scene_tail = (
            "host+face; dense collage + topic object; no sterile/meme/canned EN chat filler."
        )
        reference_line = (
            "REFERENCE FACE only top-left when cover_mode=host_reference: use blog-hero visual_lock; "
            "expressive editorial pose; no headphones; no meme reaction."
        )
        inline_suffix = (
            "Inline all: dense collage — BLACK heading, UI card, ≥2 stickers+tape/sticky; "
            "NO people/faces/host/meme/EXCALIBUR badge; no cover-hook duplicate. "
            "Neg: sterile white, all-pink headline, keyword spam, watermark, logo, 9:16, "
            "unreadable text, extra faces."
        )
    lines = [
        # NEVER open with "Excalibur BLOG" — models stamp that phrase as a logo
        # badge on every panel (INC-20260723-1223 / user correction).
        style_prefix,
        "Canvas 2048x1152 exact 2x2; four 16:9 panels (1024x576); thin white gutters; no bleed.",
        "",
        ban_line,
        "TEXT LANGUAGE LOCK: all visible text is RUSSIAN Cyrillic only. Renderable strings are given per panel in TEXT LOCK lines — render them exactly. No English headline, no Latin slogan, no pseudo-Cyrillic squiggles, no invented words.",
        "",
        reference_line,
        "",
        f'Top-left COVER TEXT LOCK: the ONLY large headline is EXACTLY this Russian sentence: «{cover_hook_text}» — big bold condensed Cyrillic, black #141821, '
        f'{highlight_rule}; any other large/headline text (especially English like "TOKEN BURN RATE") is FORBIDDEN.{sticky_lock} '
        "no keyword list card; "
        f"scene: {compact(cover_scene, COVER_SCENE_HINT_COMPACT)}; {cover_scene_tail}",
        "",
        f"Top-right inline: {inline_panel_prompt(i1, types_catalog)}",
        f"Bottom-left inline: {inline_panel_prompt(i2, types_catalog)}",
        f"Bottom-right inline: {inline_panel_prompt(i3, types_catalog)}",
        "",
        inline_suffix,
    ]
    if fact_locks:
        lines.extend(["", *fact_locks])
    return "\n".join(line for line in lines if line)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--article-dir", required=True)
    ap.add_argument("--manifest", default="cover/quad-manifest.json")
    ap.add_argument("--write-batch", action="store_true", help="Write cover/quad-mcp-batch.json")
    args = ap.parse_args()

    root = project_root()
    article_dir = Path(args.article_dir)
    if not article_dir.is_absolute():
        article_dir = root / article_dir

    manifest_path = Path(args.manifest)
    if not manifest_path.is_absolute():
        manifest_path = article_dir / manifest_path
    if not manifest_path.is_file():
        print(f"❌ PROMPT BLOCKER: {manifest_path} not found", file=sys.stderr)
        return 1

    manifest = load_json(manifest_path)
    hero = load_json(root / manifest.get("blog_hero", "memory/cover/blog-hero.json"))
    style = load_json(
        root
        / manifest.get(
            "style_file",
            "memory/cover/quad-style-kitchen-warmth-ru.json",
        )
    )
    types_path = root / manifest.get("inline_types_catalog", "memory/cover/inline-visual-types.json")
    types_catalog = load_json(types_path) if types_path.is_file() else {"types": {}}
    design_code_path = root / style.get("design_code", "memory/cover/cover-design-code.json")
    design_code = load_json(design_code_path) if design_code_path.is_file() else {}

    cat_hero = style_is_situational_cat_hero(style)
    illustrative = style_is_illustrative_no_host(style, hero)
    local_reference = str(style.get("local_reference") or "").strip()
    prefer_local_reference = False
    plate_gap = False
    batch_ref_url = ""
    if cat_hero and local_reference:
        local_path = root / local_reference
        if not local_path.is_file():
            print(
                f"❌ COVER STYLE BLOCKER: local_reference missing: {local_reference}",
                file=sys.stderr,
            )
            return 1
        # Git-safe placeholder; Kie uploads local_reference before createTask.
        batch_ref_url = (
            f"{SITE_BASE_PLACEHOLDER}/wp-content/uploads/excalibur/"
            f"{Path(local_reference).name}"
        )
        prefer_local_reference = True
    elif illustrative:
        if local_reference:
            local_path = root / local_reference
            if not local_path.is_file():
                print(
                    f"❌ COVER STYLE BLOCKER: local_reference missing: {local_reference}",
                    file=sys.stderr,
                )
                return 1
            batch_ref_url = (
                f"{SITE_BASE_PLACEHOLDER}/wp-content/uploads/excalibur/"
                f"{Path(local_reference).name}"
            )
            prefer_local_reference = True
        else:
            plate_gap = True
            print(
                "WARN COVER PLATE GAP: illustrative scene, no local_reference PNG "
                "and no reference_url_hosted. Prompt may be written; --write-batch / Kie i2i "
                "blocked until tenant moodboard. Do not invent a face or foreign CDN.",
                file=sys.stderr,
            )
    else:
        ref_url = (hero.get("reference_url_hosted") or "").strip()
        if not ref_url:
            print(
                "❌ COVER HERO BLOCKER: reference_url_hosted missing. Run excalibur_blog_hero_reference_url.py",
                file=sys.stderr,
            )
            return 1
        if not validate_reference_url(ref_url):
            return 1
        # Committed batch always uses {{SITE_BASE}}; Kie API expands at runtime.
        batch_ref_url = git_safe_reference_url(ref_url)
        if REDACTED_LITERAL in batch_ref_url:
            print(
                "❌ COVER HERO BLOCKER: cannot derive git-safe reference_url_hosted; "
                f"set blog-hero.json to {SITE_BASE_PLACEHOLDER}/wp-content/.../ava.jpg",
                file=sys.stderr,
            )
            return 1

    warn_long_scene_hints(manifest)
    prompt = build_prompt(
        manifest, style, hero, types_catalog, design_code, article_dir=article_dir
    )
    if not validate_prompt_budget(prompt):
        return 1
    prompt_path = article_dir / "cover" / "quad-mcp-prompt.txt"
    prompt_path.write_text(prompt + "\n", encoding="utf-8")
    print(f"OK prompt={prompt_path} chars={len(prompt)} max={MAX_MCP_PROMPT_CHARS}")

    if args.write_batch:
        if plate_gap or not str(batch_ref_url or "").strip():
            print(
                "❌ COVER PLATE GAP: --write-batch / Kie i2i requires a tenant style plate "
                "(local_reference PNG) or reference_url_hosted. cover_mode=illustrative — "
                "do not invent a face or fetch a foreign CDN. Wait for moodboard.",
                file=sys.stderr,
            )
            return 1
        # Cover copy is agent-owned. This script transports the completed
        # manifest to Kie; it must not evaluate wording or suggest alternatives.
        cover_slot = (manifest.get("slots") or {}).get("cover") or {}
        hook = str(manifest.get("cover_hook") or "").strip()
        highlight = str(manifest.get("cover_hook_highlight") or "").strip()
        required_errors: list[str] = []
        if not hook:
            required_errors.append("cover_hook empty — Cover agent must write it")
        if not highlight:
            required_errors.append(
                "cover_hook_highlight empty — Cover agent must choose it"
            )
        for key in ("cover", "inline_1", "inline_2", "inline_3"):
            slot = (manifest.get("slots") or {}).get(key) or {}
            if not str(slot.get("scene_hint") or "").strip():
                required_errors.append(
                    f"{key}.scene_hint empty — Cover agent must invent it "
                    "(no script templates; situational cat hero invents unique scene)"
                )
            if not str(slot.get("alt") or "").strip():
                required_errors.append(f"{key}.alt empty — Cover agent must invent alt")
        if required_errors:
            print(
                "❌ COVER MANIFEST BLOCKER: agent-owned fields are missing; "
                "complete quad-manifest.json before image API.",
                file=sys.stderr,
            )
            for err in required_errors:
                print(f"  - {err}", file=sys.stderr)
            return 1
        api_input = {
            "prompt": prompt,
            "input_urls": [batch_ref_url],
            "aspect_ratio": "16:9",
            "resolution": MCP_RESOLUTION,
        }
        batch = {
            "pipeline": "quad_canvas_1x_image_api",
            "reference_url_hosted": batch_ref_url,
            "cover_hero_mode": style.get("cover_hero_mode") or "host",
            "prefer_local_reference": prefer_local_reference,
            "local_reference": local_reference if prefer_local_reference else "",
            "output_canvas": "cover/canvas-quad.png",
            "expected_runtime_seconds": 900,
            "preferred_image_flow": {
                "provider": "kie.ai",
                "model": KIE_IMAGE_MODEL,
                "script": "python scripts/excalibur_blog_kie_gpt_image2_api.py --article-dir <article_dir>",
                "api_key_env": "KIE_API_KEY",
                "result_path": "cover/quad-mcp-result.json",
                "apply_script": "python scripts/excalibur_blog_quad_apply.py --article-dir <article_dir> --inject-html",
                "note": "PRIMARY Cloud path when KIE_API_KEY is set. Do NOT call sync MCP gpt-image-2 first — it often times out (-32001) on 2K i2i. createTask -> recordInfo polls in shell.",
            },
            "timeout_policy": {
                "tool": "gpt-image-2",
                "timeout_error": "HTTP MCP tool execution failed: MCP error -32001: Request timed out",
                "not_final_blocker": True,
                "sync_create_max_attempts": 1,
                "backend_max_wait_seconds": 900,
                "recommended_async_poll_interval_seconds": 10,
                "recommended_async_max_wait_seconds": 900,
                "backend_note": "If KIE_API_KEY is set, skip MCP entirely and use preferred_image_flow. Sync MCP -32001 is client timeout; do not blind-retry create.",
                "preferred_async_flow": {
                    "primary": "python scripts/excalibur_blog_kie_gpt_image2_api.py --article-dir <article_dir> when KIE_API_KEY is set.",
                    "create": "Legacy MCP only if KIE_API_KEY missing: use async image create/start MCP tool if present. Call once with jobs[0].mcp_args and record task_id.",
                    "status": "Poll status/result MCP tool by task_id every 10-15 seconds until url is ready, up to backend_max_wait_seconds.",
                    "idempotency": "Do not create a second image job unless status/result confirms the previous job was not created or failed.",
                },
                "blocker_only_if": "KIE_API_KEY missing AND sync gpt-image-2 times out with -32001 and no generated URL, task_id, or async status/result MCP tool is available.",
                "mcp_invocation": "Legacy fallback ONLY when KIE_API_KEY is missing. If KIE_API_KEY is set, call scripts/excalibur_blog_kie_gpt_image2_api.py and do not invoke MCP gpt-image-2.",
                "log_recovery": "If the MCP/Cloud log or expanded MCP tool response already contains a generated image URL after the HTTP timeout, treat it as success: save that URL to cover/quad-mcp-result.json yourself or pass it directly to quad_apply. Do not search cover/* for the URL; it will not exist there until you save it. Do not start another image job while a generated URL exists.",
                "recovery_needed": "If there is no URL/task_id and no async status/result tool after a sync timeout, stop with COVER MCP ASYNC BLOCKER. Do not blindly retry and create a duplicate generation.",
                "instruction": "If KIE_API_KEY is set: run kie_gpt_image2_api.py only — never start with sync MCP gpt-image-2. If KIE_API_KEY is missing: prefer async MCP tools; if only sync gpt-image-2 exists, call it once. After -32001, inspect MCP logs for URL/task_id; do not blind-retry sync create. Without URL do not split/apply.",
            },
            "jobs": [
                {
                    "slot": "canvas_quad",
                    "tool": "gpt-image-2",
                    "note": "ONE successful image only — 4 panels inside, then excalibur_blog_cover_quad_split.py. Prefer Kie API script when KIE_API_KEY set. MCP is fallback only if key missing. HTTP -32001 from sync gpt-image-2 means client timeout; do not blindly retry sync create.",
                    "api_args": {
                        "model": KIE_IMAGE_MODEL,
                        "input": api_input,
                    },
                    "mcp_args": {
                        **api_input,
                    },
                }
            ],
            "validation": {
                "prompt_chars": len(prompt),
                "max_prompt_chars": MAX_MCP_PROMPT_CHARS,
                # Git-safe placeholder only — never live PUBLIC_SITE_URL host / [REDACTED].
                "required_reference_host": SITE_HOST_PLACEHOLDER,
                "resolution": MCP_RESOLUTION,
            },
        }
        batch_path = article_dir / "cover" / "quad-mcp-batch.json"
        save_json(batch_path, batch)
        # Runtime expand check (does not write live host into batch).
        live = resolve_public_base_from_env()
        if live and SITE_BASE_PLACEHOLDER in batch_ref_url:
            _ = expand_site_base(batch_ref_url, live)
        print(f"OK batch={batch_path} jobs=1 input_urls=1 git_safe_ref={batch_ref_url}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
