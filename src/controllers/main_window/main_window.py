import os
import re
import shutil
import threading
import time
import traceback
import webbrowser

from PyQt5.QtCore import QEvent, QPoint, QTimer, Qt, pyqtSignal
from PyQt5.QtGui import QCursor, QHoverEvent, QIcon, QKeySequence
from PyQt5.QtWidgets import QAction, QApplication, QFileDialog, QInputDialog, QMainWindow, QMenu, QMessageBox, \
    QShortcut, QTreeWidgetItem

from controllers.cut_window import CutWindow
from controllers.main_window.init import Init_QSystemTrayIcon, Init_Singal, Init_Ui, init_QTreeWidget
from controllers.main_window.load_config import load_config
from controllers.main_window.save_config import save_config
from controllers.main_window.style import set_dark_style, set_style
from models.base.file import _open_file_thread, delete_file, move_file, split_path
from models.base.image import get_pixmap
from models.base.number import get_info
from models.base.path import get_main_path, get_path
from models.base.utils import _async_raise, add_html, convert_path, get_current_time, get_used_time, kill_a_thread
from models.base.web import check_theporndb_api_token, check_version, get_avsox_domain, get_html, ping_host, \
    scraper_html
from models.config.config import config
from models.config.resources import resources
from models.core.file import check_and_clean_files, get_success_list, movie_lists, \
    newtdisk_creat_symlink, save_remain_list, save_success_list
from models.core.flags import Flags
from models.core.image import add_del_extrafanart_copy
from models.core.nfo import write_nfo
from models.core.scraper import again_search, get_remain_list, start_new_scrape
from models.core.subtitle import add_sub_for_all_video
from models.core.utils import deal_url, get_movie_path_setting
from models.core.video import add_del_extras, add_del_theme_videos
from models.core.web import show_netstatus
from models.entity.enums import FileMode
from models.signals import signal
from models.tools.actress_db import ActressDB
from models.tools.emby_actor_image import update_emby_actor_photo
from models.tools.emby_actor_info import creat_kodi_actors, show_emby_actor_list, update_emby_actor_info
from models.tools.missing import check_missing_number
from views.MDCx import Ui_MDCx


class MyMAinWindow(QMainWindow):
    # region 信号量
    main_logs_show = pyqtSignal(str)  # 显示刮削日志信号
    main_logs_clear = pyqtSignal(str)  # 清空刮削日志信号
    req_logs_clear = pyqtSignal(str)  # 清空请求日志信号
    main_req_logs_show = pyqtSignal(str)  # 显示刮削后台日志信号
    net_logs_show = pyqtSignal(str)  # 显示网络检测日志信号
    set_javdb_cookie = pyqtSignal(str)  # 加载javdb cookie文本内容到设置页面
    set_javbus_cookie = pyqtSignal(str)  # 加载javbus cookie文本内容到设置页面
    set_javbus_status = pyqtSignal(str)  # javbus 检查状态更新
    set_label_file_path = pyqtSignal(str)  # 主界面更新路径信息显示
    set_pic_pixmap = pyqtSignal(list, list)  # 主界面显示封面、缩略图
    set_pic_text = pyqtSignal(str)  # 主界面显示封面信息
    change_to_mainpage = pyqtSignal(str)  # 切换到主界面
    label_result = pyqtSignal(str)
    pushButton_start_cap = pyqtSignal(str)
    pushButton_start_cap2 = pyqtSignal(str)
    pushButton_start_single_file = pyqtSignal(str)
    pushButton_add_sub_for_all_video = pyqtSignal(str)
    pushButton_show_pic_actor = pyqtSignal(str)
    pushButton_add_actor_info = pyqtSignal(str)
    pushButton_add_actor_pic = pyqtSignal(str)
    pushButton_add_actor_pic_kodi = pyqtSignal(str)
    pushButton_del_actor_folder = pyqtSignal(str)
    pushButton_check_and_clean_files = pyqtSignal(str)
    pushButton_move_mp4 = pyqtSignal(str)
    pushButton_find_missing_number = pyqtSignal(str)
    label_show_version = pyqtSignal(str)

    # endregion

    def __init__(self, parent=None):
        super(MyMAinWindow, self).__init__(parent)

        # region 初始化需要的变量
        self.localversion = config.local_version  # 当前版本号
        self.new_version = ''  # 有版本更新时在左下角显示的新版本信息
        self.json_data = {}  # 当前树状图选中文件的json_data
        self.img_path = ''  # 当前树状图选中文件的图片地址
        self.m_drag = False  # 允许鼠标拖动的标识
        self.m_DragPosition = 0  # 鼠标拖动位置
        self.logs_counts = 0  # 日志次数（每1w次清屏）
        self.req_logs_counts = 0  # 日志次数（每1w次清屏）
        self.file_main_open_path = ''  # 主界面打开的文件路径
        self.json_array = {}  # 主界面右侧结果树状数据

        self.window_radius = 0  # 窗口四角弧度，为0时表示显示窗口标题栏
        self.window_border = 0  # 窗口描边，为0时表示显示窗口标题栏
        self.dark_mode = False  # 暗黑模式标识
        self.check_mac = True  # 检测配置目录
        # self.window_marjin = 0 窗口外边距，为0时不往里缩
        self.show_flag = True  # 是否加载刷新样式

        self.timer = QTimer()  # 初始化一个定时器，用于显示日志
        self.timer.timeout.connect(self.show_detail_log)
        self.timer.start(100)  # 设置间隔100毫秒
        self.timer_scrape = QTimer()  # 初始化一个定时器，用于间隔刮削
        self.timer_scrape.timeout.connect(self.auto_scrape)
        self.timer_update = QTimer()  # 初始化一个定时器，用于检查更新
        self.timer_update.timeout.connect(check_version)
        self.timer_update.start(43200000)  # 设置检查间隔12小时
        self.timer_remain_task = QTimer()  # 初始化一个定时器，用于显示保存剩余任务
        self.timer_remain_task.timeout.connect(save_remain_list)
        self.timer_remain_task.start(1500)  # 设置间隔1.5秒
        self.atuo_scrape_count = 0  # 循环刮削次数
        self.label_number_url = ''
        self.label_actor_url = ''
        # endregion

        # region 其它属性声明
        self.start_click_time = None
        self.start_click_pos = None
        self.menu_start = None
        self.menu_stop = None
        self.menu_number = None
        self.menu_website = None
        self.menu_del_file = None
        self.menu_del_folder = None
        self.menu_folder = None
        self.menu_nfo = None
        self.menu_play = None
        self.menu_hide = None
        self.window_marjin = None
        self.now_show_name = None
        self.show_name = None
        self.t_net = None
        self.options = None
        # endregion

        # region 初始化 UI
        resources.get_fonts()
        self.Ui = Ui_MDCx()  # 实例化 Ui
        self.Ui.setupUi(self)  # 初始化 Ui
        self.cutwindow = CutWindow(self)
        self.Init_Singal()  # 信号连接
        self.Init_Ui()  # 设置Ui初始状态
        self.load_config()  # 加载配置
        get_success_list()  # 获取历史成功刮削列表
        # endregion

        # region 启动显示信息和后台检查更新
        self.show_scrape_info()  # 主界面左下角显示一些配置信息
        self.show_net_info('\n🏠 Proxy settings are located under: [Settings] -> [Network] -> [Proxy Settings].\n')  # 检查网络界面显示提示信息
        show_netstatus()  # 检查网络界面显示当前网络代理信息
        self.show_net_info(
            '\n💡 Information: \n '
            'Proxied Agent:      javbus, jav321, javlibrary, mgstage, mywife, giga, freejavbt, mdtv, madouqu,\n '
            '                    7mmtv, falenodahlia, prestige, theporndb, cnmdb, fantastica, kin8\n '
            'Non-Japanese Agent: javdb, airav-cc, avsex（Japanese agent will report an error）\n '
            'Japanese Agent:     seesaawiki\n '
            'No Agent Required:  avsex, hdouban, iqqtv, airav-wiki, love6, lulubar, fc2, fc2club, fc2hub\n\n'
            '▶️ Click the [Start Test] button in the upper right corner to test network connectivity.')  # 检查网络界面显示提示信息
        signal.add_log("🍯 You can click the icon in the lower right hand corner to show/hide this panel!")
        self.show_version()  # 日志页面显示版本信息
        self.creat_right_menu()  # 加载右键菜单
        self.pushButton_main_clicked()  # 切换到主界面
        self.auto_start()  # 自动开始刮削
        # self.load_langid()# 后台加载langid，第一次加载需要时间，预加载避免卡住
        # endregion

    # region Init
    def Init_Ui(self):
        ...

    def Init_Singal(self):
        ...

    def Init_QSystemTrayIcon(self):
        ...

    def init_QTreeWidget(self):
        ...

    def load_config(self):
        ...

    def creat_right_menu(self):
        self.menu_start = QAction(QIcon(resources.start_icon), u'  Start scraping\tS', self)
        self.menu_stop = QAction(QIcon(resources.stop_icon), u'  Stop scraping\tS', self)
        self.menu_number = QAction(QIcon(resources.input_number_icon), u'  Re-shaving\tN', self)
        self.menu_website = QAction(QIcon(resources.input_website_icon), u'  Enter the URL to scrape again\tU', self)
        self.menu_del_file = QAction(QIcon(resources.del_file_icon), u'  Delete files\tD', self)
        self.menu_del_folder = QAction(QIcon(resources.del_folder_icon), u'  Delete files and folders\tA', self)
        self.menu_folder = QAction(QIcon(resources.open_folder_icon), u'  Open folder\tF', self)
        self.menu_nfo = QAction(QIcon(resources.open_nfo_icon), u'  Edit NFO\tE', self)
        self.menu_play = QAction(QIcon(resources.play_icon), u'  Play\tP', self)
        self.menu_hide = QAction(QIcon(resources.hide_boss_icon), u'  Hide\tQ', self)

        self.menu_start.triggered.connect(self.pushButton_start_scrape_clicked)
        self.menu_stop.triggered.connect(self.pushButton_start_scrape_clicked)
        self.menu_number.triggered.connect(self.search_by_number_clicked)
        self.menu_website.triggered.connect(self.search_by_url_clicked)
        self.menu_del_file.triggered.connect(self.main_del_file_click)
        self.menu_del_folder.triggered.connect(self.main_del_folder_click)
        self.menu_folder.triggered.connect(self.main_open_folder_click)
        self.menu_nfo.triggered.connect(self.main_open_nfo_click)
        self.menu_play.triggered.connect(self.main_play_click)
        self.menu_hide.triggered.connect(self.hide)

        QShortcut(QKeySequence(self.tr("N")), self, self.search_by_number_clicked)
        QShortcut(QKeySequence(self.tr("U")), self, self.search_by_url_clicked)
        QShortcut(QKeySequence(self.tr("D")), self, self.main_del_file_click)
        QShortcut(QKeySequence(self.tr("A")), self, self.main_del_folder_click)
        QShortcut(QKeySequence(self.tr("F")), self, self.main_open_folder_click)
        QShortcut(QKeySequence(self.tr("E")), self, self.main_open_nfo_click)
        QShortcut(QKeySequence(self.tr("P")), self, self.main_play_click)
        QShortcut(QKeySequence(self.tr("S")), self, self.pushButton_start_scrape_clicked)
        QShortcut(QKeySequence(self.tr("Q")), self, self.hide)
        # QShortcut(QKeySequence(self.tr("Esc")), self, self.hide)
        QShortcut(QKeySequence(self.tr("Ctrl+M")), self, self.pushButton_min_clicked2)
        QShortcut(QKeySequence(self.tr("Ctrl+W")), self, self.ready_to_exit)

        self.Ui.page_main.setContextMenuPolicy(Qt.CustomContextMenu)
        self.Ui.page_main.customContextMenuRequested.connect(self._menu)

    def _menu(self, pos=''):
        if not pos:
            pos = self.Ui.pushButton_right_menu.pos() + QPoint(40, 10)
            # pos = QCursor().pos()
        menu = QMenu()
        if self.file_main_open_path:
            file_name = split_path(self.file_main_open_path)[1]
            menu.addAction(QAction(file_name, self))
            menu.addSeparator()
        else:
            menu.addAction(QAction('Please scrape before use!', self))
            menu.addSeparator()
            if self.Ui.pushButton_start_cap.text() != 'Start':
                menu.addAction(self.menu_stop)
            else:
                menu.addAction(self.menu_start)
        menu.addAction(self.menu_number)
        menu.addAction(self.menu_website)
        menu.addSeparator()
        menu.addAction(self.menu_del_file)
        menu.addAction(self.menu_del_folder)
        menu.addSeparator()
        menu.addAction(self.menu_folder)
        menu.addAction(self.menu_nfo)
        menu.addAction(self.menu_play)
        menu.addAction(self.menu_hide)
        menu.exec_(self.Ui.page_main.mapToGlobal(pos))
        # menu.move(pos)
        # menu.show()

    # endregion

    # region 窗口操作
    def tray_icon_click(self, e):
        if int(e) == 3:
            if config.is_windows:
                if self.isVisible():
                    self.hide()
                else:
                    self.activateWindow()
                    self.raise_()
                    self.show()

    def tray_icon_show(self):
        if int(self.windowState()) == 1:  # 最小化时恢复
            self.showNormal()
        self.recover_windowflags()  # 恢复焦点
        self.activateWindow()
        self.raise_()
        self.show()

    def change_mainpage(self, t):
        self.pushButton_main_clicked()

    def eventFilter(self, object_, event):
        # print(event.type())

        if event.type() == 3:  # 松开鼠标，检查是否在前台
            self.recover_windowflags()
        if event.type() == 121:
            if not self.isVisible():
                self.show()
        if object_.objectName() == 'label_poster' or object_.objectName() == 'label_thumb':
            if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                self.start_click_time = time.time()
                self.start_click_pos = event.globalPos()
            elif event.type() == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
                if not (event.globalPos() - self.start_click_pos) or (time.time() - self.start_click_time < 0.05):
                    self._pic_main_clicked()
        if object_ is self.Ui.textBrowser_log_main.viewport() or object_ is self.Ui.textBrowser_log_main_2.viewport():
            if not self.Ui.textBrowser_log_main_3.isHidden() and event.type() == QEvent.MouseButtonPress:
                self.Ui.textBrowser_log_main_3.hide()
                self.Ui.pushButton_scraper_failed_list.hide()
                self.Ui.pushButton_save_failed_list.hide()
        return super().eventFilter(object_, event)

    def showEvent(self, event):
        self.resize(1030, 700)  # 调整窗口大小

    # 当隐藏边框时，最小化后，点击任务栏时，需要监听事件，在恢复窗口时隐藏边框
    def changeEvent(self, event):
        # self.show_traceback_log(QEvent.WindowStateChange) 
        # WindowState （WindowNoState=0 正常窗口; WindowMinimized= 1 最小化; 
        # WindowMaximized= 2 最大化; WindowFullScreen= 3 全屏;WindowActive= 8 可编辑。） 
        # windows平台无问题，仅mac平台python版有问题
        if not config.is_windows:
            if self.window_radius and event.type() == QEvent.WindowStateChange and not int(self.windowState()):
                self.setWindowFlag(Qt.FramelessWindowHint, True)  # 隐藏边框
                self.show()

        # activeAppName = AppKit.NSWorkspace.sharedWorkspace().activeApplication()['NSApplicationName'] # 活动窗口的标题

    def closeEvent(self, event):
        self.ready_to_exit()
        event.ignore()

    # Show and hide window title bar
    def _windows_auto_adjust(self):
        if config.window_title == 'hide':  # 隐藏标题栏
            if self.window_radius == 0:
                self.show_flag = True
            self.window_radius = 5
            if config.is_windows:
                self.window_border = 1
            else:
                self.window_border = 0
            self.setWindowFlag(Qt.FramelessWindowHint, True)  # 隐藏标题栏
            self.Ui.pushButton_close.setVisible(True)
            self.Ui.pushButton_min.setVisible(True)
            self.Ui.widget_buttons.move(0, 50)

        else:  # 显示标题栏
            if self.window_radius == 5:
                self.show_flag = True
            self.window_radius = 0
            self.window_border = 0
            self.window_marjin = 0
            self.setWindowFlag(Qt.FramelessWindowHint, False)  # 显示标题栏
            self.Ui.pushButton_close.setVisible(False)
            self.Ui.pushButton_min.setVisible(False)
            self.Ui.widget_buttons.move(0, 20)

        if bool(self.dark_mode != self.Ui.checkBox_dark_mode.isChecked()):
            self.show_flag = True
            self.dark_mode = self.Ui.checkBox_dark_mode.isChecked()

        if self.show_flag:
            self.show_flag = False
            self.set_style()  # 样式美化

            # self.setWindowState(Qt.WindowNoState)                               # 恢复正常窗口
            self.show()
            self._change_page()

    def _change_page(self):
        page = int(self.Ui.stackedWidget.currentIndex())
        if page == 0:
            self.pushButton_main_clicked()
        elif page == 1:
            self.pushButton_show_log_clicked()
        elif page == 2:
            self.pushButton_show_net_clicked()
        elif page == 3:
            self.pushButton_tool_clicked()
        elif page == 4:
            self.pushButton_setting_clicked()
        elif page == 5:
            self.pushButton_about_clicked()

    def set_style(self):
        ...

    def set_dark_style(self):
        ...

    # region 拖动窗口
    # 按下鼠标
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.m_drag = True
            self.m_DragPosition = e.globalPos() - self.pos()
            self.setCursor(QCursor(Qt.OpenHandCursor))  # 按下左键改变鼠标指针样式为手掌

    # 松开鼠标
    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.m_drag = False
            self.setCursor(QCursor(Qt.ArrowCursor))  # 释放左键改变鼠标指针样式为箭头

    # 拖动鼠标
    def mouseMoveEvent(self, e):
        if Qt.LeftButton and self.m_drag:
            self.move(e.globalPos() - self.m_DragPosition)
            e.accept()

    # endregion

    # region 关闭
    # 关闭按钮点击事件响应函数
    def pushButton_close_clicked(self):
        if 'hide_close' in config.switch_on:
            self.hide()
        else:
            self.ready_to_exit()

    def ready_to_exit(self):
        if 'show_dialog_exit' in config.switch_on:
            if not self.isVisible():
                self.show()
            if int(self.windowState()) == 1:
                self.showNormal()

            # print(self.window().isActiveWindow()) # 是否为活动窗口
            self.raise_()
            box = QMessageBox(QMessageBox.Warning, 'Quit', 'Are you sure you want to exit?')
            box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            box.button(QMessageBox.Yes).setText('Quit MDCx')
            box.button(QMessageBox.No).setText('Cancel')
            box.setDefaultButton(QMessageBox.No)
            reply = box.exec()
            if reply != QMessageBox.Yes:
                self.raise_()
                self.show()
                return
        self.exit_app()

    # 关闭窗口
    def exit_app(self):
        show_poster = config.show_poster
        switch_on = config.switch_on
        need_save_config = False

        if bool(self.Ui.checkBox_cover.isChecked()) != bool(show_poster):
            if self.Ui.checkBox_cover.isChecked():
                config.show_poster = 1
            else:
                config.show_poster = 0
            need_save_config = True
        if self.Ui.textBrowser_log_main_2.isHidden() == bool('show_logs' in switch_on):
            if self.Ui.textBrowser_log_main_2.isHidden():
                config.switch_on = switch_on.replace('show_logs,', '')
            else:
                config.switch_on = switch_on + 'show_logs,'
            need_save_config = True
        if need_save_config:
            try:
                config.save_config()
            except:
                signal.show_traceback_log(traceback.format_exc())
        try:
            self.tray_icon.hide()
        except:
            signal.show_traceback_log(traceback.format_exc())
        signal.show_traceback_log('\n\n\n\n************ The program exits normally!************\n')
        os._exit(0)

    # endregion

    # 最小化窗口
    def pushButton_min_clicked(self):
        if 'hide_mini' in config.switch_on:
            self.hide()
            return
        # mac 平台 python 版本 最小化有问题，此处就是为了兼容它，需要先设置为显示窗口标题栏才能最小化
        if not config.is_windows:
            self.setWindowFlag(Qt.FramelessWindowHint, False)  # 不隐藏边框

        # self.setWindowState(Qt.WindowMinimized)
        # self.show_traceback_log(self.isMinimized())
        self.showMinimized()

    def pushButton_min_clicked2(self):
        if not config.is_windows:
            self.setWindowFlag(Qt.FramelessWindowHint, False)  # 不隐藏边框
            # self.show()                                                         # 加上后可以显示缩小动画
        self.showMinimized()

    # 重置左侧按钮样式
    def set_left_button_style(self):
        try:
            if self.dark_mode:
                self.Ui.left_backgroud_widget.setStyleSheet(
                    'background: #1F272F;border-right: 1px solid #20303F;border-top-left-radius: %spx;border-bottom-left-radius: %spx;' % (
                        self.window_radius, self.window_radius))
                self.Ui.pushButton_main.setStyleSheet(
                    'QPushButton:hover#pushButton_main{color: white;background-color: rgba(160,160,165,40);}')
                self.Ui.pushButton_log.setStyleSheet(
                    'QPushButton:hover#pushButton_log{color: white;background-color: rgba(160,160,165,40);}')
                self.Ui.pushButton_net.setStyleSheet(
                    'QPushButton:hover#pushButton_net{color: white;background-color: rgba(160,160,165,40);}')
                self.Ui.pushButton_tool.setStyleSheet(
                    'QPushButton:hover#pushButton_tool{color: white;background-color: rgba(160,160,165,40);}')
                self.Ui.pushButton_setting.setStyleSheet(
                    'QPushButton:hover#pushButton_setting{color: white;background-color: rgba(160,160,165,40);}')
                self.Ui.pushButton_about.setStyleSheet(
                    'QPushButton:hover#pushButton_about{color: white;background-color: rgba(160,160,165,40);}')
            else:
                self.Ui.pushButton_main.setStyleSheet(
                    'QPushButton:hover#pushButton_main{color: black;background-color: rgba(160,160,165,40);}')
                self.Ui.pushButton_log.setStyleSheet(
                    'QPushButton:hover#pushButton_log{color: black;background-color: rgba(160,160,165,40);}')
                self.Ui.pushButton_net.setStyleSheet(
                    'QPushButton:hover#pushButton_net{color: black;background-color: rgba(160,160,165,40);}')
                self.Ui.pushButton_tool.setStyleSheet(
                    'QPushButton:hover#pushButton_tool{color: black;background-color: rgba(160,160,165,40);}')
                self.Ui.pushButton_setting.setStyleSheet(
                    'QPushButton:hover#pushButton_setting{color: black;background-color: rgba(160,160,165,40);}')
                self.Ui.pushButton_about.setStyleSheet(
                    'QPushButton:hover#pushButton_about{color: black;background-color: rgba(160,160,165,40);}')
        except:
            signal.show_traceback_log(traceback.format_exc())

    # endregion

    # region 显示版本号
    def show_version(self):
        try:
            t = threading.Thread(target=self._show_version_thread)
            t.start()  # 启动线程,即让线程开始执行
        except:
            signal.show_traceback_log(traceback.format_exc())
            signal.show_log_text(traceback.format_exc())

    def _show_version_thread(self):
        version_info = f'Modified from MDC-GUI current version: {self.localversion}'
        download_link = ''
        latest_version = check_version()
        if latest_version:
            if int(self.localversion) < int(latest_version):
                self.new_version = f'\n🍉 New Update!（{latest_version}）'
                signal.show_scrape_info()
                self.Ui.label_show_version.setCursor(Qt.OpenHandCursor)  # 设置鼠标形状为十字形
                version_info = f'Modified from MDC-GUI · Current version: {self.localversion} （<font color=\"red\" >The latest version is {latest_version}，Please update! 🚀</font>）'
                download_link = ' ⬇️ <a href="https://github.com/sqzw-x/mdcx/releases">Download latest version</a>'
            else:
                version_info = f'Modified from MDC-GUI · Current version: {self.localversion} （<font color=\"green\">You are using the latest version! 🎉</font>）'

        feedback = f' 💌 Feedback: <a href="https://github.com/sqzw-x/mdcx/issues/new">GitHub Issues</a>'

        # 显示版本信息和反馈入口
        signal.show_log_text(version_info)
        if feedback or download_link:
            self.main_logs_show.emit(f'{feedback}{download_link}')
        signal.show_log_text('================================================================================')
        self.pushButton_check_javdb_cookie_clicked()  # 检测javdb cookie
        self.pushButton_check_javbus_cookie_clicked()  # 检测javbus cookie
        if config.use_database:
            ActressDB.init_db()
        try:
            t = threading.Thread(target=check_theporndb_api_token)
            t.start()  # 启动线程,即让线程开始执行
        except:
            signal.show_traceback_log(traceback.format_exc())
            signal.show_log_text(traceback.format_exc())

    # endregion

    # region 各种点击跳转浏览器
    def label_number_clicked(self, test):
        """
        主界面点番号或数据来源
        """
        try:
            if self.label_number_url:
                if hasattr(config, 'javdb_website'):
                    self.label_number_url = self.label_number_url.replace('https://javdb.com', config.javdb_website)
                webbrowser.open(self.label_number_url)
        except:
            signal.show_traceback_log(traceback.format_exc())

    def label_actor_clicked(self, test):
        """
        主界面点演员名
        """
        try:
            if self.label_actor_url:
                if hasattr(config, 'javdb_website'):
                    self.label_actor_url = self.label_actor_url.replace('https://javdb.com', config.javdb_website)
                webbrowser.open(self.label_actor_url)
        except:
            signal.show_traceback_log(traceback.format_exc())

    def label_version_clicked(self, test):
        try:
            if self.new_version:
                webbrowser.open('https://github.com/sqzw-x/mdcx/releases')
        except:
            signal.show_traceback_log(traceback.format_exc())

    # endregion

    # region 左侧切换页面
    # 点左侧的主界面按钮
    def pushButton_main_clicked(self):
        self.Ui.left_backgroud_widget.setStyleSheet(
            'background: #F5F5F6;border-right: 1px solid #EDEDED;border-top-left-radius: %spx;border-bottom-left-radius: %spx;' % (
                self.window_radius, self.window_radius))
        self.Ui.stackedWidget.setCurrentIndex(0)
        self.set_left_button_style()
        self.Ui.pushButton_main.setStyleSheet('font-weight: bold; background-color: rgba(160,160,165,60);')

    # 点左侧的日志按钮
    def pushButton_show_log_clicked(self):
        self.Ui.left_backgroud_widget.setStyleSheet(
            'background: #EFFFFC;border-right: 1px solid #EDEDED;border-top-left-radius: %spx;border-bottom-left-radius: %spx;' % (
                self.window_radius, self.window_radius))
        self.Ui.stackedWidget.setCurrentIndex(1)
        self.set_left_button_style()
        self.Ui.pushButton_log.setStyleSheet('font-weight: bold; background-color: rgba(160,160,165,60);')
        self.Ui.textBrowser_log_main.verticalScrollBar().setValue(
            self.Ui.textBrowser_log_main.verticalScrollBar().maximum())
        self.Ui.textBrowser_log_main_2.verticalScrollBar().setValue(
            self.Ui.textBrowser_log_main_2.verticalScrollBar().maximum())

    # 点左侧的工具按钮
    def pushButton_tool_clicked(self):
        self.Ui.left_backgroud_widget.setStyleSheet(
            'background: #FFEFF6;border-right: 1px solid #EDEDED;border-top-left-radius: %spx;border-bottom-left-radius: %spx;' % (
                self.window_radius, self.window_radius))
        self.Ui.stackedWidget.setCurrentIndex(3)
        self.set_left_button_style()
        self.Ui.pushButton_tool.setStyleSheet('font-weight: bold; background-color: rgba(160,160,165,60);')

    # 点左侧的设置按钮
    def pushButton_setting_clicked(self):
        self.Ui.left_backgroud_widget.setStyleSheet(
            'background: #84CE9A;border-right: 1px solid #EDEDED;border-top-left-radius: %spx;border-bottom-left-radius: %spx;' % (
                self.window_radius, self.window_radius))
        self.Ui.stackedWidget.setCurrentIndex(4)
        self.set_left_button_style()
        try:
            if self.dark_mode:
                self.Ui.pushButton_setting.setStyleSheet('font-weight: bold; background-color: rgba(160,160,165,60);')
            else:
                self.Ui.pushButton_setting.setStyleSheet('font-weight: bold; background-color: rgba(160,160,165,100);')
            self._check_mac_config_folder()
        except:
            signal.show_traceback_log(traceback.format_exc())

    # 点击左侧【检测网络】按钮，切换到检测网络页面
    def pushButton_show_net_clicked(self):
        self.Ui.left_backgroud_widget.setStyleSheet(
            'background: #E1F2FF;border-right: 1px solid #EDEDED;border-top-left-radius: %spx;border-bottom-left-radius: %spx;' % (
                self.window_radius, self.window_radius))
        self.Ui.stackedWidget.setCurrentIndex(2)
        self.set_left_button_style()
        self.Ui.pushButton_net.setStyleSheet('font-weight: bold; background-color: rgba(160,160,165,60);')

    # 点左侧的关于按钮
    def pushButton_about_clicked(self):
        self.Ui.left_backgroud_widget.setStyleSheet(
            'background: #FFEFEF;border-right: 1px solid #EDEDED;border-top-left-radius: %spx;border-bottom-left-radius: %spx;' % (
                self.window_radius, self.window_radius))
        self.Ui.stackedWidget.setCurrentIndex(5)
        self.set_left_button_style()
        self.Ui.pushButton_about.setStyleSheet('font-weight: bold; background-color: rgba(160,160,165,60);')

    # endregion

    # region 主界面
    # 开始刮削按钮
    def pushButton_start_scrape_clicked(self):
        if self.Ui.pushButton_start_cap.text() == 'Start':
            if not get_remain_list():
                start_new_scrape(FileMode.Default)
        elif self.Ui.pushButton_start_cap.text() == '■ stop':
            self.pushButton_stop_scrape_clicked()

    # 停止确认弹窗
    def pushButton_stop_scrape_clicked(self):
        if 'show_dialog_stop_scrape' in config.switch_on:
            box = QMessageBox(QMessageBox.Warning, 'Stop scraping', 'Are you sure you want to stop scraping?')
            box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            box.button(QMessageBox.Yes).setText('Stop scraping')
            box.button(QMessageBox.No).setText('Cancel')
            box.setDefaultButton(QMessageBox.No)
            reply = box.exec()
            if reply != QMessageBox.Yes:
                return
        if self.Ui.pushButton_start_cap.text() == '■ stop':
            save_success_list()  # 保存成功列表
            Flags.stop_flag = True  # 在pool启动前，点停止按钮时，需要用这个来停止启动pool
            Flags.rest_time_convert_ = Flags.rest_time_convert
            Flags.rest_time_convert = 0
            Flags.rest_sleepping = False
            self.Ui.pushButton_start_cap.setText(' ■ Stopping ')
            self.Ui.pushButton_start_cap2.setText(' ■ Stopping ')
            signal.show_scrape_info('⛔️ Scraping has stopped...')
            try:  # pool可能还没启动
                Flags.pool.shutdown39(wait=False, cancel_futures=True)
            except:
                signal.show_traceback_log(traceback.format_exc())
            t = threading.Thread(target=self._kill_threads)  # 关闭线程池和扫描线程
            t.start()

    # 显示停止信息
    def _show_stop_info(self):
        signal.reset_buttons_status.emit()
        try:
            Flags.rest_time_convert = Flags.rest_time_convert_
            if Flags.stop_other:
                signal.show_scrape_info('⛔️ Stopped manually!')
                signal.show_log_text(
                    "⛔️ Stopped manually!\n================================================================================")
                self.set_label_file_path.emit('⛔️ Stopped manually!')
                return
            signal.exec_set_processbar.emit(0)
            end_time = time.time()
            used_time = str(round((end_time - Flags.start_time), 2))
            if Flags.scrape_done:
                average_time = str(round((end_time - Flags.start_time) / Flags.scrape_done, 2))
            else:
                average_time = used_time
            signal.show_scrape_info('⛔️ Scraping has been stopped manually!')
            self.set_label_file_path.emit(
                '⛔️ Scraping has been stopped manually!\n   Scraped %s Videos, still remaining %s indivual! Scraping time %s Second' % (
                    Flags.scrape_done, (Flags.total_count - Flags.scrape_done), used_time))
            signal.show_log_text(
                '\n ⛔️ Scraping has been stopped manually!\n 😊 Scraped %s videos, still remaining %s indivual! Scraping time %s seconds, stop using time %s Second' % (
                    Flags.scrape_done, (Flags.total_count - Flags.scrape_done), used_time, self.stop_used_time))
            signal.show_log_text("================================================================================")
            signal.show_log_text(
                ' ⏰ Start time'.ljust(13) + ': ' + time.strftime("%Y-%m-%d %H:%M:%S",
                                                                 time.localtime(Flags.start_time)))
            signal.show_log_text(
                ' 🏁 End time'.ljust(13) + ': ' + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(end_time)))
            signal.show_log_text(' ⏱ Used time'.ljust(13) + ': %sS' % used_time)
            signal.show_log_text(' 🍕 Per time'.ljust(13) + ': %sS' % average_time)
            signal.show_log_text("================================================================================")
            Flags.again_dic.clear()
        except:
            signal.show_traceback_log(traceback.format_exc())
            signal.show_log_text(traceback.format_exc())
        print(threading.enumerate())

    def show_stop_info_thread(self, ):
        t = threading.Thread(target=self._show_stop_info)
        t.start()

    # 关闭线程池和扫描线程
    def _kill_threads(self, ):
        thread_list = threading.enumerate()
        new_thread_list = []
        [new_thread_list.append(i) for i in thread_list if 'MDCx-Pool' in i.getName()]  # 线程池的线程
        [new_thread_list.append(i) for i in Flags.threads_list]  # 其他开启的线程
        other_name = new_thread_list[-1].getName()
        Flags.total_kills = len(new_thread_list)
        Flags.now_kill = 0
        start_time = time.time()
        self.set_label_file_path.emit(
            f'⛔️ Stopping scraping...\n   Stopping an already running task thread（1/{Flags.total_kills} ...')
        signal.show_log_text(
            f'\n ⛔️ {get_current_time()} Stopped adding new scraping tasks, stopping already running task threads（{Flags.total_kills} ...')
        signal.show_traceback_log(f"⛔️ Stopping running task thread ({Flags.total_kills}) ...")
        i = 0
        for each in new_thread_list:
            i += 1
            signal.show_traceback_log(f'Stopping thread: {i}/{Flags.total_kills} {each.getName()} ...')
        signal.show_traceback_log(
            'The thread is stopping, please wait...\n 🍯 The stop time is related to the number of threads and the tasks that the threads are performing. For example, when performing network requests, file downloads and other IO operations, you need to wait for them to release resources...\n')
        signal.stop = True
        for each in new_thread_list:  # 线程池的线程
            if 'MDCx-Pool' not in each.getName():
                kill_a_thread(each)
            while each.is_alive():
                pass

        signal.stop = False
        self.stop_used_time = get_used_time(start_time)
        signal.show_log_text(
            ' 🕷 %s Thread stopped:%s/%s %s' % (get_current_time(), Flags.total_kills, Flags.total_kills, other_name))
        signal.show_traceback_log(f'All threads have been stopped! ! !({self.stop_used_time}s)\n ⛔️ Scraping has been stopped manually!\n')
        signal.show_log_text(f' ⛔️ {get_current_time()} All threads have been stopped!({self.stop_used_time}s)')
        thread_remain_list = []
        [thread_remain_list.append(i.getName()) for i in threading.enumerate()]  # 剩余线程名字列表
        thread_remain = ', '.join(thread_remain_list)
        print(f"✅ Remaining threads ({len(thread_remain_list)}): {thread_remain}")
        self.show_stop_info_thread()

    # 进度条
    def set_processbar(self, value):
        self.Ui.progressBar_scrape.setProperty("value", value)

    # region 刮削结果显示
    def _addTreeChild(self, result, filename):
        node = QTreeWidgetItem()
        node.setText(0, filename)
        if result == 'succ':
            self.item_succ.addChild(node)
        else:
            self.item_fail.addChild(node)
        # self.Ui.treeWidget_number.verticalScrollBar().setValue(self.Ui.treeWidget_number.verticalScrollBar().maximum())
        # self.Ui.treeWidget_number.setCurrentItem(node)
        # self.Ui.treeWidget_number.scrollToItem(node)

    def show_list_name(self, filename, result, json_data, real_number=''):
        # 添加树状节点
        self._addTreeChild(result, filename)

        # 解析json_data，以在主界面左侧显示
        if not json_data.get('number'):
            json_data['number'] = real_number
        if not json_data.get('actor'):
            json_data['actor'] = ''
        if not json_data.get('title') or result == 'fail':
            json_data['title'] = json_data['error_info']
        if not json_data.get('outline'):
            json_data['outline'] = ''
        if not json_data.get('tag'):
            json_data['tag'] = ''
        if not json_data.get('release'):
            json_data['release'] = ''
        if not json_data.get('runtime'):
            json_data['runtime'] = ''
        if not json_data.get('director'):
            json_data['director'] = ''
        if not json_data.get('series'):
            json_data['series'] = ''
        if not json_data.get('publisher'):
            json_data['publisher'] = ''
        if not json_data.get('studio'):
            json_data['studio'] = ''
        if not json_data.get('poster_path'):
            json_data['poster_path'] = ''
        if not json_data.get('thumb_path'):
            json_data['thumb_path'] = ''
        if not json_data.get('fanart_path'):
            json_data['fanart_path'] = ''
        if not json_data.get('website'):
            json_data['website'] = ''
        if not json_data.get('source'):
            json_data['source'] = ''
        if not json_data.get('c_word'):
            json_data['c_word'] = ''
        if not json_data.get('cd_part'):
            json_data['cd_part'] = ''
        if not json_data.get('leak'):
            json_data['leak'] = ''
        if not json_data.get('mosaic'):
            json_data['mosaic'] = ''
        if not json_data.get('actor_href'):
            json_data['actor_href'] = ''
        json_data['show_name'] = filename
        self.show_name = filename
        signal.add_label_info(json_data)
        self.json_array[filename] = json_data

    def add_label_info_Thread(self, json_data):
        try:
            if not json_data:
                json_data = {
                    'number': '',
                    'actor': '',
                    'all_actor': '',
                    'source': '',
                    'website': '',
                    'title': '',
                    'outline': '',
                    'tag': '',
                    'release': '',
                    'year': '',
                    'runtime': '',
                    'director': '',
                    'series': '',
                    'studio': '',
                    'publisher': '',
                    'poster_path': '',
                    'thumb_path': '',
                    'fanart_path': '',
                    'has_sub': False,
                    'c_word': '',
                    'leak': '',
                    'cd_part': '',
                    'mosaic': '',
                    'destroyed': '',
                    'actor_href': '',
                    'definition': '',
                    'cover_from': '',
                    'poster_from': '',
                    'extrafanart_from': '',
                    'trailer_from': '',
                    'file_path': '',
                    'show_name': '',
                    'country': '',
                }
            number = str(json_data['number'])
            self.Ui.label_number.setToolTip(number)
            if len(number) > 11:
                number = number[:10] + '……'
            self.Ui.label_number.setText(number)
            self.label_number_url = json_data['website']
            actor = str(json_data['actor'])
            if json_data['all_actor'] and 'actor_all,' in config.nfo_include_new:
                actor = str(json_data['all_actor'])
            self.Ui.label_actor.setToolTip(actor)
            if number and not actor:
                actor = config.actor_no_name
            if len(actor) > 10:
                actor = actor[:9] + '……'
            self.Ui.label_actor.setText(actor)
            self.label_actor_url = json_data['actor_href']
            self.file_main_open_path = json_data['file_path']  # 文件路径
            self.show_name = json_data['show_name']
            if json_data.get('source'):
                self.Ui.label_source.setText('data:' + json_data['source'].replace('.main', ''))
            else:
                self.Ui.label_source.setText('')
            self.Ui.label_source.setToolTip(json_data['website'])
            title = json_data['title'].split('\n')[0].strip(' :')
            self.Ui.label_title.setToolTip(title)
            if len(title) > 27:
                title = title[:25] + '……'
            self.Ui.label_title.setText(title)
            outline = str(json_data['outline'])
            self.Ui.label_outline.setToolTip(outline)
            if len(outline) > 38:
                outline = outline[:36] + '……'
            self.Ui.label_outline.setText(outline)
            tag = str(json_data['tag']).strip(" [',']").replace('\'', '')
            self.Ui.label_tag.setToolTip(tag)
            if len(tag) > 76:
                tag = tag[:75] + '……'
            self.Ui.label_tag.setText(tag)
            self.Ui.label_release.setText(str(json_data['release']))
            self.Ui.label_release.setToolTip(str(json_data['release']))
            if json_data['runtime']:
                self.Ui.label_runtime.setText(str(json_data['runtime']) + ' minute')
                self.Ui.label_runtime.setToolTip(str(json_data['runtime']) + ' minute')
            else:
                self.Ui.label_runtime.setText('')
            self.Ui.label_director.setText(str(json_data['director']))
            self.Ui.label_director.setToolTip(str(json_data['director']))
            series = str(json_data['series'])
            self.Ui.label_series.setToolTip(series)
            if len(series) > 32:
                series = series[:31] + '……'
            self.Ui.label_series.setText(series)
            self.Ui.label_studio.setText(str(json_data['studio']))
            self.Ui.label_studio.setToolTip(str(json_data['studio']))
            self.Ui.label_publish.setText(str(json_data['publisher']))
            self.Ui.label_publish.setToolTip(str(json_data['publisher']))
            self.Ui.label_poster.setToolTip('Click to crop the image')
            self.Ui.label_thumb.setToolTip('Click to crop the image')
            if os.path.isfile(json_data['fanart_path']):  # 生成img_path，用来裁剪使用
                json_data['img_path'] = json_data['fanart_path']
            else:
                json_data['img_path'] = json_data['thumb_path']
            self.json_data = json_data
            self.img_path = json_data['img_path']
            if self.Ui.checkBox_cover.isChecked():  # 主界面显示封面和缩略图
                poster_path = json_data['poster_path']
                thumb_path = json_data['thumb_path']
                fanart_path = json_data['fanart_path']
                if not os.path.exists(thumb_path):
                    if os.path.exists(fanart_path):
                        thumb_path = fanart_path

                poster_from = json_data['poster_from']
                cover_from = json_data['cover_from']

                self.set_pixmap_thread(poster_path, thumb_path, poster_from, cover_from)
        except:
            if not signal.stop:
                signal.show_traceback_log(traceback.format_exc())

    def set_pixmap_thread(self, poster_path='', thumb_path='', poster_from='', cover_from=''):
        t = threading.Thread(target=self._set_pixmap, args=(
            poster_path,
            thumb_path,
            poster_from,
            cover_from,
        ))
        t.start()

    def _set_pixmap(self, poster_path='', thumb_path='', poster_from='', cover_from=''):
        poster_pix = [False, '', 'No Cover Image', 156, 220]
        thumb_pix = [False, '', 'No Thumbnail Image', 328, 220]
        if os.path.exists(poster_path):
            poster_pix = get_pixmap(poster_path, poster=True, pic_from=poster_from)
        if os.path.exists(thumb_path):
            thumb_pix = get_pixmap(thumb_path, poster=False, pic_from=cover_from)

        # self.Ui.label_poster_size.setText(poster_pix[2] + '  ' + thumb_pix[2])
        poster_text = poster_pix[2] if poster_pix[2] != 'No Cover Image' else ''
        thumb_text = thumb_pix[2] if thumb_pix[2] != 'No Thumbnail Image' else ''
        self.set_pic_text.emit((poster_text + ' ' + thumb_text).strip())
        self.set_pic_pixmap.emit(poster_pix, thumb_pix)

    def resize_label_and_setpixmap(self, poster_pix, thumb_pix):
        self.Ui.label_poster.resize(poster_pix[3], poster_pix[4])
        self.Ui.label_thumb.resize(thumb_pix[3], thumb_pix[4])

        if poster_pix[0]:
            self.Ui.label_poster.setPixmap(poster_pix[1])
        else:
            self.Ui.label_poster.setText(poster_pix[2])

        if thumb_pix[0]:
            self.Ui.label_thumb.setPixmap(thumb_pix[1])
        else:
            self.Ui.label_thumb.setText(thumb_pix[2])

    # endregion

    # 主界面-点击树状条目
    def treeWidget_number_clicked(self, qmodeLindex):
        item = self.Ui.treeWidget_number.currentItem()
        if item.text(0) != 'Success' and item.text(0) != 'Failure':
            try:
                index_json = str(item.text(0))
                signal.add_label_info(self.json_array[str(index_json)])
                if not self.Ui.widget_nfo.isHidden():
                    self._show_nfo_info()
            except:
                signal.show_traceback_log(item.text(0) + ': No info!')

    def _check_main_file_path(self):
        if not self.file_main_open_path:
            QMessageBox.about(self, 'No target file', 'Please scrape before use!')
            signal.show_scrape_info('💡 Please scrape before use!%s' % get_current_time())
            return False
        return True

    def main_play_click(self):
        """
        主界面点播放
        """
        # 发送hover事件，清除hover状态（因为弹窗后，失去焦点，状态不会变化）
        self.Ui.pushButton_play.setAttribute(Qt.WA_UnderMouse, False)
        event = QHoverEvent(QEvent.HoverLeave, QPoint(40, 40), QPoint(0, 0))
        QApplication.sendEvent(self.Ui.pushButton_play, event)
        if self._check_main_file_path():
            file_path = convert_path(self.file_main_open_path)
            # mac需要改为无焦点状态，不然弹窗失去焦点后，再切换回来会有找不到焦点的问题（windows无此问题）
            # if not self.is_windows:
            #     self.setWindowFlags(self.windowFlags() | Qt.WindowDoesNotAcceptFocus)
            #     self.show()
            # 启动线程打开文件
            t = threading.Thread(target=_open_file_thread, args=(self.file_main_open_path, False))
            t.start()

    def main_open_folder_click(self):
        """
        主界面点打开文件夹
        """
        self.Ui.pushButton_open_folder.setAttribute(Qt.WA_UnderMouse, False)
        event = QHoverEvent(QEvent.HoverLeave, QPoint(40, 40), QPoint(0, 0))
        QApplication.sendEvent(self.Ui.pushButton_open_folder, event)
        if self._check_main_file_path():
            file_path = convert_path(self.file_main_open_path)
            # mac需要改为无焦点状态，不然弹窗失去焦点后，再切换回来会有找不到焦点的问题（windows无此问题）
            # if not self.is_windows:
            #     self.setWindowFlags(self.windowFlags() | Qt.WindowDoesNotAcceptFocus)
            #     self.show()
            # 启动线程打开文件
            t = threading.Thread(target=_open_file_thread, args=(self.file_main_open_path, True))
            t.start()

    def main_open_nfo_click(self):
        """
        主界面点打开nfo
        """
        self.Ui.pushButton_open_nfo.setAttribute(Qt.WA_UnderMouse, False)
        event = QHoverEvent(QEvent.HoverLeave, QPoint(40, 40), QPoint(0, 0))
        QApplication.sendEvent(self.Ui.pushButton_open_nfo, event)
        if self._check_main_file_path():
            self.Ui.widget_nfo.show()
            self._show_nfo_info()

    def main_open_right_menu(self):
        """
        主界面点打开右键菜单
        """
        # 发送hover事件，清除hover状态（因为弹窗后，失去焦点，状态不会变化）
        self.Ui.pushButton_right_menu.setAttribute(Qt.WA_UnderMouse, False)
        event = QHoverEvent(QEvent.HoverLeave, QPoint(40, 40), QPoint(0, 0))
        QApplication.sendEvent(self.Ui.pushButton_right_menu, event)
        self._menu()

    def search_by_number_clicked(self):
        """
        主界面点输入番号
        """
        if self._check_main_file_path():
            file_path = self.file_main_open_path
            main_file_name = split_path(file_path)[1]
            default_text = os.path.splitext(main_file_name)[0].upper()
            text, ok = QInputDialog.getText(self, 'Enter number and re-scrape', f'File name: {main_file_name}\nPlease enter the number:',
                                            text=default_text)
            if ok and text:
                Flags.again_dic[file_path] = [text, '', '']
                signal.show_scrape_info('💡 Scrape added!%s' % get_current_time())
                if self.Ui.pushButton_start_cap.text() == 'Start':
                    again_search()

    def search_by_url_clicked(self):
        """
        主界面点输入网址
        """
        if self._check_main_file_path():
            file_path = self.file_main_open_path
            main_file_name = split_path(file_path)[1]
            text, ok = QInputDialog.getText(self, 'Enter the URL to scrape again',
                                            f'File name: {main_file_name}\nSupport website:airav_cc、airav、avsex、avsox、dmm、getchu、fc2'
                                            f'、fc2club、fc2hub、iqqtv、jav321、javbus、javdb、freejavbt、javlibrary、mdtv'
                                            f'、madouqu、mgstage、7mmtv、xcity、mywife、giga、faleno、dahlia、fantastica'
                                            f'、prestige、hdouban、lulubar、love6、cnmdb、theporndb、kin8\nPlease enter the URL corresponding to the number (not the homepage address of the website!!! It is the address of the number page!!!）:')
            if ok and text:
                website, url = deal_url(text)
                if website:
                    Flags.again_dic[file_path] = ['', url, website]
                    signal.show_scrape_info('💡 Scrape added!%s' % get_current_time())
                    if self.Ui.pushButton_start_cap.text() == 'Start':
                        again_search()
                else:
                    signal.show_scrape_info('💡 Unsupported website!%s' % get_current_time())

    def main_del_file_click(self):
        """
        主界面点删除文件
        """
        if self._check_main_file_path():
            file_path = self.file_main_open_path
            box = QMessageBox(QMessageBox.Warning, 'Delete files', f'Files to be deleted: \n{file_path}\n\n Are you sure you want to delete it?')
            box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            box.button(QMessageBox.Yes).setText('Delete files')
            box.button(QMessageBox.No).setText('Cancel')
            box.setDefaultButton(QMessageBox.No)
            reply = box.exec()
            if reply != QMessageBox.Yes:
                return
            delete_file(file_path)
            signal.show_scrape_info('💡 File deleted!%s' % get_current_time())

    def main_del_folder_click(self):
        """
        主界面点删除文件夹
        """
        if self._check_main_file_path():
            folder_path = split_path(self.file_main_open_path)[0]
            box = QMessageBox(QMessageBox.Warning, 'Delete files', f'Folder to be deleted: \n{folder_path}\n\n Are you sure you want to delete it?')
            box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            box.button(QMessageBox.Yes).setText('Delete files and folders')
            box.button(QMessageBox.No).setText('Cancel')
            box.setDefaultButton(QMessageBox.No)
            reply = box.exec()
            if reply != QMessageBox.Yes:
                return
            shutil.rmtree(folder_path, ignore_errors=True)
            self.show_scrape_info('💡 Folder deleted!%s' % get_current_time())

    def _pic_main_clicked(self):
        """
        主界面点图片
        """
        self.cutwindow.showimage(self.img_path, self.json_data)
        self.cutwindow.show()

    # 主界面-开关封面显示
    def checkBox_cover_clicked(self):
        if not self.Ui.checkBox_cover.isChecked():
            self.Ui.label_poster.setText("Cover image")
            self.Ui.label_thumb.setText("Thumbnail")
            self.Ui.label_poster.resize(156, 220)
            self.Ui.label_thumb.resize(328, 220)
            self.Ui.label_poster_size.setText("")
            self.Ui.label_thumb_size.setText("")
        else:
            signal.add_label_info(self.json_data)

    # region 主界面编辑nfo
    def _show_nfo_info(self):
        try:
            json_data = self.json_array[self.show_name]
            self.now_show_name = json_data['show_name']
            title, originaltitle, studio, publisher, year, outline, runtime, director, actor_photo, actor, release, tag, number, cover, poster, website, series, mosaic, definition, trailer, letters = get_info(
                json_data)
            file_path = json_data.get('file_path')
            number = json_data.get('number')
            originalplot = json_data.get('originalplot')
            score = json_data.get('score')
            wanted = json_data.get('wanted')
            country = json_data.get('country')
            self.Ui.label_nfo.setText(file_path)
            self.Ui.lineEdit_nfo_number.setText(number)
            if json_data['all_actor'] and 'actor_all,' in config.nfo_include_new:
                actor = str(json_data['all_actor'])
            self.Ui.lineEdit_nfo_actor.setText(actor)
            self.Ui.lineEdit_nfo_year.setText(year)
            self.Ui.lineEdit_nfo_title.setText(title)
            self.Ui.lineEdit_nfo_originaltitle.setText(originaltitle)
            self.Ui.textEdit_nfo_outline.setPlainText(outline)
            self.Ui.textEdit_nfo_originalplot.setPlainText(originalplot)
            self.Ui.textEdit_nfo_tag.setPlainText(tag)
            self.Ui.lineEdit_nfo_release.setText(release)
            self.Ui.lineEdit_nfo_runtime.setText(runtime)
            self.Ui.lineEdit_nfo_score.setText(score)
            self.Ui.lineEdit_nfo_wanted.setText(wanted)
            self.Ui.lineEdit_nfo_director.setText(director)
            self.Ui.lineEdit_nfo_series.setText(series)
            self.Ui.lineEdit_nfo_studio.setText(studio)
            self.Ui.lineEdit_nfo_publisher.setText(publisher)
            self.Ui.lineEdit_nfo_poster.setText(poster)
            self.Ui.lineEdit_nfo_cover.setText(cover)
            self.Ui.lineEdit_nfo_trailer.setText(trailer)
            self.Ui.lineEdit_nfo_website.setText(website)
            if not country:
                if '.' in number:
                    country = 'US'
                else:
                    country = 'JP'
            AllItems = [self.Ui.comboBox_nfo.itemText(i) for i in range(self.Ui.comboBox_nfo.count())]
            self.Ui.comboBox_nfo.setCurrentIndex(AllItems.index(country))
        except:
            if not signal.stop:
                signal.show_traceback_log(traceback.format_exc())

    def save_nfo_info(self):
        try:
            json_data = self.json_array[self.now_show_name]
            file_path = json_data['file_path']
            nfo_path = os.path.splitext(file_path)[0] + '.nfo'
            nfo_folder = split_path(file_path)[0]
            json_data['number'] = self.Ui.lineEdit_nfo_number.text()
            if 'actor_all,' in config.nfo_include_new:
                json_data['all_actor'] = self.Ui.lineEdit_nfo_actor.text()
            json_data['actor'] = self.Ui.lineEdit_nfo_actor.text()
            json_data['year'] = self.Ui.lineEdit_nfo_year.text()
            json_data['title'] = self.Ui.lineEdit_nfo_title.text()
            json_data['originaltitle'] = self.Ui.lineEdit_nfo_originaltitle.text()
            json_data['outline'] = self.Ui.textEdit_nfo_outline.toPlainText()
            json_data['originalplot'] = self.Ui.textEdit_nfo_originalplot.toPlainText()
            json_data['tag'] = self.Ui.textEdit_nfo_tag.toPlainText()
            json_data['release'] = self.Ui.lineEdit_nfo_release.text()
            json_data['runtime'] = self.Ui.lineEdit_nfo_runtime.text()
            json_data['score'] = self.Ui.lineEdit_nfo_score.text()
            json_data['wanted'] = self.Ui.lineEdit_nfo_wanted.text()
            json_data['director'] = self.Ui.lineEdit_nfo_director.text()
            json_data['series'] = self.Ui.lineEdit_nfo_series.text()
            json_data['studio'] = self.Ui.lineEdit_nfo_studio.text()
            json_data['publisher'] = self.Ui.lineEdit_nfo_publisher.text()
            json_data['poster'] = self.Ui.lineEdit_nfo_poster.text()
            json_data['cover'] = self.Ui.lineEdit_nfo_cover.text()
            json_data['trailer'] = self.Ui.lineEdit_nfo_trailer.text()
            json_data['website'] = self.Ui.lineEdit_nfo_website.text()
            json_data['country'] = self.Ui.comboBox_nfo.currentText()
            if write_nfo(json_data, nfo_path, nfo_folder, file_path, edit_mode=True):
                self.Ui.label_save_tips.setText(f'Saved! {get_current_time()}')
                signal.add_label_info(json_data)
            else:
                self.Ui.label_save_tips.setText(f'Save failed! {get_current_time()}')
        except:
            if not signal.stop:
                signal.show_traceback_log(traceback.format_exc())

    # endregion

    # 主界面左下角显示信息
    def show_scrape_info(self, before_info=''):
        try:
            if Flags.file_mode == FileMode.Single:
                scrape_info = '💡 single File Scraping\n💠 %s · %s' % (Flags.main_mode_text, self.Ui.comboBox_website.currentText())
            else:
                scrape_info = '💠 %s · %s' % (Flags.main_mode_text, Flags.scrape_like_text)
                if config.scrape_like == 'single':
                    scrape_info = f"💡 {config.website_single} scrape\n" + scrape_info
            if config.soft_link == 1:
                scrape_info = '🍯 Soft Link · Open\n' + scrape_info
            elif config.soft_link == 2:
                scrape_info = '🍯 Hard Link · Open\n' + scrape_info
            after_info = '\n%s\n🛠 %s\n🐰 MDCx %s' % (scrape_info, config.file, self.localversion)
            self.label_show_version.emit(before_info + after_info + self.new_version)
        except:
            signal.show_traceback_log(traceback.format_exc())

    # region 获取/保存成功刮削列表
    def pushButton_success_list_save_clicked(self):
        box = QMessageBox(QMessageBox.Warning, 'Save success list', 'Are you sure you want to save the current list as a list of successfully scraped files?')
        box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        box.button(QMessageBox.Yes).setText('Keep')
        box.button(QMessageBox.No).setText('Cancel')
        box.setDefaultButton(QMessageBox.No)
        reply = box.exec()
        if reply == QMessageBox.Yes:
            with open(resources.userdata_path('success.txt'), 'w', encoding='utf-8', errors='ignore') as f:
                f.write(self.Ui.textBrowser_show_success_list.toPlainText().replace('No files successfully scraped yet', '').strip())
                get_success_list()
            self.Ui.widget_show_success.hide()

    def pushButton_success_list_clear_clicked(self):
        box = QMessageBox(QMessageBox.Warning, 'Clear success list', 'Are you sure you want to clear the current list of successfully scraped files?')
        box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        box.button(QMessageBox.Yes).setText('Clear')
        box.button(QMessageBox.No).setText('Cancel')
        box.setDefaultButton(QMessageBox.No)
        reply = box.exec()
        if reply == QMessageBox.Yes:
            Flags.success_list.clear()
            save_success_list()
            self.Ui.widget_show_success.hide()

    def pushButton_view_success_file_clicked(self):
        self.Ui.widget_show_success.show()
        info = 'No files successfully scraped yet'
        if len(Flags.success_list):
            temp = list(Flags.success_list)
            temp.sort()
            info = '\n'.join(temp)
        self.Ui.textBrowser_show_success_list.setText(info)

    # endregion
    # endregion

    # region 日志页
    # 日志页点展开折叠日志
    def pushButton_show_hide_logs_clicked(self):
        if self.Ui.textBrowser_log_main_2.isHidden():
            self.show_hide_logs(True)
        else:
            self.show_hide_logs(False)

    # 日志页点展开折叠日志
    def show_hide_logs(self, show):
        if show:
            self.Ui.pushButton_show_hide_logs.setIcon(QIcon(resources.hide_logs_icon))
            self.Ui.textBrowser_log_main_2.show()
            self.Ui.textBrowser_log_main.resize(790, 418)
            self.Ui.textBrowser_log_main.verticalScrollBar().setValue(
                self.Ui.textBrowser_log_main.verticalScrollBar().maximum())
            self.Ui.textBrowser_log_main_2.verticalScrollBar().setValue(
                self.Ui.textBrowser_log_main_2.verticalScrollBar().maximum())

            # self.Ui.textBrowser_log_main_2.moveCursor(self.Ui.textBrowser_log_main_2.textCursor().End)

        else:
            self.Ui.pushButton_show_hide_logs.setIcon(QIcon(resources.show_logs_icon))
            self.Ui.textBrowser_log_main_2.hide()
            self.Ui.textBrowser_log_main.resize(790, 689)
            self.Ui.textBrowser_log_main.verticalScrollBar().setValue(
                self.Ui.textBrowser_log_main.verticalScrollBar().maximum())

    # 日志页点展开折叠失败列表
    def pushButton_show_hide_failed_list_clicked(self):
        if self.Ui.textBrowser_log_main_3.isHidden():
            self.show_hide_failed_list(True)
        else:
            self.show_hide_failed_list(False)

    # 日志页点展开折叠失败列表
    def show_hide_failed_list(self, show):
        if show:
            self.Ui.textBrowser_log_main_3.show()
            self.Ui.pushButton_scraper_failed_list.show()
            self.Ui.pushButton_save_failed_list.show()
            self.Ui.textBrowser_log_main_3.verticalScrollBar().setValue(
                self.Ui.textBrowser_log_main_3.verticalScrollBar().maximum())

        else:
            self.Ui.pushButton_save_failed_list.hide()
            self.Ui.textBrowser_log_main_3.hide()
            self.Ui.pushButton_scraper_failed_list.hide()

    # 日志页点一键刮削失败列表
    def pushButton_scraper_failed_list_clicked(self):
        if len(Flags.failed_file_list) and self.Ui.pushButton_start_cap.text() == 'Start':
            start_new_scrape(FileMode.Default, movie_list=Flags.failed_file_list)
            self.show_hide_failed_list(False)

    # 日志页点另存失败列表
    def pushButton_save_failed_list_clicked(self):
        if len(Flags.failed_file_list) or True:
            log_name = 'failed_' + time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime()) + '.txt'
            log_name = convert_path(os.path.join(get_movie_path_setting()[0], log_name))
            filename, filetype = QFileDialog.getSaveFileName(None, "Save failed file list", log_name, "Text Files (*.txt)",
                                                             options=self.options)
            if filename:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(self.Ui.textBrowser_log_main_3.toPlainText().strip())

    # 显示详细日志
    def show_detail_log(self):
        text = signal.get_log()
        if text:
            self.main_req_logs_show.emit(add_html(text))
            if self.req_logs_counts < 10000:
                self.req_logs_counts += 1
            else:
                self.req_logs_counts = 0
                self.req_logs_clear.emit('')
                self.main_req_logs_show.emit(add_html(' 🗑️ There are too many logs, the screen has been cleared!'))

    # 日志页面显示内容
    def show_log_text(self, text):
        if not text:
            return
        text = str(text)
        if config.save_log == 'on':  # 保存日志
            try:
                Flags.log_txt.write((text + '\n').encode('utf-8'))
            except:
                log_folder = os.path.join(get_main_path(), 'Log')
                if not os.path.exists(log_folder):
                    os.makedirs(log_folder)
                log_name = time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime()) + '.txt'
                log_name = convert_path(os.path.join(log_folder, log_name))

                Flags.log_txt = open(log_name, "wb", buffering=0)
                signal.show_log_text('Create log file: ' + log_name + '\n')
                signal.show_log_text(text)
                return
        try:
            self.main_logs_show.emit(add_html(text))
            if self.logs_counts < 10000:
                self.logs_counts += 1
            else:
                self.logs_counts = 0
                self.main_logs_clear.emit('')
                self.main_logs_show.emit(add_html(' 🗑️ There are too many logs, the screen has been cleared!'))
            # self.show_traceback_log(self.Ui.textBrowser_log_main.document().lineCount())

        except:
            signal.show_traceback_log(traceback.format_exc())
            self.Ui.textBrowser_log_main.append(traceback.format_exc())

    # endregion

    # region 工具页
    # 工具页面点查看本地番号
    def label_local_number_clicked(self, test):
        if self.Ui.pushButton_find_missing_number.isEnabled():
            self.pushButton_show_log_clicked()  # 点击按钮后跳转到日志页面
            if self.Ui.lineEdit_actors_name.text() != config.actors_name:  # 保存配置
                self.pushButton_save_config_clicked()
            try:
                t = threading.Thread(target=check_missing_number, args=(False,))
                t.start()  # 启动线程,即让线程开始执行
            except:
                signal.show_traceback_log(traceback.format_exc())
                signal.show_log_text(traceback.format_exc())

    # 工具页面本地资源库点选择目录
    def pushButton_select_local_library_clicked(self):
        media_folder_path = self._get_select_folder_path()
        if media_folder_path:
            self.Ui.lineEdit_local_library_path.setText(convert_path(media_folder_path))
            self.pushButton_save_config_clicked()

    # 工具页面网盘目录点选择目录
    def pushButton_select_netdisk_path_clicked(self):
        media_folder_path = self._get_select_folder_path()
        if media_folder_path:
            self.Ui.lineEdit_netdisk_path.setText(convert_path(media_folder_path))
            self.pushButton_save_config_clicked()

    # 工具页面本地目录点选择目录
    def pushButton_select_localdisk_path_clicked(self):
        media_folder_path = self._get_select_folder_path()
        if media_folder_path:
            self.Ui.lineEdit_localdisk_path.setText(convert_path(media_folder_path))
            self.pushButton_save_config_clicked()

    # 工具/设置页面点选择目录
    def pushButton_select_media_folder_clicked(self):
        media_folder_path = self._get_select_folder_path()
        if media_folder_path:
            self.Ui.lineEdit_movie_path.setText(convert_path(media_folder_path))
            self.pushButton_save_config_clicked()

    # 工具-软链接助手
    def pushButton_creat_symlink_clicked(self):
        """
        工具点一键创建软链接
        """
        self.pushButton_show_log_clicked()  # 点击按钮后跳转到日志页面

        if bool('copy_netdisk_nfo' in config.switch_on) != bool(
                self.Ui.checkBox_copy_netdisk_nfo.isChecked()):
            self.pushButton_save_config_clicked()

        try:
            t = threading.Thread(target=newtdisk_creat_symlink,
                                 args=(bool(self.Ui.checkBox_copy_netdisk_nfo.isChecked()),))
            Flags.threads_list.append(t)
            t.start()  # 启动线程,即让线程开始执行
        except:
            signal.show_traceback_log(traceback.format_exc())
            signal.show_log_text(traceback.format_exc())

    # 工具-检查番号
    def pushButton_find_missing_number_clicked(self):
        """
        工具点检查缺失番号
        """
        self.pushButton_show_log_clicked()  # 点击按钮后跳转到日志页面

        # 如果本地资源库或演员与配置内容不同，则自动保存
        if self.Ui.lineEdit_actors_name.text() != config.actors_name \
                or self.Ui.lineEdit_local_library_path.text() != config.local_library:
            self.pushButton_save_config_clicked()
        try:
            t = threading.Thread(target=check_missing_number, args=(True,))
            Flags.threads_list.append(t)
            t.start()  # 启动线程,即让线程开始执行
        except:
            signal.show_traceback_log(traceback.format_exc())
            signal.show_log_text(traceback.format_exc())

    # 工具-单文件刮削
    def pushButton_select_file_clicked(self):
        media_path = self.Ui.lineEdit_movie_path.text()  # 获取待刮削目录作为打开目录
        if not media_path:
            media_path = get_main_path()
        file_path, filetype = QFileDialog.getOpenFileName(None, "Select video file", media_path,
                                                          "Movie Files(*.mp4 " "*.avi *.rmvb *.wmv " "*.mov *.mkv *.flv *.ts " "*.webm *.MP4 *.AVI " "*.RMVB *.WMV *.MOV " "*.MKV *.FLV *.TS " "*.WEBM);;All Files(*)",
                                                          options=self.options)
        if file_path:
            self.Ui.lineEdit_single_file_path.setText(convert_path(file_path))

    def pushButton_start_single_file_clicked(self):  # 点刮削
        Flags.single_file_path = self.Ui.lineEdit_single_file_path.text().strip()
        if not Flags.single_file_path:
            signal.show_scrape_info('💡 Please select a file!')
            return

        if not os.path.isfile(Flags.single_file_path):
            signal.show_scrape_info('💡 File does not exist!')  # 主界面左下角显示信息
            return

        if not self.Ui.lineEdit_appoint_url.text():
            signal.show_scrape_info('💡 Please fill in the number and URL!')  # 主界面左下角显示信息
            return

        self.pushButton_show_log_clicked()  # 点击刮削按钮后跳转到日志页面
        Flags.appoint_url = self.Ui.lineEdit_appoint_url.text().strip()
        # 单文件刮削从用户输入的网址中识别网址名，复用现成的逻辑=>主页面输入网址刮削
        website, url = deal_url(Flags.appoint_url)
        if website:
            Flags.website_name = website
        else:
            signal.show_scrape_info('💡 Unsupported website!%s' % get_current_time())
            return
        start_new_scrape(FileMode.Single)

    def pushButton_select_file_clear_info_clicked(self):  # 点清空信息
        self.Ui.lineEdit_single_file_path.setText('')
        self.Ui.lineEdit_appoint_url.setText('')

        # self.Ui.lineEdit_movie_number.setText('')

    # 工具-裁剪封面图
    def pushButton_select_thumb_clicked(self):
        path = self.Ui.lineEdit_movie_path.text()
        if not path:
            path = get_main_path()
        file_path, fileType = QFileDialog.getOpenFileName(None, "Select thumbnail", path,
                                                          "Picture Files(*.jpg *.png);;All Files(*)",
                                                          options=self.options)
        if file_path != '':
            self.cutwindow.showimage(file_path)
            self.cutwindow.show()

    # 工具-视频移动
    def pushButton_move_mp4_clicked(self):
        box = QMessageBox(QMessageBox.Warning, 'Mobile video and subtitles', 'Are you sure you want to move the video and subtitles?')
        box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        box.button(QMessageBox.Yes).setText('Move')
        box.button(QMessageBox.No).setText('Cancel')
        box.setDefaultButton(QMessageBox.No)
        reply = box.exec()
        if reply == QMessageBox.Yes:
            self.pushButton_show_log_clicked()  # 点击开始移动按钮后跳转到日志页面
            try:
                t = threading.Thread(target=self._move_file_thread)
                Flags.threads_list.append(t)
                t.start()  # 启动线程,即让线程开始执行
            except:
                signal.show_traceback_log(traceback.format_exc())
                signal.show_log_text(traceback.format_exc())

    def _move_file_thread(self):
        signal.change_buttons_status.emit()
        movie_type = self.Ui.lineEdit_movie_type.text().lower()
        sub_type = self.Ui.lineEdit_sub_type.text().lower().replace('|.txt', '')
        all_type = movie_type.strip('|') + '|' + sub_type.strip('|')
        movie_path = config.media_path.replace('\\', '/')  # 用户设置的扫描媒体路径
        if movie_path == '':  # 未设置为空时，使用主程序目录
            movie_path = get_main_path()
        escape_dir = self.Ui.lineEdit_escape_dir_move.text().replace('\\', '/')
        escape_dir = escape_dir + ',Movie_moved'
        escape_folder_list = escape_dir.split(',')
        escape_folder_new_list = []
        for es in escape_folder_list:  # 排除目录可以多个，以，,分割
            es = es.strip(' ')
            if es:
                es = get_path(movie_path, es).replace('\\', '/')
                if es[-1] != '/':  # 路径尾部添加“/”，方便后面move_list查找时匹配路径
                    es += '/'
                escape_folder_new_list.append(es)
        movie_list = movie_lists(escape_folder_new_list, all_type, movie_path)
        if not movie_list:
            signal.show_log_text("No movie found!")
            signal.show_log_text("================================================================================")
            signal.reset_buttons_status.emit()
            return
        des_path = os.path.join(movie_path, 'Movie_moved')
        if not os.path.exists(des_path):
            signal.show_log_text('Created folder: Movie_moved')
            os.makedirs(des_path)
        signal.show_log_text('Start move movies...')
        skip_list = []
        for file_path in movie_list:
            file_name = split_path(file_path)[1]
            file_ext = os.path.splitext(file_name)[1]
            try:
                # move_file(file_path, des_path)
                shutil.move(file_path, des_path)
                if file_ext in movie_type:
                    signal.show_log_text('   Move movie: ' + file_name + ' to Movie_moved Success!')
                else:
                    signal.show_log_text('   Move sub: ' + file_name + ' to Movie_moved Success!')
            except Exception as e:
                skip_list.append([file_name, file_path, str(e)])
        if skip_list:
            signal.show_log_text("\n%s file(s) did not move!" % len(skip_list))
            i = 0
            for info in skip_list:
                i += 1
                signal.show_log_text("[%s] %s\n file path: %s\n %s\n" % (i, info[0], info[1], info[2]))
        signal.show_log_text("Move movies finished!")
        signal.show_log_text("================================================================================")
        signal.reset_buttons_status.emit()

    # endregion

    # region 设置页
    # region 选择目录
    # 设置-目录-软链接目录-点选择目录
    def pushButton_select_softlink_folder_clicked(self):
        media_folder_path = self._get_select_folder_path()
        if media_folder_path:
            self.Ui.lineEdit_movie_softlink_path.setText(convert_path(media_folder_path))
            self.pushButton_save_config_clicked()

    # 设置-目录-成功输出目录-点选择目录
    def pushButton_select_sucess_folder_clicked(self):
        media_folder_path = self._get_select_folder_path()
        if media_folder_path:
            self.Ui.lineEdit_success.setText(convert_path(media_folder_path))
            self.pushButton_save_config_clicked()

    # 设置-目录-失败输出目录-点选择目录
    def pushButton_select_failed_folder_clicked(self):
        media_folder_path = self._get_select_folder_path()
        if media_folder_path:
            self.Ui.lineEdit_fail.setText(convert_path(media_folder_path))
            self.pushButton_save_config_clicked()

    # 设置-字幕-字幕文件目录-点选择目录
    def pushButton_select_subtitle_folder_clicked(self):
        media_folder_path = self._get_select_folder_path()
        if media_folder_path:
            self.Ui.lineEdit_sub_folder.setText(convert_path(media_folder_path))
            self.pushButton_save_config_clicked()

    # 设置-头像-头像文件目录-点选择目录
    def pushButton_select_actor_photo_folder_clicked(self):
        media_folder_path = self._get_select_folder_path()
        if media_folder_path:
            self.Ui.lineEdit_actor_photo_folder.setText(convert_path(media_folder_path))
            self.pushButton_save_config_clicked()

    # 设置-其他-配置文件目录-点选择目录
    def pushButton_select_config_folder_clicked(self):
        media_folder_path = convert_path(self._get_select_folder_path())
        if media_folder_path and media_folder_path != config.folder:
            config_path = os.path.join(media_folder_path, 'config.ini')
            with open(config.get_mark_file_path(), 'w', encoding='UTF-8') as f:
                f.write(config_path)
            if os.path.isfile(config_path):
                temp_dark = self.dark_mode
                temp_window_radius = self.window_radius
                self.load_config()
                if temp_dark != self.dark_mode and temp_window_radius == self.window_radius:
                    self.show_flag = True
                    self._windows_auto_adjust()
            else:
                self.Ui.lineEdit_config_folder.setText(media_folder_path)
                self.pushButton_save_config_clicked()
            signal.show_scrape_info('💡 Directory has been changed!%s' % get_current_time())

    # endregion

    # 设置-演员-补全信息-演员信息数据库-选择文件按钮
    def pushButton_select_actor_info_db_clicked(self):
        database_path, _ = QFileDialog.getOpenFileName(None, "Select database file", config.folder, options=self.options)
        if database_path:
            self.Ui.lineEdit_actor_db_path.setText(convert_path(database_path))
            self.pushButton_save_config_clicked()

    # region 设置-问号
    def pushButton_tips_normal_mode_clicked(self):
        self._show_tips(self.Ui.pushButton_tips_normal_mode.toolTip())

    def pushButton_tips_sort_mode_clicked(self):
        self._show_tips(self.Ui.pushButton_tips_sort_mode.toolTip())

    def pushButton_tips_update_mode_clicked(self):
        self._show_tips(self.Ui.pushButton_tips_update_mode.toolTip())

    def pushButton_tips_read_mode_clicked(self):
        self._show_tips(self.Ui.pushButton_tips_read_mode.toolTip())

    def pushButton_tips_soft_clicked(self):
        self._show_tips(self.Ui.pushButton_tips_soft.toolTip())

    def pushButton_tips_hard_clicked(self):
        self._show_tips(self.Ui.pushButton_tips_hard.toolTip())

    # 设置-显示说明信息
    def _show_tips(self, msg):
        self.Ui.textBrowser_show_tips.setText(msg)
        self.Ui.widget_show_tips.show()

    # 设置-刮削网站和字段中的详细说明弹窗
    def pushButton_scrape_note_clicked(self):
        self._show_tips('''<html><head/><body><p><span style=" font-weight:700;">1. For the following types and numbers, please specify the scraping website, which can provide the success rate and save scraping time.</span></p><p>· Europe and America: theporndb</p><p>· Domestic: mdtv, madouqu, hdouban, cnmdb, love6</p><p>· Lifan: getchu_dmm</p><p>· Mywife：mywife</p><p>· GIGA: giga</p><p>· Kin8：Kin8</p><p><span style=" font-weight:700;">2. Trailers and stills cannot be downloaded, please select "Field Priority"</span></p>\
            <p>· Speed ​​first: fields come from a website</p><p>· Field priority: scraping by field, different fields come from different websites</p><p>Field first information will be much better than speed first! It is recommended to use "field priority" by default</p><p>When there are a large number of files and the number of threads is more than 10, the time consumption of the two is about the same.</p><p><span style=" font-weight:700;">3. Match another number information or wrong number with the same name</span></p><p>Please use single file scraping. Path: Tools - Single File Scraping</p><p><span style=" font-weight:700;">4. IP blocked due to frequent requests</span></p><p>It is recommended to replace the node and enable "intermittent scraping": Settings - Others - Intermittent scraping</p></body></html>''')

    # 设置-刮削网站和字段中的详细说明弹窗
    def pushButton_field_tips_website_clicked(self):
        self._show_tips('''<html><head/><body><p><span style=" font-weight:700;">Field description</span></p><p>For example 🌰, when scraping the introduction field of a coded number, it is assumed that:</p><p>1. The websites with coded numbers are (1, 2, 3, 4, 5, 6, 7)</p><p>2. The website whose introduction field is set is (9, 5, 2, 7)</p><p>3. The excluded websites in the introduction field are (3, 6) (for example, websites 3 and 6 do not have introductions, so there is no need to request them at this time, so they can be added to the excluded websites)</p><p><br/></p><p><span style=" font-weight:700;">The program will generate a sequence table of requested websites through the following methods:</span></p><p>1. Take the intersection of the profile field website and the coded website: (5, 2, 7) (This order is subject to the website order set in the profile field)</p><p>\
            2. Take the remaining websites with coded numbers and add them at the end. The result is (5, 2, 7, 1, 3, 4, 6) (This order is based on the order of the websites set with coded numbers. The reason for the supplement is that when If the set field website is not requested, you can continue to use the coded website to query. If you do not want to query, you can add an excluded website or remove the check box to complete the fields as much as possible)</p><p>3. Remove the excluded websites, and the website request sequence for generating profiles is (5, 2, 7, 1, 4)</p><p>The program will scrape in this order, that is, request 5 first, and when 5 is obtained successfully, the request will not continue. When 5 is not obtained successfully, continue to request 2 in sequence, and so on... The same goes for scraping other numbers and fields.</p></body></html>''')

    # 设置-刮削网站和字段中的详细说明弹窗
    def pushButton_field_tips_nfo_clicked(self):
        msg = '''
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n\
<movie>\n\
    <plot><![CDATA[剧情简介]]></plot>\n\
    <outline><![CDATA[剧情简介]]></outline>\n\
    <originalplot><![CDATA[原始剧情简介]]></originalplot>\n\
    <tagline>发行日期 XXXX-XX-XX</tagline> \n\
    <premiered>发行日期</premiered>\n\
    <releasedate>发行日期</releasedate>\n\
    <release>发行日期</release>\n\
    <num>番号</num>\n\
    <title>标题</title>\n\
    <originaltitle>原始标题</originaltitle>\n\
    <sorttitle>类标题 </sorttitle>\n\
    <mpaa>家长分级</mpaa>\n\
    <customrating>自定义分级</customrating>\n\
    <actor>\n\
        <name>名字</name>\n\
        <type>类型：演员</type>\n\
    </actor>\n\
    <director>导演</director>\n\
    <rating>评分</rating>\n\
    <criticrating>影评人评分</criticrating>\n\
    <votes>想看人数</votes>\n\
    <year>年份</year>\n\
    <runtime>时长</runtime>\n\
    <series>系列</series>\n\
    <set>\n\
        <name>合集</name>\n\
    </set>\n\
    <studio>片商/制作商</studio> \n\
    <maker>片商/制作商</maker>\n\
    <publisher>厂牌/发行商</publisher>\n\
    <label>厂牌/发行商</label>\n\
    <tag>标签</tag>\n\
    <genre>风格</genre>\n\
    <cover>背景图地址</cover>\n\
    <poster>封面图地址</poster>\n\
    <trailer>预告片地址</trailer>\n\
    <website>刮削网址</website>\n\
</movie>\n\
        '''
        self._show_tips(msg)

    # endregion

    # 设置-刮削目录 点击检查待刮削目录并清理文件
    def pushButton_check_and_clean_files_clicked(self):
        if not config.can_clean:
            self.pushButton_save_config_clicked()
        self.pushButton_show_log_clicked()
        try:
            t = threading.Thread(target=check_and_clean_files)
            Flags.threads_list.append(t)
            t.start()  # 启动线程,即让线程开始执行
        except:
            signal.show_traceback_log(traceback.format_exc())
            signal.show_log_text(traceback.format_exc())

    # 设置-字幕 为所有视频中的无字幕视频添加字幕
    def pushButton_add_sub_for_all_video_clicked(self):
        self.pushButton_show_log_clicked()  # 点按钮后跳转到日志页面
        try:
            t = threading.Thread(target=add_sub_for_all_video)
            Flags.threads_list.append(t)
            t.start()  # 启动线程,即让线程开始执行
        except:
            signal.show_traceback_log(traceback.format_exc())
            signal.show_log_text(traceback.format_exc())

    # region 设置-下载
    # 为所有视频中的创建/删除剧照附加内容
    def pushButton_add_all_extras_clicked(self):
        self.pushButton_show_log_clicked()  # 点按钮后跳转到日志页面
        try:
            t = threading.Thread(target=add_del_extras, args=('add',))
            t.start()  # 启动线程,即让线程开始执行
        except:
            signal.show_log_text(traceback.format_exc())

    def pushButton_del_all_extras_clicked(self):
        self.pushButton_show_log_clicked()  # 点按钮后跳转到日志页面
        try:
            t = threading.Thread(target=add_del_extras, args=('del',))
            t.start()  # 启动线程,即让线程开始执行
        except:
            signal.show_log_text(traceback.format_exc())

    # 为所有视频中的创建/删除剧照副本
    def pushButton_add_all_extrafanart_copy_clicked(self):
        self.pushButton_show_log_clicked()  # 点按钮后跳转到日志页面
        self.pushButton_save_config_clicked()
        try:
            t = threading.Thread(target=add_del_extrafanart_copy, args=('add',))
            t.start()  # 启动线程,即让线程开始执行
        except:
            signal.show_log_text(traceback.format_exc())

    def pushButton_del_all_extrafanart_copy_clicked(self):
        self.pushButton_show_log_clicked()  # 点按钮后跳转到日志页面
        self.pushButton_save_config_clicked()
        try:
            t = threading.Thread(target=add_del_extrafanart_copy, args=('del',))
            t.start()  # 启动线程,即让线程开始执行
        except:
            signal.show_log_text(traceback.format_exc())

    # 为所有视频中的创建/删除主题视频
    def pushButton_add_all_theme_videos_clicked(self):
        self.pushButton_show_log_clicked()  # 点按钮后跳转到日志页面
        try:
            t = threading.Thread(target=add_del_theme_videos, args=('add',))
            t.start()  # 启动线程,即让线程开始执行
        except:
            signal.show_log_text(traceback.format_exc())

    def pushButton_del_all_theme_videos_clicked(self):
        self.pushButton_show_log_clicked()  # 点按钮后跳转到日志页面
        try:
            t = threading.Thread(target=add_del_theme_videos, args=('del',))
            t.start()  # 启动线程,即让线程开始执行
        except:
            signal.show_log_text(traceback.format_exc())

    # endregion

    # region 设置-演员
    # 设置-演员 补全演员信息
    def pushButton_add_actor_info_clicked(self):
        self.pushButton_save_config_clicked()
        self.pushButton_show_log_clicked()  # 点按钮后跳转到日志页面
        try:
            t = threading.Thread(target=update_emby_actor_info)
            Flags.threads_list.append(t)
            t.start()  # 启动线程,即让线程开始执行
        except:
            signal.show_log_text(traceback.format_exc())

    # 设置-演员 补全演员头像按钮
    def pushButton_add_actor_pic_clicked(self):
        self.pushButton_save_config_clicked()
        self.pushButton_show_log_clicked()  # 点按钮后跳转到日志页面
        try:
            t = threading.Thread(target=update_emby_actor_photo)
            Flags.threads_list.append(t)
            t.start()  # 启动线程,即让线程开始执行
        except:
            signal.show_log_text(traceback.format_exc())

    # 设置-演员 补全演员头像按钮 kodi
    def pushButton_add_actor_pic_kodi_clicked(self):
        self.pushButton_save_config_clicked()
        self.pushButton_show_log_clicked()  # 点按钮后跳转到日志页面
        try:
            t = threading.Thread(target=creat_kodi_actors, args=(True,))
            Flags.threads_list.append(t)
            t.start()  # 启动线程,即让线程开始执行
        except:
            signal.show_log_text(traceback.format_exc())

    # 设置-演员 清除演员头像按钮 kodi
    def pushButton_del_actor_folder_clicked(self):
        self.pushButton_show_log_clicked()  # 点按钮后跳转到日志页面
        try:
            t = threading.Thread(target=creat_kodi_actors, args=(False,))
            Flags.threads_list.append(t)
            t.start()  # 启动线程,即让线程开始执行
        except:
            signal.show_log_text(traceback.format_exc())

    # 设置-演员 查看演员列表按钮
    def pushButton_show_pic_actor_clicked(self):
        self.pushButton_show_log_clicked()  # 点按钮后跳转到日志页面
        try:
            t = threading.Thread(target=show_emby_actor_list, args=(self.Ui.comboBox_pic_actor.currentIndex(),))
            Flags.threads_list.append(t)
            t.start()  # 启动线程,即让线程开始执行
        except:
            signal.show_log_text(traceback.format_exc())

    # endregion

    # 设置-线程数量
    def lcdNumber_thread_change(self):
        thread_number = self.Ui.horizontalSlider_thread.value()
        self.Ui.lcdNumber_thread.display(thread_number)

    # 设置-javdb延时
    def lcdNumber_javdb_time_change(self):
        javdb_time = self.Ui.horizontalSlider_javdb_time.value()
        self.Ui.lcdNumber_javdb_time.display(javdb_time)

    # 设置-其他网站延时
    def lcdNumber_thread_time_change(self):
        thread_time = self.Ui.horizontalSlider_thread_time.value()
        self.Ui.lcdNumber_thread_time.display(thread_time)

    # 设置-超时时间
    def lcdNumber_timeout_change(self):
        timeout = self.Ui.horizontalSlider_timeout.value()
        self.Ui.lcdNumber_timeout.display(timeout)

    # 设置-重试次数
    def lcdNumber_retry_change(self):
        retry = self.Ui.horizontalSlider_retry.value()
        self.Ui.lcdNumber_retry.display(retry)

    # 设置-水印大小
    def lcdNumber_mark_size_change(self):
        mark_size = self.Ui.horizontalSlider_mark_size.value()
        self.Ui.lcdNumber_mark_size.display(mark_size)

    # 设置-网络-网址设置-下拉框切换
    def switch_custom_website_change(self, new_website_name):
        self.Ui.lineEdit_custom_website.setText(getattr(config, f"{new_website_name}_website", ''))

    # 切换配置
    def config_file_change(self, new_config_file):
        if new_config_file != config.file:
            new_config_path = os.path.join(config.folder, new_config_file)
            signal.show_log_text(
                '\n================================================================================\nSwitch configuration:%s' % new_config_path)
            with open(config.get_mark_file_path(), 'w', encoding='UTF-8') as f:
                f.write(new_config_path)
            temp_dark = self.dark_mode
            temp_window_radius = self.window_radius
            self.load_config()
            if temp_dark != self.dark_mode and temp_window_radius == self.window_radius:
                self.show_flag = True
                self._windows_auto_adjust()
            signal.show_scrape_info('💡 Configuration has been switched!%s' % get_current_time())

    # 重置配置
    def pushButton_init_config_clicked(self):
        self.Ui.pushButton_init_config.setEnabled(False)
        config.init_config()
        temp_dark = self.dark_mode
        temp_window_radius = self.window_radius
        self.load_config()
        if temp_dark and temp_window_radius:
            self.show_flag = True
            self._windows_auto_adjust()
        self.Ui.pushButton_init_config.setEnabled(True)
        signal.show_scrape_info('💡 Configuration has been reset!%s' % get_current_time())

    # 设置-命名-分集-字母
    def checkBox_cd_part_a_clicked(self):
        if self.Ui.checkBox_cd_part_a.isChecked():
            self.Ui.checkBox_cd_part_c.setEnabled(True)
        else:
            self.Ui.checkBox_cd_part_c.setEnabled(False)

    # 设置-刮削目录-同意清理(我已知晓/我已同意)
    def checkBox_i_agree_clean_clicked(self):
        if self.Ui.checkBox_i_understand_clean.isChecked() and self.Ui.checkBox_i_agree_clean.isChecked():
            self.Ui.pushButton_check_and_clean_files.setEnabled(True)
            self.Ui.checkBox_auto_clean.setEnabled(True)
        else:
            self.Ui.pushButton_check_and_clean_files.setEnabled(False)
            self.Ui.checkBox_auto_clean.setEnabled(False)

    # 读取设置页的设置, 保存config.ini，然后重新加载
    def _check_mac_config_folder(self):
        if self.check_mac and not config.is_windows and '.app/Contents/Resources' in config.folder:
            self.check_mac = False
            box = QMessageBox(QMessageBox.Warning, 'Select configuration file directory',
                              f'It is detected that the current configuration file directory is:\n {config.folder}\n\nSince the MacOS platform will overwrite the configuration of this directory every time the APP version is updated, please choose another configuration directory!\nIn this way, when you update the APP next time, you can select the same configuration directory to read your previous configuration!!!')
            box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            box.button(QMessageBox.Yes).setText('Select directory')
            box.button(QMessageBox.No).setText('Cancel')
            box.setDefaultButton(QMessageBox.Yes)
            reply = box.exec()
            if reply == QMessageBox.Yes:
                self.pushButton_select_config_folder_clicked()

    # 设置-保存
    def pushButton_save_config_clicked(self):
        self.save_config()
        # self.load_config()
        signal.show_scrape_info('💡 Configuration saved!%s' % get_current_time())

    # 设置-另存为
    def pushButton_save_new_config_clicked(self):
        new_config_name, ok = QInputDialog.getText(self, 'Save as new configuration', 'Please enter the file name of the new configuration')
        if ok and new_config_name:
            new_config_name = new_config_name.replace('/', '').replace('\\', '')
            new_config_name = re.sub(r'[\\:*?"<>|\r\n]+', '', new_config_name)
            if os.path.splitext(new_config_name)[1] != '.ini':
                new_config_name += '.ini'
            if new_config_name != config.file:
                config.file = new_config_name
                self.pushButton_save_config_clicked()

    def save_config(self):
        ...

    # endregion

    # region 检测网络
    def network_check(self):
        start_time = time.time()
        try:
            # 显示代理信息
            signal.show_net_info('\n⛑ Start checking the network....')
            show_netstatus()
            # 检测网络连通性
            signal.show_net_info(' Start checking network connectivity...')

            net_info = {'github': ['https://raw.githubusercontent.com', ''],
                        'airav_cc': ['https://airav.io', ''],
                        'iqqtv': ['https://iqq5.xyz', ''],
                        'avsex': ['https://paycalling.com', ''],
                        'freejavbt': ['https://freejavbt.com', ''],
                        'javbus': ['https://www.javbus.com', ''],
                        'javdb': ['https://javdb.com', ''],
                        'jav321': ['https://www.jav321.com', ''],
                        'javlibrary': ['https://www.javlibrary.com', ''],
                        'dmm': ['https://www.dmm.co.jp', ''],
                        'mgstage': ['https://www.mgstage.com', ''],
                        'getchu': ['http://www.getchu.com', ''],
                        'theporndb': ['https://api.theporndb.net', ''],
                        'avsox': [get_avsox_domain(), ''],
                        'xcity': ['https://xcity.jp', ''],
                        '7mmtv': ['https://7mmtv.sx', ''],
                        'mdtv': ['https://www.mdpjzip.xyz', ''],
                        'madouqu': ['https://madouqu.com', ''],
                        'cnmdb': ['https://cnmdb.net', ''],
                        'hscangku': ['https://hscangku.net', ''],
                        'cableav': ['https://cableav.tv', ''],
                        'lulubar': ['https://lulubar.co', ''],
                        'love6': ['https://love6.tv', ''],
                        'yesjav': ['http://www.yesjav.info', ''],
                        'fc2': ['https://adult.contents.fc2.com', ''],
                        'fc2club': ['https://fc2club.top', ''],
                        'fc2hub': ['https://fc2hub.com', ''],
                        'airav': ['https://www.airav.wiki', ''],
                        'av-wiki': ['https://av-wiki.net', ''],
                        'seesaawiki': ['https://seesaawiki.jp', ''],
                        'mywife': ['https://mywife.cc', ''], 
                        'giga': ['https://www.giga-web.jp', ''],
                        'kin8': ['https://www.kin8tengoku.com', ''],
                        'fantastica': ['http://fantastica-vr.com', ''], 
                        'faleno': ['https://faleno.jp', ''],
                        'dahlia': ['https://dahlia-av.jp', ''], 
                        'prestige': ['https://www.prestige-av.com', ''],
                        's1s1s1': ['https://s1s1s1.com', ''], 
                        'moodyz': ['https://moodyz.com', ''],
                        'madonna': ['https://www.madonna-av.com', ''],
                        'wanz-factory': ['https://www.wanz-factory.com', ''],
                        'ideapocket': ['https://ideapocket.com', ''], 
                        'kirakira': ['https://kirakira-av.com', ''],
                        'ebody': ['https://www.av-e-body.com', ''], 
                        'bi-av': ['https://bi-av.com', ''],
                        'premium': ['https://premium-beauty.com', ''], 
                        'miman': ['https://miman.jp', ''],
                        'tameikegoro': ['https://tameikegoro.jp', ''], 
                        'fitch': ['https://fitch-av.com', ''],
                        'kawaiikawaii': ['https://kawaiikawaii.jp', ''], 
                        'befreebe': ['https://befreebe.com', ''],
                        'muku': ['https://muku.tv', ''], 
                        'attackers': ['https://attackers.net', ''],
                        'mko-labo': ['https://mko-labo.net', ''], 
                        'dasdas': ['https://dasdas.jp', ''],
                        'mvg': ['https://mvg.jp', ''], 
                        'opera': ['https://av-opera.jp', ''],
                        'oppai': ['https://oppai-av.com', ''], 
                        'v-av': ['https://v-av.com', ''],
                        'to-satsu': ['https://to-satsu.com', ''], 
                        'bibian': ['https://bibian-av.com', ''],
                        'honnaka': ['https://honnaka.jp', ''], 
                        'rookie': ['https://rookie-av.jp', ''],
                        'nanpa': ['https://nanpa-japan.jp', ''], 
                        'hajimekikaku': ['https://hajimekikaku.com', ''],
                        'hhh-av': ['https://hhh-av.com', '']}
            
            for website in config.SUPPORTED_WEBSITES:
                if hasattr(config, f"{website}_website"):
                    signal.show_net_info(f"   ⚠️{website} Use a custom URL:{getattr(config, f'{website}_website')}")
                    net_info[website][0] = getattr(config, f"{website}_website")

            net_info['javdb'][0] += '/v/D16Q5?locale=zh'
            net_info['seesaawiki'][0] += '/av_neme/d/%C9%F1%A5%EF%A5%A4%A5%D5'
            net_info['airav_cc'][0] += '/playon.aspx?hid=44733'
            net_info['javlibrary'][0] += '/cn/?v=javme2j2tu'
            net_info['kin8'][0] += '/moviepages/3681/index.html'

            for name, each in net_info.items():
                host_address = each[0].replace('https://', '').replace('http://', '').split('/')[0]
                if name == 'javdb':
                    res_javdb = self._check_javdb_cookie()
                    each[1] = res_javdb.replace('✅ Connection normal', f'✅ Connection normal{ping_host(host_address)}')
                elif name == 'javbus':
                    res_javbus = self._check_javbus_cookie()
                    each[1] = res_javbus.replace('✅ Connection normal', f'✅ Connection normal{ping_host(host_address)}')
                elif name == 'theporndb':
                    res_theporndb = check_theporndb_api_token()
                    each[1] = res_theporndb.replace('✅ Connection normal', f'✅ Connection normal{ping_host(host_address)}')
                elif name == 'javlibrary':
                    proxies = True
                    if hasattr(config, f"javlibrary_website"):
                        proxies = False
                    result, html_info = scraper_html(each[0], proxies=proxies)
                    if not result:
                        each[1] = '❌ Connection failed. Please check network or proxy settings! ' + html_info
                    elif 'Cloudflare' in html_info:
                        each[1] = '❌ Connection failed (blocked by Cloudflare 5-second shield!)'
                    else:
                        each[1] = f'✅ Connection normal{ping_host(host_address)}'
                elif name in ['avsex', 'freejavbt', 'airav_cc', 'airav', 'madouqu', '7mmtv']:
                    result, html_info = scraper_html(each[0])
                    if not result:
                        each[1] = '❌ Connection failed. Please check network or proxy settings! ' + html_info
                    elif 'Cloudflare' in html_info:
                        each[1] = '❌ Connection failed (blocked by Cloudflare 5-second shield!)'
                    else:
                        each[1] = f'✅ Connection normal{ping_host(host_address)}'
                else:
                    try:
                        result, html_content = get_html(each[0])
                        if not result:
                            each[1] = '❌ Connection failed. Please check network or proxy settings! ' + str(html_content)
                        else:
                            if name == 'dmm':
                                if re.findall('This page is not available in your region', html_content):
                                    each[1] = '❌ Connection failed due to geographical restrictions, please use the Japanese node to access!'
                                else:
                                    each[1] = f'✅ Connection normal{ping_host(host_address)}'
                            elif name == 'mgstage':
                                if not html_content.strip():
                                    each[1] = '❌ Connection failed due to geographical restrictions, please use the Japanese node to access!'
                                else:
                                    each[1] = f'✅ Connection normal{ping_host(host_address)}'
                            else:
                                each[1] = f'✅ Connection normal{ping_host(host_address)}'
                    except Exception as e:
                        each[1] = 'An exception occurred while testing the connection! information:' + str(e)
                        signal.show_traceback_log(traceback.format_exc())
                        signal.show_net_info(traceback.format_exc())
                signal.show_net_info('   ' + name.ljust(12) + each[1])
            signal.show_net_info(f"\n🎉 Network detection completed! time {get_used_time(start_time)} Second!")
            signal.show_net_info("================================================================================\n")
        except:
            if signal.stop:
                signal.show_net_info('\n⛔️ A scraping task is currently being stopped. Please wait until the scraping stops before testing again!')
                signal.show_net_info(
                    "================================================================================\n")
        self.Ui.pushButton_check_net.setEnabled(True)
        self.Ui.pushButton_check_net.setText('Start Test')
        self.Ui.pushButton_check_net.setStyleSheet(
            'QPushButton#pushButton_check_net{background-color:#4C6EFF}QPushButton:hover#pushButton_check_net{background-color: rgba(76,110,255,240)}QPushButton:pressed#pushButton_check_net{#4C6EE0}')

    # 网络检查
    def pushButton_check_net_clicked(self):
        if self.Ui.pushButton_check_net.text() == 'Start Test':
            self.Ui.pushButton_check_net.setText('Stop Test')
            self.Ui.pushButton_check_net.setStyleSheet(
                'QPushButton#pushButton_check_net{color: white;background-color: rgba(230, 36, 0, 250);}QPushButton:hover#pushButton_check_net{color: white;background-color: rgba(247, 36, 0, 250);}QPushButton:pressed#pushButton_check_net{color: white;background-color: rgba(180, 0, 0, 250);}')
            try:
                self.t_net = threading.Thread(target=self.network_check)
                self.t_net.start()  # 启动线程,即让线程开始执行
            except:
                signal.show_traceback_log(traceback.format_exc())
                signal.show_net_info(traceback.format_exc())
        elif self.Ui.pushButton_check_net.text() == 'Stop Test':
            self.Ui.pushButton_check_net.setText(' Stop Test ')
            self.Ui.pushButton_check_net.setText(' Stop Test ')
            t = threading.Thread(target=kill_a_thread, args=(self.t_net,))
            t.start()
            signal.show_net_info('\n⛔️ Network testing has been stopped manually!')
            signal.show_net_info("================================================================================\n")
            self.Ui.pushButton_check_net.setStyleSheet(
                'QPushButton#pushButton_check_net{color: white;background-color:#4C6EFF;}QPushButton:hover#pushButton_check_net{color: white;background-color: rgba(76,110,255,240)}QPushButton:pressed#pushButton_check_net{color: white;background-color:#4C6EE0}')
            self.Ui.pushButton_check_net.setText('Start Test')
        else:
            try:
                _async_raise(self.t_net.ident, SystemExit)
            except Exception as e:
                signal.show_traceback_log(str(e))
                signal.show_traceback_log(traceback.format_exc())

    # 检测网络界面日志显示
    def show_net_info(self, text):
        try:
            self.net_logs_show.emit(add_html(text))
        except:
            signal.show_traceback_log(traceback.format_exc())
            self.Ui.textBrowser_net_main.append(traceback.format_exc())

    # 检查javdb cookie
    def pushButton_check_javdb_cookie_clicked(self):
        input_cookie = self.Ui.plainTextEdit_cookie_javdb.toPlainText()
        if not input_cookie:
            self.Ui.label_javdb_cookie_result.setText('❌ JavDB cookie missing, this will affect FC2 scraping!')
            self.show_log_text(' ❌ JavDB cookie missing, this will affect FC2 scraping! It can be added under [Settings] -> [Network]!')
            return
        self.Ui.label_javdb_cookie_result.setText('⏳ Checking...')
        try:
            t = threading.Thread(target=self._check_javdb_cookie)
            t.start()  # 启动线程,即让线程开始执行
        except:
            signal.show_traceback_log(traceback.format_exc())
            signal.show_log_text(traceback.format_exc())

    def _check_javdb_cookie(self):
        tips = '❌ JavDB cookie missing, this will affect FC2 scraping!'
        input_cookie = self.Ui.plainTextEdit_cookie_javdb.toPlainText()
        if not input_cookie:
            self.Ui.label_javdb_cookie_result.setText(tips)
            return tips
        # self.Ui.pushButton_check_javdb_cookie.setEnabled(False)
        tips = '✅ Connection OK!'
        header = {'cookie': input_cookie}
        cookies = config.javdb
        javdb_url = getattr(config, 'javdb_website', 'https://javdb.com') + '/v/D16Q5?locale=zh'
        try:
            result, response = scraper_html(javdb_url, headers=header)
            if not result:
                if 'Cookie' in response:
                    if cookies != input_cookie:
                        tips = '❌ JavDB cookie expired!'
                    else:
                        tips = '❌ JavDB cookie expired! Cleared! (Cannot be accessed without removal)'
                        self.set_javdb_cookie.emit('')
                        self.pushButton_save_config_clicked()
                else:
                    tips = f'❌ Connection failed! Please check your network or proxy settings! {response}'
            else:
                if "The owner of this website has banned your access based on your browser's behaving" in response:
                    ip_adress = re.findall(r'(\d+\.\d+\.\d+\.\d+)', response)
                    ip_adress = ip_adress[0] + ' ' if ip_adress else ''
                    tips = f'❌ Your IP {ip_adress} has been banned by JavDB!'
                elif 'Due to copyright restrictions' in response or 'Access denied' in response:
                    tips = '❌ The current IP is blocked! Please use non-Japanese nodes!'
                elif 'ray-id' in response:
                    tips = '❌ Access blocked by CloudFlare!'
                elif '/logout' in response:  # 已登录，有登出按钮
                    vip_info = 'VIP not activated'
                    tips = f'✅ Connection OK! ({vip_info}）'
                    if input_cookie:
                        if 'icon-diamond' in response or '/v/D16Q5' in response:  # 有钻石图标或者跳到详情页表示已开通
                            vip_info = 'VIP already activated'
                        if cookies != input_cookie:  # 保存cookie
                            tips = f'✅ Connection OK! ({vip_info}）Cookie Saved!'
                            self.pushButton_save_config_clicked()
                        else:
                            tips = f'✅ Connection OK! ({vip_info}）'

                else:
                    if cookies != input_cookie:
                        tips = '❌ Cookie invalid! Please fill it in again!'
                    else:
                        tips = '❌ Cookie invalid! Cleared!'
                        self.set_javdb_cookie.emit('')
                        self.pushButton_save_config_clicked()
        except Exception as e:
            tips = f'❌ Connection failed! Please check your network or proxy settings! {e}'
            signal.show_traceback_log(tips)
        if input_cookie:
            self.Ui.label_javdb_cookie_result.setText(tips)
            # self.Ui.pushButton_check_javdb_cookie.setEnabled(True)
        self.show_log_text(tips.replace('❌', ' ❌ JavDB').replace('✅', ' ✅ JavDB'))
        return tips

    # javbus cookie
    def pushButton_check_javbus_cookie_clicked(self):
        try:
            t = threading.Thread(target=self._check_javbus_cookie)
            t.start()  # 启动线程,即让线程开始执行
        except:
            signal.show_traceback_log(traceback.format_exc())
            self.show_log_text(traceback.format_exc())

    def _check_javbus_cookie(self):
        self.set_javbus_status.emit('⏳ Checking...')

        # self.Ui.pushButton_check_javbus_cookie.setEnabled(False)
        tips = '✅ The connection is OK!'
        input_cookie = self.Ui.plainTextEdit_cookie_javbus.toPlainText()
        new_cookie = {'cookie': input_cookie}
        cookies = config.javbus
        headers_o = config.headers
        headers = {
            'Accept-Language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7,ja;q=0.6',
        }
        headers.update(headers_o)
        javbus_url = getattr(config, 'javbus_website', 'https://javbus.com') + '/FSDSS-660'

        try:
            result, response = get_html(javbus_url, headers=headers, cookies=new_cookie)

            if not result:
                tips = f'❌ Connection failed! Please check your network or proxy settings! {response}'
            elif 'lostpasswd' in response:
                if input_cookie:
                    tips = '❌ Cookie is invalid!'
                else:
                    tips = '❌ The current node requires cookies to scrape! Please fill in the cookie or change the node!'
            elif cookies != input_cookie:
                self.pushButton_save_config_clicked()
                tips = '✅ The connection is OK! Cookie saved!  '

        except Exception as e:
            tips = f'❌ Connection failed! Please check your network or proxy settings! {e}'

        self.show_log_text(tips.replace('❌', ' ❌ JavBus').replace('✅', ' ✅ JavBus'))
        self.set_javbus_status.emit(tips)
        # self.Ui.pushButton_check_javbus_cookie.setEnabled(True)
        return tips

    # endregion

    # region 其它
    # 点选择目录弹窗
    def _get_select_folder_path(self):
        media_path = self.Ui.lineEdit_movie_path.text()  # 获取待刮削目录作为打开目录
        if not media_path:
            media_path = get_main_path()
        media_folder_path = QFileDialog.getExistingDirectory(None, "Select directory", media_path, options=self.options)
        return convert_path(media_folder_path)

    # 改回接受焦点状态
    def recover_windowflags(self):
        return
        if not config.is_windows and not self.window().isActiveWindow():  # 不在前台，有点击事件，即切换回前台
            if (self.windowFlags() | Qt.WindowDoesNotAcceptFocus) == self.windowFlags():
                self.setWindowFlags(self.windowFlags() & ~Qt.WindowDoesNotAcceptFocus)
                self.show()

    # 申明
    def show_statement(self):
        if not self.statement:
            return
        msg = '''Statement
————————————————————————————————————————————————————————————————
When you view and download the source code or binary program of this project, you accept the following terms:

    · This project and project results are only used for technical, academic exchange and Python3 performance testing
    · Users must ensure that the method of obtaining the video is legal in the user's local area
    · The copyright of data such as metadata and cover images obtained during and after operation belongs to the copyright holder.
    · The contributors to this project wrote this project to learn Python3 and improve their programming level
    · This project does not provide any clues for video downloads
    · Do not provide data obtained during runtime and after runtime to third parties that may have illegal purposes, such as for illegal transactions, infringement of the rights of minors, etc.
    · Users can only use this tool in their own private computers or test environments, and are prohibited from using the obtained data for commercial purposes or other purposes, such as sales, dissemination, etc.
    · Before using this project and project results, users are requested to understand and abide by local laws and regulations. If there are any violations of local laws and regulations during the use of this project and project results, please do not use the project and project results.
    · The legal consequences and consequences of use shall be borne by the user
    · GPL LICENSE
    · If the user does not agree with any of the above terms, please do not use this project and project results.
        '''
        box = QMessageBox(QMessageBox.Warning, 'Statement', msg)
        box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        box.button(QMessageBox.Yes).setText('Agree')
        box.button(QMessageBox.No).setText('Disagree')
        box.setDefaultButton(QMessageBox.No)
        reply = box.exec()
        if reply == QMessageBox.No:
            os._exit(0)
        else:
            self.statement -= 1
            self.save_config()

    def change_buttons_status(self):
        Flags.stop_other = True
        self.Ui.pushButton_start_cap.setText('■ Stop')
        self.Ui.pushButton_start_cap2.setText('■ Stop')
        self.Ui.pushButton_select_media_folder.setVisible(False)
        self.Ui.pushButton_start_single_file.setEnabled(False)
        self.Ui.pushButton_start_single_file.setText('Scraping in progress...')
        self.Ui.pushButton_add_sub_for_all_video.setEnabled(False)
        self.Ui.pushButton_add_sub_for_all_video.setText('Scraping in progress...')
        self.Ui.pushButton_show_pic_actor.setEnabled(False)
        self.Ui.pushButton_show_pic_actor.setText('Scraping...')
        self.Ui.pushButton_add_actor_info.setEnabled(False)
        self.Ui.pushButton_add_actor_info.setText('Scraping in progress...')
        self.Ui.pushButton_add_actor_pic.setEnabled(False)
        self.Ui.pushButton_add_actor_pic.setText('Scraping in progress...')
        self.Ui.pushButton_add_actor_pic_kodi.setEnabled(False)
        self.Ui.pushButton_add_actor_pic_kodi.setText('Scraping in progress...')
        self.Ui.pushButton_del_actor_folder.setEnabled(False)
        self.Ui.pushButton_del_actor_folder.setText('Scraping in progress...')
        # self.Ui.pushButton_check_and_clean_files.setEnabled(False)
        self.Ui.pushButton_check_and_clean_files.setText('Scraping in progress...')
        self.Ui.pushButton_move_mp4.setEnabled(False)
        self.Ui.pushButton_move_mp4.setText('Scraping in progress...')
        self.Ui.pushButton_find_missing_number.setEnabled(False)
        self.Ui.pushButton_find_missing_number.setText('Scraping in progress...')
        self.Ui.pushButton_start_cap.setStyleSheet(
            'QPushButton#pushButton_start_cap{color: white;background-color: rgba(230, 66, 30, 255);}QPushButton:hover#pushButton_start_cap{color: white;background-color: rgba(247, 36, 0, 250);}QPushButton:pressed#pushButton_start_cap{color: white;background-color: rgba(180, 0, 0, 250);}')
        self.Ui.pushButton_start_cap2.setStyleSheet(
            'QPushButton#pushButton_start_cap2{color: white;background-color: rgba(230, 66, 30, 255);}QPushButton:hover#pushButton_start_cap2{color: white;background-color: rgba(247, 36, 0, 250);}QPushButton:pressed#pushButton_start_cap2{color: white;background-color: rgba(180, 0, 0, 250);}')

    def reset_buttons_status(self):
        self.Ui.pushButton_start_cap.setEnabled(True)
        self.Ui.pushButton_start_cap2.setEnabled(True)
        self.pushButton_start_cap.emit('Start')
        self.pushButton_start_cap2.emit('Start')
        self.Ui.pushButton_select_media_folder.setVisible(True)
        self.Ui.pushButton_start_single_file.setEnabled(True)
        self.pushButton_start_single_file.emit('Scrape')
        self.Ui.pushButton_add_sub_for_all_video.setEnabled(True)
        self.pushButton_add_sub_for_all_video.emit('Click to check the subtitle status of all videos and add subtitles to videos without subtitles')

        self.Ui.pushButton_show_pic_actor.setEnabled(True)
        self.pushButton_show_pic_actor.emit('Check')
        self.Ui.pushButton_add_actor_info.setEnabled(True)
        self.pushButton_add_actor_info.emit('Start completing')
        self.Ui.pushButton_add_actor_pic.setEnabled(True)
        self.pushButton_add_actor_pic.emit('Start completing')
        self.Ui.pushButton_add_actor_pic_kodi.setEnabled(True)
        self.pushButton_add_actor_pic_kodi.emit('Start completing')
        self.Ui.pushButton_del_actor_folder.setEnabled(True)
        self.pushButton_del_actor_folder.emit('Clear all .actors folders')
        self.Ui.pushButton_check_and_clean_files.setEnabled(True)
        self.pushButton_check_and_clean_files.emit('Click to check the directory to be scraped and clean the files')
        self.Ui.pushButton_move_mp4.setEnabled(True)
        self.pushButton_move_mp4.emit('Start moving')
        self.Ui.pushButton_find_missing_number.setEnabled(True)
        self.pushButton_find_missing_number.emit('Check for missing numbers')

        self.Ui.pushButton_start_cap.setStyleSheet(
            'QPushButton#pushButton_start_cap{color: white;background-color:#4C6EFF;}QPushButton:hover#pushButton_start_cap{color: white;background-color: rgba(76,110,255,240)}QPushButton:pressed#pushButton_start_cap{color: white;background-color:#4C6EE0}')
        self.Ui.pushButton_start_cap2.setStyleSheet(
            'QPushButton#pushButton_start_cap2{color: white;background-color:#4C6EFF;}QPushButton:hover#pushButton_start_cap2{color: white;background-color: rgba(76,110,255,240)}QPushButton:pressed#pushButton_start_cap2{color: white;background-color:#4C6EE0}')
        Flags.file_mode = FileMode.Default
        Flags.threads_list = []
        if len(Flags.failed_list):
            self.Ui.pushButton_scraper_failed_list.setText(f'Re-scrape the current one with one click {len(Flags.failed_list)} failed files')
        else:
            self.Ui.pushButton_scraper_failed_list.setText('When there are failed tasks, click to scrape the current failed list with one click.')

    # endregion

    # region 自动刮削
    def auto_scrape(self):
        if 'timed_scrape' in config.switch_on and self.Ui.pushButton_start_cap.text() == 'Start':
            time.sleep(0.1)
            timed_interval = config.timed_interval
            self.atuo_scrape_count += 1
            signal.show_log_text(
                f'\n\n 🍔 "Cycle Scrape" is enabled! Interval time:{timed_interval}! About to start the chapter {self.atuo_scrape_count} Second cycle scraping!')
            if Flags.scrape_start_time:
                signal.show_log_text(
                    ' ⏰ Last scraping time:' + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(Flags.scrape_start_time)))
            start_new_scrape(FileMode.Default)

    def auto_start(self):
        if 'auto_start' in config.switch_on:
            signal.show_log_text('\n\n 🍔 "Automatic scraping after software startup" has been enabled! Automatic scraping is about to begin!')
            self.pushButton_start_scrape_clicked()
    # endregion


# region 外部方法定义
MyMAinWindow.load_config = load_config
MyMAinWindow.save_config = save_config
MyMAinWindow.Init_QSystemTrayIcon = Init_QSystemTrayIcon
MyMAinWindow.Init_Ui = Init_Ui
MyMAinWindow.Init_Singal = Init_Singal
MyMAinWindow.init_QTreeWidget = init_QTreeWidget
MyMAinWindow.set_style = set_style
MyMAinWindow.set_dark_style = set_dark_style
# endregion
