from quote_generator.utils.pricing import calculate_pricing, resolve_discounted_price


def test_calculate_pricing():
    # 34450 with 20% off is exactly 27560 per unit, tax included
    # 27560 * 18 = 496080
    # 496080 / 1.19 = 416873.95 -> rounded to 416874
    # 496080 - 416874 = 79206

    pricing = calculate_pricing(
        quantity=18,
        unit_price_with_tax=34450,
        discount_percent=0.20,
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


def test_resolve_discounted_price_drops_the_half_peso_like_sap():
    # Reported against SAP: CUERPO DE BOMBEROS DE LLAY LLAY, GAS45N.
    # 112550 * 0.73 = 82161.5 — SAP reads 82161, not 82162.
    assert resolve_discounted_price(112550, 0.27) == 82161
    assert resolve_discounted_price(113450, 0.27) == 82818
    assert resolve_discounted_price(108950, 0.27) == 79533
    assert resolve_discounted_price(29850, 0.27) == 21790


def test_resolve_discounted_price_leaves_exact_prices_untouched():
    assert resolve_discounted_price(36550, 0.38) == 22661
    assert resolve_discounted_price(38250, 0.38) == 23715
    assert resolve_discounted_price(112550, 0.0) == 112550


def test_resolve_discounted_price_rounds_nearest_off_the_multiple_of_50():
    # Nothing enforces the multiple of 50 at the write boundary, so other
    # fractions are reachable — they must round, not floor.
    assert resolve_discounted_price(10001, 0.10) == 9001  # 9000.9
    assert resolve_discounted_price(10001, 0.27) == 7301  # 7300.73
    assert resolve_discounted_price(10010, 0.25) == 7507  # 7507.5, a tie, goes down


def test_resolve_discounted_price_does_not_mis_round_on_floating_point():
    # 1000 * (1 - 0.07) is 929.9999999999999 in floating point.
    assert resolve_discounted_price(1000, 0.07) == 930
    assert resolve_discounted_price(1100, 0.31) == 759


def test_line_total_does_not_drift_with_quantity():
    # The tax-included line total must be the SAP unit price times the quantity,
    # with no drift from carrying an unrounded price into the multiplication.
    for quantity in (1, 2, 5, 10, 18, 100):
        pricing = calculate_pricing(quantity, 112550, 0.27)
        assert pricing.total == 82161 * quantity


def test_subtotal_and_tax_always_add_up_to_the_total():
    for price in range(10_000, 120_000, 50):
        for percent in range(0, 46):
            pricing = calculate_pricing(7, price, percent / 100)
            assert pricing.subtotal + pricing.tax == pricing.total


def test_matches_the_sales_app_rule_across_every_price_and_discount_in_use():
    def reference(list_price: int, percent: int) -> int:
        scaled = list_price * (100 - percent) * 100
        pesos, remainder = divmod(scaled, 10_000)
        return pesos + 1 if remainder * 2 > 10_000 else pesos

    mismatches = []
    for list_price in range(1_000, 60_001):
        for percent in range(0, 46):
            actual = resolve_discounted_price(list_price, percent / 100)
            expected = reference(list_price, percent)
            if actual != expected:
                mismatches.append(f"{list_price} @ {percent}%: {actual} != {expected}")
    assert mismatches == []
