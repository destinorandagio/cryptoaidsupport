import tempfile
from pathlib import Path
import pytest
from core import CaseEngine, CaseError

def eng(): return CaseEngine(Path(tempfile.mkdtemp())/'BLOCKCHAINPLUS-MASTER.sqlite')
def user(e,sic='SIC-1',key='u1'): return e.register_user(sic,{'name':'x'},key,key)

def test_new_returning_user_and_duplicate_request():
 e=eng(); a=user(e); b=e.register_user('SIC-1',{},'u2','u2'); assert a['user_id']==b['user_id'] and b['returning'] is True
 assert e.register_user('OTHER',{},'u1','different')['user_id']==a['user_id']

def test_wallet_and_sic_mismatch():
 e=eng(); a=user(e); e.bind_wallet(a['user_id'],'SIC-1','0xabc','r','b')
 with pytest.raises(CaseError) as x:e.bind_wallet(a['user_id'],'WRONG','0xdef','r2','b2')
 assert x.value.code=='SIC_ID_MISMATCH'
 b=e.register_user('SIC-2',{},'u2','u2')
 with pytest.raises(CaseError) as x:e.bind_wallet(b['user_id'],'SIC-2','0xabc','r3','b3')
 assert x.value.code=='WALLET_MISMATCH'

def test_to_verify_does_not_block_case_and_resume():
 e=eng(); a=user(e); c=e.open_case(a['user_id'],'SIC-1',None,'unknown',False,'USER','r','case1'); assert c['project_truth']=='TO_VERIFY'
 assert e.get_case(c['case_id'],a['user_id'])['state']=='DRAFT'
 assert e.open_case(a['user_id'],'SIC-1',None,'unknown',False,'USER','r','case1')['case_id']==c['case_id']

def test_invalid_transition_stale_and_missing_entitlement():
 e=eng(); a=user(e); c=e.open_case(a['user_id'],'SIC-1',None,None,False,'USER','r','c')
 with pytest.raises(CaseError) as x:e.transition(c['case_id'],a['user_id'],'ACTIVE','USER','skip','r2','t1','OWNER',1)
 assert x.value.code=='INVALID_TRANSITION'
 c=e.transition(c['case_id'],a['user_id'],'TRIAGE','USER','triage','r3','t2','OWNER',1)
 with pytest.raises(CaseError) as x:e.transition(c['case_id'],a['user_id'],'PRODUCT_SELECTED','USER','p','r4','t3','OWNER',1)
 assert x.value.code=='STALE_STATE'
 c=e.transition(c['case_id'],a['user_id'],'PRODUCT_SELECTED','USER','p','r4','t4','OWNER',2)
 with pytest.raises(CaseError) as x:e.transition(c['case_id'],a['user_id'],'ACTIVE','SYSTEM','free?','r5','t5','OWNER',3)
 assert x.value.code=='MISSING_ENTITLEMENT'

def test_product_kinds_task_timeline_and_unauthorized_case():
 e=eng(); a=user(e); e.upsert_product('P','CASE','ACTIVE',{}, {'price_source':'MASTER'},1); c=e.open_case(a['user_id'],'SIC-1',None,None,True,'USER','r','c')
 assert e.select_product(c['case_id'],a['user_id'],'P')['kind']=='CASE'; assert e.add_task(c['case_id'],a['user_id'],'Do it','NEXT')['next_action']=='NEXT'; assert len(e.timeline(c['case_id'],a['user_id']))==1
 b=e.register_user('SIC-2',{},'u2','u2')
 with pytest.raises(CaseError):e.get_case(c['case_id'],b['user_id'])

def test_concurrency_guard_is_optimistic_version():
 e=eng(); a=user(e); c=e.open_case(a['user_id'],'SIC-1',None,None,False,'USER','r','c'); e.transition(c['case_id'],a['user_id'],'TRIAGE','A','x','r1','x1','OWNER',1)
 with pytest.raises(CaseError) as x:e.transition(c['case_id'],a['user_id'],'TRIAGE','B','x','r2','x2','OWNER',1)
 assert x.value.code=='STALE_STATE'
