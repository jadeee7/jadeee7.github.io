import sys
import urlparse
import xbmcaddon

addon         = xbmcaddon.Addon()
addon_name    = addon.getAddonInfo('name')
addon_handle  = int(sys.argv[1])
base_url      = sys.argv[0]

l = addon.getLocalizedString

args = urlparse.parse_qs(sys.argv[2][1:])
# strip single-element tuples
for k, arg in args.items():
  if len(arg) == 1:
    args[k] = arg[0]

sesame_base_domain = 'sesamestreet.org'
sesame_base_url = 'http://www.' + sesame_base_domain
sesame_m_base_url = 'http://m.' + sesame_base_domain

tvshow_title = l(30001)
tvshow_imdb = 'tt0063951'
