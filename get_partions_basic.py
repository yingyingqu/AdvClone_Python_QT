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


class dispart_partition_volume:
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
            
    def get_disk_partition_info(self):
        print(f"\n[Info]--- get_disk_partition_info by powershell ---\n")
        """
        获取所有逻辑分区对应的物理磁盘编号及相关信息，没有diskpart volume的编号用于压缩
        返回一个列表，每项包含：
        - DiskNumber
        - PartitionNumber
        - DriveLetter
        - StartingAddress (Bytes)
        - EndingAddress (Bytes)
        """
        ps_cmd = r"""Get-WmiObject -Class Win32_LogicalDiskToPartition |Select Antecedent, Dependent, StartingAddress, EndingAddress |ConvertTo-Json -Compress"""
        try:
            output=self.run_powershell(ps_cmd)
            print(type(output),output)
            data_json = output.strip()
            if not data_json:
                print(f"[Error]Get-WmiObject -Class Win32_LogicalDiskToPartition获取为空")
                return []
            try:
                data = json.loads(data_json)
            except json.JSONDecodeError as je:
                print(f"JSON解析错误: {je}")
                return []
            partitions = []
            
            for item in data:
                antecedent = item.get('Antecedent', '')
                dependent = item.get('Dependent', '')
                starting_address = int(item.get('StartingAddress', 0))
                EndingAddress = int(item.get('EndingAddress', 0))

                # 解析 Disk # 和 Partition #
                disk_match = re.search(r'Disk #(\d+)', antecedent)
                part_match = re.search(r'Partition #(\d+)', antecedent)
                drive_letter_match = re.search(r'DeviceID="?([A-Z]):"?', dependent)

                disk_number = int(disk_match.group(1)) if disk_match else None
                partition_number = int(part_match.group(1)) if part_match else None
                drive_letter = drive_letter_match.group(1) + ':' if drive_letter_match else None

                partitions.append({
                    "DiskNumber": disk_number,
                    "PartitionNumber": partition_number,
                    "DriveLetter": drive_letter,
                    "StartingAddress": starting_address,
                    "EndingAddress": EndingAddress
                })
                
            # 构造树状结构
            disk_partitions = {}
            for p in partitions:
                disk_num = p["DiskNumber"]
                if disk_num not in disk_partitions:
                    disk_partitions[disk_num] = {"DiskNumber": disk_num, "Partitions": []}
                disk_partitions[disk_num]["Partitions"].append({
                    "PartitionNumber": p["PartitionNumber"],
                    "DriveLetter": p["DriveLetter"],
                    "StartingAddress": p["StartingAddress"],
                    "EndingAddress": p["EndingAddress"],
                    "Size": p["EndingAddress"]-p["StartingAddress"]
                })

            return disk_partitions
        except Exception as e:
            print(f"执行出错: {e}")
            return {e}    
    
    
    def _convert_to_bytes(self, size_str: str, unit: str) -> int:
        """将带单位的尺寸转换为字节"""
        size = int(size_str.replace(',', ''))
        unit_multipliers = {
            'B': 1, 'KB': 1024, 'MB': 1024**2, 
            'GB': 1024**3, 'TB': 1024**4
        }
        return size * unit_multipliers.get(unit.upper(), 1)
        
    def get_all_disks(self):
        print(f"[Info]--- get_all_disks ---")
        ps_cmd="""Get-CimInstance Win32_DiskDrive | Select-Object Index, Model |  ConvertTo-Json -Compress"""
        #或者：Get-PhysicalDisk | Select-Object FriendlyName, SerialNumber, Size, MediaType, DeviceId
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
            print(f"get_all_disks执行出错: {e}")
            return {e}
    def get_hard_disks(self):
        print("[Info]---get_hard_disks---")
        ps_cmd="""Get-CimInstance Win32_DiskDrive | Where-Object MediaType -eq "Fixed hard disk media" | Select-Object Index, Model, SerialNumber |  ConvertTo-Json -Compress"""
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
            print(f"get_hard_disks执行出错: {e}")
            return {e}

    def get_disks_type_info(self):
        """ 从 diskpart 的 list disk 输出中解析磁盘编号、大小、是否为动态磁盘 """
        #正则匹配*位置来判断是否是动态磁盘判断不准，只能精确位置来匹配
        script = "list disk\nexit\n"
        output = self.run_diskpart(script)
        disks = {} 
        lines = output.splitlines() 
        parsing = False
        # 找到包含 "Disk" 的行 
        for line in lines:
            
            if re.match(r"\s*Disk\s+###", line):
                parsing = True
                continue
            if parsing and line.strip().startswith("Disk"):
                # 按固定列宽解析，而不是简单split
                # Disk ###  Status         Size     Free     Dyn  Gpt
                disk_number   = line[6:8].strip()       # Disk #
                status     = line[9:22].strip()           # Status
                size       = line[22:33].strip()          # Size
                free       = line[33:44].strip()          # Free
                dyn_flag   = line[44:48].strip() == "*"   # Dyn 列
                gpt_flag   = line[48:52].strip() == "*"   # Gpt 列
                detial_info= {
                    "Status": status,
                    "Size": size,
                    "Free": free,
                    "IsDynamic": dyn_flag,
                    "IsGPT": gpt_flag
                    }
                if dyn_flag == True:
                    disks[f'{disk_number}'] = {
                        "Disk": f"Disk {disk_number}",
                        "DiskNumber": disk_number,
                        "DiskType": "Dynamic",
                        "Detials": detial_info
                    }
                else:
                    disks[f'{disk_number}'] = {
                        "Disk": f"Disk {disk_number}",
                        "DiskNumber": disk_number,
                        "DiskType": "Basic",
                        "Detials": detial_info
                    }
        print(disks)
        return disks
        
    #通过diskpart命令获取disk下面的volume对应关系
    #针对动态磁盘，目前只有这种方式可以
    def get_volumes_diskpart(self):
        print("[Info]---get_volumes_diskpart---")
        volumes = []
        #通过diskpart命令获取所有volume编号和盘符
        output = self.run_diskpart("list volume\nexit\n")
        lines = output.splitlines()
        header_index = None

        for line in lines:
            line = line.rstrip()
            
            # 只处理Volume数据行
            if line.startswith('  Volume ') and not line.startswith('  Volume ###'):
                # 精确字符位置提取
                # 基于: Volume 0     E   Backup 11      NTFS   Simple       221 GB  Healthy    Pagefile
                volume_number = line[8:11].strip()    # 位置 8-10
                drive_letter = line[15:16].strip()    # 位置 15
                label = line[18:29].strip()           # 位置 18-28
                file_system = line[31:36].strip()     # 位置 31-35
                vol_type = line[38:48].strip()        # 位置 38-47
                size = line[50:58].strip()            # 位置 50-57
                status = line[60:68].strip()          # 位置 60-67
                info = line[70:].strip()              # 位置 70到最后
                
                volumes.append({
                    'volume_number': volume_number,
                    'DriveLetter': drive_letter,
                    'label': label,
                    'file_system': file_system,
                    'type': vol_type,
                    'size': size,
                    'status': status,
                    'info': info
                })

        for vol in volumes:
            script = f"select volume {vol['volume_number']}\ndetail volume\nexit\n"
            detail_output = self.run_diskpart(script)
            # 提取 Disk ###
            disks = re.findall(r"Disk\s+(\d+)", detail_output)
            #特殊情况，动态磁盘有些volume跨磁盘了，暂时不考虑这种特殊情况
            disk_num = int(disks[0])
            vol['DiskNumber'] = disk_num

        print(f"(1)volumes is:\n{volumes}")
        return volumes
        
    def get_volumes_ps(self):
        # 调用 PowerShell，输出 JSON
        print("[Info]---get_volumes_ps---")
        ps_cmd="""Get-Volume | Select-Object DriveLetter, FileSystemLabel, FileSystem, Size, SizeRemaining, HealthStatus, DriveType, UniqueId | ConvertTo-Json"""
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
            print(f"get_volumes_ps执行出错: {e}")
            return {e}

    
    #获取基础磁盘（Basic）的分区详情
    #针对basic类型的磁盘，重新获取的原因是，有些分区是reserved分区，powershell下使用Get-Volume也显示不全，但是Get-Partition -DiskNumber 0可以显示完整，（diskpart也可以）
    def get_disk_partitions_basic(self, disk_id):
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

    #获取动态磁盘（Dynamic Disk）的分区详情
    def get_disk_partitions_dyn(self, disk_id):
        pass
    
    def meger_disk_info(self):
        hard_disks = self.get_hard_disks()
        # 构造树状结构
        merger_disks_partitions = {}
        for d in hard_disks:
            disk_num = str(d["Index"])
            if disk_num not in merger_disks_partitions:
                merger_disks_partitions[disk_num] = {"DiskNumber": disk_num, "DiskInfo": [], "Volumes":[]}
            merger_disks_partitions[disk_num]["DiskInfo"]=d
        print(f"[Debug](1)merger_disks_partitions is:\n{merger_disks_partitions}")
        
        disk_type_info = self.get_disks_type_info()
        print(disk_type_info)
        for t in disk_type_info:
            print("t:", type(t), t)
            type_disk = disk_type_info[t]["DiskType"]
            print("type:",type_disk)
            merger_disks_partitions[t]["DiskType"]=type_disk
        print(f"[Debug](2)merger_disks_partitions (add disk type)is:\n{merger_disks_partitions}")


        volumes = self.get_volumes_diskpart()
        print(f"[Debug]get_volumes_diskpart volumes is:\n{volumes}")
        for vid in range(len(volumes)):
            print(f"[Debug]{type(vid)} vid={vid}")
            v=volumes[vid]
            num = str(v['DiskNumber'])
            print(f"xxxx\n{type(num)}, {num}\n")
            merger_disks_partitions[num]['Volumes'].append(v)
        print(f"[Debug](3)merger_disks_partitions is:\n{merger_disks_partitions}")



        for m in merger_disks_partitions:
            type_disk=merger_disks_partitions[m]["DiskType"]
            # 对get_volumes_diskpart没有获取到的分区进行补充，比如reserved等分区
            if type_disk == "Basic":
                basic_partitons = self.get_disk_partitions_basic(m)
                print(f"[Debug]get_disk_partitions_basic :{basic_partitons}")
                for bp in basic_partitons:
                    bp_letter = bp.get("DriveLetter")
                    bp_info = bp.get("Type")
                    print(f"[Debug]bp.get('DriveLetter')={bp.get('DriveLetter')}, bp.get('Type')={bp_info}")
                    for mp_index in range(len(merger_disks_partitions[m]["Volumes"])):
                        mp=merger_disks_partitions[m]["Volumes"][mp_index]
                        print(f"---[Debug]mp.get('DriveLetter')={mp.get('DriveLetter')}, mp.get('info')={mp.get('info')}")
                        if mp.get("DriveLetter"):
                            if mp.get("DriveLetter")==bp_letter:
                                integrated = mp.copy()     # 以卷数据为基础
                                integrated.update(bp)  # 用分区数据更新
                                merger_disks_partitions[m]["Volumes"][mp_index]=integrated
                                break
                        else:
                            if mp.get("info")==bp_info:
                                integrated = mp.copy()  # 以卷数据为基础
                                integrated.update(bp)  # 用分区数据更新
                                merger_disks_partitions[m]["Volumes"][mp_index] = integrated
                                break
                            else:
                                merger_disks_partitions[m]["Volumes"].append(bp)
                print(f"[Debug](4)补充diskpart list volume没有列举获取到的分区\n{merger_disks_partitions}")
            if type_disk == "Dynamic":
                # 补充动态磁盘各个分区的偏移地址和大小size信息
                tmp_info = self.get_disk_partition_info()
                print(f"[Debug]get_disk_partition_info() :{tmp_info}")
                pass






        print(f"[Debug](5)补充动态磁盘各个分区的偏移地址\n")
        '''
        volumes = self.get_volumes_ps()
        print(volumes)
        '''
    '''   
    def get_all_disks_partitons(self):
        # 获取所有磁盘的分区详情
        disks_nums = self.get_hard_disk_numbers()
        disks_details = self.get_disks_info()
        print("磁盘编号:", disks_nums)
        for d in disks_nums:
            print(f"---disk {d}")
            #获取磁盘类型：动态或者基础
            disk_type= disks_details[f'{d}'].get('DiskType')
            if disk_type == 'Basic':
                print(f"[Debug]disk {d} is Basic")
                partitions = self.get_disk_partitions_basic(d)
                partitions = self.update_partition_used_space(partitions)  # 增加已用/剩余空间
                #partitions = self.update_partition_total_size(d, partitions)
            if disk_type == 'Dynamic':
                print(f"[Debug]disk {d} is Dynamic")
                partitions = self.get_disk_partitions_dyn(d)
                partitions = self.update_partition_used_space(partitions)  # 增加已用/剩余空间
                #partitions = self.update_partition_total_size(d, partitions)
            disk_info = {
                "Disk": f"Disk {d}",
                "Disk_ID": d,
                "Disk_type": disk_type,
                "Partitions": partitions
            }
            self.all_disk_info.append(disk_info)
        return self.all_disk_info
    def get_system_disk_partitions(self):
        # 仅获取系统启动所在磁盘的分区详情
        print(f"\n[debug]self.sys_disk_num is: {self.sys_disk_num}\n")
        self.get_system_disk_id()
        print(f"\n[debug]self.sys_disk_num is: {self.sys_disk_num}\n")
        partitions = self.get_disk_partitions_basic(self.sys_disk_num)
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
'''
info = manager.get_disk_partition_info()
print("---1--\n",info)
info = manager.get_hard_disks()
print("---2--\n",info)
info = manager.get_disks_type_info()
print("---3--\n",info)

info = manager.get_disk_partitions_basic(0)
print("---4--\n",info)
'''


info = manager.meger_disk_info()
print("---6--\n",info)