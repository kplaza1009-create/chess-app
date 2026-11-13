import asyncio

from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

AUTH_BODY_LIMIT = 16_384
AUTH_BODY_TIMEOUT = 10


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        is_api = scope["path"].startswith("/api/v1/")

        async def secure_send(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["X-Content-Type-Options"] = "nosniff"
                headers["Referrer-Policy"] = "same-origin"
                if is_api:
                    headers["Cache-Control"] = "no-store"
                    headers["Pragma"] = "no-cache"
            await send(message)

        if is_api and scope["method"] == "POST":
            # Only PGN import needs a larger JSON envelope. Keep auth limits intact.
            body_limit = 524_288 if scope["path"] == "/api/v1/history/import" else AUTH_BODY_LIMIT
            content_length = Headers(scope=scope).get("content-length", "")
            if content_length.isascii() and content_length.isdecimal():
                if len(content_length) > 20 or int(content_length) > body_limit:
                    response = JSONResponse(
                        {"detail": "Request body is too large"}, status_code=413
                    )
                    await response(scope, receive, secure_send)
                    return
            body = bytearray()
            try:
                async with asyncio.timeout(AUTH_BODY_TIMEOUT):
                    while True:
                        message = await receive()
                        if message["type"] == "http.disconnect":
                            return
                        body.extend(message.get("body", b""))
                        if len(body) > body_limit:
                            break
                        if not message.get("more_body", False):
                            break
            except TimeoutError:
                response = JSONResponse({"detail": "Request body timed out"}, status_code=408)
                await response(scope, receive, secure_send)
                return
            if len(body) > body_limit:
                response = JSONResponse({"detail": "Request body is too large"}, status_code=413)
                await response(scope, receive, secure_send)
                return
            delivered = False

            async def buffered_receive() -> Message:
                nonlocal delivered
                if delivered:
                    return await receive()
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}

            await self.app(scope, buffered_receive, secure_send)
        else:
            await self.app(scope, receive, secure_send)
