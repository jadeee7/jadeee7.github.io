"""
    SALTS XBMC Addon
    Copyright (C) 2014 tknorris

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
import HTMLParser
import random
import re
import string
import urllib
import urlparse
import kodi
import log_utils
import dom_parser
from salts_lib import scraper_utils
from salts_lib.constants import FORCE_NO_MATCH
from salts_lib.constants import QUALITIES
from salts_lib.constants import VIDEO_TYPES
import scraper


QUALITY_MAP = {'HD720P': QUALITIES.HD720, 'HD720P+': QUALITIES.HD720, 'DVDRIP/STANDARDDEF': QUALITIES.HIGH,
               'SD/DVD480P': QUALITIES.HIGH, 'DVDSCREENER': QUALITIES.HIGH, 'FASTSTREAM/LOWQUALITY': QUALITIES.HIGH}
BASE_URL = 'http://www.icefilms.info'
LIST_URL = BASE_URL + '/membersonly/components/com_iceplayer/video.php?h=374&w=631&vid=%s&img='
AJAX_URL = '/membersonly/components/com_iceplayer/video.phpAjaxResp.php?id=%s&s=%s&iqs=&url=&m=%s&cap= &sec=%s&t=%s'

class Scraper(scraper.Scraper):
    base_url = BASE_URL

    def __init__(self, timeout=scraper.DEFAULT_TIMEOUT):
        self.timeout = timeout
        self.base_url = kodi.get_setting('%s-base_url' % (self.get_name()))

    @classmethod
    def provides(cls):
        return frozenset([VIDEO_TYPES.TVSHOW, VIDEO_TYPES.EPISODE, VIDEO_TYPES.MOVIE])

    @classmethod
    def get_name(cls):
        return 'IceFilms'

    def resolve_link(self, link):
        url, query = link.split('?', 1)
        data = urlparse.parse_qs(query, True)
        url = urlparse.urljoin(self.base_url, url)
        url += '?s=%s&t=%s&app_id=SALTS' % (data['id'][0], data['t'][0])
        list_url = LIST_URL % (data['t'][0])
        headers = {'Referer': list_url}
        html = self._http_get(url, data=data, headers=headers, cache_limit=.25)
        match = re.search('url=(http.*)', html)
        if match:
            url = urllib.unquote_plus(match.group(1))
            return url

    def get_sources(self, video):
        source_url = self.get_url(video)
        sources = []
        if source_url and source_url != FORCE_NO_MATCH:
            try:
                url = urlparse.urljoin(self.base_url, source_url)
                html = self._http_get(url, cache_limit=2)

                pattern = '<iframe id="videoframe" src="([^"]+)'
                match = re.search(pattern, html)
                url = urlparse.urljoin(self.base_url, match.group(1))
                html = self._http_get(url, cache_limit=.5)

                match = re.search('lastChild\.value="([^"]+)"(?:\s*\+\s*"([^"]+))?', html)
                secret = ''.join(match.groups(''))

                match = re.search('"&t=([^"]+)', html)
                t = match.group(1)
                
                match = re.search('(?:\s+|,)s\s*=(\d+)', html)
                s_start = int(match.group(1))
                
                match = re.search('(?:\s+|,)m\s*=(\d+)', html)
                m_start = int(match.group(1))
                
                for fragment in dom_parser.parse_dom(html, 'div', {'class': 'ripdiv'}):
                    match = re.match('<b>(.*?)</b>', fragment)
                    if match:
                        q_str = match.group(1).replace(' ', '').upper()
                        quality = QUALITY_MAP.get(q_str, QUALITIES.HIGH)
                    else:
                        quality = QUALITIES.HIGH

                    pattern = '''onclick='go\((\d+)\)'>([^<]+)(<span.*?)</a>'''
                    for match in re.finditer(pattern, fragment):
                        link_id, label, host_fragment = match.groups()
                        source = {'multi-part': False, 'quality': quality, 'class': self, 'version': label, 'rating': None, 'views': None, 'direct': False}
                        source['host'] = re.sub('(</?[^>]*>)', '', host_fragment)
                        s = s_start + random.randint(3, 1000)
                        m = m_start + random.randint(21, 1000)
                        url = AJAX_URL % (link_id, s, m, secret, t)
                        source['url'] = url
                        sources.append(source)
            except Exception as e:
                log_utils.log('Failure (%s) during icefilms get sources: |%s|' % (str(e), video), log_utils.LOGWARNING)
        return sources

    def search(self, video_type, title, year, season=''):
        results = []
        if video_type == VIDEO_TYPES.MOVIE:
            url = urlparse.urljoin(self.base_url, '/movies/a-z/')
        else:
            url = urlparse.urljoin(self.base_url, '/tv/a-z/')

        if title.upper().startswith('THE '):
            search_title = title[4:5]
        elif title.upper().startswith('A '):
            search_title = title[2:3]
        else:
            search_title = title
            
        if title[:1] in string.digits:
            first_letter = '1'
        else:
            first_letter = search_title[:1]
        url = url + first_letter.upper()
        
        html = self._http_get(url, cache_limit=48)
        norm_title = scraper_utils.normalize_title(title)
        pattern = 'class=star.*?href=([^>]+)>(.*?)</a>'
        for match in re.finditer(pattern, html, re.DOTALL):
            match_url, match_title_year = match.groups()
            match = re.search('(.*?)\s+\((\d{4})\)', match_title_year)
            if match:
                match_title, match_year = match.groups()
            else:
                match_title = match_title_year
                match_year = ''
            
            if norm_title in scraper_utils.normalize_title(match_title) and (not year or not match_year or year == match_year):
                result = {'url': match_url, 'title': scraper_utils.cleanse_title(match_title), 'year': match_year}
                results.append(result)
        return results

    def _get_episode_url(self, show_url, video):
        episode_pattern = 'href=(/ip\.php[^>]+)>%sx0?%s\s+' % (video.season, video.episode)
        title_pattern = 'class=star>\s*<a href=(?P<url>[^>]+)>(?:\d+x\d+\s+)+(?P<title>[^<]+)'
        return self._default_get_episode_url(show_url, video, episode_pattern, title_pattern)
