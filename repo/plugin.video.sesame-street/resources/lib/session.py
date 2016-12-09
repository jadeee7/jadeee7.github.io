import re
from resources.lib import common, settings

def getCookie():
  cookie = ['COOKIE_SUPPORT=true']
  cookie.append(settings.sessionCookie)
  return ';'.join(cookie)

def setCookie(cookie):
  settings.set('cookie', ';'.join(cookie))

def parseCookieHeaders(result):
  cookie = []
  resinfo = re.split("[\r\n]+", str(result.info()))
  for info in resinfo:
    cookiematch = re.findall("^Set-Cookie:\s(.*)$", info)
    if len(cookiematch) > 0:
      cookie.append(cookiematch[0])
      setCookie(cookie)
  return cookie
