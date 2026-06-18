import psutil

def list_top_processes(sort_by="cpu", limit=5):
    """
    专家级进程占用诊断工具
    """
    try:
        processes = []
        # 注意：qwen3:4b 可能会传 'cpu' 或 'mem'，我们需要映射到 psutil 的属性名
        attr_map = {
            "cpu": "cpu_percent",
            "mem": "memory_percent"
        }
        sort_attr = attr_map.get(sort_by.lower(), "cpu_percent")

        # 预热：psutil.cpu_percent 首次调用总是返回 0（需要两次采样间的差值）
        psutil.cpu_percent(interval=0.1)

        # 遍历进程
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try:
                processes.append(proc.info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        # 排序
        processes.sort(key=lambda x: x[sort_attr], reverse=True)
        top_list = processes[:limit]

        # 专家分析结论
        if not top_list:
            return {"status": "失败", "summary": "无法获取进程信息", "detail": ""}

        # 识别"首犯"
        leader = top_list[0]
        leader_val = leader[sort_attr]

        # 阈值判断：如果第一名占用显著（比如CPU > 50% 或 内存 > 30%）
        is_anomaly = (sort_by == "cpu" and leader_val > 50) or (sort_by == "mem" and leader_val > 30)

        # 构造展示列表
        detail_lines = [
            f"PID: {p['pid']} | Name: {p['name']} | CPU: {p['cpu_percent']}% | MEM: {p['memory_percent']:.1f}%"
            for p in top_list
        ]

        anomaly_summary = f"发现异常高耗能进程 '{leader['name']}'(PID: {leader['pid']})，请重点排查。" if is_anomaly else "各进程资源占用处于正常区间。"

        return {
            "status": "成功",
            "summary": f"[进程专项诊断-{sort_by.upper()}] {anomaly_summary}",
            "detail": f"Top {limit} 列表：\n" + "\n".join(detail_lines),
        }

    except Exception as e:
        return {"status": "失败", "summary": f"进程分析崩溃: {str(e)}", "detail": ""}
