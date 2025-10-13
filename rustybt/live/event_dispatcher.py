"""Event dispatcher for routing events to handlers.

This module provides the EventDispatcher class that routes events to registered
handler functions based on event type.
"""

import asyncio
from collections.abc import Awaitable, Callable

import structlog

from rustybt.live.events import Event

logger = structlog.get_logger()


HandlerFunc = Callable[[Event], Awaitable[None]]


class EventDispatcher:
    """Dispatches events to registered handler functions."""

    def __init__(self) -> None:
        """Initialize event dispatcher."""
        self._handlers: dict[str, list[HandlerFunc]] = {}

    def register_handler(self, event_type: str, handler: HandlerFunc) -> None:
        """Register a handler for an event type.

        Args:
            event_type: Type of event to handle (e.g., 'market_data', 'order_fill')
            handler: Async function to call when event occurs

        Example:
            >>> dispatcher.register_handler('market_data', strategy.on_data)
        """
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
        logger.debug("handler_registered", event_type=event_type, handler=handler.__name__)

    def unregister_handler(self, event_type: str, handler: HandlerFunc) -> None:
        """Unregister a handler for an event type.

        Args:
            event_type: Type of event
            handler: Handler function to remove
        """
        if event_type in self._handlers:
            try:
                self._handlers[event_type].remove(handler)
                logger.debug(
                    "handler_unregistered", event_type=event_type, handler=handler.__name__
                )
            except ValueError:
                logger.warning("handler_not_found", event_type=event_type, handler=handler.__name__)

    async def dispatch(self, event: Event) -> None:
        """Dispatch event to all registered handlers.

        Handlers are called concurrently. If a handler raises an exception,
        it is logged and execution continues.

        Args:
            event: Event to dispatch
        """
        event_type = event.event_type
        handlers = self._handlers.get(event_type, [])

        if not handlers:
            logger.debug("no_handlers", event_type=event_type)
            return

        logger.debug(
            "dispatching_event",
            event_type=event_type,
            handler_count=len(handlers),
            priority=event.priority,
        )

        # Execute all handlers concurrently
        tasks = []
        for handler in handlers:
            tasks.append(self._safe_handler_call(handler, event))

        await asyncio.gather(*tasks)

    async def _safe_handler_call(self, handler: HandlerFunc, event: Event) -> None:
        """Call handler with error handling.

        Args:
            handler: Handler function to call
            event: Event to pass to handler
        """
        try:
            await handler(event)
        except Exception as e:
            logger.error(
                "handler_error",
                event_type=event.event_type,
                handler=handler.__name__,
                error=str(e),
                exc_info=True,
            )

    def get_handler_count(self, event_type: str) -> int:
        """Get number of handlers registered for event type.

        Args:
            event_type: Type of event

        Returns:
            Number of registered handlers
        """
        return len(self._handlers.get(event_type, []))

    def clear_handlers(self, event_type: str | None = None) -> None:
        """Clear handlers for event type or all handlers.

        Args:
            event_type: Type of event to clear, or None to clear all
        """
        if event_type is None:
            self._handlers.clear()
            logger.debug("all_handlers_cleared")
        else:
            self._handlers.pop(event_type, None)
            logger.debug("handlers_cleared", event_type=event_type)
