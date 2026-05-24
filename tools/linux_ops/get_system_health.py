import psutil
import os

def get_system_health(target="all", path="/"):
    """
    专家级系统健康诊断工具
    """
    try:
        report = []
        target = target.lower()

        # 1. CPU 诊断
        if target in ["all", "cpu"]:
            cpu_usage = psutil.cpu_percent(interval=0.5)
            status = "正常" if cpu_usage < 80 else "过载[需关注]"
            report.append(f"CPU使用率: {cpu_usage}% ({status})")

        # 2. 负载诊断 (针对小模型优化版)
        if target in ["all", "load"]:
            load1, load5, load15 = psutil.getloadavg()
            raw_cpu_count = psutil.cpu_count()
            cpu_count = raw_cpu_count if raw_cpu_count is not None else 1
            
            # 计算利用率百分比，让模型更直观理解
            load_usage_pct = round((load1 / cpu_count) * 100, 2)
            
            # 趋势分析：比较 1分钟 和 15分钟 负载
            if load1 > load15 * 1.2:
                trend = "上升趋势"
            elif load1 < load15 * 0.8:
                trend = "下降趋势"
            else:
                trend = "平稳"

            status = "正常" if (load1 / cpu_count) < 0.7 else "负载较高"
            
            # 核心优化：提供保留2位小数的数值，并增加语义化描述
            load_msg = (
                f"系统平均负载: [1min:{load1:.2f}, 5min:{load5:.2f}, 15min:{load15:.2f}] "
                f"(当前核心利用率: {load_usage_pct}%, 压力趋势: {trend}, 状态: {status})"
            )
            report.append(load_msg)

        # 3. 内存诊断
        if target in ["all", "mem"]:
            mem = psutil.virtual_memory()
            status = "正常" if mem.percent < 90 else "内存紧缺"
            report.append(f"内存占用: {mem.percent}% (可用: {mem.available // (1024**2)}MB, 状态: {status})")

        # 4. 磁盘诊断
        if target in ["all", "disk"]:
            if os.path.exists(path):
                usage = psutil.disk_usage(path)
                status = "正常" if usage.percent < 85 else "空间不足[警告]"
                report.append(f"磁盘({path}): {usage.percent}% (剩余: {usage.free // (1024**3)}GB, 状态: {status})")
            else:
                return f"失败 | 指定路径 {path} 不存在"

        # 组装最终结论
        header = f"[{target.upper()}专项报告]" if target != "all" else "[系统全局概览]"
        conclusion = f"成功 | {header} " + " | ".join(report)
        return conclusion

    except Exception as e:
        return f"失败 | 诊断过程中发生异常: {str(e)}"