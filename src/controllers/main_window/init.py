import traceback
import webbrowser

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QAction, QMenu, QSystemTrayIcon, QTreeWidgetItem

from models.config.config import config
from models.config.resources import resources
from models.core.flags import Flags
from models.core.utils import get_movie_path_setting
from models.signals import signal


def Init_Ui(self):
    self.setWindowTitle("MDCx")  # 设置任务栏标题
    self.setWindowIcon(QIcon(resources.icon_ico))  # 设置任务栏图标
    self.setWindowOpacity(1.0)  # 设置窗口透明度
    if config.is_windows:
        self.setFixedSize(self.width(), self.height())  # 禁止调整窗口大小(mac 平台禁止后最小化没反应，恢复时顶部会残留标题栏)
    self.setAttribute(Qt.WA_TranslucentBackground)  # 设置窗口背景透明
    self.Ui.progressBar_scrape.setValue(0)  # 进度条清0
    self.Ui.progressBar_scrape.setTextVisible(False)  # 不显示进度条文字
    self.Ui.pushButton_start_cap.setCheckable(True)  # 主界面开始按钮可点状态
    self.init_QTreeWidget()  # 初始化树状图
    self.Ui.label_poster.setScaledContents(True)  # 图片自适应窗口
    self.Ui.label_thumb.setScaledContents(True)  # 图片自适应窗口
    self.Ui.pushButton_right_menu.setIcon(QIcon(resources.right_menu))
    self.Ui.pushButton_right_menu.setToolTip(' Right Click Menu ')
    self.Ui.pushButton_play.setIcon(QIcon(resources.play_icon))
    self.Ui.pushButton_play.setToolTip(' Play ')
    self.Ui.pushButton_open_folder.setIcon(QIcon(resources.open_folder_icon))
    self.Ui.pushButton_open_folder.setToolTip(' Open Folder ')
    self.Ui.pushButton_open_nfo.setIcon(QIcon(resources.open_nfo_icon))
    self.Ui.pushButton_open_nfo.setToolTip(' Edit NFO ')
    self.Ui.pushButton_tree_clear.setIcon(QIcon(resources.clear_tree_icon))
    self.Ui.pushButton_tree_clear.setToolTip(' Clear Results List')
    self.Ui.pushButton_close.setToolTip(' Close ')
    self.Ui.pushButton_min.setToolTip(' Minimize ')
    self.Ui.pushButton_main.setIcon(QIcon(resources.home_icon))
    self.Ui.pushButton_log.setIcon(QIcon(resources.log_icon))
    self.Ui.pushButton_tool.setIcon(QIcon(resources.tool_icon))
    self.Ui.pushButton_setting.setIcon(QIcon(resources.setting_icon))
    self.Ui.pushButton_net.setIcon(QIcon(resources.net_icon))
    help_icon = QIcon(resources.help_icon)
    self.Ui.pushButton_about.setIcon(help_icon)
    self.Ui.pushButton_tips_normal_mode.setIcon(help_icon)
    self.Ui.pushButton_tips_normal_mode.setToolTip('''<html><head/><body><p><b>Normal Mode:</b><br/>1）Suitable for poster wall users. The normal mode will connect to the Internet to scrape video field information, and perform a series of automated operations such as translating field information, moving and renaming video files and folders, downloading pictures, stills, trailers, adding subtitles, 4K watermarks, etc.<br/>2）Please set the scraping directory in "Settings" - "Scraping Directory" - "Directory to be scraped"<br/>3）To scrape websites, please set it up in "Settings" - "Scraping Websites". Some websites require proxy access. You can set up proxy and non-translation URLs in "Settings" - "Proxy". You can click "Detect Network" on the left to check network connectivity<br/>\
        4）Please set field translation in "Settings" - "Translation"<br/>5）Please set pictures, stills and trailers in "Settings" - "Downloads"<br/>6）Please set the video file naming in "Settings"-"Naming"<br/>7）If you do not need to rename after scraping, please set "Rename file after scraping successfully" below to "Off"<br/>8）If you do not need to move files after scraping, please set "Move files after scraping successfully" below to "Off"<br/>9）If you want to scrape automatically, please check "Automatic scraping" in "Settings" - "Advanced"<br/>10）You can study other settings and functions by yourself</p></body></html>''')
    self.Ui.pushButton_tips_sort_mode.setIcon(help_icon)
    self.Ui.pushButton_tips_sort_mode.setToolTip(
        '''<html><head/><body><p><b>Video mode:</b><br/>1. Suitable for situations where a picture wall is not required. Video mode will scrape video-related field information online, and then rename and move video files according to the naming rules set in "Settings" - "Naming"<br/>2. Only videos will be organized, images and nfo files will not be downloaded or renamed<br/>3. If you are a poster wall user, please do not use video mode.</p></body></html>''')
    self.Ui.pushButton_tips_update_mode.setIcon(help_icon)
    self.Ui.pushButton_tips_update_mode.setToolTip('''<html><head/><body><p><b>Update Mode:</b><br/>1. Suitable for situations where videos have been classified. The update mode will re-scrape and update some information without changing the file location structure.<br/>2. The update rules are defined in the "Update Mode Rules" below:<br/>-1) If you only update the video file name, please select "Only Update C". For the video file name naming rules, please go to "Settings-" "Naming" Set in "Rules"<br/>-2) If you want to update the directory name where the video is located, please select "Update B and C"; if you want to update the upper-level directory of the video directory, please check "Also update directory A"<br/>-3) if you want to create another first-level directory for the video in the video directory, please select "Create D Directory"<br/>\
        3. The update mode will scrape and update all videos under the "to-be-scraped directory" online.<br/>4. When some content has not been updated successfully and you want to scrape only this content next time, please select "Read Mode" and check "When nfo does not exist, scrape and execute update mode rules", it will query and read All local nfo files of the video (not connected to the Internet). When there is no nfo file, the network scraping will be automatically performed.<br/>5. When some content cannot be scraped, you can go to the "Log" page, click the "Failure" button, and click the save button in the lower left corner to save the failure list locally, and then manually view and process the video information.</p></body></html>''')
    self.Ui.pushButton_tips_read_mode.setIcon(help_icon)
    self.Ui.pushButton_tips_read_mode.setToolTip('''<html><head/><body><p><b>Read mode:</b><br/>\
        1. The read mode reads the field information in the local nfo file and can view or update video naming without the need for an Internet connection.<br/>\
        2. If you only want to view and check whether there are problems with the scraped video information and pictures, you can:<br/>\
        -1) Uncheck "Reorganize and classify files that have been successfully scraped locally";<br/>\
        -2) Uncheck "Local self-scraping of failed files, re-scraping".<br/>\
        3. If you want to quickly reorganize categories (not connected to the Internet), you can:<br/>\
        -1) Check "Local files that have been successfully scraped, reorganize and classify";<br/>\
        -2) Customize the update rules in the "Update Mode Rules" below.<br/>\
        The software will perform renaming operations according to the "Update Mode Rules" and the setting items in "Settings" - "Naming".<br/>\
        4. If you want to re-translate the mapping fields, you can:<br/>\
        -1) Check "Local files that have been successfully scraped, reorganize and classify";<br/>\
        -2) Check "Retranslate mapping nfo information".<br/>\
        The software will re-translate and map each field according to the setting items in "Settings" - "Translation".<br/>\
        6. If you want to re-download pictures and other files (requires Internet connection), you can:<br/>\
        -1) Check "Local files that have been successfully scraped, reorganize and classify";<br/>\
        -2) Check "Re-download pictures and other files".<br/>\
        The software will perform operations such as downloading and retaining according to the setting items in "Settings" - "Downloads".</p></body></html>''')
    self.Ui.pushButton_tips_soft.setIcon(help_icon)
    self.Ui.pushButton_tips_soft.setToolTip('''<html><head/><body><p><b>Create a soft link:</b><br/>\
        1. Soft links are suitable for network disk users. A soft link is like a shortcut, a symbolic link to a real file. It is small in size, supports cross-disk pointing, and does not affect the original file after deletion (when the original file is deleted, the soft link will become invalid).<br/>\
        <span style=" font-weight:700; color:red;">Notice:\
        <br/>Windows version: The soft link must be saved on a local disk (platform restriction), while real files can be saved on a network disk or a local disk.<br/>\
        MacOS version: No problem.<br/>\
        Docker version: The full path of the mounting directory needs to be the same as the full path of the actual directory, so that the soft link can point to the actual location and Emby can play it.</span><br/>\

        2. The network disk is affected by network and other factors, and its reading and writing are slow and have many restrictions. When you choose to create a soft link, a soft link file pointing to the network disk video file will be created on the local disk. At the same time, the scraped and downloaded pictures will also be placed on the local disk. Use Emby and Jellyfin to load quickly!<br/>\
        3. Scraping will not move, modify, or rename the original file. It will only read the path location of the original file and use it to create soft links.<br/>\
        4. After the scraping is successful, the soft link file will be created and renamed according to the scraping settings.<br/>\
        5. When scraping fails, soft links will not be created. If you want to create soft links for all files, you can go to [Tools]-[Soft Link Assistant]-[Create Soft Links with One Click])<br/>\
        6. If there is already scraped content in the network disk and you want to transfer the scraped information to the local disk, use the same tool as above and check [Copy scraped pictures and NFO files].<br/>\
        7. Network disk mounting and scraping methods:<br/>\
        -1) Use third-party tools such as CloudDriver, Alist, RaiDrive, etc. to mount the network disk<br/>\
        -2) MDCx sets the directory to be scraped to the network disk video directory, and the output directory to the local disk folder<br/>\
        -3) Select "Create Soft Link" in the settings, save the configuration after setting other configurations, and click to start scraping<br/>\
        -4) Emby and Jellyfin media library path is set to the disk folder saved after local scraping and scanned</p></body></html>''')
    self.Ui.pushButton_tips_hard.setIcon(help_icon)
    self.Ui.pushButton_tips_hard.setToolTip(
        '''<html><head/><body><p><b>Create a hard link:</b><br/>1. Hard links are suitable for PT users. PT user video files are generally stored in NAS. To ensure the upload sharing rate, the original file information cannot be modified.<br/>2. The hard link points to the same hard disk index as the original file, and must be on the same disk as the original file. Using hard links, scraping data can be stored separately on the same disk without affecting the original file information.<br/>3. Delete the hard link and the original file is still there; delete the original file and the hard link is still there. The file will be deleted only if both are deleted.<br/><span style=" font-weight:700; color:#ff2600;">Note: The Mac platform only supports the creation of hard links on local disks (permission issues). For non-local disks, please choose to create soft links. The Windows platform does not have this problem.</span></p></body></html>''')
    self.Ui.textBrowser_log_main_3.hide()  # 失败列表隐藏
    self.Ui.pushButton_scraper_failed_list.hide()
    self.Ui.pushButton_save_failed_list.hide()
    self.Ui.comboBox_custom_website.addItems(config.SUPPORTED_WEBSITES)
    # self.Ui.textBrowser_log_main.document().setMaximumBlockCount(100000)     # 限制日志页最大行数rowCount
    # self.Ui.textBrowser_log_main_2.document().setMaximumBlockCount(30000)     # 限制日志页最大行数rowCount
    self.Ui.textBrowser_log_main.viewport().installEventFilter(self)  # 注册事件用于识别点击控件时隐藏失败列表面板
    self.Ui.textBrowser_log_main_2.viewport().installEventFilter(self)
    self.Ui.pushButton_save_failed_list.setIcon(QIcon(resources.save_failed_list_icon))
    self.Ui.widget_show_success.resize(811, 511)
    self.Ui.widget_show_success.hide()
    self.Ui.widget_show_tips.resize(811, 511)
    self.Ui.widget_show_tips.hide()
    self.Ui.widget_nfo.resize(791, 681)
    self.Ui.widget_nfo.hide()


def Init_Singal(self):
    # region 外部信号量连接
    signal.log_text.connect(self.show_log_text)  # 可视化日志输出
    signal.scrape_info.connect(self.show_scrape_info)  # 可视化日志输出
    signal.net_info.connect(self.show_net_info)  # 可视化日志输出
    signal.set_main_info.connect(self.add_label_info_Thread)
    signal.change_buttons_status.connect(self.change_buttons_status)
    signal.reset_buttons_status.connect(self.reset_buttons_status)
    signal.logs_failed_settext.connect(self.Ui.textBrowser_log_main_3.setText)
    signal.label_result.connect(self.Ui.label_result.setText)
    signal.set_label_file_path.connect(self.Ui.label_file_path.setText)
    signal.view_success_file_settext.connect(self.Ui.pushButton_view_success_file.setText)
    signal.exec_set_processbar.connect(self.set_processbar)
    signal.view_failed_list_settext.connect(self.Ui.pushButton_view_failed_list.setText)
    signal.exec_show_list_name.connect(self.show_list_name)
    signal.exec_exit_app.connect(self.exit_app)
    signal.logs_failed_show.connect(self.Ui.textBrowser_log_main_3.append)
    # endregion

    # region 控件点击
    # self.Ui.treeWidget_number.clicked.connect(self.treeWidget_number_clicked)
    self.Ui.treeWidget_number.selectionModel().selectionChanged.connect(self.treeWidget_number_clicked)
    self.Ui.pushButton_close.clicked.connect(self.pushButton_close_clicked)
    self.Ui.pushButton_min.clicked.connect(self.pushButton_min_clicked)
    self.Ui.pushButton_main.clicked.connect(self.pushButton_main_clicked)
    self.Ui.pushButton_log.clicked.connect(self.pushButton_show_log_clicked)
    self.Ui.pushButton_net.clicked.connect(self.pushButton_show_net_clicked)
    self.Ui.pushButton_tool.clicked.connect(self.pushButton_tool_clicked)
    self.Ui.pushButton_setting.clicked.connect(self.pushButton_setting_clicked)
    self.Ui.pushButton_about.clicked.connect(self.pushButton_about_clicked)
    self.Ui.pushButton_select_local_library.clicked.connect(self.pushButton_select_local_library_clicked)
    self.Ui.pushButton_select_netdisk_path.clicked.connect(self.pushButton_select_netdisk_path_clicked)
    self.Ui.pushButton_select_localdisk_path.clicked.connect(self.pushButton_select_localdisk_path_clicked)
    self.Ui.pushButton_select_media_folder.clicked.connect(self.pushButton_select_media_folder_clicked)
    self.Ui.pushButton_select_media_folder_setting_page.clicked.connect(self.pushButton_select_media_folder_clicked)
    self.Ui.pushButton_select_softlink_folder.clicked.connect(self.pushButton_select_softlink_folder_clicked)
    self.Ui.pushButton_select_sucess_folder.clicked.connect(self.pushButton_select_sucess_folder_clicked)
    self.Ui.pushButton_select_failed_folder.clicked.connect(self.pushButton_select_failed_folder_clicked)
    self.Ui.pushButton_view_success_file.clicked.connect(self.pushButton_view_success_file_clicked)
    self.Ui.pushButton_select_subtitle_folder.clicked.connect(self.pushButton_select_subtitle_folder_clicked)
    self.Ui.pushButton_select_actor_photo_folder.clicked.connect(self.pushButton_select_actor_photo_folder_clicked)
    self.Ui.pushButton_select_config_folder.clicked.connect(self.pushButton_select_config_folder_clicked)
    self.Ui.pushButton_select_actor_info_db.clicked.connect(self.pushButton_select_actor_info_db_clicked)
    self.Ui.pushButton_select_file.clicked.connect(self.pushButton_select_file_clicked)
    self.Ui.pushButton_start_cap.clicked.connect(self.pushButton_start_scrape_clicked)
    self.Ui.pushButton_start_cap2.clicked.connect(self.pushButton_start_scrape_clicked)
    self.Ui.pushButton_show_hide_logs.clicked.connect(self.pushButton_show_hide_logs_clicked)
    self.Ui.pushButton_view_failed_list.clicked.connect(self.pushButton_show_hide_failed_list_clicked)
    self.Ui.pushButton_save_new_config.clicked.connect(self.pushButton_save_new_config_clicked)
    self.Ui.pushButton_save_config.clicked.connect(self.pushButton_save_config_clicked)
    self.Ui.pushButton_init_config.clicked.connect(self.pushButton_init_config_clicked)
    self.Ui.pushButton_move_mp4.clicked.connect(self.pushButton_move_mp4_clicked)
    self.Ui.pushButton_check_net.clicked.connect(self.pushButton_check_net_clicked)
    self.Ui.pushButton_check_javdb_cookie.clicked.connect(self.pushButton_check_javdb_cookie_clicked)
    self.Ui.pushButton_check_javbus_cookie.clicked.connect(self.pushButton_check_javbus_cookie_clicked)
    self.Ui.pushButton_check_and_clean_files.clicked.connect(self.pushButton_check_and_clean_files_clicked)
    self.Ui.pushButton_add_all_extras.clicked.connect(self.pushButton_add_all_extras_clicked)
    self.Ui.pushButton_del_all_extras.clicked.connect(self.pushButton_del_all_extras_clicked)
    self.Ui.pushButton_add_all_extrafanart_copy.clicked.connect(self.pushButton_add_all_extrafanart_copy_clicked)
    self.Ui.pushButton_del_all_extrafanart_copy.clicked.connect(self.pushButton_del_all_extrafanart_copy_clicked)
    self.Ui.pushButton_add_all_theme_videos.clicked.connect(self.pushButton_add_all_theme_videos_clicked)
    self.Ui.pushButton_del_all_theme_videos.clicked.connect(self.pushButton_del_all_theme_videos_clicked)
    self.Ui.pushButton_add_sub_for_all_video.clicked.connect(self.pushButton_add_sub_for_all_video_clicked)
    self.Ui.pushButton_add_actor_info.clicked.connect(self.pushButton_add_actor_info_clicked)
    self.Ui.pushButton_add_actor_pic.clicked.connect(self.pushButton_add_actor_pic_clicked)
    self.Ui.pushButton_add_actor_pic_kodi.clicked.connect(self.pushButton_add_actor_pic_kodi_clicked)
    self.Ui.pushButton_del_actor_folder.clicked.connect(self.pushButton_del_actor_folder_clicked)
    self.Ui.pushButton_show_pic_actor.clicked.connect(self.pushButton_show_pic_actor_clicked)
    self.Ui.pushButton_select_thumb.clicked.connect(self.pushButton_select_thumb_clicked)
    self.Ui.pushButton_find_missing_number.clicked.connect(self.pushButton_find_missing_number_clicked)
    self.Ui.pushButton_creat_symlink.clicked.connect(self.pushButton_creat_symlink_clicked)
    self.Ui.pushButton_start_single_file.clicked.connect(self.pushButton_start_single_file_clicked)
    self.Ui.pushButton_select_file_clear_info.clicked.connect(self.pushButton_select_file_clear_info_clicked)
    self.Ui.pushButton_scrape_note.clicked.connect(self.pushButton_scrape_note_clicked)
    self.Ui.pushButton_field_tips_website.clicked.connect(self.pushButton_field_tips_website_clicked)
    self.Ui.pushButton_field_tips_nfo.clicked.connect(self.pushButton_field_tips_nfo_clicked)
    self.Ui.pushButton_tips_normal_mode.clicked.connect(self.pushButton_tips_normal_mode_clicked)
    self.Ui.pushButton_tips_sort_mode.clicked.connect(self.pushButton_tips_sort_mode_clicked)
    self.Ui.pushButton_tips_update_mode.clicked.connect(self.pushButton_tips_update_mode_clicked)
    self.Ui.pushButton_tips_read_mode.clicked.connect(self.pushButton_tips_read_mode_clicked)
    self.Ui.pushButton_tips_soft.clicked.connect(self.pushButton_tips_soft_clicked)
    self.Ui.pushButton_tips_hard.clicked.connect(self.pushButton_tips_hard_clicked)
    self.Ui.checkBox_cover.stateChanged.connect(self.checkBox_cover_clicked)
    self.Ui.checkBox_i_agree_clean.stateChanged.connect(self.checkBox_i_agree_clean_clicked)
    self.Ui.checkBox_cd_part_a.stateChanged.connect(self.checkBox_cd_part_a_clicked)
    self.Ui.checkBox_i_understand_clean.stateChanged.connect(self.checkBox_i_agree_clean_clicked)
    self.Ui.horizontalSlider_timeout.valueChanged.connect(self.lcdNumber_timeout_change)
    self.Ui.horizontalSlider_retry.valueChanged.connect(self.lcdNumber_retry_change)
    self.Ui.horizontalSlider_mark_size.valueChanged.connect(self.lcdNumber_mark_size_change)
    self.Ui.horizontalSlider_thread.valueChanged.connect(self.lcdNumber_thread_change)
    self.Ui.horizontalSlider_javdb_time.valueChanged.connect(self.lcdNumber_javdb_time_change)
    self.Ui.horizontalSlider_thread_time.valueChanged.connect(self.lcdNumber_thread_time_change)
    self.Ui.comboBox_change_config.activated[str].connect(self.config_file_change)
    self.Ui.comboBox_custom_website.activated[str].connect(self.switch_custom_website_change)
    self.Ui.pushButton_right_menu.clicked.connect(self.main_open_right_menu)
    self.Ui.pushButton_play.clicked.connect(self.main_play_click)
    self.Ui.pushButton_open_folder.clicked.connect(self.main_open_folder_click)
    self.Ui.pushButton_open_nfo.clicked.connect(self.main_open_nfo_click)
    self.Ui.pushButton_tree_clear.clicked.connect(self.init_QTreeWidget)
    self.Ui.pushButton_scraper_failed_list.clicked.connect(self.pushButton_scraper_failed_list_clicked)
    self.Ui.pushButton_save_failed_list.clicked.connect(self.pushButton_save_failed_list_clicked)
    self.Ui.pushButton_success_list_close.clicked.connect(self.Ui.widget_show_success.hide)
    self.Ui.pushButton_success_list_save.clicked.connect(self.pushButton_success_list_save_clicked)
    self.Ui.pushButton_success_list_clear.clicked.connect(self.pushButton_success_list_clear_clicked)
    self.Ui.pushButton_show_tips_close.clicked.connect(self.Ui.widget_show_tips.hide)
    self.Ui.pushButton_nfo_close.clicked.connect(self.Ui.widget_nfo.hide)
    self.Ui.pushButton_nfo_save.clicked.connect(self.save_nfo_info)
    # endregion

    # region 鼠标点击
    self.Ui.label_number.mousePressEvent = self.label_number_clicked
    self.Ui.label_source.mousePressEvent = self.label_number_clicked
    self.Ui.label_actor.mousePressEvent = self.label_actor_clicked
    self.Ui.label_show_version.mousePressEvent = self.label_version_clicked
    self.Ui.label_local_number.mousePressEvent = self.label_local_number_clicked

    def n(a): ...  # mousePressEvent 的返回值必须是 None, 用这个包装一下

    self.Ui.label_download_actor_zip.mousePressEvent = lambda e: n(webbrowser.open(
        'https://github.com/moyy996/AVDC/releases/tag/%E5%A4%B4%E5%83%8F%E5%8C%85-2'))
    self.Ui.label_download_sub_zip.mousePressEvent = lambda e: n(webbrowser.open(
        'https://www.dropbox.com/sh/vkbxawm6mwmwswr/AADqZiF8aUHmK6qIc7JSlURIa'))
    self.Ui.label_download_mark_zip.mousePressEvent = lambda e: n(webbrowser.open(
        'https://www.dropbox.com/sh/vkbxawm6mwmwswr/AADqZiF8aUHmK6qIc7JSlURIa'))
    self.Ui.label_get_cookie_url.mousePressEvent = lambda e: n(webbrowser.open('https://tieba.baidu.com/p/5492736764'))
    self.Ui.label_download_actor_db.mousePressEvent = lambda e: n(webbrowser.open(
        'https://github.com/sqzw-x/mdcx/releases/tag/actor_info_database'))
    # endregion

    # region 控件更新
    self.main_logs_show.connect(self.Ui.textBrowser_log_main.append)
    self.main_logs_clear.connect(self.Ui.textBrowser_log_main.clear)
    self.req_logs_clear.connect(self.Ui.textBrowser_log_main_2.clear)
    self.main_req_logs_show.connect(self.Ui.textBrowser_log_main_2.append)
    self.net_logs_show.connect(self.Ui.textBrowser_net_main.append)
    self.set_javdb_cookie.connect(self.Ui.plainTextEdit_cookie_javdb.setPlainText)
    self.set_javbus_cookie.connect(self.Ui.plainTextEdit_cookie_javbus.setPlainText)
    self.set_javbus_status.connect(self.Ui.label_javbus_cookie_result.setText)
    self.set_pic_pixmap.connect(self.resize_label_and_setpixmap)
    self.set_pic_text.connect(self.Ui.label_poster_size.setText)
    self.change_to_mainpage.connect(self.change_mainpage)
    # endregion

    # region 文本更新
    self.set_label_file_path.connect(self.Ui.label_file_path.setText)
    self.pushButton_start_cap.connect(self.Ui.pushButton_start_cap.setText)
    self.pushButton_start_cap2.connect(self.Ui.pushButton_start_cap2.setText)
    self.pushButton_start_single_file.connect(self.Ui.pushButton_start_single_file.setText)
    self.pushButton_add_sub_for_all_video.connect(self.Ui.pushButton_add_sub_for_all_video.setText)
    self.pushButton_show_pic_actor.connect(self.Ui.pushButton_show_pic_actor.setText)
    self.pushButton_add_actor_info.connect(self.Ui.pushButton_add_actor_info.setText)
    self.pushButton_add_actor_pic.connect(self.Ui.pushButton_add_actor_pic.setText)
    self.pushButton_add_actor_pic_kodi.connect(self.Ui.pushButton_add_actor_pic_kodi.setText)
    self.pushButton_del_actor_folder.connect(self.Ui.pushButton_del_actor_folder.setText)
    self.pushButton_check_and_clean_files.connect(self.Ui.pushButton_check_and_clean_files.setText)
    self.pushButton_move_mp4.connect(self.Ui.pushButton_move_mp4.setText)
    self.pushButton_find_missing_number.connect(self.Ui.pushButton_find_missing_number.setText)
    self.label_result.connect(self.Ui.label_result.setText)
    self.label_show_version.connect(self.Ui.label_show_version.setText)
    # endregion


def Init_QSystemTrayIcon(self):
    self.tray_icon = QSystemTrayIcon(self)
    self.tray_icon.setIcon(QIcon(resources.icon_ico))
    self.tray_icon.activated.connect(self.tray_icon_click)
    self.tray_icon.setToolTip(f'MDCx {self.localversion}（Left click to show/hide | Right click to exit）')
    show_action = QAction(u"Show", self)
    hide_action = QAction(u"Hide\tQ", self)
    quit_action = QAction(u"Quit MDCx", self)
    show_action.triggered.connect(self.tray_icon_show)
    hide_action.triggered.connect(self.hide)
    quit_action.triggered.connect(self.ready_to_exit)
    tray_menu = QMenu()
    tray_menu.addAction(show_action)
    tray_menu.addAction(hide_action)
    tray_menu.addSeparator()
    tray_menu.addAction(quit_action)
    self.tray_icon.setContextMenu(tray_menu)
    self.tray_icon.show()
    # self.tray_icon.showMessage(f"MDCx {self.localversion}", u'已启动！欢迎使用!', QIcon(self.icon_ico), 3000) # icon的值  0没有图标  1是提示  2是警告  3是错误


def init_QTreeWidget(self):
    # 初始化树状控件
    try:
        self.set_label_file_path.emit('🎈 Scraping Path: \n %s' % get_movie_path_setting()[0])  # 主界面右上角显示提示信息
    except:
        signal.show_traceback_log(traceback.format_exc())
    signal.add_label_info('')
    Flags.count_claw = 0  # 批量刮削次数
    if self.Ui.pushButton_start_cap.text() != 'Start':
        Flags.count_claw = 1  # 批量刮削次数
    else:
        self.label_result.emit(' Scraping:0 Success:0 Failure:0')
    self.Ui.treeWidget_number.clear()
    self.item_succ = QTreeWidgetItem(self.Ui.treeWidget_number)
    self.item_succ.setText(0, 'Success')
    self.item_fail = QTreeWidgetItem(self.Ui.treeWidget_number)
    self.item_fail.setText(0, 'Failure')
    self.Ui.treeWidget_number.expandAll()  # 展开主界面树状内容
