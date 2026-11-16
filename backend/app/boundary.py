"""ASGI byte-boundary: bound actual streamed body before application parsing."""
import uuid
from urllib.parse import urlsplit
from starlette.responses import JSONResponse


class RequestBoundary:
    def __init__(self,app):
        self.app=app

    async def __call__(self,scope,receive,send):
        if scope['type']!='http':
            return await self.app(scope,receive,send)
        rid=str(uuid.uuid4())
        scope.setdefault('state',{})['request_id']=rid
        headers={k.decode().lower():v.decode('latin1') for k,v in scope['headers']}
        async def reject(code,detail):
            await JSONResponse({'detail':detail,'request_id':rid},code,headers={'X-Request-ID':rid})(scope,receive,send)
        try:
            host=headers.get('host','')
            parsed=urlsplit('//'+host)
            if parsed.hostname not in ('localhost','127.0.0.1','::1','testserver') or parsed.username or parsed.path:
                return await reject(400,'Host não autorizado')
            _=parsed.port
            length=headers.get('content-length')
            if length is not None and (not length.isascii() or not length.isdigit()):
                return await reject(400,'Content-Length inválido')
            if length is not None and int(length)>16384:
                return await reject(413,'Payload excede 16 KiB')
        except ValueError:
            return await reject(400,'Cabeçalho inválido')
        origin=headers.get('origin')
        if origin and origin not in ('http://'+host,'https://'+host):
            return await reject(403,'Origem não autorizada')
        chunks=[]
        total=0
        while True:
            part=await receive()
            if part['type']=='http.disconnect':
                return
            chunk=part.get('body',b'')
            total+=len(chunk)
            if total>16384:
                return await reject(413,'Payload excede 16 KiB')
            chunks.append(chunk)
            if not part.get('more_body',False):
                break
        if length is not None and int(length)!=total:
            return await reject(400,'Tamanho declarado divergente')
        sent=False
        async def replay():
            nonlocal sent
            if not sent:
                sent=True
                return {'type':'http.request','body':b''.join(chunks),'more_body':False}
            return await receive()
        async def secured(message):
            if message['type']=='http.response.start':
                message['headers'] += [(b'x-request-id',rid.encode()),(b'x-content-type-options',b'nosniff'),
                    (b'referrer-policy',b'no-referrer'),(b'content-security-policy',b"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'")]
            await send(message)
        await self.app(scope,replay,secured)
