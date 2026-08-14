"""Tenant kitchen-warmth visual lock (illustrative, no host, no pink-cat)."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from excalibur_blog_cover_quad_prompt import (  # noqa: E402
    build_prompt,
    style_allows_cat_stickers,
    style_is_illustrative_no_host,
    style_is_situational_cat_hero,
)
from excalibur_blog_quad_manifest import pick_visual_type  # noqa: E402


def _load(rel: str) -> dict:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


class KitchenWarmthVisualTests(unittest.TestCase):
    def test_tenant_and_hero_are_illustrative(self) -> None:
        tenant = _load("shared/tenant-config.json")
        hero = _load("memory/cover/blog-hero.json")
        style = _load("memory/cover/quad-style-kitchen-warmth-ru.json")
        self.assertEqual(tenant["cover_mode"], "illustrative")
        self.assertFalse(tenant["setup_complete"])
        self.assertEqual(tenant["cta_links"], [])
        self.assertEqual(
            tenant["cover_files"]["style_preset"],
            "memory/cover/quad-style-kitchen-warmth-ru.json",
        )
        self.assertEqual(hero["cover_mode"], "illustrative")
        self.assertEqual(hero["status"], "ok")
        self.assertEqual(hero["meme_caption_ru"], "")
        self.assertFalse(hero.get("reference_url_hosted"))
        self.assertEqual(style["style_id"], "kitchen-warmth-ru")
        self.assertEqual(style["cover_hero_mode"], "illustrative_scene")
        self.assertTrue(style["skip_human_host"])
        self.assertFalse(style["allows_animal_stickers"])
        self.assertEqual(style["allowed_animal_motif"], "")
        self.assertEqual(style["local_reference"], "")
        self.assertEqual(style["accent"], "#C45C26")
        self.assertTrue(style_is_illustrative_no_host(style, hero))
        self.assertFalse(style_allows_cat_stickers(style))
        self.assertFalse(style_is_situational_cat_hero(style))

    def test_design_code_palette_not_pink_cat(self) -> None:
        dc = _load("memory/cover/cover-design-code.json")
        pal = dc["color_palette"]
        self.assertEqual(dc["design_code_id"], "kitchen_warmth_dignity")
        self.assertEqual(dc["status"], "ok")
        self.assertEqual(pal["background"], "#FFFFFF")
        self.assertEqual(pal["ink"], "#2A2118")
        self.assertEqual(pal["accent_primary"], "#C45C26")
        self.assertNotEqual(pal["accent_primary"], "#FF1493")

    def test_inline_types_are_keyword_dict(self) -> None:
        catalog = _load("memory/cover/inline-visual-types.json")
        types = catalog["types"]
        self.assertIsInstance(types, dict)
        self.assertEqual(catalog["status"], "ok")
        used: set[str] = set()
        first = pick_visual_type("Рецепт с нуля: три шага на кухне", catalog, used)
        used.add(first)
        second = pick_visual_type("Сравнение чая и кофе", catalog, used)
        self.assertEqual(first, "workflow")
        self.assertEqual(second, "comparison")
        self.assertIn("keywords", types["checklist"])

    def test_prompt_is_kitchen_scene_not_host_or_cat(self) -> None:
        hero = _load("memory/cover/blog-hero.json")
        dc = _load("memory/cover/cover-design-code.json")
        style = _load("memory/cover/quad-style-kitchen-warmth-ru.json")
        types = _load("memory/cover/inline-visual-types.json")
        manifest = {
            "cover_hook": "Возраст не приговор",
            "cover_hook_highlight": "приговор",
            "slots": {
                "cover": {
                    "scene_hint": hero["prompt_fragment"],
                    "sticky": "паспорт, не приговор",
                    "meme_caption_ru": "",
                },
                "inline_1": {
                    "visual_type": "workflow",
                    "h2_anchor": "Шаги",
                    "scene_hint": "paper steps",
                    "labels": ["С нуля"],
                },
                "inline_2": {
                    "visual_type": "fact_card",
                    "h2_anchor": "Факт",
                    "scene_hint": "card",
                    "labels": ["Чай"],
                },
                "inline_3": {
                    "visual_type": "checklist",
                    "h2_anchor": "Список",
                    "scene_hint": "board",
                    "labels": ["Окно"],
                },
            },
        }
        prompt = build_prompt(manifest, style, hero, types, dc)
        self.assertIn("accent #C45C26", prompt)
        self.assertIn("NO host face", prompt)
        self.assertNotIn("host+face", prompt)
        self.assertNotIn("LARGE situational cat", prompt)
        self.assertIn("«Возраст не приговор»", prompt)
        self.assertLessEqual(len(prompt), 3500)


if __name__ == "__main__":
    unittest.main()
