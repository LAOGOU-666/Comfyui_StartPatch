import re
import os
from pathlib import Path

def find_comfyui_root():
    """查找 ComfyUI 根目录"""
    current = Path(__file__).parent
    while current.name != 'custom_nodes' and current.parent != current:
        current = current.parent
    return current.parent if current.name == 'custom_nodes' else None

def check_and_patch_server():
    """检查并安装服务器补丁"""
    try:
        # 查找 ComfyUI 根目录
        comfyui_root = find_comfyui_root()
        if not comfyui_root:
            return False
        
        server_path = comfyui_root / "server.py"
        if not server_path.exists():
            return False
            
        # 读取文件内容
        with open(server_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # 检查是否已经安装了补丁
        if 'import server_patch' in content:
            print("[StartPatch] 补丁已经安装")
            return True
            
        # 修改正则表达式模式，匹配到最后一个路由处理函数
        pattern = r'(        @routes\.post\("/history"\).*?return web\.Response\(status=200\)\n\n)'
        match = re.search(pattern, content, re.DOTALL)
        
        if not match:
            return False
            
        # 准备补丁代码，确保正确的缩进
        patch_code = '''        from custom_nodes.Comfyui_StartPatch import server_patch
        server_patch.apply_patch(self)

'''
        
        # 在最后一个路由后添加补丁代码
        new_content = content.replace(
            match.group(1),
            match.group(1) + patch_code
        )
        
        # 备份原文件
        backup_path = server_path.with_suffix('.py.bak')
        if backup_path.exists():
            backup_path.unlink()
            
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # 写回文件
        with open(server_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
            
        print("[StartPatch] 补丁安装成功")
        return True
        
    except Exception as e:
        print(f"[StartPatch] 补丁安装失败: {str(e)}")
        return False

# 在预启动时自动执行
check_and_patch_server() 