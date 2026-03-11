import jupyter_client
import queue
from nbformat.v4 import new_output

class UnifiedKernelSession:
    def __init__(self, kernel_name, timeout=60000):
        self.kernel_name = kernel_name
        self.timeout = timeout

        print(f">>> [系统] 正在启动内核: {kernel_name} ...")
        self.km = jupyter_client.KernelManager(kernel_name=kernel_name)
        # 如有需要，这里加 stdout=subprocess.PIPE 防止 Windows 报错
        self.km.start_kernel()

        self.kc = self.km.client()
        self.kc.start_channels()
        try:
            self.kc.wait_for_ready(timeout=10)
            print(f">>> [系统] {kernel_name} 内核启动就绪。")
        except RuntimeError:
            print(f">>> [系统] {kernel_name} 启动失败！")
            raise

    def run(self, code):
        """执行代码并获取输出"""
        msg_id = self.kc.execute(code)
        outputs = []
        error_occurred = False
        last_stream_output = None  # 跟踪最后一个 stream 输出

        while True:
            try:
                msg = self.kc.get_iopub_msg(timeout=self.timeout)
                if msg['parent_header'].get('msg_id') != msg_id: continue

                msg_type = msg['header']['msg_type']
                content = msg['content']

                if msg_type == 'status' and content['execution_state'] == 'idle':
                    break
                elif msg_type == 'stream':
                    text = content['text']
                    # 检查是否包含 \r（回车符，用于进度条等行内更新）
                    if '\r' in text:
                        if last_stream_output is not None:
                            # 替换最后一个 stream 输出（模拟 \r 的回车效果）
                            # 提取 \r 后的最后内容作为新行
                            last_line = text.split('\r')[-1]
                            last_stream_output.text = last_line
                        else:
                            # 如果没有之前的 stream 输出，直接添加
                            last_line = text.split('\r')[-1]
                            output = new_output('stream', name=content['name'], text=last_line)
                            outputs.append(output)
                            last_stream_output = output
                    else:
                        # 普通 stream 输出
                        output = new_output('stream', name=content['name'], text=text)
                        outputs.append(output)
                        last_stream_output = output
                elif msg_type in ('display_data', 'execute_result'):
                    # 非流输出，重置 last_stream_output
                    last_stream_output = None
                    outputs.append(new_output(msg_type, data=content['data'], metadata=content['metadata']))
                elif msg_type == 'error':
                    error_occurred = True
                    outputs.append(new_output('error', ename=content['ename'], evalue=content['evalue'], traceback=content['traceback']))
            except queue.Empty:
                error_occurred = True
                outputs.append(new_output('error', ename="timeout", evalue="Execution Timed Out", traceback=[]))
                break

        return outputs, error_occurred

    def shutdown(self):
        """优雅地关闭连接并清理对象，防止报错"""
        print(f">>> [系统] 正在注销 {self.kernel_name} 内核...")
        
        if hasattr(self, 'kc'):
            self.kc.stop_channels()
        
        if hasattr(self, 'km'):
            self.km.shutdown_kernel()

        # --- 强制垃圾回收清理，防止 TypeError: 'NoneType' object is not callable ---
        try:
            if hasattr(self, 'kc'): del self.kc
            if hasattr(self, 'km'): del self.km
        except:
            pass
        
        print(f">>> [系统] 内核已安全退出。")








        