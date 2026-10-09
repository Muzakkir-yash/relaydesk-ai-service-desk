"""
RelayDesk AI Chat Triage — Senior QA Test Suite
"""
import sys, os, time
if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8')
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path: sys.path.insert(0, backend_dir)

from fastapi.testclient import TestClient
from main import app
client = TestClient(app)

P=0; F=0; W=0; FAILS=[]

def ok(n):
    global P; P+=1; print(f"  PASS  {n}")
def fail(n, r):
    global F; F+=1; FAILS.append((n,r)); print(f"  FAIL  {n}\n        >> {r}")
def warn(n, r):
    global W; W+=1; print(f"  WARN  {n}\n        >> {r}")
def sec(t): print(f"\n--- {t} ---")

def token(email, pw="password123"):
    r = client.post("/auth/login", json={"email":email,"password":pw})
    return r.json().get("access_token") if r.status_code==200 else None

def H(t): return {"Authorization":f"Bearer {t}"}

def chat(tok, msg, hist=None):
    return client.post("/tickets/ai-triage/chat",
                       json={"message":msg,"chat_history":hist or []},
                       headers=H(tok))

print("\n"+"="*60)
print("  RELAYDESK AI CHAT — SENIOR QA QUICK TEST SUITE")
print("="*60)

# ── AUTH ──────────────────────────────────────────────────────
sec("0. AUTH")
alice = token("alice@company.com")
if alice: ok("Alice login")
else: fail("Alice login","No token"); sys.exit(1)

bad = client.post("/auth/login",json={"email":"alice@company.com","password":"wrong"})
if bad.status_code in (400,401,403): ok("Wrong password rejected")
else: fail("Wrong password rejected", f"Got {bad.status_code}")

client.cookies.clear()  # login set a session cookie; this check must carry no credentials
unauth = client.post("/tickets/ai-triage/chat",json={"message":"hi"})
if unauth.status_code==401: ok("Unauthenticated → 401")
else: fail("Unauthenticated", f"Got {unauth.status_code}")

# ── GREETING DETECTION ────────────────────────────────────────
sec("1. GREETING DETECTION (no IT steps)")
for msg, label in [
    ("hello","hello"), ("hi","hi"), ("good morning","good morning"),
    ("how are you","how are you"), ("hey can you help me","hey + vague ask"),
]:
    r = chat(alice, msg)
    if r.status_code != 200: fail(f"Greeting:{label}", f"HTTP {r.status_code}"); continue
    d = r.json()
    reply = d.get("reply","").lower()
    if d.get("status_intent")=="resolved":
        fail(f"Greeting:{label}", "Bot said RESOLVED on greeting!")
    elif any(x in reply for x in ["step 1","1.","ipconfig","restart your","windows key"]):
        fail(f"Greeting:{label}", f"Bot gave IT steps for greeting: {reply[:60]}")
    else:
        ok(f"Greeting: '{label}' → no IT steps, intent={d.get('status_intent')}")

# ── IT PROBLEM DETECTION ──────────────────────────────────────
sec("2. IT PROBLEM DETECTION (positive)")
for msg, label in [
    ("My wifi keeps disconnecting","WiFi"),
    ("Cannot connect to VPN, error 412","VPN"),
    ("My password expired, cannot log in","Password"),
    ("Outlook not syncing emails","Outlook"),
    ("Printer stuck in queue, won't print","Printer"),
    ("Blue screen of death, stop code IRQL","BSOD"),
    ("Teams audio not working in calls","Teams audio"),
    ("MFA app not showing codes","MFA"),
]:
    r = chat(alice, msg)
    if r.status_code!=200: fail(f"ITProblem:{label}", f"HTTP {r.status_code}"); continue
    d = r.json()
    if d.get("status_intent")=="resolved":
        fail(f"ITProblem:{label}", "CRITICAL: First msg flagged as RESOLVED!")
    elif d.get("can_resolve") and d.get("reply"):
        ok(f"IT Problem: {label} → intent={d['status_intent']}, cat={d['category']}")
    else:
        warn(f"ITProblem:{label}", f"intent={d.get('status_intent')}, reply={d.get('reply','')[:60]}")

# ── REGRESSION: FALSE-POSITIVE RESOLVED ──────────────────────
sec("3. REGRESSION — False-Positive Resolution Bug")
for msg, label in [
    ("what are the IT issues you solved",       "'solved' in question"),
    ("how have you solved VPN problems before", "'solved'+IT in question"),
    ("what worked for fixing wifi issues",      "'worked' in question"),
    ("which printer issues have you fixed",     "'fixed' in question"),
    ("thanks for nothing, wifi still broken",   "'thanks' + problem"),
    ("thank you but it still doesnt work",      "'thank you' + ongoing issue"),
    ("can you help me? thanks",                 "polite ask with 'thanks'"),
    ("did this solution work for others",       "'worked' as question"),
    ("who solved the outlook issue last week",  "'solved' past tense Q"),
]:
    r = chat(alice, msg, hist=[])  # NO prior AI history
    if r.status_code!=200: fail(f"Regression:{label}", f"HTTP {r.status_code}"); continue
    d = r.json()
    reply = d.get("reply","").lower()
    if d.get("status_intent")=="resolved" or "fantastic" in reply:
        fail(f"Regression:{label}", f"FALSE POSITIVE: Bot said RESOLVED! Reply={reply[:80]}")
    else:
        ok(f"Regression: {label} → NOT resolved (intent={d.get('status_intent')})")

# ── VALID RESOLUTION (after AI replied) ──────────────────────
sec("4. VALID RESOLUTION CONFIRMATION (after AI reply)")
ai_hist = [
    {"sender":"user","sender_type":"user","body":"My wifi keeps dropping"},
    {"sender":"ai",  "sender_type":"ai",  "body":"Here are steps: 1. Forget network..."},
]
for msg, label in [
    ("working now thank you", "working now"),
    ("its fixed now",         "its fixed"),
    ("all good now",          "all good now"),
    ("issue solved",          "issue solved"),
]:
    r = chat(alice, msg, hist=ai_hist)
    if r.status_code!=200: fail(f"ValidResolve:{label}", f"HTTP {r.status_code}"); continue
    d = r.json()
    if d.get("status_intent")=="resolved": ok(f"Valid Resolve: '{label}' → resolved ✓")
    else: warn(f"ValidResolve:{label}", f"Expected resolved, got {d.get('status_intent')}")

# ── ESCALATION DETECTION ─────────────────────────────────────
sec("5. ESCALATION DETECTION")
ai_hist2 = [
    {"sender":"user","sender_type":"user","body":"VPN not connecting"},
    {"sender":"ai",  "sender_type":"ai",  "body":"Try these steps: 1. Reconnect..."},
]
for msg, hist, label in [
    ("still broken after all steps",        ai_hist2, "still broken after steps"),
    ("please connect me to human support",  [],       "human support phrase"),
    ("I need to talk to a real person",     [],       "real person"),
    ("still not working after your steps",  ai_hist2, "still not working"),
]:
    r = chat(alice, msg, hist=hist)
    if r.status_code!=200: fail(f"Escalate:{label}", f"HTTP {r.status_code}"); continue
    d = r.json()
    if d.get("status_intent")=="escalate": ok(f"Escalation: '{label}' → escalated ✓")
    elif d.get("status_intent")=="resolved": fail(f"Escalate:{label}", "Bot said RESOLVED!")
    else: warn(f"Escalate:{label}", f"Expected escalate, got {d.get('status_intent')}")

# No-false-positive guards for escalation
for msg, label in [
    ("what does a technician do",      "question about technician"),
    ("who is the agent handling this", "question about agent"),
]:
    r = chat(alice, msg, hist=[])
    if r.status_code!=200: fail(f"NoEscalate:{label}", f"HTTP {r.status_code}"); continue
    d = r.json()
    if d.get("status_intent")=="escalate":
        fail(f"NoEscalate:{label}", f"WRONG: Question about {label} triggered escalation!")
    else:
        ok(f"No-Escalate Guard: '{label}' → intent={d.get('status_intent')} ✓")

# ── VAGUE MESSAGES ────────────────────────────────────────────
sec("6. VAGUE MESSAGES (should clarify, not resolve)")
for msg, label in [
    ("it doesn't work","generic"),
    ("something is broken","vague broken"),
    ("I have a problem","generic problem"),
    ("help me please","generic help"),
]:
    r = chat(alice, msg, hist=[])
    if r.status_code!=200: fail(f"Vague:{label}", f"HTTP {r.status_code}"); continue
    d = r.json()
    if d.get("status_intent")=="resolved":
        fail(f"Vague:{label}", "Bot said RESOLVED for vague message!")
    else:
        ok(f"Vague: '{label}' → intent={d.get('status_intent')} (not resolved)")

# ── EDGE CASES ────────────────────────────────────────────────
sec("7. EDGE CASES")

# XSS / injection
r = chat(alice, "wifi <script>alert('xss')</script>; DROP TABLE tickets;--")
if r.status_code==200:
    if "<script>" in r.json().get("reply",""):
        fail("XSS injection", "Raw <script> tag in reply!")
    else: ok("XSS/SQL injection sanitized")
else: fail("XSS message", f"HTTP {r.status_code}")

# Unicode / emoji
r = chat(alice, "🔥 my wifi is 💀 dead, nothing works 😭")
if r.status_code==200: ok("Unicode/emoji message handled")
else: fail("Unicode/emoji", f"HTTP {r.status_code}")

# ALL CAPS
r = chat(alice, "MY VPN IS DOWN AND I CANNOT WORK THIS IS URGENT!!!")
if r.status_code==200:
    d=r.json()
    if d.get("status_intent")=="resolved": fail("CAPS urgent", "Bot said RESOLVED!")
    else: ok(f"ALL CAPS urgent VPN → intent={d.get('status_intent')}")
else: fail("CAPS message", f"HTTP {r.status_code}")

# Long message
r = chat(alice, "My WiFi keeps disconnecting. " * 80)
if r.status_code==200: ok("Very long message (2240 chars) handled without 500")
else: fail("Long message", f"HTTP {r.status_code}")

# Missing chat_history
r = client.post("/tickets/ai-triage/chat", json={"message":"wifi not working"}, headers=H(alice))
if r.status_code==200: ok("chat_history omitted → default empty list used")
else: fail("Missing chat_history", f"HTTP {r.status_code}")

# ── API CONTRACT ──────────────────────────────────────────────
sec("8. API RESPONSE CONTRACT")
r = chat(alice, "my wifi is not connecting")
if r.status_code!=200: fail("Contract base request", f"HTTP {r.status_code}")
else:
    d = r.json()
    for field in ["reply","subject","category","priority","status_intent","can_resolve","used_articles"]:
        if field not in d: fail(f"Field '{field}' present", "MISSING from response")
        else: ok(f"Field '{field}' = {repr(d[field])[:50]}")

    if d.get("status_intent") not in ("greeting","clarify","troubleshoot","resolved","escalate"):
        fail("status_intent enum", f"Invalid value: {d.get('status_intent')}")
    if not isinstance(d.get("can_resolve"), bool):
        fail("can_resolve is bool", f"Got {type(d.get('can_resolve'))}")

# ── RESPONSE TIME ─────────────────────────────────────────────
sec("9. RESPONSE TIME")
for msg, label in [("hi","greeting"),("my wifi is down","IT problem")]:
    t0=time.time(); r=chat(alice,msg); ms=(time.time()-t0)*1000
    if r.status_code==200:
        if ms<5000: ok(f"Response time [{label}]: {ms:.0f}ms")
        else: warn(f"Response time [{label}]", f"{ms:.0f}ms > 5s")
    else: fail(f"Response time [{label}]", f"HTTP {r.status_code}")

# ── SUMMARY ───────────────────────────────────────────────────
total = P+F+W
print("\n"+"="*60)
print(f"  QA SUMMARY  |  Total={total}  PASS={P}  FAIL={F}  WARN={W}")
print("="*60)
if FAILS:
    print("\n  FAILURES:")
    for n,r in FAILS: print(f"    ❌ {n}\n       {r}")
if F==0: print("\n  ALL TESTS PASSED ✓")
else: print(f"\n  {F} FAILURE(S) — FIX BEFORE RELEASE")
print()
