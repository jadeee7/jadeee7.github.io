import sys, pickle
from resources.lib import common

generalMuppetPictures = common.addon.getSetting('general muppetpictures') == 'true'
generalDebug = common.addon.getSetting('general debug') == 'true'
listsVideonum = common.addon.getSetting('lists videonum')
listsMoreBtn = common.addon.getSetting('lists morebtn') == 'true'
filterAgegroup = common.addon.getSetting('filter agegroup')

# set during runtime, not by the user
sessionCookie = common.addon.getSetting('cookie')

def get(id):
  return common.addon.getSetting(id)

def set(id, value):
  common.addon.setSetting(id, value)

def getobj(id):
  try:
    return pickle.loads(get(id))
  except:
    return False

def setobj(id, obj):
  try:
    set(id, pickle.dumps(obj))
  except:
    return False
