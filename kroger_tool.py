#!/usr/bin/env python3
"""
Kroger grocery tool - search products, find stores, add to cart.
Usage:
  python3 kroger_tool.py stores [--zip <zip>] [--set-default N]
  python3 kroger_tool.py search <term> [--store <location_id>] [--limit N]
  python3 kroger_tool.py cart <item1> <item2> ... [--store <location_id>] [--dry-run]
  python3 kroger_tool.py history
  python3 kroger_tool.py remove <product_id>
"""
import os
import sys
import json
import argparse
import warnings
from datetime import datetime
warnings.filterwarnings("ignore")

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

from kroger_api import KrogerAPI
from kroger_api.token_storage import load_token

DEFAULT_ZIP = os.environ.get("KROGER_USER_ZIP_CODE", "85718")
DEFAULT_STORE_FILE = os.path.join(os.path.dirname(__file__), ".default_store")
USER_TOKEN_FILE = ".kroger_token_user.json"
HISTORY_FILE = os.path.join(os.path.dirname(__file__), "grocery_list.json")


# ── History helpers ─────────────────────────────────────────────────────────

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE) as f:
            return json.load(f)
    return {}

def save_history(data):
    with open(HISTORY_FILE, "w") as f:
        json.dump(data, f, indent=2)

def record_items(items):
    """items: list of {upc, description, price}"""
    history = load_history()
    for item in items:
        upc = item["upc"]
        if upc in history:
            history[upc]["count"] += 1
            history[upc]["last_added"] = datetime.now().isoformat()
        else:
            history[upc] = {
                "upc": upc,
                "description": item.get("description", ""),
                "price": item.get("price"),
                "count": 1,
                "first_added": datetime.now().isoformat(),
                "last_added": datetime.now().isoformat(),
            }
    save_history(history)


# ── API helpers ──────────────────────────────────────────────────────────────

def get_search_client():
    client = KrogerAPI()
    client.authorization.get_token_with_client_credentials("product.compact")
    return client

def get_cart_client():
    client = KrogerAPI()
    user_token = load_token(USER_TOKEN_FILE)
    if not user_token:
        print("❌ Not authenticated. Run: python3 auth_cart.py")
        sys.exit(1)
    client.client.token_info = user_token
    client.client.token_file = USER_TOKEN_FILE
    return client

def get_default_store():
    if os.path.exists(DEFAULT_STORE_FILE):
        with open(DEFAULT_STORE_FILE) as f:
            return f.read().strip()
    return None

def set_default_store(location_id, name=""):
    with open(DEFAULT_STORE_FILE, "w") as f:
        f.write(location_id)
    print(f"✅ Default store set to: {name or location_id}")

def nearest_store(client, zip_code=None):
    locs = client.location.search_locations(zip_code=zip_code or DEFAULT_ZIP, radius_in_miles=10, limit=1)
    stores = locs.get("data", [])
    return stores[0]["locationId"] if stores else None


# ── Commands ─────────────────────────────────────────────────────────────────

def cmd_stores(args):
    client = get_search_client()
    zip_code = args.zip or DEFAULT_ZIP
    locations = client.location.search_locations(zip_code=zip_code, radius_in_miles=args.radius or 10, limit=10)
    stores = locations.get("data", [])
    if not stores:
        print("No stores found.")
        return
    default = get_default_store()
    print(f"Stores near {zip_code}:")
    for i, s in enumerate(stores):
        addr = s.get("address", {})
        marker = " ← default" if s["locationId"] == default else ""
        print(f"  {i+1}. [{s['locationId']}] {s['name']} — {addr.get('addressLine1','')}, {addr.get('city','')} {addr.get('zipCode','')}{marker}")
    if args.set_default:
        idx = int(args.set_default) - 1
        if 0 <= idx < len(stores):
            set_default_store(stores[idx]["locationId"], stores[idx]["name"])

def cmd_search(args):
    client = get_search_client()
    store_id = args.store or get_default_store() or nearest_store(client)
    products = client.product.search_products(term=args.term, location_id=store_id, limit=args.limit or 10)
    items = products.get("data", [])
    if not items:
        print(f"No results for '{args.term}'")
        return
    print(f"Results for '{args.term}':")
    for p in items:
        prod_id = p.get("productId", "?")
        desc = p.get("description", "?")
        brand = p.get("brand", "")
        item0 = p.get("items", [{}])[0] if p.get("items") else {}
        size = item0.get("size", "")
        price = item0.get("price", {})
        regular = price.get("regular")
        promo = price.get("promo")
        price_str = f"${regular:.2f}" if regular else "price N/A"
        if promo and promo != regular:
            price_str += f" (sale: ${promo:.2f})"
        brand_str = f" [{brand}]" if brand else ""
        size_str = f" {size}" if size else ""
        print(f"  {prod_id}  {desc}{brand_str}{size_str}  {price_str}")

def cmd_cart(args):
    search_client = get_search_client()
    store_id = args.store or get_default_store() or nearest_store(search_client)

    found = []       # for cart API
    to_record = []   # for history
    missing = []
    total = 0.0

    print(f"Finding {len(args.items)} items at store {store_id}...\n")
    for item_name in args.items:
        products = search_client.product.search_products(term=item_name, location_id=store_id, limit=1)
        data = products.get("data", [])
        if data:
            p = data[0]
            prod_id = p.get("productId", "")
            desc = p.get("description", "?")
            item0 = p.get("items", [{}])[0] if p.get("items") else {}
            price = item0.get("price", {}).get("regular")
            price_str = f"${price:.2f}" if price else "?"
            if price:
                total += price
            print(f"  ✓  {item_name!r} → {desc}  {price_str}")
            found.append({"upc": prod_id, "quantity": 1, "modality": "PICKUP"})
            to_record.append({"upc": prod_id, "description": desc, "price": price})
        else:
            print(f"  ✗  {item_name!r} → not found")
            missing.append(item_name)

    print(f"\n{len(found)} found, {len(missing)} not found  |  est. total: ${total:.2f}")
    if missing:
        print(f"Not found: {', '.join(missing)}")

    if args.dry_run:
        print("\n[dry run] Not adding to cart.")
        return

    if not found:
        print("Nothing to add.")
        return

    cart_client = get_cart_client()
    cart_client.cart.add_to_cart(found)
    record_items(to_record)
    print(f"\n✅ {len(found)} items added to your Fry's cart!")

def cmd_history(args):
    history = load_history()
    if not history:
        print("No history yet.")
        return
    # Sort by count desc, then last_added desc
    items = sorted(history.values(), key=lambda x: (-x["count"], x["last_added"]), reverse=False)
    print(f"{'#':<4} {'Times':>5}  {'Last Added':<12}  Description")
    print("-" * 70)
    for i, item in enumerate(items, 1):
        last = item["last_added"][:10]
        count = item["count"]
        desc = item["description"]
        price = f"  ${item['price']:.2f}" if item.get("price") else ""
        print(f"  {i:<3} {count:>5}x  {last}  {desc}{price}")

def cmd_remove(args):
    history = load_history()
    if args.product_id in history:
        desc = history[args.product_id]["description"]
        del history[args.product_id]
        save_history(history)
        print(f"✅ Removed '{desc}' from history.")
    else:
        # Try matching by description substring
        matches = [(k, v) for k, v in history.items() if args.product_id.lower() in v["description"].lower()]
        if len(matches) == 1:
            k, v = matches[0]
            del history[k]
            save_history(history)
            print(f"✅ Removed '{v['description']}' from history.")
        elif len(matches) > 1:
            print("Multiple matches — be more specific or use the product ID:")
            for k, v in matches:
                print(f"  {k}  {v['description']}")
        else:
            print(f"Not found: {args.product_id}")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Kroger/Fry's grocery tool")
    sub = parser.add_subparsers(dest="cmd")

    p_stores = sub.add_parser("stores", help="Find nearby stores")
    p_stores.add_argument("--zip")
    p_stores.add_argument("--radius", type=float)
    p_stores.add_argument("--set-default", metavar="N")

    p_search = sub.add_parser("search", help="Search products")
    p_search.add_argument("term")
    p_search.add_argument("--store")
    p_search.add_argument("--limit", type=int, default=10)

    p_cart = sub.add_parser("cart", help="Add grocery list to cart")
    p_cart.add_argument("items", nargs="+")
    p_cart.add_argument("--store")
    p_cart.add_argument("--dry-run", action="store_true")

    sub.add_parser("history", help="Show all previously ordered items")

    p_remove = sub.add_parser("remove", help="Remove item from history by product ID or name")
    p_remove.add_argument("product_id", help="Product ID or name substring")

    args = parser.parse_args()
    if args.cmd == "stores":        cmd_stores(args)
    elif args.cmd == "search":      cmd_search(args)
    elif args.cmd == "cart":        cmd_cart(args)
    elif args.cmd == "history":     cmd_history(args)
    elif args.cmd == "remove":      cmd_remove(args)
    else:                           parser.print_help()

if __name__ == "__main__":
    main()
