# src/chat_manager.py
import streamlit as st
from typing import List, Dict

CHAT_STATE_KEY = "__chat_state__"


def init_chat_state():
    if CHAT_STATE_KEY not in st.session_state:
        st.session_state[CHAT_STATE_KEY] = {
            "messages": []
        }


class ChatManager:
    def __init__(self):
        if CHAT_STATE_KEY not in st.session_state:
            raise RuntimeError(
                "Chat state not initialized. "
                "Call init_chat_state() in init_session_state()."
            )

    @property
    def messages(self) -> List[Dict]:
        return st.session_state[CHAT_STATE_KEY]["messages"]

    def add_user(self, content: str):
        self.messages.append({"role": "user", "content": content})

    def add_assistant(self, content: str):
        # 防御：永远不允许 None
        if content is None:
            content = "我已经完成了操作，但没有需要额外说明的内容。"
        self.messages.append({"role": "assistant", "content": content})


