import pytest
from sqlalchemy import delete, select

from app.db.models import ShoppingList, ShoppingListItem, User

pytestmark = pytest.mark.integration

RECIPE = {
    "title": "API Test Pudding",
    "description": "A recipe made by an automated test.",
    "cuisine": "test",
    "meal_type": "dessert",
    "servings": 2,
    "total_time_min": 15,
    "steps": ["Mix.", "Chill."],
    "diet_tags": [],
    "ingredients": [
        {"name": "butter", "quantity": 50, "unit": "g"},
        {"name": "sugar", "quantity": 20, "unit": "g"},
    ],
}


# ---- tests from the spec's list ----

async def test_user_cannot_read_others_chat(client, make_user):
    alice, bob = await make_user(), await make_user()
    created = await client.post("/chat/sessions", headers=alice["headers"])
    assert created.status_code == 201
    chat_id = created.json()["id"]

    assert (await client.get(f"/chat/sessions/{chat_id}/messages", headers=alice["headers"])).status_code == 200
    assert (await client.get(f"/chat/sessions/{chat_id}/messages", headers=bob["headers"])).status_code == 404
    assert (await client.delete(f"/chat/sessions/{chat_id}", headers=bob["headers"])).status_code == 404

    alice_chats = [s["id"] for s in (await client.get("/chat/sessions", headers=alice["headers"])).json()]
    bob_chats = [s["id"] for s in (await client.get("/chat/sessions", headers=bob["headers"])).json()]
    assert chat_id in alice_chats and chat_id not in bob_chats  


async def test_admin_only_recipe_crud(client, make_user, no_gemini, track_recipe):
    user, admin = await make_user("user"), await make_user("admin")

    assert (await client.post("/recipes", json=RECIPE)).status_code == 401  
    assert (await client.post("/recipes", json=RECIPE, headers=user["headers"])).status_code == 403

    created = await client.post("/recipes", json=RECIPE, headers=admin["headers"])
    assert created.status_code == 201
    recipe = created.json()
    track_recipe(recipe["id"])
    assert recipe["allergens"] == ["dairy"]  

    url = f"/recipes/{recipe['id']}"
    assert (await client.get(url, headers=user["headers"])).status_code == 200  
    assert (await client.put(url, json=RECIPE, headers=user["headers"])).status_code == 403
    assert (await client.delete(url, headers=user["headers"])).status_code == 403
    assert (await client.delete(url, headers=admin["headers"])).status_code == 204


# ---- extra tests: roles ----

async def test_a_wrong_diet_tag_is_refused_even_for_the_admin(client, make_user, no_gemini):
    admin = await make_user("admin")
    body = {**RECIPE, "diet_tags": ["vegan"]} 
    response = await client.post("/recipes", json=body, headers=admin["headers"])
    assert response.status_code == 422


async def test_analytics_is_admin_only_and_its_sql_runs(client, make_user):
    user, admin = await make_user("user"), await make_user("admin")
    for path in ("/analytics/popular-recipes", "/analytics/ai-generated", "/analytics/intents"):
        assert (await client.get(path, headers=user["headers"])).status_code == 403
        assert (await client.get(path)).status_code == 401
        assert (await client.get(path, headers=admin["headers"])).status_code == 200  


async def test_nobody_can_make_themselves_admin_through_register(client, maker):
    email = "test-escalation@example.com"
    try:
        response = await client.post(
            "/auth/register",
            json={"email": email, "full_name": "Mallory", "password": "password123", "role": "admin"},
        )
        assert response.status_code == 201
        assert response.json()["role"] == "user"
    finally:
        async with maker() as db:
            await db.execute(delete(User).where(User.email == email))
            await db.commit()


# ---- extra tests: login ----

async def test_register_login_me_and_the_password_is_never_returned(client, maker):
    email = "test-login-flow@example.com"
    try:
        registered = await client.post(
            "/auth/register", json={"email": email, "full_name": "Login Flow", "password": "password123"}
        )
        assert registered.status_code == 201 and "password" not in registered.text
        duplicate = await client.post(
            "/auth/register", json={"email": email.upper(), "full_name": "Again", "password": "password123"}
        )
        assert duplicate.status_code == 409  

        wrong = await client.post("/auth/login", data={"username": email, "password": "wrong-password"})
        assert wrong.status_code == 401
        login = await client.post("/auth/login", data={"username": email, "password": "password123"})
        assert login.status_code == 200
        me = await client.get("/auth/me", headers={"Authorization": f"Bearer {login.json()['access_token']}"})
        assert me.status_code == 200 and me.json()["email"] == email and "hashed_password" not in me.text
    finally:
        async with maker() as db:
            await db.execute(delete(User).where(User.email == email))
            await db.commit()


async def test_a_short_password_is_refused(client):
    response = await client.post(
        "/auth/register", json={"email": "test-short@example.com", "full_name": "Short", "password": "short"}
    )
    assert response.status_code == 422


# ---- extra tests: every user's data is private ----

async def test_pantry_is_private(client, make_user):
    alice, bob = await make_user(), await make_user()
    added = await client.post("/pantry", json={"name": "Rice", "quantity": 500, "unit": "g"}, headers=alice["headers"])
    assert added.status_code == 201
    item_id = added.json()["id"]

    assert (await client.get("/pantry", headers=bob["headers"])).json() == []
    assert (await client.put(f"/pantry/{item_id}", json={"quantity": 1}, headers=bob["headers"])).status_code == 404
    assert (await client.delete(f"/pantry/{item_id}", headers=bob["headers"])).status_code == 404
    assert len((await client.get("/pantry", headers=alice["headers"])).json()) == 1  


async def test_profile_is_per_user(client, make_user):
    alice, bob = await make_user(), await make_user()
    body = {"allergies": ["Dairy"], "diet": "vegan", "disliked_ingredients": [], "default_servings": 4}
    saved = await client.put("/profile", json=body, headers=alice["headers"])
    assert saved.status_code == 200 and saved.json()["allergies"] == ["dairy"]
    assert (await client.get("/profile", headers=bob["headers"])).json()["allergies"] == []


async def test_shopping_lists_are_private(client, make_user, maker):
    alice, bob = await make_user(), await make_user()
    async with maker() as db:
        shopping_list = ShoppingList(user_id=alice["id"], title="Alice's list")
        shopping_list.items = [ShoppingListItem(name="carrot", quantity=100, unit="g")]
        db.add(shopping_list)
        await db.commit()
        await db.refresh(shopping_list)
        list_id = shopping_list.id
        item_id = (await db.scalar(select(ShoppingListItem.id).where(ShoppingListItem.list_id == list_id)))

    assert (await client.get(f"/shopping-lists/{list_id}", headers=alice["headers"])).status_code == 200
    assert (await client.get(f"/shopping-lists/{list_id}", headers=bob["headers"])).status_code == 404
    patch = await client.patch(
        f"/shopping-lists/{list_id}/items/{item_id}", json={"is_bought": True}, headers=bob["headers"]
    )
    assert patch.status_code == 404
    assert (await client.delete(f"/shopping-lists/{list_id}", headers=bob["headers"])).status_code == 404
    assert (await client.get("/shopping-lists", headers=bob["headers"])).json() == []


async def test_cookbook_is_private(client, make_user, no_gemini, track_recipe):
    alice, bob, admin = await make_user(), await make_user(), await make_user("admin")
    recipe = (await client.post("/recipes", json=RECIPE, headers=admin["headers"])).json()
    track_recipe(recipe["id"])

    assert (await client.post(f"/cookbook/{recipe['id']}", headers=alice["headers"])).status_code == 201
    assert len((await client.get("/cookbook", headers=alice["headers"])).json()) == 1
    assert (await client.get("/cookbook", headers=bob["headers"])).json() == []
