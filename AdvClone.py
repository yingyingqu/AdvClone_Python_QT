# -*- coding:utf-8 -*-
import os, sys, re
import json
import subprocess
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel,
    QPushButton, QTreeWidget, QTreeWidgetItem, QMessageBox,QLineEdit,
    QHBoxLayout, QStackedWidget, QFrame, QSplitter, QProgressBar, QTextEdit,QButtonGroup
)
from PyQt5.QtCore import Qt, QSettings, QThread, pyqtSignal, QProcess
from PyQt5.QtGui import  QFont, QIntValidator
import ctypes

import time, logging

from get_partitions_basic import basic_disk_patitions

# 日志名称
if not os.path.exists('log'):
    os.makedirs('log')

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_file = f"log\\log_AdvClone_QT_{timestamp}.txt"

# 自定义 Logger
logger = logging.getLogger("MyLogger")
logger.setLevel(logging.DEBUG)  # 捕获所有级别

# 1.文件输出（保存所有日志）
file_handler = logging.FileHandler(log_file, encoding="utf-8")
file_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

# 2️.控制台输出（只输出部分信息）
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)  # 只显示 INFO 及以上
console_formatter = logging.Formatter("[%(levelname)s] %(message)s")
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)


# 3️.替换 print，使 print 也输出到 logger（可选）
class PrintLogger:
    def write(self, message):
        if message.strip():  # 去掉空行
            logger.info(message.strip())
    def flush(self):
        pass


# ---------------- ModeSelectPage ----------------
class ModeSelectPage(QWidget):
    def __init__(self, auto_callback, advanced_callback):
        super().__init__()
        self.auto_callback = auto_callback
        self.advanced_callback = advanced_callback

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(25)

        # 标题
        title = QLabel("请选择备份模式")
        title.setFont(QFont("Microsoft YaHei", 20, QFont.Bold))
        title.setStyleSheet("color:#1a73e8;")
        layout.addWidget(title)

        # 帮助提示
        help_box = QFrame()
        help_box.setStyleSheet("""
            QFrame { background-color: #f5f7fa; border: 1px solid #d0d7de; border-radius: 10px; }
        """)
        help_layout = QVBoxLayout(help_box)
        help_layout.setContentsMargins(15, 15, 15, 15)
        help_layout.setSpacing(8)

        help_title = QLabel("💡 模式说明")
        help_title.setFont(QFont("Microsoft YaHei", 12, QFont.Bold))
        help_title.setStyleSheet("color:#333;")
        help_text = QLabel(
            "✅ 全自动备份：系统自动检测分区与保存位置，一键执行，无需手动干预。\n"
            "⚙️ 高级备份模式：可自行选择要备份的分区、目标存储及压缩设置。"
        )
        help_text.setFont(QFont("Microsoft YaHei", 10))
        help_text.setStyleSheet("color:#555;")
        help_text.setWordWrap(True)
        help_layout.addWidget(help_title)
        help_layout.addWidget(help_text)
        layout.addWidget(help_box)

        # 按钮
        btn_auto = QPushButton("✅ 全自动备份")
        btn_auto.setMinimumHeight(60)
        btn_auto.setFont(QFont("Microsoft YaHei", 12, QFont.Bold))
        btn_auto.setStyleSheet("""
            QPushButton { background-color:#34a853; color:white; border-radius:10px; }
            QPushButton:hover { background-color:#2c8d45; }
            QPushButton:pressed { background-color:#1e6631; }
        """)
        btn_auto.clicked.connect(self.auto_callback)

        btn_advanced = QPushButton("⚙️ 高级备份模式")
        btn_advanced.setMinimumHeight(60)
        btn_advanced.setFont(QFont("Microsoft YaHei", 12, QFont.Bold))
        btn_advanced.setStyleSheet("""
            QPushButton { background-color:#1a73e8; color:white; border-radius:10px; }
            QPushButton:hover { background-color:#1669c1; }
            QPushButton:pressed { background-color:#0d47a1; }
        """)
        btn_advanced.clicked.connect(self.advanced_callback)

        layout.addWidget(btn_auto)
        layout.addWidget(btn_advanced)
        layout.addStretch()


# ---------------- BackupWizard ----------------
class BackupWizard(QMainWindow):
    def __init__(self, all_disks):
        super().__init__()
        self.setWindowTitle("AdvClone 备份向导")
        self.resize(1000, 600)

        splitter = QSplitter()
        splitter.setHandleWidth(1)
        self.setCentralWidget(splitter)

        # 左侧步骤栏
        self.step_widget = QWidget()
        step_layout = QVBoxLayout(self.step_widget)
        step_layout.setContentsMargins(10, 20, 10, 20)
        step_layout.setSpacing(20)
        self.step_labels = []
        for s in ["选择模式", "备份分区", "确认选择", "执行准备"]:
            lbl = QLabel(s)
            lbl.setFont(QFont("Microsoft YaHei", 12, QFont.Bold))
            lbl.setStyleSheet("color:#777;")
            self.step_labels.append(lbl)
            step_layout.addWidget(lbl)
        step_layout.addStretch()
        splitter.addWidget(self.step_widget)

        # 右侧堆栈页面
        self.stack = QStackedWidget()
        splitter.addWidget(self.stack)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 5)

        # 参数
        self.all_disks = all_disks
        self.compress_rate = self.getConfigValue('COMPRESSRATE', 'rate')

        
        # --- 页面初始化 ---
        self.page0 = ModeSelectPage(self.go_to_auto, self.go_to_advanced)
        self.stack.addWidget(self.page0)
        self.stack.setCurrentWidget(self.page0)
        self.update_steps(0)
        self.update_step_visibility(mode_select=True)  # ✅ 只显示“选择模式”

        self.page1 = None
        self.page2 = None
        self.page3 = None


    # ---------------- 辅助函数 ----------------
    def update_steps(self, index):
        for i, lbl in enumerate(self.step_labels):
            lbl.setStyleSheet("color:#1a73e8;" if i == index else "color:#444;")

    def update_step_visibility(self, mode_select=False):
        """控制左侧步骤栏显示"""
        if mode_select:
            # 模式选择页：仅显示第一个步骤
            for i, lbl in enumerate(self.step_labels):
                lbl.setVisible(i == 0)
        else:
            # 高级模式：显示全部步骤
            for lbl in self.step_labels:
                lbl.setVisible(True)


    def getConfigValue(self, section, key, default_value=None):
        """通用的配置读取方法"""
        settings = QSettings('config.ini', QSettings.IniFormat)
        
        # 构建完整的键路径
        full_key = f'{section}/{key}'
        return settings.value(full_key, default_value)

    # ---------------- 页面切换 ----------------

    def go_to_auto(self):
        """自动模式：直接进入执行页"""
        self.step_widget.hide()  # ✅ 隐藏左侧步骤栏

        selected_backup, selected_storage, shrink_space_mb = self.auto_select_partitions()
        
        if not selected_backup or not selected_storage:
            # 自动选择失败，返回模式选择页
            #QMessageBox.information(self, "提示", "自动选择分区失败，请使用高级模式手动选择分区。")
            self.go_to_mode_select()
            return

        if not self.page3:
            self.page3 = ExecutionPage(self.go_to_mode_select)  # 修改为返回模式选择页
            self.stack.addWidget(self.page3)


        self.page3.load_data(selected_backup, selected_storage, shrink_space_mb, "selected_partitions.json")
        self.page3.set_auto_mode(True)
        self.stack.setCurrentWidget(self.page3)
        self.page3.start_exec()

    def go_to_advanced(self):
        """高级模式：进入分区选择页"""
        self.step_widget.show()
        self.update_step_visibility(mode_select=False)
        self.update_steps(1)

        if not self.page1:
            self.page1 = PartitionSelectorPage(self.all_disks, self.go_to_confirm, self.compress_rate, back_callback=self.go_to_mode_select)
            self.stack.addWidget(self.page1)
        if not self.page2:
            self.page2 = ConfirmSelectionPage(self.go_to_select, self.go_to_exec, self.all_disks, self.compress_rate)
            self.stack.addWidget(self.page2)
        if not self.page3:
            self.page3 = ExecutionPage(self.go_to_confirm_back)
            self.stack.addWidget(self.page3)

        self.stack.setCurrentWidget(self.page1)



    # ---------------- 页面回调 ----------------
    def go_to_mode_select(self):
        """返回模式选择页"""
        self.step_widget.show()
        self.stack.setCurrentWidget(self.page0)
        self.update_steps(0)
        self.update_step_visibility(mode_select=True)

    def go_to_confirm(self, selected_first_page):
        self.page2.load_data(selected_first_page)
        self.stack.setCurrentWidget(self.page2)
        self.update_steps(2)

    def go_to_exec(self, selected_first_page, selected_storage, shrink_space_mb):
        if not self.page3:
            self.page3 = ExecutionPage(self.go_to_confirm_back)
            self.stack.addWidget(self.page3)
        
        save_path = os.path.join(os.getcwd(), "selected_partitions.json")   
        # 标记模式，方便执行页识别
        mode_data = {
            "auto_mode": False,
            "backup": selected_first_page,
            "storage": selected_storage,
            "shrink_space_mb": shrink_space_mb
        }
        # 写入前先清空文件
        with open(save_path, "w", encoding="utf-8") as f:
            f.write("")  # 先清空文件内容
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(mode_data, f, ensure_ascii=False, indent=2)

        self.page3.load_data(selected_first_page, selected_storage, shrink_space_mb, "selected_partitions.json")
        self.stack.setCurrentWidget(self.page3)
        self.update_steps(3)

    def go_to_select(self):
        self.stack.setCurrentWidget(self.page1)
        self.update_steps(1)

    def go_to_confirm_back(self):
        self.stack.setCurrentWidget(self.page2)
        self.update_steps(2)

    # ---------------- 自动模式分区选择逻辑 ----------------
    def format_size_auto(self, size_bytes):
        if size_bytes <= 0:
            return ""
        units = [(1024**3, "GB"), (1024**2,"MB"),(1024,"KB"),(1,"B")]
        for threshold, unit in units:
            if size_bytes >= threshold:
                size = size_bytes / threshold
                return f"{size:.2f} {unit}"
        return f"{size_bytes} B"
    def auto_select_partitions(self):
        """返回 (selected_backup, selected_storage, shrink_space_mb)"""
        selected_backup = []
        selected_storage = {}
        total_used_bytes = 0
        advclone_found = False
        
        logger.debug("Find advclone and caculate total_used_bytes")
        for d in self.all_disks:
            disk = self.all_disks[d]
            for part in disk["Partitions"]:
                logger.debug(f"{part}\npart.get('label')={part.get('label')}")
                if (part.get('label') or "").lower() != "advclone":
                    selected_backup.append(part)
                    total_used_bytes += part.get("used_bytes", part.get("size_bytes", 0))
                    logger.debug(f"Not advclone: selected_backup={selected_backup}\ntotal_used_bytes={total_used_bytes}\n")
                else:
                    advclone_found = True
                    advclone_part = part
                    advclone_size_bytes = part.get("size_bytes", 0)
                    advclone_available_size_bytes = advclone_size_bytes - 730*1024*1024

        try:
            logger.debug(f"[Debug]计算所需空间")
            need_bytes = int(total_used_bytes / float(self.compress_rate))
            shrink_space_mb = int(need_bytes / 1024 / 1024)
        except Exception as e:
            logger.error(f"{e}")
        
        logger.debug(f"\ntotal_used_bytes={total_used_bytes} bytes({self.format_size_auto(total_used_bytes)})\ncompress_rate={self.compress_rate}\nneed_bytes={need_bytes} bytes({self.format_size_auto(need_bytes)})")

        if advclone_found:
            if advclone_available_size_bytes >= need_bytes:
                logger.debug("\n-->advclone already exist and size is ok.")
                logger.debug(f"advclone_available_size_bytes={advclone_available_size_bytes}bytes({self.format_size_auto(advclone_available_size_bytes)})")
                selected_storage = advclone_part
            else:
                mesg = f"""advclone 分区空间不足。
    advclone分区可用空间大小: {advclone_available_size_bytes} bytes({self.format_size_auto(advclone_available_size_bytes)})
    所需空间: {need_bytes} bytes({self.format_size_auto(need_bytes)})
    请退出本程序，在设备管理中删除后重新执行。"""
                #QMessageBox.warning(self,"提示",mesg)
                logger.debug(mesg)
                # 询问用户是否继续
                reply = QMessageBox.question(
                    self, 
                    "Warning", 
                    f"{mesg}\n\n点击 Yes 退出程序，点击 No 继续使用。",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )
                
                if reply == QMessageBox.Yes:
                    QApplication.quit()  # 只有用户确认时才退出
                else:
                    return [],[],0
        elif not advclone_found:
            logger.debug("advclone not exist.")
            # 自动选择一个可用分区作为 storage
            for d in self.all_disks:
                disk = self.all_disks[d]
                disk_Unallocated = disk.get('Size')-disk.get('AllocatedSize')
                if disk_Unallocated > need_bytes:
                    selected_storage = {'DiskNumber': int(d), 'Type':'Unallocated'}
                else:
                    for part in disk["Partitions"]:
                        logger.debug(f"{part}\npart.get('free_bytes')={part.get('free_bytes')}, need_bytes={need_bytes}")
                        if part.get('free_bytes') and part.get('free_bytes') >= need_bytes:
                            logger.debug(f"!!Find the selected_storage!!")
                            selected_storage = part
                            break
                if not selected_storage:
                    logger.error(f"selected_storage is empty!!")
                    break
        
        save_path = os.path.join(os.getcwd(), "selected_partitions.json")

        # 标记全自动模式，方便执行页识别
        mode_data = {
            "auto_mode": True,
            "backup": selected_backup,
            "storage": selected_storage,
            "shrink_space_mb": shrink_space_mb
        }
        # 写入前先清空文件
        with open(save_path, "w", encoding="utf-8") as f:
            f.write("")  # 先清空文件内容
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(mode_data, f, ensure_ascii=False, indent=2)

        logger.debug(f"\nAutoMode:\nselected_backup={selected_backup}\nselected_storage={selected_storage}\nshrink_space_mb={shrink_space_mb}")
        return selected_backup, selected_storage, shrink_space_mb






# ---------------- 修改 PartitionSelectorPage ----------------
class PartitionSelectorPage(QWidget):
    def __init__(self, all_disks, next_callback, compress_rate, back_callback=None):
        super().__init__()
        self.all_disks = all_disks
        self.next_callback = next_callback
        self.back_callback = back_callback
        self.compress_rate = compress_rate

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        card = QFrame()
        card.setFrameShape(QFrame.StyledPanel)
        card.setStyleSheet("QFrame { background:#ffffff; border-radius:12px; }")
        card_layout = QVBoxLayout(card)

        title = QLabel("请选择要备份的分区")
        title.setFont(QFont("Microsoft YaHei", 18, QFont.Bold))
        title.setStyleSheet("color:#1a73e8;")
        subtitle = QLabel("请勾选要备份的分区（advclone 分区不可选）")
        subtitle.setFont(QFont("Microsoft YaHei", 11))
        subtitle.setStyleSheet("color:#555;")
        card_layout.addWidget(title)
        card_layout.addWidget(subtitle)

        # 树控件逻辑
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Partition #","Label","FS","Capacity","Free Space","Info"])
        self.tree.setColumnWidth(0, 200)   # Partition#列：200像素
        self.tree.setAnimated(True)
        self.tree.setStyleSheet("QTreeWidget {background:#ffffff; border:none; font-size:12px;} QTreeWidget::item:hover {background:#eaf1fb;}")
        card_layout.addWidget(self.tree)


        # 遍历磁盘和分区
        self.partition_items = []

        for key in all_disks:
            disk=all_disks.get(key)
            disk_item = QTreeWidgetItem(self.tree)
            disk_item.setFlags(disk_item.flags() & ~Qt.ItemIsSelectable)
            self.tree.addTopLevelItem(disk_item)
            partitons_info = disk["Partitions"]
            # 按盘符或 OffsetBytes 排序
            partitons_info.sort(key=lambda p: (p.get('OffsetBytes', 0)))
            for part in partitons_info:
                #print("[Debug]", part)
                label = str(part.get("label","") or "")
                part_info = f"{part.get('Type','')} ({part.get('drive_letter','')}:)" if part.get('drive_letter') else part.get('Type','')
                #size = f"{part.get('size','')} {part.get('size_unit','')}"
                size = f"{self.format_size_auto(part.get('size_bytes', 0))}"
                free = f"{self.format_size_auto(part.get('free_bytes'))}" if part.get('free_bytes') else ""
                item = QTreeWidgetItem([part_info,label,part.get('FileSystem',''),size,free,str(part.get("info",""))])
                item.setData(0, Qt.UserRole, part)  # 绑定分区数据
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                if label.lower() == "advclone":
                    item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
                    item.setCheckState(0, Qt.Unchecked)
                else:
                    item.setCheckState(0, Qt.Unchecked)
                disk_item.addChild(item)
                self.partition_items.append(part)
        self.tree.expandAll()

        
        # 下方按钮布局
        btn_layout = QHBoxLayout()
        self.btn_back = QPushButton("上一步")
        self.btn_next = QPushButton("下一步")
        
        self.set_buttons_enabled(True)
        

        self.btn_back.clicked.connect(self.back_callback)
        self.btn_next.clicked.connect(self.go_next)
        btn_layout.addWidget(self.btn_back)        
        btn_layout.addWidget(self.btn_next)
        #btn_layout.addStretch()#把addStretch() 放在了按钮之后，这会把按钮推到左侧
        card_layout.addLayout(btn_layout)

        layout.addWidget(card)
        
    def set_buttons_enabled(self, enabled):
        """统一设置按钮状态，禁用时变为灰色"""
        self.btn_next.setEnabled(enabled)
        self.btn_back.setEnabled(enabled)
        
        if enabled:
            # 正常样式 - 启用状态
            normal_style = """
                QPushButton {
                    background-color: #1a73e8;
                    color: white;
                    border-radius: 8px;
                    padding: 6px 18px;
                    border: none;
                }
                QPushButton:hover {
                    background-color: #1669c1;
                }
                QPushButton:pressed {
                    background-color: #0d47a1;
                }
            """
            self.btn_next.setStyleSheet(normal_style)
            self.btn_back.setStyleSheet(normal_style)
            
            
        else:
            # 禁用样式 - 灰色
            disabled_style = """
                QPushButton {
                    background-color: #cccccc;
                    color: #666666;
                    border-radius: 8px;
                    padding: 6px 18px;
                    border: 1px solid #aaaaaa;
                }
            """
            self.btn_next.setStyleSheet(disabled_style)
            self.btn_back.setStyleSheet(disabled_style)
        
        # 强制UI更新
        QApplication.processEvents()
        
    def format_size_auto(self, size_bytes):
        if size_bytes <= 0:
            return ""
        units = [(1024**3, "GB"), (1024**2,"MB"),(1024,"KB"),(1,"B")]
        for threshold, unit in units:
            if size_bytes >= threshold:
                size = size_bytes / threshold
                return f"{size:.2f} {unit}"
        return f"{size_bytes} B"

    
    def go_next(self):
        selected = []
        for i in range(self.tree.topLevelItemCount()):
            disk_item = self.tree.topLevelItem(i)
            for j in range(disk_item.childCount()):
                item = disk_item.child(j)
                if item.checkState(0) == Qt.Checked:
                    part = item.data(0, Qt.UserRole)
                    if part:
                        selected.append(part)

        if not selected:
            QMessageBox.warning(self,"提示","请至少选择一个分区！")
            return

        try:
            # advclone 空间检查                   
            for d in self.all_disks:
                disk = self.all_disks.get(d)
                for part in disk["Partitions"]:
                    if (part.get("label") or "").lower() == "advclone":
                        total_used_bytes = sum(p.get("used_bytes",0) or p.get("size_bytes",0) for p in selected)
                        need_bytes = int(total_used_bytes / float(self.compress_rate))
                        advclone_size_bytes = part.get("size_bytes",0)
                        advclone_available_size_bytes = advclone_size_bytes - 730*1024*1024
                        if advclone_available_size_bytes < need_bytes:
                            drive = part.get("drive_letter","")
                            mesg = f"""advclone 分区 ({drive}) 空间不足。
    已选要备份的分区总大小: {total_used_bytes} bytes ({self.format_size_auto(total_used_bytes)})
    所需空间: {need_bytes} bytes({self.format_size_auto(need_bytes)})
    advclone分区可用空间: {advclone_available_size_bytes} bytes({self.format_size_auto(advclone_available_size_bytes)})"""
                            QMessageBox.warning(self,"提示",mesg)
                            return
            # 正常跳转第二页，并传递已选分区
            if hasattr(self, 'next_callback'):
                self.next_callback(selected)

        except Exception as e:
            logger.error(f"执行出错: {e}")
            QMessageBox.critical(self,"错误", f"出现异常: {e}")
            return




        
# ---------- 第2页 ----------
class ConfirmSelectionPage(QWidget):
    def __init__(self, back_callback, next_callback, all_disks, compress_rate=1.5):
        super().__init__()
        self.back_callback = back_callback
        self.next_callback = next_callback
        self.all_disks = all_disks
        self.compress_rate = compress_rate
        self.need_bytes = 0
        self.selected_first_page = []
        
        self.partition_button_group = QButtonGroup(self)
        self.partition_button_group.setExclusive(True)  # 设置互斥

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20,20,20,20)
        layout.setSpacing(15)

        card = QFrame()
        card.setFrameShape(QFrame.StyledPanel)
        card.setStyleSheet("QFrame{background:#ffffff;border-radius:12px;}")
        card_layout = QVBoxLayout(card)

        title = QLabel("确认选择的分区")
        title.setFont(QFont("Microsoft YaHei",18,QFont.Bold))
        title.setStyleSheet("color:#1a73e8;")
        card_layout.addWidget(title)

        self.info_label = QLabel()
        self.info_label.setFont(QFont("Microsoft YaHei",11))
        self.info_label.setStyleSheet("color:#555;")
        card_layout.addWidget(self.info_label)

        self.tree = QTreeWidget()
        #self.tree.setHeaderLabels(["Name","Label","FS","Size","Used","Free","Info"])
        self.tree.setHeaderLabels(["Name","Label","Size","Used","Free","Info"])
        self.tree.setColumnWidth(0, 200)   # Name列：200像素
        self.tree.setColumnWidth(0, 200)
        self.tree.setAnimated(True)
        self.tree.setStyleSheet("QTreeWidget {background:#ffffff;border:none;font-size:12px;} QTreeWidget::item:hover {background:#eaf1fb;}")
        card_layout.addWidget(self.tree)
        
        
        
        
        # 输入框：压缩分区大小
        size_layout = QHBoxLayout()
        size_layout.addWidget(QLabel("压缩分区大小 (MB):"))
        self.size_input = QLineEdit()
        self.size_input.setValidator(QIntValidator(1, 9999999, self))
        
        size_layout.addWidget(self.size_input)
        size_layout.addStretch()
        card_layout.addLayout(size_layout)

        btn_layout = QHBoxLayout()
        self.btn_back = QPushButton("上一步")
        self.btn_next = QPushButton("下一步")

        self.set_buttons_enabled(True)
        
        self.btn_back.clicked.connect(self.back_callback)
        self.btn_next.clicked.connect(self.go_next)
        btn_layout.addWidget(self.btn_back)
        btn_layout.addWidget(self.btn_next)
        card_layout.addLayout(btn_layout)

        layout.addWidget(card)
        
    def set_buttons_enabled(self, enabled):
        """统一设置按钮状态，禁用时变为灰色"""
        self.btn_next.setEnabled(enabled)
        self.btn_back.setEnabled(enabled)
        
        if enabled:
            # 正常样式 - 启用状态
            normal_style = """
                QPushButton {
                    background-color: #1a73e8;
                    color: white;
                    border-radius: 8px;
                    padding: 6px 18px;
                    border: none;
                }
                QPushButton:hover {
                    background-color: #1669c1;
                }
                QPushButton:pressed {
                    background-color: #0d47a1;
                }
            """
            self.btn_next.setStyleSheet(normal_style)
            self.btn_back.setStyleSheet(normal_style)
            
            
        else:
            # 禁用样式 - 灰色
            disabled_style = """
                QPushButton {
                    background-color: #cccccc;
                    color: #666666;
                    border-radius: 8px;
                    padding: 6px 18px;
                    border: 1px solid #aaaaaa;
                }
            """
            self.btn_next.setStyleSheet(disabled_style)
            self.btn_back.setStyleSheet(disabled_style)
        
        # 强制UI更新
        QApplication.processEvents()

    def format_size_auto(self, size_bytes):
        if size_bytes <= 0:
            return ""
        units = [(1024**3, "GB"), (1024**2,"MB"),(1024,"KB"),(1,"B")]
        for threshold, unit in units:
            if size_bytes >= threshold:
                size = size_bytes / threshold
                return f"{size:.2f} {unit}"
        return f"{size_bytes} B"

    def load_data(self, selected_first_page):
        logger.debug(f"======[Debug]page2: load_data======")
        self.selected_first_page = selected_first_page
        logger.debug(f"self.selected_first_page={self.selected_first_page}")
        total_used_bytes = sum(p.get("used_bytes",0) or p.get("size_bytes",0) for p in selected_first_page)
        need_bytes = int(total_used_bytes / float(self.compress_rate))
        self.need_bytes = need_bytes
        logger.debug(f"[Debug]total_used_bytes={total_used_bytes},need_bytes={need_bytes},self.compress_rate={self.compress_rate}")
        self.info_label.setText(f"已选择 {len(selected_first_page)} 个分区\n原始总大小: {self.format_size_auto(total_used_bytes)}\n预计需要空间: {self.format_size_auto(need_bytes)}\n(压缩率: {self.compress_rate})")
        input_default_bytes = self.need_bytes + 750*1024*1024
        input_default_mb = float(input_default_bytes/1024/1024)
        input_default_gb = float(input_default_bytes/1024/1024/1024)
        logger.debug(f"[Debug]input_default_bytes={input_default_bytes} bytes\ninput_default_mb={input_default_mb} MB\ninput_default_gb={input_default_gb} GB")
        self.size_input.setText(str(int(input_default_mb+1)))

        self.tree.clear()

        # 已选备份分区
        logger.debug(f"[Debug]加载已选备份分区")
        root1 = QTreeWidgetItem(["已选择备份分区"])
        root1.setFlags(root1.flags() & ~Qt.ItemIsSelectable)
        self.tree.addTopLevelItem(root1)
        for part in selected_first_page:
            label = str(part.get("label","") or "")
            info = f"{part.get('Type','')} ({part.get('drive_letter','')}:)" if part.get('drive_letter') else part.get('Type','')
            item = QTreeWidgetItem([info,label,
                                     f"{self.format_size_auto(part.get('size_bytes', 0))}",
                                     f"{self.format_size_auto(part.get('used_bytes'))}" if part.get('used_bytes') else "",
                                     f"{self.format_size_auto(part.get('free_bytes'))}" if part.get('free_bytes') else "",
                                     str(part.get("info",""))])
            item.setFlags(item.flags() & ~Qt.ItemIsUserCheckable)
            root1.addChild(item)

        # 可选压缩分区/存储备份文件分区
        logger.debug(f"[Debug]可选压缩分区/存储备份文件分区")
        self.partition_forbackup_items = []
        root2 = QTreeWidgetItem(["可选压缩分区/存储备份文件分区"])
        root2.setFlags(root2.flags() & ~Qt.ItemIsSelectable)
        self.tree.addTopLevelItem(root2)
        advclone_found = False
        self.selected_advclone_storage=[]
        for d in self.all_disks:
            disk=self.all_disks.get(d)
            disk_name=disk.get('FriendlyName')
            #print(f"disk={disk}")
            title_key='disk%s:%s'%(d,disk_name)
            title={title_key:disk_name}
            disk_Unallocated= disk.get('Size')-disk.get('AllocatedSize')
            disk_item = QTreeWidgetItem(title)
            disk_item.setFlags(disk_item.flags() & ~Qt.ItemIsSelectable)
            root2.addChild(disk_item)
            # 找到advclone分区，默认选择它，其他不可选
            for part in disk["Partitions"]:
                label= str(part.get("label","") or "")
                label_lower = (part.get("label") or "").lower()
                logger.debug(f"[Debug]Finding advclone...\n{part}")
                if label_lower == "advclone":
                    logger.debug(f"[Debug]Finded advclone...\n")
                    advclone_found = True
                    self.selected_advclone_storage = [part]
                    item = QTreeWidgetItem([f"{part.get('Type','')} ({part.get('drive_letter','')})",
                                            label,
                                            f"{self.format_size_auto(part.get('size_bytes', 0))}",
                                            f"{part.get('used_bytes',0)/1024**3:.2f} GB",
                                            f"--",
                                            str(part.get("info",""))])
                    item.setData(0, Qt.UserRole, part)  # 绑定分区数据
                    item.setFlags(item.flags() & ~Qt.ItemIsUserCheckable)
                    item.setCheckState(0, Qt.Checked)
                    disk_item.addChild(item)
                    self.partition_forbackup_items.append(part)
                    break
                logger.debug(f"advclone_found={advclone_found}")   
            if advclone_found == False :      
               #如果没有advclone分区，且没有未分配空间或者未分配空间大小不足的时候，让用户自己选择
                logger.debug(f"No advclone , load partition to choose for shrink")
                for part in disk["Partitions"]:
                    free_bytes = part.get("free_bytes",0)
                    logger.debug(f"[Debug]找到其他满足大小的分区ing:\n{part}\nfree_bytes={free_bytes}")
                    # 其他分区，如果 free_bytes >= need_bytes 才能选
                    if free_bytes and free_bytes > int(self.need_bytes):
                        label = part.get("label") or ""
                        #part_info = f"{part.get('Type','')} ({part.get('drive_letter','')}:)" if part.get('drive_letter') else part.get('Type','')
                        item = QTreeWidgetItem([f"{part.get('Type','')} ({part.get('drive_letter','')})",
                                                f"{label}",
                                                f"{self.format_size_auto(part.get('size_bytes', 0))}",
                                                f"{part.get('used_bytes',0)/1024**3:.2f} GB",
                                                f"{free_bytes/1024**3:.2f} GB",
                                                str(part.get("info",""))])
                        item.setData(0, Qt.UserRole, part)  # 绑定分区数据
                        if advclone_found == False:
                            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                            item.setCheckState(0, Qt.Unchecked)
                        else:
                            item.setFlags(item.flags() | Qt.ItemIsEnabled)
                        disk_item.addChild(item)
                        self.partition_forbackup_items.append(part)
                logger.debug(f"load disk Unallocated")
                if disk_Unallocated > int(self.need_bytes):
                    part={'DiskNumber':int(d), 'Type':'Unallocated'}
                    item = QTreeWidgetItem([f"Unallocated",
                                            "",
                                            f"{self.format_size_auto(disk_Unallocated)}",
                                            "--",
                                            "--",
                                            str("Unallocated")])
                    item.setData(0, Qt.UserRole, part)  # 绑定分区数据
                    item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                    item.setCheckState(0, Qt.Unchecked)
                    disk_item.addChild(item)
                    self.partition_forbackup_items.append(part)
                
        self.tree.itemChanged.connect(self.on_item_changed)                
        self.tree.expandAll()
        print(f"self.partition_forbackup_items={self.partition_forbackup_items}")

    def on_item_changed(self, item, column):
        """确保在可选分区中只能勾选一个"""
        try:
            if not hasattr(self, "_handling_check"):
                self._handling_check = False
            if self._handling_check:
                return

            # 只关心可选压缩分区节点下的项
            top_item = item
            while top_item.parent():
                top_item = top_item.parent()
            if top_item.text(0) != "可选压缩分区/存储备份文件分区":
                return

            # 如果当前项被勾选，则取消同级别的其他勾选
            if item.checkState(0) == Qt.Checked:
                self._handling_check = True
                parent = item.parent()
                if parent:
                    for i in range(parent.childCount()):
                        sibling = parent.child(i)
                        if sibling is not item and sibling.checkState(0) == Qt.Checked:
                            sibling.setCheckState(0, Qt.Unchecked)
                else:
                    # 没有父节点时，遍历所有子磁盘项的分区
                    for i in range(self.tree.topLevelItemCount()):
                        root = self.tree.topLevelItem(i)
                        if root.text(0) == "可选压缩分区/存储备份文件分区":
                            for d in range(root.childCount()):
                                disk_item = root.child(d)
                                for p in range(disk_item.childCount()):
                                    other = disk_item.child(p)
                                    if other is not item and other.checkState(0) == Qt.Checked:
                                        other.setCheckState(0, Qt.Unchecked)
                self._handling_check = False
        except Exception as e:
            print(f"[Error] on_item_changed: {e}")
        
        
    def go_next(self):
        try:
            logger.debug("======[Debug]ConfirmSelectionPage: go_next======")
            logger.debug(f"self.selected_first_page: {self.selected_first_page}")

            # 读取第二部分（可选压缩分区/存储备份文件分区）中被勾选的项
            self.selected_storage = []
            storage_root = None
            for i in range(self.tree.topLevelItemCount()):
                root = self.tree.topLevelItem(i)
                if root.text(0) == "可选压缩分区/存储备份文件分区":
                    storage_root = root
                    break

            if storage_root is None:
                QMessageBox.warning(self, "提示", "未找到存储分区节点。")
                return

            # 遍历 storage_root 下的磁盘节点和分区节点，收集被勾选的
            for d in range(storage_root.childCount()):
                disk_item = storage_root.child(d)
                print(f"disk_item={disk_item}")
                for p in range(disk_item.childCount()):
                    item = disk_item.child(p)
                    print(f"[Debug]item={item}, item.checkState(0)={item.checkState(0)}, Qt.Checked={Qt.Checked}")
                    if item.checkState(0) == Qt.Checked:
                        part = item.data(0, Qt.UserRole)
                        print(f"[Debug]part={part}")
                        if part:
                            self.selected_storage=part

            logger.debug(f"self.selected_storage:{self.selected_storage}")

            if not self.selected_storage:
                QMessageBox.warning(self,"提示","未找到可用的存储分区！")
                return

            try:
                size_mb = int(self.size_input.text())
                size_bytes = size_mb * 1024 * 1024
            except ValueError:
                QMessageBox.warning(self,"提示","请输入有效大小！")
                return

            if size_bytes < self.need_bytes:
                QMessageBox.warning(self,"提示","压缩空间不足！")
                return

            # 调用外部回调
            if hasattr(self, 'next_callback') and self.next_callback:
                self.next_callback(self.selected_first_page, self.selected_storage, size_mb)            

        except Exception as e:
            import traceback
            logger.debug(f"[Error] ConfirmSelectionPage.go_next exception:{e}")
            logger.debug(traceback.format_exc())
            QMessageBox.critical(self, "异常", f"点击下一步时出现异常:\n{e}")



# ---------- 第3页 ----------
class ExecutionPage(QWidget):
    def __init__(self, back_callback):
        super().__init__()
        self.back_callback = back_callback
        self.save_path = None
        self.shrink_space_mb = 0
        self.thread = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20,20,20,20)
        layout.setSpacing(15)

        card = QFrame()
        card.setFrameShape(QFrame.StyledPanel)
        card.setStyleSheet("QFrame{background:#ffffff;border-radius:12px;}")
        card_layout = QVBoxLayout(card)

        title = QLabel("执行准备程序")
        title.setFont(QFont("Microsoft YaHei",18,QFont.Bold))
        title.setStyleSheet("color:#1a73e8;")
        card_layout.addWidget(title)

        self.info_label = QLabel("点击开始执行，将调用外部程序。")
        self.info_label.setFont(QFont("Microsoft YaHei",11))
        self.info_label.setStyleSheet("color:#555;")
        card_layout.addWidget(self.info_label)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0,100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        card_layout.addWidget(self.progress_bar)
        
        # 添加输出显示控件
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)  # 只读
        self.output_text.setFont(QFont("Microsoft YaHei", 10))
        self.output_text.setStyleSheet("background:#f5f5f5;color:#333;")
        card_layout.addWidget(self.output_text)

        btn_layout = QHBoxLayout()
        self.btn_back = QPushButton("上一步")
        self.btn_exec = QPushButton("开始执行")
        
        # 设置初始按钮样式
        self.set_buttons_enabled(True)
        
        self.btn_back.clicked.connect(self.back_callback)
        self.btn_exec.clicked.connect(self.start_exec)
        logger.debug("绑定开始执行按钮信号完成")
        btn_layout.addWidget(self.btn_back)
        btn_layout.addWidget(self.btn_exec)
        card_layout.addLayout(btn_layout)

        layout.addWidget(card)
    def set_buttons_enabled(self, enabled):
        """统一设置按钮状态，禁用时变为灰色"""
        self.btn_exec.setEnabled(enabled)
        self.btn_back.setEnabled(enabled)
        
        if enabled:
            # 正常样式 - 启用状态
            normal_style = """
                QPushButton {
                    background-color: #1a73e8;
                    color: white;
                    border-radius: 8px;
                    padding: 6px 18px;
                    border: none;
                }
                QPushButton:hover {
                    background-color: #1669c1;
                }
                QPushButton:pressed {
                    background-color: #0d47a1;
                }
            """
            self.btn_exec.setStyleSheet(normal_style)
            self.btn_back.setStyleSheet(normal_style)
            self.btn_exec.setText("开始执行")
            
        else:
            # 禁用样式 - 灰色
            disabled_style = """
                QPushButton {
                    background-color: #cccccc;
                    color: #666666;
                    border-radius: 8px;
                    padding: 6px 18px;
                    border: 1px solid #aaaaaa;
                }
            """
            self.btn_exec.setStyleSheet(disabled_style)
            self.btn_back.setStyleSheet(disabled_style)
            self.btn_exec.setText("执行中...")
        
        # 强制UI更新
        QApplication.processEvents()

    def set_auto_mode(self, is_auto):
        self.auto_mode = is_auto
        if is_auto:
            self.info_label.setText("全自动模式：即将开始执行备份...") 
            
    def load_data(self, selected_backup, selected_storage, shrink_space_mb, save_path):
        logger.debug(f"[Debug]--ExecutionPage:load_data--")
        self.selected_backup = selected_backup
        self.selected_storage = selected_storage
        self.shrink_space_mb = shrink_space_mb
        self.save_path = save_path

        backup_info = "\n".join([f"{p.get('Type')} ({p.get('drive_letter','')}): {p.get('size','')}{p.get('size_unit','')}" for p in selected_backup])
        print(f"[Debug]selected_storage={selected_storage},{type(selected_storage)}")
        if selected_storage.get('Type')=='Unallocated':
            storage_info = "\nThe unallocated disk space will be formatted to store backup data."
            message=f"已选择备份分区:\n{backup_info}\n\n存储备份文件空间:{storage_info}\n"                    
            self.info_label.setText(message)
        else:
            p = selected_storage
            storage_info = "\n".join(f"{p.get('Type')} ({p.get('drive_letter','')}): {p.get('free_bytes',0)/1024**3:.2f} GB 可用")
            try:
                label=p.get('label')
                if label == 'advclone':
                    message=f"已选择备份分区:\n{backup_info}\n\nadvclone已存在，且空间大下为:\n{storage_info}\n\n备份所需空间大小: {self.shrink_space_mb} MB\n"                    
                    self.info_label.setText(message)
                else:
                    message=f"已选择备份分区:\n{backup_info}\n\n待压缩空间分区:\n{storage_info}\n\n压缩分区大小: {self.shrink_space_mb} MB"
                    self.info_label.setText(message)
                logger.debug(message)
            except Exception as e:
                logger.debug(f"执行出错: {e}")
                return {e}
        
        self.progress_bar.setValue(0)
        logger.debug(f"[Debug]--ExecutionPage:load_data ok --")



    
    def start_exec(self):
        logger.debug("======[Debug]page3: start_exec======")
        try:
            self.set_buttons_enabled(False)
            
            if getattr(self, "auto_mode", False):
                logger.debug("[Debug] 全自动模式执行")
                # 可直接调用对应程序，无需用户交互

            script_path = os.path.join(os.getcwd(), "run_prepare_grub_env.exe")
            
            #script_path = r"C:\Program Files (x86)\Notepad++\notepad++.exe"
            if not os.path.exists(script_path):
                QMessageBox.warning(self, "错误", f"脚本文件不存在！\n路径: {script_path}")
                return

            '''
            # 检查是否已有进程在运行
            if hasattr(self, 'process') and self.process and self.process.state() == QProcess.Running:
                QMessageBox.information(self, "提示", "已有程序正在运行，请等待完成。")
                return
            '''
            # 如果已经创建过进程对象，则先断开旧信号
            if hasattr(self, 'process') and self.process:
                try:
                    self.process.readyReadStandardOutput.disconnect()
                    self.process.readyReadStandardError.disconnect()
                    self.process.finished.disconnect()
                    self.process.errorOccurred.disconnect()
                except TypeError:
                    pass  # 若信号未连接则忽略
            else:
                self.process = QProcess(self)

            self.info_label.setText("执行中，请等待...")
            self.output_text.clear()

            # 启动外部程序
            self.process = QProcess(self)
            self.process.setProgram(script_path)
            self.process.setWorkingDirectory(os.getcwd())
            
            # 连接所有信号
            self.process.readyReadStandardOutput.connect(self.handle_stdout)
            self.process.readyReadStandardError.connect(self.handle_stderr)
            self.process.finished.connect(self.process_finished)
            self.process.errorOccurred.connect(self.handle_process_error)
            #self.process.started.connect(lambda: print("进程已启动"))

       
            
            # 启动进程
            self.process.start()
            
            if not self.process.waitForStarted(5000):  # 等待5秒启动
                raise Exception("进程启动超时")
                
            self.progress_bar.setValue(10)
            
        except Exception as e:
            logger.debug(f"启动进程时出错: {e}")
            QMessageBox.critical(self, "错误", f"启动进程失败: {str(e)}")
            #self.reset_buttons()
            self.set_buttons_enabled(True)  # 重新启用按钮
    
    def process_finished(self, exit_code, exit_status):
        """进程执行完成"""
        logger.debug(f"进程完成 - 退出代码: {exit_code}, 状态: {exit_status}")
        
        # 完成进度条
        self.progress_bar.setValue(100)
        
        # 根据退出代码显示不同消息
        if exit_code == 0:
            success_msg = "执行成功！"
            self.info_label.setText(success_msg)
            
            # 询问用户是否继续
            reply = QMessageBox.question(
                self, 
                "完成", 
                f"{success_msg}\n\n请重启系统\n系统重启后默认进入Windows系统，若在重启后按'F9'则开始备份，按'F10'开始还原\n\n点击 Yes 退出程序，点击 No 继续使用。",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                QApplication.quit()  # 只有用户确认时才退出
            else:
                self.set_buttons_enabled(True)  # 重新启用按钮
                
        else:
            error_msg = f"外部程序执行失败！退出代码: {exit_code}"
            self.info_label.setText(error_msg)
            QMessageBox.warning(self, "失败", error_msg)
            self.set_buttons_enabled(True)  # 重新启用按钮

    def reset_buttons(self):
        """重置按钮状态"""
        self.btn_exec.setEnabled(True)
        self.btn_back.setEnabled(True)
        if hasattr(self, 'btn_cancel'):
            self.btn_cancel.setEnabled(False)

    def cancel_execution(self):
        """取消执行"""
        if hasattr(self, 'process') and self.process and self.process.state() == QProcess.Running:
            reply = QMessageBox.question(
                self, 
                "确认取消", 
                "确定要终止正在运行的程序吗？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.process.terminate()
                if not self.process.waitForFinished(5000):  # 等待5秒
                    self.process.kill()  # 强制终止
                self.info_label.setText("执行已取消")
                self.set_buttons_enabled(True)
    
    def handle_stdout(self):
        try:
            data = self.process.readAllStandardOutput()
            output = data.data().decode("utf-8", errors="ignore").strip()
            if output:
                self.output_text.append(output)
                #logger.debug(f"STDOUT: {output}") 
            
            # 模拟进度条增加
            current_value = self.progress_bar.value()
            if current_value < 90:
                self.progress_bar.setValue(current_value + 5)
                
        except Exception as e:
            logger.debug(f"处理标准输出时出错: {e}")

    def handle_stderr(self):
        try:
            data = self.process.readAllStandardError()
            output = data.data().decode("utf-8", errors="ignore").strip()
            if output:
                self.output_text.append(f"<font color='red'>错误: {output}</font>")
                #logger.debug(f"STDERR: {output}")
        except Exception as e:
            logger.debug(f"处理标准错误时出错: {e}")
    
    def handle_process_error(self, error):
        """处理进程错误"""
        error_msg = f"进程错误: {error}"
        logger.debug(error_msg)
        self.output_text.append(f"<font color='red'>{error_msg}</font>")
        #self.reset_buttons()
        self.set_buttons_enabled(True)  # 重新启用按钮


        
# ---------------- 初始化线程 ----------------
class InitThread(QThread):
    finished_signal = pyqtSignal(object)  # 传回 all_disks_data

    def run(self):
        # 模拟耗时操作
        # 这里替换为 DP.get_system_disk_partitions()
        DP = basic_disk_patitions()
        all_disks_data = DP.get_system_disk_partitions()
        filename = f"disk_details_1st.json"
        first_save_path = os.path.join(os.getcwd(),filename)
        # 写入前先清空文件
        with open(first_save_path, "w", encoding="utf-8") as f:
            f.write("")  # 先清空文件内容
        with open(first_save_path,"w",encoding="utf-8") as f:
            json.dump(all_disks_data,f,ensure_ascii=False,indent=2)
            time.sleep(1)  # 模拟延迟
        self.finished_signal.emit(all_disks_data)

# ---------------- 初始化窗口 ----------------
class InitWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("初始化")
        self.resize(300, 100)
        layout = QVBoxLayout(self)
        self.label = QLabel("正在初始化，请稍候...")
        self.progress = QProgressBar()
        self.progress.setRange(0,0)  # 无限加载
        layout.addWidget(self.label)
        layout.addWidget(self.progress)   

# ---------------- 主程序 ----------------



if __name__ == "__main__":
    
    def is_admin():
        """检查是否有管理员权限"""
        try:
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except:
            return False

    def run_as_admin():
        """尝试以管理员权限重新运行自己"""
        script = sys.executable
        params = ' '.join(f'"{x}"' for x in sys.argv)
        try:
            ctypes.windll.shell32.ShellExecuteW(
                None, "runas", script, params, None, 1
            )
            sys.exit(0)
        except Exception as e:
            ctypes.windll.user32.MessageBoxW(0, f"无法以管理员权限重新运行程序！\n{e}", "权限不足", 0)
            sys.exit(1)

    if not is_admin():
        # 弹窗提示并尝试以管理员权限重新运行
        ctypes.windll.user32.MessageBoxW(0, "请以管理员权限运行此程序！将尝试提升权限...", "权限不足", 0)
        run_as_admin()
        #sys.exit(1)

    
    app = QApplication(sys.argv)

    init_win = InitWindow()
    init_win.show()

    def on_init_finished(all_disks_data):
        logger.debug("初始化完成:", all_disks_data)
        init_win.close()
        # 进入主界面
        win = BackupWizard(all_disks_data)
        win.show()

    thread = InitThread()
    thread.finished_signal.connect(on_init_finished)
    thread.start()

    sys.exit(app.exec_())
        

