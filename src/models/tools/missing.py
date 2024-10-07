"""
查找指定演员缺少作品
"""
import json
import os
import re
import time

from lxml import etree

from models.base.path import get_main_path
from models.base.utils import get_used_time
from models.base.web import get_html, scraper_html
from models.config.config import config
from models.config.resources import resources
from models.core.file import get_file_info, movie_lists
from models.core.flags import Flags
from models.signals import signal


def _scraper_web(url):
    result, html = scraper_html(url)
    if not result:
        signal.show_log_text('Request Error: %s' % html)
        return ''
    if "The owner of this website has banned your access based on your browser's behaving" in html:
        signal.show_log_text('Due to too many requests, the JavDB website has temporarily banned access from your current IP!! Visit javdb.com for details!%s' % html)
        return ''
    if 'Cloudflare' in html:
        signal.show_log_text('Blocked by Cloudflare 5 second shield! Please try replacing cookies!')
        return ''
    return html


def _get_actor_numbers(actor_url, actor_single_url):
    """
    获取演员的番号列表
    """
    # 获取单体番号
    next_page = True
    number_single_list = set()
    i = 1
    while next_page:
        page_url = actor_url + '?page=%s' % i + '&t=s'
        result, html = get_html(page_url)
        if not result:
            result, html = scraper_html(page_url)
        if not result:
            return
        if 'pagination-next' not in html or i >= 60:
            next_page = False
            if i == 60:
                signal.show_log_text('   60 page limit reached!!! (JavDB can only return the first 60 pages of data for an actor!）')
        html = etree.fromstring(html, etree.HTMLParser())
        actor_info = html.xpath('//a[@class="box"]')
        for each in actor_info:
            video_number = each.xpath('div[@class="video-title"]/strong/text()')[0]
            number_single_list.add(video_number)
        i += 1
    Flags.actor_numbers_dic[actor_single_url] = number_single_list

    # 获取全部番号
    next_page = True
    i = 1
    while next_page:
        page_url = actor_url + '?page=%s' % i
        html = _scraper_web(page_url)
        if len(html) < 1:
            return
        if 'pagination-next' not in html or i >= 60:
            next_page = False
            if i == 60:
                signal.show_log_text('   60 page limit reached! ! ! (JavDB can only return the first 60 pages of data for an actor!）')
        html = etree.fromstring(html, etree.HTMLParser(encoding="utf-8"))
        actor_info = html.xpath('//a[@class="box"]')
        for each in actor_info:
            video_number = each.xpath('div[@class="video-title"]/strong/text()')[0]
            video_title = each.xpath('div[@class="video-title"]/text()')[0]
            video_date = each.xpath('div[@class="meta"]/text()')[0].strip()
            video_url = 'https://javdb.com' + each.get('href')
            video_download_link = each.xpath('div[@class="tags has-addons"]/span[@class="tag is-success"]/text()')
            video_sub_link = each.xpath('div[@class="tags has-addons"]/span[@class="tag is-warning"]/text()')
            download_info = '   '
            if video_sub_link:
                download_info = '🧲  🀄️'
            elif video_download_link:
                download_info = '🧲    '
            if video_number in number_single_list:
                single_info = '单体'
            else:
                single_info = '\u3000\u3000'
            time_list = re.split(r'[./-]', video_date)
            if len(time_list[0]) == 2:
                video_date = '%s/%s/%s' % (time_list[2], time_list[0], time_list[1])
            else:
                video_date = '%s/%s/%s' % (time_list[0], time_list[1], time_list[2])
            # self.show_log_text('{}  {:<10}{:\u3000>5}   {}'.format(video_date, video_number, download_info, video_url))
            Flags.actor_numbers_dic[actor_url].update(
                {video_number: [video_number, video_date, video_url, download_info, video_title, single_info]})
        i += 1


def _get_actor_missing_numbers(actor_name, actor_url, actor_flag):
    """
    获取演员缺少的番号列表
    """
    start_time = time.time()
    actor_single_url = actor_url + '?t=s'

    # 获取演员的所有番号，如果字典有，就从字典读取，否则去网络请求
    if not Flags.actor_numbers_dic.get(actor_url):
        Flags.actor_numbers_dic[actor_url] = {}
        Flags.actor_numbers_dic[actor_single_url] = {}  # 单体作品
        _get_actor_numbers(actor_url, actor_single_url)  # 如果字典里没有该演员主页的番号，则从网络获取演员番号

    # 演员信息排版和显示
    actor_info = Flags.actor_numbers_dic.get(actor_url)
    len_single = len(Flags.actor_numbers_dic.get(actor_single_url))
    signal.show_log_text('🎉 Obtained! Found in total [ %s ] number quantity（%s）number of monomers（%s）(%ss)' % (
        actor_name, len(actor_info), len_single, get_used_time(start_time)))
    if actor_info:
        actor_numbers = actor_info.keys()
        all_list = set()
        not_download_list = set()
        not_download_magnet_list = set()
        not_download_cnword_list = set()
        for actor_number in actor_numbers:
            video_number, video_date, video_url, download_info, video_title, single_info = actor_info.get(
                actor_number)
            if actor_flag:
                video_url = video_title[:30]
            number_str = (
                '{:>13}  {:<10} {}  {:\u3000>5}   {}'.format(video_date, video_number, single_info, download_info,
                                                             video_url))
            all_list.add(number_str)
            if actor_number not in Flags.local_number_set:
                not_download_list.add(number_str)
                if '🧲' in download_info:
                    not_download_magnet_list.add(number_str)

                if '🀄️' in download_info:
                    not_download_cnword_list.add(number_str)
            elif actor_number not in Flags.local_number_cnword_set and '🀄️' in download_info:
                not_download_cnword_list.add(number_str)

        all_list = sorted(all_list, reverse=True)
        not_download_list = sorted(not_download_list, reverse=True)
        not_download_magnet_list = sorted(not_download_magnet_list, reverse=True)
        not_download_cnword_list = sorted(not_download_cnword_list, reverse=True)

        signal.show_log_text('\n👩 [ %s ] All network numbers of(%s)...\n%s' % (actor_name, len(all_list), ('=' * 97)))
        if all_list:
            for each in all_list:
                signal.show_log_text(each)
        else:
            signal.show_log_text('🎉 There are no missing numbers...\n')

        signal.show_log_text(
            '\n👩 [ %s ] Missing local number(%s)...\n%s' % (actor_name, len(not_download_list), ('=' * 97)))
        if not_download_list:
            for each in not_download_list:
                signal.show_log_text(each)
        else:
            signal.show_log_text('🎉 There are no missing numbers...\n')

        signal.show_log_text('\n👩 [ %s ] Locally missing magnetic number(%s)...\n%s' % (
            actor_name, len(not_download_magnet_list), ('=' * 97)))
        if not_download_magnet_list:
            for each in not_download_magnet_list:
                signal.show_log_text(each)
        else:
            signal.show_log_text('🎉 There are no missing numbers...\n')

        signal.show_log_text('\n👩 [ %s ] Numbers with subtitles that are missing locally(%s)...\n%s' % (
            actor_name, len(not_download_cnword_list), ('=' * 97)))
        if not_download_cnword_list:
            for each in not_download_cnword_list:
                signal.show_log_text(each)
        else:
            signal.show_log_text('🎉 There are no missing numbers...\n')


def check_missing_number(actor_flag):
    """
    检查缺失番号
    """
    signal.change_buttons_status.emit()
    start_time = time.time()
    json_data_new = {}

    # 获取资源库配置
    movie_type = config.media_type
    movie_path = config.local_library.replace('\\', '/')  # 用户设置的扫描媒体路径
    movie_path_list = set(re.split(r'[,，]', movie_path))  # 转成集合，去重
    new_movie_path_list = set()
    for i in movie_path_list:
        if i == '':  # 为空时，使用主程序目录
            i = get_main_path()
        new_movie_path_list.add(i)
    new_movie_path_list = sorted(new_movie_path_list)

    # 遍历本地资源库
    if Flags.local_number_flag != new_movie_path_list:
        signal.show_log_text('')
        signal.show_log_text(
            '\nLocal resource library address:\n   %s\n\n>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>\n⏳ Start traversing the local resource library to get the latest list of local videos...\n   Tip: The first query will update the local video data each time it is launched. (About 1000 videos/30 seconds. If there are many videos, please wait patiently.）' % '\n   '.join(
                new_movie_path_list))
        all_movie_list = []
        for i in new_movie_path_list:
            movie_list = movie_lists('', movie_type, i)  # 获取所有需要刮削的影片列表
            all_movie_list.extend(movie_list)
        signal.show_log_text(
            '🎉 Obtained! Total number of videos found（%s）(%ss)' % (len(all_movie_list), get_used_time(start_time)))

        # 获取本地番号
        start_time_local = time.time()
        signal.show_log_text(
            '\n>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>\n⏳ Start getting local video number information...')
        local_number_list = resources.userdata_path('number_list.json')
        if not os.path.exists(local_number_list):
            signal.show_log_text(
                '   Tip: The number information data of the local video is being generated...（The first time is slow, please be patient, in the future you just need to find new videos, it will be very fast）')
            with open(local_number_list, 'w', encoding='utf-8') as f:
                f.write('{}')
        with open(local_number_list, 'r', encoding='utf-8') as data:
            json_data = json.load(data)
        for movie_path in all_movie_list:
            nfo_path = os.path.splitext(movie_path)[0] + '.nfo'
            json_data_temp = {}
            number = ''
            if json_data.get(movie_path):
                number, has_sub = json_data.get(movie_path)

            else:
                if os.path.exists(nfo_path):
                    with open(nfo_path, 'r', encoding='utf-8') as f:
                        nfo_content = f.read()
                    number_result = re.findall(r'<num>(.+)</num>', nfo_content)
                    if number_result:
                        number = number_result[0]

                        if '<genre>中文字幕</genre>' in nfo_content or '<tag>中文字幕</tag>' in nfo_content:
                            has_sub = True
                        else:
                            has_sub = False
                if not number:
                    json_data_temp, number, folder_old_path, file_name, file_ex, sub_list, file_show_name, file_show_path = get_file_info(
                        movie_path, copy_sub=False)
                    has_sub = json_data_temp['has_sub']  # 视频中文字幕标识
                cn_word_icon = '🀄️' if has_sub else ''
                signal.show_log_text('   New number found:{:<10} {}'.format(number, cn_word_icon))
            temp_number = re.findall(r'\d{3,}([a-zA-Z]+-\d+)', number)  # 去除前缀，因为 javdb 不带前缀
            number = temp_number[0] if temp_number else number
            json_data_new[movie_path] = [number, has_sub]  # 用新表，更新完重新写入到本地文件中
            Flags.local_number_set.add(number)  # 添加到本地番号集合
            if has_sub:
                Flags.local_number_cnword_set.add(number)  # 添加到本地有字幕的番号集合

        with open(local_number_list, 'w', encoding='utf-8') as f:
            json.dump(
                json_data_new,
                f,
                ensure_ascii=False,
                sort_keys=True,
                indent=4,
                separators=(',', ': '),
            )
        Flags.local_number_flag = new_movie_path_list
        signal.show_log_text(
            '🎉 Obtained! Total number of numbers obtained（%s）(%ss)' % (len(json_data_new), get_used_time(start_time_local)))

    # 查询演员番号
    if config.actors_name:
        actor_list = re.split(r'[,，]', config.actors_name)
        signal.show_log_text(
            '\n>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>\n🔍 Actors to be queried:\n   %s' % (
                ', '.join(actor_list)))
        for actor_name in actor_list:
            if not actor_name:
                continue
            if 'http' in actor_name:
                actor_url = actor_name
            else:
                actor_url = resources.get_actor_data(actor_name).get('href')
            if actor_url:
                signal.show_log_text(
                    '\n>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>\n⏳ Get from JavDB [ %s ] List of all numbers...' % actor_name)
                _get_actor_missing_numbers(actor_name, actor_url, actor_flag)
            else:
                signal.show_log_text(
                    '\n🔴 not found [ %s ] Home page address, you can fill in the actors JavDB home page address to replace the actors name...' % actor_name)
    else:
        signal.show_log_text('\n🔴 There are no actors to search for!')

    signal.show_log_text('\n🎉 Inquiry completed! When sharing(%ss)' % (get_used_time(start_time)))
    signal.reset_buttons_status.emit()
