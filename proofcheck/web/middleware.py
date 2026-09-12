"""Request admission and streamed body limits before multipart parsing."""
from collections import defaultdict, deque
from threading import BoundedSemaphore, Lock
from time import monotonic

from starlette.formparsers import MultiPartException
from starlette.requests import Request
from starlette.responses import JSONResponse

from . import auth


class ResourceLimitsMiddleware:
    def __init__(self, app, *, upload_limit, max_checks=2):
        self.app = app
        self.upload_limit = upload_limit
        self.slots = BoundedSemaphore(max_checks)
        self.attempts = defaultdict(deque)
        self.lock = Lock()

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        path = scope['path']
        request = Request(scope)
        processing = scope['method'] == 'POST' and path in {'/api/check', '/api/inspect'}
        logging_in = scope['method'] == 'POST' and path in {'/api/auth/login', '/api/auth/register'}

        async def reject(status, message, headers=None):
            await JSONResponse({'error': message}, status_code=status, headers=headers)(scope, receive, send)

        if processing and auth.auth_enabled() and not auth.verify_token(request.cookies.get(auth.SESSION_COOKIE)):
            return await reject(401, 'Authentication required.')
        if logging_in:
            # Per-process, bounded IP buckets; a reverse proxy should also rate-limit.
            now = monotonic()
            host = (scope.get('client') or ('unknown', 0))[0]
            with self.lock:
                for key in list(self.attempts):
                    if not self.attempts[key] or self.attempts[key][-1] < now - 60:
                        del self.attempts[key]
                if host not in self.attempts and len(self.attempts) >= 10000:
                    limited = True
                else:
                    bucket = self.attempts[host]
                    while bucket and bucket[0] < now - 60:
                        bucket.popleft()
                    limited = len(bucket) >= 20
                    if not limited:
                        bucket.append(now)
            if limited:
                return await reject(429, 'Too many sign-in attempts. Try again in a minute.', {'Retry-After': '60'})

        limit = (2 * self.upload_limit() + 1024 * 1024) if processing else 16384 if logging_in else None
        if limit is not None:
            try:
                size = int(request.headers.get('content-length', '0'))
                if size < 0:
                    raise ValueError()
            except ValueError:
                return await reject(400, 'Invalid Content-Length header.')
            if size > limit:
                return await reject(413, 'Request exceeds the configured upload limit.')
        if processing and not self.slots.acquire(blocking=False):
            return await reject(429, 'The server is processing other checks. Please retry shortly.', {'Retry-After': '3'})
        consumed = 0
        body_exceeded = False
        async def limited_receive():
            nonlocal consumed, body_exceeded
            message = await receive()
            if message['type'] == 'http.request':
                consumed += len(message.get('body', b''))
                if limit is not None and consumed > limit:
                    body_exceeded = True
                    raise MultiPartException('Request exceeds the configured upload limit.')
            return message
        async def private_send(message):
            if message['type'] == 'http.response.start' and body_exceeded:
                message['status'] = 413
            if message['type'] == 'http.response.start' and (path.startswith('/api/') or path.startswith('/reports/')):
                headers = list(message.get('headers', []))
                if not any(key.lower() == b'cache-control' for key, _ in headers):
                    headers.append((b'cache-control', b'no-store'))
                headers.append((b'x-content-type-options', b'nosniff'))
                message['headers'] = headers
            await send(message)
        try:
            await self.app(scope, limited_receive, private_send)
        finally:
            if processing:
                self.slots.release()
