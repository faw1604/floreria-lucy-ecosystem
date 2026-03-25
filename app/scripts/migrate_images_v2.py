"""
Migrate remaining product images from Kyte catalog using Playwright (visible browser).

Strategy: intercept Kyte API responses while clicking category links in-page.
This avoids Cloudflare blocks from direct URL navigation.

Usage:
    venv\\Scripts\\activate
    $env:PYTHONIOENCODING="utf-8"
    python -m app.scripts.migrate_images_v2

Required env vars:
    DATABASE_URL
    CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET
"""
import asyncio
import json
import os
import random
import re
import sys
import time
from difflib import SequenceMatcher

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

KYTE_URL = "https://florerialucy.kyte.site/es"


def normalize(text: str) -> str:
    text = text.lower().strip()
    for k, v in {"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ñ": "n", "ü": "u"}.items():
        text = text.replace(k, v)
    text = re.sub(r"[^\w\s]", "", text)
    return re.sub(r"\s+", " ", text)


def scrape_kyte() -> list[dict]:
    """Intercept Kyte API responses while clicking categories like a human."""
    from playwright.sync_api import sync_playwright

    all_products = []
    seen_ids = set()

    def extract_products_from_data(data):
        """Recursively extract products from any API response structure."""
        products = []
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    if "products" in item:
                        products.extend(item["products"])
                    elif "name" in item and ("image" in item or "imageLarge" in item):
                        products.append(item)
                    else:
                        products.extend(extract_products_from_data(list(item.values())))
        elif isinstance(data, dict):
            if "products" in data:
                products.extend(data["products"])
            if "name" in data and ("image" in data or "imageLarge" in data):
                products.append(data)
            for v in data.values():
                if isinstance(v, (list, dict)):
                    products.extend(extract_products_from_data(v))
        return products

    def capture(response):
        """Capture products from Kyte API responses (broad matching)."""
        try:
            url = response.url
            # Capture any Kyte API response that might contain products
            if "kyte" not in url and "firestore" not in url:
                return
            ct = response.headers.get("content-type", "")
            if "json" not in ct and "javascript" not in ct:
                return
            data = response.json()
            products = extract_products_from_data(data)

            for p in products:
                pid = p.get("id", p.get("_id"))
                name = p.get("name", "")
                if not name:
                    continue
                key = pid or normalize(name)
                if key in seen_ids:
                    continue
                seen_ids.add(key)
                img = p.get("image") or p.get("imageLarge") or p.get("imageMedium", "")
                if img and not img.startswith("http"):
                    img = "https://firebasestorage.googleapis.com/v0/b/kyte-7c484.appspot.com/o" + img
                if img:
                    all_products.append({
                        "name": name,
                        "code": p.get("code", ""),
                        "image": img,
                        "category": (p.get("category") or {}).get("name", ""),
                    })
        except Exception:
            pass

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False, slow_mo=300)
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        )
        page = context.new_page()
        page.on("response", capture)

        # Step 1: load main page
        print("Cargando pagina principal de Kyte...")
        page.goto(KYTE_URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(8000)
        print(f"  Despues de carga inicial: {len(all_products)} productos")

        # Step 2: scroll the main page to trigger lazy loads
        print("Scrolleando pagina principal...")
        for i in range(20):
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(random.randint(800, 1500))
        print(f"  Despues de scroll: {len(all_products)} productos")

        # Step 3: find and click category links (staying in-page to avoid Cloudflare)
        cat_links = page.query_selector_all('a[href*="/es/c/"]')
        unique_cats = []
        seen_hrefs = set()
        for link in cat_links:
            href = link.get_attribute("href") or ""
            if href and href not in seen_hrefs:
                seen_hrefs.add(href)
                unique_cats.append(href)

        print(f"\nEncontradas {len(unique_cats)} categorias. Navegando con clicks...")

        for ci, href in enumerate(unique_cats):
            try:
                print(f"  [{ci+1}/{len(unique_cats)}] {href.split('/es/c/')[-1].split('/')[0]}", end="")
                before = len(all_products)

                # Click the category link (find fresh reference to avoid stale element)
                link_el = page.query_selector(f'a[href="{href}"]')
                if link_el:
                    link_el.click()
                else:
                    # Fallback: navigate but with domcontentloaded
                    full_url = href if href.startswith("http") else f"https://florerialucy.kyte.site{href}"
                    page.goto(full_url, wait_until="domcontentloaded", timeout=20000)

                # Wait for API response to load products
                page.wait_for_timeout(random.randint(3000, 5000))

                # Scroll to trigger lazy loading within category
                for _ in range(random.randint(5, 10)):
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    page.wait_for_timeout(random.randint(600, 1200))

                new_count = len(all_products) - before
                print(f" -> +{new_count} (total: {len(all_products)})")

                # Random delay between categories to look human
                page.wait_for_timeout(random.randint(1000, 3000))

            except Exception as e:
                err_msg = str(e).split("\n")[0][:80]
                print(f" -> Error: {err_msg}")
                # If disconnected, wait longer and try to recover
                if "DISCONNECTED" in str(e).upper():
                    print("    Esperando 15s para recuperar conexion...")
                    page.wait_for_timeout(15000)
                    try:
                        page.goto(KYTE_URL, wait_until="domcontentloaded", timeout=30000)
                        page.wait_for_timeout(5000)
                    except Exception:
                        print("    No se pudo recuperar. Continuando con lo que hay.")
                        break

        print(f"\nDespues de categorias: {len(all_products)} productos")

        # Step 4: scroll back to top and try scrolling the whole page once more
        try:
            page.goto(KYTE_URL, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(5000)
            for i in range(10):
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(1000)
        except Exception:
            pass

        browser.close()

    print(f"\nTotal productos unicos extraidos de Kyte: {len(all_products)}")
    return all_products


def fuzzy_match(kyte_name: str, db_name: str) -> float:
    kn = normalize(kyte_name)
    dn = normalize(db_name)
    score = SequenceMatcher(None, kn, dn).ratio()
    if kn in dn or dn in kn:
        score = max(score, 0.85)
    return score


def upload_to_cloudinary(img_url: str, public_id: str) -> str | None:
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


async def run(kyte_products: list[dict]):
    from app.database import async_session, inicializar_db
    from app.models.productos import Producto
    from sqlalchemy import select

    if not kyte_products:
        print("No se encontraron productos en Kyte. Abortando.")
        return

    # Load DB products
    print("\n=== Cargando productos de la BD ===")
    await inicializar_db()
    async with async_session() as session:
        result = await session.execute(select(Producto).where(Producto.activo == True))
        db_productos = result.scalars().all()

    db_list = [{"id": p.id, "codigo": p.codigo, "nombre": p.nombre, "imagen_url": p.imagen_url} for p in db_productos]
    print(f"Productos en BD: {len(db_list)}")
    already_have_image = sum(1 for p in db_list if p["imagen_url"])
    print(f"  Ya tienen imagen: {already_have_image}")

    # Match: first by code, then fuzzy name
    print("\n=== Matching Kyte -> BD ===")
    matches = []
    no_match = []
    matched_db_ids = set()

    # Code match first
    db_by_code = {}
    for p in db_list:
        if p["codigo"]:
            db_by_code[p["codigo"].strip().upper()] = p

    unmatched_kyte = []
    for kp in kyte_products:
        code = kp.get("code", "").strip().upper()
        if code and code in db_by_code:
            db_p = db_by_code[code]
            if db_p["id"] not in matched_db_ids:
                matched_db_ids.add(db_p["id"])
                matches.append({"kyte": kp, "db": db_p, "score": 1.0, "method": "code"})
                continue
        unmatched_kyte.append(kp)

    # Fuzzy name match for the rest
    remaining_db = [p for p in db_list if p["id"] not in matched_db_ids]
    for kp in unmatched_kyte:
        best_db = None
        best_score = 0
        for db_p in remaining_db:
            score = fuzzy_match(kp["name"], db_p["nombre"])
            if score > best_score:
                best_score = score
                best_db = db_p
        if best_score >= 0.6 and best_db:
            matched_db_ids.add(best_db["id"])
            remaining_db = [p for p in remaining_db if p["id"] != best_db["id"]]
            matches.append({"kyte": kp, "db": best_db, "score": best_score, "method": "name"})
        else:
            no_match.append(kp)

    code_matches = sum(1 for m in matches if m["method"] == "code")
    name_matches = sum(1 for m in matches if m["method"] == "name")
    print(f"Matched: {len(matches)} (code: {code_matches}, name: {name_matches})")
    print(f"Sin match: {len(no_match)}")

    # Upload only those without imagen_url
    has_cloudinary = all([
        os.getenv("CLOUDINARY_CLOUD_NAME"),
        os.getenv("CLOUDINARY_API_KEY"),
        os.getenv("CLOUDINARY_API_SECRET"),
    ])

    if not has_cloudinary:
        print("\nERROR: Cloudinary no configurado.")
        return

    uploaded = 0
    skipped = 0
    failed = 0

    print(f"\n=== Subiendo imagenes nuevas a Cloudinary ===")
    for i, m in enumerate(matches):
        kp = m["kyte"]
        db_p = m["db"]
        tag = f"[{i+1}/{len(matches)}]"

        # Skip if already has image (don't overwrite the 47 already migrated)
        if db_p["imagen_url"]:
            skipped += 1
            continue

        codigo = db_p.get("codigo") or f"id-{db_p['id']}"
        public_id = re.sub(r"[^\w-]", "-", codigo.lower())

        print(f"  {tag} [{m['method']}:{m['score']:.2f}] '{kp['name']}' -> '{db_p['nombre']}'", end="")

        cloud_url = upload_to_cloudinary(kp["image"], public_id)
        if cloud_url:
            async with async_session() as session:
                result = await session.execute(select(Producto).where(Producto.id == db_p["id"]))
                producto = result.scalar_one_or_none()
                if producto:
                    producto.imagen_url = cloud_url
                    await session.commit()
            uploaded += 1
            print(" -> OK")
        else:
            failed += 1
            print(" -> FAIL")

    # Save log
    log_path = os.path.join(os.path.dirname(__file__), "..", "..", "migration_log_v2.json")
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump({
            "total_kyte": len(kyte_products),
            "matched": len(matches),
            "matched_by_code": code_matches,
            "matched_by_name": name_matches,
            "uploaded": uploaded,
            "skipped_already_have_image": skipped,
            "failed_upload": failed,
            "no_match_count": len(no_match),
            "no_match": [{"name": u["name"], "code": u.get("code", ""), "image": u.get("image", "")[:100]} for u in no_match],
        }, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*50}")
    print(f"=== RESUMEN MIGRACION V2 ===")
    print(f"{'='*50}")
    print(f"Productos en Kyte:          {len(kyte_products)}")
    print(f"Matched con BD:             {len(matches)}")
    print(f"  - Por codigo:             {code_matches}")
    print(f"  - Por nombre:             {name_matches}")
    print(f"Ya tenian imagen (skip):    {skipped}")
    print(f"Subidos a Cloudinary:       {uploaded}")
    print(f"Fallo subida:               {failed}")
    print(f"Sin match en BD:            {len(no_match)}")
    print(f"Log: {os.path.abspath(log_path)}")


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    # Playwright sync must run outside asyncio loop
    print("=" * 50)
    print("=== SCRAPING CATALOGO KYTE (Playwright visible) ===")
    print("=" * 50)
    kyte_products = scrape_kyte()

    if not kyte_products:
        print("No se encontraron productos en Kyte. Abortando.")
    else:
        asyncio.run(run(kyte_products))
