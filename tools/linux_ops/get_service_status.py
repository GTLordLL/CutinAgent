import subprocess

def get_service_status(service_name: str):
    """
    专家级 systemd 服务诊断工具
    """
    try:
        # 1. 获取服务基本状态 (Active/Inactive/Failed)
        # 使用 --no-pager 避免进入交互模式
        status_cmd = ["systemctl", "status", service_name, "--no-pager"]
        
        try:
            status_output = subprocess.check_output(status_cmd, stderr=subprocess.STDOUT, universal_newlines=True)
        except subprocess.CalledProcessError as e:
            # systemctl status 在服务 dead/failed 时会返回非0码，所以需要捕获输出
            status_output = e.output

        # 2. 解析关键状态位
        is_active = "active (running)" in status_output
        is_failed = "failed" in status_output or "dead" in status_output
        
        # 提取 Main PID (如果有)
        import re
        pid_match = re.search(r"Main PID: (\d+)", status_output)
        pid_str = pid_match.group(1) if pid_match else "未知"

        # 3. 获取最近 20 行错误日志 (Journalctl)
        # -u 指定服务, -n 20 最近20行, --no-pager
        log_cmd = ["journalctl", "-u", service_name, "-n", 20, "--no-pager"]
        try:
            log_output = subprocess.check_output(log_cmd, stderr=subprocess.STDOUT, universal_newlines=True)
        except:
            log_output = "无法获取日志内容。"

        # 4. 专家逻辑汇总
        status_desc = "运行中" if is_active else "已停止/异常"
        if is_failed: status_desc = "启动失败 (Failed)"

        # 寻找日志中的关键错误信号
        error_keywords = ["error", "failed", "denied", "address already in use", "timeout", "panic"]
        found_errors = []
        matched_keywords = set()
        for line in log_output.lower().split('\n'):
            for key in error_keywords:
                if key in line:
                    found_errors.append(line.strip())
                    matched_keywords.add(key)

        error_summary = "发现异常日志：" + " | ".join(found_errors[-3:]) if found_errors else "暂未发现明显错误关键字。"
        kw_text = ", ".join(sorted(matched_keywords)) if matched_keywords else "无"

        diagnosis = '服务运行正常' if is_active and not found_errors else '服务可能存在配置或资源问题'
        return (
            f"成功 | [服务诊断: {service_name}] 状态: {status_desc} (PID: {pid_str})。"
            f"诊断结论: {diagnosis}。匹配错误关键字: {kw_text}\n"
            f"[DETAIL]\n"
            f"最近关键日志: {error_summary}"
        )

    except Exception as e:
        return f"失败 | 服务诊断过程出错: {str(e)}"