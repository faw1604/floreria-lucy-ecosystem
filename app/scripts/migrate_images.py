"""
Scrape Kyte catalog via API interception → upload to Cloudinary → update BD.

Usage:
    python -m app.scripts.migrate_images

Required env vars:
    DATABASE_URL
    CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET (optional - skip upload if missing)
"""
import asyncio
import json
import os
import re
import sys
from difflib import SequenceMatcher

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

KYTE_URL = "https://florerialucy.kyte.site/es"


def scrape_kyte() -> list[dict]:
    """Intercept Kyte public API responses via Playwright to get product data."""
    from playwright.sync_api import sync_playwright

    all_products = []
    seen_ids = set()

    def capture(response):
        try:
            if "kyte-query-public" not in response.url:
                return
            if "/api/product/" not in response.url:
                return
            data = response.json()
            products = []
            if isinstance(data, list):
                for cat in data:
                    products.extend(cat.get("products", []))
            elif isinstance(data, dict) and "products" in data:
                products = data.get("products", [])

            for p in products:
                pid = p.get("id", p.get("_id"))
                if pid and pid not in seen_ids:
                    seen_ids.add(pid)
                    # Use original image (not large_) for Firebase direct access
                    img = p.get("image") or p.get("imageLarge") or p.get("imageMedium", "")
                    # Build Firebase Storage URL (publicly accessible, unlike images-cdn.kyte.site)
                    if img and not img.startswith("http"):
                        img = "https://firebasestorage.googleapis.com/v0/b/kyte-7c484.appspot.com/o" + img
                    all_products.append({
                        "name": p.get("name", ""),
                        "code": p.get("code", ""),
                        "image": img,
                        "category": (p.get("category") or {}).get("name", ""),
                    })
        except Exception:
            pass

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.on("response", capture)

        print("Cargando catalogo Kyte...")
        page.goto(KYTE_URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(12000)
        print(f"  Despues de carga inicial: {len(all_products)} productos")

        # Scroll to trigger lazy loading of categories
        for i in range(30):
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(1500)

        print(f"  Despues de scroll: {len(all_products)} productos")

        # Click each category to load its products
        cat_links = page.query_selector_all('a[href*="/es/c/"]')
        unique_cats = []
        seen_hrefs = set()
        for link in cat_links:
            href = link.get_attribute("href") or ""
            if href and href not in seen_hrefs:
                seen_hrefs.add(href)
                unique_cats.append(link)

        print(f"  Navegando {len(unique_cats)} categorias...")
        for cat_link in unique_cats:
            try:
                cat_link.click()
                page.wait_for_timeout(3000)
                for _ in range(8):
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    page.wait_for_timeout(1000)
            except Exception:
                pass

        print(f"  Despues de categorias: {len(all_products)} productos")
        browser.close()

    print(f"Total productos del catalogo: {len(all_products)}")
    return all_products


def normalize(text: str) -> str:
    """Normalize text for fuzzy matching."""
    text = text.lower().strip()
    for k, v in {"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ñ": "n", "ü": "u"}.items():
        text = text.replace(k, v)
    text = re.sub(r"[^\w\s]", "", text)
    return re.sub(r"\s+", " ", text)


def match_products(kyte_products: list[dict], db_products: list[dict]) -> list[dict]:
    """Match Kyte products to DB products. Returns list of matches."""
    matches = []
    unmatched = []

    # First pass: exact code match
    db_by_code = {}
    for p in db_products:
        if p["codigo"]:
            db_by_code[p["codigo"].strip().upper()] = p

    matched_db_ids = set()
    for kp in kyte_products:
        code = kp["code"].strip().upper() if kp["code"] else ""
        if code and code in db_by_code:
            db_p = db_by_code[code]
            matched_db_ids.add(db_p["id"])
            matches.append({"kyte": kp, "db": db_p, "method": "code", "score": 1.0})
        else:
            unmatched.append(kp)

    # Second pass: fuzzy name match for remaining
    remaining_db = [p for p in db_products if p["id"] not in matched_db_ids]
    still_unmatched = []

    for kp in unmatched:
        kyte_norm = normalize(kp["name"])
        best_match = None
        best_score = 0

        for db_p in remaining_db:
            db_norm = normalize(db_p["nombre"])
            score = SequenceMatcher(None, kyte_norm, db_norm).ratio()
            if kyte_norm in db_norm or db_norm in kyte_norm:
                score = max(score, 0.85)
            if score > best_score:
                best_score = score
                best_match = db_p

        if best_score >= 0.6 and best_match:
            matched_db_ids.add(best_match["id"])
            remaining_db = [p for p in remaining_db if p["id"] != best_match["id"]]
            matches.append({"kyte": kp, "db": best_match, "method": "name", "score": best_score})
        else:
            still_unmatched.append(kp)

    return matches, still_unmatched


def upload_to_cloudinary(img_url: str, public_id: str) -> str | None:
    """Upload image to Cloudinary from URL."""
    import cloudinary
    import cloudinary.uploader

    cloudinary.config(
        cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
        api_key=os.getenv("CLOUDINARY_API_KEY"),
        api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    )

    try:
        result = cloudinary.uploader.upload(
            img_url,
            public_id=public_id,
            folder="floreria-lucy",
            overwrite=True,
            resource_type="image",
        )
        return result.get("secure_url")
    except Exception as e:
        print(f"    Cloudinary error: {e}")
        return None


async def update_db(producto_id: int, imagen_url: str):
    """Update imagen_url in DB."""
    from app.database import async_session
    from app.models.productos import Producto
    from sqlalchemy import select

    async with async_session() as session:
        result = await session.execute(select(Producto).where(Producto.id == producto_id))
        producto = result.scalar_one_or_none()
        if producto:
            producto.imagen_url = imagen_url
            await session.commit()


async def get_all_products_from_db() -> list[dict]:
    """Get all active products from DB."""
    from app.database import async_session, inicializar_db
    from app.models.productos import Producto
    from sqlalchemy import select

    await inicializar_db()
    async with async_session() as session:
        result = await session.execute(select(Producto).where(Producto.activo == True))
        productos = result.scalars().all()
        return [
            {"id": p.id, "codigo": p.codigo, "nombre": p.nombre, "categoria": p.categoria}
            for p in productos
        ]


async def async_steps(kyte_products: list[dict]):
    """DB matching and Cloudinary upload steps."""
    print("\n=== Cargando productos de la BD ===")
    db_products = await get_all_products_from_db()
    print(f"Productos en BD: {len(db_products)}")

    print("\n=== Matching productos ===")
    matches, unmatched = match_products(kyte_products, db_products)
    print(f"Matched: {len(matches)} (code: {sum(1 for m in matches if m['method']=='code')}, name: {sum(1 for m in matches if m['method']=='name')})")
    print(f"Sin match: {len(unmatched)}")

    # Upload to Cloudinary
    has_cloudinary = all([
        os.getenv("CLOUDINARY_CLOUD_NAME"),
        os.getenv("CLOUDINARY_API_KEY"),
        os.getenv("CLOUDINARY_API_SECRET"),
    ])

    uploaded = 0
    if not has_cloudinary:
        print("\nWARNING: Cloudinary no configurado. Solo se reporta el match.")
    else:
        print(f"\n=== Subiendo {len(matches)} imagenes a Cloudinary ===")

    for i, m in enumerate(matches):
        kp = m["kyte"]
        db_p = m["db"]
        codigo = db_p.get("codigo") or f"id-{db_p['id']}"
        public_id = re.sub(r"[^\w-]", "-", codigo.lower())

        print(f"  [{i+1}/{len(matches)}] [{m['method']}:{m['score']:.2f}] '{kp['name']}' -> '{db_p['nombre']}'", end="")

        if has_cloudinary and kp["image"]:
            cloud_url = upload_to_cloudinary(kp["image"], public_id)
            if cloud_url:
                await update_db(db_p["id"], cloud_url)
                uploaded += 1
                print(" -> OK")
            else:
                print(" -> FAIL")
        else:
            print("")

    # Save log
    log_path = os.path.join(os.path.dirname(__file__), "..", "..", "migration_log.json")
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump({
            "total_kyte": len(kyte_products),
            "matched": len(matches),
            "uploaded": uploaded,
            "failed_match_count": len(unmatched),
            "matches": [
                {"kyte": m["kyte"]["name"], "db": m["db"]["nombre"], "code": m["kyte"]["code"], "method": m["method"], "score": round(m["score"], 2)}
                for m in matches
            ],
            "failed_match": [
                {"kyte_name": u["name"], "kyte_code": u["code"], "kyte_img": u["image"][:100]}
                for u in unmatched
            ],
        }, f, ensure_ascii=False, indent=2)

    print(f"\n=== RESUMEN ===")
    print(f"Productos en Kyte:     {len(kyte_products)}")
    print(f"Matched con BD:        {len(matches)}")
    print(f"  - Por codigo:        {sum(1 for m in matches if m['method']=='code')}")
    print(f"  - Por nombre:        {sum(1 for m in matches if m['method']=='name')}")
    print(f"Subidos a Cloudinary:  {uploaded}")
    print(f"Sin match:             {len(unmatched)}")
    print(f"Log: {log_path}")


if __name__ == "__main__":
    # Playwright sync must run outside asyncio
    print("=== Scrapeando catalogo Kyte ===")
    kyte_products = scrape_kyte()

    # Async DB/Cloudinary steps
    asyncio.run(async_steps(kyte_products))
