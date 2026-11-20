import pandas as pd
import streamlit as st
from common import api, call


def render() -> None:
    st.title("📊 Analytics")
    st.caption("Admin only. Every number is counted by the database.")
    client = api()

    popular = call(client.popular_recipes, 10, stop=True)
    left, right = st.columns(2)
    with left:
        st.subheader("Most shown")
        st.dataframe(popular["most_shown"], hide_index=True)
    with right:
        st.subheader("Most saved")
        st.dataframe(popular["most_saved"], hide_index=True)

    st.subheader("AI-generated recipes")
    stats = call(client.ai_generated)
    if stats:
        a, b, c, d = st.columns(4)
        a.metric("Created", stats["created"])
        b.metric("Saved by users", stats["saved"])
        c.metric("In cookbooks", stats["in_cookbooks"])
        d.metric("Save rate", "–" if stats["save_rate"] is None else f"{stats['save_rate']:.0%}")

    st.subheader("What people ask for")
    intents = call(client.intents)
    if intents:
        st.bar_chart(pd.DataFrame(intents).set_index("intent"))
    else:
        st.info("No data yet.")
