"""Events extension inside the existing authenticated MCP transport boundary."""

import json

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from ..oauth.verifier import OAUTH_STATE_ATTR, OAuthIdentity
from .protocol import DEFINITION, MAX_BODY, Refused, talk_message


class EventTransport:
    def __init__(self, app, service):
        self.app, self.service = app, service

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] != "POST":
            return await self.app(scope, receive, send)
        captured, body = [], b""
        while True:
            message = await receive()
            captured.append(message)
            body += message.get("body", b"")
            if (
                message["type"] == "http.disconnect"
                or not message.get("more_body")
                or len(body) > MAX_BODY
            ):
                break

        async def replay():
            return captured.pop(0) if captured else await receive()

        rpc = {}
        try:
            rpc = json.loads(body) if len(body) <= MAX_BODY else {}
            method = rpc.get("method") if isinstance(rpc, dict) else None
        except ValueError:
            method = None
        if method in ("events/list", "events/subscribe", "events/unsubscribe"):
            request = Request(scope)
            identity = getattr(request.state, OAUTH_STATE_ATTR, None)
            result = None
            error = None
            try:
                if not isinstance(identity, OAuthIdentity) or identity.revoked:
                    raise Refused("Events require an OAuth connection")
                if (
                    rpc.get("jsonrpc") != "2.0"
                    or "id" not in rpc
                    or not isinstance(rpc.get("params", {}), dict)
                ):
                    raise Refused("Invalid request")
                result = (
                    {"events": [DEFINITION]}
                    if method == "events/list"
                    else await self.service.subscription(
                        identity.auth_id, method, rpc.get("params", {})
                    )
                )
            except Refused as exc:
                error = {"code": -32602, "message": str(exc)}
            except Exception:
                error = {"code": -32603, "message": "Events temporarily unavailable"}
            answer = {"jsonrpc": "2.0", "id": rpc.get("id")}
            answer["error" if error else "result"] = error if error else result
            return await JSONResponse(answer, headers={"Cache-Control": "no-store"})(
                scope, receive, send
            )
        if method not in ("initialize", "server/discover"):
            return await self.app(scope, replay, send)

        # Discovery is one bounded JSON reply on the MCP 2 transport; other encodings pass through.
        start, chunks = None, []

        async def advertise(message):
            nonlocal start
            if message["type"] == "http.response.start":
                start = message
                return
            chunks.append(message)
            if message.get("more_body"):
                return
            raw = b"".join(part.get("body", b"") for part in chunks)
            if start is None:
                raise RuntimeError("Missing response start")
            try:
                data = json.loads(raw)
                if "result" in data and isinstance(data["result"], dict):
                    data["result"].setdefault("capabilities", {})["events"] = {}
                    raw = json.dumps(data, separators=(",", ":")).encode()
                    start["headers"] = [
                        (k, v) for k, v in start["headers"] if k.lower() != b"content-length"
                    ]
                    start["headers"].append((b"content-length", str(len(raw)).encode()))
                    await send(start)
                    await send({"type": "http.response.body", "body": raw})
                    return
            except (ValueError, TypeError, KeyError):
                pass
            await send(start)
            for part in chunks:
                await send(part)

        return await self.app(scope, replay, advertise)


def webhook(service, secret: str, backend: str):
    async def handle(request: Request):
        if request.headers.get("x-nextcloud-talk-backend", "").rstrip("/") != backend.rstrip("/"):
            return Response(status_code=403)
        body = b""
        async for chunk in request.stream():
            body += chunk
            if len(body) > MAX_BODY:
                return Response(status_code=413)
        try:
            message = talk_message(
                secret,
                request.headers.get("x-nextcloud-talk-random", ""),
                request.headers.get("x-nextcloud-talk-signature", ""),
                body,
            )
            if message:
                await service.ingest(*message)
        except Refused:
            return Response(status_code=403)
        except OverflowError:
            return Response(status_code=503)
        return Response(status_code=204)

    return handle
