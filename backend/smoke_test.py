"""Logic Labs university smoke test. Run after starting the app."""
import os, sys, uuid, httpx
BASE=os.getenv("LOGICLABS_BASE_URL","http://127.0.0.1:8000").rstrip("/")
USERS={"rahul@student":"Student@123","neha@faculty":"Faculty@123","arjun@admin":"Admin@123"}

def login(c, login_id, pw):
    r=c.post('/api/login',json={'username':login_id,'password':pw}); r.raise_for_status(); d=r.json(); return d['token'],d['user']

def ask(c,tok,q):
    r=c.post('/api/ask',headers={'Authorization':f'Bearer {tok}'},json={'question':q}); r.raise_for_status(); return r.json()

def main():
    with httpx.Client(base_url=BASE,timeout=180) as c:
        c.get('/').raise_for_status(); print('PASS  server reachable')
        u=c.get('/api/users'); u.raise_for_status(); rows=u.json(); names={x['username']:x['role_name'] for x in rows}
        assert names['rahul@student']=='Student' and names['neha@faculty']=='Faculty Member' and names['arjun@admin']=='Admin'; print('PASS  role-based login IDs')
        st,stu=login(c,'rahul@student',USERS['rahul@student']); ft,fac=login(c,'neha@faculty',USERS['neha@faculty']); at,adm=login(c,'arjun@admin',USERS['arjun@admin']); print('PASS  seeded logins')
        q=ask(c,st,"What is Rahul Patel's result?"); assert q['claims']; print('PASS  student can retrieve own result')
        q2=ask(c,st,"Show Priya Shah's result"); assert q2['blocked']>0 or not q2['claims']; print('PASS  student cannot retrieve another student result')
        q3=ask(c,ft,'What is my Monday timetable?'); assert q3['claims']; print('PASS  faculty timetable retrieval')
        q4=ask(c,ft,"Show Rahul Patel's result"); assert q4['blocked']>0 or not q4['claims']; print('PASS  faculty cannot retrieve student-private result')
        q5=ask(c,at,"Show Rahul Patel's result"); assert q5['claims']; print('PASS  admin can retrieve student result')
        handle='demo'+uuid.uuid4().hex[:7]
        sr=c.post('/api/signup',json={'full_name':'Demo Student','handle':handle,'role':'student','password':'DemoPass123','password_confirm':'DemoPass123'}); sr.raise_for_status(); sd=sr.json(); assert sd['user']['login_id']==handle+'@student'; print('PASS  student self-signup')
        red=c.post('/api/redteam',headers={'Authorization':f'Bearer {st}'}); red.raise_for_status(); rd=red.json(); assert rd['attacks']==12 and rd['leaks']==0; print('PASS  red team: 12 attacks, 0 leaks')
    print('\nLogic Labs university smoke test PASSED')
if __name__=='__main__':
    try: main()
    except Exception as exc: print(f'FAILED: {exc}',file=sys.stderr); raise
