import urllib, urllib2
import json, inspect
import xbmc, xbmcgui, xbmcplugin

from resources.lib import common, settings

def filestack(depth=2):
  stack = inspect.stack()[depth]
  file = stack[1].split('/')
  return (file[len(file)-1], stack[2], stack[3])

def log(txt):
  if settings.generalDebug == False:
    return
  if isinstance (txt, str):
    txt = txt.decode("utf-8")
  (file, line, func) = filestack()
  message = u'%s: (%s, %s, %s) - %s' % ('SESAMESTREET', file, line, func, txt)
  xbmc.log(msg=message.encode("utf-8"), level=xbmc.LOGDEBUG)

def build_url(query):
  return common.base_url + '?' + urllib.urlencode(query)

def getHTML(uri, mobile=False):
  if mobile == True:
    url = common.sesame_m_base_url + '/' + uri
  else:
    url = common.sesame_base_url + '/' + uri
  html = urllib.urlopen(url)
  return html.read()
