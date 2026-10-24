# ForkFinder

A Cubbie Skill that tells ASU students which dishes at the Tempe dining halls fit their own diet today.

Built for Track 1 of the Cubbie Hackathon.

## The problem

Hundreds of dishes across the dining halls, and the menu doesn't tell you what fits your diet. Being Jain, vegan, allergic to sesame or just hating mushrooms means scrolling ingredient lists at 12:15.

## What it does

- Learns your diet once, in your own words, and remembers it
- Fetches any meal's menu for the six Tempe dining halls (breakfast, brunch, lunch, light lunch, dinner, snacks, overnight), with every dish's ingredients, allergens and nutrition
- Optional nutrition: show calories and protein next to each pick, or keep it off (the default). Goals like high protein or under 600 calories work either way
- Cubbie reads each ingredient list against your diet, including hidden things like chicken stock, fish sauce, gelatin or egg wash
- Texts the best picks per hall, plus which halls have nothing for you and what to double-check
- Sends the full list as a PDF on request
- Offers daily check-ins before the meals you pick

## Example

```text
You: I'm vegetarian and allergic to nuts. What can I eat for lunch on Monday?

Cubbie: Got it: vegetarian, and allergic to nuts. Right?

You: yes

Cubbie: Checking the dining halls

Cubbie: Monday lunch, vegetarian and nut-free:
- Hassayampa: Asian Seared Tofu, Jasmine Rice, Quinoa Lentil Blend
- Tooker House: Grilled Black Bean Burger, Refried Beans, Roasted Cauliflower
- Barrett: Vegetable Soup with Brown Rice, Quinoa Lentil Blend, Roasted Butternut Squash
Skip: Kung Pao Cauliflower (peanuts) and the Caesar Pasta Salad at HIDA (anchovies)
Double-check: cheese pizzas (the cheese source isn't specified)

I go by the ingredients listed on the menu, so check with dining staff for allergies.
```

## Install on Cubbie

Text Cubbie the link to this repository. Cubbie says what it's about to fetch and asks first. Reply "yes", then try "what can I eat at the dining halls today".

## What you need

Cubbie. No Canvas, no account, no key.

## How it works

```text
forkfinder/
  SKILL.md            how Cubbie learns your diet, reads the menus and replies
  scripts/menu.py     fetches menus with ingredients, caches them, prints them one hall and page at a time
  assets/halls.json   Tempe halls and their menu url keys
  assets/meals.json   known meal period IDs; more are looked up from the menu service
  assets/sample.json  sample menus so the script runs offline
```

The script only fetches. Cubbie does all the judging, so any diet you can describe works. Your diet lives in Cubbie's memory. The script caches each day's menu in `~/.config/forkfinder/cache/` in your own Cubbie sandbox. Output is paged under 7,000 characters, because Cubbie reads the first 8,000 characters of a command's output.

Try it offline:

```bash
python3 scripts/menu.py --sample --date 2026-10-24
python3 scripts/menu.py --sample --date 2026-10-24 --hall hassayampa --page 1
python3 scripts/menu.py --list-halls
python3 scripts/menu.py --list-meals
```

Exit codes: 0 ok, 2 usage problem (`UNKNOWN_MEAL`, `MEALS_NOT_FOUND`, `NO_SUCH_HALL`, `AMBIGUOUS_HALL`, `BAD_PAGE`, `HALL_NOT_FOUND`, `BAD_DATE`), 3 menu couldn't be reached.

## Scope and limits

- Tempe campus only. Cubbie can add a Tempe hall it finds on the dining site
- Picks are judged from the ingredients the menu lists. It can miss things and isn't an allergy guarantee. If you have an allergy, check with dining staff
- Halal and kosher meat can't be judged from ingredients. Nutrition numbers are per the serving the menu lists
- The menu data comes from ASU's public dining menu service, which isn't an official API, so it may change

## Meals

Each meal has a numeric ID in the menu service. `assets/meals.json` holds all 11 meal periods the service listed on 2026-10-24 (breakfast 10, brunch 13, lunch 25, light lunch 88, dinner 16 and the snack periods). `python3 scripts/menu.py --discover-meals` asks the menu service for its meal list and saves it under `~/.config/forkfinder/meals.json`, so new meals like brunch or late night work without a code change.

If discovery fails, find an ID by hand. Open https://asu.mydininghub.com in a desktop browser with the network tab open, switch to the meal, and read the `mealPeriod` value in the `getLocationRecipes` request. Then add it to `assets/meals.json`, for example `{"lunch": 25, "dinner": 26}`.

## Team

**Midnight Merge**

- Karthik Reddy Yalala
- Arun Teja Reddy Kallam
- Venkat Preetam Pulla
- Ritvik Reddy Gangula
- Chinmay Vasisht Naganand
