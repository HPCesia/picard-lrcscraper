from __future__ import annotations

from typing import Any

from picard.plugin3.api import PluginApi

from ..common.models import Request
from .runner import ResponseHandler, Transport


def make_transport(api: PluginApi) -> Transport:
    def transport(request: Request, handler: ResponseHandler) -> None:
        def reply_handler(document: Any, reply: Any, error: Any) -> None:
            if error is not None:
                handler(None, error)
                return
            if request.response_type is None and isinstance(
                document, (bytes, bytearray)
            ):
                document = bytes(document).decode("utf-8", "replace")
            handler(document, None)

        kwargs: dict[str, Any] = {
            "url": request.url,
            "handler": reply_handler,
            "parse_response_type": request.response_type,
            "priority": True,
        }
        if request.queryargs:
            kwargs["queryargs"] = dict(request.queryargs)
        if request.headers:
            kwargs["headers"] = dict(request.headers)
        if request.method == "POST":
            if request.data is not None:
                kwargs["data"] = request.data
                kwargs["request_mimetype"] = (
                    request.mimetype or "application/x-www-form-urlencoded"
                )
            api.web_service.post_url(**kwargs)
        else:
            api.web_service.get_url(**kwargs)

    return transport
