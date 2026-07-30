import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.automation.password_finder import RadioPasswordFinder

finder = RadioPasswordFinder()

# Debug step by step
import urllib.request, urllib.parse, http.cookiejar, ssl, json

cj = http.cookiejar.CookieJar()
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
opener = urllib.request.build_opener(
    urllib.request.HTTPCookieProcessor(cj),
    urllib.request.HTTPSHandler(context=ctx),
)

res = finder._try_login_robust('http://192.168.1.3', 'cednet', 'GCrouter@734', 'ZTE')
print('RESULT OF _try_login_robust:', res)
