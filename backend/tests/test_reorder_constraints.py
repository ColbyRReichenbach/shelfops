import pytest
from unittest.mock import AsyncMock, patch
from alerts.engine import detect_reorder_needed
import uuid

@pytest.mark.asyncio
async def test_detect_reorder_needed_constraints():
    """Test that detect_reorder_needed respects case_pack_size and moq rounding."""
    customer_id = uuid.uuid4()
    store_id = uuid.uuid4()
    product_id = uuid.uuid4()
    
    # Mocks
    class MockRP:
        def __init__(self):
            self.customer_id = customer_id
            self.store_id = store_id
            self.product_id = product_id
            self.reorder_point = 10
            self.safety_stock = 5
            self.economic_order_qty = 15

    class MockInv:
        def __init__(self):
            self.store_id = store_id
            self.product_id = product_id
            self.quantity_available = 4
    
    class MockProduct:
        def __init__(self):
            self.name = "Test Product"
            self.moq = 50
            self.case_pack_size = 12

    class MockResult:
        def __init__(self, data):
            self._data = data
        def scalars(self):
            class MockScalars:
                def __init__(self, d):
                    self.d = d
                def all(self):
                    return self.d
            return MockScalars(self._data)

    db = AsyncMock()
    
    # Setup execute side effects
    db.execute.side_effect = [
        MockResult([MockRP()]), # reorder points
        MockResult([MockInv()]) # inventories (subquery skipped by mocking the whole chain or we just mock the result)
    ]
    
    db.get.return_value = MockProduct()

    with patch("alerts.engine.is_product_active_in_store", new_callable=AsyncMock) as mock_active:
        mock_active.return_value = True
        
        alerts = await detect_reorder_needed(db, customer_id)
        
        assert len(alerts) == 1
        alert = alerts[0]
        # economic_order_qty is 15.
        # MOQ is 50. Max(15, 50) = 50.
        # Pack size is 12. Ceil(50 / 12) * 12 = 5 * 12 = 60.
        assert alert["metadata"]["suggested_qty"] == 60
        assert "Suggested order qty: 60" in alert["message"]
