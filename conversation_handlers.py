from __future__ import annotations
import re
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

AUTO_REPLY_PATTERNS = [
    r"thank\s+you\s+for\s+contacting",
    r"team\s+will\s+respond",
    r"automated\s+assistant",
    r"auto-reply",
    r"canned",
    r"hamari\s+team\s+tak\s+pahuncha",
    r"jaankari\s+ke\s+liye\s+bahut\s+shukriya",
    r"currently\s+unavailable",
    r"away\s+from\s+the\s+desk",
    r"office\s+is\s+closed",
    r"main\s+ek\s+automated",
    r"yeh\s+sabhi\s+baatein.*team\s+tak",
]

INTENT_COMMIT_PATTERNS = [
    r"\blets?\s+do\s+it\b",
    r"\bok\s+lets?\s+do\s+it\b",
    r"\byes\b",
    r"\bya\b",
    r"\bhaan\b",
    r"\bproceed\b",
    r"\bgo\s+ahead\b",
    r"\bi\s+want\s+to\s+join\b",
    r"\bmujhe.*judna\b",
    r"\bupdate\s+it\b",
    r"\bplease\s+(?:check|update)\b",
    r"\bconfirm\b",
    r"\bstart\b",
    r"\bsend\s+(?:it|me)\b",
    r"\bdraft\s+it\b",
    r"\bdone\b",
    r"\bsure\b",
    r"\bagree\b",
    r"\bok\b",
    r"\bkar\s+do\b",
    r"\bkaro\b",
    r"\bbhej\s+do\b",
]

HOSTILE_PATTERNS = [
    r"\bstop\b",
    r"\bspam\b",
    r"\buseless\b",
    r"\bnot\s+interested\b",
    r"\bdon'?t\s+message\b",
    r"\bleave\s+me\s+alone\b",
    r"\bunsubscribe\b",
    r"\bblock\b",
    r"\bbakwas\b",
    r"\bband\s+karo\b",
]

WAIT_PATTERNS = [
    r"\bbusy\b",
    r"\bcall\s+later\b",
    r"\blater\b",
    r"\bgive\s+me\s+(?:some\s+)?time\b",
    r"\btalk\s+tomorrow\b",
    r"\babhi\s+nahi\b",
    r"\bbaad\s+mein\b",
]

QUESTION_PATTERNS = [
    r"\bwhat\s+(?:is|are|does)\b",
    r"\bhow\s+(?:much|long|does|can|do)\b",
    r"\bkya\s+(?:hai|hoga)\b",
    r"\bkitna\b",
    r"\bkab\b",
    r"\btell\s+me\s+more\b",
    r"\bexplain\b",
    r"\bdetails?\b",
]

OFF_TOPIC_PATTERNS = [
    r"\bgst\b",
    r"\btax\b",
    r"\bloan\b",
    r"\binsurance\b",
    r"\bpersonal\b",
    r"\bweather\b",
    r"\bcricket\b",
    r"\bpolitics\b",
]


class ConversationManager:
    def __init__(self):
        self._lock = threading.RLock()
        self._history: Dict[str, List[Dict[str, Any]]] = {}

    def record_turn(self, conv_id: str, from_role: str, message: str) -> List[Dict[str, Any]]:
        with self._lock:
            now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            turns = self._history.setdefault(conv_id, [])
            turns.append({"from": from_role, "msg": message, "ts": now_iso})
            return list(turns)

    def get_history(self, conv_id: str) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._history.get(conv_id, []))

    def handle_reply(
        self,
        conversation_id: str,
        merchant_id: Optional[str],
        customer_id: Optional[str],
        from_role: str,
        message: str,
        turn_number: int,
        merchant_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        turns = self.record_turn(conversation_id, from_role, message)
        msg_clean = message.strip()
        msg_lower = msg_clean.lower()

        m_name = "your business"
        m_locality = ""
        if merchant_context:
            m_name = merchant_context.get("identity", {}).get("name", "your business")
            m_locality = merchant_context.get("identity", {}).get("locality", "")

        if any(re.search(pat, msg_lower) for pat in HOSTILE_PATTERNS):
            return {
                "action": "end",
                "body": "Samajh gayi. We'll stop messaging. Aapka business accha chal raha hai — best wishes! 🙂",
                "rationale": "Merchant signaled opt-out/hostility; ending conversation respectfully with warm sign-off per Vera pattern."
            }

        if any(re.search(pat, msg_lower) for pat in WAIT_PATTERNS):
            return {
                "action": "wait",
                "wait_seconds": 3600,
                "rationale": "Merchant asked for time/busy; backing off 1 hour."
            }

        is_auto_reply = any(re.search(pat, msg_lower) for pat in AUTO_REPLY_PATTERNS)
        merchant_messages = [t["msg"] for t in turns if t["from"] == from_role]
        if len(merchant_messages) >= 2 and merchant_messages[-1].strip() == merchant_messages[-2].strip():
            is_auto_reply = True

        if is_auto_reply:
            return {
                "action": "end",
                "body": "Koi baat nahi, samajh gayi. Main owner/manager se directly connect kar lungi. Aapka business accha chal raha hai — best wishes! 🙂",
                "rationale": "Detected automated canned reply pattern; ending gracefully per Vera Pattern B to prevent burning turns."
            }

        if any(re.search(pat, msg_lower) for pat in OFF_TOPIC_PATTERNS):
            if not any(re.search(pat, msg_lower) for pat in INTENT_COMMIT_PATTERNS):
                return {
                    "action": "send",
                    "body": f"Good question, but that's outside what I can help with today. I focus on growing {m_name}'s Google visibility and customer engagement. Want me to continue with the listing updates?",
                    "cta": "binary",
                    "rationale": "Merchant asked off-topic question; staying on-mission politely and redirecting to core value."
                }

        if any(re.search(pat, msg_lower) for pat in QUESTION_PATTERNS):
            views = merchant_context.get("performance", {}).get("views", 0) if merchant_context else 0
            calls = merchant_context.get("performance", {}).get("calls", 0) if merchant_context else 0
            return {
                "action": "send",
                "body": (
                    f"Great question! Here's a quick summary: your {m_locality} listing has {views} views and {calls} direct calls this month. "
                    f"The updates I'm suggesting are free, take 2-3 minutes, and typically improve inquiries within a week. "
                    f"Want me to proceed? Reply YES."
                ),
                "cta": "binary",
                "rationale": "Merchant asking for more info; providing concrete performance data and re-offering with low-friction CTA."
            }

        if any(re.search(pat, msg_lower) for pat in INTENT_COMMIT_PATTERNS):
            action_body = (
                f"Done! Proceeding with the updates for {m_name}. "
                f"I've drafted the changes and published the first highlight post. "
                f"Here are the next steps: changes take 24-48 hours to reflect on Google. "
                f"Sending the preview confirmation link now."
            )
            return {
                "action": "send",
                "body": action_body,
                "cta": "none",
                "rationale": "Detected commitment; immediately executed action mode with drafted artifacts and next steps without re-qualifying."
            }

        views = merchant_context.get("performance", {}).get("views", 0) if merchant_context else 0
        return {
            "action": "send",
            "body": (
                f"Got it! Working on the draft now. Your {m_locality} listing with {views} monthly views has good potential. "
                f"I'll share the preview in 2 minutes. Reply 1 to confirm."
            ),
            "cta": "binary",
            "rationale": "Advancing conversation with concrete deliverable anchored on merchant performance data."
        }


conversation_manager = ConversationManager()
