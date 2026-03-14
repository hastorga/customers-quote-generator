import pytest
from quote_generator.services.supabase_service import SupabaseService
from quote_generator.core.models import ClientInfo, QuoteItem

def test_supabase_service_mock_data():
    service = SupabaseService()
    
    # Check client basic fetch
    client = service.get_client_info("test_id")
    assert isinstance(client, ClientInfo)
    assert client.contact_name == "JUAN MANUEL AREVALO"
    
    # Check item details fetch
    item = service.build_quote_item(
        client_id="test_id", 
        cylinder_type="Aluminum VM gas load", 
        quantity=10, 
        description="Deliver"
    )
    assert isinstance(item, QuoteItem)
    assert item.name == "Aluminum VM gas load"
    assert item.quantity == 10
    assert item.unit_price_with_tax == 34450
    assert item.discount_percent == 20.0
