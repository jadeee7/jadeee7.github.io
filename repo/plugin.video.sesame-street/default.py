import sys, re
import urllib, urllib2, urlparse
import json
import xbmcgui
import xbmcplugin

from BeautifulSoup import BeautifulSoup as bsoup

from resources.lib import common, settings, utils, session, menu

xbmcplugin.setContent(common.addon_handle, 'movies')

def fetch_vids(filters={}, reset=False):
  post_data = {
    'serviceClassName': 'org.sesameworkshop.service.UmpServiceUtil',
    'serviceMethodName': 'getMediaItems',
    'serviceParameters': ['criteria','capabilities','resultsBiasingPolicy','context'],
    'criteria': {
      'qty': settings.listsVideonum,
      'reset': reset,
      'type': 'video',
      'filters': filters
    },
    'capabilities': {},
    'resultsBiasingPolicy': '',
    'context': {}
  }
  
  # check for age restriction
  if settings.filterAgegroup > 0:
    post_data['criteria']['filters']['age'] = settings.filterAgegroup
  
  utils.log(post_data)
  headers = {'Content-Type': 'application/x-www-form-urlencoded', 'Cookie': session.getCookie()}
  req = urllib2.Request(common.sesame_base_url + '/c/portal/json_service', urllib.urlencode(post_data), headers)
  res = urllib2.urlopen(req)
  session.parseCookieHeaders(res)
  data = json.load(res)
  if len(data['content']) == 0:
    return False
  return data['content']

def list_vids(videos):
  items = []
  for video in videos:
    if len(video['source']) == 0:
      continue
    
    item = {
      'uid': video['sesameItemId'],
      'file': {
        'url': video['source'][0]['fileName'],
        'codec': video['source'][0]['codec'],
        'bitrate': video['source'][0]['bitRate'],
      },
      'title': video['title'],
      'description': video['description'],
      'images': {
        'small': common.sesame_base_url + video['thumbnailSmall'],
        'medium': common.sesame_base_url + video['thumbnailLarge'],
        'large': common.sesame_base_url + video['poster']
      },
      'cast': str(video['character']).split(';'),
      'width': float(video['width']),
      'height': float(video['height']),
    }
    menu.addVideoItem(item, video)
    items.append(item)
  settings.setobj('temp video list', items)

ok = True
page = common.args.get('page', None)
if page == 'topics':
  html = utils.getHTML('videos')
  lis = bsoup(html).find('select', {'class':re.compile("filter-topic")}).findAll('option')
  for item in lis:
    if item['value'] == '':
      continue
    menu.addFolderItem(item.string, {'page':'list_vids','reset':1,'topic':int(item['value'])})

elif page == 'recent':
  videos = fetch_vids(reset=True)
  list_vids(videos)
  menu.moreVideosBtn()

elif page == 'muppets':
  # get JSON-formatted names
  html = utils.getHTML('ump-portlet/js/sw/sw.ump.js')
  match = re.findall("muppets\s+:\s+\[([\s\"a-zA-Z\|\,]+)\]", html)
  match = re.findall("\"([a-zA-Z\s\|]+)\"", match[0])
  muppets = {}
  for matchi in match:
    muppets.update({matchi.split('|')[0]: {'json-name': matchi.split('|')[1]}})
  
  # get pretty names and pictures
  if settings.generalMuppetPictures == True:
    html = utils.getHTML('muppets', True)
    lis = bsoup(html).find('ul', {'id':'muppet-slideshow'}).findAll('li', {'class':re.compile("section")})
    for item in lis:
      m_name = item.a['href'][item.a['href'].index('/muppets/') + len('/muppets/'):]
      m_name_pretty = ' '.join(m_name.split('-')).title()
      for k,muppet in muppets.items():
        if re.search(muppet['json-name'], m_name_pretty) != None:
          muppets[k].update({'pretty-name': m_name_pretty, 'image-src': item.a.img['src']})
          break;
  
  for k,muppet in muppets.items():
    title = muppet.get('pretty-name', muppet['json-name'])
    query = {'page':'list_vids','reset':1,'muppet':muppet['json-name']}
    icon = thumb = muppet.get('image-src', '')
    menu.addFolderItem(title, query, icon, thumb)

elif page == 'list_vids':
  utils.log(common.args)
  filters = {}
  if common.args.get('muppet'):
    filters['muppet'] = common.args['muppet']
  if common.args.get('topic'):
    filters['topic'] = int(common.args['topic'])
  
  videos = fetch_vids(filters, bool(int(common.args.get('reset', 0))))
  if videos==False:
    ok = False
    xbmcgui.Dialog().ok(common.addon_name, common.l(30601))
  else:
    list_vids(videos)
    menu.moreVideosBtn(common.args)

elif page == 'playall':
  playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
  playlist.clear()
  tempvs = settings.getobj('temp video list')
  for tempv in tempvs:
    li = menu.formatVideoItemBasic(tempv)
    playlist.add(tempv['file']['url'], li)
  xbmc.executebuiltin('playlist.playoffset(video , 0)')

else:
  menu.addFolderItem(common.l(30502), {'page':'recent'})
  menu.addFolderItem(common.l(30503), {'page':'muppets'})
  menu.addFolderItem(common.l(30504), {'page':'topics'})


if ok:
  xbmcplugin.endOfDirectory(common.addon_handle)
