import ctypes
import string
import subprocess
import json
import os
import re,sys
import shutil
import tempfile
from datetime import datetime
import time
import locale

from get_partitions_basic import basic_disk_patitions

import logging
import sys
# 日志名称
if not os.path.exists('log'):
    os.makedirs('log')
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_file = f"log\\log_run_prepare_grub_env_{timestamp}.txt"

# 自定义 Logger
logger = logging.getLogger("MyLogger")
logger.setLevel(logging.DEBUG)  # 捕获所有级别

# 1️⃣ 文件输出（保存所有日志）
file_handler = logging.FileHandler(log_file, encoding="utf-8")
file_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)
'''
# 2️⃣ 控制台输出（只输出部分信息）
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)  # 只显示 INFO 及以上
console_formatter = logging.Formatter("[%(levelname)s] %(message)s")
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)
'''

# 3️⃣ 替换 print，使 print 也输出到 logger（可选）
class PrintLogger:
    def write(self, message):
        if message.strip():  # 去掉空行
            logger.info(message.strip())
    def flush(self):
        pass

# 可选：把 print 重定向到 logger
# sys.stdout = PrintLogger()

# 使用示例
#logger.debug("这是调试信息（仅文件）")
#logger.info("这是普通信息（文件+控制台）")
#logger.warning("这是警告信息（文件+控制台）")
#print("这是 print 输出（会被 logger 捕获，如果重定向了）")

def run_diskpart(cmds):
    #print(f"[Info]--run_diskpart: {cmds}")
    logger.debug(f"[Info]--run_diskpart: {cmds}")
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
        logger.debug(result.stdout)
        return result.stdout
    finally:
        os.remove(script_path)
def run_powershell(cmd: str) -> str:
    #print(f"[Func]run_powershell: {cmd}")
    logger.debug(f"[Func]run_powershell: {cmd}")
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



def runCmd(cmd: str, timeout: int = 60) -> str:
    """
    执行命令，不弹出窗口，强制英文输出，兼容中文系统。
    支持 Windows 系统命令英文输出。
    """
    logger.debug(f"---[runCmd]{cmd}----")
    env = os.environ.copy()

    # 强制英文输出
    env["LANG"] = "en_US.UTF-8"
    env["LC_ALL"] = "en_US.UTF-8"

    # 设置编码为 utf-8
    encoding = "utf-8"

    # Windows cmd 隐藏窗口
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

    # 在 Windows 上强制英文，使用 chcp 65001 临时切换为 UTF-8
    if os.name == "nt":
        cmd = f"chcp 65001>nul && {cmd}"

    try:
        result = subprocess.run(
            cmd,
            shell=True,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            text=True,
            encoding=encoding,
            errors="replace",
            env=env,
            startupinfo=startupinfo
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        logger.error(f"[ERROR] command: {cmd}\noutput:\n{e.stdout}")
        raise
    except subprocess.TimeoutExpired:
        logger.warning(f"[TIMEOUT] command timeout: {cmd}")
        raise


def runCmd_x(cmd: str, timeout: int = 60) -> str:
    """执行命令，不弹出窗口，兼容中文系统输出，中文系统输出含中文，不适合匹配"""
    env = os.environ.copy()
    
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW  # 隐藏窗口

    # 中文系统默认编码
    encoding = locale.getpreferredencoding()

    try:
        result = subprocess.run(
            cmd,
            shell=True,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            text=True,
            encoding=encoding,
            errors="replace",
            env=env,
            startupinfo=startupinfo
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        #print(f"[ERROR] 命令失败: {cmd}\n输出:\n{e.stdout}")
        logger.error(f"[ERROR] command: {cmd}\noutput:\n{e.stdout}")
        raise
    except subprocess.TimeoutExpired:
        #print(f"[TIMEOUT] 命令超时: {cmd}")
        logger.warning(f"[TIMEOUT] command timeout: {cmd}")
        raise
        
def get_disk_type(disk_id):
    ps_cmd=f"(Get-PhysicalDisk | Where-Object {{$_.DeviceId -eq {'%s'}}}).BusType"%(disk_id)
    try:
        # 调用 PowerShell，获取 BusType
        cmd = [
            "powershell",
            "-Command",
            f"(Get-PhysicalDisk | Where-Object {{$_.DeviceId -eq {'%s'}}}).BusType"%(disk_id)
        ]
        #result = subprocess.check_output(cmd, text=True).strip()
        result = run_powershell(ps_cmd)
        #print(result)
        logger.debug(result)
        if result == "NVMe":
            sataType = 'nvme0n1p'
        else:
            sataType = "sda"
        loginfo = f"\nget disk type:{sataType}\n"

    except Exception as e:
        loginfo = f"Get disk type failed: {e}"  
    #print(loginfo)
    logger.debug(loginfo)
    return sataType        
        
def get_available_drive_letter(exclude=('A','B','C')):
    used = []
    bitmask = ctypes.cdll.kernel32.GetLogicalDrives()
    for i in range(26):
        if bitmask & (1 << i):
            used.append(chr(ord('A') + i))
    all_letters = set(string.ascii_uppercase) - set(exclude)
    free_letters = sorted(list(all_letters - set(used)))
    return free_letters[0] if free_letters else None
        
def shrink_and_create_with_diskpart(disk_number, partition_number, shrink_size_mb, 
                                  new_drive_letter=None, new_label=None):
    logmsg=f"[Func]shrink_and_create_with_diskpart: disk_number={disk_number},partition_number={partition_number}, shrink_size_mb={shrink_size_mb}, new_drive_letter={new_drive_letter}, new_label={new_label}----->>>>>>"
    #print(logmsg)  
    logger.debug(logmsg)    
    """
    使用 diskpart 创建分区，完全避免提示
    """
    
    if not new_drive_letter:
        new_drive_letter = get_available_drive_letter()
    if not new_label:
        new_label = 'advclone'
    
    # 创建 diskpart 脚本
    diskpart_script = f"""
select disk {disk_number}
select partition {partition_number}
shrink desired={shrink_size_mb}
create partition primary
assign letter={new_drive_letter}
format fs=ntfs label="{new_label}" quick
exit
"""
    try:
        run_diskpart(diskpart_script)
    except Exception as e:
        infomsg=f"ERROR:\n{e}"
        logger.error(infomsg)
        #print(f"执行出错: {e}")
        return {e}

def format_unAllocated_with_diskpart_0(disk_number, new_drive_letter=None, new_label=None):
    logmsg=f"[Func]format_unAllocated_with_diskpart: disk_number={disk_number},new_drive_letter={new_drive_letter}, new_label={new_label}----->>>>>>"
    #print(logmsg)  
    logger.debug(logmsg)  
    logger.info(f"[Debug]start: format_unAllocated_with_diskpart--->>>")    
    """
    使用 diskpart 创建分区，完全避免提示
    """
    
    if not new_drive_letter:
        new_drive_letter = get_available_drive_letter()
    if not new_label:
        new_label = 'advclone'
    
    # 创建 diskpart 脚本
    diskpart_script = f"""
select disk {disk_number}
create partition primary
assign letter={new_drive_letter}
format fs=ntfs label="{new_label}" quick
exit
"""
    try:
        time.sleep(10)
        logger.info(f"[Debug]start diskpart--->>>>")
        run_diskpart(diskpart_script)
    except Exception as e:
        infomsg=f"ERROR:\n{e}"
        logger.error(infomsg)
        #print(f"执行出错: {e}")
        return {e}

def format_unAllocated_with_diskpart(disk_number, new_label=None):
    logmsg=f"[Func]format_unAllocated_with_diskpart: disk_number={disk_number},new_label={new_label}----->>>>>>"
    #print(logmsg)  
    logger.debug(logmsg)     
    """
    使用 diskpart 创建分区，完全避免提示
    """
    if not new_label:
        new_label = 'advclone'
    
    # 创建 diskpart 脚本
    diskpart_script = f"""
select disk {disk_number}
create partition primary
format fs=ntfs label="{new_label}" quick
exit
"""
    try:
        run_diskpart(diskpart_script)
    except Exception as e:
        infomsg=f"ERROR:\n{e}"
        logger.error(infomsg)
        #print(f"执行出错: {e}")
        return {e}


def remove_drive_letter(disk_number, partition_number, drive_letter):
    logmsg=f"[Func]remove_drive_letter: disk_number={disk_number},partition_number={partition_number}, drive_letter={drive_letter}----->>>>>>"
    #print(logmsg)
    logger.debug(logmsg)   
    diskpart_script = f"""
select disk {disk_number}
select partition {partition_number}
remove letter={drive_letter}
exit
"""       
    try:
        run_diskpart(diskpart_script)
    except Exception as e:
        infomsg=f"ERROR:\n{e}"
        logger.error(infomsg)
        #print(f"执行出错: {e}")
        return {e}
def assign_drive_letter(disk_number, partition_number, drive_letter):
    logmsg=f"[Func]assign_drive_letter: disk_number={disk_number},partition_number={partition_number}, drive_letter={drive_letter}----->>>>>>"
    #print(logmsg)
    logger.debug(logmsg)  
    diskpart_script = f"""
select disk {disk_number}
select partition {partition_number}
assign letter={drive_letter}
exit
"""       
    try:
        run_diskpart(diskpart_script)
    except Exception as e:
        infomsg=f"ERROR:\n{e}"
        logger.error(infomsg)
        #print(f"执行出错: {e}")
        return {e}
def rescan_disks(disk_number):
    logmsg=f"[Func]rescan_disks: disk_number={disk_number}----->>>>>>"
    #print(logmsg)
    logger.debug(logmsg)
    diskpart_script=f"""
select disk {disk_number}
rescan
exit        
        """
    try:
        run_diskpart(diskpart_script)
    except Exception as e:
        infomsg=f"ERROR:\n{e}"
        logger.error(infomsg)
        #print(f"执行出错: {e}")
        return {e}
        
def copytree_overwrite(source_path, target_path):
    logmsg=f"[Func]copytree_overwrite: source_path={source_path},target_path={target_path}----->>>>>>"
    #print(logmsg)
    logger.debug(logmsg)
    if not os.path.exists(target_path):
        # 如果目标路径不存在原文件夹的话就创建
        os.makedirs(target_path)
    try:
        shutil.copytree(source_path, target_path, dirs_exist_ok=True)
        infomsg=f"Copy Successfully: {source_path} -> {target_path}"
        logger.info(infomsg)
        #print(f"复制成功: {source_path} -> {target_path}")
        return True
    except Exception as e:
        infomsg=f"Copy ERROR:\n{e}"
        logger.error(infomsg)
        #print(f"复制失败: {e}")
        return False

def load_json_data(json_file):
    if not os.path.exists(json_file):
        raise FileNotFoundError(f"{json_file} 不存在")
    with open(json_file, "r", encoding="utf-8") as f:
        all_datas = json.load(f)
        return all_datas
def save_json_data(json_data, save_path):
    # 写入前先清空文件
    with open(save_path, "w", encoding="utf-8") as f:
        f.write("")  # 先清空文件内容
    with open(save_path,"w",encoding="utf-8") as f:
        json.dump(json_data,f,ensure_ascii=False,indent=2)
        
def prepare_advclone_partition(storage_selected, shrink_space_mb):
    logmsg=f"[Func]prepare_advclone_partition: storage_list={storage_selected},shrink_space_mb={shrink_space_mb}----->>>>>>"
    #print(logmsg)
    logger.debug(logmsg)
    part = storage_selected
    disk_num = part.get("DiskNumber")
    if storage_selected.get('Type')=='Unallocated':
        logger.info(f"The unallocated disk space will be formatted to store backup data.")
        free_letter = get_available_drive_letter()        
        if free_letter:
            logger.info(f"{free_letter} will be used.")
            time.sleep(10)
            format_unAllocated_with_diskpart(disk_num)
            #重新扫描磁盘，获取advclone分区partiton编号，分配盘符
            rescan_disks(disk_num)
            disk_data_new = DP.get_system_disk_partitions()
            partitions_data = disk_data_new[str(disk_num)].get('Partitions')
            for p in partitions_data:
                if p.get('label') == 'advclone':
                    advclone_part_num=p.get('PartitionNumber')
                    break
            assign_drive_letter(disk_num, advclone_part_num, free_letter)
            logger.info(f"[Debug]format_unAllocated_with_diskpart finish.")
            return free_letter
    else:
        label = (part.get("label") or "").lower()        
        partition_num = part.get("PartitionNumber")
        size_bytes = part.get("size_bytes", 0)
        drive_letter = part.get("drive_letter")

        required_bytes = shrink_space_mb * 1024 * 1024

        if label == "advclone":
            if size_bytes >= required_bytes:
                if not drive_letter:
                    free_letter = get_available_drive_letter()
                    if free_letter:
                        out= assign_drive_letter(disk_num, partition_num, free_letter)
                        if out != None:
                            infomsg=f"The advclone partition exists, but an error occurred during drive letter assignment:\n{out}"
                            logger.info(infomsg)
                            #print(f"advclone分区已存在，但是分配盘符异常：{out}")
                            sys.exit(1)
                        else:
                            part["drive_letter"] = free_letter
                            infomsg=f"The advclone partition has been successfully mounted to {free_letter}:\n{out}"
                            logger.info(infomsg)
                            #print(f"advclone 成功挂载到 {free_letter}:\n", out)
                            return free_letter
                else:
                    infomsg=f"The advclone partition already exists and is mounted to {drive_letter}:"
                    logger.info(infomsg)
                    #print(f"advclone已经存在，且挂在到了{drive_letter}")
                    return drive_letter
        else:
            infomsg=f"No advclone partition. Needs to be created and mounted."
            logger.info(infomsg)
            #print(f"没有advclone分区，需要新建并分配盘符挂载")
            free_letter = get_available_drive_letter()
            if free_letter:
                out = shrink_and_create_with_diskpart(disk_num, partition_num, shrink_space_mb, free_letter)
                part["drive_letter"] = free_letter
                infomsg=f"A new advclone partition({shrink_space_mb}MB) has been created from {drive_letter}: and mounted to {free_letter}:"
                logger.info(infomsg)
                #print(f"从 {drive_letter}: 创建新分区 {shrink_space_mb}MB 挂载到 {free_letter}:\n", out)
                #重新扫描磁盘，获取advclone分区partiton编号，分配盘符
                rescan_disks(disk_num)
                return free_letter
                
def mount_EFI(all_disk_list):
    logmsg=f"[Func]run function: mount_EFI()------>>>>"
    logger.debug(logmsg)
    #print(logmsg)
    for d in all_disk_list:
        disk=all_disk_list.get(d)
        logmsg=f"[Debug]Get disk: type(disk)={type(disk)} , disk={disk}"
        logger.debug(logmsg)
        disk_num=disk.get('Number')
        logmsg=f"[Debug]Get disk_num: type(disk_num)={type(disk_num)} , disk_num={disk_num}"
        logger.debug(logmsg)
        for part in disk["Partitions"]:
            info = part.get("info", '')
            sys_type = part.get("Type")
            print()
            if info == 'System' or sys_type == 'System':
                drive_letter=part.get("drive_letter")
                partition_num = part.get("PartitionNumber")
                if not drive_letter:
                    infomsg=f"Mount EFI partition firstly."
                    logger.info(infomsg)
                    #print(f"EFI分区没有挂载，需要先挂载起来")
                    free_letter = get_available_drive_letter()
                    if free_letter:
                        out= assign_drive_letter(disk_num, partition_num, free_letter)
                        part["drive_letter"] = free_letter
                        if out != None:
                            infomsg=f"EFI Partition Mount Error:\n{out}"
                            logger.info(infomsg)
                            #print(f"EFI分区重新挂载异常:\n", out)
                            sys.exit(1)
                        else:
                            infomsg=f"EFI Partition Mount Success to {free_letter}:\n"
                            logger.info(infomsg)
                            #print(f"EFI分区重新挂载成功到 {free_letter}:\n", out)
                            return free_letter
                else:
                    infomsg=f"The EFI partition has been mounted to drive {drive_letter}.\n"
                    logger.info(infomsg)
                    #print(f"EFI分区已经挂载到了{drive_letter}")
                    return drive_letter

def update_grub_file(file_path, advclone_str, backup_str, before_backup_file_path, after_backup_file_path):
    """
    安全的文件替换（带备份功能）
    """
    #logger.info(f"[Debug Function]update_grub_file")
    key_advclone="/dev/sda5"
    key_backup="sda1 sda2 sda3 sda4"
    try:
        # 检查文件是否存在
        if not os.path.exists(file_path):
            infomsg=f"Error: File not exists:{file_path}"
            logger.info(infomsg)
            #print(f"错误：文件不存在 {file_path}")
            return False
        
        # 创建修改前的备份
        shutil.copy2(file_path, before_backup_file_path)
        logmsg=f"Backup grub.cfg before modify: {before_backup_file_path}"
        logger.debug(logmsg)
        #print(f"已创建修改前的备份: {before_backup_file_path}")
        
        
        # 读取原文件内容
        with open(file_path, 'r', encoding='utf-8') as f:
            original_content = f.read()
        
        # 检查是否包含目标字符串
        if key_advclone not in original_content:
            infomsg=f"Error: not found '{key_advclone}' in grub.cfg"
            logger.error(infomsg)
            #print(f"警告：文件中未找到 '{key_advclone}'")
            return False
        if key_backup not in original_content:
            infomsg=f"Error: not found '{key_backup}' in grub.cfg"
            logger.error(infomsg)
            #print(f"警告：文件中未找到 '{key_backup}'")
            return False
        
        # 执行替换
        new_content_tmp = original_content.replace(key_advclone, advclone_str)
        new_content = new_content_tmp.replace(key_backup, backup_str)
        
        
        # 写入新内容
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        infomsg=f"Complete to update grub.cfg\nSource:'{key_advclone}' New:'{advclone_str}'\nSource:'{key_backup}', New:'{backup_str}'"
        logger.debug(infomsg)
        #print("替换完成！")
        #print(f"原'{key_advclone}'替换为: '{advclone_str}'")
        #print(f"原'{key_backup}'替换为: '{backup_str}'")
        
        # 创建修改后的备份
        shutil.copy2(file_path, after_backup_file_path)
        logmsg=f"Backup grub.cfg after modify: {after_backup_file_path}"
        logger.debug(logmsg)
        #print(f"已创建修改后的备份: {after_backup_file_path}")
        
        # 显示替换前后的差异
        original_lines = original_content.split('\n')
        new_lines = new_content.split('\n')
        '''
        for i, (orig, new) in enumerate(zip(original_lines, new_lines)):
            if orig != new:
                print(f"\n第{i+1}行变化:")
                print(f"原: {orig}")
                print(f"新: {new}")
        '''
        return True
        
    except Exception as e:
        infomsg=f"ERROR:\n{e}"
        logger.error(infomsg)
        #print(f"错误：{e}")
        return False
    
    pass
    
    
def clean_advclone_entries():
    """简洁版的AdvClone清理函数"""
    infomsg=f"---Clean AdvClone boot item..."
    logger.info(infomsg)
    #print('---清理AdvClone启动项...')
    try:
        # 获取启动项列表
        '''
        result = subprocess.run('bcdedit /enum BOOTMGR', 
                              capture_output=True, text=True, shell=True, timeout=300)
        
        if result.returncode != 0:
            return False
        #print(result.stdout)
        logger.debug(result.stdout)
        # 查找所有AdvClone条目的GUID
        pattern = r'identifier\s+{([^}]+)}[^}]*?description\s+.*AdvClone'
        guids = re.findall(pattern, result.stdout, re.DOTALL | re.IGNORECASE)
        '''
        output = runCmd('bcdedit /enum BOOTMGR')
        logger.debug(output)
        pattern = r'identifier\s+{([^}]+)}[^}]*?description\s+.*AdvClone'
        guids = re.findall(pattern, output, re.DOTALL | re.IGNORECASE)
        #logger.info(f"guids={guids}")
        # 删除找到的条目
        for guid in set(guids):  # 去重
            logger.debug(f"guid: {guid}")
            subprocess.run(f'bcdedit /delete {{{guid}}} /f', 
                         shell=True, timeout=60)
            #print(f'已删除: {guid}')
            logger.info(f"Delete: {guid}")
        
        logger.info(f"Finish clean.")
        #print('清理完成')
        return True
        
    except Exception as e:
        infomsg=f"ERROR:\n{e}"
        logger.error(infomsg)
        #print(f'错误: {e}')
        return False

def modify_boot_order(EFImountLTR: str):
    infomsg="------ Starting to change boot order ------ "
    logger.info(infomsg)
    #print("------ 开始修改启动顺序 ------")

    # step1: 获取启动项ID
    """复制 bootmgr 启动项并返回新建启动项的 GUID"""
    infomsg=f"[STEP1]bcdedit copy bootmgr"
    logger.info(infomsg)
    #print("[STEP1] 复制 bootmgr 启动项")    
    output = runCmd("bcdedit /copy {bootmgr} /d AdvClone")
    #logger.info(output)

    # 用正则提取 {xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx}
    match = re.search(r"\{[0-9a-fA-F\-]{36}\}", output)
    if not match:
        raise RuntimeError(f"未能在输出中找到 GUID:\n{output}")

    ID = match.group(0).strip("{}")
    infomsg=f"[INFO] New boot item GUID: {ID}"
    logger.info(infomsg)
    #print(f"[INFO] 新启动项 GUID: {ID}")

    # step2: 设置分区
    #print("[STEP2] 设置 device 分区")
    infomsg=f"[STEP2] Set device partition"
    logger.info(infomsg)
    runCmd(f'bcdedit /set {{{ID}}} device partition={EFImountLTR}:')

    # step3: 设置引导文件路径
    #print("[STEP3] 设置引导路径")
    infomsg=f"[STEP3] Set boot path"
    logger.info(infomsg)
    runCmd(f'bcdedit /set {{{ID}}} path \\EFI\\boot\\grubx64.efi')

    # step4: 调整启动顺序
    #print("[STEP4] 调整启动顺序")
    infomsg=f"[STEP4] Change boot order"
    logger.info(infomsg)
    runCmd(f'bcdedit /set {{fwbootmgr}} displayorder {{{ID}}} /addfirst')

    # step5: 设置默认启动项
    #print("[STEP5] 设置默认启动项")
    infomsg=f"[STEP5] bcdedit set default boot item"
    logger.info(infomsg)
    runCmd(f'bcdedit /default {{{ID}}}')

    #print("------ 启动项修改完成 ------")
    infomsg=f"------ Complete to change boot order ------"
    logger.info(infomsg)
    

# --- main ---
if __name__=="__main__":
    try:
        DP=basic_disk_patitions()

        disk_path_1 = "disk_details_1st.json"
        config_path = "selected_partitions.json"
        all_disks_data = load_json_data(disk_path_1)
        select_config = load_json_data(config_path)


        backup_list = select_config.get("backup", [])
        storage_list = select_config.get("storage", [])
        shrink_space_mb = select_config.get("shrink_space_mb", 0)


        sys_disk_id = list(all_disks_data.keys())[0]


        ## 注意必须先挂载EFI分区，在分advclone分区，否则会有盘符变动异常！！！！

        #print(f"[Step]====== 挂载EFI分区 ======")
        infomsg=f"[Step]====== Mount EFI partition ======"
        logger.info(infomsg)
        EFI_ltr = mount_EFI(all_disks_data)


        #print("[Step]====== 准备advclone分区 ====== ")
        infomsg=f"[Step]====== Prepare advclone partition ======"
        logger.info(infomsg)
        advclone_ltr = prepare_advclone_partition(storage_list, shrink_space_mb)


        
        #print("[Step]====== 再次获取所有磁盘最新信息 ====== ")
        infomsg=f"[Step]====== Get disk information again ======"
        logger.info(infomsg)
        # 仅获取系统C盘所在disk的磁盘信息
        all_disks_data_new = DP.get_system_disk_partitions()
        filename = f"disk_details_2nd.json"
        save_path = os.path.join(os.getcwd(),filename)   
        save_json_data(all_disks_data_new, save_path)



        sys_disk_type=get_disk_type(sys_disk_id)


        #print(f"[Step]====== update grub.cfg ======")
        infomsg=f"[Step]====== update grub.cfg ======"
        logger.info(infomsg)
        all_disks_data_new= load_json_data(os.path.join(os.getcwd(),f"disk_details_2nd.json") )
        
        #print("[Step]找到要备份的分区，最新的sda编号（sort by offset）")
        infomsg=f"[Step]Get the partition for backup with the latest sda number.(sort by offset)"
        logger.info(infomsg)
        backup_part_ids=[]
        src_backup_part_ids=[]
        for backup in backup_list:
            backup_pnum = backup.get("PartitionNumber")
            backup_offset = backup.get("OffsetBytes")
            backup_offset_id=backup.get("SortedOffsetIndex")
            src_backup_part_ids.append(backup_offset_id)
            #print(f"[Debug]原来选择的备份分区：backup_pnum={backup_pnum},backup_offset={backup_offset},backup_offset_id={backup_offset_id} ")
            for d in all_disks_data_new:
                d_disk=all_disks_data_new.get(d)
                new_partitions = d_disk.get("Partitions")
                for new_part in new_partitions:
                    new_pnum=new_part.get("PartitionNumber")
                    new_offset = new_part.get("OffsetBytes")
                    new_offset_id=new_part.get("SortedOffsetIndex")
                    #print(f"[Debug]重新扫描后获取到的partition信息：new_pnum={new_pnum}, new_offset={new_offset}, new_offset_id={new_offset_id}")
                    #if new_pnum == backup_pnum and new_offset == backup_offset:
                    if new_offset == backup_offset:
                        #print(f"[Debug]匹配成功")
                        backup_part_ids.append(new_offset_id)
                        continue
        src_backup_part_ids.sort()
        backup_part_ids.sort()
        #print(f"src_backup_part_ids: {src_backup_part_ids}" )
        #print(f"backup_part_ids:  {backup_part_ids}" )
        logmsg=f"src_backup_part_ids: {src_backup_part_ids}\nbackup_part_ids:  {backup_part_ids}"
        logger.debug(logmsg)

        backup_parts_str = ' '.join([f'{sys_disk_type}{item}' for item in backup_part_ids])
        #print(f"backup_parts_str:{backup_parts_str}" )
        logmsg=f"backup_parts_str:{backup_parts_str}"
        logger.debug(logmsg)
        
        #print("[Step]====== 找到advclone的分区，sda编号(sort by offset)====== ")
        infomsg=f"[Step]====== Get advclone partition index with sda(sort by offset)====== "
        logger.info(infomsg)
        for d in all_disks_data_new:
            d_disk=all_disks_data_new.get(d)
            new_partitions = d_disk.get("Partitions")
            for new_part in new_partitions:
                new_label = new_part.get("label", None)
                new_offset_id = new_part.get("SortedOffsetIndex")
                new_partition_id = new_part.get("PartitionNumber")
                if new_label and new_label == "advclone":
                    advclone_offset_id = new_offset_id
                    advclone_partition_number = new_partition_id
                    break

        advclone_part_name = f"/dev/{sys_disk_type}{advclone_offset_id}"
        #print("[Debug]get advclone_part_name is: ", advclone_part_name)
        logmsg=f"[Debug]get advclone_part_name is: {advclone_part_name}"
        logger.debug(logmsg)


        # 更新grub.cfg
        #print(f"[Step]====== 更新boot\\grub\\grub.cfg文件内容 ====== ")
        infomsg=f"[Step]====== update boot\\grub\\grub.cfg ====== "
        logger.info(infomsg)

        grub_config_file=os.path.join(os.getcwd(),r"boot\grub\grub.cfg")
        #print(grub_config_file)
        infomsg=f"{grub_config_file}"
        logger.debug(infomsg)

        # grub备份文件名字
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # 修改前的备份grub文件名称
        backup_grub_src = f"grub_src_backup_{timestamp}.cfg"
        backup_grub_src_path = os.path.join(os.getcwd(), backup_grub_src)
        #print(f"backup_grub_src_path: {backup_grub_src_path}")
        # 修改后的备份grub文件名称
        backup_grub_modified = f"grub_modified_backup_{timestamp}.cfg"
        backup_grub_modified_path = os.path.join(os.getcwd(), backup_grub_modified)
        #print(f"backup_grub_modified_path: {backup_grub_modified_path}")

        # 原始grub.cnf复原
        shutil.copy('grub.cfg', r"boot\grub\grub.cfg")

        update_grub_file(grub_config_file, advclone_part_name, backup_parts_str, backup_grub_src_path, backup_grub_modified_path)

        #print(f"\n[Step]====== 拷贝文件 ======\n")
        infomsg=f"[Step]====== Copy files ====== "
        logger.info(infomsg)
        boot_Dir = '%s:\\boot' % (EFI_ltr)
        EFI_Dir = '%s:\\EFI' % (EFI_ltr)
        live_Dir = '%s:\\live' % (advclone_ltr)
        
        #print(f"----拷贝 boot folder 到 {boot_Dir}------")
        infomsg=f"----copy boot folder to {boot_Dir}------ "
        logger.info(infomsg)
        copytree_overwrite('boot', boot_Dir)
        time.sleep(1)
        
        #print(f"----拷贝 EFI folder 到 {EFI_Dir}------")
        infomsg=f"----copy EFI folder to {EFI_Dir}------ "
        logger.info(infomsg)
        copytree_overwrite('EFI', EFI_Dir)
        time.sleep(1)
        
        #print(f"----拷贝 live folder 到 {live_Dir}------")
        infomsg=f"----copy live folder to {live_Dir}------ "
        logger.info(infomsg)
        copytree_overwrite('live', live_Dir)
        time.sleep(1)

        #print(f"\n[Step]====== 隐藏advclone ======\n")
        infomsg=f"\n[Step]====== Hide advclone ======\n"
        logger.info(infomsg)
        remove_drive_letter(sys_disk_id, advclone_partition_number, advclone_ltr)

        #print(f"\n[Step]====== 修改系统启动顺序 ======\n")
        infomsg=f"\n[Step]====== Change system boot order ======\n"
        logger.info(infomsg)
        clean_advclone_entries()
        modify_boot_order(EFI_ltr)
        
        #print(f"\n[Step]====== Finish ======\n")
        infomsg=f"\n[Step]====== Finish ======\n"
        logger.info(infomsg)
        sys.exit(0)
        
    except Exception as e:
        infomsg=f"main ERROR:\n{e}"
        logger.error(infomsg)
        #print(f"main执行异常捕获：{e}" )
        sys.exit(1)
