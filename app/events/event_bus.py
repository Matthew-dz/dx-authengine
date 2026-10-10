import logging
from typing import Dict, List, Callable, Optional, Any
from fastapi import BackgroundTasks
from app.events.event import BaseEvent

logger = logging.getLogger(__name__)


class EventBus:
    """
    Internal Event Bus bất đồng bộ theo mẫu thiết kế Singleton (Bước 5.2).
    Quản lý ánh xạ event_type -> danh sách handler và ném tác vụ xử lý vào BackgroundTasks.
    """
    _instance: Optional["EventBus"] = None

    def __new__(cls, *args, **kwargs) -> "EventBus":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._subscribers = {}
        return cls._instance

    def __init__(self):
        if not hasattr(self, "_subscribers"):
            self._subscribers: Dict[str, List[Callable]] = {}

    def subscribe(self, event_type: str, handler: Callable) -> None:
        """Đăng ký handler lắng nghe cho một event_type cụ thể."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        if handler not in self._subscribers[event_type]:
            self._subscribers[event_type].append(handler)
            logger.info(f"[EventBus] Đã đăng ký handler '{handler.__name__}' cho sự kiện '{event_type}'")

    def publish(self, event: BaseEvent, background_tasks: Optional[BackgroundTasks] = None) -> None:
        """
        Phát tán sự kiện tới toàn bộ subscriber.
        Dùng background_tasks.add_task(handler, event) để chạy ngầm, không chặn luồng API.
        """
        handlers = self._subscribers.get(event.event_type, [])
        if not handlers:
            logger.debug(f"[EventBus] Không có handler nào đăng ký cho sự kiện '{event.event_type}'")
            return

        for handler in handlers:
            if background_tasks is not None:
                background_tasks.add_task(handler, event)
                logger.debug(f"[EventBus] Đã nạp handler '{handler.__name__}' vào BackgroundTasks cho '{event.event_type}'")
            else:
                try:
                    handler(event)
                except Exception as e:
                    logger.error(f"[EventBus] Lỗi thực thi handler '{handler.__name__}': {e}", exc_info=True)


# Khởi tạo singleton instance dùng chung toàn hệ thống
event_bus = EventBus()
