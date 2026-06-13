"""情绪急救站 — 本地即时共情文案（零延迟，不调用 AI）。"""

from __future__ import annotations

import random
import re

from utils.emotion_adapter import normalize_emotion_state

INSTANT_REPLIES: dict[str, list[str]] = {
    "焦虑": [
        "嗯，听到了。焦虑的时候，先把呼吸放慢一点就好，不用急着把所有事一次想清楚。\n\n你已经很努力了，允许自己此刻就是有点乱。",
        "我在这儿。睡不着、心里发紧，都是身体在告诉你「这件事对我很重要」。\n\n不用逼自己马上好起来，我们慢慢来。",
        "这种「一直悬着」的感觉很难受，我懂。\n\n先别急着找答案，能说出来就已经是在照顾自己了。",
        "一家一家投简历，等着那个「已读不回」——心里发紧、又累又慌，太正常了。\n\n你不用装没事，此刻就是很难，我陪着你。",
    ],
    "挫败": [
        "试了很多次还没结果，换谁都会泄气。这不是你不行，是这件事本来就需要时间。\n\n你的努力我看得到，先歇口气也没关系。",
        "失败了不代表你不够好，只代表这一局还没轮到。\n\n愿意继续试的人，本身就很有力量。",
        "想放弃的时候，往往是因为你已经撑太久了。\n\n先别急着否定自己，我们看看已经走过了哪些路。",
        "简历一份份发出去，像扔进海里——没有回音的时候，最容易怀疑自己。\n\n可撑到现在还在投，本身就需要很大的力气。先歇口气，我在这儿。",
        "投了那么多，身体和心理都会喊累。这不是你不够努力，是这件事真的太耗人了。\n\n允许自己此刻就是倦了，不用马上振作。",
    ],
    "迷茫": [
        "不知道往哪走，这种空落落的感觉很真实。\n\n不用马上找到标准答案，先把此刻最堵的那一点说清楚，就已经是方向了。",
        "迷茫不是落后，是在重新找自己的位置。\n\n你可以慢慢想，我陪着你，不催你。",
        "看不清路的时候，先站稳当下这一步就好。\n\n方向常常是在行动中慢慢显出来的。",
    ],
    "平稳": [
        "嗯，我在听。想说什么都可以，不评判，不催促。\n\n你慢慢讲，我在这儿。",
        "听到了。不管大事小事，能说出来就是对自己诚实。\n\n我陪你把这句话放下来。",
    ],
}


def infer_emotion_from_text(text: str) -> str:
    """从用户输入推断情绪类型（本地规则，不调 AI）。"""
    if not text:
        return "平稳"
    normalized = normalize_emotion_state(text)
    if normalized != "平稳":
        return normalized
    if re.search(r"焦虑|睡不着|担心|害怕|紧张|慌", text):
        return "焦虑"
    if re.search(r"失败|放弃|挫败|没戏|不行", text):
        return "挫败"
    if re.search(r"迷茫|不知道|方向|怎么办", text):
        return "迷茫"
    if re.search(r"委屈|不公平|难受", text):
        return "挫败"
    if re.search(r"累|疲惫|倦|熬|没回音|没回应|海投|简历|投了", text):
        if re.search(r"慌|焦虑|担心|睡不着", text):
            return "焦虑"
        return "挫败"
    return "平稳"


def is_low_quality_ai_reply(user_text: str, ai_reply: str) -> bool:
    """AI 只是在复述用户、过短或像客服时，保留本地即时共情。"""
    ai = (ai_reply or "").strip()
    if not ai:
        return True

    paragraphs = [p.strip() for p in ai.split("\n\n") if p.strip()]

    # 两段式且有一定篇幅，通常是合格共情
    if len(paragraphs) >= 2 and len(ai) >= 48:
        return False

    if len(ai) < 42:
        return True
    if len(paragraphs) <= 1 and len(ai) < 85:
        return True

    echo_prefixes = ("嗯，听到了", "听到了", "嗯，我听到了", "我听到了", "我理解", "嗯，听到")
    if any(ai.startswith(prefix) for prefix in echo_prefixes) and len(ai) < 110:
        user_terms = [t for t in re.findall(r"[\u4e00-\u9fa5]{2,}", user_text) if len(t) >= 2]
        if user_terms:
            overlap = sum(1 for t in user_terms if t in ai)
            if overlap >= min(2, len(user_terms)):
                return True

    cold_phrases = ("确实挺", "可以理解", "这种情况", "您的", "建议您")
    if sum(1 for p in cold_phrases if p in ai) >= 2 and len(ai) < 120:
        return True
    return False


def pick_instant_reply(emotion: str, score: int | None = None) -> str:
    """随机选取一条即时共情回复。"""
    key = normalize_emotion_state(emotion)
    pool = INSTANT_REPLIES.get(key) or INSTANT_REPLIES["平稳"]
    base = random.choice(pool)
    if score is not None and score <= 3:
        return base + "\n\n（你现在的状态比较低落，我们先不聊建议，只陪着你。）"
    return base
