# -*- coding:utf-8 -*-
import os, datetime, sys, re
import json
import subprocess
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel,
    QPushButton, QTreeWidget, QTreeWidgetItem, QMessageBox,QLineEdit, 
    QHBoxLayout, QStackedWidget, QFrame, QSplitter, QProgressBar, QApplication, QTextEdit
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal,QProcess
from PyQt5.QtGui import QFont, QIntValidator

from get_partions_volumes import dispart_partition_volume
'''
# ===================== 日志处理 =====================
class Logger(object):
    def __init__(self, filename="log.txt"):
        self.terminal = sys.stdout
        self.log = open(filename, "a", encoding="utf-8")

    def write(self, message):
        self.terminal.write(message)   # 控制台显示
        self.log.write(message)        # 写入文件
        self.log.flush()               # 实时刷新

    def flush(self):
        pass  # print 会调用 flush，这里留空即可

sys.stdout = Logger("log.txt")
sys.stderr = sys.stdout  # 错误也记录
'''

# ---------- 第1页 ----------
class PartitionSelectorPage(QWidget):
    def __init__(self, all_disks, next_callback):
        super().__init__()
        self.all_disks = all_disks
        self.next_callback = next_callback
        self.compress_rate = 1.5
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20,20,20,20)
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

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Partition #","Label","FS","Capacity","Free Space","Info"])
        self.tree.setColumnWidth(0, 200)   # Partition#列：200像素
        self.tree.setAnimated(True)
        self.tree.setStyleSheet("QTreeWidget {background:#ffffff; border:none; font-size:12px;} QTreeWidget::item:hover {background:#eaf1fb;}")
        card_layout.addWidget(self.tree)

        


        # 遍历磁盘和分区
        self.partition_items = []

        for disk in all_disks:
            disk_item = QTreeWidgetItem([disk["Disk"]])
            disk_item.setFlags(disk_item.flags() & ~Qt.ItemIsSelectable)
            self.tree.addTopLevelItem(disk_item)
            partitons_info = disk["Partitions"]
            # 按盘符或 OffsetBytes 排序
            partitons_info.sort(key=lambda p: (p.get('drive_letter') or '', p.get('OffsetBytes', 0)))
            for part in partitons_info:
                label = str(part.get("label","") or "")
                part_info = f"{part.get('Type','')} ({part.get('drive_letter','')}:)" if part.get('drive_letter') else part.get('Type','')
                size = f"{part.get('size','')} {part.get('size_unit','')}"
                free = f"{part.get('free_bytes',0)/1024**3:.2f} GB" if part.get('free_bytes') else ""
                item = QTreeWidgetItem([part_info,label,part.get('file_system',''),size,free,str(part.get("info",""))])
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

        btn_next = QPushButton("下一步")
        btn_next.setMinimumHeight(36)
        btn_next.setFont(QFont("Microsoft YaHei",10,QFont.Bold))
        btn_next.setStyleSheet("QPushButton { background-color:#1a73e8;color:white;border-radius:8px;padding:6px 18px; } QPushButton:hover { background-color:#1669c1; } QPushButton:pressed { background-color:#0d47a1; }")
        btn_next.clicked.connect(self.go_next)
        card_layout.addWidget(btn_next,alignment=Qt.AlignRight)

        layout.addWidget(card)

    def go_next(self):
        print("======[Debug]page1: go_next======")
        selected = []
        # 遍历 tree，直接读取绑定在 UserRole 的分区数据
        for i in range(self.tree.topLevelItemCount()):
            disk_item = self.tree.topLevelItem(i)
            for j in range(disk_item.childCount()):
                item = disk_item.child(j)
                if item.checkState(0) == Qt.Checked:
                    part = item.data(0, Qt.UserRole)
                    if part:
                        selected.append(part)
        print("selected:", selected)

        if not selected:
            QMessageBox.warning(self,"提示","请至少选择一个分区！")
            return

        # 检查是否存在 advclone 分区且空间不足
        for disk in self.all_disks:
            for part in disk["Partitions"]:
                if (part.get("label") or "").lower() == "advclone":
                    # 计算已选择总大小
                    total_used_bytes = sum(p.get("used_bytes",0) or p.get("size_bytes",0) for p in selected)
                    need_bytes = int(total_used_bytes / float(self.compress_rate)) #所需空间补上advclone自身系统占用空间
                    advclone_size_bytes = part.get("size_bytes",0)
                    advclone_available_size_bytes = advclone_size_bytes - 730*1024*1024 #可用有效空间，去掉advclone自身系统占用空间
                    print(f"[Debug]total_used_bytes={total_used_bytes}, need_bytes={need_bytes},advclone_size_bytes={advclone_size_bytes}，advclone_available_size_bytes={advclone_available_size_bytes} ")
                    if advclone_available_size_bytes < need_bytes:
                        drive = part.get("drive_letter","")
                        mesg = f"""  已有 advclone 分区 ({drive}) 空间不足\n  被选分区已用空间总大小{total_used_bytes} bytes\n  我们需要{need_bytes} bytes\n  但是advclone只用{advclone_size_bytes} bytes\n  请删除或扩展该分区后重新创建。"""
                        QMessageBox.warning(self,"提示",mesg)
                        print(mesg)
                        return  # 停留在第一页

        # 正常跳转第二页
        self.next_callback(selected)

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
        self.tree.setHeaderLabels(["Name","Label","FS","Size","Used","Free","Info"])
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
            return "0 B"
        units = [(1024**3, "GB"), (1024**2,"MB"),(1024,"KB"),(1,"B")]
        for threshold, unit in units:
            if size_bytes >= threshold:
                size = size_bytes / threshold
                return f"{size:.2f} {unit}"
        return f"{size_bytes} B"

    def load_data(self, selected_first_page):
        print(f"======[Debug]page2: load_data======")
        self.selected_first_page = selected_first_page
        total_used_bytes = sum(p.get("used_bytes",0) or p.get("size_bytes",0) for p in selected_first_page)
        need_bytes = int(total_used_bytes / float(self.compress_rate))
        self.need_bytes = need_bytes
        print(f"[Debug]total_used_bytes={total_used_bytes},need_bytes={need_bytes},self.need_bytes={self.need_bytes}")
        self.info_label.setText(f"已选择 {len(selected_first_page)} 个分区\n原始总大小: {self.format_size_auto(total_used_bytes)}\n预计需要空间: {self.format_size_auto(need_bytes)}\n(压缩率: {self.compress_rate})")
        input_default_bytes = self.need_bytes + 750*1024*1024
        input_default_mb = float(input_default_bytes/1024/1024)
        input_default_gb = float(input_default_bytes/1024/1024/1024)
        print(f"input_default_bytes={input_default_bytes} bytes\ninput_default_mb={input_default_mb} MB\ninput_default_gb={input_default_gb} GB")
        self.size_input.setText(str(int(input_default_mb+1)))

        self.tree.clear()
        # 已选备份分区
        root1 = QTreeWidgetItem(["已选择备份分区"])
        root1.setFlags(root1.flags() & ~Qt.ItemIsSelectable)
        self.tree.addTopLevelItem(root1)
        for part in selected_first_page:
            info = f"{part.get('Type','')} ({part.get('drive_letter','')}:)" if part.get('drive_letter') else part.get('Type','')
            item = QTreeWidgetItem([info,str(part.get("label","") or ""),part.get('file_system',''),
                                     f"{part.get('size','')} {part.get('size_unit','')}",
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
        for disk in self.all_disks:
            disk_item = QTreeWidgetItem([disk["Disk"]])
            disk_item.setFlags(disk_item.flags() & ~Qt.ItemIsSelectable)
            root2.addChild(disk_item)
            # 找到advclone分区，默认选择它，其他不可选
            for part in disk["Partitions"]:
                label_lower = (part.get("label") or "").lower()
                print(f"[Debug]Finding advclone...\n{part}")
                if label_lower == "advclone":
                    advclone_found = True
                    self.selected_advclone_storage = [part]
                    item = QTreeWidgetItem([f"{part.get('Type','')} ({part.get('drive_letter','')})",part.get("label") or "",part.get("file_system",""),
                                            f"{part.get('size','')} {part.get('size_unit','')}",
                                            f"{part.get('used_bytes',0)/1024**3:.2f} GB",
                                            f"--",
                                            str(part.get("info",""))])
                    item.setData(0, Qt.UserRole, part)  # 绑定分区数据
                    item.setFlags(item.flags() & ~Qt.ItemIsUserCheckable)
                    item.setCheckState(0, Qt.Checked)
                    disk_item.addChild(item)
                    self.partition_forbackup_items.append(part)
                    break
                print(f"advclone_found={advclone_found}")
                
            if advclone_found == False:         
                for part in disk["Partitions"]:
                    free_bytes = part.get("free_bytes",0)
                    print(f"[Debug]找到其他满足大小的分区ing:\n{part}\nfree_bytes={free_bytes}")
                    # 其他分区，如果 free_bytes >= need_bytes 才能选
                    if free_bytes and free_bytes >= int(self.need_bytes*1.05):
                        label = part.get("label") or ""
                        part_info = f"{part.get('Type','')} ({part.get('drive_letter','')}:)" if part.get('drive_letter') else part.get('Type','')
                        item = QTreeWidgetItem([part_info,
                                                f"{part.get('size','')} {part.get('size_unit','')}",
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
        print("======[Debug]page2: go_next======")
        print("self.partition_forbackup_items is:\n",self.partition_forbackup_items)

        # 读取第二部分（可选存储分区）中被勾选的项
        self.selected_storage = []
        # storage root 应该是第一个 root 的下一个 top-level。我们先找到"可选存储分区"根结点
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
                        
        print("self.selected_storage:",self.selected_storage)
        if not self.selected_storage:
            QMessageBox.warning(self,"提示","请选择一个存储分区用于备份！")
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

        self.next_callback(self.selected_first_page, self.selected_storage, size_mb)

# ---------- 第3页执行线程 ----------
'''
# ---------- 执行线程 ----------
class ExecThread(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(bool, str)  # 成功与否, 信息

    def __init__(self, cmd):
        super().__init__()
        self.cmd = cmd

    def run(self):
        try:
            # 这里使用 Popen 调用外部程序
            # stdout/stderr 可根据实际需求读取并更新进度
            proc = subprocess.Popen(self.cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            # 简单模拟进度
            for i in range(101):
                self.msleep(50)  # 模拟等待
                self.progress.emit(i)
            proc.wait()
            if proc.returncode == 0:
                self.finished.emit(True, "外部程序执行完成！")
            else:
                self.finished.emit(False, f"程序返回错误码: {proc.returncode}")
        except Exception as e:
            self.finished.emit(False, str(e))
'''
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
        btn_layout.addWidget(self.btn_back)
        btn_layout.addWidget(self.btn_exec)
        card_layout.addLayout(btn_layout)

        layout.addWidget(card)

            
    def load_data(self, selected_backup, selected_storage, shrink_space_mb, save_path):
        self.selected_backup = selected_backup
        self.selected_storage = selected_storage
        self.shrink_space_mb = shrink_space_mb
        self.save_path = save_path

        backup_info = "\n".join([f"{p.get('Type')} ({p.get('drive_letter','')}): {p.get('size','')}{p.get('size_unit','')}" for p in selected_backup])
        storage_info = "\n".join([f"{p.get('Type')} ({p.get('drive_letter','')}): {p.get('free_bytes',0)/1024**3:.2f} GB 可用" for p in selected_storage])
        self.info_label.setText(
            f"已选择备份分区:\n{backup_info}\n\n待压缩空间分区:\n{storage_info}\n\n压缩分区大小: {self.shrink_space_mb} MB"
        )
        self.progress_bar.setValue(0)

    def start_exec(self):
        print("======[Debug]page3: start_exec======")
        if not self.save_path or not os.path.exists(self.save_path):
            QMessageBox.warning(self,"错误","配置文件不存在！")
            return

        # 禁用按钮
        self.btn_exec.setEnabled(False)
        self.btn_back.setEnabled(False)
        self.info_label.setText("执行中，请等待...")

        # 启动外部程序
        self.process = QProcess(self)
        #self.process.setProgram("notepad.exe")  # 这里替换为你的外部程序
        #self.process.setArguments([self.save_path])
        self.process.setProgram(sys.executable)  # Python 解释器
        self.process.setWorkingDirectory(r"D:\QT\20250926")
        self.process.setArguments([r"D:\QT\20250926\prepare_grub_env.py"])
        self.process.readyReadStandardOutput.connect(self.handle_stdout)
        self.process.readyReadStandardError.connect(self.handle_stderr)
        self.process.finished.connect(self.process_finished)
        self.process.errorOccurred.connect(lambda e: print("QProcess error:", e))
        self.process.start()

        # 模拟进度条
        self.progress_bar.setValue(10)

    def handle_stdout(self):
        output = self.process.readAllStandardOutput().data().decode("utf-8").strip()
        if output:
            self.output_text.append(output)
            print(output) 
        
        # 模拟进度条增加
        value = self.progress_bar.value() + 10
        self.progress_bar.setValue(min(value, 90))

    def handle_stderr(self):
        output = bytes(self.process.readAllStandardError()).decode("utf-8")
        self.output_text.append(f"错误: {output}")

    def process_finished(self):
        self.progress_bar.setValue(100)
        self.btn_exec.setEnabled(True)
        self.btn_back.setEnabled(True)
        self.info_label.setText("外部程序执行完成！")
        #QMessageBox.information(self, "完成", "外部程序执行完成！")
        reply = QMessageBox.information(self, "完成", "外部程序执行完成！点击 OK 退出程序。")
        QApplication.quit()
        


# ---------- 主向导 ----------
class BackupWizard(QMainWindow):
    def __init__(self, all_disks):
        super().__init__()
        self.setWindowTitle("AdvClone 备份向导")
        self.resize(1000,600)

        splitter = QSplitter()
        splitter.setHandleWidth(1)
        self.setCentralWidget(splitter)

        # 左侧步骤栏
        self.step_widget = QWidget()
        step_layout = QVBoxLayout(self.step_widget)
        step_layout.setContentsMargins(10,20,10,20)
        step_layout.setSpacing(20)
        self.step_labels = []
        for s in ["1. 选择分区","2. 确认选择","3. 执行备份"]:
            lbl = QLabel(s)
            lbl.setFont(QFont("Microsoft YaHei",12,QFont.Bold))
            lbl.setStyleSheet("color:#777;")
            self.step_labels.append(lbl)
            step_layout.addWidget(lbl)
        step_layout.addStretch()
        splitter.addWidget(self.step_widget)

        # 右侧堆栈页面
        self.stack = QStackedWidget()
        splitter.addWidget(self.stack)
        splitter.setStretchFactor(0,1)
        splitter.setStretchFactor(1,5)

        self.all_disks = all_disks
        self.compress_rate = 1.5

        self.page1 = PartitionSelectorPage(all_disks, self.go_to_confirm)
        self.page2 = ConfirmSelectionPage(self.go_to_select, self.go_to_exec, all_disks, self.compress_rate)
        self.page3 = ExecutionPage(self.go_to_confirm_back)

        self.stack.addWidget(self.page1)
        self.stack.addWidget(self.page2)
        self.stack.addWidget(self.page3)

        self.update_steps(0)

    def update_steps(self,index):
        for i,lbl in enumerate(self.step_labels):
            lbl.setStyleSheet("color:#1a73e8;" if i==index else "color:#777;")

    def go_to_confirm(self, selected):
        self.selected_first_page = selected
        self.page2.load_data(selected)
        self.stack.setCurrentWidget(self.page2)
        self.update_steps(1)

    def go_to_select(self):
        self.stack.setCurrentWidget(self.page1)
        self.update_steps(0)

    def go_to_exec(self, selected_first_page, selected_storage, shrink_space_mb):
        current_time = datetime.datetime.now()
        #filename = f"backup_selected_partitions_{current_time.strftime('%Y%m%d_%H%M%S')}.json"
        filename = f"selected_partitions.json"
        self.save_path = os.path.join(os.getcwd(),filename)
        self.shrink_space_mb = shrink_space_mb
        with open(self.save_path,"w",encoding="utf-8") as f:
            print(f"selected_first_page: {selected_first_page}")
            print(f"selected_storage: {selected_storage}")
            print(f"shrink_space_mb: {shrink_space_mb}")
            json.dump({"backup": selected_first_page, "storage": selected_storage, "shrink_space_mb": self.shrink_space_mb},f,ensure_ascii=False,indent=2)
        self.page3.load_data(selected_first_page, selected_storage, self.shrink_space_mb, self.save_path)
        self.stack.setCurrentWidget(self.page3)
        self.update_steps(2)

    def go_to_confirm_back(self):
        self.stack.setCurrentWidget(self.page2)
        self.update_steps(1)

# ---------- 运行 ----------
if __name__=="__main__":
    import sys
    '''
    # 模拟磁盘数据
    all_disks_0 = [{'Disk': 'Disk 0', 'Partitions': [{'PartitionNumber': '1', 'Type': 'System', 'VolumeNumber': 0, 'drive_letter': '', 'label': None, 'file_system': 'FAT32', 'type': 'Partition', 'size': '600', 'size_unit': 'MB', 'status': 'Healthy', 'info': 'Hidden', 'size_bytes': 629145600, 'OffsetBytes': 1048576, 'SortedOffsetIndex': 1, 'free_bytes': None, 'used_bytes': None}, {'PartitionNumber': '2', 'Type': 'Unknown', 'OffsetBytes': 630194176, 'SortedOffsetIndex': 2, 'free_bytes': None, 'used_bytes': None}, {'PartitionNumber': '3', 'Type': 'Unknown', 'OffsetBytes': 1703936000, 'SortedOffsetIndex': 3, 'free_bytes': None, 'used_bytes': None}]}, {'Disk': 'Disk 1', 'Partitions': [{'PartitionNumber': '1', 'Type': 'System', 'VolumeNumber': 4, 'drive_letter': 'E', 'label': None, 'file_system': 'FAT32', 'type': 'Partition', 'size': '100', 'size_unit': 'MB', 'status': 'Healthy', 'info': 'System', 'size_bytes': 104857600, 'OffsetBytes': 1048576, 'SortedOffsetIndex': 1, 'free_bytes': 72510464, 'used_bytes': 28152832}, {'PartitionNumber': '2', 'Type': 'Reserved', 'OffsetBytes': 105906176, 'SortedOffsetIndex': 2, 'free_bytes': None, 'used_bytes': None}, {'PartitionNumber': '3', 'Type': 'Primary', 'VolumeNumber': 1, 'drive_letter': 'C', 'label': None, 'file_system': 'NTFS', 'type': 'Partition', 'size': '237', 'size_unit': 'GB', 'status': 'Healthy', 'info': 'Boot', 'size_bytes': 254476812288, 'OffsetBytes': 122683392, 'SortedOffsetIndex': 3, 'free_bytes': 189623177216, 'used_bytes': 65256263680}, {'PartitionNumber': '6', 'Type': 'Primary', 'VolumeNumber': 2, 'drive_letter': 'F', 'label': 'advclone', 'file_system': 'NTFS', 'type': 'Partition', 'size': '40', 'size_unit': 'GB', 'status': 'Healthy', 'info': None, 'size_bytes': 42949672960, 'OffsetBytes': 255002148864, 'SortedOffsetIndex': 4, 'free_bytes': 43177353216, 'used_bytes': 88985600}, {'PartitionNumber': '4', 'Type': 'Primary', 'VolumeNumber': 3, 'drive_letter': 'D', 'label': '新加卷', 'file_system': 'NTFS', 'type': 'Partition', 'size': '19', 'size_unit': 'GB', 'status': 'Healthy', 'info': None, 'size_bytes': 20401094656, 'OffsetBytes': 298268491776, 'SortedOffsetIndex': 5, 'free_bytes': 20879720448, 'used_bytes': 90746880}, {'PartitionNumber': '5', 'Type': 'Recovery', 'VolumeNumber': 5, 'drive_letter': '', 'label': None, 'file_system': 'NTFS', 'type': 'Partition', 'size': '793', 'size_unit': 'MB', 'status': 'Healthy', 'info': 'Hidden', 'size_bytes': 831520768, 'OffsetBytes': 319240011776, 'SortedOffsetIndex': 6, 'free_bytes': None, 'used_bytes': None}]}]
    
    all_disks_1 = [{'Disk': 'Disk 0', 'Partitions': [{'PartitionNumber': '1', 'Type': 'System', 'VolumeNumber': 0, 'drive_letter': '', 'label': None, 'file_system': 'FAT32', 'type': 'Partition', 'size': '600', 'size_unit': 'MB', 'status': 'Healthy', 'info': 'Hidden', 'size_bytes': 629145600, 'OffsetBytes': 1048576, 'SortedOffsetIndex': 1, 'free_bytes': None, 'used_bytes': None}, {'PartitionNumber': '2', 'Type': 'Unknown', 'OffsetBytes': 630194176, 'SortedOffsetIndex': 2, 'free_bytes': None, 'used_bytes': None}, {'PartitionNumber': '3', 'Type': 'Unknown', 'OffsetBytes': 1703936000, 'SortedOffsetIndex': 3, 'free_bytes': None, 'used_bytes': None}]}, {'Disk': 'Disk 1', 'Partitions': [{'PartitionNumber': '1', 'Type': 'System', 'VolumeNumber': 4, 'drive_letter': 'E', 'label': None, 'file_system': 'FAT32', 'type': 'Partition', 'size': '100', 'size_unit': 'MB', 'status': 'Healthy', 'info': 'System', 'size_bytes': 104857600, 'OffsetBytes': 1048576, 'SortedOffsetIndex': 1, 'free_bytes': 72510464, 'used_bytes': 28152832}, {'PartitionNumber': '2', 'Type': 'Reserved', 'OffsetBytes': 105906176, 'SortedOffsetIndex': 2, 'free_bytes': None, 'used_bytes': None}, {'PartitionNumber': '3', 'Type': 'Primary', 'VolumeNumber': 1, 'drive_letter': 'C', 'label': None, 'file_system': 'NTFS', 'type': 'Partition', 'size': '237', 'size_unit': 'GB', 'status': 'Healthy', 'info': 'Boot', 'size_bytes': 254476812288, 'OffsetBytes': 122683392, 'SortedOffsetIndex': 3, 'free_bytes': 189623177216, 'used_bytes': 65256263680}, {'PartitionNumber': '4', 'Type': 'Primary', 'VolumeNumber': 3, 'drive_letter': 'D', 'label': '新加卷', 'file_system': 'NTFS', 'type': 'Partition', 'size': '19', 'size_unit': 'GB', 'status': 'Healthy', 'info': None, 'size_bytes': 20401094656, 'OffsetBytes': 298268491776, 'SortedOffsetIndex': 5, 'free_bytes': 20879720448, 'used_bytes': 90746880}, {'PartitionNumber': '5', 'Type': 'Recovery', 'VolumeNumber': 5, 'drive_letter': '', 'label': None, 'file_system': 'NTFS', 'type': 'Partition', 'size': '793', 'size_unit': 'MB', 'status': 'Healthy', 'info': 'Hidden', 'size_bytes': 831520768, 'OffsetBytes': 319240011776, 'SortedOffsetIndex': 6, 'free_bytes': None, 'used_bytes': None}]}]
    '''
    DP = dispart_partition_volume()
    # 获取所有disk的分区信息
    #all_disks_data = DP.get_all_disks_partitons()
    # 仅获取系统C盘所在disk的磁盘信息
    all_disks_data = DP.get_system_disk_partitions()
    print("all_disks_data is:\n",all_disks_data)
    # 保存第一次获取磁盘信息
    # 获取当前时间
    current_time = datetime.datetime.now()
    #filename = f"backup_disk_details_1_{current_time.strftime('%Y%m%d_%H%M%S')}.json"
    filename = f"disk_details_1.json"
    first_save_path = os.path.join(os.getcwd(),filename)
    with open(first_save_path,"w",encoding="utf-8") as f:
        json.dump(all_disks_data,f,ensure_ascii=False,indent=2)
    
    app = QApplication(sys.argv)
    win = BackupWizard(all_disks_data)
    win.show()
    sys.exit(app.exec_())
