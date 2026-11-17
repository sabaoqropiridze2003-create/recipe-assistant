"""Recipe catalog for the Recipe Assistant.

Each ingredient is a tuple: (name, quantity, unit) or (name, quantity, unit, True) for staples.
Staples (salt, pepper, oil, water) are ignored by the pantry match score.
Allergens are NOT written here: seed_recipes.py computes them from the ingredient names.
Ingredient names are in English so safety checks and pantry matching stay consistent.
"""

RECIPES = [
    # ------------------------------------------------------------------ Georgian
    dict(
        title="Lobio (Georgian Red Bean Stew)",
        description="ლობიო: a hearty Georgian stew of red beans, onion, garlic, herbs and crushed walnuts.",
        cuisine="georgian", meal_type="dinner", servings=4, total_time_min=45,
        diet_tags=["vegan", "gluten_free"],
        ingredients=[
            ("red kidney beans", 800, "g"), ("onion", 2, "pcs"), ("garlic", 4, "cloves"),
            ("walnuts", 60, "g"), ("fresh cilantro", 30, "g"), ("utskho suneli", 1, "tsp"),
            ("vegetable oil", 2, "tbsp", True), ("salt", 1, "tsp", True),
        ],
        steps=[
            "Fry the chopped onion in oil until golden.",
            "Add the beans, crushed garlic, ground walnuts and utskho suneli, and simmer for 20 minutes.",
            "Mash a few beans to thicken the stew, stir in the cilantro and serve warm.",
        ],
    ),
    dict(
        title="Spinach Pkhali",
        description="ფხალი: a Georgian cold appetizer of spinach and walnut paste with garlic and pomegranate seeds.",
        cuisine="georgian", meal_type="snack", servings=4, total_time_min=30,
        diet_tags=["vegan", "gluten_free"],
        ingredients=[
            ("spinach", 500, "g"), ("walnuts", 100, "g"), ("garlic", 2, "cloves"),
            ("fresh cilantro", 20, "g"), ("wine vinegar", 1, "tbsp"),
            ("pomegranate seeds", 40, "g"), ("salt", 1, "tsp", True),
        ],
        steps=[
            "Blanch the spinach for 2 minutes, squeeze out all the water and chop finely.",
            "Grind the walnuts with garlic, cilantro, vinegar and salt into a paste.",
            "Mix with the spinach, shape into small balls and top with pomegranate seeds.",
        ],
    ),
    dict(
        title="Ajapsandali (Georgian Vegetable Stew)",
        description="აჯაფსანდალი: a summer stew of eggplant, tomatoes, peppers and potatoes with fresh herbs.",
        cuisine="georgian", meal_type="dinner", servings=4, total_time_min=50,
        diet_tags=["vegan", "gluten_free"],
        ingredients=[
            ("eggplant", 2, "pcs"), ("tomatoes", 4, "pcs"), ("bell pepper", 2, "pcs"),
            ("potatoes", 2, "pcs"), ("onion", 1, "pcs"), ("garlic", 3, "cloves"),
            ("fresh basil", 15, "g"), ("fresh cilantro", 15, "g"),
            ("vegetable oil", 3, "tbsp", True), ("salt", 1, "tsp", True),
        ],
        steps=[
            "Cube the eggplant and potatoes and fry them separately until lightly browned.",
            "Fry the onion and peppers, add chopped tomatoes and garlic, and cook for 10 minutes.",
            "Combine everything, simmer for 15 minutes and finish with fresh herbs.",
        ],
    ),
    dict(
        title="Khachapuri Imeruli (Cheese Bread)",
        description="ხაჭაპური: round Georgian bread filled with melted sulguni cheese.",
        cuisine="georgian", meal_type="dinner", servings=4, total_time_min=75,
        diet_tags=["vegetarian"],
        ingredients=[
            ("wheat flour", 400, "g"), ("matsoni yogurt", 150, "ml"), ("dry yeast", 1, "tsp"),
            ("sulguni cheese", 400, "g"), ("egg", 1, "pcs"), ("butter", 30, "g"),
            ("salt", 1, "tsp", True),
        ],
        steps=[
            "Mix flour, yogurt, yeast and salt into a soft dough and let it rest for 40 minutes.",
            "Fill rounds of dough with grated cheese mixed with the egg, then seal and flatten.",
            "Bake at 220 C for 15 minutes and brush with melted butter.",
        ],
    ),
    dict(
        title="Khinkali (Georgian Dumplings)",
        description="ხინკალი: juicy Georgian dumplings filled with spiced meat and broth.",
        cuisine="georgian", meal_type="dinner", servings=4, total_time_min=90,
        diet_tags=[],
        ingredients=[
            ("wheat flour", 500, "g"), ("ground beef", 250, "g"), ("ground pork", 250, "g"),
            ("onion", 2, "pcs"), ("fresh cilantro", 30, "g"), ("ground cumin", 1, "tsp"),
            ("black pepper", 1, "tsp", True), ("water", 250, "ml", True), ("salt", 2, "tsp", True),
        ],
        steps=[
            "Knead flour, water and salt into a firm dough and rest it for 30 minutes.",
            "Mix the meat with onion, cilantro, cumin, pepper and some cold water.",
            "Wrap spoonfuls of filling in dough rounds with pleats on top and boil for 12 minutes.",
        ],
    ),
    dict(
        title="Chakhokhbili (Georgian Chicken Stew)",
        description="ჩახოხბილი: chicken slowly stewed with tomatoes, onion and plenty of fresh herbs.",
        cuisine="georgian", meal_type="dinner", servings=4, total_time_min=55,
        diet_tags=["gluten_free"],
        ingredients=[
            ("chicken thighs", 800, "g"), ("tomatoes", 5, "pcs"), ("onion", 2, "pcs"),
            ("garlic", 4, "cloves"), ("fresh cilantro", 30, "g"), ("fresh basil", 20, "g"),
            ("chili pepper", 1, "pcs"), ("vegetable oil", 2, "tbsp", True), ("salt", 1, "tsp", True),
        ],
        steps=[
            "Brown the chicken pieces in oil without extra liquid.",
            "Add sliced onion and grated tomatoes, cover and simmer for 35 minutes.",
            "Stir in garlic, chili and chopped herbs and cook for 5 more minutes.",
        ],
    ),
    dict(
        title="Satsivi (Chicken in Walnut Sauce)",
        description="საცივი: cold-served chicken in a rich walnut and spice sauce, a Georgian festive classic.",
        cuisine="georgian", meal_type="dinner", servings=6, total_time_min=75,
        diet_tags=["gluten_free"],
        ingredients=[
            ("chicken thighs", 1000, "g"), ("walnuts", 300, "g"), ("onion", 2, "pcs"),
            ("garlic", 4, "cloves"), ("coriander seeds", 1, "tsp"), ("ground cinnamon", 1, "tsp"),
            ("wine vinegar", 2, "tbsp"), ("salt", 1, "tsp", True),
        ],
        steps=[
            "Boil the chicken until tender and keep the broth.",
            "Grind walnuts with garlic and spices, then fry the onion and mix both with hot broth.",
            "Simmer the sauce for 15 minutes, add vinegar and pour over the chicken.",
        ],
    ),
    dict(
        title="Badrijani Nigvzit (Eggplant Walnut Rolls)",
        description="ბადრიჯანი ნიგვზით: fried eggplant slices rolled around a garlicky walnut filling.",
        cuisine="georgian", meal_type="lunch", servings=4, total_time_min=40,
        diet_tags=["vegan", "gluten_free"],
        ingredients=[
            ("eggplant", 3, "pcs"), ("walnuts", 150, "g"), ("garlic", 3, "cloves"),
            ("wine vinegar", 1, "tbsp"), ("ground coriander", 1, "tsp"),
            ("pomegranate seeds", 40, "g"), ("vegetable oil", 4, "tbsp", True),
            ("salt", 1, "tsp", True),
        ],
        steps=[
            "Slice the eggplant lengthwise and fry the slices until soft and golden.",
            "Grind walnuts with garlic, vinegar, coriander and salt into a thick paste.",
            "Spread paste on each slice, roll up and decorate with pomegranate seeds.",
        ],
    ),
    dict(
        title="Mchadi (Georgian Cornbread)",
        description="მჭადი: simple pan-fried Georgian cornbread, naturally gluten-free.",
        cuisine="georgian", meal_type="breakfast", servings=4, total_time_min=25,
        diet_tags=["vegan", "gluten_free"],
        ingredients=[
            ("cornmeal", 300, "g"), ("warm water", 250, "ml", True),
            ("vegetable oil", 2, "tbsp", True), ("salt", 1, "tsp", True),
        ],
        steps=[
            "Mix cornmeal, salt and warm water into a thick, smooth dough.",
            "Shape into small flat patties.",
            "Fry in oil for 4 minutes on each side until crisp and golden.",
        ],
    ),
    dict(
        title="Gozinaki (Walnut Honey Brittle)",
        description="გოზინაყი: a traditional Georgian sweet made of toasted walnuts bound with honey.",
        cuisine="georgian", meal_type="dessert", servings=8, total_time_min=30,
        diet_tags=["vegetarian", "gluten_free"],
        ingredients=[("walnuts", 300, "g"), ("honey", 200, "g"), ("sugar", 2, "tbsp")],
        steps=[
            "Toast the chopped walnuts in a dry pan for 5 minutes.",
            "Heat honey with sugar until it thickens, then stir in the walnuts.",
            "Press the mixture onto a wet board, cut into diamonds and let it set.",
        ],
    ),
    dict(
        title="Mtsvadi (Georgian Pork Skewers)",
        description="მწვადი: grilled pork skewers marinated with onion, served with pomegranate juice.",
        cuisine="georgian", meal_type="dinner", servings=4, total_time_min=60,
        diet_tags=["gluten_free"],
        ingredients=[
            ("pork shoulder", 1000, "g"), ("onion", 3, "pcs"), ("pomegranate juice", 100, "ml"),
            ("black pepper", 1, "tsp", True), ("salt", 2, "tsp", True),
        ],
        steps=[
            "Cut the pork into large cubes and marinate with sliced onion, salt and pepper.",
            "Thread onto skewers and grill over high heat for 20 minutes, turning often.",
            "Serve sprinkled with pomegranate juice.",
        ],
    ),

    # ------------------------------------------------------------------ International: dinner
    dict(
        title="Chicken, Rice and Broccoli Bowl",
        description="A quick, dairy-free weeknight bowl with seared chicken, fluffy rice and garlicky broccoli.",
        cuisine="asian", meal_type="dinner", servings=2, total_time_min=30,
        diet_tags=["gluten_free"],
        ingredients=[
            ("chicken breast", 300, "g"), ("rice", 150, "g"), ("broccoli", 250, "g"),
            ("garlic", 2, "cloves"), ("fresh ginger", 10, "g"), ("lemon juice", 1, "tbsp"),
            ("olive oil", 1, "tbsp", True), ("salt", 1, "tsp", True),
        ],
        steps=[
            "Cook the rice according to the package.",
            "Sear the sliced chicken in oil with ginger and garlic for 8 minutes.",
            "Steam the broccoli for 4 minutes, then combine everything and finish with lemon juice.",
        ],
    ),
    dict(
        title="Spaghetti Aglio e Olio",
        description="Classic Italian spaghetti with garlic, olive oil, chili and parsley.",
        cuisine="italian", meal_type="dinner", servings=2, total_time_min=20,
        diet_tags=["vegan"],
        ingredients=[
            ("spaghetti", 200, "g"), ("garlic", 4, "cloves"), ("chili flakes", 1, "tsp"),
            ("fresh parsley", 20, "g"), ("olive oil", 4, "tbsp", True), ("salt", 1, "tsp", True),
        ],
        steps=[
            "Boil the spaghetti in salted water until al dente and save a cup of pasta water.",
            "Gently fry sliced garlic and chili in olive oil until fragrant.",
            "Toss the pasta in the pan with a splash of pasta water and the parsley.",
        ],
    ),
    dict(
        title="Chickpea Curry (Chana Masala)",
        description="A fragrant Indian-style curry of chickpeas simmered in a spiced tomato and coconut sauce.",
        cuisine="indian", meal_type="dinner", servings=4, total_time_min=35,
        diet_tags=["vegan", "gluten_free"],
        ingredients=[
            ("chickpeas", 800, "g"), ("tomatoes", 400, "g"), ("onion", 1, "pcs"),
            ("garlic", 3, "cloves"), ("fresh ginger", 15, "g"), ("curry powder", 2, "tbsp"),
            ("coconut milk", 200, "ml"), ("fresh cilantro", 15, "g"),
            ("vegetable oil", 2, "tbsp", True), ("salt", 1, "tsp", True),
        ],
        steps=[
            "Fry onion, garlic and ginger in oil, then stir in the curry powder for 1 minute.",
            "Add tomatoes, chickpeas and coconut milk and simmer for 20 minutes.",
            "Season with salt and serve topped with cilantro.",
        ],
    ),
    dict(
        title="Grilled Salmon with Lemon and Asparagus",
        description="Pan-grilled salmon fillets with garlic, lemon and tender asparagus.",
        cuisine="mediterranean", meal_type="dinner", servings=2, total_time_min=25,
        diet_tags=["gluten_free"],
        ingredients=[
            ("salmon fillet", 300, "g"), ("asparagus", 250, "g"), ("lemon", 1, "pcs"),
            ("garlic", 2, "cloves"), ("olive oil", 2, "tbsp", True), ("salt", 1, "tsp", True),
        ],
        steps=[
            "Season the salmon with salt, garlic and lemon zest.",
            "Grill the fillets for 4 minutes on each side.",
            "Saute the asparagus in olive oil for 5 minutes and serve with lemon wedges.",
        ],
    ),
    dict(
        title="Garlic Shrimp and Rice",
        description="Quick stir-fried shrimp with bell pepper and ginger, served over rice.",
        cuisine="asian", meal_type="dinner", servings=2, total_time_min=25,
        diet_tags=["gluten_free"],
        ingredients=[
            ("shrimp", 300, "g"), ("rice", 150, "g"), ("garlic", 3, "cloves"),
            ("bell pepper", 1, "pcs"), ("fresh ginger", 10, "g"), ("sesame oil", 1, "tbsp"),
            ("green onion", 2, "pcs"), ("salt", 1, "tsp", True),
        ],
        steps=[
            "Cook the rice.",
            "Stir-fry garlic, ginger and sliced pepper in sesame oil for 3 minutes.",
            "Add the shrimp and cook until pink, then serve over rice with green onion.",
        ],
    ),
    dict(
        title="Beef Tacos",
        description="Soft tortillas filled with spiced ground beef, tomato, lettuce and cheese.",
        cuisine="mexican", meal_type="dinner", servings=4, total_time_min=30,
        diet_tags=[],
        ingredients=[
            ("ground beef", 400, "g"), ("tortillas", 8, "pcs"), ("tomatoes", 2, "pcs"),
            ("onion", 1, "pcs"), ("lettuce", 100, "g"), ("cheddar cheese", 100, "g"),
            ("ground cumin", 1, "tsp"), ("paprika", 1, "tsp"), ("salt", 1, "tsp", True),
        ],
        steps=[
            "Brown the beef with chopped onion, cumin, paprika and salt.",
            "Warm the tortillas in a dry pan.",
            "Fill with beef, diced tomato, lettuce and grated cheese.",
        ],
    ),
    dict(
        title="Mushroom Risotto",
        description="Creamy Italian rice slowly cooked with mushrooms, parmesan and butter.",
        cuisine="italian", meal_type="dinner", servings=3, total_time_min=40,
        diet_tags=["vegetarian", "gluten_free"],
        ingredients=[
            ("arborio rice", 250, "g"), ("mushrooms", 300, "g"), ("onion", 1, "pcs"),
            ("garlic", 2, "cloves"), ("vegetable broth", 900, "ml"), ("parmesan cheese", 50, "g"),
            ("butter", 30, "g"), ("salt", 1, "tsp", True),
        ],
        steps=[
            "Saute onion, garlic and sliced mushrooms in butter.",
            "Add the rice and ladle in hot broth a little at a time for about 20 minutes.",
            "Stir in parmesan, season and serve immediately.",
        ],
    ),
    dict(
        title="Lemon Herb Baked Chicken with Potatoes",
        description="Oven-baked chicken thighs and potatoes with lemon, garlic and rosemary.",
        cuisine="mediterranean", meal_type="dinner", servings=4, total_time_min=60,
        diet_tags=["gluten_free"],
        ingredients=[
            ("chicken thighs", 800, "g"), ("potatoes", 600, "g"), ("garlic", 4, "cloves"),
            ("lemon", 1, "pcs"), ("fresh rosemary", 10, "g"), ("olive oil", 3, "tbsp", True),
            ("salt", 1, "tsp", True),
        ],
        steps=[
            "Toss chicken and quartered potatoes with oil, garlic, rosemary, lemon juice and salt.",
            "Spread in a baking tray.",
            "Bake at 200 C for 45 minutes until golden.",
        ],
    ),

    # ------------------------------------------------------------------ International: breakfast
    dict(
        title="Banana Oatmeal with Walnuts",
        description="Warm oatmeal cooked in milk and topped with banana, walnuts and cinnamon.",
        cuisine="american", meal_type="breakfast", servings=2, total_time_min=10,
        diet_tags=["vegetarian"],
        ingredients=[
            ("rolled oats", 100, "g"), ("milk", 400, "ml"), ("banana", 2, "pcs"),
            ("walnuts", 30, "g"), ("ground cinnamon", 1, "tsp"),
        ],
        steps=[
            "Simmer the oats in milk for 5 minutes, stirring.",
            "Pour into bowls.",
            "Top with sliced banana, chopped walnuts and cinnamon.",
        ],
    ),
    dict(
        title="Berry Coconut Smoothie Bowl",
        description="A thick, dairy-free smoothie bowl of berries, banana and coconut milk topped with seeds.",
        cuisine="international", meal_type="breakfast", servings=1, total_time_min=5,
        diet_tags=["vegan", "gluten_free"],
        ingredients=[
            ("frozen berries", 150, "g"), ("banana", 1, "pcs"), ("coconut milk", 100, "ml"),
            ("chia seeds", 1, "tbsp"), ("pumpkin seeds", 1, "tbsp"),
        ],
        steps=[
            "Blend berries, banana and coconut milk until thick and smooth.",
            "Pour into a bowl.",
            "Sprinkle with chia and pumpkin seeds.",
        ],
    ),
    dict(
        title="Shakshuka",
        description="Eggs poached in a spiced tomato and pepper sauce, popular across the Middle East.",
        cuisine="middle eastern", meal_type="breakfast", servings=2, total_time_min=30,
        diet_tags=["vegetarian", "gluten_free"],
        ingredients=[
            ("eggs", 4, "pcs"), ("tomatoes", 400, "g"), ("bell pepper", 1, "pcs"),
            ("onion", 1, "pcs"), ("garlic", 2, "cloves"), ("ground cumin", 1, "tsp"),
            ("paprika", 1, "tsp"), ("olive oil", 2, "tbsp", True), ("salt", 1, "tsp", True),
        ],
        steps=[
            "Saute onion and pepper in oil, then add garlic and spices.",
            "Add tomatoes and simmer for 10 minutes.",
            "Make wells in the sauce, crack in the eggs and cook covered for 6 minutes.",
        ],
    ),
    dict(
        title="Fluffy Pancakes",
        description="Classic American pancakes with a soft, fluffy center.",
        cuisine="american", meal_type="breakfast", servings=4, total_time_min=25,
        diet_tags=["vegetarian"],
        ingredients=[
            ("wheat flour", 250, "g"), ("milk", 300, "ml"), ("egg", 2, "pcs"),
            ("butter", 40, "g"), ("sugar", 2, "tbsp"), ("baking powder", 2, "tsp"),
        ],
        steps=[
            "Whisk flour, sugar and baking powder, then stir in milk, eggs and melted butter.",
            "Pour small rounds of batter into a hot pan.",
            "Cook until bubbles form, flip and cook until golden.",
        ],
    ),
    dict(
        title="Greek Yogurt Berry Parfait",
        description="Layers of Greek yogurt, berries, honey and crunchy walnuts.",
        cuisine="greek", meal_type="breakfast", servings=1, total_time_min=5,
        diet_tags=["vegetarian", "gluten_free"],
        ingredients=[
            ("greek yogurt", 200, "g"), ("mixed berries", 100, "g"), ("honey", 1, "tbsp"),
            ("walnuts", 20, "g"),
        ],
        steps=[
            "Spoon half the yogurt into a glass.",
            "Add berries and walnuts, then repeat the layers.",
            "Drizzle with honey.",
        ],
    ),
    dict(
        title="Spinach Tomato Omelette",
        description="A fluffy omelette with spinach, tomato and onion, ready in ten minutes.",
        cuisine="french", meal_type="breakfast", servings=1, total_time_min=10,
        diet_tags=["vegetarian", "gluten_free"],
        ingredients=[
            ("eggs", 3, "pcs"), ("spinach", 50, "g"), ("tomatoes", 1, "pcs"),
            ("onion", 0.5, "pcs"), ("olive oil", 1, "tbsp", True), ("salt", 0.5, "tsp", True),
        ],
        steps=[
            "Saute the onion and spinach in oil for 2 minutes.",
            "Pour in the beaten eggs and add diced tomato.",
            "Cook until set, fold and serve.",
        ],
    ),

    # ------------------------------------------------------------------ International: lunch / snack
    dict(
        title="Greek Salad",
        description="Tomatoes, cucumber, olives and feta with olive oil and oregano.",
        cuisine="greek", meal_type="lunch", servings=2, total_time_min=15,
        diet_tags=["vegetarian", "gluten_free"],
        ingredients=[
            ("tomatoes", 3, "pcs"), ("cucumber", 1, "pcs"), ("red onion", 0.5, "pcs"),
            ("kalamata olives", 60, "g"), ("feta cheese", 100, "g"), ("dried oregano", 1, "tsp"),
            ("olive oil", 2, "tbsp", True), ("salt", 0.5, "tsp", True),
        ],
        steps=[
            "Cut the tomatoes, cucumber and onion into chunks.",
            "Add olives and top with a slab of feta.",
            "Dress with olive oil, oregano and salt.",
        ],
    ),
    dict(
        title="Caprese Salad",
        description="Sliced tomato and fresh mozzarella layered with basil and balsamic.",
        cuisine="italian", meal_type="lunch", servings=2, total_time_min=10,
        diet_tags=["vegetarian", "gluten_free"],
        ingredients=[
            ("tomatoes", 3, "pcs"), ("mozzarella", 150, "g"), ("fresh basil", 15, "g"),
            ("balsamic vinegar", 1, "tbsp"), ("olive oil", 2, "tbsp", True),
        ],
        steps=[
            "Slice the tomatoes and mozzarella.",
            "Alternate them on a plate with basil leaves.",
            "Drizzle with olive oil and balsamic.",
        ],
    ),
    dict(
        title="Red Lentil Soup",
        description="A smooth, warming soup of red lentils, carrot and cumin with a squeeze of lemon.",
        cuisine="turkish", meal_type="lunch", servings=4, total_time_min=30,
        diet_tags=["vegan", "gluten_free"],
        ingredients=[
            ("red lentils", 200, "g"), ("carrot", 1, "pcs"), ("onion", 1, "pcs"),
            ("garlic", 2, "cloves"), ("ground cumin", 1, "tsp"), ("vegetable broth", 1000, "ml"),
            ("lemon juice", 2, "tbsp"), ("olive oil", 2, "tbsp", True), ("salt", 1, "tsp", True),
        ],
        steps=[
            "Saute onion, carrot and garlic in oil with the cumin.",
            "Add lentils and broth and simmer for 20 minutes.",
            "Blend until smooth and finish with lemon juice.",
        ],
    ),
    dict(
        title="Tomato Basil Soup",
        description="A simple vegan tomato soup with garlic and fresh basil.",
        cuisine="italian", meal_type="lunch", servings=4, total_time_min=30,
        diet_tags=["vegan", "gluten_free"],
        ingredients=[
            ("tomatoes", 800, "g"), ("onion", 1, "pcs"), ("garlic", 3, "cloves"),
            ("vegetable broth", 500, "ml"), ("fresh basil", 20, "g"),
            ("olive oil", 2, "tbsp", True), ("salt", 1, "tsp", True),
        ],
        steps=[
            "Saute onion and garlic in olive oil.",
            "Add chopped tomatoes and broth and simmer for 20 minutes.",
            "Add basil, blend until smooth and season.",
        ],
    ),
    dict(
        title="Chicken Caesar Salad",
        description="Grilled chicken on romaine with parmesan, croutons and a creamy anchovy dressing.",
        cuisine="american", meal_type="lunch", servings=2, total_time_min=20,
        diet_tags=[],
        ingredients=[
            ("chicken breast", 250, "g"), ("romaine lettuce", 200, "g"), ("parmesan cheese", 40, "g"),
            ("bread croutons", 60, "g"), ("mayonnaise", 3, "tbsp"), ("anchovy fillets", 4, "pcs"),
            ("lemon juice", 1, "tbsp"), ("garlic", 1, "cloves"),
        ],
        steps=[
            "Grill the chicken breast and slice it.",
            "Mash anchovies and garlic into the mayonnaise with lemon juice to make the dressing.",
            "Toss the lettuce with dressing and top with chicken, parmesan and croutons.",
        ],
    ),
    dict(
        title="Hummus with Vegetable Sticks",
        description="Smooth homemade chickpea hummus served with crunchy carrot and cucumber sticks.",
        cuisine="middle eastern", meal_type="snack", servings=4, total_time_min=10,
        diet_tags=["vegan", "gluten_free"],
        ingredients=[
            ("chickpeas", 400, "g"), ("tahini", 3, "tbsp"), ("lemon juice", 3, "tbsp"),
            ("garlic", 1, "cloves"), ("carrot", 2, "pcs"), ("cucumber", 1, "pcs"),
            ("olive oil", 2, "tbsp", True), ("salt", 0.5, "tsp", True),
        ],
        steps=[
            "Blend chickpeas, tahini, lemon juice, garlic, oil and salt until smooth.",
            "Cut the carrots and cucumber into sticks.",
            "Serve the hummus with the vegetable sticks.",
        ],
    ),

    # ------------------------------------------------------------------ International: dessert
    dict(
        title="Apple Crumble",
        description="Baked cinnamon apples under a buttery oat crumble.",
        cuisine="british", meal_type="dessert", servings=6, total_time_min=50,
        diet_tags=["vegetarian"],
        ingredients=[
            ("apples", 800, "g"), ("wheat flour", 120, "g"), ("butter", 100, "g"),
            ("rolled oats", 60, "g"), ("brown sugar", 80, "g"), ("ground cinnamon", 1, "tsp"),
        ],
        steps=[
            "Slice the apples and toss with cinnamon in a baking dish.",
            "Rub flour, butter, oats and sugar together into coarse crumbs.",
            "Cover the apples with the crumble and bake at 190 C for 35 minutes.",
        ],
    ),
    dict(
        title="Chocolate Avocado Mousse",
        description="A rich, dairy-free chocolate mousse made with ripe avocado and coconut milk.",
        cuisine="international", meal_type="dessert", servings=2, total_time_min=10,
        diet_tags=["vegan", "gluten_free"],
        ingredients=[
            ("avocado", 2, "pcs"), ("cocoa powder", 4, "tbsp"), ("maple syrup", 4, "tbsp"),
            ("coconut milk", 60, "ml"), ("vanilla extract", 1, "tsp"),
        ],
        steps=[
            "Scoop the avocado into a blender.",
            "Add cocoa, maple syrup, coconut milk and vanilla.",
            "Blend until silky and chill before serving.",
        ],
    ),
]
