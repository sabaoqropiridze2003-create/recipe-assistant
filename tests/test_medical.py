from app.graph.logic import (
    MEDICAL_NOTICE_EN,
    MEDICAL_NOTICE_KA,
    medical_notice,
    needs_medical_notice,
    with_medical_notice,
)


def test_health_conditions_trigger_the_notice():
    for text in (
        "I have diabetes, what should I eat?",
        "Something for high blood pressure",
        "I am pregnant, any dinner ideas?",
        "recipes for kidney disease",
        "my cholesterol is high",
        "დიაბეტი მაქვს, რა ვჭამო?",
        "ორსულად ვარ, რა მოვამზადო?",
    ):
        assert needs_medical_notice(text), text


def test_normal_cooking_messages_do_not():
    for text in (
        "I have chicken, rice and broccoli",
        "red kidney beans stew",  
        "grill some chicken",
        "make it for 6 servings",
        "მაცივარში მაქვს ქათამი და ბრინჯი",
        "",
    ):
        assert not needs_medical_notice(text), text


def test_the_notice_is_in_the_users_language_and_added_by_code():
    assert medical_notice("I have diabetes") == MEDICAL_NOTICE_EN
    assert medical_notice("დიაბეტი მაქვს") == MEDICAL_NOTICE_KA
    assert medical_notice("hello", "Georgian") == MEDICAL_NOTICE_KA
    answer = with_medical_notice("Try the lentil soup.", "I have diabetes", "English")
    assert answer.startswith("Try the lentil soup.") and answer.endswith(MEDICAL_NOTICE_EN)
    assert with_medical_notice("Try the soup.", "a soup please") == "Try the soup."
