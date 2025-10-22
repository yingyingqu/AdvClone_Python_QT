# -*- coding:utf-8 -*-
import ctypes
import sys
import subprocess
import os
import logging
import chardet
import win32file,win32api,wmi
import time
import shutil
import tempfile
import re
import json
import shlex
from datetime import datetime
# 日志名称
if not os.path.exists('log'):
    os.makedirs('log')
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_file = f"log\\log_get_partitions_basic_{timestamp}.txt"
'''
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


class basic_disk_patitions:
    def __init__(self):
        self.sys_disk_num = 0
        self.all_disk_info = []
        self.sys_disk_info = []
        
            
    def run_diskpart(self, cmds):
        logmsg=f"[Info]--run_diskpart: {cmds}"
        #print(logmsg)
        logger.debug(logmsg)
        if not cmds.strip():
            return ""

        with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8", suffix=".txt") as f:
            f.write(cmds)
            script_path = f.name

        try:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW  # 隐藏窗口

            result = subprocess.run(
                f'chcp 437 >nul & diskpart /s "{script_path}"',
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                startupinfo=startupinfo,
                shell=True,
                encoding="cp437",
                check=True  # 会抛出 CalledProcessError，如果不是管理员会抛
            )
            #print(result.stdout)
            logger.info(result.stdout)
            return result.stdout
        finally:
            os.remove(script_path)
  
       
       
    def run_powershell(self, cmd: str) -> str:
        with tempfile.NamedTemporaryFile("r+", delete=False, encoding="utf-8", suffix=".txt") as output_file:
            output_file_path = output_file.name

        try:        
            subprocess.run(
                            ["powershell", "-NoProfile", "-Command", f"{cmd} | Out-File -Encoding utf8 {output_file_path}"],
                            startupinfo=subprocess.STARTUPINFO(dwFlags=subprocess.STARTF_USESHOWWINDOW, wShowWindow=0),
                            check=True
                            )
            
            with open(output_file_path, "r", encoding="utf-8-sig") as f:
                return f.read()
        finally:
            os.remove(output_file_path)

    
    
    def _convert_to_bytes(self, size_str: str, unit: str) -> int:
        """将带单位的尺寸转换为字节"""
        size = int(size_str.replace(',', ''))
        unit_multipliers = {
            'B': 1, 'KB': 1024, 'MB': 1024**2, 
            'GB': 1024**3, 'TB': 1024**4
        }
        return size * unit_multipliers.get(unit.upper(), 1)
        
    def get_boot_disk(self):
        ps_cmd = r"""Get-Disk | Where-Object {$_.IsBoot -eq $true} | Select Number, FriendlyName, Size, AllocatedSize, PartitionStyle, IsBoot, IsSystem|ConvertTo-Json -Compress"""
        try:
            output=self.run_powershell(ps_cmd)
            #print(type(output),output)
            logger.debug(f"{type(output)}, {output}")
            data_json = output.strip()
            if not data_json:
                #print(f"[Error]Get-Disk获取启动硬盘为空")
                infomsg=f"[Error]Get-Disk get boot disk is none"
                logger.error(infomsg)
                return []
            try:
                data = json.loads(data_json)
                return data
            except json.JSONDecodeError as je:
                #print(f"JSON解析错误: {je}")
                infomsg=f"JSON Parsing Error: {je}"
                logger.error(infomsg)
                return []
        except Exception as e:
            #print(f"执行出错: {e}")
            infomsg=f"Run Error: {e}"
            logger.error(infomsg)
            return {e}
    def get_disk_partitions_basic_x(self, disk_id):
        ps_cmd = f"""Get-Partition -DiskNumber {disk_id} | Select-Object PartitionNumber, DriveLetter, Offset, Size, Guid, Type | ConvertTo-Json -Compress"""
        try:
            output=self.run_powershell(ps_cmd)
            #print(type(output),output)
            logger.debug(f"{type(output)}, {output}")
            data_json = output.strip()
            if not data_json:
                #print(f"[Error]Get-Partition获取磁盘分区信息为空")
                infomsg=f"[Error]Get-Partition get is none"
                logger.error(infomsg)
                return []
            try:
                data = json.loads(data_json)
                # 按 OffsetBytes 排序，并增加排序序号
                sorted_partitions = sorted(data, key=lambda x: x['Offset'])
                # 增加排序序号
                for idx, part in enumerate(sorted_partitions, 1):
                    part['SortedOffsetIndex'] = idx
                return sorted_partitions
            except json.JSONDecodeError as je:
                #print(f"JSON解析错误: {je}")
                infomsg=f"JSON Parsing Error: {je}"
                logger.error(infomsg)
                return []
        except Exception as e:
            #print(f"get_disk_partitions_basic执行出错: {e}")
            infomsg=f"get_disk_partitions_basic Run Error: {e}"
            logger.error(infomsg)
            return {e}

    def get_disk_partitions_basic(self, disk_id):
        ps_script=r"""Get-Partition -DiskNumber %s | ForEach-Object {
    $partition = $_
    $volume = if ($partition.DriveLetter) {
        Get-Volume -DriveLetter $partition.DriveLetter -ErrorAction SilentlyContinue
    } else {
        # 对于没有盘符的分区，通过其他方式获取卷信息
        Get-Volume | Where-Object {
            $_.UniqueId -like "*$($partition.Guid)*" -or 
            $_.Path -like "*$($partition.Guid)*"
        } | Select-Object -First 1
    }
    
    [PSCustomObject]@{
        DiskNumber = $partition.DiskNumber
        PartitionNumber = $partition.PartitionNumber
        drive_letter = if ($partition.DriveLetter) { $partition.DriveLetter } else { "" }
        size_bytes = $partition.Size 
        free_bytes = $volume.SizeRemaining
        used_bytes = $partition.Size - $volume.SizeRemaining
        Type = $partition.Type
        OffsetBytes = $partition.Offset
        IsBoot = $partition.IsBoot
        label = if ($volume) { $volume.FileSystemLabel } else { "N/A" }
        FileSystem = if ($volume) { $volume.FileSystem } else { "N/A" }
        HealthStatus = if ($volume) { $volume.HealthStatus } else { "N/A" }
    }
} | ConvertTo-Json -Compress"""%disk_id
        try:
            output=self.run_powershell(ps_script)
            #print(type(output),output)
            logger.debug(f"{type(output)}, {output}")
            data_json = output.strip()
            if not data_json:
                #print(f"[Error]获取json异常")
                infomsg=f"[Error]Get-get_disk_partitions_basic get is none"
                logger.error(infomsg)
                return []
            try:
                data = json.loads(data_json)
                # 按 OffsetBytes 排序，并增加排序序号
                sorted_partitions = sorted(data, key=lambda x: x['OffsetBytes'])
                # 增加排序序号
                for idx, part in enumerate(sorted_partitions, 1):
                    part['SortedOffsetIndex'] = idx
                return sorted_partitions
            except json.JSONDecodeError as je:
                #print(f"JSON解析错误: {je}")
                infomsg=f"JSON Parsing Error: {je}"
                logger.error(infomsg)
                return []
        except Exception as e:
            #print(f"get_disk_partitions_basic执行出错: {e}")
            infomsg=f"get_disk_partitions_basic Run Error: {e}"
            logger.error(infomsg)
            return {e}

    #因为Get-Partition 使用的是 Storage Management API (MSFT_Partition)。Windows 在这个 API 层面会过滤掉受保护的分区类型（比如 EFI、MSR、Recovery），导致Get-Partition和Get-Volume都无法获取系统分区的盘符，即使已经挂载分配了盘符
    #这里是补充system分区的盘符的！
    def get_system_letter(self, disk_id):
        #print(f"[Func]get_system_letter: disk_id={disk_id}------>>>>>>")
        logmsg=f"[Func]get_system_letter: disk_id={disk_id}------>>>>>>"
        logger.debug(logmsg)
        ps_script=r"""Get-CimInstance Win32_DiskPartition | ForEach-Object {
         $assoc = Get-CimInstance -Query "ASSOCIATORS OF {Win32_DiskPartition.DeviceID='$($_.DeviceID)'} WHERE AssocClass=Win32_LogicalDiskToPartition"
         [PSCustomObject]@{
             DiskIndex = $_.DiskIndex
             PartitionIndex = $_.Index
             Type = $_.Type
             DriveLetter = $assoc.DeviceID
             SizeGB = [math]::Round($_.Size / 1GB, 2)
         }
     }| ConvertTo-Json -Compress"""
        try:
            output=self.run_powershell(ps_script)
            #print(type(output),output)
            logger.debug(f"{type(output)}, {output}")
            data_json = output.strip()
            if not data_json:
                print(f"[Error]获取json异常")
                return []
            try:
                data = json.loads(data_json)
                for d in data:
                    logmsg=f"{d},type(d.get('DiskIndex'))={type(d.get('DiskIndex'))}, type(disk_id)={type(disk_id)}, d.get('Type')={d.get('Type')}"
                    #print(logmsg)
                    logger.debug(logmsg)
                    if str(d.get('DiskIndex'))==str(disk_id) and d.get('Type')=='GPT: System':
                        #print(f"[Debug]返回结果：{d.get('DriveLetter')}")
                        if d.get('DriveLetter') != None:
                            return d.get('DriveLetter').replace(":", "")
                        else:
                            return None
            except json.JSONDecodeError as je:
                #print(f"JSON解析错误: {je}")
                infomsg=f"JSON Parsing Error: {je}"
                logger.error(infomsg)
                return []
        except Exception as e:
            #print(f"get_system_letter执行出错: {e}")
            infomsg=f"get_system_letter Run Error: {e}"
            logger.error(infomsg)
            return {e}
        
    def get_system_disk_partitions(self):
        disk_infos={}
        disk=self.get_boot_disk()
        disk_num=str(disk.get('Number'))
        #print(f"[Debug]disk_num={disk_num}")
        logmsg=f"[Debug]disk_num={disk_num}"
        logger.debug(logmsg)
        paritons=self.get_disk_partitions_basic(disk_num)
        sys_ltr=self.get_system_letter(disk_num)
        
        #print(f"[Debug]获取sys_ltr={sys_ltr}")
        logmsg=f"[Debug]get sys_ltr={sys_ltr}"
        logger.debug(logmsg)
        
        #print(f"[Debug](0)paritons={paritons}")
        logmsg=f"[Debug](0)paritons={paritons}"
        logger.debug(logmsg)
        
        for i in range(len(paritons)):
            p=paritons[i]
            if p.get('Type')=='System':
                #print(f"[Debug]找到System了")
                paritons[i]['drive_letter']=sys_ltr
        #print(f"[Debug](1)paritons={paritons}")
        logmsg=f"[Debug](1)paritons={paritons}"
        logger.debug(logmsg)
        disk['Partitions']=paritons
        disk_infos[disk_num]=disk
        #print(disk_infos)
        return disk_infos
# 使用示例

manager = basic_disk_patitions()
#boot=manager.get_boot_disk()
#print(boot)


ltr = manager.get_system_letter(1)
print(ltr)

info = manager.get_system_disk_partitions()

print("---1---\n",info)
