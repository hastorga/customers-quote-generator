from quote_generator.utils.pricing import calculate_pricing

def test_calculate_pricing():
    # 34450 / 1.19 = 28949.5798
    # 28949.5798 * 0.8 = 23159.6638
    # 23159.6638 * 18 = 416873.94 -> rounded to 416874
    # 416874 * 0.19 = 79206.06 -> rounded to 79206
    # Total = 416874 + 79206 = 496080

    pricing = calculate_pricing(
        quantity=18,
        unit_price_with_tax=34450,
        discount_percent=20.0,
    )

    assert pricing.subtotal == 416874
    assert pricing.tax == 79206
    assert pricing.total == 496080
    
    # testing another basic math
    pricing2 = calculate_pricing(
        quantity=1,
        unit_price_with_tax=11900,
        discount_percent=0.0,
    )
    assert pricing2.subtotal == 10000
    assert pricing2.tax == 1900
    assert pricing2.total == 11900
