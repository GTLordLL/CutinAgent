import subprocess
import os

def locate_large_files(path: str = "/", limit: int = 10):
    """
    专家级大文件定位工具
    """
    try:
        # 1. 前置安全检查与参数预处理
        if not os.path.exists(path):
            return f"失败 | 路径 {path} 不存在。"
        
        # 限制 limit，防止输出过长
        limit = min(max(int(limit), 1), 20)

        # 2. 执行专家检索逻辑
        # 使用 du 命令，同时排除虚拟文件系统，提高准确性
        # -a: 显示所有文件和目录, -h: 易读格式, -x: 跳过不同文件系统的目录
        # 结合 sort -rh 降序排列
        
        # 专家命令构造 (注意：这里使用 -x 参数非常重要，避免扫描 /proc 等挂载点)
        cmd = f"du -ahx {path} 2>/dev/null | sort -rh | head -n {limit}"
        
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT, universal_newlines=True)
            
            if not output.strip():
                return f"成功 | 在路径 {path} 下未发现明显的可扫描文件。"

            # 3. 结果解析与定性分析
            lines = output.strip().split('\n')
            
            # 获取最大文件的大小进行专家评估
            top_file_info = lines[0].split('\t')
            top_size = top_file_info[0]
            top_name = top_file_info[1]

            # 简单的专家逻辑：如果最大文件超过 1GB，给出清理建议
            is_huge = 'G' in top_size or ('M' in top_size and int(top_size.split('M')[0]) > 500)
            
            summary = ""
            if is_huge:
                if "log" in top_name.lower():
                    summary = f"警告：发现超大日志文件 {top_name} ({top_size})，建议检查日志轮转配置或手动压缩。"
                elif "temp" in top_name.lower() or "tmp" in top_name.lower():
                    summary = f"建议：发现较大临时文件 {top_name} ({top_size})，可能可以安全删除。"
                else:
                    summary = f"发现显着占用文件 {top_name} ({top_size})，请确认其用途。"
            else:
                summary = "当前目录下文件大小分布相对均匀，未发现极端异常的单体文件。"

            # 构建精简的条目列表（供迭代使用）
            compact_items = []
            for line in lines:
                parts = line.split('\t', 1)
                if len(parts) == 2:
                    compact_items.append(f"{parts[1]}({parts[0]})")
            items_text = ", ".join(compact_items)

            return (
                f"成功 | [大文件扫描报告: {path}] 结论: {summary} 占用列表({len(lines)}项): {items_text}\n"
                f"[DETAIL]\n"
                f"--- Top {limit} 占用列表 ---\n"
                f"{output.strip()}"
            )

        except subprocess.CalledProcessError as e:
            return f"失败 | 执行磁盘扫描时出错: {str(e)}"

    except Exception as e:
        return f"失败 | 大文件工具崩溃: {str(e)}"