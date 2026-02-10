# API Integration Skill

**Purpose**: Integrate with external POS, ERP, and WMS systems via REST APIs

**When to use**: OAuth flows, webhooks, API clients, rate limiting, error handling

---

## Core Integration Patterns

### Pattern 1: OAuth 2.0 Authentication

**Used for**: Square, Shopify, NetSuite (user grants access to their data)

```python
from fastapi import FastAPI, HTTPException
from authlib.integrations.starlette_client import OAuth
import httpx

app = FastAPI()
oauth = OAuth()

# Register OAuth provider
oauth.register(
    name='square',
    client_id=os.getenv('SQUARE_CLIENT_ID'),
    client_secret=os.getenv('SQUARE_CLIENT_SECRET'),
    authorize_url='https://connect.squareup.com/oauth2/authorize',
    access_token_url='https://connect.squareup.com/oauth2/token',
    client_kwargs={'scope': 'ORDERS_READ ITEMS_READ INVENTORY_READ'}
)

@app.get('/api/v1/integrations/square/connect')
async def initiate_square_oauth(customer_id: str):
    """Step 1: Redirect user to Square authorization page"""
    redirect_uri = f"{BASE_URL}/api/v1/integrations/square/callback"
    return await oauth.square.authorize_redirect(
        request,
        redirect_uri,
        state=customer_id  # Pass customer_id to callback
    )

@app.get('/api/v1/integrations/square/callback')
async def square_oauth_callback(code: str, state: str):
    """Step 2: Exchange authorization code for access token"""
    
    # Exchange code for token
    token_response = await oauth.square.authorize_access_token(request)
    
    access_token = token_response['access_token']
    refresh_token = token_response.get('refresh_token')
    expires_at = datetime.now() + timedelta(seconds=token_response['expires_in'])
    
    # Store encrypted tokens in database
    await store_integration(
        customer_id=state,
        integration_type='square',
        credentials={
            'access_token': encrypt(access_token),
            'refresh_token': encrypt(refresh_token),
            'expires_at': expires_at.isoformat()
        }
    )
    
    return {"status": "success", "message": "Square connected successfully"}

async def refresh_access_token(integration_id: str):
    """Refresh expired access token"""
    integration = await get_integration(integration_id)
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            'https://connect.squareup.com/oauth2/token',
            json={
                'client_id': SQUARE_CLIENT_ID,
                'client_secret': SQUARE_CLIENT_SECRET,
                'grant_type': 'refresh_token',
                'refresh_token': decrypt(integration.credentials['refresh_token'])
            }
        )
    
    data = response.json()
    
    # Update stored tokens
    await update_integration_tokens(
        integration_id,
        access_token=encrypt(data['access_token']),
        expires_at=datetime.now() + timedelta(seconds=data['expires_in'])
    )
```

**Security Best Practices**:
- ✅ Store tokens encrypted (Fernet or AES-256)
- ✅ Use environment variables for client secrets
- ✅ Implement token refresh before expiration
- ✅ Validate state parameter (prevent CSRF)
- ✅ Use HTTPS only

---

### Pattern 2: Webhook Handling

**Used for**: Real-time POS transactions, inventory updates

```python
from fastapi import Request, HTTPException
import hmac
import hashlib

@app.post('/webhooks/square/payment')
async def handle_square_webhook(request: Request):
    """Receive Square payment webhooks (real-time transactions)"""
    
    # Step 1: Verify webhook signature (prevent spoofing)
    body = await request.body()
    signature = request.headers.get('X-Square-Signature')
    
    if not verify_square_signature(body, signature):
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    # Step 2: Parse webhook payload
    payload = await request.json()
    
    # Step 3: Handle event type
    event_type = payload['type']
    
    if event_type == 'payment.created':
        await process_payment_created(payload['data']['object'])
    elif event_type == 'payment.updated':
        await process_payment_updated(payload['data']['object'])
    
    # Step 4: Respond quickly (Square expects 200 within 10 seconds)
    return {"status": "received"}

def verify_square_signature(body: bytes, signature: str) -> bool:
    """Verify webhook came from Square"""
    webhook_secret = os.getenv('SQUARE_WEBHOOK_SECRET')
    
    # Square uses HMAC-SHA256
    expected_signature = hmac.new(
        webhook_secret.encode(),
        body,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(signature, expected_signature)

async def process_payment_created(payment_data: dict):
    """Process new payment (background task)"""
    
    # Extract transaction details
    order_id = payment_data['order_id']
    
    # Fetch full order details from Square API
    order = await fetch_square_order(order_id)
    
    # Store transactions in database
    for line_item in order['line_items']:
        await create_transaction(
            customer_id=get_customer_from_location(order['location_id']),
            store_id=map_location_to_store(order['location_id']),
            product_id=map_catalog_to_product(line_item['catalog_object_id']),
            quantity=int(line_item['quantity']),
            unit_price=Decimal(line_item['base_price_money']['amount']) / 100,
            timestamp=parse_datetime(payment_data['created_at']),
            source_system='square'
        )
```

**Webhook Best Practices**:
- ✅ Verify signatures (prevent fake webhooks)
- ✅ Respond within timeout (10 seconds)
- ✅ Process async (use background tasks)
- ✅ Implement idempotency (same webhook = same result)
- ✅ Retry on failure (with exponential backoff)

---

### Pattern 3: Scheduled API Sync

**Used for**: Hourly inventory sync, daily product catalog updates

```python
from celery import Celery
from tenacity import retry, stop_after_attempt, wait_exponential

celery_app = Celery('shelfops', broker='redis://localhost:6379/0')

@celery_app.task
async def sync_shopify_inventory(customer_id: str):
    """Hourly task: Sync inventory levels from Shopify"""
    
    integration = await get_integration(customer_id, 'shopify')
    
    # Get all store locations
    stores = await get_customer_stores(customer_id)
    
    for store in stores:
        location_id = store.metadata['shopify_location_id']
        
        # Fetch inventory levels (paginated)
        async for inventory_batch in fetch_shopify_inventory(
            integration, 
            location_id
        ):
            # Bulk insert inventory snapshots
            await bulk_insert_inventory_levels(
                customer_id=customer_id,
                store_id=store.id,
                inventory_data=inventory_batch,
                timestamp=datetime.utcnow(),
                source='shopify_sync'
            )
    
    # Update last sync timestamp
    await update_integration_last_sync(integration.id, datetime.utcnow())

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10)
)
async def fetch_shopify_inventory(integration, location_id: str):
    """Fetch inventory with retry logic"""
    
    headers = {
        'X-Shopify-Access-Token': decrypt(integration.credentials['access_token'])
    }
    
    url = f"{integration.config['shop_url']}/admin/api/2024-01/inventory_levels.json"
    params = {
        'location_ids': location_id,
        'limit': 250  # Max per page
    }
    
    async with httpx.AsyncClient() as client:
        while url:
            response = await client.get(url, headers=headers, params=params)
            
            # Handle rate limiting (429)
            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 2))
                await asyncio.sleep(retry_after)
                continue
            
            response.raise_for_status()
            data = response.json()
            
            yield data['inventory_levels']
            
            # Pagination (Link header)
            url = parse_link_header(response.headers.get('Link'))
            params = None  # Params in URL now
```

**Sync Best Practices**:
- ✅ Use retry logic (3 attempts with exponential backoff)
- ✅ Handle rate limits (429 → wait and retry)
- ✅ Paginate large datasets (don't fetch all at once)
- ✅ Track last sync time (avoid duplicate work)
- ✅ Batch database inserts (faster than one-by-one)

---

### Pattern 4: Rate Limiting (Client-Side)

**Prevent hitting API rate limits**

```python
import asyncio
from collections import deque
from datetime import datetime, timedelta

class RateLimiter:
    """Token bucket rate limiter"""
    
    def __init__(self, requests_per_second: int):
        self.rate = requests_per_second
        self.tokens = requests_per_second
        self.last_update = datetime.now()
        self.lock = asyncio.Lock()
    
    async def acquire(self):
        """Wait until a token is available"""
        async with self.lock:
            now = datetime.now()
            elapsed = (now - self.last_update).total_seconds()
            
            # Refill tokens based on elapsed time
            self.tokens = min(
                self.rate,
                self.tokens + elapsed * self.rate
            )
            self.last_update = now
            
            # Wait if no tokens available
            if self.tokens < 1:
                wait_time = (1 - self.tokens) / self.rate
                await asyncio.sleep(wait_time)
                self.tokens = 0
            else:
                self.tokens -= 1

# Square: 500 requests/minute per location
square_limiter = RateLimiter(requests_per_second=500/60)

async def call_square_api(endpoint: str, **kwargs):
    """Make Square API call with rate limiting"""
    await square_limiter.acquire()
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://connect.squareup.com/v2/{endpoint}",
            **kwargs
        )
    
    return response.json()
```

---

### Pattern 5: Error Handling & Circuit Breaker

```python
from enum import Enum
from datetime import datetime, timedelta

class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if recovered

class CircuitBreaker:
    """Prevent cascading failures from unreliable APIs"""
    
    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED
    
    async def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker"""
        
        # If circuit open, check if timeout elapsed
        if self.state == CircuitState.OPEN:
            if datetime.now() - self.last_failure_time > timedelta(seconds=self.timeout):
                self.state = CircuitState.HALF_OPEN
            else:
                raise Exception("Circuit breaker open - API unavailable")
        
        try:
            result = await func(*args, **kwargs)
            
            # Success - reset circuit
            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.CLOSED
            self.failure_count = 0
            
            return result
            
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = datetime.now()
            
            # Open circuit if threshold exceeded
            if self.failure_count >= self.failure_threshold:
                self.state = CircuitState.OPEN
                await notify_ops_team(f"Circuit breaker opened for {func.__name__}")
            
            raise

# Usage
square_circuit = CircuitBreaker(failure_threshold=5, timeout=60)

async def fetch_square_data_safe(endpoint: str):
    return await square_circuit.call(
        call_square_api,
        endpoint=endpoint
    )
```

---

## Integration-Specific Guides

### Square POS Integration

**API Reference**: https://developer.squareup.com/reference/square

**Key Endpoints**:
- `GET /v2/orders/{order_id}` - Fetch order details
- `GET /v2/catalog/list` - List products
- `GET /v2/inventory/counts` - Inventory levels
- `POST /v2/orders/batch-retrieve` - Bulk order fetch

**Authentication**: OAuth 2.0 (access token in `Authorization: Bearer` header)

**Rate Limits**: 500 requests/minute per location

**Webhooks**:
- `payment.created` - New payment processed
- `payment.updated` - Payment status changed
- `order.created` - New order placed
- `inventory.count.updated` - Inventory changed

**Data Mapping**:
```python
# Square Location → ShelfOps Store
store_id = map_square_location_to_store(square_location_id)

# Square CatalogObject → ShelfOps Product
product_id = map_square_catalog_to_product(catalog_object_id)

# Square Order → ShelfOps Transactions
for line_item in square_order['line_items']:
    transaction = Transaction(
        store_id=store_id,
        product_id=map_square_catalog_to_product(line_item['catalog_object_id']),
        quantity=int(line_item['quantity']),
        unit_price=Decimal(line_item['base_price_money']['amount']) / 100,
        timestamp=parse_square_datetime(square_order['created_at'])
    )
```

---

### Shopify Integration

**API Reference**: https://shopify.dev/docs/api

**Key Endpoints**:
- `GET /admin/api/2024-01/products.json` - Product catalog
- `GET /admin/api/2024-01/inventory_levels.json` - Inventory levels
- `GET /admin/api/2024-01/orders.json` - Orders

**Authentication**: 
- OAuth 2.0 (for app installation)
- Access token in `X-Shopify-Access-Token` header

**Rate Limits**: 
- REST: 2 requests/second (burst: 40)
- GraphQL: 1000 points/second (queries cost different points)

**Webhooks**:
- `orders/create` - New order
- `products/update` - Product changed
- `inventory_levels/update` - Inventory changed

**Data Mapping**:
```python
# Shopify Location → ShelfOps Store
store_id = map_shopify_location_to_store(shopify_location_id)

# Shopify Product Variant → ShelfOps Product
product_id = map_shopify_variant_to_product(variant_id)

# Shopify Order → ShelfOps Transactions
for line_item in shopify_order['line_items']:
    transaction = Transaction(
        store_id=get_store_from_location(shopify_order['location_id']),
        product_id=map_shopify_variant_to_product(line_item['variant_id']),
        quantity=line_item['quantity'],
        unit_price=Decimal(line_item['price']),
        timestamp=parse_shopify_datetime(shopify_order['created_at'])
    )
```

---

## Testing Integrations

```python
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_square_oauth_flow():
    """Test Square OAuth integration"""
    
    # Mock OAuth response
    with patch('authlib.integrations.starlette_client.OAuth.square') as mock_oauth:
        mock_oauth.authorize_access_token = AsyncMock(return_value={
            'access_token': 'test_token',
            'refresh_token': 'test_refresh',
            'expires_in': 3600
        })
        
        # Call callback
        response = await square_oauth_callback(
            code='test_code',
            state='customer_123'
        )
        
        assert response['status'] == 'success'
        
        # Verify token was stored
        integration = await get_integration('customer_123', 'square')
        assert integration is not None
        assert decrypt(integration.credentials['access_token']) == 'test_token'

@pytest.mark.asyncio
async def test_webhook_signature_validation():
    """Test webhook signature verification"""
    
    body = b'{"type": "payment.created", "data": {}}'
    secret = 'webhook_secret'
    
    # Generate valid signature
    signature = hmac.new(
        secret.encode(),
        body,
        hashlib.sha256
    ).hexdigest()
    
    assert verify_square_signature(body, signature) == True
    assert verify_square_signature(body, 'invalid_sig') == False

@pytest.mark.asyncio
async def test_rate_limiter():
    """Test rate limiter prevents exceeding limits"""
    
    limiter = RateLimiter(requests_per_second=10)
    
    # Make 10 requests (should be instant)
    start = datetime.now()
    for _ in range(10):
        await limiter.acquire()
    elapsed = (datetime.now() - start).total_seconds()
    assert elapsed < 0.1
    
    # 11th request should wait ~0.1 second
    start = datetime.now()
    await limiter.acquire()
    elapsed = (datetime.now() - start).total_seconds()
    assert 0.08 < elapsed < 0.12
```

---

## DO / DON'T

### DO
- ✅ Encrypt OAuth tokens before storing
- ✅ Verify webhook signatures
- ✅ Implement retry logic (exponential backoff)
- ✅ Handle rate limits gracefully
- ✅ Use circuit breakers for unreliable APIs
- ✅ Log all API calls (for debugging)
- ✅ Test with mock responses

### DON'T
- ❌ Store tokens in plain text
- ❌ Trust webhooks without signature verification
- ❌ Ignore rate limits (you'll get blocked)
- ❌ Fetch all data at once (paginate)
- ❌ Retry indefinitely (set max attempts)
- ❌ Expose API credentials in code (use env vars)
- ❌ Skip error handling (APIs fail)

---

**Last Updated**: 2026-02-09  
**Version**: 1.0.0
