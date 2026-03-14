from __future__ import annotations

from quote_generator.core.models import ClientInfo, QuoteItem

class SupabaseService:
    """Service to connect to Supabase for fetching info.
    Currently mocked until the real API endpoint is integrated.
    """

    def __init__(self, endpoint_url: str = "", api_key: str = "") -> None:
        self.endpoint_url = endpoint_url
        self.api_key = api_key

    def get_client_info(self, client_id: str) -> ClientInfo:
        """Fetch client information from Supabase."""
        # Mock logic
        return ClientInfo(
            contact_name="JUAN MANUEL AREVALO",
            company_name="INGREDION CHILE S.A.",
            tax_id="96.845.100-6",
            address="AVDA. CANAVERAL 240",
            city="SANTIAGO",
        )

    def get_cylinder_price(self, cylinder_type: str) -> float:
        """Fetch base price mapped by cylinder type layout."""
        # Mock logic
        return 34450.0

    def get_client_discount(self, client_id: str, cylinder_type: str) -> float:
        """Fetch discount % applied for a client/cylinder type."""
        # Mock logic
        return 20.0

    def build_quote_item(self, client_id: str, cylinder_type: str, quantity: int, description: str) -> QuoteItem:
        """Fetch data and build the quote item."""
        unit_price = self.get_cylinder_price(cylinder_type)
        discount = self.get_client_discount(client_id, cylinder_type)
        return QuoteItem(
            name=cylinder_type,
            quantity=quantity,
            description=description,
            unit_price_with_tax=int(unit_price),
            discount_percent=discount,
        )
