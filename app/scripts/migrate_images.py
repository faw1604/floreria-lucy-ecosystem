"""
Scrape Kyte catalog → download images → upload to Cloudinary → update BD.

Usage:
    python -m app.scripts.migrate_images

Required env vars:
    DATABASE_URL, CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET
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
    """Use Playwright to scrape product names and image URLs from Kyte catalog."""
    from playwright.sync_api import sync_playwright

    all_products = []
    seen_names = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        # Load main page
        print("Cargando catalogo Kyte...")
        page.goto(KYTE_URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(10000)

        # Get category URLs
        categories = page.evaluate('''() => {
            const results = [];
            const seen = new Set();
            document.querySelectorAll('a[href*="/es/c/"]').forEach(a => {
                if (!seen.has(a.href)) {
                    seen.add(a.href);
                    results.push(a.href);
                }
            });
            return results;
        }''')
        print(f"Encontradas {len(categories)} categorias")

        # Scrape each category
        for i, cat_url in enumerate(categories):
            cat_name = cat_url.split("/c/")[1].split("/")[0] if "/c/" in cat_url else "unknown"
            print(f"  [{i+1}/{len(categories)}] {cat_name}...", end=" ")

            try:
                page.goto(cat_url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(5000)

                # Scroll to load all products
                for _ in range(5):
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    page.wait_for_timeout(1000)

                # Extract products: find links with images
                products = page.evaluate('''() => {
                    const results = [];
                    const links = document.querySelectorAll('a[href*="/es/p/"]');
                    links.forEach(a => {
                        const img = a.querySelector('img');
                        // Get the product name - try multiple selectors
                        let name = '';
                        const nameEl = a.querySelector('h2, h3, [class*="name"], [class*="title"]');
                        if (nameEl) name = nameEl.textContent.trim();
                        if (!name && img && img.alt) name = img.alt;

                        if (img && name && img.src) {
                            results.push({
                                name: name,
                                img: img.src,
                                href: a.href
                            });
                        }
                    });
                    return results;
                }''')

                count = 0
                for prod in products:
                    name = prod["name"].strip()
                    if name and name not in seen_names and not re.match(r'^-?\d+%$', name) and name not in ("opciones",):
                        seen_names.add(name)
                        all_products.append({
                            "name": name,
                            "img_url": prod["img"],
                            "href": prod["href"],
                            "category": cat_name,
                        })
                        count += 1
                print(f"{count} productos")

            except Exception as e:
                print(f"ERROR: {e}")
                continue

        browser.close()

    print(f"\nTotal productos scraped: {len(all_products)}")
    return all_products


def normalize(text: str) -> str:
    """Normalize text for fuzzy matching."""
    text = text.lower().strip()
    # Remove accents
    replacements = {
        "á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u",
        "ñ": "n", "ü": "u",
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    # Remove extra whitespace and punctuation
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text


def fuzzy_match(kyte_name: str, db_products: list[dict], threshold: float = 0.6) -> dict | None:
    """Find best matching product in DB by name."""
    kyte_norm = normalize(kyte_name)
    best_match = None
    best_score = 0

    for prod in db_products:
        db_norm = normalize(prod["nombre"])
        score = SequenceMatcher(None, kyte_norm, db_norm).ratio()

        # Bonus for exact substring match
        if kyte_norm in db_norm or db_norm in kyte_norm:
            score = max(score, 0.85)

        if score > best_score:
            best_score = score
            best_match = prod

    if best_score >= threshold:
        return {**best_match, "_match_score": best_score}
    return None


def upload_to_cloudinary(img_url: str, public_id: str) -> str | None:
    """Download image and upload to Cloudinary. Returns Cloudinary URL."""
    import cloudinary
    import cloudinary.uploader
    import httpx

    cloudinary.config(
        cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
        api_key=os.getenv("CLOUDINARY_API_KEY"),
        api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    )

    try:
        # Upload directly from URL
        result = cloudinary.uploader.upload(
            img_url,
            public_id=public_id,
            folder="floreria-lucy",
            overwrite=True,
            resource_type="image",
        )
        return result.get("secure_url")
    except Exception as e:
        print(f"    Error Cloudinary: {e}")
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
    """Get all products from DB."""
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


async def main():
    # 1. Get DB products
    print("=== PASO 1: Cargando productos de la BD ===")
    db_products = await get_all_products_from_db()
    print(f"Productos en BD: {len(db_products)}")

    # 2. Scrape Kyte
    print("\n=== PASO 2: Scrapeando catalogo Kyte ===")
    kyte_products = scrape_kyte()

    # 3. Match and upload
    print("\n=== PASO 3: Match + Upload a Cloudinary ===")
    matched = 0
    uploaded = 0
    failed_match = []

    has_cloudinary = all([
        os.getenv("CLOUDINARY_CLOUD_NAME"),
        os.getenv("CLOUDINARY_API_KEY"),
        os.getenv("CLOUDINARY_API_SECRET"),
    ])

    if not has_cloudinary:
        print("WARNING: Cloudinary no configurado. Solo se hara match sin subir imagenes.")

    for i, kp in enumerate(kyte_products):
        match = fuzzy_match(kp["name"], db_products)

        if not match:
            failed_match.append({
                "kyte_name": kp["name"],
                "kyte_img": kp["img_url"],
                "kyte_category": kp["category"],
            })
            continue

        matched += 1
        codigo = match.get("codigo") or f"id-{match['id']}"
        public_id = re.sub(r"[^\w-]", "-", codigo.lower())

        print(f"  [{i+1}/{len(kyte_products)}] '{kp['name']}' -> '{match['nombre']}' (score: {match['_match_score']:.2f})", end="")

        if has_cloudinary:
            cloud_url = upload_to_cloudinary(kp["img_url"], public_id)
            if cloud_url:
                await update_db(match["id"], cloud_url)
                uploaded += 1
                print(f" -> uploaded")
            else:
                print(f" -> UPLOAD FAILED")
        else:
            print(f" -> (skip upload, no cloudinary)")

    # 4. Save log
    log_path = os.path.join(os.path.dirname(__file__), "..", "..", "migration_log.json")
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump({
            "total_kyte": len(kyte_products),
            "matched": matched,
            "uploaded": uploaded,
            "failed_match_count": len(failed_match),
            "failed_match": failed_match,
        }, f, ensure_ascii=False, indent=2)

    print(f"\n=== RESUMEN ===")
    print(f"Productos en Kyte:    {len(kyte_products)}")
    print(f"Matched con BD:       {matched}")
    print(f"Subidos a Cloudinary: {uploaded}")
    print(f"Sin match:            {len(failed_match)}")
    print(f"Log guardado en:      {log_path}")


if __name__ == "__main__":
    asyncio.run(main())
