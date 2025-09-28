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

st = subprocess.STARTUPINFO()
# st.dwFlags = subprocess.CREATE_NEW_CONSOLE | subprocess.STARTF_USESHOWWINDOW
st.dwFlags = subprocess.STARTF_USESHOWWINDOW
st.wShowWindow = subprocess.SW_HIDE
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

class dispart_partition_volume:
    def __init__(self):
        self.sys_disk_num = 0
        self.all_disk_info = []
        self.sys_disk_info = []
        
    def run_diskpart(self, cmds):
        with tempfile.NamedTemporaryFile('w', delete=False, suffix='.txt') as f:
            f.write(cmds)
            script_path = f.name
        command = f'cmd /c "chcp 437 >nul & diskpart /s {script_path}"'
        # 调用 diskpart 执行脚本
        try:
            #result = subprocess.run(['diskpart', '/s', script_path], capture_output=True, text=True)
            result = subprocess.run(command, capture_output=True, text=True, shell=True)  # 必须用 shell=True 才能执行 cmd /c
            return result.stdout
        except subprocess.TimeoutExpired:
            return "命令执行超时%s"%(cmds)
        except Exception as e:
            return f"执行错误: {str(e)}"
            
            
    def run_command(self, command):
        """通用的命令执行函数（被其他函数调用）"""        
        try:
            result = subprocess.run( command, shell=True, capture_output=True, text=True, timeout=30)
            return result.stdout if result.returncode == 0 else result.stderr
        except subprocess.TimeoutExpired:
            return "命令执行超时%s"%(command)
        except Exception as e:
            return f"执行错误: {str(e)}"
            
    def get_system_disk_id(self):
        try:
            # 调用 wmic 命令
            cmd = r'wmic logicaldisk where "DeviceID=\"C:\" " assoc /assocclass:Win32_LogicalDiskToPartition'
            result = subprocess.check_output(cmd, shell=True, text=True, encoding="utf-8", errors="ignore")

            # 从输出中提取 Disk #
            for line in result.splitlines():
                if "Disk #" in line:
                    disk_id = line.strip().split(",")[0].split("#")[-1]
                    self.sys_disk_num = disk_id
                    return disk_id
        except Exception as e:
            return {e}
    
    def _convert_to_bytes(self, size_str: str, unit: str) -> int:
        """将带单位的尺寸转换为字节"""
        size = int(size_str.replace(',', ''))
        unit_multipliers = {
            'B': 1, 'KB': 1024, 'MB': 1024**2, 
            'GB': 1024**3, 'TB': 1024**4
        }
        return size * unit_multipliers.get(unit.upper(), 1)
        
    def get_disk_numbers(self):
        try:
            result = subprocess.run(['wmic', 'diskdrive', 'get', 'index'], 
                                  capture_output=True, text=True, encoding='gbk')
            return sorted([int(line.strip()) for line in result.stdout.split('\n')[1:] if line.strip()])
        except:
            return []
            
    def get_hard_disk_numbers(self):
        """
        简单但有效的方法：通过介质类型筛选
        """
        try:
            # 只获取固定硬盘
            result = subprocess.run(
                ['wmic', 'diskdrive', 'where', 'MediaType="Fixed hard disk media"', 'get', 'index'],
                capture_output=True, 
                text=True, 
                encoding='gbk'
            )
            
            disk_numbers = []
            for line in result.stdout.split('\n')[1:]:
                if line.strip().isdigit():
                    disk_numbers.append(int(line.strip()))
            
            return sorted(disk_numbers)
            
        except:
            return []

        
    def get_disk_info(self, disk_id):
        """获取磁盘信息（调用run_command函数）"""
        print(f"正在获取磁盘 {disk_id} 信息...")

        # 列出所有分区
        script = "list disk\nselect disk %s\nlist partition\nexit\n"%(disk_id)
        output = self.run_diskpart(script)
        print(output)
        partitions = []
        for line in output.splitlines():
            #m = re.match(r"\s*Partition (\d+)\s+(\w+)\s+([\d,]+) (\w+)", line)#r"Partition\s+(\d+)\s+([A-Za-z ]+?)\s+\d"
            pattern = re.compile(r"Partition\s+(\d+)\s+([A-Za-z ]+?)\s+\d")
            m= pattern.findall(line)
            if m:
                partitions.append({'PartitionNumber': m[0][0], 'Type': m[0][1]})
  
        print("第一次获取partitions列表:", partitions)


        for part in partitions:
            p_num=part['PartitionNumber']
            print("PartitionNumber:", p_num)
            script="select disk %s\nselect partition %s\ndetail partition\nexit\n"%(disk_id, p_num)
            #print("script_detail:",script)
            output = self.run_diskpart(script)
            print("\n-----获取detail partition-----\n", output,"\n----\n")
            volume_line = ''
            for line in output.splitlines():
                volume_pattern = re.compile(
                    r"\s*\*?\s*"                    # 可选的前导*号和空白
                    r"Volume\s+(\d+)\s+"            # Volume 编号
                    r"([A-Z]?)\s+"                   # 盘符
                    r"(\w*)\s+"                     # 标签（可能为空）
                    r"(\w+)\s+"                     # 文件系统
                    r"(\w+)\s+"                     # 类型
                    r"([\d,]+)\s*"                  # 大小
                    r"([KMGTP]?B)\s+"               # 大小单位
                    r"(\w+)"                        # 状态
                    r"(?:\s+(\w+))?"                # 可选信息
                )
                match = re.match(volume_pattern, line)    
                if match:
                    volume_line=line
                    label = match.group(3).strip()
                    part['VolumeNumber']=int(match.group(1))
                    part['drive_letter']=match.group(2)
                    part['label']= label if label else None
                    part['file_system']= match.group(4)
                    part['type']= match.group(5)
                    part['size']= match.group(6)
                    part['size_unit']= match.group(7)
                    part['status']= match.group(8)
                    part['info']= match.group(9) if match.group(9) else None
                    part['size_bytes']= self._convert_to_bytes(match.group(6), match.group(7))
                    '''
                    print(
                        'volume_number', int(match.group(1)),
                        'drive_letter', match.group(2),
                        'label', label if label else None,
                        'file_system', match.group(4),
                        'type', match.group(5),
                        'size', match.group(6),
                        'size_unit', match.group(7),
                        'status', match.group(8),
                        'info', match.group(9) if match.group(9) else None,
                        'size_bytes', self._convert_to_bytes(match.group(6), match.group(7))
                    )
                    '''
                    continue
            print("获取offset in bytes......")
            for line in output.splitlines():
                offset_match = re.search(r"Offset in Bytes:\s*(\d+)", line)
                if offset_match:
                    value= offset_match.groups(1)
                    part['OffsetBytes'] = int(value[0])
                    print(part['OffsetBytes'])
                    continue
        
            if volume_line == '':
                print("no volume information")
            print(part)
            
        print("---debug---\n", partitions)

        # 按 OffsetBytes 排序，并增加排序序号
        sorted_partitions = sorted(partitions, key=lambda x: x['OffsetBytes'])
        # 增加排序序号
        for idx, part in enumerate(sorted_partitions, 1):
            part['SortedOffsetIndex'] = idx
        print("---按 OffsetBytes 排序后---\n",partitions)

        return partitions
        
    def update_partition_used_space(self, partitions):
        """
        为每个分区增加 'free_bytes' 和 'used_bytes'
        """
        print(f"[Debug]----- function: update_partition_used_space")
        for part in partitions:
            drive_letter = part.get('drive_letter')
            if drive_letter:
                try:
                    sectors_per_cluster, bytes_per_sector, free_clusters, total_clusters = win32file.GetDiskFreeSpace(f"{drive_letter}:\\")
                    total_bytes = total_clusters * sectors_per_cluster * bytes_per_sector
                    free_bytes = free_clusters * sectors_per_cluster * bytes_per_sector
                    print(f"[Debug]total_bytes={total_bytes},free_bytes={free_bytes} ")
                    used_bytes = total_bytes - free_bytes
                    print(f"[Debug]used_bytes=total_bytes({total_bytes})-free_bytes({free_bytes})={used_bytes} ")
                    part['free_bytes'] = free_bytes
                    part['used_bytes'] = used_bytes
                except Exception as e:
                    part['free_bytes'] = 0
                    part['used_bytes'] = 0
            else:
                part['free_bytes'] = 0
                part['used_bytes'] = 0
        return partitions
    #diskpart 获取的总大小不太准，重新获取更新
    def update_partition_total_size(self, disk_index, partitions):
        print(f"[Debug]----- function: update_partition_total_size -----")
        print(f"[Debug]WMI: get partition, disk_index={disk_index}")
        c = wmi.WMI()
        wmi_parts = []
        for disk in c.Win32_DiskDrive():
            print(f"[Debug]disk.Index={disk.Index}")
            #print(type(disk.Index), type(disk_index))
            if disk.Index == int(disk_index):
                wmi_parts = disk.associators("Win32_DiskDriveToDiskPartition")
                #print(f"[Debug]wmi_parts={wmi_parts}")
                break

        wmi_info = []
        for wp in wmi_parts:
            wmi_info.append({
                "DeviceID": wp.DeviceID,
                "Offset": int(wp.StartingOffset),
                "Size": int(wp.Size),
                "Type": wp.Type
            })
        #print("[Debug]wmi_info is:",wmi_info)
        print("[Debug]update size")
        for part in partitions:
            for wp in wmi_info:
                #print(f"[Debug]part['OffsetBytes']={part['OffsetBytes']} wp['Offset']={wp['Offset']}" )
                if wp["Offset"] == part["OffsetBytes"]:
                    print(f"[Debug]原来的size:{part["size_bytes"]}")
                    part["size_bytes"] = wp.get('Size')
                    print(f"[Debug]更新后的size:{part["size_bytes"]}")
        return partitions
        
    def get_all_disks_partitons(self):
        # 获取所有磁盘的分区详情
        disks = self.get_hard_disk_numbers()
        print("磁盘编号:", disks)
        for d in disks:
            partitions = self.get_disk_info(d)
            partitions = self.update_partition_used_space(partitions)  # 增加已用/剩余空间
            partitions = self.update_partition_total_size(d, partitions)
            disk_info = {
                "Disk": f"Disk {d}",
                "Partitions": partitions
            }
            self.all_disk_info.append(disk_info)
        return self.all_disk_info
    def get_system_disk_partitions(self):
        # 仅获取系统启动所在磁盘的分区详情
        print(f"\n[debug]self.sys_disk_num is: {self.sys_disk_num}\n")
        self.get_system_disk_id()
        print(f"\n[debug]self.sys_disk_num is: {self.sys_disk_num}\n")
        partitions = self.get_disk_info(self.sys_disk_num)
        partitions = self.update_partition_used_space(partitions)  # 增加已用/剩余空间
        partitions = self.update_partition_total_size(self.sys_disk_num, partitions)
        sys_disk_info = {
                "Disk": f"Disk {self.sys_disk_num}",
                "Partitions": partitions
        }
        self.sys_disk_info.append(sys_disk_info)
        return self.sys_disk_info
'''
# 使用示例
manager = dispart_partition_volume()
print("--------2-----------\n")
all_info=manager.get_all_disks_partitons()
print("--------3-----------\n")
print(all_info)
print("--------4-----------\n")
sys_disk=manager.get_system_disk_partitions()
print("--------5-----------\n")
print(sys_disk)
'''