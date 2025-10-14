# -*- coding:utf-8 -*-
import os, sys, re
import json
import subprocess
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel,
    QPushButton, QTreeWidget, QTreeWidgetItem, QMessageBox,QLineEdit,
    QHBoxLayout, QStackedWidget, QFrame, QSplitter, QProgressBar, QTextEdit
)
from PyQt5.QtCore import Qt, QSettings, QThread, pyqtSignal, QProcess
from PyQt5.QtGui import  QFont, QIntValidator


import time, logging

from get_partitions_basic import basic_disk_patitions

# 日志名称
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_file = f"log\\log_QT_{timestamp}.txt"
# ===================== 日志处理 =====================
'''
class Logger(object):
    def __init__(self, filename=log_file):
        # 尝试获取原 stdout
        self.terminal = getattr(sys, "__stdout__", None)
        self.log = open(filename, "a", encoding="utf-8")

    def write(self, message):
        # 写入控制台（如果有）
        if self.terminal:
            try:
                self.terminal.write(message)
            except Exception:
                pass
        # 写入日志文件
        if self.log:
            self.log.write(message)
            self.log.flush()

    def flush(self):
        if self.terminal:
            try:
                self.terminal.flush()
            except Exception:
                pass
        if self.log:
            self.log.flush()
log_path = os.path.join(os.path.dirname(sys.executable if getattr(sys, 'frozen', False) else __file__), log_file)
sys.stdout = Logger(log_path)
sys.stderr = sys.stdout
'''
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
            "⚙️ 高级备份模式：可自行选择源分区、目标存储路径及压缩设置，适合进阶用户。"
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
                size = f"{self.format_size_auto(part.get('used_bytes', 0))}"
                free = f"{part.get('free_bytes',0)/1024**3:.2f} GB" if part.get('free_bytes') else ""
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
        if self.back_callback:
            btn_back = QPushButton("上一步")
            btn_back.setMinimumHeight(36)
            btn_back.setFont(QFont("Microsoft YaHei", 10, QFont.Bold))
            btn_back.setStyleSheet(
                "QPushButton { background-color:#1a73e8;color:white;border-radius:8px;padding:6px 18px; }"
                "QPushButton:hover { background-color:#1669c1; }"
                "QPushButton:pressed { background-color:#0d47a1; }"
            )
            btn_back.clicked.connect(self.back_callback)
            btn_layout.addWidget(btn_back)
        btn_next = QPushButton("下一步")
        btn_next.setMinimumHeight(36)
        btn_next.setFont(QFont("Microsoft YaHei", 10, QFont.Bold))
        btn_next.setStyleSheet(
            "QPushButton { background-color:#1a73e8;color:white;border-radius:8px;padding:6px 18px; }"
            "QPushButton:hover { background-color:#1669c1; }"
            "QPushButton:pressed { background-color:#0d47a1; }"
        )
        btn_next.clicked.connect(self.go_next)
        btn_layout.addWidget(btn_next)
        btn_layout.addStretch()
        card_layout.addLayout(btn_layout)

        layout.addWidget(card)
        
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
    已选分区总大小: {total_used_bytes} bytes
    所需空间: {need_bytes} bytes
    advclone 分区可用: {advclone_available_size_bytes} bytes"""
                            QMessageBox.warning(self,"提示",mesg)
                            return
            # 正常跳转第二页，并传递已选分区
            if hasattr(self, 'next_callback'):
                self.next_callback(selected)

        except Exception as e:
            logger.error(f"执行出错: {e}")
            QMessageBox.critical(self,"错误", f"出现异常: {e}")
            return



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
        for s in ["一、选择模式", "二、选择分区", "三、确认选择", "四、执行备份"]:
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

        # 页面实例化
        self.page0 = ModeSelectPage(self.go_to_auto, self.go_to_advanced)
        self.page1 = PartitionSelectorPage(all_disks, self.go_to_confirm, self.compress_rate, back_callback=self.go_to_mode_select)
        self.page2 = ConfirmSelectionPage(self.go_to_select, self.go_to_exec, all_disks, self.compress_rate)
        self.page3 = ExecutionPage(self.go_to_confirm_back)

        self.stack.addWidget(self.page0)
        self.stack.addWidget(self.page1)
        self.stack.addWidget(self.page2)
        self.stack.addWidget(self.page3)

        self.update_steps(0)

    # ---------------- 辅助函数 ----------------
    def update_steps(self, index):
        for i, lbl in enumerate(self.step_labels):
            lbl.setStyleSheet("color:#1a73e8;" if i == index else "color:#777;")

    def getConfigValue(self, section, key):
        return 5  # 占位

    # ---------------- 页面切换 ----------------
    def go_to_mode_select(self):
        """返回模式选择页"""
        for lbl in self.step_labels:
            lbl.show()
        self.stack.setCurrentWidget(self.page0)
        self.update_steps(0)

    def go_to_advanced(self):
        """进入高级模式"""
        for lbl in self.step_labels:
            lbl.show()
        self.stack.setCurrentWidget(self.page1)
        self.update_steps(1)

    def go_to_auto(self):
        """进入全自动模式"""
        # 隐藏中间步骤
        logger.debug(f"[Debug]BackupWizard->go_to_auto")
        self.step_labels[1].hide()
        self.step_labels[2].hide()
        self.update_steps(3)
        advclone_found = False
        advclone_size_ok = False
        # ---------------- 自动模式参数 ----------------
        selected_backup = []     # 磁盘全部分区
        selected_storage = []    # 可留空或从 DP 自动选择
        total_used_bytes=0
        shrink_space_mb = 2048   # 默认压缩空间大小
        #计算总大小,
        #并找到合适的advclone分区，如果有判断大小是否OK，如果没有则自动选择目标分区
        try:
            for d in self.all_disks:
                disk=self.all_disks.get(d)
                for part in disk["Partitions"]:
                    logger.debug(f"[Debug]{part.get('label', '')}")
                    logger.debug(part.get("label", ""))
                    if part.get("label", "").lower() != "advclone":
                        selected_backup.append(part)
                        if part.get("used_bytes"):
                            total_used_bytes = total_used_bytes + part.get("used_bytes")
                        else:
                            total_used_bytes = total_used_bytes + part.get("size_bytes",0)
                    else:
                        logger.debug(f"[Debug]Find advclone")
                        advclone_found = True
                        advclone_size_bytes = part.get("size_bytes",0)
                        advclone_available_size_bytes = advclone_size_bytes - 730*1024*1024 #可用有效空间，去掉advclone自身系统占用空间
                        logger.debug(f"[Debug]advclone_size_bytes={advclone_size_bytes}, advclone_available_size_bytes={advclone_available_size_bytes}")
            need_bytes = int(total_used_bytes + 730*1024*1024 / float(self.compress_rate)) #所需空间补上advclone自身系统占用空间
            logger.debug(f"[Debug]total_used_bytes={total_used_bytes}")
            logger.debug(f"[Debug]need_bytes={need_bytes}")
            shrink_space_mb = int(need_bytes/1024/1024)
            if advclone_found == True:
                if advclone_available_size_bytes < need_bytes:
                    drive = part.get("drive_letter","")
                    mesg = f"""  已有 advclone 分区 ({drive}) 空间不足\n  被选分区已用空间总大小{total_used_bytes} bytes\n  我们需要{need_bytes} bytes\n  但是advclone只用{advclone_size_bytes} bytes\n  请删除或扩展该分区后重新创建。"""
                    QMessageBox.warning(self,"提示",mesg)
                    logger.debug(mesg)
                    return
                else:
                    selected_storage=[part]
            else:
                logger.debug(f"Find the selected_storage to shrink advclone...")
                for d in self.all_disks:
                    disk=self.all_disks.get(d)
                    for part in disk["Partitions"]:
                        part_free_size=part.get('free_bytes', 0)
                        logger.debug(f"{part}, part_free_size={part_free_size}, drive_letter={part.get('drive_letter')}")
                        if part_free_size and part_free_size > need_bytes and part.get('drive_letter')!='':
                            logger.debug("Find it!")
                            selected_storage = [part]
                            mesg = f"""We will shrink {need_bytes}bytes from {part.get('drive_letter')} as advclone partition to store backup files"""
                            logger.debug(f"[Debug]{mesg}")
                            break
        except Exception as e:
            raise
            
                  
        save_path = os.path.join(os.getcwd(), "selected_partitions.json")

        # 标记全自动模式，方便执行页识别
        auto_mode_data = {
            "auto_mode": True,
            "backup": selected_backup,
            "storage": selected_storage,
            "shrink_space_mb": shrink_space_mb
        }
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(auto_mode_data, f, ensure_ascii=False, indent=2)

        # ---------------- 加载到执行页 ----------------
        self.page3.load_data(selected_backup, selected_storage, shrink_space_mb, save_path)
        self.page3.set_auto_mode(True)  # 可在 ExecutionPage 新增此方法
        self.stack.setCurrentWidget(self.page3)

        # 可直接启动执行逻辑（如果希望自动运行）
        # self.page3.start_exec()


    def go_to_confirm(self, selected_first_page):
        """跳转确认选择页"""
        self.page2.load_data(selected_first_page)
        self.stack.setCurrentWidget(self.page2)
        self.update_steps(2)

    def go_to_exec(self, selected_first_page, selected_storage, shrink_space_mb):
        current_time = datetime.now()
        #filename = f"backup_selected_partitions_{current_time.strftime('%Y%m%d_%H%M%S')}.json"
        filename = f"selected_partitions.json"
        self.save_path = os.path.join(os.getcwd(),filename)
        self.shrink_space_mb = shrink_space_mb
        with open(self.save_path,"w",encoding="utf-8") as f:
            logger.debug(f"selected_first_page: {selected_first_page}")
            logger.debug(f"selected_storage: {selected_storage}")
            logger.debug(f"shrink_space_mb: {shrink_space_mb}")
            json.dump({"backup": selected_first_page, "storage": selected_storage, "shrink_space_mb": self.shrink_space_mb},f,ensure_ascii=False,indent=2)
        self.page3.load_data(selected_first_page, selected_storage, self.shrink_space_mb, self.save_path)
        self.stack.setCurrentWidget(self.page3)
        self.update_steps(2)

    def go_to_select(self):
        self.stack.setCurrentWidget(self.page1)
        self.update_steps(1)

    def go_to_confirm_back(self):
        self.stack.setCurrentWidget(self.page2)
        self.update_steps(2)


        
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
        self.tree.setHeaderLabels(["Name","Size","Used","Free","Info"])
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
        btn_back = QPushButton("上一步")
        btn_next = QPushButton("下一步")
        for btn in [btn_back, btn_next]:
            btn.setMinimumHeight(36)
            btn.setFont(QFont("Microsoft YaHei",10,QFont.Bold))
            btn.setStyleSheet("QPushButton {background-color:#1a73e8;color:white;border-radius:8px;padding:6px 18px;} QPushButton:hover {background-color:#1669c1;} QPushButton:pressed {background-color:#0d47a1;}")
        btn_back.clicked.connect(self.back_callback)
        btn_next.clicked.connect(self.go_next)
        btn_layout.addWidget(btn_back)
        btn_layout.addWidget(btn_next)
        card_layout.addLayout(btn_layout)

        layout.addWidget(card)

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
        total_used_bytes = sum(p.get("used_bytes",0) or p.get("size_bytes",0) for p in selected_first_page)
        need_bytes = int(total_used_bytes / float(self.compress_rate))
        self.need_bytes = need_bytes
        logger.debug(f"[Debug]total_used_bytes={total_used_bytes},need_bytes={need_bytes},self.need_bytes={self.need_bytes}")
        self.info_label.setText(f"已选择 {len(selected_first_page)} 个分区\n原始总大小: {self.format_size_auto(total_used_bytes)}\n预计需要空间: {self.format_size_auto(need_bytes)}\n(压缩率: {self.compress_rate})")
        input_default_bytes = self.need_bytes + 750*1024*1024
        input_default_mb = float(input_default_bytes/1024/1024)
        input_default_gb = float(input_default_bytes/1024/1024/1024)
        logger.debug(f"input_default_bytes={input_default_bytes} bytes\ninput_default_mb={input_default_mb} MB\ninput_default_gb={input_default_gb} GB")
        self.size_input.setText(str(int(input_default_mb+1)))

        self.tree.clear()

        # 已选备份分区
        root1 = QTreeWidgetItem(["已选择备份分区"])
        root1.setFlags(root1.flags() & ~Qt.ItemIsSelectable)
        self.tree.addTopLevelItem(root1)
        for part in selected_first_page:
            info = f"{part.get('Type','')} ({part.get('drive_letter','')}:)" if part.get('drive_letter') else part.get('Type','')
            item = QTreeWidgetItem([info,
                                     f"{self.format_size_auto(part.get('size_bytes', 0))}",
                                     f"{part.get('used_bytes',0)/1024**3:.2f} GB" if part.get('used_bytes') else "",
                                     f"{part.get('free_bytes',0)/1024**3:.2f} GB" if part.get('free_bytes') else "",
                                     str(part.get("info",""))])
            item.setFlags(item.flags() & ~Qt.ItemIsUserCheckable)
            root1.addChild(item)

        # 可选存储分区
        self.partition_forbackup_items = []
        root2 = QTreeWidgetItem(["可选存储分区"])
        root2.setFlags(root2.flags() & ~Qt.ItemIsSelectable)
        self.tree.addTopLevelItem(root2)
        advclone_found = False
        self.selected_advclone_storage=[]
        for d in self.all_disks:
            disk=self.all_disks.get(d)
            title_key='disk%s'%d
            title={title_key:disk.get('FriendlyName')}
            disk_item = QTreeWidgetItem(title)
            disk_item.setFlags(disk_item.flags() & ~Qt.ItemIsSelectable)
            root2.addChild(disk_item)
            # 找到advclone分区，默认选择它，其他不可选
            for part in disk["Partitions"]:
                label_lower = (part.get("label") or "").lower()
                logger.debug(f"[Debug]Finding advclone...\n{part}")
                if label_lower == "advclone":
                    logger.debug(f"[Debug]Finded advclone...\n")
                    advclone_found = True
                    self.selected_advclone_storage = [part]
                    item = QTreeWidgetItem([f"{part.get('Type','')} ({part.get('drive_letter','')})",
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
            if advclone_found == False:         
                for part in disk["Partitions"]:
                    free_bytes = part.get("free_bytes",0)
                    logger.debug(f"[Debug]找到其他满足大小的分区ing:\n{part}\nfree_bytes={free_bytes}")
                    # 其他分区，如果 free_bytes >= need_bytes 才能选
                    if free_bytes and free_bytes > int(self.need_bytes):
                        label = part.get("label") or ""
                        #part_info = f"{part.get('Type','')} ({part.get('drive_letter','')}:)" if part.get('drive_letter') else part.get('Type','')
                        item = QTreeWidgetItem([f"{part.get('Type','')} ({part.get('drive_letter','')})",
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
                        
        self.tree.expandAll()


        
        
    def go_next(self):
        try:
            logger.debug("======[Debug]ConfirmSelectionPage: go_next======")
            logger.debug(f"self.selected_first_page: {self.selected_first_page}")

            # 读取第二部分（可选存储分区）中被勾选的项
            self.selected_storage = []
            storage_root = None
            for i in range(self.tree.topLevelItemCount()):
                root = self.tree.topLevelItem(i)
                if root.text(0) == "可选存储分区":
                    storage_root = root
                    break

            if storage_root is None:
                QMessageBox.warning(self, "提示", "未找到存储分区节点。")
                return

            # 遍历 storage_root 下的磁盘节点和分区节点，收集被勾选的
            for d in range(storage_root.childCount()):
                disk_item = storage_root.child(d)
                for p in range(disk_item.childCount()):
                    item = disk_item.child(p)
                    if item.checkState(0) == Qt.Checked:
                        part = item.data(0, Qt.UserRole)
                        if part:
                            self.selected_storage.append(part)

            logger.debug(f"self.selected_storage:{self.selected_storage}")
            '''
            if not self.selected_storage:
                # 自动选择第一个可用分区，防止异常退出
                for d in range(storage_root.childCount()):
                    disk_item = storage_root.child(d)
                    for p in range(disk_item.childCount()):
                        item = disk_item.child(p)
                        part = item.data(0, Qt.UserRole)
                        if part:
                            self.selected_storage.append(part)
                            break
                    if self.selected_storage:
                        break
            '''
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

        title = QLabel("执行备份程序")
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
        for btn in [self.btn_back, self.btn_exec]:
            btn.setMinimumHeight(36)
            btn.setFont(QFont("Microsoft YaHei",10,QFont.Bold))
            btn.setStyleSheet("""
                QPushButton{background-color:#1a73e8;color:white;border-radius:8px;padding:6px 18px;}
                QPushButton:hover{background-color:#1669c1;}
                QPushButton:pressed{background-color:#0d47a1;}
            """)
        self.btn_back.clicked.connect(self.back_callback)
        self.btn_exec.clicked.connect(self.start_exec)
        logger.debug("绑定开始执行按钮信号完成")
        btn_layout.addWidget(self.btn_back)
        btn_layout.addWidget(self.btn_exec)
        card_layout.addLayout(btn_layout)

        layout.addWidget(card)

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
        storage_info = "\n".join([f"{p.get('Type')} ({p.get('drive_letter','')}): {p.get('free_bytes',0)/1024**3:.2f} GB 可用" for p in selected_storage])
        for p in selected_storage:
            try:
                label=p.get('label')
                if label == 'advclone':
                    message=f"已选择备份分区:\n{backup_info}\n\nadvclone已存在，且空间大下为:\n{storage_info}\n\n备份所需空间大小: {self.shrink_space_mb} MB\n"
                    self.info_label.setText(message)
                else:
                    message=f"已选择备份分区:\n{backup_info}\n\n待压缩空间分区:\n{storage_info}\n\n压缩分区大小: {self.shrink_space_mb} MB"
                    self.info_label.setText(message)
            except Exception as e:
                logger.debug(f"执行出错: {e}")
                return {e}
        
        self.progress_bar.setValue(0)
        logger.debug(f"[Debug]--ExecutionPage:load_data ok --")


    def start_exec(self):
        logger.debug("======[Debug]page3: start_exec======")
        try:
            if getattr(self, "auto_mode", False):
                logger.debug("[Debug] 全自动模式执行")
                # 可直接调用对应程序，无需用户交互

            script_path = os.path.join(os.getcwd(), "run_prepare_grub_env.exe")
            
            #script_path = r"C:\Program Files (x86)\Notepad++\notepad++.exe"
            if not os.path.exists(script_path):
                QMessageBox.warning(self, "错误", f"脚本文件不存在！\n路径: {script_path}")
                return

            # 检查是否已有进程在运行
            if hasattr(self, 'process') and self.process and self.process.state() == QProcess.Running:
                QMessageBox.information(self, "提示", "已有程序正在运行，请等待完成。")
                return

            # 禁用按钮
            self.btn_exec.setEnabled(False)
            self.btn_back.setEnabled(False)
            #self.btn_cancel.setEnabled(True)  # 添加取消按钮
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
            self.process.started.connect(lambda: print("进程已启动"))
            
            # 启动进程
            self.process.start()
            
            if not self.process.waitForStarted(5000):  # 等待5秒启动
                raise Exception("进程启动超时")
                
            self.progress_bar.setValue(10)
            
        except Exception as e:
            logger.debug(f"启动进程时出错: {e}")
            QMessageBox.critical(self, "错误", f"启动进程失败: {str(e)}")
            self.reset_buttons()

    def process_finished(self, exit_code, exit_status):
        """进程执行完成"""
        logger.debug(f"进程完成 - 退出代码: {exit_code}, 状态: {exit_status}")
        
        # 完成进度条
        self.progress_bar.setValue(100)
        
        # 根据退出代码显示不同消息
        if exit_code == 0:
            success_msg = "外部程序执行成功！"
            self.info_label.setText(success_msg)
            
            # 询问用户是否继续
            reply = QMessageBox.question(
                self, 
                "完成", 
                f"{success_msg}\n\n点击 Yes 退出程序，点击 No 继续使用。",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                QApplication.quit()  # 只有用户确认时才退出
            else:
                self.reset_buttons()
                
        else:
            error_msg = f"外部程序执行失败！退出代码: {exit_code}"
            self.info_label.setText(error_msg)
            QMessageBox.warning(self, "失败", error_msg)
            self.reset_buttons()

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
                self.reset_buttons()

    def handle_stdout(self):
        try:
            data = self.process.readAllStandardOutput()
            output = data.data().decode("utf-8", errors="ignore").strip()
            if output:
                self.output_text.append(output)
                logger.debug(f"STDOUT: {output}") 
            
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
                logger.debug(f"STDERR: {output}")
        except Exception as e:
            logger.debug(f"处理标准错误时出错: {e}")

    def handle_process_error(self, error):
        """处理进程错误"""
        error_msg = f"进程错误: {error}"
        logger.debug(error_msg)
        self.output_text.append(f"<font color='red'>{error_msg}</font>")
        self.reset_buttons()


        
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
        

