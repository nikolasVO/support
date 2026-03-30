from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Category:
    key: str
    title: str


CATEGORIES: tuple[Category, ...] = (
    Category(key="complaints", title="Жалобы и предложения"),
    Category(key="payment", title="Проблема с оплатой"),
    Category(key="generation", title="Не работает генерация"),
    Category(key="reference", title="Референс не учтен"),
)

CATEGORY_BY_KEY = {category.key: category for category in CATEGORIES}
