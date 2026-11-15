from io import BytesIO


def scan_barcode(image_bytes):
    try:
        import zxingcpp
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError('Barcode camera scanning needs zxing-cpp and Pillow') from exc
    with Image.open(BytesIO(image_bytes)) as image:
        image.load()
        if image.width * image.height > 12_000_000:
            raise ValueError('Image is too large for barcode scanning')
        results = zxingcpp.read_barcodes(image)
    codes = [row.text for row in results if row.text and row.text.isascii() and row.text.isdigit()]
    if not codes:
        return None
    if len(set(codes)) != 1:
        raise ValueError('Multiple product barcodes detected. Scan only one package')
    return codes[0]
