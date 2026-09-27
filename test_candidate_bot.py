"""
Direct contract and integration test for Candidate Bot components.
Tests ContextStore, Composer, and ConversationHandlers against challenge specifications.
"""

import sys
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from context_store import ContextStore
from composer import compose
from conversation_handlers import conversation_manager


def test_context_store():
    print("Testing ContextStore...")
    cs = ContextStore()

    # 1. New push
    ok, code, res = cs.push("merchant", "m_001", 1, {"name": "Test Clinic"})
    assert ok and code == 200, f"Expected 200, got {code}"

    # 2. Idempotent re-push of same version
    ok, code, res = cs.push("merchant", "m_001", 1, {"name": "Test Clinic"})
    assert ok and code == 200, f"Expected 200 on idempotent re-push, got {code}"

    # 3. Stale version push
    ok, code, res = cs.push("merchant", "m_001", 0, {"name": "Old Clinic"})
    assert not ok and code == 409, f"Expected 409 on stale version, got {code}"

    # 4. Newer version update
    ok, code, res = cs.push("merchant", "m_001", 2, {"name": "Updated Clinic"})
    assert ok and code == 200, f"Expected 200 on newer version, got {code}"
    assert cs.get("merchant", "m_001")["name"] == "Updated Clinic"

    print(" ContextStore tests passed successfully.")


def test_composer():
    print("Testing Composer...")
    cat = {
        "slug": "dentists",
        "voice": {"tone": "peer_clinical", "vocab_taboo": ["guaranteed"]},
        "digest": [{"id": "d1", "title": "3-mo fluoride recall", "source": "JIDA Oct 2026, p.14"}]
    }
    m = {
        "merchant_id": "m_001_drmeera",
        "category_slug": "dentists",
        "identity": {"name": "Dr. Meera's Clinic", "owner_first_name": "Meera", "locality": "Lajpat Nagar"},
        "performance": {"views": 2410, "calls": 18, "ctr": 0.021},
        "customer_aggregate": {"high_risk_adult_count": 124},
        "offers": [{"title": "Dental Cleaning @ ₹299", "status": "active"}]
    }
    trg = {
        "id": "trg_001",
        "kind": "research_digest",
        "scope": "merchant",
        "payload": {"top_item_id": "d1"},
        "suppression_key": "res:dentists:w17"
    }

    # Merchant-facing compose
    res = compose(cat, m, trg)
    assert "Dr. Meera" in res["body"] or "Doctor" in res["body"] or "JIDA" in res["body"]
    assert res["send_as"] == "vera"
    assert res["cta"] in ("binary", "open_ended", "none")
    assert len(res["rationale"]) > 5

    # Customer-facing compose
    cust = {
        "customer_id": "c_001",
        "identity": {"name": "Priya", "language_pref": "hi-en mix"}
    }
    trg_cust = {
        "id": "trg_cust_1",
        "kind": "recall_due",
        "scope": "customer",
        "payload": {
            "available_slots": [
                {"label": "Wed 5 Nov, 6pm"},
                {"label": "Thu 6 Nov, 5pm"}
            ]
        },
        "suppression_key": "recall:c_001"
    }
    res_cust = compose(cat, m, trg_cust, cust)
    assert "Priya" in res_cust["body"]
    assert res_cust["send_as"] == "merchant_on_behalf"
    assert "₹299" in res_cust["body"]

    print(" Composer tests passed successfully.")


def test_conversation_handlers():
    print("Testing ConversationHandlers...")
    
    # 1. Auto-reply detection
    reply_auto = conversation_manager.handle_reply(
        conversation_id="conv_test_auto",
        merchant_id="m_001",
        customer_id=None,
        from_role="merchant",
        message="Thank you for contacting us! Our team will respond shortly.",
        turn_number=1,
    )
    assert reply_auto["action"] == "end", f"Expected end on auto-reply, got {reply_auto['action']}"

    # 2. Intent commitment transition
    reply_intent = conversation_manager.handle_reply(
        conversation_id="conv_test_intent",
        merchant_id="m_001",
        customer_id=None,
        from_role="merchant",
        message="Ok lets do it. Whats next?",
        turn_number=2,
    )
    assert reply_intent["action"] == "send", f"Expected send on intent, got {reply_intent['action']}"
    body_lower = reply_intent["body"].lower()
    actioning = ["done", "sending", "draft", "here", "confirm", "proceed", "next"]
    qualifying = ["would you", "do you", "can you tell", "what if", "how about"]
    assert any(w in body_lower for w in actioning), "Expected actioning keywords"
    assert not any(w in body_lower for w in qualifying), "Did not expect qualifying questions"

    # 3. Hostile handling
    reply_hostile = conversation_manager.handle_reply(
        conversation_id="conv_test_hostile",
        merchant_id="m_001",
        customer_id=None,
        from_role="merchant",
        message="Stop messaging me. This is useless spam.",
        turn_number=2,
    )
    assert reply_hostile["action"] == "end", f"Expected end on hostile, got {reply_hostile['action']}"

    print(" ConversationHandler tests passed successfully.")


if __name__ == "__main__":
    test_context_store()
    test_composer()
    test_conversation_handlers()
    print("\nALL CONTRACT TESTS PASSED!")
