from backend import products


def test_generated_barcode_has_correct_format(conn):
    barcode = products.generate_local_barcode(conn)
    assert len(barcode) == 13
    assert barcode.startswith("9")
    assert barcode.isdigit()


def test_generated_barcodes_are_unique_and_increment(conn):
    b1 = products.generate_local_barcode(conn)
    b2 = products.generate_local_barcode(conn)
    b3 = products.generate_local_barcode(conn)
    assert len({b1, b2, b3}) == 3
    assert int(b1[1:]) < int(b2[1:]) < int(b3[1:])


def test_generated_barcode_never_collides_with_existing_product(conn):
    barcode = products.generate_local_barcode(conn)
    conn.execute(
        "INSERT INTO products (name, barcode, sale_price) VALUES ('x', ?, 100)", (barcode,)
    )
    next_barcode = products.generate_local_barcode(conn)
    assert next_barcode != barcode


def test_create_product_without_barcode_auto_generates(conn):
    result = products.create_product(
        conn,
        name="کاڵای نوێ",
        barcode=None,
        category=None,
        sale_price=1500,
        unit="دانە",
        min_stock=0,
        purchase_price=1000,
        quantity=10,
        expiry_date=None,
    )
    assert result["barcode"].startswith("9")
    assert len(result["barcode"]) == 13
    assert len(result["batches"]) == 1
    assert result["batches"][0]["quantity"] == 10


def test_scanning_existing_barcode_adds_new_batch_without_overwriting_price(conn):
    created = products.create_product(
        conn,
        name="کاڵا",
        barcode="123456789",
        category=None,
        sale_price=2000,
        unit="دانە",
        min_stock=0,
        purchase_price=1000,
        quantity=5,
        expiry_date=None,
    )
    product_id = created["id"]

    found = products.find_product_by_barcode(conn, "123456789")
    assert found is not None
    assert found["id"] == product_id

    updated = products.add_stock_batch(
        conn, product_id=product_id, purchase_price=1300, quantity=20, expiry_date="2027-01-01"
    )
    assert len(updated["batches"]) == 2
    prices = sorted(b["purchase_price"] for b in updated["batches"])
    assert prices == [1000, 1300]
