from uuid import NAMESPACE_URL, uuid5

from .schemas import HandlingEdit, StockTemplate


def stock_templates() -> list[StockTemplate]:
    rows = (
        ("Laptop", "electronics", (330, 225, 18), 1500, "high", "none", "neutral", False, False, "normal"),
        ("Laptop charger", "electronics", (145, 70, 45), 340, "medium", "none", "neutral", False, False, "normal"),
        ("Phone charger", "electronics", (95, 55, 35), 120, "medium", "none", "neutral", False, False, "normal"),
        ("Toiletry bag", "toiletries", (240, 150, 100), 650, "medium", "light", "neutral", False, True, "quick"),
        ("Shirt", "clothing", (300, 240, 35), 220, "low", "high", "neutral", False, False, "buried_ok"),
        ("Shoes", "clothing", (320, 210, 120), 850, "low", "light", "base", True, False, "buried_ok"),
        ("Jacket", "clothing", (380, 280, 100), 900, "low", "high", "neutral", False, False, "buried_ok"),
        ("Medication pouch", "health", (180, 110, 55), 180, "high", "none", "top_only", False, False, "quick"),
        ("Book", "books", (235, 160, 35), 480, "low", "none", "base", True, False, "normal"),
        ("Headphones", "electronics", (210, 180, 90), 310, "high", "none", "top_only", False, False, "normal"),
        ("Water bottle", "toiletries", (85, 85, 270), 650, "medium", "none", "neutral", False, True, "quick"),
        ("Camera", "electronics", (150, 115, 90), 720, "high", "none", "top_only", False, False, "quick"),
    )
    return [StockTemplate(
        id=uuid5(NAMESPACE_URL, f"packright-stock:{name.lower()}"), name=name, category=category,
        dimensions_mm={"width": dims[0], "height": dims[1], "depth": dims[2]}, weight_g=weight,
        handling=HandlingEdit(
            category=category, fragility=fragility, compressibility=compressibility, stack_class=stack,
            can_support_weight=can_support, liquid_risk=liquid,
            legal_orientations=("xyz",) if name == "Water bottle" else ("xyz", "xzy", "yxz", "yzx", "zxy", "zyx"),
            access=access,
        ),
    ) for name, category, dims, weight, fragility, compressibility, stack, can_support, liquid, access in rows]
