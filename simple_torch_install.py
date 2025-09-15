#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""简化版PyTorch安装工具
提供多种安装选项，方便用户根据需求选择
"""

import os
import subprocess
import sys

# 全局配置
PYTORCH_VERSION = "2.7.1+cu118"
TORCHAUDIO_VERSION = "2.7.1+cu118"
TORCHVISION_VERSION = "0.22.1+cu118"
PYTORCH_INDEX_URL = "https://download.pytorch.org/whl/cu118"

# 颜色编码
class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def run_command(cmd, env=None, timeout=600):
    """执行命令并显示实时输出"""
    print(f"{bcolors.OKCYAN}执行: {' '.join(cmd)}{bcolors.ENDC}")
    try:
        # 明确指定encoding=utf-8以解决Windows下的Unicode解码问题
        process = subprocess.Popen(
            cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8"
        )
        
        # 实时显示输出
        for line in process.stdout:
            print(line, end='')
        
        process.wait(timeout=timeout)
        
        return process.returncode == 0
    except Exception as e:
        print(f"{bcolors.FAIL}命令执行出错: {e}{bcolors.ENDC}")
        return False


def check_uv_installed():
    """检查UV是否已安装"""
    result = run_command([sys.executable, "-m", "uv", "--version"])
    if not result:
        print(f"{bcolors.WARNING}UV未安装，尝试使用pip...{bcolors.ENDC}")
        return False
    return True


def clean_broken_packages():
    """清理损坏的包残留"""
    print(f"{bcolors.HEADER}\n=== 清理损坏的包残留 ==={bcolors.ENDC}")
    
    # 查找site-packages目录
    site_packages_dirs = [p for p in sys.path if "site-packages" in p]
    
    for site_packages in site_packages_dirs:
        print(f"检查目录: {site_packages}")
        try:
            # 检查并删除以波浪号开头的损坏文件
            for item in os.listdir(site_packages):
                if item.startswith("~"):
                    item_path = os.path.join(site_packages, item)
                    print(f"{bcolors.WARNING}删除损坏的文件/目录: {item_path}{bcolors.ENDC}")
                    try:
                        if os.path.isdir(item_path):
                            import shutil
                            shutil.rmtree(item_path)
                        else:
                            os.remove(item_path)
                        print(f"{bcolors.OKGREEN}已删除: {item_path}{bcolors.ENDC}")
                    except Exception as e:
                        print(f"{bcolors.FAIL}无法删除 {item_path}: {e}{bcolors.ENDC}")
        except Exception as e:
            print(f"{bcolors.FAIL}访问目录时出错: {e}{bcolors.ENDC}")


def install_with_uv(options):
    """使用UV安装PyTorch"""
    print(f"{bcolors.HEADER}\n=== 使用UV安装PyTorch {PYTORCH_VERSION} ==={bcolors.ENDC}")
    
    # 设置环境变量
    env = os.environ.copy()
    env["UV_NO_CACHE"] = "1"  # 禁用缓存以节省空间
    
    # 基础安装命令
    cmd = [
        sys.executable,
        "-m",
        "uv",
        "pip",
        "install",
        "--no-cache-dir"
    ]
    
    # 根据选项添加包
    if options["full"]:
        cmd.extend([
            f"torch=={PYTORCH_VERSION}",
            f"torchaudio=={TORCHAUDIO_VERSION}",
            f"torchvision=={TORCHVISION_VERSION}"
        ])
    else:
        cmd.append(f"torch=={PYTORCH_VERSION}")
    
    # 添加索引URL
    cmd.extend(["--index-url", PYTORCH_INDEX_URL])
    
    return run_command(cmd, env=env)


def install_with_pip(options):
    """使用pip安装PyTorch"""
    print(f"{bcolors.HEADER}\n=== 使用pip安装PyTorch {PYTORCH_VERSION} ==={bcolors.ENDC}")
    
    # 基础安装命令
    cmd = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--no-cache-dir",
        "--upgrade"
    ]
    
    # 根据选项添加包
    if options["full"]:
        cmd.extend([
            f"torch=={PYTORCH_VERSION}",
            f"torchaudio=={TORCHAUDIO_VERSION}",
            f"torchvision=={TORCHVISION_VERSION}"
        ])
    else:
        cmd.append(f"torch=={PYTORCH_VERSION}")
    
    # 添加索引URL
    cmd.extend(["--index-url", PYTORCH_INDEX_URL])
    
    return run_command(cmd)


def verify_installation():
    """验证PyTorch安装"""
    print(f"{bcolors.HEADER}\n=== 验证PyTorch安装 ==={bcolors.ENDC}")
    
    # 使用逐行写入的方式，避免字符串解析问题
    verify_lines = [
        'import torch',
        'print("PyTorch版本: " + str(torch.__version__))',
        'print("CUDA可用: " + str(torch.cuda.is_available()))',
        'if torch.cuda.is_available():',
        '    print("CUDA版本: " + str(torch.version.cuda))',
        '    print("GPU数量: " + str(torch.cuda.device_count()))',
        '    print("GPU名称: " + torch.cuda.get_device_name(0))',
        '',
        '# 测试基本操作',
        'print("测试基本张量操作...")',
        'x = torch.tensor([1.0])',
        'if torch.cuda.is_available():',
        '    x = x.to(\'cuda\')',
        '    y = x * 2',
        '    print("CUDA张量操作结果: " + str(y))',
        'else:',
        '    y = x * 2',
        '    print("CPU张量操作结果: " + str(y))'
    ]
    
    # 将每一行写入文件
    with open("verify_torch_temp.py", "w", encoding="utf-8") as f:
        for line in verify_lines:
            f.write(line + '\n')
    
    # 添加-X utf8选项强制使用UTF-8编码，解决Windows控制台中的Unicode显示问题
    result = run_command([sys.executable, "-X", "utf8", "verify_torch_temp.py"])
    
    # 清理临时文件
    try:
        os.remove("verify_torch_temp.py")
    except:
        pass
    
    return result


def display_menu():
    """显示安装选项菜单"""
    print(f"{bcolors.BOLD}{bcolors.HEADER}\n==== 简化版PyTorch安装工具 ===={bcolors.ENDC}")
    print(f"此工具提供多种PyTorch安装选项，帮助您优化空间使用。\n")
    
    print(f"{bcolors.OKCYAN}请选择安装选项:{bcolors.ENDC}")
    print("1. 完整安装 (torch + torchaudio + torchvision)")
    print("2. 仅安装torch (最小化安装)")
    print("3. 仅清理损坏的包文件")
    print("4. 验证现有安装")
    print("0. 退出")
    
    try:
        choice = input(f"{bcolors.BOLD}\n请输入选项 [0-4]: {bcolors.ENDC}")
        return choice
    except KeyboardInterrupt:
        print(f"\n{bcolors.WARNING}操作已取消{bcolors.ENDC}")
        return "0"


def main():
    """主函数"""
    while True:
        choice = display_menu()
        
        if choice == "0":
            print(f"{bcolors.OKGREEN}\n感谢使用，再见！{bcolors.ENDC}")
            break
        
        elif choice == "1":
            # 完整安装
            clean_broken_packages()
            
            # 优先使用UV，否则回退到pip
            if check_uv_installed():
                success = install_with_uv({"full": True})
            else:
                success = install_with_pip({"full": True})
            
            if success:
                verify_installation()
            
        elif choice == "2":
            # 最小化安装
            clean_broken_packages()
            
            # 优先使用UV，否则回退到pip
            if check_uv_installed():
                success = install_with_uv({"full": False})
            else:
                success = install_with_pip({"full": False})
            
            if success:
                verify_installation()
        
        elif choice == "3":
            # 仅清理
            clean_broken_packages()
        
        elif choice == "4":
            # 验证安装
            verify_installation()
        
        else:
            print(f"{bcolors.FAIL}无效的选项，请重新输入！{bcolors.ENDC}")
        
        input(f"\n{bcolors.WARNING}按Enter键继续...{bcolors.ENDC}")


if __name__ == "__main__":
    main()