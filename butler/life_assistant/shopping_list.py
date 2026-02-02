from __future__ import annotations

import json
import logging
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ItemCategory(Enum):
    FOOD = "food"
    HOUSEHOLD = "household"
    PERSONAL = "personal"
    ELECTRONICS = "electronics"
    OTHER = "other"


@dataclass
class ShoppingItem:
    id: str
    name: str
    quantity: int
    category: str
    purchased: bool = False
    priority: int = 1
    notes: Optional[str] = None
    created_at: int = 0
    purchased_at: Optional[int] = None

    def __post_init__(self) -> None:
        if self.created_at == 0:
            from ..core.utils import utc_ts
            self.created_at = utc_ts()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ShoppingItem":
        return cls(**data)


class ShoppingListManager:
    def __init__(self, storage_path: Optional[str] = None) -> None:
        self.storage_path = storage_path or "/app/butler/data/shopping_list.json"
        self.items: Dict[str, ShoppingItem] = {}
        self._load_from_disk()

    def _load_from_disk(self) -> None:
        try:
            path = Path(self.storage_path)
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item_id, item_data in data.items():
                        self.items[item_id] = ShoppingItem.from_dict(item_data)
                logger.info(f"Loaded {len(self.items)} shopping items")
        except Exception as e:
            logger.error(f"Failed to load shopping list: {e}")

    def _save_to_disk(self) -> None:
        try:
            path = Path(self.storage_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                data = {item_id: item.to_dict() for item_id, item in self.items.items()}
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save shopping list: {e}")

    def add_item(
        self,
        name: str,
        quantity: int = 1,
        category: str = ItemCategory.OTHER.value,
        priority: int = 1,
        notes: Optional[str] = None,
    ) -> ShoppingItem:
        from ..core.utils import new_uuid, utc_ts
        item_id = new_uuid()
        item = ShoppingItem(
            id=item_id,
            name=name,
            quantity=quantity,
            category=category,
            priority=priority,
            notes=notes,
            created_at=utc_ts(),
        )
        self.items[item_id] = item
        self._save_to_disk()
        logger.info(f"Added shopping item: {name}")
        return item

    def update_item(
        self,
        item_id: str,
        name: Optional[str] = None,
        quantity: Optional[int] = None,
        category: Optional[str] = None,
        priority: Optional[int] = None,
        notes: Optional[str] = None,
    ) -> Optional[ShoppingItem]:
        if item_id not in self.items:
            return None
        item = self.items[item_id]
        if name is not None:
            item.name = name
        if quantity is not None:
            item.quantity = quantity
        if category is not None:
            item.category = category
        if priority is not None:
            item.priority = priority
        if notes is not None:
            item.notes = notes
        self._save_to_disk()
        logger.info(f"Updated shopping item: {item.name}")
        return item

    def mark_purchased(self, item_id: str) -> Optional[ShoppingItem]:
        if item_id not in self.items:
            return None
        from ..core.utils import utc_ts
        item = self.items[item_id]
        item.purchased = True
        item.purchased_at = utc_ts()
        self._save_to_disk()
        logger.info(f"Marked item as purchased: {item.name}")
        return item

    def mark_unpurchased(self, item_id: str) -> Optional[ShoppingItem]:
        if item_id not in self.items:
            return None
        item = self.items[item_id]
        item.purchased = False
        item.purchased_at = None
        self._save_to_disk()
        logger.info(f"Marked item as unpurchased: {item.name}")
        return item

    def delete_item(self, item_id: str) -> bool:
        if item_id in self.items:
            name = self.items[item_id].name
            del self.items[item_id]
            self._save_to_disk()
            logger.info(f"Deleted shopping item: {name}")
            return True
        return False

    def get_item(self, item_id: str) -> Optional[ShoppingItem]:
        return self.items.get(item_id)

    def get_unpurchased_items(self, category: Optional[str] = None) -> List[ShoppingItem]:
        items = [
            item for item in self.items.values()
            if not item.purchased and (category is None or item.category == category)
        ]
        items.sort(key=lambda i: (-i.priority, i.created_at))
        return items

    def get_purchased_items(self, category: Optional[str] = None) -> List[ShoppingItem]:
        items = [
            item for item in self.items.values()
            if item.purchased and (category is None or item.category == category)
        ]
        items.sort(key=lambda i: i.purchased_at or 0, reverse=True)
        return items

    def get_items_by_category(self, category: str) -> List[ShoppingItem]:
        items = [
            item for item in self.items.values()
            if item.category == category
        ]
        items.sort(key=lambda i: (-i.priority, i.created_at))
        return items

    def search_items(self, query: str) -> List[ShoppingItem]:
        query_lower = query.lower()
        items = [
            item for item in self.items.values()
            if query_lower in item.name.lower() or
               (item.notes and query_lower in item.notes.lower())
        ]
        items.sort(key=lambda i: (-i.priority, i.created_at))
        return items

    def clear_purchased(self) -> int:
        purchased_ids = [
            item_id for item_id, item in self.items.items()
            if item.purchased
        ]
        count = len(purchased_ids)
        for item_id in purchased_ids:
            del self.items[item_id]
        if count > 0:
            self._save_to_disk()
            logger.info(f"Cleared {count} purchased items")
        return count

    def get_summary(self) -> Dict[str, Any]:
        unpurchased = self.get_unpurchased_items()
        purchased = self.get_purchased_items()
        categories = {}
        for item in self.items.values():
            cat = item.category
            if cat not in categories:
                categories[cat] = {"total": 0, "purchased": 0}
            categories[cat]["total"] += 1
            if item.purchased:
                categories[cat]["purchased"] += 1
        return {
            "total_items": len(self.items),
            "unpurchased_count": len(unpurchased),
            "purchased_count": len(purchased),
            "categories": categories,
        }
