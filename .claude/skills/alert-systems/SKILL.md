# Alert Systems Skill

**Purpose**: Real-time alerting with Redis pub/sub + WebSocket + Email  
**When to use**: Implementing stockout alerts, anomaly notifications, order recommendations

---

## Alert Architecture

```
ML Prediction → Alert Engine → Redis Pub/Sub → WebSocket (dashboard)
                                             → Email (SendGrid)
                                             → Database (history)
```

---

## Core Patterns

### 1. Alert Engine

```python
from enum import Enum
from uuid import uuid4
from datetime import datetime

class AlertType(Enum):
    STOCKOUT_PREDICTED = "stockout_predicted"
    ANOMALY_DETECTED = "anomaly_detected"
    REORDER_RECOMMENDED = "reorder_recommended"
    FORECAST_ACCURACY_LOW = "forecast_accuracy_low"

class AlertSeverity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

async def create_alert(
    customer_id: str,
    store_id: str,
    product_id: str,
    alert_type: AlertType,
    severity: AlertSeverity,
    message: str,
    metadata: dict = None,
):
    alert = {
        "alert_id": str(uuid4()),
        "customer_id": customer_id,
        "store_id": store_id,
        "product_id": product_id,
        "alert_type": alert_type.value,
        "severity": severity.value,
        "message": message,
        "metadata": metadata or {},
        "status": "open",
        "created_at": datetime.utcnow().isoformat(),
    }
    
    # 1. Save to database (history)
    await insert_alert(alert)
    
    # 2. Publish to Redis (real-time)
    await redis.publish(f"alerts:{customer_id}", json.dumps(alert))
    
    # 3. Send email if critical
    if severity == AlertSeverity.CRITICAL:
        await send_alert_email(customer_id, alert)
    
    return alert
```

### 2. Redis Pub/Sub Publisher

```python
import redis.asyncio as redis

redis_client = redis.from_url("redis://localhost:6379/0")

async def publish_alert(customer_id: str, alert: dict):
    channel = f"alerts:{customer_id}"
    await redis_client.publish(channel, json.dumps(alert))

async def publish_batch_alerts(customer_id: str, alerts: list[dict]):
    async with redis_client.pipeline() as pipe:
        for alert in alerts:
            pipe.publish(f"alerts:{customer_id}", json.dumps(alert))
        await pipe.execute()
```

### 3. Stockout Detection Rules

```python
async def check_stockout_risk(store_id: str, product_id: str):
    """Run after each forecast to check for stockout risk"""
    
    forecast = await get_latest_forecast(store_id, product_id)
    inventory = await get_current_inventory(store_id, product_id)
    reorder_point = await get_reorder_point(store_id, product_id)
    
    # Calculate days until stockout
    daily_demand = forecast["forecasted_demand"]
    days_until_stockout = inventory.quantity_on_hand / max(daily_demand, 0.1)
    
    if days_until_stockout <= 1:
        severity = AlertSeverity.CRITICAL
    elif days_until_stockout <= 2:
        severity = AlertSeverity.HIGH
    elif days_until_stockout <= 3:
        severity = AlertSeverity.MEDIUM
    else:
        return None  # No alert needed
    
    return await create_alert(
        customer_id=inventory.customer_id,
        store_id=store_id,
        product_id=product_id,
        alert_type=AlertType.STOCKOUT_PREDICTED,
        severity=severity,
        message=f"Stockout predicted in {days_until_stockout:.1f} days",
        metadata={
            "current_stock": inventory.quantity_on_hand,
            "daily_demand": daily_demand,
            "days_until_stockout": days_until_stockout,
            "reorder_point": reorder_point,
        },
    )
```

### 4. Email Delivery (SendGrid)

```python
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

async def send_alert_email(customer_id: str, alert: dict):
    recipients = await get_alert_recipients(customer_id)
    
    message = Mail(
        from_email="alerts@shelfops.com",
        to_emails=recipients,
        subject=f"[ShelfOps] {alert['severity'].upper()}: {alert['message']}",
        html_content=render_alert_email_template(alert),
    )
    
    sg = SendGridAPIClient(os.getenv("SENDGRID_API_KEY"))
    await sg.send(message)
```

### 5. Alert Deduplication

```python
async def create_alert_deduplicated(alert_data: dict):
    """Prevent duplicate alerts for same store/product/type"""
    
    existing = await db.execute(
        select(Alert).where(
            Alert.store_id == alert_data["store_id"],
            Alert.product_id == alert_data["product_id"],
            Alert.alert_type == alert_data["alert_type"],
            Alert.status == "open",
        )
    )
    
    if existing.scalar_one_or_none():
        # Update existing alert instead of creating duplicate
        await update_alert(existing.id, message=alert_data["message"])
        return existing
    
    return await create_alert(**alert_data)
```

---

## DO / DON'T

### DO
- ✅ Deduplicate alerts (same store/product/type = update, not new)
- ✅ Use severity levels (critical gets email, low just dashboard)
- ✅ Log all alerts to database (for analytics/audit)
- ✅ Include actionable metadata (current stock, demand, recommendation)
- ✅ Respond to webhooks quickly, process alerts async

### DON'T
- ❌ Send emails for every alert (alert fatigue)
- ❌ Skip deduplication (floods dashboard)
- ❌ Block on email sends (use background tasks)
- ❌ Ignore alert acknowledgment (track human responses)

---

**Last Updated**: 2026-02-09
