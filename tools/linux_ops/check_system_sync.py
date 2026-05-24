import subprocess
import datetime

def check_system_sync():
    """
    专家级系统时间与同步状态诊断工具
    """
    try:
        # 获取本地时间
        local_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        timezone = subprocess.check_output(["date", "+%Z"], universal_newlines=True).strip()
        
        # 检查 NTP 同步状态 (使用 timedatectl)
        sync_status = "未知"
        try:
            ntp_output = subprocess.check_output(["timedatectl", "show"], universal_newlines=True)
            # 查找 NTP 是否同步
            is_synced = "NTPSynchronized=yes" in ntp_output
            sync_status = "已同步" if is_synced else "未同步/正在同步"
        except:
            sync_status = "无法获取(timedatectl不可用)"

        time_judgment = '时间状态正常' if sync_status == '已同步' else '警告：系统时间可能未同步，这可能导致证书校验失败或分布式日志错乱。'
        return (
            f"成功 | [系统时间诊断] 结论: {time_judgment}\n"
            f"[DETAIL]\n"
            f"当前时间: {local_time} {timezone}\n"
            f"NTP同步状态: {sync_status}"
        )
    except Exception as e:
        return f"失败 | 检查时间同步出错: {str(e)}"