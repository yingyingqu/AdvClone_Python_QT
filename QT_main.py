# -*- coding:utf-8 -*-
import os, sys, re
import json
import subprocess
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel,
    QPushButton, QTreeWidget, QTreeWidgetItem, QMessageBox,QLineEdit,
    QHBoxLayout, QStackedWidget, QFrame, QSplitter, QProgressBar, QApplication, QTextEdit
)
from PyQt5.QtCore import Qt, QSettings, QThread, pyqtSignal,QProcess
from PyQt5.QtGui import  QFont, QIntValidator

from get_partitions_basic import basic_disk_patitions

# 日志名称
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_file = f"log\\log_QT_{timestamp}.txt"
# ===================== 日志处理 =====================
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


# ---------- 第1页 ----------
class PartitionSelectorPage(QWidget):
    def __init__(self, all_disks, next_callback, compress_rate):
        super().__init__()
        self.all_disks = all_disks
        self.next_callback = next_callback
        self.compress_rate = compress_rate
        
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

        for key in all_disks:
            disk=all_disks.get(key)
            disk_item = QTreeWidgetItem(self.tree)
            disk_item.setFlags(disk_item.flags() & ~Qt.ItemIsSelectable)
            self.tree.addTopLevelItem(disk_item)
            partitons_info = disk["Partitions"]
            # 按盘符或 OffsetBytes 排序
            partitons_info.sort(key=lambda p: (p.get('OffsetBytes', 0)))
            for part in partitons_info:
                print("[Debug]", part)
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

        btn_next = QPushButton("下一步")
        btn_next.setMinimumHeight(36)
        btn_next.setFont(QFont("Microsoft YaHei",10,QFont.Bold))
        btn_next.setStyleSheet("QPushButton { background-color:#1a73e8;color:white;border-radius:8px;padding:6px 18px; } QPushButton:hover { background-color:#1669c1; } QPushButton:pressed { background-color:#0d47a1; }")
        btn_next.clicked.connect(self.go_next)
        card_layout.addWidget(btn_next,alignment=Qt.AlignRight)

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
        for d in self.all_disks:
            disk=self.all_disks.get(d)
            for part in disk["Partitions"]:
                if (part.get("label") or "").lower() == "advclone":
                    # 计算已选择总大小
                    try:
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
                    except Exception as e:
                        print(f"执行出错: {e}")
                        return {e}
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
                print(f"[Debug]Finding advclone...\n{part}")
                if label_lower == "advclone":
                    print(f"[Debug]Finded advclone...\n")
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
                print(f"advclone_found={advclone_found}")   
            if advclone_found == False:         
                for part in disk["Partitions"]:
                    free_bytes = part.get("free_bytes",0)
                    print(f"[Debug]找到其他满足大小的分区ing:\n{part}\nfree_bytes={free_bytes}")
                    # 其他分区，如果 free_bytes >= need_bytes 才能选
                    if free_bytes and free_bytes >= int(self.need_bytes*1.05):
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
        print(storage_root.childCount())
        for d in range(storage_root.childCount()):
            print(f"debug{d}")
            disk_item = storage_root.child(d)
            print(f"debug: disk_item={disk_item}")
            for p in range(disk_item.childCount()):
                item = disk_item.child(p)
                print(f"[Debug]check: {item}")
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
        for p in selected_storage:
            try:
                label=p.get('label')
                if label == 'advclone':
                    message=f"已选择备份分区:\n{backup_info}\n\nadvclone已存在，且空间大下为:\n{storage_info}\n\n备份所需空间大小: {self.shrink_space_mb} MB\n"
                else:
                    message=f"已选择备份分区:\n{backup_info}\n\n待压缩空间分区:\n{storage_info}\n\n压缩分区大小: {self.shrink_space_mb} MB"
            except Exception as e:
                print(f"执行出错: {e}")
                return {e}
        self.info_label.setText(message)
        self.progress_bar.setValue(0)

    def start_exec(self):
        print("======[Debug]page3: start_exec======")
        try:
            script_path = os.path.join(os.getcwd(), r"run_prepare_grub_env.exe")
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
            print(f"启动进程时出错: {e}")
            QMessageBox.critical(self, "错误", f"启动进程失败: {str(e)}")
            self.reset_buttons()

    def process_finished(self, exit_code, exit_status):
        """进程执行完成"""
        print(f"进程完成 - 退出代码: {exit_code}, 状态: {exit_status}")
        
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
    '''
    def start_exec(self):
        print("======[Debug]page3: start_exec======")
        try:
            script_path = os.path.join(os.getcwd(), r"run_prepare_grub_env.exe")
            if not os.path.exists(script_path):
                QMessageBox.warning(self, "错误", f"脚本文件不存在！\n路径: {script_path}")
                return


            # 禁用按钮
            self.btn_exec.setEnabled(False)
            self.btn_back.setEnabled(False)
            self.info_label.setText("执行中，请等待...")

            # 启动外部程序
            self.process = QProcess(self)
            #self.process.setProgram("notepad.exe")  # 这里替换为你的外部程序
            self.process.setProgram(script_path) 
            self.process.readyReadStandardOutput.connect(self.handle_stdout)
            self.process.readyReadStandardError.connect(self.handle_stderr)
            self.process.finished.connect(self.process_finished)
            self.process.errorOccurred.connect(lambda e: print("QProcess error:", e))
            self.process.start()

            # 模拟进度条
            self.progress_bar.setValue(10)
        except Exception as e:
            print(f"处理标准输出时出错: {e}")
    def process_finished(self):
        self.progress_bar.setValue(100)
        self.btn_exec.setEnabled(True)
        self.btn_back.setEnabled(True)
        self.info_label.setText("外部程序执行完成！")
        #QMessageBox.information(self, "完成", "外部程序执行完成！")
        reply = QMessageBox.information(self, "完成", "外部程序执行完成！点击 OK 退出程序。")
        #QApplication.quit()
    '''
    def handle_stdout(self):
        try:
            data = self.process.readAllStandardOutput()
            output = data.data().decode("utf-8", errors="ignore").strip()
            if output:
                self.output_text.append(output)
                print(f"STDOUT: {output}") 
            
            # 模拟进度条增加
            current_value = self.progress_bar.value()
            if current_value < 90:
                self.progress_bar.setValue(current_value + 5)
                
        except Exception as e:
            print(f"处理标准输出时出错: {e}")

    def handle_stderr(self):
        try:
            data = self.process.readAllStandardError()
            output = data.data().decode("utf-8", errors="ignore").strip()
            if output:
                self.output_text.append(f"<font color='red'>错误: {output}</font>")
                print(f"STDERR: {output}")
        except Exception as e:
            print(f"处理标准错误时出错: {e}")

    def handle_process_error(self, error):
        """处理进程错误"""
        error_msg = f"进程错误: {error}"
        print(error_msg)
        self.output_text.append(f"<font color='red'>{error_msg}</font>")
        self.reset_buttons()


        
    

# ---------- 主向导 ----------
class BackupWizard(QMainWindow):
    def __init__(self, all_disks):
        super().__init__()
        self.setWindowTitle("AdvClone 备份向导")
        self.resize(1000,600)
        self.settings = None
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
        self.compress_rate = self.getConfigValue('COMPRESSRATE','rate')

        self.page1 = PartitionSelectorPage(all_disks, self.go_to_confirm, self.compress_rate)
        self.page2 = ConfirmSelectionPage(self.go_to_select, self.go_to_exec, all_disks, self.compress_rate)
        self.page3 = ExecutionPage(self.go_to_confirm_back)

        self.stack.addWidget(self.page1)
        self.stack.addWidget(self.page2)
        self.stack.addWidget(self.page3)

        self.update_steps(0)
        
    def getConfigValue(self, section, key, default_value=None):
        """通用的配置读取方法"""
        if self.settings is None:
            self.settings = QSettings('config.ini', QSettings.IniFormat)
        
        # 构建完整的键路径
        full_key = f'{section}/{key}'
        return self.settings.value(full_key, default_value)

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
        current_time = datetime.now()
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

    DP = basic_disk_patitions()
    # 获取所有disk的分区信息
    #all_disks_data = DP.get_all_disks_partitons()
    # 仅获取系统C盘所在disk的磁盘信息
    all_disks_data = DP.get_system_disk_partitions()
    print("all_disks_data is:\n",all_disks_data)
    # 保存第一次获取磁盘信息
    # 获取当前时间
    current_time = datetime.now()
    #filename = f"backup_disk_details_1_{current_time.strftime('%Y%m%d_%H%M%S')}.json"
    filename = f"disk_details_1st.json"
    first_save_path = os.path.join(os.getcwd(),filename)
    with open(first_save_path,"w",encoding="utf-8") as f:
        json.dump(all_disks_data,f,ensure_ascii=False,indent=2)
    
    app = QApplication(sys.argv)
    win = BackupWizard(all_disks_data)
    win.show()
    sys.exit(app.exec_())
