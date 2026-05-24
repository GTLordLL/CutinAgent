import psutil

def check_network_port(port: int):
    """
    专家级网络端口监听诊断工具
    """
    try:
        # 确保 port 是整数
        port = int(port)
        found_conns = []
        
        # 遍历系统网络连接
        # kind='inet' 涵盖 IPv4 和 IPv6
        connections = psutil.net_connections(kind='inet')
        
        for conn in connections:
            # laddr 是 local address, raddr 是 remote address
            if conn.laddr and len(conn.laddr) >= 2 and conn.laddr[1] == port and conn.status == 'LISTEN':
                pid = conn.pid
                process_name = "未知 (可能需要sudo权限)"
                
                if pid:
                    try:
                        proc = psutil.Process(pid)
                        process_name = proc.name()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                
                found_conns.append({
                    "pid": pid,
                    "name": process_name,
                    "family": "IPv4" if conn.family == 2 else "IPv6"
                })

        # 专家结论逻辑
        if not found_conns:
            return f"成功 | 端口 {port} 当前未被任何进程监听。如果业务本应启动，请检查服务运行状态。"

        # 如果有多个监听（例如同时监听了 IPv4/v6）
        pids = list(set([str(c['pid']) for c in found_conns]))
        names = list(set([c['name'] for c in found_conns]))
        
        conclusion = (
            f"成功 | 端口 {port} 正在被正常监听。"
            f"占用进程: {' / '.join(names)} (PID: {' / '.join(pids)})。"
            f"结论: 端口状态正常，若外部无法访问，请检查防火墙规则。"
        )
        return conclusion

    except Exception as e:
        return f"失败 | 端口扫描出错: {str(e)}"