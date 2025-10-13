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


# ===================== 日志处理 =====================
class Logger(object):
    def __init__(self, filename="log_get_partitions_volumes.txt"):
        self.terminal = sys.stdout
        self.log = open(filename, "a", encoding="utf-8")

    def write(self, message):
        self.terminal.write(message)   # 控制台显示
        self.log.write(message)        # 写入文件
        self.log.flush()               # 实时刷新

    def flush(self):
        pass  # print 会调用 flush，这里留空即可

sys.stdout = Logger("log_get_partitions_volumes.txt")
sys.stderr = sys.stdout  # 错误也记录


class basic_disk_patitions:
    def __init__(self):
        self.sys_disk_num = 0
        self.all_disk_info = []
        self.sys_disk_info = []
        
            
    def run_diskpart(self, cmds):
        print(f"[Info]--run_diskpart: {cmds}")
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
            print(result.stdout)
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
        ps_cmd = r"""Get-Disk | Where-Object {$_.IsBoot -eq $true} | Select Number, FriendlyName, Size, PartitionStyle, IsBoot, IsSystem|ConvertTo-Json -Compress"""
        try:
            output=self.run_powershell(ps_cmd)
            print(type(output),output)
            data_json = output.strip()
            if not data_json:
                print(f"[Error]Get-WmiObject -Class Win32_LogicalDiskToPartition获取为空")
                return []
            try:
                data = json.loads(data_json)
                return data
            except json.JSONDecodeError as je:
                print(f"JSON解析错误: {je}")
                return []
        except Exception as e:
            print(f"执行出错: {e}")
            return {e}
    def get_disk_partitions_basic_x(self, disk_id):
        ps_cmd = f"""Get-Partition -DiskNumber {disk_id} | Select-Object PartitionNumber, DriveLetter, Offset, Size, Guid, Type | ConvertTo-Json -Compress"""
        try:
            output=self.run_powershell(ps_cmd)
            print(type(output),output)
            data_json = output.strip()
            if not data_json:
                print(f"[Error]Get-WmiObject -Class Win32_LogicalDiskToPartition获取为空")
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
                print(f"JSON解析错误: {je}")
                return []
        except Exception as e:
            print(f"get_disk_partitions_basic执行出错: {e}")
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
        Type = $partition.Type
        Offset = $partition.Offset
        IsBoot = $partition.IsBoot
        label = if ($volume) { $volume.FileSystemLabel } else { "N/A" }
        FileSystem = if ($volume) { $volume.FileSystem } else { "N/A" }
        HealthStatus = if ($volume) { $volume.HealthStatus } else { "N/A" }
    }
} | ConvertTo-Json -Compress"""%disk_id
        try:
            output=self.run_powershell(ps_script)
            print(type(output),output)
            data_json = output.strip()
            if not data_json:
                print(f"[Error]获取json异常")
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
                print(f"JSON解析错误: {je}")
                return []
        except Exception as e:
            print(f"get_disk_partitions_basic执行出错: {e}")
            return {e}

    def get_system_disk_partitions(self):
        disk_infos={}
        disk=self.get_boot_disk()
        disk_num=disk.get('Number')
        paritons=self.get_disk_partitions_basic(disk_num)
        disk['Partitions']=paritons
        disk_infos[disk_num]=disk
        print(disk_infos)
        return disk_infos
# 使用示例
'''
manager = basic_disk_patitions()

info = manager.get_system_disk_partitions()
print("---1---\n",info)
'''