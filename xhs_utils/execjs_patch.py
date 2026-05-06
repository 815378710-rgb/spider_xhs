"""
execjs Node.js 运行时补丁
解决 Windows Git Bash 环境下 execjs 无法自动发现 node 的问题
必须在任何 import execjs 之前调用
"""
import os
import sys


def patch_execjs():
    """手动注册 Node.js 运行时到 execjs"""
    node_cmd = r"D:\node.exe"
    if not os.path.exists(node_cmd):
        return
    
    # 设置 NODE_PATH 让 node 能找到 crypto-js 等依赖
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    node_modules = os.path.join(project_root, "node_modules")
    if os.path.isdir(node_modules) and "NODE_PATH" not in os.environ:
        os.environ["NODE_PATH"] = node_modules
    
    import execjs
    import execjs._runner_sources as runner_sources
    from execjs._external_runtime import ExternalRuntime
    
    # 检查 Node 是否已经可用
    for name, rt in execjs._runtimes._runtimes:
        if name == "Node" and rt.is_available():
            return
    
    # 手动注册 Node 运行时
    node_rt = ExternalRuntime("Node", [node_cmd], runner_sources.Node)
    node_rt._available = True
    execjs._runtimes._runtimes.insert(0, ("Node", node_rt))


# 自动执行
patch_execjs()
