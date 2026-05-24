import subprocess
import platform
import re

def test_connection(target: str):
    """
    专家级网络连通性诊断工具（集成 Ping 与 HTTP 检查）
    """
    try:
        # 1. 执行 Ping 检查 (探测基础链路)
        # 根据系统选择参数 (-c 为 Linux, -n 为 Windows)
        param = '-c' if platform.system().lower() != 'windows' else '-n'
        ping_cmd = ["ping", param, "3", "-W", "2", target]
        
        ping_status = "未知"
        avg_latency = "N/A"
        packet_loss = "100%"
        
        try:
            ping_output = subprocess.check_output(ping_cmd, stderr=subprocess.STDOUT, universal_newlines=True)
            # 提取延迟和丢包率 (兼容中英文输出)
            loss_match = re.search(r'(\d+)% packet loss', ping_output)
            latency_match = re.search(r'min/avg/max/mdev = [\d.]+/([\d.]+)', ping_output)
            
            if loss_match:
                packet_loss = loss_match.group(1) + "%"
            if latency_match:
                avg_latency = latency_match.group(1) + "ms"
            
            ping_status = "良好" if int(packet_loss.strip('%')) < 20 else "不稳定"
            if int(packet_loss.strip('%')) == 100: ping_status = "不可达"
            
        except subprocess.CalledProcessError:
            ping_status = "不可达"

        # 2. 执行 HTTP 检查 (探测应用响应)
        # 只尝试 HEAD 请求，节省流量和时间
        http_status = "N/A"
        try:
            # -I 仅获取请求头, -m 5 秒超时, -s 静默
            curl_cmd = ["curl", "-Is", "-m", "5", target]
            curl_output = subprocess.check_output(curl_cmd, stderr=subprocess.STDOUT, universal_newlines=True)
            first_line = curl_output.split('\n')[0]
            if "HTTP/" in first_line:
                http_status = first_line.split(' ')[1]
        except:
            http_status = "连接失败/无响应"

        # 3. 专家逻辑汇总
        if ping_status == "不可达":
            return f"成功 | 连通性测试结论：目标 {target} 基础链路不可达。请检查网络路由、物理连接或目标防火墙是否拦截了 ICMP 包。"
        
        status_map = {
            "200": "服务正常响应 (200 OK)",
            "403": "访问被拒绝 (403 Forbidden)，请检查权限配置",
            "404": "路径不存在 (404 Not Found)",
            "500": "服务器内部错误 (500 Internal Error)",
            "502": "网关错误/后端服务掉线 (502 Bad Gateway)",
            "503": "服务不可用 (503 Service Unavailable)"
        }
        http_desc = status_map.get(http_status, f"状态码: {http_status}")

        conclusion = (
            f"成功 | 连通性测试结论：基础链路状态{ping_status} (延迟: {avg_latency}, 丢包: {packet_loss})。 "
            f"应用层响应：{http_desc}。 "
            f"建议：如果基础链路通但应用层报错，请关注对应服务的业务逻辑或配置文件。"
        )
        return conclusion

    except Exception as e:
        return f"失败 | 连通性测试过程中发生错误: {str(e)}"