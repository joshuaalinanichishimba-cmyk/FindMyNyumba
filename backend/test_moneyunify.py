import requests, time
from app.core.config import settings
num = input("Your number (0965...): ").strip()
r = requests.post("https://api.moneyunify.one/payments/request",
    headers={"Content-Type":"application/x-www-form-urlencoded","Accept":"application/json"},
    data={"from_payer":num,"amount":"1","auth_id":settings.MONEYUNIFY_AUTH_ID}, timeout=40)
print("REQUEST:", r.status_code, r.text[:250])
if r.status_code < 400 and not r.json().get("isError"):
    txid = r.json()["data"]["transaction_id"]
    print("Approve on your phone. Transaction:", txid)
    for i in range(10):
        time.sleep(6)
        v = requests.post("https://api.moneyunify.one/payments/verify",
            headers={"Content-Type":"application/x-www-form-urlencoded","Accept":"application/json"},
            data={"transaction_id":txid,"auth_id":settings.MONEYUNIFY_AUTH_ID}, timeout=40)
        print(f"poll {i+1}:", v.json().get("data",{}).get("status"))
