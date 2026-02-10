# FastAPI Skill

**Purpose**: Build production-ready REST APIs with FastAPI  
**When to use**: Creating API endpoints, authentication, middleware, error handling

---

## Project Structure

```
backend/api/
├── main.py              # FastAPI app, CORS, lifespan
├── deps.py              # Dependency injection
├── middleware.py         # Tenant context, logging
└── v1/routers/
    ├── stores.py
    ├── products.py
    ├── forecasts.py
    ├── alerts.py
    └── integrations.py
```

---

## Core Patterns

### 1. App Setup

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: init DB pool, Redis
    await init_db()
    await init_redis()
    yield
    # Shutdown: close connections
    await close_db()
    await close_redis()

app = FastAPI(
    title="ShelfOps API",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 2. Pydantic Models (Request/Response)

```python
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime

class StoreCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    city: str
    state: str = Field(..., min_length=2, max_length=2)
    
class StoreResponse(BaseModel):
    store_id: UUID
    customer_id: UUID
    name: str
    city: str
    state: str
    created_at: datetime
    
    model_config = {"from_attributes": True}
```

### 3. Dependency Injection

```python
from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session

async def get_current_user(
    token: str = Depends(oauth2_scheme)
) -> User:
    payload = decode_jwt(token)
    user = await get_user_by_id(payload["sub"])
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user

async def set_tenant_context(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    await db.execute(
        text("SET LOCAL app.current_customer_id = :cid"),
        {"cid": str(user.customer_id)}
    )
    return db
```

### 4. Router Pattern

```python
from fastapi import APIRouter, Depends, HTTPException, Query

router = APIRouter(prefix="/api/v1/stores", tags=["stores"])

@router.get("/", response_model=list[StoreResponse])
async def list_stores(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(set_tenant_context),
):
    stores = await db.execute(
        select(Store).offset(skip).limit(limit)
    )
    return stores.scalars().all()

@router.post("/", response_model=StoreResponse, status_code=201)
async def create_store(
    store: StoreCreate,
    db: AsyncSession = Depends(set_tenant_context),
    user: User = Depends(get_current_user),
):
    db_store = Store(**store.model_dump(), customer_id=user.customer_id)
    db.add(db_store)
    await db.commit()
    await db.refresh(db_store)
    return db_store
```

### 5. Error Handling

```python
from fastapi import Request
from fastapi.responses import JSONResponse

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "status_code": exc.status_code}
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "status_code": 500}
    )
```

### 6. WebSocket (Real-Time Alerts)

```python
from fastapi import WebSocket, WebSocketDisconnect

@app.websocket("/ws/alerts/{customer_id}")
async def websocket_alerts(websocket: WebSocket, customer_id: str):
    await websocket.accept()
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(f"alerts:{customer_id}")
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                await websocket.send_json(json.loads(message["data"]))
    except WebSocketDisconnect:
        await pubsub.unsubscribe(f"alerts:{customer_id}")
```

---

## DO / DON'T

### DO
- ✅ Use Pydantic for all request/response validation
- ✅ Use dependency injection for DB sessions, auth
- ✅ Use `async def` for all I/O-bound endpoints
- ✅ Return proper HTTP status codes (201 for create, 204 for delete)
- ✅ Use `APIRouter` for modular routes
- ✅ Auto-generate OpenAPI docs (built-in)

### DON'T
- ❌ Put business logic in route handlers (use service layer)
- ❌ Use synchronous DB calls (use async)
- ❌ Skip input validation (Pydantic handles this)
- ❌ Return 200 for everything (use correct HTTP codes)
- ❌ Hardcode secrets (use environment variables)

---

**Last Updated**: 2026-02-09
