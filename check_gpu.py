import torch

# 检查PyTorch版本
print('PyTorch version:', torch.__version__)

# 检查CUDA是否可用
print('CUDA available:', torch.cuda.is_available())

# 如果有GPU，显示GPU数量和名称
if torch.cuda.is_available():
    print('Number of GPUs:', torch.cuda.device_count())
    for i in range(torch.cuda.device_count()):
        print(f'GPU {i}:', torch.cuda.get_device_name(i))
else:
    print('No GPU found or CUDA not properly configured')

# 检查NVIDIA驱动版本（如果有NVIDIA GPU）
try:
    import subprocess
    result = subprocess.run(['nvidia-smi'], capture_output=True, text=True)
    if result.returncode == 0:
        print('\nNVIDIA驱动信息:')
        print(result.stdout[:500] + '...')  # 只显示前500个字符
    else:
        print('NVIDIA驱动未安装或无法访问')
except FileNotFoundError:
    print('NVIDIA驱动未安装或nvidia-smi命令不可用')