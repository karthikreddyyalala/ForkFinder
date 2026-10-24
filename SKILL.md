---
name: forkfinder
description: "Texts a student which dishes at ASU Tempe dining halls fit their own diet today, judged from the real ingredient lists on the menus. Any diet works: vegetarian, vegan, Jain, no beef, no onion or garlic, allergies, or foods they just don't like. Any meal works too: breakfast, brunch, lunch, light lunch, dinner, snacks. Can also pick by calories or protein. Use when a student asks 'what can I eat at the dining halls', 'what's for dinner', 'anything vegan at Barrett for breakfast', or wants to set or change their diet. Offers optional daily check-ins before their meals."
---

# ForkFinder

Dining hall menus are long and don't say what fits a student's diet. This skill learns the student's diet once, in their own words. Each time, a script fetches the Tempe dining hall menus for the meal they ask about with every dish's ingredient list, and Cubbie reads them and picks what fits.

The script only fetches. All judging is Cubbie's job, so read carefully.

Setup: none. The script uses Python 3 and its standard library, and needs no key or sign-in. Run every command from this skill's folder.

## 1. Learn the diet

Check Cubbie's memory for the student's dining diet. If there isn't one, ask in one open question: "What do you eat and not eat? Any allergies? Say it however you like, like 'Jain', 'vegetarian but eggs only in baked stuff', 'no beef', 'allergic to sesame'."

Ask one short follow-up at a time, only for what's unclear. For example, ask whether egg is ok, only baked in, or never. Or ask whether they skip onion and garlic too.

Then text back a one-line summary in plain words for them to confirm, like: "Got it: vegetarian, eggs only baked into bread or cake, no mushrooms, allergic to sesame. Right?"

After the yes, save the diet to memory exactly as confirmed. Also save their usual halls and favorite foods if they mention them.

Then ask once: "Want calories and protein next to each pick? Default is no." Save the answer to memory as their nutrition setting, on or off. They can change it any time ("show calories", "hide nutrition"). Update memory and confirm in one line: "Nutrition on." or "Nutrition off."

If they listed allergies, add once: "I go by the ingredients listed on the menu, so check with dining staff for allergies."

Goals like high protein, under 600 calories or low sodium work too, from the menu's nutrition numbers, so save those in the diet if they mention them. Whether meat is halal or kosher can't be judged from ingredients, so say that plainly. For halal, offer to skip pork, alcohol and gelatin, and mention that the meat itself isn't verified halal.

To change the diet later, update memory and confirm the new summary.

## 2. Pick the meal

Use the meal the student names, in any wording. The menu service has breakfast, brunch, lunch, light lunch, limited dinner, dinner, morning, afternoon and evening snack, overnight and all day. Map other words yourself: supper is dinner, and late night is overnight. If they don't name one ("what can I eat?"), pick the next meal by their local time and say which in the reply. Before 10:30 am that's breakfast, or brunch on weekends. Before 2 pm it's lunch, and after that it's dinner. For "tomorrow" or a weekday, use that date.

`python3 scripts/menu.py --list-meals` shows the meals the script knows. If a meal is missing, run `python3 scripts/menu.py --discover-meals` once. It asks the menu service for its full meal list and saves it.

## 3. Fetch the menus

Do this as a background task. Text first: "Checking the dining halls ⏳"

1. Run `python3 scripts/menu.py --date <YYYY-MM-DD> --meal "<meal>"`. If the student has usual halls, add `--halls "barrett,tooker"`. If they ask about one hall, use that one.
2. The output lists each hall with its dish count and number of pages, or says it failed or has no menu.
3. For each hall with dishes, read every page: `python3 scripts/menu.py --date <date> --meal "<meal>" --hall "<name>" --page <n>`. When the output ends with `MORE:`, read the next page too.

Each dish shows its name, station, ingredients, allergen statement and, when the menu has it, nutrition per serving (calories, protein, carbs, fat, fiber, sugar, sodium). If the student's nutrition setting is off and they have no nutrition goal, add `--no-nutrition` to every command so the pages stay shorter. The script caches the menu, so reading pages doesn't fetch again. Add `--refresh` only if the student says the menu changed.

Exit codes:
- 0: continue.
- 2 `UNKNOWN_MEAL`: map the word to a known meal and retry. If the service may have added a new meal, run `--discover-meals` once, then try again. If it's still unknown, or discovery fails, text the meals it does know: "I can check <the known meals>. Which one?"
- 2 `NO_SUCH_HALL`: see section 6.
- A hall that says "no <meal> menu posted" doesn't serve that meal that day, so list it under "No <meal> menu".
- 3 with every hall failed: "I couldn't reach the dining menus right now. Try again in a few minutes."
- 3 for one hall: list it as "couldn't load" and carry on with the rest.

## 4. Judge each dish

Go through every dish in every page against the saved diet. Put each dish in one of three buckets.

- Fits: nothing in its ingredients or allergen statement breaks the diet.
- Doesn't fit: an ingredient clearly breaks it.
- Double-check: you can't tell, and say why in a few words.

How to judge:
- Read the ingredient list and the allergen statement, not just the name. "Veggie" in a name doesn't make a dish vegetarian, and "Impossible Burger" isn't beef.
- Look for hidden sources: chicken or beef stock or broth, fish sauce, Worcestershire, anchovy, gelatin, lard, bacon bits, wine or other alcohol, egg wash, mayo, whey or casein, ghee, honey. Also look for a sub-ingredient in brackets, like "pesto (basil, parmesan, pine nuts)".
- For allergies, be strict. If the allergen statement or any ingredient mentions it, it doesn't fit. If the ingredients say NOT LISTED, the dish goes in double-check, never fits.
- For diets that are about how something is prepared, like "egg only when baked in", decide from the ingredients. If it's unclear, use double-check.
- When unsure, use double-check. A dish wrongly marked as fitting is worse than one left out.
- Skip drinks, condiments, plain sides like ice or salt, and items that are only ingredients for build-your-own stations.
- For nutrition goals, use the numbers shown, which are per the serving listed. A dish with no nutrition line can't count toward a goal, so mention that instead of guessing.
- Never invent dishes, ingredients or nutrition. Never call anything "safe".

## 5. Reply

Rank the dishes that fit: favorite foods first, then the student's nutrition goal if they have one (most protein first, for example), then full meals (a main dish or a curry, pasta or bowl) before sides and desserts. Then text, here with nutrition off:

```
Lunch today, Jain:
- Barrett: Masoor Dal, Coconut Curry Tofu, Vegan Burrito Bowl
- Tooker House: Jeera Rice, Pasta Primavera, Almond Milk Oatmeal
- Hassayampa: Cheese Pizza, Peanut Noodles
Nothing fits at HIDA
Couldn't load Manzanita
Double-check: Garden Salad at Hassayampa (no ingredients listed)
```

- At most 3 dishes per hall, with "(+N more)" for the rest.
- Nutrition setting on: add calories and protein after each dish, like "Masoor Dal (240 cal, 14g protein)". Off: show names only, even when a nutrition goal was used for ranking.
- If they ask about one dish's nutrition, answer with the full numbers and the serving size, whatever the setting.
- At most 5 halls, best options first.
- Keep the "Nothing fits", "Couldn't load", "No <meal> menu" and "Double-check" lines short. Leave out any that don't apply.

If the student wants the full list, or more than 5 halls have options, make a one-page PDF of everything that fits, grouped by hall and station, plus the double-check list. End it with "Based on the ingredients listed on the dining menu. Check with dining staff for allergies." Send it with a one-line text.

If they ask why a dish was left out, or about one dish, answer from its ingredient list.

## 6. Halls

`python3 scripts/menu.py --list-halls` shows the known Tempe halls.

If the student names a Tempe hall that isn't listed:
1. Open https://asu.mydininghub.com in the browser.
2. Go to the Tempe campus and open that hall's menu page.
3. Take the url key from the end of the page address, like `barrett-dining-center`.
4. Run `python3 scripts/menu.py --add-hall "Hall Name=url-key"`.

The script checks the key before saving, and `HALL_NOT_FOUND` means it isn't a Tempe location there. To drop a hall: `--remove-hall "name"`. The skill only covers the Tempe campus.

## 7. Daily check-ins

After the first good result, offer once: "Want this every day before lunch, say 10:30 am?" Students can have one check-in per meal they care about, like breakfast at 7:30 am and dinner at 4:30 pm. Create each only after a yes, at their time, in their time zone (Phoenix unless they say otherwise).

Word each task so it makes sense later, naming the meal: "Run the forkfinder skill for today's <meal>: read the student's saved dining diet from memory, fetch and read every hall's <meal> menu pages with scripts/menu.py, judge each dish against the diet as the skill says, and text the student the short picks list. If no hall has a <meal> menu today, send nothing. If menus can't be loaded, text one short line saying so."

If they ask to stop, cancel that meal's check-in, or all of them if they say so, and reply "Daily menu off. Text me anytime for today's picks."

## Limits

Say these when they matter:
- Tempe campus only. Meals are the ones the dining menu service lists.
- Picks are judged from the ingredients the dining menu lists. That can miss things, and it isn't an allergy guarantee.
- The menu comes from ASU's public dining menu service, which isn't an official API, so it can change.
- Nutrition numbers are per the serving the menu lists, not per plate.

## Replies

Short, plain text, no headings, bold, tables or code blocks. Lead with what's on the menu. Put links on their own line. Ask one question at a time and suggest a default the student can say "yes" to. Sound like a friend texting, not a report.
