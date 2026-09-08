from __future__ import annotations

from typing import Any


POSITIVE_TERMS = (
    "قرارداد", "قرارداد جدید", "افزایش سرمایه", "فروش", "صادرات", "پروژه",
    "مناقصه", "بهره برداری", "راه اندازی", "تولید", "افزایش نرخ", "مجوز",
    "تغییر نرخ", "تعدیل مثبت", "سود", "تقسیم سود", "تفاهم نامه", "واگذاری",
    "contract", "export", "project", "license", "production", "price increase",
)
NEGATIVE_TERMS = (
    "توقف", "کاهش تولید", "کاهش فروش", "لغو", "زیان", "عدم تحقق", "تعلیق",
    "محدودیت", "بدهی", "ورشکست", "کاهش نرخ", "تعدیل منفی", "loss", "cancelled",
    "suspension", "production cut",
)


def _text(row: dict[str, Any]) -> str:
    parts = []
    for key in ("title", "subject", "description", "reportTitle", "reportDesc", "letterTitle", "letterDesc", "text"):
        value = row.get(key)
        if value is not None:
            parts.append(str(value))
    return " ".join(parts).strip().lower()


def detect_catalysts(rows: list[dict[str, Any]] | None, max_items: int = 10) -> dict[str, Any]:
    """Classify recent Codal metadata as a catalyst signal without inventing facts."""
    rows = [r for r in (rows or []) if isinstance(r, dict)]
    positive: list[dict[str, Any]] = []
    negative: list[dict[str, Any]] = []
    for row in rows[:max_items]:
        text = _text(row)
        if not text:
            continue
        pos = [term for term in POSITIVE_TERMS if term.lower() in text]
        neg = [term for term in NEGATIVE_TERMS if term.lower() in text]
        item = {"date": row.get("date") or row.get("publishDate") or row.get("dEven"), "title": row.get("title") or row.get("subject") or row.get("reportTitle") or row.get("letterTitle"), "positive_matches": pos, "negative_matches": neg}
        if pos and not neg:
            positive.append(item)
        elif neg and not pos:
            negative.append(item)
    status = "positive" if positive and not negative else ("negative" if negative and not positive else ("mixed" if positive or negative else "unavailable"))
    return {
        "new_catalyst": True if positive else (False if negative and not positive else None),
        "status": status,
        "positive_count": len(positive),
        "negative_count": len(negative),
        "positive_items": positive,
        "negative_items": negative,
        "source": "codal_metadata",
        "confidence": "metadata_keyword_proxy",
    }
