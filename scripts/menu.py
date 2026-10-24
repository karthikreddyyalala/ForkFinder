#!/usr/bin/env python3
import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

MESH_ID = "c087f756-cc72-4649-a36f-3a41b700c519"
GRAPHQL_URL = f"https://api.elevate-dxp.com/api/mesh/{MESH_ID}/graphql"
CAMPUS = "tempe-campus"

HEADERS = {
    "accept": "application/graphql-response+json,application/json;q=0.9",
    "aem-elevate-clientpath": "ch/asu/en",
    "content-type": "application/json",
    "magento-customer-group": "b6589fc6ab0dc82cf12099d1c2d40ab994e8410c",
    "magento-store-code": "ch_asu",
    "magento-store-view-code": "ch_asu_en",
    "magento-website-code": "ch_asu",
    "store": "ch_asu_en",
    "x-api-key": "ElevateAPIProd",
    "user-agent": "Mozilla/5.0",
}

RECIPES_QUERY = (
    "query getLocationRecipes($campusUrlKey:String!$locationUrlKey:String!"
    "$date:String!$mealPeriod:Int$viewType:Commerce_MenuViewType!)"
    "{getLocationRecipes(campusUrlKey:$campusUrlKey locationUrlKey:$locationUrlKey "
    "date:$date mealPeriod:$mealPeriod viewType:$viewType){"
    "locationRecipesMap{stationSkuMap{id skus __typename}__typename}"
    "products{items{id name sku attributes{name value __typename} __typename}__typename}"
    "__typename}}"
)

STATIONS_QUERY = (
    "query getLocation($campus_url_key:String!$location_url_key:String!)"
    "{getLocation(campusUrlKey:$campus_url_key locationUrlKey:$location_url_key)"
    "{commerceAttributes{children{id name position __typename}__typename}"
    "__typename}}"
)

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(SKILL_DIR, "assets")
CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".config", "forkfinder")
HALLS_PATH = os.path.join(CONFIG_DIR, "halls.json")
MEALS_PATH = os.path.join(CONFIG_DIR, "meals.json")
CACHE_DIR = os.path.join(CONFIG_DIR, "cache")
OTHER_STATION = "Other"
PAGE_CHARS = 7000
SHOW_NUTRITION = True


def graphql_get(query, operation_name, variables):
    params = {"query": query}
    if operation_name:
        params["operationName"] = operation_name
    if variables:
        params["variables"] = json.dumps(variables)
    url = GRAPHQL_URL + "?" + urllib.parse.urlencode(params)
    last_error = None
    for _ in range(2):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=20) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            if body.get("errors"):
                raise RuntimeError(f"GraphQL errors: {body['errors']}")
            return body.get("data", {})
        except Exception as exc:
            last_error = exc
    raise last_error


def fetch_stations(slug):
    data = graphql_get(STATIONS_QUERY, "getLocation", {"campus_url_key": CAMPUS, "location_url_key": slug})
    location = data.get("getLocation")
    if location is None:
        return None
    children = (location.get("commerceAttributes") or {}).get("children") or []
    return {c["id"]: {"name": c["name"], "position": c.get("position", 0)} for c in children}


TYPE_REF = "kind name ofType{kind name ofType{kind name ofType{kind name}}}"
ID_KEYS = ("id", "value", "mealPeriodId", "meal_period_id", "mealPeriod", "code")
NAME_KEYS = ("name", "label", "title", "displayName", "display_name", "mealPeriodName")


def unwrap(t):
    while t and t.get("ofType"):
        t = t["ofType"]
    return t or {}


def type_fields(type_name):
    q = "{__type(name:%s){fields{name args{name type{kind}} type{%s}}}}" % (json.dumps(type_name), TYPE_REF)
    return ((graphql_get(q, None, {}).get("__type") or {}).get("fields")) or []


def selection(type_name, depth):
    parts = []
    for f in type_fields(type_name):
        if any(a["type"]["kind"] == "NON_NULL" for a in f.get("args") or []):
            continue
        t = unwrap(f["type"])
        if t.get("kind") in ("SCALAR", "ENUM"):
            parts.append(f["name"])
        elif t.get("kind") == "OBJECT" and depth > 0:
            inner = selection(t["name"], depth - 1)
            if inner:
                parts.append(f"{f['name']}{{{inner}}}")
    return " ".join(parts)


def collect_meals(node, found):
    if isinstance(node, list):
        for n in node:
            collect_meals(n, found)
    elif isinstance(node, dict):
        ident = next((node[k] for k in ID_KEYS if k in node and str(node[k]).isdigit()), None)
        label = next((node[k] for k in NAME_KEYS if isinstance(node.get(k), str) and node[k].strip()), None)
        if ident is not None and label:
            found[normalize_meal(label)] = int(ident)
        for v in node.values():
            if isinstance(v, (dict, list)):
                collect_meals(v, found)


def discover_meals():
    fields = type_fields("Query")
    candidates = [f for f in fields if "mealperiod" in f["name"].lower().replace("_", "")]
    for f in candidates:
        if any(a["type"]["kind"] == "NON_NULL" for a in f.get("args") or []):
            continue
        t = unwrap(f["type"])
        sel = f["name"] if t.get("kind") in ("SCALAR", "ENUM") else f"{f['name']}{{{selection(t['name'], 3)}}}"
        found = {}
        collect_meals(graphql_get("{" + sel + "}", None, {}), found)
        if found:
            return found
    return {}


def normalize_meal(name):
    return " ".join(name.lower().replace("-", " ").replace("_", " ").split())


def load_meals():
    meals = {normalize_meal(k): v for k, v in read_json(os.path.join(ASSETS, "meals.json"), {}).items()}
    meals.update(read_json(MEALS_PATH, {}))
    return meals


def resolve_meal(meals, wanted):
    w = normalize_meal(wanted)
    if w in meals:
        return w
    close = [m for m in meals if w in m or m in w]
    return max(close, key=len) if len(close) == 1 else None


def fetch_raw(slug, date_str, period, sample_data):
    if sample_data is not None:
        hall = sample_data["halls"].get(slug, {})
        if hall.get("error"):
            raise RuntimeError("sample failure")
        stations = {
            sid: {"name": s["name"], "position": s.get("position", 0)}
            for sid, s in hall.get("stations", {}).items()
        }
        return hall.get("items", []), hall.get("stationSkuMap", []), stations
    variables = {
        "campusUrlKey": CAMPUS, "locationUrlKey": slug, "date": date_str,
        "mealPeriod": period, "viewType": "DAILY",
    }
    recipes = graphql_get(RECIPES_QUERY, "getLocationRecipes", variables).get("getLocationRecipes") or {}
    items = (recipes.get("products") or {}).get("items") or []
    station_map = (recipes.get("locationRecipesMap") or {}).get("stationSkuMap") or []
    try:
        stations = fetch_stations(slug) or {}
    except Exception:
        stations = {}
    return items, station_map, stations


def clean(value):
    return " ".join((value or "").split())


NUTRIENTS = [
    ("calories", "cal", ""), ("protein", "protein", "g"), ("total_carbohydrates", "carbs", "g"),
    ("total_fat", "fat", "g"), ("dietary_fiber", "fiber", "g"), ("sugars", "sugar", "g"),
    ("sodium", "sodium", "mg"),
]


def nutrition_text(attrs):
    parts = []
    for key, label, unit in NUTRIENTS:
        try:
            value = round(float(attrs.get(key)))
        except (TypeError, ValueError):
            continue
        parts.append(f"{value} {label}" if not unit else f"{value}{unit} {label}")
    if not parts:
        return ""
    serving = clean(attrs.get("serving_combined"))
    return (f"per {serving}: " if serving and serving != "N/A" else "") + ", ".join(parts)


def fetch_hall(name, slug, date_str, period, sample_data):
    try:
        items, station_map, stations = fetch_raw(slug, date_str, period, sample_data)
    except Exception:
        return {"name": name, "slug": slug, "status": "failed", "dishes": []}
    sku_to_station = {}
    for group in station_map:
        for sku in group.get("skus") or []:
            sku_to_station.setdefault(sku, group["id"])
    seen = set()
    dishes = []
    for item in items:
        attrs = {a["name"]: a["value"] for a in item.get("attributes", [])}
        if attrs.get("ingredient_item") == "yes" or attrs.get("is_hide_from_web_menu") == "yes":
            continue
        dish_name = clean(item.get("name"))
        if not dish_name or dish_name in seen:
            continue
        seen.add(dish_name)
        station = stations.get(sku_to_station.get(item.get("sku")))
        dishes.append({
            "name": dish_name,
            "station": station["name"] if station else OTHER_STATION,
            "position": station["position"] if station else 9999,
            "ingredients": clean(attrs.get("recipe_ingredients")),
            "allergens": clean(attrs.get("allergen_statement")),
            "description": clean(attrs.get("marketing_description")),
            "nutrition": nutrition_text(attrs),
        })
    dishes.sort(key=lambda d: d["position"])
    return {"name": name, "slug": slug, "status": "ok" if dishes else "no_menu", "dishes": dishes}


def dish_text(d):
    lines = [f"* {d['name']} [{d['station']}]"]
    lines.append(f"  ingredients: {d['ingredients'] or 'NOT LISTED'}")
    if d["allergens"] and d["allergens"].lower().strip(" :") != "contains":
        lines.append(f"  allergens: {d['allergens']}")
    if SHOW_NUTRITION and d.get("nutrition"):
        lines.append(f"  nutrition {d['nutrition']}")
    if d["description"] and not d["ingredients"]:
        lines.append(f"  description: {d['description']}")
    return "\n".join(lines)


def paginate(hall, page_chars):
    pages, current, size = [], [], 0
    for d in hall["dishes"]:
        block = dish_text(d)
        if current and size + len(block) + 1 > page_chars:
            pages.append(current)
            current, size = [], 0
        current.append(block[:page_chars])
        size += len(block) + 1
    if current:
        pages.append(current)
    return pages


def read_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)


def load_halls(sample):
    defaults = read_json(os.path.join(ASSETS, "halls.json"), [])
    return defaults if sample else read_json(HALLS_PATH, defaults)


def find_halls(halls, query):
    q = query.lower().strip()
    return [h for h in halls if q in h["name"].lower() or q in h["slug"]]


def fail(code, message):
    print(message)
    sys.exit(code)


def cache_path(date_str, meal, sample):
    return os.path.join(CACHE_DIR, f"{'sample-' if sample else ''}{date_str}-{meal.replace(' ', '-')}.json")


def get_menu(args, date_str, meal, period, halls):
    path = cache_path(date_str, meal, args.sample)
    cached = {} if args.refresh else read_json(path, {})
    cached_halls = cached.get("halls", {})
    sample_data = read_json(os.path.join(ASSETS, "sample.json"), None) if args.sample else None
    changed = False
    for h in halls:
        prev = cached_halls.get(h["slug"])
        if prev is None or prev["status"] == "failed":
            cached_halls[h["slug"]] = fetch_hall(h["name"], h["slug"], date_str, period, sample_data)
            changed = True
    if changed:
        write_json(path, {"date": date_str, "meal": meal, "halls": cached_halls})
    return [cached_halls[h["slug"]] for h in halls]


def cmd_add_hall(args):
    if "=" not in args.add_hall:
        fail(2, "BAD_HALL: use --add-hall \"Name=url-key\"")
    name, slug = (p.strip() for p in args.add_hall.split("=", 1))
    slug = slug.strip("/").split("/")[-1].lower()
    if not args.sample:
        try:
            found = fetch_stations(slug)
        except Exception:
            fail(3, "NETWORK: couldn't reach the dining menus to check this hall")
        if found is None:
            fail(2, f"HALL_NOT_FOUND: {slug} isn't a Tempe location on the dining menu")
    halls = [h for h in load_halls(args.sample) if h["slug"] != slug]
    halls.append({"name": name, "slug": slug})
    if not args.sample:
        write_json(HALLS_PATH, halls)
    print(f"Added: {name} ({slug}). Halls: " + ", ".join(h["name"] for h in halls))


def cmd_remove_hall(args):
    halls = load_halls(False)
    match = find_halls(halls, args.remove_hall)
    if not match:
        fail(2, "NO_SUCH_HALL: " + ", ".join(h["name"] for h in halls))
    write_json(HALLS_PATH, [h for h in halls if h not in match])
    print("Removed: " + ", ".join(h["name"] for h in match))


def main():
    parser = argparse.ArgumentParser(description="Fetch ASU Tempe dining hall menus with ingredients")
    parser.add_argument("--date")
    parser.add_argument("--meal", default="lunch")
    parser.add_argument("--meal-period", type=int)
    parser.add_argument("--halls", help="comma separated hall names; default all known Tempe halls")
    parser.add_argument("--hall", help="print one hall's dishes")
    parser.add_argument("--page", type=int, default=1)
    parser.add_argument("--page-chars", type=int, default=PAGE_CHARS)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--no-nutrition", action="store_true")
    parser.add_argument("--sample", action="store_true")
    parser.add_argument("--list-halls", action="store_true")
    parser.add_argument("--list-meals", action="store_true")
    parser.add_argument("--discover-meals", action="store_true")
    parser.add_argument("--add-hall")
    parser.add_argument("--remove-hall")
    args = parser.parse_args()
    global SHOW_NUTRITION
    SHOW_NUTRITION = not args.no_nutrition

    if args.list_halls:
        for h in load_halls(args.sample):
            print(f"{h['name']} = {h['slug']}")
        return
    if args.add_hall:
        return cmd_add_hall(args)
    if args.remove_hall:
        return cmd_remove_hall(args)

    if args.list_meals or args.discover_meals:
        if args.discover_meals:
            try:
                found = discover_meals()
            except Exception:
                fail(3, "NETWORK: couldn't reach the dining menu service to look up meals")
            if not found:
                fail(2, "MEALS_NOT_FOUND: the menu service didn't return a meal list; add IDs to assets/meals.json")
            write_json(MEALS_PATH, found)
            print("Saved meals from the menu service.")
        for name, ident in sorted(load_meals().items(), key=lambda kv: kv[1]):
            print(f"{name} = {ident}")
        return

    meals = load_meals()
    if args.meal_period:
        meal, period = normalize_meal(args.meal), args.meal_period
    else:
        meal = resolve_meal(meals, args.meal)
        if meal is None:
            fail(2, f"UNKNOWN_MEAL: {args.meal}. Known meals: {', '.join(sorted(meals))}. Run --discover-meals to look up the rest")
        period = meals[meal]

    if args.date:
        try:
            day = datetime.strptime(args.date, "%Y-%m-%d")
        except ValueError:
            fail(2, "BAD_DATE: use YYYY-MM-DD")
    else:
        day = datetime.now(timezone.utc) - timedelta(hours=7)
    date_str = day.strftime("%Y-%m-%d")

    known = load_halls(args.sample)
    names = args.hall or args.halls
    if names:
        halls = []
        for q in [q for q in names.split(",") if q.strip()]:
            match = find_halls(known, q)
            if not match:
                fail(2, f"NO_SUCH_HALL: {q.strip()}. Known halls: " + ", ".join(h["name"] for h in known))
            halls.extend(h for h in match if h not in halls)
    else:
        halls = known
    if args.hall and len(halls) != 1:
        fail(2, "AMBIGUOUS_HALL: " + ", ".join(h["name"] for h in halls))

    menu = get_menu(args, date_str, meal, period, halls)

    if args.hall:
        hall = menu[0]
        if hall["status"] == "failed":
            fail(3, f"FAILED: couldn't load {hall['name']}")
        if hall["status"] == "no_menu":
            print(f"{hall['name']}: no {meal} menu posted for {date_str}")
            return
        pages = paginate(hall, args.page_chars)
        if not 1 <= args.page <= len(pages):
            fail(2, f"BAD_PAGE: {hall['name']} has {len(pages)} page(s)")
        print(f"{hall['name']}, {meal} {date_str}, page {args.page} of {len(pages)}")
        print("\n".join(pages[args.page - 1]))
        if args.page < len(pages):
            print(f"MORE: run again with --hall \"{hall['name']}\" --page {args.page + 1}")
        return

    print(f"Tempe {meal} menus for {date_str}:")
    for hall in menu:
        if hall["status"] == "failed":
            print(f"- {hall['name']}: FAILED, couldn't load")
        elif hall["status"] == "no_menu":
            print(f"- {hall['name']}: no {meal} menu posted")
        else:
            pages = len(paginate(hall, args.page_chars))
            print(f"- {hall['name']}: {len(hall['dishes'])} dishes, {pages} page(s)")
    print("Read each hall with: python3 scripts/menu.py --date " + date_str + f" --meal {meal} --hall \"<name>\" --page 1")
    if all(h["status"] == "failed" for h in menu):
        sys.exit(3)


if __name__ == "__main__":
    main()
