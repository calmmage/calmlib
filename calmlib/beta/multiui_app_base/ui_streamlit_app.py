"""
Goal of this file:
given an app that has a simple text-based interface, we want to create a Streamlit interface for it
app will have .invoke() method that takes a string and returns a string
"""

import streamlit as st

from app import App

app = App()


def main():
    st.title(f"{app.__class__.__name__} Streamlit App")

    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Display chat messages from history on app rerun
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Accept user input
    if input_str := st.chat_input("Enter your input"):
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": input_str})
        # Display user message in chat message container
        with st.chat_message("user"):
            st.markdown(input_str)

        output_str = app.invoke(input_str)

        with st.chat_message("assistant"):
            st.markdown(output_str)
        st.session_state.messages.append({"role": "assistant", "content": output_str})


if __name__ == "__main__":
    main()
# Compare this snippet from dev/example_1_app_template/ui_telegram_bot.py:
