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
from get_partions_volumes import dispart_partition_volume
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")


DP = dispart_partition_volume()
#all_disks_data = DP.get_all_partitions()

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
    

def runCmd(cmd: str, timeout: int = 60) -> str:
    """执行命令并强制输出为英文"""
    env = os.environ.copy()
    # Windows下强制英文环境
    env["LANG"] = "en_US.UTF-8"
    env["LC_ALL"] = "en_US.UTF-8"
    env["LANGUAGE"] = "en"

    try:
        result = subprocess.run(
            cmd,
            shell=True,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            text=True,        # 自动转 str
            encoding="utf-8", # 确保是utf-8
            errors="replace",
            env=env
        )
        print(f"[OK] {cmd}\n{result.stdout}")
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] 命令失败: {cmd}\n输出:\n{e.stdout}")
        raise
    except subprocess.TimeoutExpired:
        print(f"[TIMEOUT] 命令超时: {cmd}")
        raise


def load_json_data(json_file):
    if not os.path.exists(json_file):
        raise FileNotFoundError(f"{json_file} 不存在")
    with open(json_file, "r", encoding="utf-8") as f:
        all_datas = json.load(f)
        return all_datas
def save_json_data(json_data, save_path):
    with open(save_path,"w",encoding="utf-8") as f:
        json.dump(json_data,f,ensure_ascii=False,indent=2)
        
def copytree_overwrite(source_path, target_path):
    if not os.path.exists(target_path):
        # 如果目标路径不存在原文件夹的话就创建
        os.makedirs(target_path)
    try:
        shutil.copytree(source_path, target_path, dirs_exist_ok=True)
        print(f"复制成功: {source_path} -> {target_path}")
        return True
    except Exception as e:
        print(f"复制失败: {e}")
        return False

# 获取可用盘符，排除A、B、C
def get_available_drive_letter(exclude=('A','B','C')):
    used = []
    bitmask = ctypes.cdll.kernel32.GetLogicalDrives()
    for i in range(26):
        if bitmask & (1 << i):
            used.append(chr(ord('A') + i))
    all_letters = set(string.ascii_uppercase) - set(exclude)
    free_letters = sorted(list(all_letters - set(used)))
    return free_letters[0] if free_letters else None

def run_diskpart(cmds):
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

# 挂载分区
def mount_partition(volume_number, drive_letter):
    script = f"""
select volume {volume_number}
assign letter={drive_letter}
exit
"""
    output = run_diskpart(script)
    return output

# 压缩分区并创建新分区
def shrink_and_create_partition(volume_number, size_mb, drive_letter):
    print(f"[Debug]shrink_and_create_partition, 压缩空间大小{size_mb}MB，并分配盘符{drive_letter}")
    script = f"""
select volume {volume_number}
shrink desired={size_mb}
create partition primary size={size_mb}
format fs=ntfs label="advclone"quick
assign letter={drive_letter}
exit
"""
    output = run_diskpart(script)
    return output

# 准备advclone分区
def prepare_advclone_partition(storage_list, shrink_space_mb):
    print(f"[Debug]-----prepare_advclone_partition:\n storage_list={storage_list}\n shrink_space_mb={shrink_space_mb}")
    for part in storage_list:
        label = (part.get("label") or "").lower()
        vol_num = part.get("VolumeNumber")
        size_bytes = part.get("size_bytes", 0)
        drive_letter = part.get("drive_letter")

        required_bytes = shrink_space_mb * 1024 * 1024
        #按照逻辑，既然能走到这一步，说明即使有advclone分区，它的空间也是足够的，因此这里不再判断, shrink_space_mb是在所需空间的基础上加了750M的
        if label == "advclone":
            print(f"[Debug]Found advclone, size_bytes={size_bytes}, required_bytes={required_bytes}")
            if not drive_letter:
                free_letter = get_available_drive_letter()
                if free_letter:
                    out= mount_partition(vol_num, free_letter)
                    part["drive_letter"] = free_letter
                    print(f"advclone 挂载到 {free_letter}:\n", out)
            else:
                print(f"advclone已经存在，且挂在到了{drive_letter}")
        else:
            print(f"没有advclone分区，需要新建并分配盘符挂载")
            free_letter = get_available_drive_letter()
            if free_letter:
                out = shrink_and_create_partition(vol_num, shrink_space_mb, free_letter)
                part["drive_letter"] = free_letter
                print(f"从 {drive_letter}: 创建新分区 {shrink_space_mb}MB 挂载到 {free_letter}:\n", out)
        print(f"prepare_advclone_partition return part.get('drive_letter'): {part.get('drive_letter')}\n")
        return part.get("drive_letter")

def mount_EFI(all_disk_list):
    for disk in all_disk_list:
        for part in disk["Partitions"]:
            info = part.get("info", '')
            sys_type = part.get("Type")
            if info == 'System' and sys_type == 'System':
                drive_letter=part.get("drive_letter")
                vol_num = part.get("VolumeNumber")
                if not drive_letter:
                    print(f"EFI分区没有挂载，需要先挂载起来")
                    free_letter = get_available_drive_letter()
                    if free_letter:
                        out= mount_partition(vol_num, free_letter)
                        part["drive_letter"] = free_letter
                        print(f"advclone 挂载到 {free_letter}:\n", out)
                else:
                    print(f"EFI分区已经挂载到了{drive_letter}")
            print(f"mount_EFI return part.get('drive_letter'): {part.get('drive_letter')}\n")
            return part.get("drive_letter")

def rescan_disks():
    #DP = dispart_partition_volume()
    disk_nums=DP.get_hard_disk_numbers()
    for d in disk_nums:
        script=f"""
select disk {d}
rescan
exit        
        """
        out = run_diskpart(script)
        print(out)
   
def update_grub_file(file_path, advclone_str, backup_str, before_backup_file_path, after_backup_file_path):
    """
    安全的文件替换（带备份功能）
    """
    key_advclone="/dev/sda5"
    key_backup="sda1 sda2 sda3 sda4"
    try:
        # 检查文件是否存在
        if not os.path.exists(file_path):
            print(f"错误：文件不存在 {file_path}")
            return False
        
        # 创建修改前的备份
        shutil.copy2(file_path, before_backup_file_path)
        print(f"已创建修改前的备份: {before_backup_file_path}")
        
        
        # 读取原文件内容
        with open(file_path, 'r', encoding='utf-8') as f:
            original_content = f.read()
        
        # 检查是否包含目标字符串
        if key_advclone not in original_content:
            print(f"警告：文件中未找到 '{key_advclone}'")
            return False
        if key_backup not in original_content:
            print(f"警告：文件中未找到 '{key_backup}'")
            return False
        
        # 执行替换
        new_content_tmp = original_content.replace(key_advclone, advclone_str)
        new_content = new_content_tmp.replace(key_backup, backup_str)
        
        
        # 写入新内容
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        print("替换完成！")
        print(f"原'{key_advclone}'替换为: '{advclone_str}'")
        print(f"原'{key_backup}'替换为: '{backup_str}'")
        
        # 创建修改后的备份
        shutil.copy2(file_path, after_backup_file_path)
        print(f"已创建修改后的备份: {after_backup_file_path}")
        
        # 显示替换前后的差异
        original_lines = original_content.split('\n')
        new_lines = new_content.split('\n')
        
        for i, (orig, new) in enumerate(zip(original_lines, new_lines)):
            if orig != new:
                print(f"\n第{i+1}行变化:")
                print(f"原: {orig}")
                print(f"新: {new}")
        
        return True
        
    except Exception as e:
        print(f"错误：{e}")
        return False
    
    pass
    
    
def clean_advclone_entries():
    """简洁版的AdvClone清理函数"""
    print('---清理AdvClone启动项...')
    try:
        # 获取启动项列表
        result = subprocess.run('bcdedit /enum BOOTMGR', 
                              capture_output=True, text=True, shell=True, timeout=300)
        
        if result.returncode != 0:
            return False
        print(result.stdout)
        # 查找所有AdvClone条目的GUID
        pattern = r'identifier\s+{([^}]+)}[^}]*?description\s+.*AdvClone'
        guids = re.findall(pattern, result.stdout, re.DOTALL | re.IGNORECASE)
        
        # 删除找到的条目
        for guid in set(guids):  # 去重
            subprocess.run(f'bcdedit /delete {{{guid}}} /f', 
                         shell=True, timeout=60)
            print(f'已删除: {guid}')
        
        print('清理完成')
        return True
        
    except Exception as e:
        print(f'错误: {e}')
        return False

def modify_boot_order(EFImountLTR: str):
    print("------ 开始修改启动顺序 ------")

    # step1: 获取启动项ID
    """复制 bootmgr 启动项并返回新建启动项的 GUID"""
    print("[STEP1] 复制 bootmgr 启动项")    
    output = runCmd('bcdedit /copy {bootmgr} /d "AdvClone"')

    # 用正则提取 {xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx}
    match = re.search(r"\{[0-9a-fA-F\-]{36}\}", output)
    if not match:
        raise RuntimeError(f"未能在输出中找到 GUID:\n{output}")

    ID = match.group(0).strip("{}")
    print(f"[INFO] 新启动项 GUID: {ID}")

    # step2: 设置分区
    print("[STEP2] 设置 device 分区")
    runCmd(f'bcdedit /set {{{ID}}} device partition={EFImountLTR}:')

    # step3: 设置引导文件路径
    print("[STEP3] 设置引导路径")
    runCmd(f'bcdedit /set {{{ID}}} path \\EFI\\boot\\grubx64.efi')

    # step4: 调整启动顺序
    print("[STEP4] 调整启动顺序")
    runCmd(f'bcdedit /set {{fwbootmgr}} displayorder {{{ID}}} /addfirst')

    # step5: 设置默认启动项
    print("[STEP5] 设置默认启动项")
    runCmd(f'bcdedit /default {{{ID}}}')

    print("------ 启动项修改完成 ------")
    

# 使用示例
# 测试数据 -1
disk_path_1 = "disk_details_1.json"
config_path = "selected_partitions.json"
all_disks_data = load_json_data(disk_path_1)
select_config = load_json_data(config_path)


backup_list = select_config.get("backup", [])
storage_list = select_config.get("storage", [])
shrink_space_mb = select_config.get("shrink_space_mb", 0)

# --- main ---


## 注意必须先挂载EFI分区，在分advclone分区，否则会有盘符变动异常！！！！

print(f"[Step]====== 挂载EFI分区 ======")
EFI_ltr = mount_EFI(all_disks_data)


print("[Step]====== 准备advclone分区 ====== ")
advclone_ltr = prepare_advclone_partition(storage_list, shrink_space_mb)

print("[Step]====== 重新扫描磁盘 ====== ")
rescan_disks()

print("[Step]====== 再次获取所有磁盘最新信息 ====== ")
# 获取所有disk的分区信息    
#all_disks_data_new = DP.get_all_disks_partitons()
# 仅获取系统C盘所在disk的磁盘信息
all_disks_data_new = DP.get_system_disk_partitions()
filename = f"disk_details_2.json"
save_path = os.path.join(os.getcwd(),filename)   
save_json_data(all_disks_data_new, save_path)


print(f"[Step]====== update grub.cfg ======")
all_disks_data_new= load_json_data(os.path.join(os.getcwd(),f"disk_details_2.json") )
print("[Step]找到要备份的分区，最新的sda编号（sort by offset）")
backup_part_ids=[]
src_backup_part_ids=[]
for backup in backup_list:
    backup_pnum = backup.get("PartitionNumber")
    backup_offset = backup.get("OffsetBytes")
    backup_offset_id=backup.get("SortedOffsetIndex")
    src_backup_part_ids.append(backup_offset_id)
    for d in all_disks_data_new:
        d_disk=d.get("Disk")
        new_partitions = d.get("Partitions")
        for new_part in new_partitions:
            new_pnum=new_part.get("PartitionNumber")
            new_offset = new_part.get("OffsetBytes")
            new_offset_id=new_part.get("SortedOffsetIndex")
            if new_pnum == backup_pnum and new_offset == backup_offset:
                backup_part_ids.append(new_offset_id)
                continue
src_backup_part_ids.sort()
backup_part_ids.sort()
print(f"src_backup_part_ids: {src_backup_part_ids}" )
print(f"backup_part_ids:  {backup_part_ids}" )

backup_parts_str = ' '.join([f'sda{item}' for item in backup_part_ids])
print(f"backup_parts_str:{backup_parts_str}" )

print("[Step]====== 找到advclone的分区，sda编号（sort by offset）====== ")
for d in all_disks_data_new:
    d_disk=d.get("Disk")
    new_partitions = d.get("Partitions")
    for new_part in new_partitions:
        new_label = new_part.get("label", None)
        new_offset_id = new_part.get("SortedOffsetIndex")
        new_volume_id = new_part.get("VolumeNumber")
        if new_label and new_label == "advclone":
            advclone_offset_id = new_offset_id
            advclone_volume_number = new_volume_id
            break

advclone_part_name = f"/dev/sda{advclone_offset_id}"
print("[Debug]get advclone_part_name is: ", advclone_part_name)


# 更新grub.cfg
print(f"[Step]====== 更新boot\\grub\\grub.cfg文件内容 ====== ")

grub_config_file=os.path.join(os.getcwd(),r"boot\grub\grub.cfg")
print(grub_config_file)

# grub备份文件名字
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
# 修改前的备份grub文件名称
backup_grub_src = f"grub_src_backup_{timestamp}.cfg"
backup_grub_src_path = os.path.join(os.getcwd(), backup_grub_src)
print(f"backup_grub_src_path: {backup_grub_src_path}")
# 修改后的备份grub文件名称
backup_grub_modified = f"grub_modified_backup_{timestamp}.cfg"
backup_grub_modified_path = os.path.join(os.getcwd(), backup_grub_modified)
print(f"backup_grub_modified_path: {backup_grub_modified_path}")

update_grub_file(grub_config_file, advclone_part_name, backup_parts_str, backup_grub_src_path, backup_grub_modified_path)
'''
# 测试数据-2         
EFI_ltr = 'E'
advclone_ltr = 'F'
#
'''
print(f"\n[Step]====== 拷贝文件 ======\n")
boot_Dir = '%s:\\boot' % (EFI_ltr)
EFI_Dir = '%s:\\EFI' % (EFI_ltr)
live_Dir = '%s:\\live' % (advclone_ltr)
print(f"----拷贝 boot folder 到 {boot_Dir}------")
copytree_overwrite('boot', boot_Dir)
time.sleep(1)
print(f"----拷贝 EFI folder 到 {EFI_Dir}------")
copytree_overwrite('EFI', EFI_Dir)
time.sleep(1)
print(f"----拷贝 live folder 到 {live_Dir}------")
copytree_overwrite('live', live_Dir)
time.sleep(1)

print(f"\n[Step]====== 隐藏advclone ======\n")
script = f"""
select volume {advclone_volume_number}
remove letter={advclone_ltr}
exit
"""
output = run_diskpart(script)

print(f"\n[Step]====== 修改系统启动顺序 ======\n")
clean_advclone_entries()
modify_boot_order(EFI_ltr)

print(f"\n[Step]====== Finish ======\n")