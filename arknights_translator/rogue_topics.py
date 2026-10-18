"""Traditional Chinese display names for Integrated Strategies topics.

Use original internal topic IDs in saved data and matching operations.
"""

ROGUE_TOPICS = {
    'rogue_1': '傀影與猩紅孤鑽',
    'rogue_2': '水月與深藍之樹',
    'rogue_3': '探索者的銀凇止境',
    'rogue_4': '薩卡茲的無終奇語',
    'rogue_5': '歲的界園志異',
}


def topic_label(topic_id: str) -> str:
    """Human-readable UI label with ID fallback for future topics."""
    return ROGUE_TOPICS.get(topic_id, topic_id)
