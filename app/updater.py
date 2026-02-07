import requests

VERSION="1.0"

def check_update():
    try:
        latest = requests.get("https://server/version.txt").text.strip()
        return latest != VERSION
    except:
        return False
