"""
交互式反馈收集器 MCP 服务器
AI调用时会汇报工作内容，用户可以提供文本反馈和/或图片反馈
"""

import io
import base64
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
from PIL import Image, ImageTk
import threading
import queue
from pathlib import Path
from datetime import datetime
import os
import time # Import the time module

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.utilities.types import Image as MCPImage

# 创建MCP服务器
mcp = FastMCP(
    "交互式反馈收集器",
    dependencies=["pillow", "tkinter"]
)

# 配置超时时间（秒）
DEFAULT_DIALOG_TIMEOUT = 300  # 5分钟
try:
    DIALOG_TIMEOUT = int(os.getenv("MCP_DIALOG_TIMEOUT", DEFAULT_DIALOG_TIMEOUT))
    # 支持更长的超时时间，最大支持24小时
    if DIALOG_TIMEOUT > 86400:  # 24小时
        print(f"警告：超时时间过长 ({DIALOG_TIMEOUT}秒)，已限制为24小时")
        DIALOG_TIMEOUT = 86400
    print(f"MCP反馈收集器超时时间设置为: {DIALOG_TIMEOUT}秒 ({DIALOG_TIMEOUT//60}分钟)")
except ValueError as e:
    print(f"警告：无法解析MCP_DIALOG_TIMEOUT环境变量，使用默认值 {DEFAULT_DIALOG_TIMEOUT}秒: {e}")
    DIALOG_TIMEOUT = DEFAULT_DIALOG_TIMEOUT

class FeedbackDialog:
    def __init__(self, work_summary: str = "", timeout_seconds: int = DIALOG_TIMEOUT):
        self.result_queue = queue.Queue()
        self.root = None
        self.work_summary = work_summary
        self.timeout_seconds = timeout_seconds
        self.selected_images = []  # 改为支持多张图片
        self.image_preview_frame = None
        self.text_widget = None
        # 倒计时相关属性
        self.remaining_seconds = timeout_seconds
        self.countdown_label = None
        self.countdown_timer = None
        self.auto_timeout_message = "由于我现在有些忙,不能立即回复你,继续调用mcp-feedback-collector进行反馈,直到我主动回复你其他内容"
        
    def show_dialog(self):
        """在新线程中显示反馈收集对话框"""
        def run_dialog():
            self.root = tk.Tk()
            self.root.title("🎯 工作完成汇报与反馈收集")
            self.root.geometry("700x1150") # 增大窗口高度以容纳倒计时
            self.root.resizable(True, True)
            self.root.configure(bg="#f5f5f5")
            
            # 设置窗口图标和样式
            try:
                self.root.iconbitmap(default="")
            except:
                pass
            
            # --- 确保窗口显示和居中 --- #
            # 手动计算并设置窗口位置
            self.root.update_idletasks() # 更新窗口信息
            window_width = self.root.winfo_width()
            window_height = self.root.winfo_height()
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()

            x = (screen_width // 2) - (window_width // 2)
            y = (screen_height // 2) - (window_height // 2)

            self.root.geometry(f'{window_width}x{window_height}+{x}+{y}')
            
            # 确保窗口显示在前
            self.root.deiconify() # 如果窗口被最小化，恢复它
            self.root.lift()      # 将窗口带到顶部
            # self.root.attributes('-topmost', True) # 可选：使其置顶
            # self.root.after(500, lambda: self.root.attributes('-topmost', False)) # 可选：短暂置顶后取消 (500ms)
            
            # 绑定键盘快捷键
            # self.root.bind('<Return>', lambda event=None: self.submit_feedback()) # Enter键绑定提交
            self.root.bind('<Control-Return>', lambda event=None: self.submit_feedback()) # Ctrl+Enter键绑定提交
            self.root.bind('<Escape>', lambda event=None: self.cancel())   # Esc键绑定取消

            # 注意：Ctrl+V将直接绑定到text_widget以确保单次粘贴

            # 创建界面
            self.create_widgets()
            
            # 启动倒计时
            self.start_countdown()
            
            # 运行主循环
            self.root.mainloop()
            
        # 在新线程中运行对话框
        dialog_thread = threading.Thread(target=run_dialog)
        dialog_thread.daemon = True
        dialog_thread.start()
        
        # 等待结果，给内部倒计时额外的缓冲时间
        try:
            # 外部超时时间比内部倒计时多5秒，确保内部自动提交能够执行
            external_timeout = self.timeout_seconds + 5
            result = self.result_queue.get(timeout=external_timeout)
            return result
        except queue.Empty:
            return None
    
    def start_countdown(self):
        """启动倒计时"""
        self.update_countdown()
    
    def update_countdown(self):
        """更新倒计时显示"""
        if self.remaining_seconds <= 0:
            # 超时，自动提交
            self.auto_submit_on_timeout()
            return
        
        # 更新倒计时显示
        minutes = self.remaining_seconds // 60
        seconds = self.remaining_seconds % 60
        
        if self.remaining_seconds <= 60:
            # 最后1分钟，显示为红色
            countdown_text = f"⏰ 剩余时间：{seconds}秒"
            countdown_color = "#e74c3c"
        else:
            countdown_text = f"⏰ 剩余时间：{minutes}分{seconds:02d}秒"
            countdown_color = "#2c3e50"
        
        if self.countdown_label:
            self.countdown_label.config(text=countdown_text, fg=countdown_color)
        
        # 减少1秒
        self.remaining_seconds -= 1
        
        # 安排下次更新
        self.countdown_timer = self.root.after(1000, self.update_countdown)
    
    def auto_submit_on_timeout(self):
        """超时自动提交反馈"""
        # 清除占位符文本
        if self.text_widget.get(1.0, tk.END).strip() == "请在此输入您的反馈、建议或问题...":
            self.text_widget.delete(1.0, tk.END)
        
        # 插入自动超时消息
        self.text_widget.insert(1.0, self.auto_timeout_message)
        
        # 更新倒计时显示为超时状态
        if self.countdown_label:
            self.countdown_label.config(text="⏰ 已超时，自动提交反馈", fg="#e74c3c")
        
        # 自动提交反馈
        self.submit_feedback()
            
    def create_widgets(self):
        """创建美化的界面组件"""
        # 主框架
        main_frame = tk.Frame(self.root, bg="#f5f5f5")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        # 标题
        title_label = tk.Label(
            main_frame,
            text="🎯 工作完成汇报与反馈收集",
            font=("Microsoft YaHei", 16, "bold"),
            bg="#f5f5f5",
            fg="#2c3e50"
        )
        title_label.pack(pady=(0, 10))
        
        # 倒计时显示
        self.countdown_label = tk.Label(
            main_frame,
            text=f"⏰ 剩余时间：{self.timeout_seconds//60}分{self.timeout_seconds%60:02d}秒",
            font=("Microsoft YaHei", 12, "bold"),
            bg="#f5f5f5",
            fg="#2c3e50"
        )
        self.countdown_label.pack(pady=(0, 20))
        
        # 1. 工作汇报区域
        report_frame = tk.LabelFrame(
            main_frame, 
            text="📋 AI工作完成汇报", 
            font=("Microsoft YaHei", 12, "bold"),
            bg="#ffffff",
            fg="#34495e",
            relief=tk.RAISED,
            bd=2
        )
        report_frame.pack(fill=tk.X, pady=(0, 15))
        
        report_text = tk.Text(
            report_frame, 
            height=8, # 调整高度
            wrap=tk.WORD, 
            bg="#ecf0f1", 
            fg="#2c3e50",
            font=("Microsoft YaHei", 10),
            relief=tk.FLAT,
            bd=5,
            state=tk.DISABLED
        )
        report_text.pack(fill=tk.X, padx=15, pady=15)
        
        # 显示工作汇报内容
        report_text.config(state=tk.NORMAL)
        report_text.insert(tk.END, self.work_summary or "本次对话中完成的工作内容...")
        report_text.config(state=tk.DISABLED)
        
        # 2. 用户反馈文本区域
        feedback_frame = tk.LabelFrame(
            main_frame, 
            text="💬 您的文字反馈（可选）", 
            font=("Microsoft YaHei", 12, "bold"),
            bg="#ffffff",
            fg="#34495e",
            relief=tk.RAISED,
            bd=2
        )
        feedback_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        # 文本输入框
        self.text_widget = scrolledtext.ScrolledText(
            feedback_frame, 
            height=10, # 调整高度，为底部按钮腾出空间
            wrap=tk.WORD,
            font=("Microsoft YaHei", 10),
            bg="#ffffff",
            fg="#2c3e50",
            relief=tk.FLAT,
            bd=5,
            insertbackground="#3498db",
            undo=True
        )
        self.text_widget.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        self.text_widget.insert(tk.END, "请在此输入您的反馈、建议或问题...")
        self.text_widget.bind("<FocusIn>", self.clear_placeholder)
        self.text_widget.bind('<Control-v>', self.paste_handler) # 直接绑定到文本框
        self.text_widget.bind('<Control-V>', self.paste_handler) # 直接绑定到文本框
        
        # 3. 图片选择区域
        image_frame = tk.LabelFrame(
            main_frame, 
            text="🖼️ 图片反馈（可选，支持多张）", 
            font=("Microsoft YaHei", 12, "bold"),
            bg="#ffffff",
            fg="#34495e",
            relief=tk.RAISED,
            bd=2
        )
        image_frame.pack(fill=tk.X, pady=(0, 15))
        
        # 图片操作按钮
        btn_frame = tk.Frame(image_frame, bg="#ffffff")
        btn_frame.pack(fill=tk.X, padx=15, pady=10)
        
        # 美化的按钮样式
        btn_style = {
            "font": ("Microsoft YaHei", 10, "bold"),
            "relief": tk.FLAT,
            "bd": 0,
            "cursor": "hand2",
            "height": 2
        }
        
        tk.Button(
            btn_frame,
            text="📁 选择图片文件",
            command=self.select_image_file,
            bg="#3498db",
            fg="white",
            width=15,
            **btn_style
        ).pack(side=tk.LEFT, padx=(0, 8))
        
        tk.Button(
            btn_frame,
            text="📋 粘贴图片",
            command=self.paste_from_clipboard,
            bg="#2ecc71",
            fg="white",
            width=15,
            **btn_style
        ).pack(side=tk.LEFT, padx=4)
        
        tk.Button(
            btn_frame,
            text="❌ 清除所有图片",
            command=self.clear_all_images,
            bg="#e74c3c",
            fg="white",
            width=15,
            **btn_style
        ).pack(side=tk.LEFT, padx=8)
        
        # 图片预览区域（支持滚动）
        preview_container = tk.Frame(image_frame, bg="#ffffff")
        preview_container.pack(fill=tk.X, padx=15, pady=(0, 15))
        
        # 创建滚动画布
        canvas = tk.Canvas(preview_container, height=120, bg="#f8f9fa", relief=tk.SUNKEN, bd=1)
        scrollbar = tk.Scrollbar(preview_container, orient="horizontal", command=canvas.xview)
        self.image_preview_frame = tk.Frame(canvas, bg="#f8f9fa")
        
        self.image_preview_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=self.image_preview_frame, anchor="nw")
        canvas.configure(xscrollcommand=scrollbar.set)
        
        canvas.pack(side="top", fill="x")
        scrollbar.pack(side="bottom", fill="x")
        
        # 初始提示
        self.update_image_preview()
        
        # 4. 操作按钮
        button_frame = tk.Frame(main_frame, bg="#f5f5f5")
        button_frame.pack(fill=tk.X, pady=(15, 0))
        
        # 主要操作按钮
        submit_btn = tk.Button(
            button_frame,
            text="✅ 提交反馈 (Ctrl+Enter)",
            command=self.submit_feedback,
            font=("Microsoft YaHei", 12, "bold"),
            bg="#27ae60",
            fg="white",
            width=18,
            height=2,
            relief=tk.FLAT,
            bd=0,
            cursor="hand2"
        )
        submit_btn.pack(side=tk.LEFT, padx=(0, 15))
        
        cancel_btn = tk.Button(
            button_frame,
            text="❌ 取消 (Esc)",
            command=self.cancel,
            font=("Microsoft YaHei", 12),
            bg="#95a5a6",
            fg="white",
            width=18,
            height=2,
            relief=tk.FLAT,
            bd=0,
            cursor="hand2"
        )
        cancel_btn.pack(side=tk.LEFT)
        
        # 提示信息
        info_label = tk.Label(
            main_frame,
            text="💡 提示：文本粘贴请在文本框中使用 Ctrl+V，图片粘贴请使用上方按钮（支持多张图片）\n⏰ 超时后将自动提交固定反馈内容",
            font=("Microsoft YaHei", 9),
            fg="#7f8c8d",
            bg="#f5f5f5"
        )
        info_label.pack(pady=(15, 0))
        
    def clear_placeholder(self, event):
        """清除占位符文本"""
        if self.text_widget.get(1.0, tk.END).strip() == "请在此输入您的反馈、建议或问题...":
            self.text_widget.delete(1.0, tk.END)
            
    def select_image_file(self):
        """选择图片文件（支持多选）"""
        file_types = [
            ("图片文件", "*.png *.jpg *.jpeg *.gif *.bmp *.webp"),
            ("PNG文件", "*.png"),
            ("JPEG文件", "*.jpg *.jpeg"),
            ("所有文件", "*.*")
        ]
        
        file_paths = filedialog.askopenfilenames(
            title="选择图片文件（可多选）",
            filetypes=file_types
        )
        
        for file_path in file_paths:
            try:
                # 读取并验证图片
                with open(file_path, 'rb') as f:
                    image_data = f.read()
                
                img = Image.open(io.BytesIO(image_data))
                self.selected_images.append({
                    'data': image_data,
                    'source': f'文件: {Path(file_path).name}',
                    'size': img.size,
                    'image': img
                })
                
            except Exception as e:
                messagebox.showerror("错误", f"无法读取图片文件 {Path(file_path).name}: {str(e)}")
                
        self.update_image_preview()
                
    def paste_handler(self, event=None):
        """智能粘贴处理：优先粘贴图片，否则粘贴文本，并阻止默认行为"""
        try:
            from PIL import ImageGrab
            img = ImageGrab.grabclipboard()

            if img:
                # 尝试粘贴图片
                buffer = io.BytesIO()
                img.save(buffer, format='PNG')
                image_data = buffer.getvalue()

                self.selected_images.append({
                    'data': image_data,
                    'source': '剪贴板',
                    'size': img.size,
                    'image': img
                })
                self.update_image_preview()
                return "break"  # 阻止Tkinter默认的粘贴行为
            else:
                # 尝试粘贴文本
                text_content = self.root.clipboard_get()
                if text_content:
                    if self.text_widget.get(1.0, tk.END).strip() == "请在此输入您的反馈、建议或问题...":
                        self.text_widget.delete(1.0, tk.END)
                    self.text_widget.insert(tk.INSERT, text_content)
                    return "break"  # 阻止Tkinter默认的粘贴行为
        except Exception:
            # 捕获异常（如剪贴板内容无法识别），不做任何操作
            pass
        return None # 让Tkinter处理其他未被处理的粘贴事件

    def paste_from_clipboard(self):
        """从剪贴板粘贴图片（此方法现在仅为按钮点击服务，并调用paste_handler）"""
        self.paste_handler() # 调用智能粘贴处理方法
        
    def clear_all_images(self):
        """清除所有选择的图片"""
        self.selected_images = []
        self.update_image_preview()
        
    def update_image_preview(self):
        """更新图片预览显示"""
        # 清除现有预览
        for widget in self.image_preview_frame.winfo_children():
            widget.destroy()
            
        if not self.selected_images:
            # 显示未选择图片的提示
            no_image_label = tk.Label(
                self.image_preview_frame,
                text="未选择图片",
                bg="#f8f9fa",
                fg="#95a5a6",
                font=("Microsoft YaHei", 10)
            )
            no_image_label.pack(pady=20)
        else:
            # 显示所有图片预览
            for i, img_info in enumerate(self.selected_images):
                try:
                    # 创建单个图片预览容器
                    img_container = tk.Frame(self.image_preview_frame, bg="#ffffff", relief=tk.RAISED, bd=1)
                    img_container.pack(side=tk.LEFT, padx=5, pady=5)
                    
                    # 创建缩略图
                    img_copy = img_info['image'].copy()
                    img_copy.thumbnail((100, 80), Image.Resampling.LANCZOS)
                    
                    # 转换为tkinter可用的格式
                    photo = ImageTk.PhotoImage(img_copy)
                    
                    # 图片标签
                    img_label = tk.Label(img_container, image=photo, bg="#ffffff")
                    img_label.image = photo  # 保持引用
                    img_label.pack(padx=5, pady=5)
                    
                    # 图片信息
                    info_text = f"{img_info['source']}\n{img_info['size'][0]}x{img_info['size'][1]}"
                    info_label = tk.Label(
                        img_container,
                        text=info_text,
                        font=("Microsoft YaHei", 8),
                        bg="#ffffff",
                        fg="#7f8c8d"
                    )
                    info_label.pack(pady=(0, 5))
                    
                    # 删除按钮
                    del_btn = tk.Button(
                        img_container,
                        text="×",
                        command=lambda idx=i: self.remove_image(idx),
                        font=("Arial", 10, "bold"),
                        bg="#e74c3c",
                        fg="white",
                        width=3,
                        relief=tk.FLAT,
                        cursor="hand2"
                    )
                    del_btn.pack(pady=(0, 5))
                    
                except Exception as e:
                    print(f"预览更新失败: {e}")
                    
    def remove_image(self, index):
        """删除指定索引的图片"""
        if 0 <= index < len(self.selected_images):
            self.selected_images.pop(index)
            self.update_image_preview()
            
    def submit_feedback(self):
        """提交反馈"""
        # 停止倒计时
        if self.countdown_timer:
            self.root.after_cancel(self.countdown_timer)
            
        # 获取文本内容
        text_content = self.text_widget.get(1.0, tk.END).strip()
        if text_content == "请在此输入您的反馈、建议或问题...":
            text_content = ""
            
        # 检查是否有内容
        has_text = bool(text_content)
        has_images = bool(self.selected_images)
        
        if not has_text and not has_images:
            messagebox.showwarning("警告", "请至少提供文字反馈或图片反馈")
            # 重新启动倒计时
            self.start_countdown()
            return
            
        # 准备结果数据
        result = {
            'success': True,
            'text_feedback': text_content if has_text else None,
            'images': [img['data'] for img in self.selected_images] if has_images else None,
            'image_sources': [img['source'] for img in self.selected_images] if has_images else None,
            'has_text': has_text,
            'has_images': has_images,
            'image_count': len(self.selected_images),
            'timestamp': datetime.now().isoformat()
        }
        
        self.result_queue.put(result)
        self.root.destroy()
        
    def cancel(self):
        """取消操作"""
        # 停止倒计时
        if self.countdown_timer:
            self.root.after_cancel(self.countdown_timer)
            
        self.result_queue.put({
            'success': False,
            'message': '用户取消了反馈提交'
        })
        self.root.destroy()


@mcp.tool()
def collect_feedback(work_summary: str = "") -> list:
    """
    收集用户反馈的交互式工具。AI可以汇报完成的工作，用户可以提供文字和/或图片反馈。
    
    Args:
        work_summary: AI完成的工作内容汇报
        
    Returns:
        包含用户反馈内容的列表，可能包含文本和图片
    """
    dialog = FeedbackDialog(work_summary)
    result = dialog.show_dialog()
    
    if result is None:
        # 超时时自动返回固定的反馈内容，而不是抛出异常
        from mcp.types import TextContent
        auto_timeout_message = "由于我现在有些忙,不能立即回复你,继续调用mcp-feedback-collector进行反馈,直到我主动回复你其他内容"
        feedback_items = []
        feedback_items.append(TextContent(
            type="text", 
            text=f"用户文字反馈：{auto_timeout_message}\n提交时间：{datetime.now().isoformat()}\n状态：自动超时反馈"
        ))
        return feedback_items
        
    if not result['success']:
        raise Exception(result.get('message', '用户取消了反馈提交'))
    
    # 构建返回内容列表
    feedback_items = []
    
    # 添加文字反馈
    if result['has_text']:
        from mcp.types import TextContent
        feedback_items.append(TextContent(
            type="text", 
            text=f"用户文字反馈：{result['text_feedback']}\n提交时间：{result['timestamp']}"
        ))
        
    # 添加图片反馈
    if result['has_images']:
        for image_data, source in zip(result['images'], result['image_sources']):
            feedback_items.append(MCPImage(data=image_data, format='png'))
        
    return feedback_items


@mcp.tool()
def pick_image() -> MCPImage:
    """
    弹出图片选择对话框，让用户选择图片文件或从剪贴板粘贴图片。
    用户可以选择本地图片文件，或者先截图到剪贴板然后粘贴。
    """
    # 使用简化的对话框只选择图片
    dialog = FeedbackDialog()
    dialog.work_summary = "请选择一张图片"
    
    # 创建简化版本的图片选择对话框
    def simple_image_dialog():
        root = tk.Tk()
        root.title("选择图片")
        root.geometry("400x300")
        root.resizable(False, False)
        root.eval('tk::PlaceWindow . center')
        
        selected_image = {'data': None}
        
        def select_file():
            file_path = filedialog.askopenfilename(
                title="选择图片文件",
                filetypes=[("图片文件", "*.png *.jpg *.jpeg *.gif *.bmp *.webp")]
            )
            if file_path:
                try:
                    with open(file_path, 'rb') as f:
                        selected_image['data'] = f.read()
                    root.destroy()
                except Exception as e:
                    messagebox.showerror("错误", f"无法读取图片: {e}")
                    
        def paste_clipboard():
            try:
                from PIL import ImageGrab
                img = ImageGrab.grabclipboard()
                if img:
                    buffer = io.BytesIO()
                    img.save(buffer, format='PNG')
                    selected_image['data'] = buffer.getvalue()
                    root.destroy()
                else:
                    messagebox.showwarning("警告", "剪贴板中没有图片")
            except Exception as e:
                messagebox.showerror("错误", f"剪贴板操作失败: {e}")
                
        def cancel():
            root.destroy()
            
        # 界面
        tk.Label(root, text="请选择图片来源", font=("Arial", 14, "bold")).pack(pady=20)
        
        btn_frame = tk.Frame(root)
        btn_frame.pack(pady=20)
        
        tk.Button(btn_frame, text="📁 选择图片文件", font=("Arial", 12), 
                 width=20, height=2, command=select_file).pack(pady=10)
        tk.Button(btn_frame, text="📋 从剪贴板粘贴", font=("Arial", 12), 
                 width=20, height=2, command=paste_clipboard).pack(pady=10)
        tk.Button(btn_frame, text="❌ 取消", font=("Arial", 12), 
                 width=20, height=1, command=cancel).pack(pady=10)
        
        root.mainloop()
        return selected_image['data']
    
    image_data = simple_image_dialog()
    
    if image_data is None:
        raise Exception("未选择图片或操作被取消")
        
    return MCPImage(data=image_data, format='png')


@mcp.tool()
def get_image_info(image_path: str) -> str:
    """
    获取指定路径图片的信息（尺寸、格式等）
    
    Args:
        image_path: 图片文件路径
    """
    try:
        path = Path(image_path)
        if not path.exists():
            return f"文件不存在: {image_path}"
            
        with Image.open(path) as img:
            info = {
                "文件名": path.name,
                "格式": img.format,
                "尺寸": f"{img.width} x {img.height}",
                "模式": img.mode,
                "文件大小": f"{path.stat().st_size / 1024:.1f} KB"
            }
            
        return "\n".join([f"{k}: {v}" for k, v in info.items()])
        
    except Exception as e:
        return f"获取图片信息失败: {str(e)}"


if __name__ == "__main__":
    mcp.run()


def main():
    """Main entry point for the mcp-feedback-collector command."""
    mcp.run() 