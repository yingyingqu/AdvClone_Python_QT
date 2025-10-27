python -m PyInstaller --onefile --windowed run_prepare_grub_env.py
python -m PyInstaller --onefile --windowed --version-file version_info.txt AdvClone.py

#version_info.txt存放版本等产品信息
用户看到的版本：4.0.0（来自 FileVersion 和 ProductVersion）

内部版本号：1.0.0.0（来自 filevers 和 prodvers）