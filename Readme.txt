#文件说明
AdvClone.py是QT主程序
get_partitions_basic.py是获取磁盘分区情况的公用脚本
run_prepare_grub_env.py是根据QT的选择执行压缩advclone分区、分配盘符、拷贝文件等执行动作

#打包命令
python -m PyInstaller --onefile --windowed run_prepare_grub_env.py
python -m PyInstaller --onefile --windowed --version-file version_info.txt AdvClone.py

#版本说明：
version_info.txt存放版本等产品信息
用户看到的版本：4.0.0（来自 FileVersion 和 ProductVersion）

内部版本号：1.0.0.0（来自 filevers 和 prodvers）