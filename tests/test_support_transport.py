import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from bot.support_transport import SupportTransportRejected, SupportTransportStore
from bot.telegram_private_support import TelegramPrivateSupportRuntime
from bot.telegram_support_transport import TelegramDurableSupportRejected, TelegramDurableSupportRuntime
from core import CaseEngine


def fixture(tmp_path: Path):
    core_db=tmp_path/"BLOCKCHAINPLUS-MASTER.sqlite"; binding_db=tmp_path/"private"/"support-binding.sqlite"; transport_db=tmp_path/"private"/"support-transport.sqlite"
    core=CaseEngine(core_db); owner=core.register_user("SIC-TRANSPORT-OWNER",{},"reg-owner","req-owner"); other=core.register_user("SIC-TRANSPORT-OTHER",{},"reg-other","req-other")
    owner_session=core.create_session(owner["user_id"],owner["sic_id"],"req-so","idem-so",3600); other_session=core.create_session(other["user_id"],other["sic_id"],"req-sx","idem-sx",3600)
    case=core.open_case(owner["user_id"],owner["sic_id"],None,"project:unknown",False,"USER","req-case-transport","idem-case-transport")
    private=TelegramPrivateSupportRuntime(binding_db,core_db); durable=TelegramDurableSupportRuntime(private_runtime=private,transport_db_path=transport_db)
    return core,private,durable,transport_db,owner,other,owner_session,other_session,case


def bind(private,session,sic_id,principal):
    code=private.store.issue_link_code(core_session_id=session["session_id"],sic_id=sic_id)
    return private.bind(telegram_principal=principal,link_code=code)


def test_authorized_ticket_is_durable_idempotent_and_principal_is_hashed(tmp_path: Path):
    _,private,durable,db,owner,_,session,_,case=fixture(tmp_path); principal="telegram:1001"; token=bind(private,session,owner["sic_id"],principal)
    first=durable.create_ticket(telegram_principal=principal,support_session_id=token,case_id=case["case_id"],summary="Please review my Case status and next action.",category="CASE_STATUS")
    replay=durable.create_ticket(telegram_principal=principal,support_session_id=token,case_id=case["case_id"],summary="Please review my Case status and next action.",category="CASE_STATUS")
    assert first.ticket_id==replay.ticket_id and first.idempotent is False and replay.idempotent is True
    assert principal.encode() not in db.read_bytes()
    with sqlite3.connect(db) as connection: assert connection.execute("SELECT case_id,category,escalate,summary FROM support_tickets").fetchone()==(case["case_id"],"CASE_STATUS",0,"Please review my Case status and next action.")


def test_cross_user_revoked_and_secret_ticket_fail_before_persistence(tmp_path: Path):
    core,private,durable,db,owner,other,owner_session,other_session,case=fixture(tmp_path)
    other_token=bind(private,other_session,other["sic_id"],"telegram:other")
    with pytest.raises(TelegramDurableSupportRejected): durable.create_ticket(telegram_principal="telegram:other",support_session_id=other_token,case_id=case["case_id"],summary="Need help")
    owner_token=bind(private,owner_session,owner["sic_id"],"telegram:owner")
    with pytest.raises(TelegramDurableSupportRejected): durable.create_ticket(telegram_principal="telegram:owner",support_session_id=owner_token,case_id=case["case_id"],summary="my seed phrase is alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu")
    core.revoke_session(owner_session["session_id"],owner["user_id"])
    with pytest.raises(TelegramDurableSupportRejected): durable.create_ticket(telegram_principal="telegram:owner",support_session_id=owner_token,case_id=case["case_id"],summary="Need escalation",escalate=True)
    with sqlite3.connect(db) as connection: assert connection.execute("SELECT COUNT(*) FROM support_tickets").fetchone()[0]==0


def test_notification_claim_is_single_winner_then_delivery_is_deduped(tmp_path: Path):
    _,private,durable,db,owner,_,session,_,case=fixture(tmp_path); principal="telegram:notify-owner"; token=bind(private,session,owner["sic_id"],principal)
    def claim(): return durable.claim_notification(telegram_principal=principal,support_session_id=token,case_id=case["case_id"],event_type="STATUS_CHANGED",lease_seconds=60,now=1000.0)
    with ThreadPoolExecutor(max_workers=8) as pool: claims=list(pool.map(lambda _:claim(),range(8)))
    winners=[item for item in claims if item.should_send]; assert len(winners)==1; winner=winners[0]; assert winner.claim_token
    receipt=durable.mark_notification_delivered(delivery_id=winner.delivery_id,claim_token=winner.claim_token,transport_message_id="telegram-message-42",now=1001.0)
    assert receipt=={"delivery_id":winner.delivery_id,"state":"DELIVERED","idempotent":False}
    after=claim(); assert after.should_send is False and after.state=="DELIVERED"
    raw=db.read_bytes().lower(); assert b"evidence" not in raw and principal.encode() not in raw


def test_expired_claim_can_be_reclaimed_but_old_claim_cannot_ack(tmp_path: Path):
    _,private,durable,_,owner,_,session,_,case=fixture(tmp_path); principal="telegram:lease-owner"; token=bind(private,session,owner["sic_id"],principal)
    first=durable.claim_notification(telegram_principal=principal,support_session_id=token,case_id=case["case_id"],event_type="ACTION_REQUIRED",lease_seconds=10,now=100.0)
    second=durable.claim_notification(telegram_principal=principal,support_session_id=token,case_id=case["case_id"],event_type="ACTION_REQUIRED",lease_seconds=10,now=111.0)
    assert first.should_send and second.should_send and second.attempt_count==2 and second.claim_token!=first.claim_token
    with pytest.raises(TelegramDurableSupportRejected): durable.mark_notification_delivered(delivery_id=first.delivery_id,claim_token=first.claim_token,transport_message_id="stale")
    durable.mark_notification_delivered(delivery_id=second.delivery_id,claim_token=second.claim_token,transport_message_id="fresh")


def test_transport_db_rejects_public_html_and_integrity_is_ok(tmp_path: Path):
    with pytest.raises(SupportTransportRejected): SupportTransportStore(tmp_path/"public_html"/"support.sqlite")
    store=SupportTransportStore(tmp_path/"private"/"support.sqlite"); assert store.integrity()=="ok"


def _symlink_or_skip(target: Path, link: Path):
    link.parent.mkdir(parents=True, exist_ok=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.symlink(target, link)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlink unavailable on this runner: {exc}")


def test_transport_db_rejects_precreated_final_symlink_before_target_mutation(tmp_path: Path):
    target=tmp_path/"public_html"/"redirected-support.sqlite"
    link=tmp_path/"private"/"support-transport.sqlite"
    _symlink_or_skip(target,link)
    with pytest.raises(SupportTransportRejected):
        SupportTransportStore(link)
    assert link.is_symlink()
    assert not target.exists()


def test_transport_db_rechecks_final_component_before_each_open(tmp_path: Path):
    db=tmp_path/"private"/"support-transport.sqlite"
    store=SupportTransportStore(db)
    assert store.integrity()=="ok"
    db.unlink()
    target=tmp_path/"outside"/"redirected.sqlite"
    _symlink_or_skip(target,db)
    with pytest.raises(SupportTransportRejected):
        store.integrity()
    assert not target.exists()