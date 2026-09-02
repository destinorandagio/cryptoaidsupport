import tempfile
from pathlib import Path
import pytest
from evidence_payment import EvidencePaymentEngine, EvidencePaymentError


def engine():
    root=Path(tempfile.mkdtemp())
    return EvidencePaymentEngine(root/'BLOCKCHAINPLUS-MASTER.sqlite', root/'private-evidence')


def advance(e, intent):
    for state in ('USER_ACTION_REQUIRED','TX_OBSERVED','VERIFYING','FINALITY_PENDING'):
        intent=e.transition_payment(intent['intent_id'],state,'test')
    return intent


def good_obs(i):
    return {'chain_id':137,'from':i['payer'],'to':i['treasury_address'],'value':i['expected_value'],'asset':i['asset'],
            'receipt_status':1,'case_id':i['case_id'],'entitlement_ref':i['entitlement_ref'],'tx_hash':'0xabc',
            'block_hash':'0xblock','confirmations':10,'required_confirmations':5}


def providers(obs):
    return [{'tx_hash':obs['tx_hash'],'block_hash':obs['block_hash'],'receipt_status':1},
            {'tx_hash':obs['tx_hash'],'block_hash':obs['block_hash'],'receipt_status':1}]


def test_evidence_hash_private_versioning_and_tamper_guards():
    e=engine(); a=e.store_evidence(case_id='c1',content=b'abc',original_name='a.pdf',mime_declared='application/pdf',mime_detected='application/pdf',uploader='u',consent_id='cons',authorization='ALLOW')
    b=e.store_evidence(case_id='c1',content=b'abcd',original_name='a.pdf',mime_declared='application/pdf',mime_detected='application/pdf',uploader='u',consent_id='cons',authorization='ALLOW',parent_evidence_id=a['evidence_id'],reason='replace')
    assert a['sha256'] != b['sha256'] and b['version']==2
    with pytest.raises(EvidencePaymentError): e.store_evidence(case_id='c',content=b'x',original_name='x',mime_declared='image/png',mime_detected='image/jpeg',uploader='u',consent_id='c',authorization='ALLOW')
    with pytest.raises(EvidencePaymentError): e.store_evidence(case_id='c',content=b'xx',original_name='x',mime_declared='image/png',mime_detected='image/png',uploader='u',consent_id='c',authorization='ALLOW',max_bytes=1)
    with pytest.raises(EvidencePaymentError): e.store_evidence(case_id='c',content=b'x',original_name='x',mime_declared='image/png',mime_detected='image/png',uploader='u',consent_id='c',authorization='DENIED')


def test_payment_idempotency_wrong_chain_and_provider_disagreement_manual_review():
    e=engine(); i=e.create_payment_intent(case_id='c',entitlement_ref='ent',payer='0xsender',asset='POL',expected_value='500',request_id='r',idempotency_key='idem')
    assert e.create_payment_intent(case_id='c',entitlement_ref='ent',payer='0xsender',asset='POL',expected_value='500',request_id='r',idempotency_key='idem')['intent_id']==i['intent_id']
    i=advance(e,i); o=good_obs(i); o['chain_id']=1
    assert e.verify_observation(i['intent_id'],o,providers(o))=='MANUAL_REVIEW'
    o=good_obs(i); ps=providers(o); ps[1]['block_hash']='different'
    assert e.verify_observation(i['intent_id'],o,ps)=='MANUAL_REVIEW'


def test_settlement_is_append_only_and_idempotent():
    e=engine(); i=e.create_payment_intent(case_id='c',entitlement_ref='ent',payer='0xsender',asset='POL',expected_value='500',request_id='r',idempotency_key='x'); i=advance(e,i); o=good_obs(i)
    first=e.settle(i['intent_id'],o,providers(o)); second=e.settle(i['intent_id'],o,providers(o))
    assert first['entitlement_granted'] is True and second['idempotent'] is True
    with e._connect() as c: assert c.execute('SELECT COUNT(*) FROM entitlement_ledger').fetchone()[0]==1


def test_duplicate_tx_different_case_goes_manual_review():
    e=engine(); a=e.create_payment_intent(case_id='a',entitlement_ref='ea',payer='0xsender',asset='POL',expected_value='500',request_id='1',idempotency_key='1'); a=advance(e,a); oa=good_obs(a); e.settle(a['intent_id'],oa,providers(oa))
    b=e.create_payment_intent(case_id='b',entitlement_ref='eb',payer='0xsender',asset='POL',expected_value='500',request_id='2',idempotency_key='2'); b=advance(e,b); ob=good_obs(b)
    assert e.verify_observation(b['intent_id'],ob,providers(ob))=='MANUAL_REVIEW'


def test_multiple_active_treasuries_and_version_history():
    e=engine(); r=e.configure_treasury(treasury_id='backup',address='0xB',asset='POL',status='ACTIVE',priority=2,routing_rule='FALLBACK',valid_from='2020-01-01T00:00:00+00:00',valid_to=None,created_by='admin',approved_by='admin2')
    r2=e.configure_treasury(treasury_id='backup',address='0xC',asset='POL',status='ACTIVE',priority=2,routing_rule='FALLBACK',valid_from='2020-01-01T00:00:00+00:00',valid_to=None,created_by='admin',approved_by='admin2')
    assert r['version']==1 and r2['version']==2
