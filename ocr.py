import requests
import os
import base64
import tkinter as tk
from tkinter import filedialog, scrolledtext, messagebox, simpledialog, Menu, ttk
from pathlib import Path
from urllib.parse import quote_plus
from PIL import Image
import threading
import json
from datetime import datetime
import pandas as pd
import re
import random
import copy
import hashlib

plt = None
FigureCanvasTkAgg = None
NavigationToolbar2Tk = None
LassoSelector = None
MplPath = None
font_manager = None
_matplotlib_loaded = False

# 加载 .env 文件
env_path = Path(__file__).parent / '.env'
if env_path.exists():
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key.strip()] = value.strip()

# 高精度识别的密钥
API_KEY = os.getenv("BAIDU_API_KEY", "")
SECRET_KEY = os.getenv("BAIDU_SECRET_KEY", "")

# 快速识别的密钥（必须单独配置）
API_KEY_BASIC = os.getenv("BAIDU_API_KEY_BASIC", "")
SECRET_KEY_BASIC = os.getenv("BAIDU_SECRET_KEY_BASIC", "")

# 通用识别的密钥（必须单独配置）
API_KEY_GENERAL = os.getenv("BAIDU_API_KEY_GENERAL", "")
SECRET_KEY_GENERAL = os.getenv("BAIDU_SECRET_KEY_GENERAL", "")


# === 字体配置 (Windows 环境) ===
def configure_styles_force():
    plt.rcParams['axes.unicode_minus'] = False
    font_paths = [r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\msyh.ttf", r"C:\Windows\Fonts\simhei.ttf"]
    font_loaded = False
    for path in font_paths:
        if os.path.exists(path):
            try:
                font_manager.fontManager.addfont(path)
                font_name = font_manager.FontProperties(fname=path).get_name()
                plt.rcParams['font.sans-serif'] = [font_name]
                font_loaded = True
                break
            except:
                pass
    if not font_loaded:
        plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Arial Unicode MS']


def ensure_matplotlib_loaded():
    """延迟加载 matplotlib，避免拖慢软件首次打开。"""
    global plt, FigureCanvasTkAgg, NavigationToolbar2Tk, LassoSelector, MplPath, font_manager, _matplotlib_loaded
    if _matplotlib_loaded:
        return

    import matplotlib.pyplot as _plt
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg as _FigureCanvasTkAgg
    from matplotlib.backends.backend_tkagg import NavigationToolbar2Tk as _NavigationToolbar2Tk
    from matplotlib.widgets import LassoSelector as _LassoSelector
    from matplotlib.path import Path as _MplPath
    from matplotlib import font_manager as _font_manager

    plt = _plt
    FigureCanvasTkAgg = _FigureCanvasTkAgg
    NavigationToolbar2Tk = _NavigationToolbar2Tk
    LassoSelector = _LassoSelector
    MplPath = _MplPath
    font_manager = _font_manager
    configure_styles_force()
    _matplotlib_loaded = True


_token_cache = {}

def get_access_token(use_basic=False, use_general=False):
    """
    使用 AK，SK 生成鉴权签名（Access Token），带缓存，过期自动刷新
    :param use_basic: 是否使用快速识别的密钥
    :param use_general: 是否使用通用识别的密钥
    :return: access_token，或是None(如果错误)
    """
    import time
    cache_key = 'general' if use_general else 'basic' if use_basic else 'accurate'
    cached = _token_cache.get(cache_key)
    if cached and cached['expires'] > time.time():
        return cached['token']

    url = "https://aip.baidubce.com/oauth/2.0/token"
    if use_general:
        params = {"grant_type": "client_credentials", "client_id": API_KEY_GENERAL, "client_secret": SECRET_KEY_GENERAL}
    elif use_basic:
        params = {"grant_type": "client_credentials", "client_id": API_KEY_BASIC, "client_secret": SECRET_KEY_BASIC}
    else:
        params = {"grant_type": "client_credentials", "client_id": API_KEY, "client_secret": SECRET_KEY}

    resp = requests.post(url, params=params).json()
    token = resp.get("access_token")
    expires_in = resp.get("expires_in", 2592000)  # 百度默认30天
    _token_cache[cache_key] = {
        'token': token,
        'expires': time.time() + expires_in - 300  # 提前5分钟过期
    }
    return str(token)


def get_file_content_as_base64(path, max_size=8192, max_file_size_mb=3.5):
    """将图片文件转换为 base64 编码，自动压缩大图片和大文件"""
    try:
        # 检查原始文件大小
        file_size = os.path.getsize(path)
        file_size_mb = file_size / (1024 * 1024)
        
        # 打开图片
        img = Image.open(path)
        width, height = img.size
        
        # 判断是否需要压缩（尺寸过大或文件过大）
        need_compress = (width > max_size or height > max_size or file_size_mb > max_file_size_mb)
        
        if need_compress:
            print(f"图片需要压缩: 尺寸({width}x{height}) 文件大小({file_size_mb:.1f}MB)")
            
            # 计算目标尺寸
            if width > max_size or height > max_size:
                # 按尺寸压缩
                scale = min(max_size / width, max_size / height)
                new_width = int(width * scale)
                new_height = int(height * scale)
            else:
                # 按文件大小压缩（保持尺寸，降低质量）
                new_width = width
                new_height = height
            
            # 压缩图片
            if new_width != width or new_height != height:
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                print(f"尺寸压缩: {width}x{height} → {new_width}x{new_height}")
            
            # 转换为字节流并调整质量
            import io
            img_byte_arr = io.BytesIO()
            
            # 根据文件大小动态调整质量
            quality = 85
            if file_size_mb > 10:
                quality = 60
            elif file_size_mb > 5:
                quality = 70
            elif file_size_mb > 3:
                quality = 80
            
            img.save(img_byte_arr, format='JPEG', quality=quality, optimize=True)
            compressed_data = img_byte_arr.getvalue()
            compressed_size_mb = len(compressed_data) / (1024 * 1024)
            
            print(f"压缩完成: {file_size_mb:.1f}MB → {compressed_size_mb:.1f}MB (质量:{quality})")
            
            # 如果压缩后仍然太大，进一步降低质量
            if compressed_size_mb > max_file_size_mb:
                for lower_quality in [50, 40, 30, 20]:
                    img_byte_arr = io.BytesIO()
                    img.save(img_byte_arr, format='JPEG', quality=lower_quality, optimize=True)
                    compressed_data = img_byte_arr.getvalue()
                    compressed_size_mb = len(compressed_data) / (1024 * 1024)
                    print(f"进一步压缩: 质量{lower_quality} → {compressed_size_mb:.1f}MB")
                    if compressed_size_mb <= max_file_size_mb:
                        break
            
            return base64.b64encode(compressed_data).decode("utf8")
        else:
            # 图片尺寸和文件大小都合适，直接读取
            print(f"图片无需压缩: 尺寸({width}x{height}) 文件大小({file_size_mb:.1f}MB)")
            with open(path, "rb") as f:
                return base64.b64encode(f.read()).decode("utf8")
    
    except Exception as e:
        print(f"处理图片时出错: {e}")
        # 如果出错，尝试使用原始方法
        try:
            with open(path, "rb") as f:
                return base64.b64encode(f.read()).decode("utf8")
        except:
            return None


def ocr_image(image_path):
    """对图片进行 OCR 识别（高精度版）"""
    url = "https://aip.baidubce.com/rest/2.0/ocr/v1/accurate?access_token=" + get_access_token()
    
    # 高精度识别使用较宽松的文件大小限制
    image_base64 = get_file_content_as_base64(image_path, max_size=8192, max_file_size_mb=3.8)
    
    if image_base64 is None:
        return {"error_msg": "图片处理失败", "error_code": -1}
    
    # 需要获取位置信息，所以不关闭 location
    payload = {
        'image': image_base64,
        'detect_direction': 'false',
        'paragraph': 'false',
        'probability': 'false',
        'char_probability': 'false',
        'multidirectional_recognize': 'false'
    }
    
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept': 'application/json'
    }
    
    response = requests.post(url, headers=headers, data=payload)
    response.encoding = "utf-8"
    return response.json()


def ocr_image_basic(image_path):
    """对图片进行 OCR 识别（快速版 - general，含位置信息）"""
    url = "https://aip.baidubce.com/rest/2.0/ocr/v1/general?access_token=" + get_access_token(use_basic=True)

    image_base64 = get_file_content_as_base64(image_path, max_size=8100, max_file_size_mb=3.5)

    if image_base64 is None:
        return {"error_msg": "图片处理失败", "error_code": -1}

    payload = {
        'image': image_base64,
        'detect_direction': 'false',
        'paragraph': 'false',
        'probability': 'false',
    }

    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept': 'application/json'
    }
    
    response = requests.post(url, headers=headers, data=payload)
    response.encoding = "utf-8"
    return response.json()


def ocr_image_general(image_path):
    """对图片进行 OCR 识别（通用版 - accurate_basic，使用通用识别密钥）"""
    url = "https://aip.baidubce.com/rest/2.0/ocr/v1/accurate_basic?access_token=" + get_access_token(use_general=True)

    image_base64 = get_file_content_as_base64(image_path, max_size=8100, max_file_size_mb=3.5)

    if image_base64 is None:
        return {"error_msg": "图片处理失败", "error_code": -1}

    payload = {
        'image': image_base64,
        'detect_direction': 'false',
        'paragraph': 'false',
        'probability': 'false',
        'multidirectional_recognize': 'false'
    }

    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept': 'application/json'
    }

    response = requests.post(url, headers=headers, data=payload)
    response.encoding = "utf-8"
    return response.json()



class DataStore:
    """统一数据存储管理器"""
    def __init__(self, filepath):
        self.filepath = filepath
        self.data = {
            'window_config': {},
            'stats': {},
            'history': [],
            'history_limit': 100,
            'ocr_cache': {},
            'size_limits': {},
            'font_config': {'font_size': 11},
            'popup_windows': {}
        }
        self.load()

    def load(self):
        if self.filepath.exists():
            try:
                with open(self.filepath, 'r', encoding='utf-8') as f:
                    saved = json.load(f)
                    # 深度合并或更新，这里简单更新顶层键
                    for k, v in saved.items():
                        self.data[k] = v
            except Exception as e:
                print(f"加载数据文件失败: {e}")

    def save(self):
        try:
            with open(self.filepath, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存数据文件失败: {e}")

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value
        self.save()

    def migrate_legacy_files(self, parent_dir):
        """从旧的分散文件迁移数据"""
        legacy_files = {
            'window_config': 'window_config.json',
            'stats': 'ocr_stats.json',
            'history': 'ocr_history.json',
            'history_limit': 'history_limit.json',
            'size_limits': 'size_limits.json',
            'font_config': 'font_config.json',
            'popup_windows': 'popup_windows.json'
        }
        
        migrated = False
        for key, filename in legacy_files.items():
            path = parent_dir / filename
            if path.exists():
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        content = json.load(f)
                        # 特殊处理 history_limit 格式
                        if key == 'history_limit' and isinstance(content, dict):
                            self.data[key] = content.get('limit', 100)
                        else:
                            self.data[key] = content
                    print(f"✓ 已迁移旧文件: {filename}")
                    migrated = True
                    
                    # 可选：重命名旧文件作为备份
                    # try:
                    #     path.rename(path.with_suffix('.json.bak'))
                    # except: pass
                except Exception as e:
                    print(f"迁移 {filename} 失败: {e}")
        
        if migrated:
            self.save()
            print("✓ 数据迁移完成，已保存到 ocr_data.json")


class OCRApp:
    def __init__(self, root):
        self.root = root
        self.root.title("OCR 数据分类工具")
        

        # 数据存储初始化
        self.data_file = Path(__file__).parent / 'ocr_data.json'
        self.store = DataStore(self.data_file)
        
        # 如果数据文件不存在，尝试迁移旧数据
        if not self.data_file.exists():
            self.store.migrate_legacy_files(Path(__file__).parent)
        
        # 加载并应用窗口配置
        self.load_window_config()
        
        self.root.minsize(1200, 800)  # 设置最小尺寸，防止窗口过小
        
        # 绑定窗口关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # 统计数据
        self.stats = self.store.get('stats', {})
        self.stats_count_cache_as_success = self.store.get('stats_count_cache_as_success', False)
        
        # 历史记录
        self.history_limit = self.store.get('history_limit', 100)
        self.history_data = self.store.get('history', [])
        self._pending_history_book_page = None
        self._suppress_book_page_trace = False
        
        # 尺寸限制解锁状态
        self.size_limit_unlocked = False
        self.unlock_password = "000"  # 设置密码
        
        # 图片尺寸限制配置（可自定义）- 使用范围限制
        self.size_limits = {
            'accurate_min_width': 3500,    # 高精度最小宽度
            'accurate_min_height': 4000,   # 高精度最小高度
            'accurate_max_width': 15000,   # 高精度最大宽度
            'accurate_max_height': 15000,  # 高精度最大高度
            'basic_min_width': 0,          # 快速识别最小宽度
            'basic_min_height': 0,         # 快速识别最小高度
            'basic_max_width': 8100,       # 快速识别最大宽度
            'basic_max_height': 3000,      # 快速识别最大高度
            'general_min_width': 0,        # 通用识别最小宽度
            'general_min_height': 0,       # 通用识别最小高度
            'general_max_width': 8192,     # 通用识别最大宽度
            'general_max_height': 8192     # 通用识别最大高度
        }
        self.load_size_limits()
        
        # 数据分类相关属性
        self.current_font_size = 11  # 默认字号
        self.font_config_file = Path(__file__).parent / 'font_config.json'  # 字号配置文件
        self.load_font_config()  # 加载保存的字号设置
        
        # 空格规则配置
        self.space_config_file = Path(__file__).parent / 'space_rules_config.json'
        self.space_presets = {}  # 用户保存的空格规则预设
        self.load_space_config()  # 加载空格规则配置
        
        # 字体样式配置
        self.font_style_rules = {}  # 字体样式规则：{前缀: {样式配置}}
        self.load_font_style_config()  # 加载字体样式配置

        # 过滤清理规则
        self.filter_rules = []  # 用户配置的过滤词/符号列表
        self.load_filter_config()  # 加载过滤规则

        # 替换规则
        self.replace_rules = []  # [{find: str, replace: str}, ...]
        self.load_replace_config()

        # 报告分隔方式：'line'=----分隔线，'blank'=空行
        self.report_separator = 'line'
        self.report_format = 'legacy'
        self.df = pd.DataFrame(columns=['Label', 'Y', 'X', 'Group', 'Order'])
        self.thresholds = []
        self.category_list = []
        self.marked_indices = set()
        self.custom_cat_names = {}
        self.drag_source_item = None
        self.drag_source_index = None
        self.drag_indicator = None
        self.undo_stack = []
        self.redo_stack = []
        self._pending_snapshot = None
        self.parsed_snapshot = None
        self.undo_limit = 30
        self.enable_lasso_mode = tk.BooleanVar(value=False)
        self.color_cycle = ['#FF0000', '#00AA00', '#FF8C00', '#9400D3', '#0000FF', '#00CED1']
        self.lasso = None
        self.plot_initialized = False
        self.fig = None
        self.ax = None
        self.canvas = None
        
        # 创建主界面
        self.setup_main_interface()
        
        # 启用拖放功能
        self._setup_drag_drop()
        
        # 检查数据文件大小（延迟执行，避免影响启动速度）
        self.root.after(2000, self.check_data_file_size)

    def setup_main_interface(self):
        """设置主界面 — 左侧导航栏 + 顶部标题栏 + 右侧主体"""
        self.root.configure(bg='#F0F4F8')

        # ── 顶部标题栏 ──
        title_bar = tk.Frame(self.root, bg='white', height=48,
                             highlightthickness=1, highlightbackground='#E5E7EB')
        title_bar.pack(fill=tk.X, side=tk.TOP)
        title_bar.pack_propagate(False)

        # logo + 标题
        tk.Label(title_bar, text='C', bg='#1A6FD4', fg='white',
                 font=('Microsoft YaHei', 13, 'bold'),
                 padx=8, pady=4).pack(side=tk.LEFT, padx=(10, 6), pady=10)
        tk.Label(title_bar, text='OCR 数据分类工具', bg='white', fg='#111827',
                 font=('Microsoft YaHei', 12, 'bold')).pack(side=tk.LEFT, pady=6)

        # 右侧按钮区
        def _title_btn(parent, text, cmd, fg='#374151'):
            b = tk.Label(parent, text=text, bg='white', fg=fg,
                         font=('Microsoft YaHei', 9), cursor='hand2', padx=10)
            b.pack(side=tk.RIGHT, pady=10)
            b.bind('<Button-1>', lambda e: cmd())
            b.bind('<Enter>', lambda e: b.config(fg='#1A6FD4'))
            b.bind('<Leave>', lambda e: b.config(fg=fg))
            return b

        _title_btn(self.root.nametowidget(title_bar) if False else title_bar,
                   '?  帮助', lambda: messagebox.showinfo('帮助', '使用左侧导航切换功能页面'))
        _title_btn(title_bar, '⚙  设置', self.show_api_key_settings)
        _title_btn(title_bar, '☆  主题', lambda: None)

        # 分隔线
        tk.Frame(title_bar, bg='#E5E7EB', width=1).pack(side=tk.RIGHT, fill=tk.Y, pady=8, padx=4)

        _title_btn(title_bar, '📋  导入数据', self._show_import_dialog, fg='#1A6FD4')
        _title_btn(title_bar, '↺  重置', self.clear_all_data)

        tk.Frame(title_bar, bg='#E5E7EB', width=1).pack(side=tk.RIGHT, fill=tk.Y, pady=8, padx=4)

        # 字号选择
        font_frame = tk.Frame(title_bar, bg='white')
        font_frame.pack(side=tk.RIGHT, padx=4, pady=8)
        tk.Label(font_frame, text='字号', bg='white', fg='#374151',
                 font=('Microsoft YaHei', 9)).pack(side=tk.LEFT, padx=(0, 4))
        self.combo_font = ttk.Combobox(font_frame, values=[str(i) for i in range(8, 31)],
                                       width=4, state='readonly',
                                       font=('Microsoft YaHei', 9))
        self.combo_font.set(str(self.current_font_size))
        self.combo_font.pack(side=tk.LEFT)
        self.combo_font.bind('<<ComboboxSelected>>', self.on_font_combo_change)

        # ── 主体：左侧导航 + 右侧内容 ──
        body = tk.Frame(self.root, bg='#F7F9FC')
        body.pack(fill=tk.BOTH, expand=True)

        # ── 左侧导航栏 ──
        nav_bg = '#FFFFFF'
        nav = tk.Frame(body, bg=nav_bg, width=130,
                       highlightthickness=1, highlightbackground='#E5E7EB')
        nav.pack(side=tk.LEFT, fill=tk.Y)
        nav.pack_propagate(False)

        # 右侧内容区
        self._content_area = tk.Frame(body, bg='white')
        self._content_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 各导航页 frame（用 pack/pack_forget 切换）
        self.ocr_tab        = tk.Frame(self._content_area, bg='white')
        self.classifier_tab = self.ocr_tab  # 兼容旧代码
        self._page_stats    = tk.Frame(self._content_area, bg='white')
        self._page_history  = tk.Frame(self._content_area, bg='white')
        self._page_api_key  = tk.Frame(self._content_area, bg='white')
        self._page_unlock   = tk.Frame(self._content_area, bg='white')

        # main_notebook 兼容旧代码（不实际显示）
        self.main_notebook = ttk.Notebook(self._content_area)

        self._nav_pages = {
            'OCR识别': self.ocr_tab,
            '统计':    self._page_stats,
            '历史':    self._page_history,
            '密钥':    self._page_api_key,
            '解锁':    self._page_unlock,
        }

        # ── 导航菜单项 ──
        self._nav_buttons = {}
        nav_items = [
            ('🏠', '首页',    self._nav_home),
            ('▦',  'OCR识别', lambda: self._nav_to('OCR识别')),
            ('📊', '统计',    lambda: self._nav_to('统计')),
            ('📜', '历史',    lambda: self._nav_to('历史')),
            ('🔑', '密钥',    lambda: self._nav_to('密钥')),
            ('🔓', '解锁',    lambda: self._nav_to('解锁')),
        ]

        tk.Frame(nav, bg=nav_bg, height=8).pack()  # 顶部间距

        for icon, label, cmd in nav_items:
            item = tk.Frame(nav, bg=nav_bg, cursor='hand2')
            item.pack(fill=tk.X, pady=2)

            # 左侧激活条
            bar = tk.Frame(item, bg=nav_bg, width=3)
            bar.pack(side=tk.LEFT, fill=tk.Y)

            # 图标+文字垂直排列
            content = tk.Frame(item, bg=nav_bg)
            content.pack(fill=tk.X, expand=True, padx=4, pady=6)

            icon_lbl = tk.Label(content, text=icon, bg=nav_bg, fg='#9CA3AF',
                                font=('Microsoft YaHei', 16))
            icon_lbl.pack()
            text_lbl = tk.Label(content, text=label, bg=nav_bg, fg='#9CA3AF',
                                font=('Microsoft YaHei', 8))
            text_lbl.pack()

            def _on_enter(e, f=item, c=content, il=icon_lbl, tl=text_lbl):
                active = getattr(self, '_active_nav', '')
                lbl = tl.cget('text')
                if active != lbl:
                    for w in (f, c, il, tl):
                        w.config(bg='#F3F4F6')

            def _on_leave(e, f=item, c=content, il=icon_lbl, tl=text_lbl, b=bar, lbl=label):
                active = getattr(self, '_active_nav', '')
                bg = '#EFF6FF' if active == lbl else nav_bg
                for w in (f, c, il, tl):
                    w.config(bg=bg)

            def _on_click(e, c=cmd, lbl=label):
                self._set_active_nav(lbl)
                c()

            for w in (item, content, icon_lbl, text_lbl):
                w.bind('<Enter>', _on_enter)
                w.bind('<Leave>', _on_leave)
                w.bind('<Button-1>', _on_click)

            self._nav_buttons[label] = (item, icon_lbl, text_lbl, bar)

        # 底部状态栏
        status_bar = tk.Frame(nav, bg=nav_bg,
                              highlightthickness=1, highlightbackground='#E5E7EB')
        status_bar.pack(side=tk.BOTTOM, fill=tk.X, pady=0)
        self._status_dot = tk.Label(status_bar, text='●', bg=nav_bg, fg='#3B82F6',
                                    font=('Arial', 9))
        self._status_dot.pack(side=tk.LEFT, padx=(14, 4), pady=8)
        self._status_text = tk.Label(status_bar, text='就绪', bg=nav_bg, fg='#9CA3AF',
                 font=('Microsoft YaHei', 8))
        self._status_text.pack(side=tk.LEFT)

        # 默认激活 OCR识别
        self._set_active_nav('OCR识别')

        # 设置各页内容
        self.setup_ocr_tab()
        self._build_stats_page()
        self._build_history_page()
        self._build_api_key_page()
        self._build_unlock_page()

        # 默认显示 OCR识别页
        self._nav_to('OCR识别')

    def _set_active_nav(self, label):
        """设置当前激活的导航项"""
        self._active_nav = label
        nav_bg = '#FFFFFF'
        for lbl, (item, icon_lbl, text_lbl, bar) in self._nav_buttons.items():
            # content frame 是 item 的第二个子控件
            children = item.winfo_children()
            content = children[1] if len(children) > 1 else item
            if lbl == label:
                for w in (item, content, icon_lbl, text_lbl):
                    w.config(bg='#EFF6FF')
                icon_lbl.config(fg='#1A6FD4')
                text_lbl.config(fg='#1A6FD4', font=('Microsoft YaHei', 8, 'bold'))
                bar.config(bg='#1A6FD4')
            else:
                for w in (item, content, icon_lbl, text_lbl):
                    w.config(bg=nav_bg)
                icon_lbl.config(fg='#9CA3AF')
                text_lbl.config(fg='#9CA3AF', font=('Microsoft YaHei', 8))
                bar.config(bg=nav_bg)

    def _show_import_dialog(self):
        """顶部导入数据弹窗"""
        win = tk.Toplevel(self.root)
        win.title('导入数据')
        win.transient(self.root)
        win.grab_set()
        win.configure(bg='white')

        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        w, h = 520, 420
        win.geometry(f'{w}x{h}+{sw-w-20}+52')  # 右上角，标题栏下方
        win.resizable(False, True)

        # 标题
        tk.Label(win, text='粘贴并解析数据', bg='white', fg='#111827',
                 font=('Microsoft YaHei', 12, 'bold')).pack(anchor='w', padx=18, pady=(14, 4))
        tk.Label(win, text='格式：名称|Y|X|高度  每行一条',
                 bg='white', fg='#9CA3AF',
                 font=('Microsoft YaHei', 9)).pack(anchor='w', padx=18, pady=(0, 8))

        # 文本框
        txt = tk.Text(win, font=('Consolas', 10), relief='flat',
                      highlightthickness=1, highlightbackground='#DDE3EA',
                      bg='#F9FAFB', wrap=tk.NONE)
        txt.pack(fill=tk.BOTH, expand=True, padx=18, pady=(0, 10))

        # 自动粘贴剪贴板内容
        try:
            clip = self.root.clipboard_get()
            if clip.strip():
                txt.insert('1.0', clip)
        except Exception:
            pass

        # 底部按钮
        btn_row = tk.Frame(win, bg='white')
        btn_row.pack(fill=tk.X, padx=18, pady=(0, 14))

        def do_parse():
            content = txt.get('1.0', tk.END).strip()
            if not content:
                return
            if hasattr(self, 'text_input'):
                self.text_input.delete('1.0', tk.END)
                self.text_input.insert(tk.END, content)
            self.load_from_text()
            win.destroy()

        tk.Button(btn_row, text='解析数据', command=do_parse,
                  bg='#1A6FD4', fg='white', relief='flat',
                  font=('Microsoft YaHei', 10, 'bold'),
                  padx=20, pady=6, cursor='hand2').pack(side=tk.LEFT)
        tk.Button(btn_row, text='取消', command=win.destroy,
                  bg='#F3F4F6', fg='#374151', relief='flat',
                  font=('Microsoft YaHei', 10),
                  padx=20, pady=6, cursor='hand2').pack(side=tk.LEFT, padx=(8, 0))

        win.bind('<Return>', lambda e: do_parse())
        win.bind('<Escape>', lambda e: win.destroy())
        txt.focus_set()

    def _nav_to(self, name):
        """切换右侧导航页"""
        self._set_active_nav(name)
        for n, frame in self._nav_pages.items():
            frame.pack_forget()
        if name in self._nav_pages:
            self._nav_pages[name].pack(fill=tk.BOTH, expand=True)
        # 切换到历史页时自动刷新表格
        if name == '历史' and hasattr(self._page_history, '_refresh'):
            self._page_history._refresh()

    def _nav_home(self):
        self._nav_to('OCR识别')

    def _nav_switch(self, index):
        self._nav_to('OCR识别')

    # ── 四个内嵌页面构建方法 ──

    def _build_stats_page(self):
        """统计页内嵌"""
        page = self._page_stats
        page.configure(bg='white')

        header = tk.Frame(page, bg='white')
        header.pack(fill=tk.X, padx=24, pady=(18, 10))
        tk.Label(header, text='📊 识别统计', bg='white', fg='#111827',
                 font=('Microsoft YaHei', 14, 'bold')).pack(side=tk.LEFT)
        tk.Button(header, text='🔄 刷新', command=lambda: _reload(),
                  bg='#EFF6FF', fg='#1A6FD4', relief='flat',
                  font=('Microsoft YaHei', 9), padx=10, pady=4,
                  cursor='hand2').pack(side=tk.RIGHT)

        # 三个子标签
        nb = ttk.Notebook(page)
        nb.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 12))

        tab_total   = tk.Frame(nb, bg='white')
        tab_daily   = tk.Frame(nb, bg='white')
        tab_monthly = tk.Frame(nb, bg='white')
        nb.add(tab_total,   text=' 📈 总计 ')
        nb.add(tab_daily,   text=' 📅 按日 ')
        nb.add(tab_monthly, text=' 📊 按月 ')

        self._stats_tabs = (tab_total, tab_daily, tab_monthly)

        def _reload():
            for tab in self._stats_tabs:
                for w in tab.winfo_children():
                    w.destroy()
            self._normalize_stats_for_display()
            self._render_total_stats(tab_total)
            self._render_daily_stats(tab_daily)
            self._render_monthly_stats(tab_monthly)

        _reload()

    def _render_total_stats(self, parent):
        """渲染总计统计"""
        BG = 'white'
        BLUE = '#1A6FD4'

        totals = {
            'accurate': self._empty_ocr_stats(),
            'basic':    self._empty_ocr_stats(),
            'general':  self._empty_ocr_stats(),
        }
        # 按月汇总，用于计算月均
        monthly = {}
        for date, day_data in self.stats.items():
            month = date[:7]
            if month not in monthly:
                monthly[month] = {m: self._empty_ocr_stats() for m in totals}
            for mode in totals:
                s = day_data.get(mode, {})
                for k in totals[mode]:
                    totals[mode][k] += s.get(k, 0)
                    monthly[month][mode][k] += s.get(k, 0)

        total_days = len(self.stats)
        total_months = len(monthly) or 1
        success_col = '成功(含缓存)' if self.stats_count_cache_as_success else '接口成功'

        # 汇总卡片
        cards = tk.Frame(parent, bg=BG)
        cards.pack(fill=tk.X, padx=16, pady=(12, 16))
        total_cached = sum(totals[m]['cached'] for m in totals)
        for label, val in [('使用天数', f'{total_days} 天'),
                            ('使用月数', f'{total_months} 月'),
                            ('缓存复用', f'{total_cached} 次')]:
            card = tk.Frame(cards, bg='#F0F7FF', highlightthickness=1,
                            highlightbackground='#BFDBFE')
            card.pack(side=tk.LEFT, padx=(0, 12), pady=4, ipadx=18, ipady=12)
            tk.Label(card, text=val, bg='#F0F7FF', fg=BLUE,
                     font=('Microsoft YaHei', 16, 'bold')).pack()
            tk.Label(card, text=label, bg='#F0F7FF', fg='#6B7280',
                     font=('Microsoft YaHei', 8)).pack()

        # 三种模式详细（只显示高精度和通用）
        BORDER = '#DDE3EA'
        for mode, title, bg_c in [
            ('accurate', '高精度识别', '#E3F2FD'),
            ('general',  '通用识别',   '#F3E5F5'),
        ]:
            s = totals[mode]
            days = total_days or 1

            # 计算每月日均接口成功（不含缓存）
            month_daily_avgs = []
            for month, mdata in monthly.items():
                month_days = sum(1 for d in self.stats if d[:7] == month) or 1
                ms = mdata[mode]
                if self.stats_count_cache_as_success:
                    api_success = max(ms['success'] - ms['cached'], 0)
                else:
                    api_success = ms['success']
                month_daily_avgs.append(api_success / month_days)
            avg_per_day = sum(month_daily_avgs) / len(month_daily_avgs) if month_daily_avgs else 0

            sec = tk.Frame(parent, bg=bg_c, highlightthickness=1,
                           highlightbackground=BORDER)
            sec.pack(fill=tk.X, padx=16, pady=(0, 8), ipadx=10, ipady=8)
            tk.Label(sec, text=f'【{title}】', bg=bg_c, fg='#374151',
                     font=('Microsoft YaHei', 10, 'bold')).pack(anchor='w', padx=8, pady=(6, 2))
            info = (f"{success_col}：{s['success']} 张   缓存复用：{s['cached']} 张   "
                    f"月均日接口成功：{avg_per_day:.1f} 张/天")
            tk.Label(sec, text=info, bg=bg_c, fg='#374151',
                     font=('Microsoft YaHei', 9)).pack(anchor='w', padx=8, pady=(0, 6))

    def _render_daily_stats(self, parent):
        """渲染按日统计表格"""
        success_col = '成功(含缓存)' if self.stats_count_cache_as_success else '接口成功'
        cols = ('日期', '类型', success_col, '缓存', '失败')

        frame = tk.Frame(parent, bg='white')
        frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # 删除指定日期
        ctrl = tk.Frame(parent, bg='white')
        ctrl.pack(fill=tk.X, padx=16, pady=(0, 6))
        tk.Label(ctrl, text='删除日期：', bg='white',
                 font=('Microsoft YaHei', 9)).pack(side=tk.LEFT)
        del_var = tk.StringVar()
        tk.Entry(ctrl, textvariable=del_var, width=14,
                 font=('Microsoft YaHei', 9), relief='flat',
                 highlightthickness=1, highlightbackground='#DDE3EA').pack(
                     side=tk.LEFT, padx=(4, 8), ipady=3)

        vsb = ttk.Scrollbar(frame, orient=tk.VERTICAL)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        tree = ttk.Treeview(frame, columns=cols, show='headings',
                            yscrollcommand=vsb.set)
        vsb.config(command=tree.yview)
        widths = [120, 70, 90, 65, 55]
        for col, w in zip(cols, widths):
            tree.heading(col, text=col)
            tree.column(col, width=w, anchor='center')
        tree.pack(fill=tk.BOTH, expand=True)
        tree.tag_configure('accurate', background='#E3F2FD')
        tree.tag_configure('basic',    background='#FFF3E0')
        tree.tag_configure('general',  background='#F3E5F5')
        tree.tag_configure('total',    background='#E8F5E9',
                           font=('Microsoft YaHei', self.current_font_size, 'bold'))

        def _fill():
            tree.delete(*tree.get_children())
            for date in sorted(self.stats.keys(), reverse=True):
                d = self.stats[date]
                first = True
                for mode, tag in [('accurate','accurate'),('basic','basic'),('general','general')]:
                    s = d.get(mode, {})
                    lbl = {'accurate':'高精度','basic':'快速','general':'通用'}[mode]
                    tree.insert('', tk.END, iid=f'{date}_{mode}', tags=(tag,),
                                values=(date if first else '', lbl,
                                        s.get('success',0), s.get('cached',0),
                                        s.get('failed',0)))
                    first = False

        def on_select(e):
            sel = tree.selection()
            if sel:
                date = tree.item(sel[0], 'values')[0]
                if date:
                    del_var.set(date)

        def do_delete():
            dates = [d.strip() for d in re.split(r'[,\s，;；]+', del_var.get()) if d.strip()]
            found = [d for d in dates if d in self.stats]
            if not found:
                messagebox.showwarning('提示', '未找到对应日期的统计记录')
                return
            if not self.verify_admin_password(title='删除统计记录',
                                              message=f'删除 {", ".join(found)} 的统计？'):
                return
            for d in found:
                del self.stats[d]
            self.save_stats()
            _fill()

        tree.bind('<<TreeviewSelect>>', on_select)
        tk.Button(ctrl, text='删除', command=do_delete,
                  bg='#FEF2F2', fg='#EF4444', relief='flat',
                  font=('Microsoft YaHei', 9), padx=10, pady=3,
                  cursor='hand2').pack(side=tk.LEFT)
        _fill()

    def _render_monthly_stats(self, parent):
        """渲染按月统计表格"""
        success_col = '成功(含缓存)' if self.stats_count_cache_as_success else '接口成功'
        cols = ('月份', '天数', '类型', success_col, '缓存', '日均接口成功', '日均缓存')

        frame = tk.Frame(parent, bg='white')
        frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        vsb = ttk.Scrollbar(frame, orient=tk.VERTICAL)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        tree = ttk.Treeview(frame, columns=cols, show='headings',
                            yscrollcommand=vsb.set)
        vsb.config(command=tree.yview)
        widths = [90, 55, 65, 90, 65, 80, 80]
        for col, w in zip(cols, widths):
            tree.heading(col, text=col)
            tree.column(col, width=w, anchor='center')
        tree.pack(fill=tk.BOTH, expand=True)
        tree.tag_configure('accurate', background='#E3F2FD')
        tree.tag_configure('basic',    background='#FFF3E0')
        tree.tag_configure('general',  background='#F3E5F5')
        tree.tag_configure('total',    background='#E8F5E9',
                           font=('Microsoft YaHei', self.current_font_size, 'bold'))

        monthly = {}
        for date, day_data in self.stats.items():
            month = date[:7]
            if month not in monthly:
                monthly[month] = {'accurate': self._empty_ocr_stats(),
                                  'basic':    self._empty_ocr_stats(),
                                  'general':  self._empty_ocr_stats(),
                                  'days': set()}
            monthly[month]['days'].add(date)
            for mode in ('accurate', 'basic', 'general'):
                s = day_data.get(mode, {})
                for k in monthly[month][mode]:
                    monthly[month][mode][k] += s.get(k, 0)

        for month in sorted(monthly.keys(), reverse=True):
            d = monthly[month]
            days = len(d['days']) or 1
            first = True
            for mode, tag in [('accurate','accurate'),('basic','basic'),('general','general')]:
                s = d[mode]
                lbl = {'accurate':'高精度','basic':'快速','general':'通用'}[mode]
                if self.stats_count_cache_as_success:
                    api_success = max(s['success'] - s['cached'], 0)
                else:
                    api_success = s['success']
                tree.insert('', tk.END, tags=(tag,),
                            values=(month if first else '', days if first else '',
                                    lbl, api_success, s['cached'],
                                    f"{api_success/days:.1f}",
                                    f"{s['cached']/days:.1f}"))
                first = False

    def _render_stats_inline(self, parent):
        """兼容旧调用"""
        self._render_daily_stats(parent)

    def _build_history_page(self):
        """历史记录页内嵌"""
        page = self._page_history
        page.configure(bg='white')

        header = tk.Frame(page, bg='white')
        header.pack(fill=tk.X, padx=24, pady=(18, 8))
        tk.Label(header, text='📜 识别历史记录', bg='white', fg='#111827',
                 font=('Microsoft YaHei', 14, 'bold')).pack(side=tk.LEFT)

        # 搜索栏
        search_row = tk.Frame(page, bg='white')
        search_row.pack(fill=tk.X, padx=24, pady=(0, 8))
        tk.Label(search_row, text='搜索：', bg='white',
                 font=('Microsoft YaHei', 9)).pack(side=tk.LEFT)
        search_var = tk.StringVar()
        tk.Entry(search_row, textvariable=search_var,
                 font=('Microsoft YaHei', 9), width=28,
                 relief='flat', highlightthickness=1,
                 highlightbackground='#DDE3EA').pack(side=tk.LEFT, padx=(4, 8), ipady=3)

        # 表格
        tbl_frame = tk.Frame(page, bg='white')
        tbl_frame.pack(fill=tk.BOTH, expand=True, padx=24, pady=(0, 8))
        vsb = ttk.Scrollbar(tbl_frame, orient=tk.VERTICAL)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        cols = ('时间', '名称', '类型', '页码', '总行数')
        htree = ttk.Treeview(tbl_frame, columns=cols, show='headings',
                             yscrollcommand=vsb.set, style='History.Treeview')
        vsb.config(command=htree.yview)
        for col, w, anchor in zip(cols, [160, 200, 90, 60, 70], ['center', 'w', 'center', 'center', 'center']):
            htree.heading(col, text=col)
            htree.column(col, width=w, anchor=anchor)
        htree.pack(fill=tk.BOTH, expand=True)

        # 底部按钮
        btn_row = tk.Frame(page, bg='white')
        btn_row.pack(fill=tk.X, padx=24, pady=(0, 12))

        def copy_selected_item():
            sel = htree.selection()
            if not sel:
                return
            # iid 格式是 h_原始索引，直接解析
            iid = sel[0]
            try:
                idx = int(iid.replace('h_', ''))
            except ValueError:
                return
            if idx >= len(self.history_data):
                return
            item = self.history_data[idx]
            self.show_history_detail(item)

        def parse_selected_item():
            sel = htree.selection()
            if not sel:
                messagebox.showwarning('提示', '请先选择一条历史记录')
                return
            iid = sel[0]
            try:
                idx = int(str(iid).replace('h_', ''))
            except ValueError:
                messagebox.showwarning('提示', f'无法解析记录索引：{iid}')
                return
            if idx >= len(self.history_data):
                messagebox.showwarning('提示', '记录不存在，请刷新后重试')
                return
            item = self.history_data[idx]
            lines = []
            for f in item.get('files', []):
                lines.extend(f.get('content', []))
            text = '\n'.join(l for l in lines if l.strip())
            if not text:
                messagebox.showwarning('提示', '该记录没有可解析的内容')
                return
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            if hasattr(self, 'text_input'):
                self.text_input.delete('1.0', tk.END)
                self.text_input.insert(tk.END, text)
            self.load_from_text()
            self._nav_to('OCR识别')

        def clear_all():
            if messagebox.askyesno('确认', '清空所有历史记录？'):
                self.history_data = []
                self.save_history()
                _refresh()

        def _refresh(*args):
            kw = search_var.get().strip().lower()
            htree.delete(*htree.get_children())
            for i, item in enumerate(self.history_data):
                ts    = item.get('timestamp', '')
                typ   = item.get('type', '')
                fc    = item.get('file_count', 0)
                tl    = item.get('total_lines', 0)
                files = item.get('files', [])
                # 优先用 book_name，没有则用文件名
                name  = item.get('book_name', '')
                if not name:
                    if len(files) == 1:
                        name = files[0].get('name', '')
                    elif len(files) > 1:
                        name = f'{files[0].get("name", "")} 等{len(files)}个文件'
                page_no = item.get('page_no', '')
                if kw:
                    searchable = f'{ts}{typ}{name}{page_no}'
                    for f in files:
                        searchable += f.get('name', '')
                        searchable += ' '.join(f.get('content', []))
                    if kw not in searchable.lower():
                        continue
                htree.insert('', tk.END, iid=f'h_{i}',
                             values=(ts, name, typ, page_no, tl))

        for text, cmd, bg, fg in [
            ('📋 复制解析', parse_selected_item, '#EFF6FF', '#1A6FD4'),
            ('🗑 清空', clear_all, '#FEF2F2', '#EF4444'),
        ]:
            tk.Button(btn_row, text=text, command=cmd, bg=bg, fg=fg,
                      relief='flat', font=('Microsoft YaHei', 9),
                      padx=12, pady=4, cursor='hand2').pack(side=tk.LEFT, padx=(0, 8))

        htree.bind('<Double-1>', lambda e: copy_selected_item())
        search_var.trace_add('write', _refresh)
        _refresh()

        # 每次切换到此页刷新
        self._page_history._refresh = _refresh

    def _build_api_key_page(self):
        """密钥设置页内嵌"""
        page = self._page_api_key
        page.configure(bg='white')

        tk.Label(page, text='🔑 密钥设置', bg='white', fg='#111827',
                 font=('Microsoft YaHei', 14, 'bold')).pack(anchor='w', padx=24, pady=(18, 4))
        tk.Label(page, text='修改后点击保存，立即生效', bg='white', fg='#9CA3AF',
                 font=('Microsoft YaHei', 9)).pack(anchor='w', padx=24, pady=(0, 12))

        form = tk.Frame(page, bg='white')
        form.pack(fill=tk.X, padx=24)

        BORDER = '#DDE3EA'

        def field(parent, label, var):
            row = tk.Frame(parent, bg='white')
            row.pack(fill=tk.X, pady=4)
            tk.Label(row, text=label, bg='white', fg='#374151',
                     font=('Microsoft YaHei', 9), width=22, anchor='w').pack(side=tk.LEFT)
            e = tk.Entry(row, textvariable=var, font=('Microsoft YaHei', 9),
                         relief='flat', highlightthickness=1,
                         highlightbackground=BORDER, width=40)
            e.pack(side=tk.LEFT, ipady=5, padx=(8, 0))
            return e

        v_ak  = tk.StringVar(value=API_KEY)
        v_sk  = tk.StringVar(value=SECRET_KEY)
        v_akb = tk.StringVar(value=API_KEY_BASIC)
        v_skb = tk.StringVar(value=SECRET_KEY_BASIC)
        v_akg = tk.StringVar(value=API_KEY_GENERAL)
        v_skg = tk.StringVar(value=SECRET_KEY_GENERAL)

        for section_title, pairs in [
            ('高精度识别', [(v_ak, 'API Key'), (v_sk, 'Secret Key')]),
            ('快速识别',   [(v_akb, 'API Key'), (v_skb, 'Secret Key')]),
            ('通用识别',   [(v_akg, 'API Key'), (v_skg, 'Secret Key')]),
        ]:
            tk.Frame(form, bg=BORDER, height=1).pack(fill=tk.X, pady=(12, 6))
            tk.Label(form, text=section_title, bg='white', fg='#1A6FD4',
                     font=('Microsoft YaHei', 10, 'bold')).pack(anchor='w', pady=(0, 4))
            for var, lbl in pairs:
                field(form, lbl, var)

        def save_keys():
            global API_KEY, SECRET_KEY, API_KEY_BASIC, SECRET_KEY_BASIC
            global API_KEY_GENERAL, SECRET_KEY_GENERAL
            API_KEY = v_ak.get().strip()
            SECRET_KEY = v_sk.get().strip()
            API_KEY_BASIC = v_akb.get().strip()
            SECRET_KEY_BASIC = v_skb.get().strip()
            API_KEY_GENERAL = v_akg.get().strip()
            SECRET_KEY_GENERAL = v_skg.get().strip()
            env_path = Path(__file__).parent / '.env'
            lines_env = []
            if env_path.exists():
                with open(env_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        k = line.split('=', 1)[0].strip()
                        if k not in ('BAIDU_API_KEY', 'BAIDU_SECRET_KEY',
                                     'BAIDU_API_KEY_BASIC', 'BAIDU_SECRET_KEY_BASIC',
                                     'BAIDU_API_KEY_GENERAL', 'BAIDU_SECRET_KEY_GENERAL'):
                            lines_env.append(line.rstrip())
            for k, v in [('BAIDU_API_KEY', API_KEY), ('BAIDU_SECRET_KEY', SECRET_KEY),
                          ('BAIDU_API_KEY_BASIC', API_KEY_BASIC), ('BAIDU_SECRET_KEY_BASIC', SECRET_KEY_BASIC),
                          ('BAIDU_API_KEY_GENERAL', API_KEY_GENERAL), ('BAIDU_SECRET_KEY_GENERAL', SECRET_KEY_GENERAL)]:
                if v:
                    lines_env.append(f'{k}={v}')
            with open(env_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines_env))
            self._update_ocr_btn_by_keys()
            self.show_toast('✅ 密钥已保存')

        tk.Button(page, text='💾 保存密钥', command=save_keys,
                  bg='#1A6FD4', fg='white', relief='flat',
                  font=('Microsoft YaHei', 10, 'bold'),
                  padx=24, pady=8, cursor='hand2').pack(anchor='w', padx=24, pady=16)

    def _build_unlock_page(self):
        """解锁页内嵌"""
        page = self._page_unlock
        page.configure(bg='white')

        tk.Label(page, text='🔓 解锁尺寸限制', bg='white', fg='#111827',
                 font=('Microsoft YaHei', 14, 'bold')).pack(anchor='w', padx=24, pady=(18, 4))

        form = tk.Frame(page, bg='white')
        form.pack(fill=tk.X, padx=24, pady=8)
        BORDER = '#DDE3EA'

        def int_var(val):
            v = tk.StringVar(value=str(val))
            return v

        vars_ = {k: int_var(v) for k, v in self.size_limits.items()}

        labels = {
            'accurate_min_width': '高精度最小宽度', 'accurate_max_width': '高精度最大宽度',
            'accurate_min_height': '高精度最小高度', 'accurate_max_height': '高精度最大高度',
            'basic_min_width': '快速最小宽度',     'basic_max_width': '快速最大宽度',
            'basic_min_height': '快速最小高度',    'basic_max_height': '快速最大高度',
            'general_min_width': '通用最小宽度',   'general_max_width': '通用最大宽度',
            'general_min_height': '通用最小高度',  'general_max_height': '通用最大高度',
        }

        pwd_row = tk.Frame(form, bg='white')
        pwd_row.pack(fill=tk.X, pady=(0, 12))
        tk.Label(pwd_row, text='密码：', bg='white',
                 font=('Microsoft YaHei', 9)).pack(side=tk.LEFT)
        pwd_var = tk.StringVar()
        tk.Entry(pwd_row, textvariable=pwd_var, show='*',
                 font=('Microsoft YaHei', 9), width=12,
                 relief='flat', highlightthickness=1,
                 highlightbackground=BORDER).pack(side=tk.LEFT, padx=8, ipady=4)

        grid = tk.Frame(form, bg='white')
        grid.pack(fill=tk.X)
        for i, (k, lbl) in enumerate(labels.items()):
            row, col = divmod(i, 2)
            f = tk.Frame(grid, bg='white')
            f.grid(row=row, column=col, sticky='w', padx=(0, 24), pady=3)
            tk.Label(f, text=lbl, bg='white', fg='#374151',
                     font=('Microsoft YaHei', 8), width=14, anchor='w').pack(side=tk.LEFT)
            tk.Entry(f, textvariable=vars_[k], font=('Microsoft YaHei', 9),
                     width=8, relief='flat', highlightthickness=1,
                     highlightbackground=BORDER).pack(side=tk.LEFT, ipady=4, padx=(4, 0))

        def save_limits():
            if pwd_var.get() != self.unlock_password:
                messagebox.showerror('错误', '密码错误！')
                return
            try:
                for k, v in vars_.items():
                    self.size_limits[k] = int(v.get())
                self.save_size_limits()
                self.size_limit_unlocked = True
                self.show_toast('✅ 尺寸限制已保存')
            except ValueError:
                messagebox.showerror('错误', '请输入有效数字！')

        def reset_defaults():
            defaults = {
                'accurate_min_width': 3500, 'accurate_max_width': 15000,
                'accurate_min_height': 4000, 'accurate_max_height': 15000,
                'basic_min_width': 0,        'basic_max_width': 8100,
                'basic_min_height': 0,       'basic_max_height': 3000,
                'general_min_width': 0,      'general_max_width': 8192,
                'general_min_height': 0,     'general_max_height': 8192,
            }
            for k, v in defaults.items():
                vars_[k].set(str(v))

        btn_row = tk.Frame(page, bg='white')
        btn_row.pack(anchor='w', padx=24, pady=12)
        tk.Button(btn_row, text='💾 保存', command=save_limits,
                  bg='#1A6FD4', fg='white', relief='flat',
                  font=('Microsoft YaHei', 10, 'bold'),
                  padx=20, pady=7, cursor='hand2').pack(side=tk.LEFT)
        tk.Button(btn_row, text='恢复默认', command=reset_defaults,
                  bg='white', fg='#374151', relief='flat',
                  highlightthickness=1, highlightbackground=BORDER,
                  font=('Microsoft YaHei', 9),
                  padx=16, pady=7, cursor='hand2').pack(side=tk.LEFT, padx=(8, 0))




    def setup_ocr_tab(self):
        """合并页面 — 左侧操作面板 + 顶部4步骤标签 + 右侧内容区"""
        BG = 'white'
        PANEL_BG = '#F7F9FC'
        BORDER = '#DDE3EA'
        BLUE = '#1A6FD4'

        self.ocr_tab.configure(bg=BG)

        # ── 左右分栏 ──
        self._ocr_left = tk.Frame(self.ocr_tab, bg=PANEL_BG, width=230,
                                  highlightthickness=1, highlightbackground=BORDER)
        self._ocr_left.pack(side=tk.LEFT, fill=tk.Y)
        self._ocr_left.pack_propagate(False)

        main_right = tk.Frame(self.ocr_tab, bg=BG)
        main_right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # ── 顶部4步骤标签栏 ──
        step_bar = tk.Frame(main_right, bg=BG,
                            highlightthickness=1, highlightbackground=BORDER)
        step_bar.pack(fill=tk.X)
        step_inner = tk.Frame(step_bar, bg=BG)
        step_inner.pack(fill=tk.X, padx=16, pady=0)

        self._step_btns = {}
        steps = [
            ('交互绘图', '标注识别区域'),
            ('分类表格', '生成结构化数据'),
            ('文本报告', '生成识别报告'),
        ]

        for i, (name, sub) in enumerate(steps):
            col = tk.Frame(step_inner, bg=BG)
            col.pack(side=tk.LEFT)
            num_lbl = tk.Label(col, text=f' {i+1} ', bg='#E5E7EB', fg='#6B7280',
                               font=('Microsoft YaHei', 9, 'bold'),
                               padx=6, pady=3, relief='flat')
            num_lbl.pack(side=tk.LEFT, padx=(0, 8), pady=12)
            txt_col = tk.Frame(col, bg=BG)
            txt_col.pack(side=tk.LEFT, pady=8)
            name_lbl = tk.Label(txt_col, text=name, bg=BG, fg='#6B7280',
                                font=('Microsoft YaHei', 9, 'bold'), cursor='hand2')
            name_lbl.pack(anchor='w')
            sub_lbl = tk.Label(txt_col, text=sub, bg=BG, fg='#9CA3AF',
                               font=('Microsoft YaHei', 7))
            sub_lbl.pack(anchor='w')
            # 底部指示线
            bar = tk.Frame(col, bg=BG, height=2)
            bar.pack(fill=tk.X)
            self._step_btns[name] = (col, num_lbl, name_lbl, sub_lbl, bar)
            for w in (col, num_lbl, name_lbl, sub_lbl):
                w.bind('<Button-1>', lambda e, n=name, ix=i: self._step_switch(n, ix))
            if i < len(steps) - 1:
                tk.Label(step_inner, text='›', bg=BG, fg='#D1D5DB',
                         font=('Arial', 16)).pack(side=tk.LEFT, padx=8)

        # ── 右侧内容区 ──
        self._right_content = tk.Frame(main_right, bg=BG)
        self._right_content.pack(fill=tk.BOTH, expand=True)

        self.tab_plt          = tk.Frame(self._right_content, bg=BG)
        self.tab_res          = tk.Frame(self._right_content, bg=BG)
        self.tab_report_outer = tk.Frame(self._right_content, bg=BG)
        self._page_ocr        = self.tab_plt  # 兼容旧代码

        self._classifier_pages = {
            '交互绘图': self.tab_plt,
            '分类表格': self.tab_res,
            '文本报告': self.tab_report_outer,
        }

        self._build_left_ocr_panel(PANEL_BG, BORDER, BLUE)
        self.setup_plot_placeholder()
        self.setup_results_tab()
        self._setup_drag_drop()
        self.image_paths = []
        self.all_results = []

        # result_text 隐藏占位
        self.result_text = scrolledtext.ScrolledText(
            self.ocr_tab, width=1, height=1, font=('Microsoft YaHei', 10))
        self.result_text.pack_forget()
        self.context_menu = tk.Menu(self.result_text, tearoff=0)
        self.context_menu.add_command(label='复制选中内容', command=self.copy_selected)
        self.context_menu.add_command(label='复制全部（文字+位置）', command=self.copy_all_text)
        self.context_menu.add_separator()
        self.context_menu.add_command(label='全选', command=self.select_all)
        self.result_text.bind('<Button-3>', self.show_context_menu)

        self._update_ocr_btn_by_keys()
        self._step_switch('交互绘图', 0)
        # 初始化时应用一次字体样式，确保行高正确
        self.root.after(100, self.apply_font_style)

    def _build_left_ocr_panel(self, PANEL_BG, BORDER, BLUE):
        """构建左侧操作面板 — 卡片风格"""
        left_panel = self._ocr_left
        BG = '#F7F9FC'
        left_panel.configure(bg=BG)

        def card(parent, title):
            """创建卡片式分组"""
            outer = tk.Frame(parent, bg=BG)
            outer.pack(fill=tk.X, padx=10, pady=(8, 0))
            tk.Label(outer, text=title, bg=BG, fg='#374151',
                     font=('Microsoft YaHei', 9, 'bold')).pack(anchor='w', pady=(0, 4))
            inner = tk.Frame(outer, bg='white',
                             highlightthickness=1, highlightbackground='#E5E7EB')
            inner.pack(fill=tk.X)
            return inner

        # ── 1. 导入图片 ──
        drop_card = card(left_panel, '1. 导入图片')
        drop_zone = tk.Frame(drop_card, bg='white', cursor='hand2')
        drop_zone.pack(fill=tk.X, padx=12, pady=10)
        self.drop_zone = drop_zone

        tk.Label(drop_zone, text='🖼', bg='white', fg='#BFDBFE',
                 font=('Arial', 28)).pack(pady=(8, 4))
        self.file_label = tk.Label(drop_zone, text='拖拽图片到此处\n或',
                                   bg='white', fg='#9CA3AF',
                                   font=('Microsoft YaHei', 8), justify='center')
        self.file_label.pack()
        self.select_btn = tk.Button(drop_zone, text='选择图片',
                                    command=self.select_file,
                                    bg=BLUE, fg='white', relief='flat',
                                    font=('Microsoft YaHei', 9, 'bold'),
                                    padx=20, pady=6, cursor='hand2')
        self.select_btn.pack(pady=(6, 10))

        tk.Label(drop_card, text='支持 JPG / PNG / BMP / TIFF',
                 bg='white', fg='#9CA3AF',
                 font=('Microsoft YaHei', 7)).pack(anchor='w', padx=12, pady=(0, 4))

        # 清空按钮
        clear_row = tk.Frame(drop_card, bg='white')
        clear_row.pack(fill=tk.X, padx=12, pady=(0, 8))
        self.clear_btn = tk.Button(clear_row, text='清空',
                                   command=self.clear_result,
                                   bg='white', fg='#9CA3AF', relief='flat',
                                   font=('Microsoft YaHei', 8), cursor='hand2')
        self.clear_btn.pack(side=tk.RIGHT)

        # 进度 / 状态
        self.progress_frame = tk.Frame(left_panel, bg=BG)
        self.progress_frame.pack(fill=tk.X, padx=10, pady=(4, 0))
        self.progress_label = tk.Label(self.progress_frame, text='',
                                       bg=BG, fg='#F59E0B',
                                       font=('Microsoft YaHei', 7),
                                       wraplength=190, justify='left')
        self.progress_label.pack(anchor='w')
        acc_range = f"{self.size_limits['accurate_min_width']}~{self.size_limits['accurate_max_width']}x{self.size_limits['accurate_min_height']}~{self.size_limits['accurate_max_height']}"
        bas_range = f"{self.size_limits['basic_min_width']}~{self.size_limits['basic_max_width']}x{self.size_limits['basic_min_height']}~{self.size_limits['basic_max_height']}"
        gen_range = f"{self.size_limits['general_min_width']}~{self.size_limits['general_max_width']}x{self.size_limits['general_min_height']}~{self.size_limits['general_max_height']}"
        self.size_hint_label = tk.Label(self.progress_frame,
                                        text=f"高精度({acc_range})\n快速({bas_range})\n通用({gen_range})",
                                        bg=BG, fg='#9CA3AF',
                                        font=('Microsoft YaHei', 7), justify='left')
        self.size_hint_label.pack(anchor='w')

        # ── 2. 识别设置 ──
        mode_card = card(left_panel, '2. 识别设置')
        tk.Label(mode_card, text='识别模式', bg='white', fg='#6B7280',
                 font=('Microsoft YaHei', 8)).pack(anchor='w', padx=12, pady=(8, 4))
        mode_row = tk.Frame(mode_card, bg='white')
        mode_row.pack(fill=tk.X, padx=12, pady=(0, 10))

        self._selected_ocr_mode = tk.StringVar(value='accurate')

        def _select_mode(mode, btn):
            if btn['state'] == tk.DISABLED:
                return
            self._selected_ocr_mode.set(mode)
            for m, b in _mode_btns.items():
                if m == mode:
                    b.config(bg=BLUE, fg='white',
                             highlightthickness=0)
                else:
                    b.config(bg='white', fg='#374151',
                             highlightthickness=1,
                             highlightbackground='#E5E7EB')

        _mode_btns = {}
        for mode, text in [('accurate', '高精度'), ('basic', '快速'), ('general', '通用')]:
            b = tk.Button(mode_row, text=text,
                          bg='white', fg='#9CA3AF', relief='flat',
                          highlightthickness=1, highlightbackground='#E5E7EB',
                          font=('Microsoft YaHei', 8),
                          padx=8, pady=5, cursor='hand2', state=tk.DISABLED)
            b.pack(side=tk.LEFT, padx=(0, 4))
            b.bind('<Button-1>', lambda e, m=mode, btn=b: _select_mode(m, btn))
            _mode_btns[mode] = b

        self.ocr_btn         = _mode_btns['accurate']
        self.quick_ocr_btn   = _mode_btns['basic']
        self.general_ocr_btn = _mode_btns['general']
        self._mode_btns      = _mode_btns
        self._select_mode_fn = _select_mode

        # ── 3. 图片处理 ──
        proc_card = card(left_panel, '3. 图片处理')
        proc_row = tk.Frame(proc_card, bg='white')
        proc_row.pack(fill=tk.X, padx=12, pady=8)
        for text, cmd in [('拼接', self.merge_images),
                           ('截图', self.start_screenshot_capture),
                           ('裁剪', self.crop_and_merge_direct)]:
            tk.Button(proc_row, text=text, command=cmd,
                      bg='white', fg='#374151', relief='flat',
                      highlightthickness=1, highlightbackground='#E5E7EB',
                      font=('Microsoft YaHei', 8), padx=10, pady=5,
                      cursor='hand2').pack(side=tk.LEFT, padx=(0, 6))
        self.merge_btn      = proc_row.winfo_children()[0]
        self.screenshot_btn = proc_row.winfo_children()[1]
        self.crop_merge_btn = proc_row.winfo_children()[2]

        # ── 4. 绘图模式 ──
        draw_card = card(left_panel, '4. 绘图模式')
        for text, val in [('🖱  直线模式（左键加线/右键删线）', False),
                           ('🎯  圈选模式（画圈提取数据）', True)]:
            tk.Radiobutton(draw_card, text=text,
                           variable=self.enable_lasso_mode, value=val,
                           command=self.update_plot_view,
                           bg='white', fg='#374151',
                           font=('Microsoft YaHei', 8),
                           activebackground='white',
                           wraplength=180, justify='left').pack(
                               anchor='w', padx=12, pady=4)
        tk.Frame(draw_card, bg=BG, height=4).pack()

        # ── 书籍信息 ──
        book_card = card(left_panel, '5. 书籍信息')
        book_inner = tk.Frame(book_card, bg='white')
        book_inner.pack(fill=tk.X, padx=12, pady=(6, 8))

        tk.Label(book_inner, text='书名', bg='white', fg='#6B7280',
                 font=('Microsoft YaHei', 8)).grid(row=0, column=0, sticky='w', pady=2)
        self._book_name_var = tk.StringVar(value=self.store.get('book_name', ''))
        book_name_entry = tk.Entry(book_inner, textvariable=self._book_name_var,
                                   font=('Microsoft YaHei', 8), relief='flat',
                                   highlightthickness=1, highlightbackground='#E5E7EB',
                                   width=16)
        book_name_entry.grid(row=0, column=1, sticky='ew', padx=(6, 0), pady=2, ipady=3)

        tk.Label(book_inner, text='当前页', bg='white', fg='#6B7280',
                 font=('Microsoft YaHei', 8)).grid(row=1, column=0, sticky='w', pady=2)
        self._book_page_var = tk.StringVar(value=str(self.store.get('book_page', 1)))
        page_entry = tk.Entry(book_inner, textvariable=self._book_page_var,
                              font=('Microsoft YaHei', 8), relief='flat',
                              highlightthickness=1, highlightbackground='#E5E7EB',
                              width=16)
        page_entry.grid(row=1, column=1, sticky='ew', padx=(6, 0), pady=2, ipady=3)
        book_inner.columnconfigure(1, weight=1)

        def _save_book_name(*_):
            self.store.set('book_name', self._book_name_var.get().strip())

        def _save_book_page(*_):
            try:
                page_no = int(self._book_page_var.get())
                self.store.set('book_page', page_no)
                if not getattr(self, '_suppress_book_page_trace', False):
                    self._pending_history_book_page = page_no
            except ValueError:
                pass

        self._book_name_var.trace_add('write', _save_book_name)
        self._book_page_var.trace_add('write', _save_book_page)

        # ── 开始识别按钮 ──
        tk.Frame(left_panel, bg=BG, height=8).pack()
        self.copy_btn = tk.Button(left_panel, text='▶   开始识别',
                                  command=self._start_ocr_and_parse,
                                  bg=BLUE, fg='white', relief='flat',
                                  font=('Microsoft YaHei', 10, 'bold'),
                                  pady=11, cursor='hand2', state=tk.DISABLED)
        self.copy_btn.pack(fill=tk.X, padx=10, pady=(0, 6))

        # 辅助按钮
        aux_row = tk.Frame(left_panel, bg=BG)
        aux_row.pack(fill=tk.X, padx=10)
        for text, cmd in [('加|0|0', self.add_zeros_to_lines),
                           ('导出',   self.export_results)]:
            tk.Button(aux_row, text=text, command=cmd,
                      bg='white', fg='#6B7280', relief='flat',
                      highlightthickness=1, highlightbackground='#E5E7EB',
                      font=('Microsoft YaHei', 8), padx=8, pady=4,
                      cursor='hand2').pack(side=tk.LEFT, padx=(0, 6))
        self.add_zeros_btn = aux_row.winfo_children()[0]
        self.export_btn    = aux_row.winfo_children()[1]

        self.text_input = tk.Text(left_panel, height=1, font=('Consolas', 10))
        # 不 pack，仅数据中转

    def _build_ocr_preview_page(self, BG, BORDER):
        """构建步骤1识别结果预览页"""
        page = self._page_ocr
        top_bar = tk.Frame(page, bg=BG)
        top_bar.pack(fill=tk.X, padx=16, pady=(14, 6))
        self._ocr_preview_title = tk.Label(top_bar, text='识别结果预览',
                                           bg=BG, fg='#111827',
                                           font=('Microsoft YaHei', 12, 'bold'))
        self._ocr_preview_title.pack(side=tk.LEFT)

        self.result_text = scrolledtext.ScrolledText(page, width=1, height=1,
                                                     font=('Microsoft YaHei', 10))
        self.result_text.pack_forget()
        self.context_menu = tk.Menu(self.result_text, tearoff=0)
        self.context_menu.add_command(label='复制选中内容', command=self.copy_selected)
        self.context_menu.add_command(label='复制全部（文字+位置）', command=self.copy_all_text)
        self.context_menu.add_separator()
        self.context_menu.add_command(label='全选', command=self.select_all)
        self.result_text.bind('<Button-3>', self.show_context_menu)

        tbl_frame = tk.Frame(page, bg=BG)
        tbl_frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 12))
        vsb = ttk.Scrollbar(tbl_frame, orient=tk.VERTICAL)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self._preview_tree = ttk.Treeview(
            tbl_frame,
            columns=('cat', 'label', 'c_group', 'group'),
            show='headings', yscrollcommand=vsb.set)
        vsb.config(command=self._preview_tree.yview)
        self._preview_tree.heading('cat',     text='分类')
        self._preview_tree.heading('label',   text='名称')
        self._preview_tree.heading('c_group', text='C组')
        self._preview_tree.heading('group',   text='组')
        self._preview_tree.column('cat',     width=80,  anchor='center')
        self._preview_tree.column('label',   width=320, anchor='w')
        self._preview_tree.column('c_group', width=60,  anchor='center')
        self._preview_tree.column('group',   width=60,  anchor='center')
        self._preview_tree.pack(fill=tk.BOTH, expand=True)
        bottom = tk.Frame(page, bg=BG)
        bottom.pack(fill=tk.X, padx=16, pady=(0, 8))
        self._preview_count_lbl = tk.Label(bottom, text='', bg=BG, fg='#6B7280',
                                           font=('Microsoft YaHei', 9))
        self._preview_count_lbl.pack(side=tk.LEFT)

    def _start_ocr_and_parse(self):
        """根据选中模式执行识别，完成后解析并跳到交互绘图"""
        if not self.image_paths:
            messagebox.showwarning('警告', '请先选择图片文件！')
            return
        mode = getattr(self, '_selected_ocr_mode', tk.StringVar()).get()

        # 识别完成的回调：解析并跳到交互绘图
        def _after_ocr():
            self.copy_and_parse_text()
            self.root.after(400, lambda: self._step_switch('交互绘图', 0))

        # 根据选中模式启动识别线程，识别结束时调用回调
        if mode == 'accurate':
            if not API_KEY or not SECRET_KEY:
                messagebox.showerror('错误', '请先配置高精度识别密钥！')
                return
            self._run_ocr_with_callback(self._perform_ocr_thread, _after_ocr)
        elif mode == 'basic':
            if not API_KEY_BASIC or not SECRET_KEY_BASIC:
                messagebox.showerror('错误', '请先配置快速识别密钥！')
                return
            self._run_ocr_with_callback(self._perform_quick_ocr_thread, _after_ocr)
        elif mode == 'general':
            if not API_KEY_GENERAL or not SECRET_KEY_GENERAL:
                messagebox.showerror('错误', '请先配置通用识别密钥！')
                return
            self._run_ocr_with_callback(self._perform_general_ocr_thread, _after_ocr)

    def _run_ocr_with_callback(self, thread_func, callback):
        """启动识别线程，完成后在主线程执行 callback"""
        self.ocr_btn.config(state=tk.DISABLED)
        self.quick_ocr_btn.config(state=tk.DISABLED)
        self.general_ocr_btn.config(state=tk.DISABLED)
        self.select_btn.config(state=tk.DISABLED)
        self.copy_btn.config(state=tk.DISABLED)
        self._set_status('running')

        def _thread_wrapper():
            thread_func()
            self.root.after(0, callback)
            self.root.after(0, lambda: self._set_status('done'))

        import threading
        threading.Thread(target=_thread_wrapper, daemon=True).start()


    def _step_switch(self, name, index):
        """切换步骤标签页"""
        BLUE = '#1A6FD4'
        BG = 'white'
        self._current_step = name
        for n, (col, num_lbl, name_lbl, sub_lbl, bar) in self._step_btns.items():
            if n == name:
                num_lbl.config(bg=BLUE, fg='white')
                name_lbl.config(fg=BLUE, font=('Microsoft YaHei', 9, 'bold'))
                sub_lbl.config(fg='#60A5FA')
                bar.config(bg=BLUE)
            else:
                num_lbl.config(bg='#E5E7EB', fg='#6B7280')
                name_lbl.config(fg='#6B7280', font=('Microsoft YaHei', 9))
                sub_lbl.config(fg='#9CA3AF')
                bar.config(bg=BG)

        for frame in self._classifier_pages.values():
            frame.pack_forget()
        self._classifier_pages[name].pack(fill=tk.BOTH, expand=True)

        # 交互绘图懒加载
        if name == '交互绘图' and not self.plot_initialized:
            self.setup_plot_tab()

        # 切换到分类表格后，强制 Treeview 重算内部布局（避免 pack_forget→pack 后的渲染残留）
        if name == '分类表格' and hasattr(self, 'tree'):
            self.root.after(10, self._tree_ensure_layout)

    def _tree_ensure_layout(self):
        """强制 Treeview 刷新内部几何，消除 pack_forget→pack 后的渲染残留"""
        try:
            if not self.tree.winfo_exists():
                return
            self.tree.update_idletasks()
            # 修改 height 属性触发 ttk 内部完整几何重算
            self.tree.configure(height=self.tree['height'])
        except Exception:
            pass

    def setup_left_panel(self):
        """左侧面板 — 内容随步骤动态切换"""
        PANEL_BG = '#F7F9FC'
        BORDER = '#DDE3EA'
        BLUE = '#1A6FD4'
        self._ocr_left.configure(bg=PANEL_BG)

        # text_input 保留但隐藏（load_from_text 需要它）
        self.text_input = tk.Text(self._ocr_left, height=1,
                                  font=('Consolas', 10))
        # 不 pack，仅作数据中转用

        # ── ① 分类表格页面板（空，顶部已有重置和字号）──
        self._panel_tree = tk.Frame(self._ocr_left, bg=PANEL_BG)

        # ── ② 交互绘图页面板 ──
        self._panel_plot = tk.Frame(self._ocr_left, bg=PANEL_BG)

        def sec(parent, title):
            tk.Label(parent, text=title, bg=PANEL_BG, fg='#374151',
                     font=('Microsoft YaHei', self.current_font_size, 'bold')).pack(
                         anchor='w', padx=16, pady=(16, 6))

        sec(self._panel_plot, '绘图模式切换')
        for text, val in [
            ('🖱 直线模式（左键加线/右键删线）', False),
            ('🎯 圈选模式（画圈提取数据）',       True),
        ]:
            tk.Radiobutton(self._panel_plot, text=text,
                           variable=self.enable_lasso_mode, value=val,
                           command=self.update_plot_view,
                           bg=PANEL_BG, font=('Microsoft YaHei', 9),
                           wraplength=190, justify='left').pack(
                               anchor='w', padx=16, pady=4)

        # ③ 文本报告页无面板（_panel_report 为空占位）
        self._panel_report = tk.Frame(self._ocr_left, bg=PANEL_BG)

        self._left_panels = {
            '分类表格': self._panel_tree,
            '交互绘图': self._panel_plot,
            '文本报告': self._panel_report,
        }


    def _update_ocr_btn_by_keys(self):
        """根据密钥配置更新识别模式按钮状态，并自动选中第一个可用模式"""
        has_accurate = bool(API_KEY and SECRET_KEY)
        has_basic    = bool(API_KEY_BASIC and SECRET_KEY_BASIC)
        has_general  = bool(API_KEY_GENERAL and SECRET_KEY_GENERAL)
        BLUE = '#1A6FD4'

        availability = {
            'accurate': has_accurate,
            'basic':    has_basic,
            'general':  has_general,
        }

        if not hasattr(self, '_mode_btns'):
            return

        # 更新按钮可用状态
        for mode, btn in self._mode_btns.items():
            btn.config(state=tk.NORMAL if availability[mode] else tk.DISABLED)

        # 自动选中第一个可用模式并高亮
        current = getattr(self, '_selected_ocr_mode', tk.StringVar()).get()
        if not availability.get(current):
            for mode in ('accurate', 'basic', 'general'):
                if availability[mode]:
                    self._selected_ocr_mode.set(mode)
                    break

        selected = self._selected_ocr_mode.get()
        for mode, btn in self._mode_btns.items():
            if mode == selected and availability[mode]:
                btn.config(bg=BLUE, fg='white',
                           highlightthickness=0)
            elif availability[mode]:
                btn.config(bg='white', fg=BLUE,
                           highlightthickness=1,
                           highlightbackground=BLUE)
            else:
                btn.config(bg='white', fg='#9CA3AF',
                           highlightthickness=1,
                           highlightbackground='#DDE3EA')

        # 开始识别按钮：有任一可用模式就启用
        any_available = any(availability.values())
        if hasattr(self, 'copy_btn'):
            self.copy_btn.config(state=tk.NORMAL if any_available else tk.DISABLED)

        hints = [n for n, v in [('高精度', has_accurate), ('快速', has_basic), ('通用', has_general)] if not v]
        if hints and hasattr(self, 'progress_label'):
            self.progress_label.config(
                text=f"⚠️ 未配置密钥：{'、'.join(hints)}",
                fg='orange'
            )

    def _has_ocr_key(self, ocr_type):
        if ocr_type == 'accurate':
            return bool(API_KEY and SECRET_KEY)
        if ocr_type == 'basic':
            return bool(API_KEY_BASIC and SECRET_KEY_BASIC)
        if ocr_type == 'general':
            return bool(API_KEY_GENERAL and SECRET_KEY_GENERAL)
        return False

    def setup_results_tab(self):
        """设置分类表格页 + 文本报告页"""
        BG = 'white'
        BORDER = '#DDE3EA'
        BLUE = '#1A6FD4'
        PANEL_BG = '#F7F9FC'

        def flat_btn(parent, text, cmd, bg='white', fg='#374151', **kw):
            b = tk.Button(parent, text=text, command=cmd, bg=bg, fg=fg,
                          relief='flat', bd=0, cursor='hand2',
                          font=('Microsoft YaHei', 9),
                          highlightthickness=1, highlightbackground=BORDER,
                          padx=8, pady=4, **kw)
            return b

        # ════════════════════════════════
        # 分类表格页 (self.tab_res)
        # ════════════════════════════════
        self.tab_res.configure(bg=BG)

        # 工具栏
        t_bar = tk.Frame(self.tab_res, bg=BG,
                         highlightthickness=1, highlightbackground=BORDER)
        t_bar.pack(fill=tk.X, padx=0, pady=0)

        bar_inner = tk.Frame(t_bar, bg=BG)
        bar_inner.pack(fill=tk.X, padx=10, pady=6)

        for text, cmd, bg, fg in [
            ('➕ 新增', self.open_add_data_dialog, '#EFF6FF', BLUE),
            ('❌ 删除', self.delete_selected_data, '#FEF2F2', '#EF4444'),
            ('↑', self.move_item_up, 'white', '#374151'),
            ('↓', self.move_item_down, 'white', '#374151'),
        ]:
            flat_btn(bar_inner, text, cmd, bg=bg, fg=fg).pack(side=tk.LEFT, padx=(0, 4))

        tk.Frame(bar_inner, bg=BORDER, width=1).pack(side=tk.LEFT, fill=tk.Y, padx=6)

        self.undo_btn = flat_btn(bar_inner, '↶ 撤销', self.undo_classifier_action,
                                  state=tk.DISABLED)
        self.undo_btn.pack(side=tk.LEFT, padx=(0, 4))
        flat_btn(bar_inner, '📋 历史', self.show_history_panel).pack(side=tk.LEFT, padx=(0, 4))

        tk.Frame(bar_inner, bg=BORDER, width=1).pack(side=tk.LEFT, fill=tk.Y, padx=6)

        flat_btn(bar_inner, '拆分A组', self.apply_corrections,
                 bg='#EFF6FF', fg=BLUE).pack(side=tk.LEFT, padx=(0, 4))
        flat_btn(bar_inner, '⚙ 空格/清理', self.show_space_settings).pack(side=tk.LEFT, padx=(0, 4))
        flat_btn(bar_inner, '🎨 字体样式', self.show_font_style_settings).pack(side=tk.LEFT, padx=(0, 4))

        # 消息区
        self.message_area = tk.Frame(bar_inner, bg=BG)
        self.message_area.pack(side=tk.RIGHT)

        # 表格
        tree_frame = tk.Frame(self.tab_res, bg=BG)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        vsb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree = ttk.Treeview(
            tree_frame,
            columns=('Label', 'Status', 'Group', 'Index', 'Category', 'CategoryKey'),
            show='headings',
            displaycolumns=('Category', 'Label', 'Status', 'Group'),
            yscrollcommand=vsb.set
        )
        vsb.config(command=self.tree.yview)

        self.tree.heading('Category', text='分类')
        self.tree.heading('Label',    text='名称')
        self.tree.heading('Status',   text='C组')
        self.tree.heading('Group',    text='组')
        self.tree.column('Index',       width=0,   stretch=False)
        self.tree.column('CategoryKey', width=0,   stretch=False)
        self.tree.column('Category',    width=120, minwidth=80,  stretch=False)
        self.tree.column('Label',       width=400, minwidth=200, stretch=True)
        self.tree.column('Status',      width=60,  minwidth=50,  stretch=False)
        self.tree.column('Group',       width=55,  minwidth=40,  stretch=False)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 绑定事件
        self.tree.bind('<ButtonPress-1>',   self.on_drag_start)
        self.tree.bind('<B1-Motion>',       self.on_drag_motion)
        self.tree.bind('<ButtonRelease-1>', self.on_drag_release)
        self.tree.bind('<ButtonPress-1>',   self.on_long_press_start,  add='+')
        self.tree.bind('<ButtonRelease-1>', self.on_long_press_cancel, add='+')
        self.tree.bind('<Button-3>',        self.on_right_click)
        self.tree.bind('<Double-1>',        self.on_double_click)
        self.tree.bind('<space>',           self.split_group_a_items)
        self.tree.bind('<Insert>',          lambda e: self.open_add_data_dialog())
        self.tree.bind('<Delete>',          lambda e: self.delete_selected_data())
        self.tree.bind('<Up>',              self._on_tree_up)
        self.tree.bind('<Down>',            self._on_tree_down)
        self.tree.bind('<Control-z>',       lambda e: self.undo_classifier_action())
        self.tree.bind('<KeyPress-plus>',      lambda e: self.set_selected_group_by_shortcut('D'))
        self.tree.bind('<KeyPress-KP_Add>',    lambda e: self.set_selected_group_by_shortcut('D'))
        self.tree.bind('<KeyPress-minus>',     lambda e: self.set_selected_group_by_shortcut('C'))
        self.tree.bind('<KeyPress-KP_Subtract>', lambda e: self.set_selected_group_by_shortcut('C'))

        # ════════════════════════════════
        # 文本报告页 (self.tab_report_outer)
        # ════════════════════════════════
        self.tab_report = self.tab_report_outer
        self.tab_report.configure(bg=BG)

        r_bar = tk.Frame(self.tab_report, bg=BG,
                         highlightthickness=1, highlightbackground=BORDER)
        r_bar.pack(fill=tk.X)
        r_inner = tk.Frame(r_bar, bg=BG)
        r_inner.pack(fill=tk.X, padx=10, pady=6)

        flat_btn(r_inner, '💾 导出 TXT',  self.export_txt_file,
                 bg='#EFF6FF', fg=BLUE).pack(side=tk.LEFT, padx=(0, 4))
        flat_btn(r_inner, '导出 Excel',   self.export_excel_file,
                 bg='#F0FDF4', fg='#16A34A').pack(side=tk.LEFT, padx=(0, 4))
        flat_btn(r_inner, '📜 导出历史',  self.show_export_history).pack(side=tk.LEFT, padx=(0, 4))

        tk.Frame(r_inner, bg=BORDER, width=1).pack(side=tk.LEFT, fill=tk.Y, padx=6)

        flat_btn(r_inner, '繁→简', self.convert_to_simplified).pack(side=tk.LEFT, padx=(0, 4))
        flat_btn(r_inner, '简→繁', self.convert_to_traditional).pack(side=tk.LEFT, padx=(0, 4))

        tk.Frame(r_inner, bg=BORDER, width=1).pack(side=tk.LEFT, fill=tk.Y, padx=6)

        flat_btn(r_inner, '🔄 替换',   self._run_replace_rules_report).pack(side=tk.LEFT, padx=(0, 4))
        flat_btn(r_inner, '⚙ 替换设置', self.show_replace_settings).pack(side=tk.LEFT, padx=(0, 4))

        tk.Frame(r_inner, bg=BORDER, width=1).pack(side=tk.LEFT, fill=tk.Y, padx=6)

        self.separator_btn = flat_btn(r_inner, '分隔: ----', self.toggle_report_separator)
        self.separator_btn.pack(side=tk.LEFT, padx=(0, 4))
        self.report_format_btn = flat_btn(r_inner, '格式: 仅名称', self.toggle_report_format)
        self.report_format_btn.pack(side=tk.LEFT, padx=(0, 4))

        self.report_text = scrolledtext.ScrolledText(
            self.tab_report, wrap=tk.WORD,
            font=('Microsoft YaHei', 11),
            relief='flat', bd=0,
            bg='white'
        )
        self.report_text.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        self.load_report_config()


    def setup_plot_tab(self):
        """定义绘图标签页内容"""
        if self.plot_initialized:
            return
        ensure_matplotlib_loaded()
        for widget in self.tab_plt.winfo_children():
            widget.destroy()
        self.fig, self.ax = plt.subplots(figsize=(6, 6), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.tab_plt)
        self.canvas.mpl_connect('button_press_event', self.on_plot_click)

        # 添加 matplotlib 工具栏
        toolbar = NavigationToolbar2Tk(self.canvas, self.tab_plt)
        toolbar.update()

        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.plot_initialized = True
        self.update_plot_view()

    def setup_plot_placeholder(self):
        """创建轻量占位页，首次进入绘图区时再加载 matplotlib。"""
        placeholder = tk.Frame(self.tab_plt, bg="white")
        placeholder.pack(fill=tk.BOTH, expand=True)
        tk.Label(
            placeholder,
            text="交互绘图区将在首次打开时加载",
            bg="white",
            fg="#666",
            font=("Microsoft YaHei", 13)
        ).pack(expand=True)

    def on_classifier_tab_changed(self, event=None):
        """切换到绘图区时再初始化 matplotlib。"""
        selected_tab = self.classifier_notebook.select()
        if selected_tab == str(self.tab_plt) and not self.plot_initialized:
            self.setup_plot_tab()

    # ===============================================
    # 数据分类功能方法
    # ===============================================
    def _create_classifier_snapshot(self):
        """创建分类树可撤销状态快照。"""
        # 记录当前选中条目的 df 索引
        selected_df_indices = []
        if hasattr(self, 'tree'):
            for iid in self.tree.selection():
                if self.is_tree_data_item(iid):
                    vals = self.tree.item(iid, 'values')
                    if vals and len(vals) > 3:
                        try:
                            selected_df_indices.append(int(vals[3]))
                        except:
                            pass
        return {
            'df': self.df.copy(deep=True),
            'category_list': copy.deepcopy(self.category_list),
            'marked_indices': set(self.marked_indices),
            'thresholds': list(self.thresholds),
            'custom_cat_names': copy.deepcopy(self.custom_cat_names),
            'selected_df_indices': selected_df_indices,
        }

    def push_undo_snapshot(self, action_name="操作"):
        """保存当前状态到历史栈（操作前调用）。"""
        try:
            snapshot = self._create_classifier_snapshot()
            snapshot['action_name'] = action_name
            self.redo_stack = []  # 新操作清空 redo
            self.undo_stack.append(snapshot)
            if len(self.undo_stack) > self.undo_limit:
                self.undo_stack.pop(0)
            self.update_undo_button_state()
            self._refresh_history_panel()
        except Exception as e:
            print(f"保存撤销快照失败: {e}")

    def commit_undo_snapshot(self, action_name=None):
        """兼容方法，不再需要，保留避免调用报错。"""
        pass

    def update_undo_button_state(self):
        """刷新撤销按钮可用状态。"""
        if hasattr(self, 'undo_btn'):
            self.undo_btn.config(state=tk.NORMAL if self.undo_stack else tk.DISABLED)

    def undo_classifier_action(self):
        """撤销上一次分类树修改。"""
        if not self.undo_stack:
            self.show_temp_message("没有可撤销的操作")
            return
        try:
            # 把当前状态压入 redo 栈
            current = self._create_classifier_snapshot()
            current['action_name'] = '（撤销前）'
            self.redo_stack.append(current)

            snapshot = self.undo_stack.pop()
            self._restore_snapshot(snapshot)
            self.update_undo_button_state()
            self._refresh_history_panel()
            self.show_temp_message(f"↶ 已撤销：{snapshot.get('action_name', '上一步操作')}")
        except Exception as e:
            messagebox.showerror("错误", f"撤销失败：{str(e)}")

    def _restore_snapshot(self, snapshot):
        """恢复到指定快照状态。"""
        self.df = snapshot['df'].copy(deep=True)
        self.category_list = copy.deepcopy(snapshot['category_list'])
        self.marked_indices = set(snapshot['marked_indices'])
        self.thresholds = list(snapshot['thresholds'])
        self.custom_cat_names = copy.deepcopy(snapshot['custom_cat_names'])
        self.refresh_all()

        # 恢复选中位置
        selected_df_indices = snapshot.get('selected_df_indices', [])
        if selected_df_indices and hasattr(self, 'tree'):
            # 遍历表格找到对应的 iid
            target_iids = []
            for iid in self.tree.get_children(""):
                vals = self.tree.item(iid, 'values')
                if vals and len(vals) > 3:
                    try:
                        if int(vals[3]) in selected_df_indices:
                            target_iids.append(iid)
                    except:
                        pass
            if target_iids:
                self.tree.selection_set(target_iids)
                self.tree.focus(target_iids[0])
                self.tree.see(target_iids[0])

    def jump_to_history(self, index):
        """跳转到历史记录中的某一步（PS风格）。"""
        try:
            if index < 0 or index >= len(self.undo_stack):
                return
            # 把当前状态和 index 之后的步骤都移到 redo 栈
            while len(self.undo_stack) > index + 1:
                self.redo_stack.append(self.undo_stack.pop())
            snapshot = self.undo_stack[index]
            self._restore_snapshot(snapshot)
            self.update_undo_button_state()
            self._refresh_history_panel()
            self.show_temp_message(f"↩ 已跳转：{snapshot.get('action_name', '')}")
        except Exception as e:
            messagebox.showerror("错误", f"跳转失败：{str(e)}")

    def show_history_panel(self):
        """显示历史记录浮窗。"""
        if hasattr(self, '_history_win') and self._history_win and self._history_win.winfo_exists():
            self._history_win.lift()
            return

        win = tk.Toplevel(self.root)
        win.withdraw()
        win.title("历史记录")
        self.center_window(win, 260, 420)
        win.resizable(False, True)
        win.transient(self.root)
        self._history_win = win

        tk.Label(win, text="📋 历史记录", font=("Microsoft YaHei", 11, "bold"),
                 bg="#1E293B", fg="white").pack(fill=tk.X, ipady=8)

        frame = tk.Frame(win)
        frame.pack(fill=tk.BOTH, expand=True)

        sb = ttk.Scrollbar(frame, orient=tk.VERTICAL)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        self._history_listbox = tk.Listbox(frame, font=("Microsoft YaHei", 10),
                                           yscrollcommand=sb.set, activestyle='dotbox',
                                           selectbackground="#2563EB", selectforeground="white",
                                           relief="flat", bd=0)
        self._history_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.config(command=self._history_listbox.yview)

        def on_select(e):
            sel = self._history_listbox.curselection()
            if sel:
                self.jump_to_history(sel[0])

        self._history_listbox.bind('<<ListboxSelect>>', on_select)

        btn_frame = tk.Frame(win, bg="#F1F5F9")
        btn_frame.pack(fill=tk.X, pady=4)
        tk.Button(btn_frame, text="清空历史", command=self._clear_history,
                  bg="#EF4444", fg="white", relief="flat", font=("Microsoft YaHei", 9),
                  padx=10, pady=4).pack(side=tk.RIGHT, padx=8)

        self._refresh_history_panel()
        win.protocol("WM_DELETE_WINDOW", lambda: setattr(self, '_history_win', None) or win.destroy())
        win.after_idle(lambda: (self.center_window(win, 260, 420), win.deiconify(), win.lift()))

    def _refresh_history_panel(self):
        """刷新历史记录面板内容。"""
        if not hasattr(self, '_history_listbox') or not self._history_listbox.winfo_exists():
            return
        self._history_listbox.delete(0, tk.END)
        for i, snap in enumerate(self.undo_stack):
            name = snap.get('action_name', '操作')
            self._history_listbox.insert(tk.END, f"  {i + 1}.  {name}")
        # 选中最后一步（当前状态）
        if self.undo_stack:
            last = len(self.undo_stack) - 1
            self._history_listbox.selection_set(last)
            self._history_listbox.see(last)

    def _clear_history(self):
        """清空历史记录。"""
        if messagebox.askyesno("确认", "清空所有历史记录？"):
            self.undo_stack.clear()
            self.redo_stack = []
            self.update_undo_button_state()
            self._refresh_history_panel()
            self.show_temp_message("✓ 历史记录已清空")

    def save_current_order(self):
        """保存当前树视图中的顺序到DataFrame"""
        try:
            self.update_order_from_tree()
            
            # 显示调试信息
            if 'Order' in self.df.columns:
                order_info = f"已保存 {len(self.df)} 个项目的位置顺序"
                self.show_temp_message("✓ 位置顺序已固定！")
                messagebox.showinfo("成功", f"{order_info}\n即使刷新数据，文字顺序也不会改变。")
            else:
                messagebox.showwarning("提示", "DataFrame中没有Order列，无法保存顺序")
        except Exception as e:
            messagebox.showerror("错误", f"保存顺序失败：{str(e)}")

    def reorder_dataframe(self):
        """Rebuild the Order column while preserving the intended row order."""
        if 'Order' not in self.df.columns:
            self.df['Order'] = range(len(self.df))
        else:
            self.df = self.df.sort_values('Order').reset_index(drop=True)
            self.df['Order'] = range(len(self.df))

    def _split_group_a_preserve_tree_order(self, progress_callback=None):
        """Split A-group labels in place without changing category tree order."""
        if self.df.empty:
            return 0

        if 'Order' not in self.df.columns:
            self.df['Order'] = range(len(self.df))
        if 'LassoTag' not in self.df.columns:
            self.df['LassoTag'] = ''
        self.df['LassoTag'] = self.df['LassoTag'].fillna('')

        rows = []
        old_to_new_indices = {}
        split_count = 0
        total_count = int(((self.df['Group'] == 'A') & (self.df['Label'].astype(str).str.len() > 2)).sum())

        for old_idx, row in self.df.sort_values('Order').iterrows():
            label = str(row['Label'])
            should_split = row['Group'] == 'A' and len(label) > 2
            if progress_callback and should_split:
                progress_callback(split_count + 1, total_count, label)

            if should_split:
                first_row = row.copy()
                second_row = row.copy()
                first_row['Label'] = label[:2]
                first_row['Group'] = 'A'
                second_row['Label'] = label[2:]
                second_row['Group'] = 'C'
                if 'X' in second_row.index:
                    second_row['X'] = second_row['X'] + 10

                first_new_idx = len(rows)
                rows.append(first_row.to_dict())
                second_new_idx = len(rows)
                rows.append(second_row.to_dict())
                old_to_new_indices[old_idx] = [first_new_idx, second_new_idx]
                split_count += 1
            else:
                new_idx = len(rows)
                rows.append(row.to_dict())
                old_to_new_indices[old_idx] = [new_idx]

        if split_count == 0:
            return 0

        self.df = pd.DataFrame(rows, columns=self.df.columns).reset_index(drop=True)
        self.df['Order'] = range(len(self.df))

        def expand_old_indices(indices):
            expanded = []
            seen = set()
            for old_idx in indices:
                for new_idx in old_to_new_indices.get(old_idx, []):
                    if new_idx not in seen:
                        expanded.append(new_idx)
                        seen.add(new_idx)
            return expanded

        for cat in self.category_list:
            base_order = cat.get('ordered_indices')
            if base_order is None:
                base_order = sorted(cat.get('indices', set()), key=lambda idx: old_to_new_indices.get(idx, [idx])[0])
            else:
                base_order = list(base_order)
                missing = [idx for idx in cat.get('indices', set()) if idx not in base_order]
                base_order.extend(sorted(missing, key=lambda idx: old_to_new_indices.get(idx, [idx])[0]))

            new_ordered = expand_old_indices(base_order)
            cat['indices'] = set(new_ordered)
            cat['ordered_indices'] = new_ordered

        self.marked_indices = set(expand_old_indices(self.marked_indices))
        return split_count

    def _shift_category_indices_after_insert(self, insert_pos, count=1):
        """Keep lasso categories aligned after inserting rows into df."""
        def shift_idx(idx):
            return idx + count if idx >= insert_pos else idx

        for cat in self.category_list:
            cat['indices'] = {shift_idx(idx) for idx in cat.get('indices', set())}
            if cat.get('ordered_indices') is not None:
                cat['ordered_indices'] = [shift_idx(idx) for idx in cat['ordered_indices']]
        self.marked_indices = {shift_idx(idx) for idx in self.marked_indices}

    def _shift_tree_indices_after_insert(self, insert_pos, count=1):
        """Keep hidden row indices in the table aligned after inserting rows."""
        if not hasattr(self, 'tree'):
            return
        for iid in self.tree.get_children(""):
            values = self.tree.item(iid, 'values')
            if values and len(values) > 3:
                idx = int(values[3])
                if idx >= insert_pos:
                    self.set_tree_row_values(iid, values[0], values[1], values[2], idx + count)

    def _shift_category_indices_after_delete(self, deleted_indices):
        """Keep lasso categories aligned after deleting rows from df."""
        deleted = set(deleted_indices)
        if not deleted:
            return

        deleted_sorted = sorted(deleted)

        def map_idx(idx):
            if idx in deleted:
                return None
            shift = sum(1 for deleted_idx in deleted_sorted if deleted_idx < idx)
            return idx - shift

        for cat in self.category_list:
            remapped = [map_idx(idx) for idx in cat.get('indices', set())]
            cat['indices'] = {idx for idx in remapped if idx is not None}
            if cat.get('ordered_indices') is not None:
                ordered = [map_idx(idx) for idx in cat['ordered_indices']]
                cat['ordered_indices'] = [idx for idx in ordered if idx is not None]

        marked = [map_idx(idx) for idx in self.marked_indices]
        self.marked_indices = {idx for idx in marked if idx is not None}

    def _shift_tree_indices_after_delete(self, deleted_indices):
        """Keep hidden row indices in the table aligned after deleting rows."""
        deleted = set(deleted_indices)
        if not deleted or not hasattr(self, 'tree'):
            return
        deleted_sorted = sorted(deleted)
        for iid in self.tree.get_children(""):
            values = self.tree.item(iid, 'values')
            if not values or len(values) <= 3:
                continue
            idx = int(values[3])
            if idx in deleted:
                continue
            shift = sum(1 for deleted_idx in deleted_sorted if deleted_idx < idx)
            if shift:
                self.set_tree_row_values(iid, values[0], values[1], values[2], idx - shift)

    def _on_tree_up(self, event):
        """↑ 键：移动选中条目向上，阻止默认光标跳行"""
        self.move_item_up()
        return "break"

    def _on_tree_down(self, event):
        """↓ 键：移动选中条目向下，阻止默认光标跳行"""
        self.move_item_down()
        return "break"

    def move_item_up(self):
        """上移项目"""
        selected = self.tree.selection()
        if not selected:
            return

        undo_snapshot = self._create_classifier_snapshot()
        moved_items = []
        for item in selected:
            if self.is_tree_data_item(item):
                idx = self.tree.index(item)
                if idx > 0:
                    # 获取当前项目的DataFrame索引
                    values = self.tree.item(item, 'values')
                    if values and len(values) > 3:
                        current_df_idx = int(values[3])
                        moved_items.append(current_df_idx)
                    
                    self.tree.move(item, "", idx - 1)
        
        # 更新DataFrame中的Order
        if moved_items:
            labels = [self.df.loc[i, 'Label'] if i in self.df.index else str(i) for i in moved_items[:2]]
            label_str = '、'.join(labels) + ('…' if len(moved_items) > 2 else '')
            undo_snapshot['action_name'] = f"上移 — {label_str}"
            self.undo_stack.append(undo_snapshot)
            if len(self.undo_stack) > self.undo_limit:
                self.undo_stack.pop(0)
            self.update_undo_button_state()
            self._refresh_history_panel()
            self.update_order_from_tree()

        self.generate_report_from_tree()
        # 移动后让焦点和视图跟随被移动的条目
        if selected:
            self.tree.focus(selected[0])
            self.tree.see(selected[0])

    def move_item_down(self):
        """下移项目"""
        selected = list(reversed(self.tree.selection()))
        if not selected:
            return

        undo_snapshot = self._create_classifier_snapshot()
        moved_items = []
        for item in selected:
            if self.is_tree_data_item(item):
                idx = self.tree.index(item)
                siblings = self.tree.get_children("")
                if idx < len(siblings) - 1:
                    # 获取当前项目的DataFrame索引
                    values = self.tree.item(item, 'values')
                    if values and len(values) > 3:
                        current_df_idx = int(values[3])
                        moved_items.append(current_df_idx)
                    
                    self.tree.move(item, "", idx + 1)
        
        # 更新DataFrame中的Order
        if moved_items:
            labels = [self.df.loc[i, 'Label'] if i in self.df.index else str(i) for i in moved_items[:2]]
            label_str = '、'.join(labels) + ('…' if len(moved_items) > 2 else '')
            undo_snapshot['action_name'] = f"下移 — {label_str}"
            self.undo_stack.append(undo_snapshot)
            if len(self.undo_stack) > self.undo_limit:
                self.undo_stack.pop(0)
            self.update_undo_button_state()
            self._refresh_history_panel()
            self.update_order_from_tree()

        self.generate_report_from_tree()
        # 移动后让焦点和视图跟随被移动的条目
        if selected:
            self.tree.focus(selected[0])
            self.tree.see(selected[0])

    def update_order_from_tree(self):
        """从树视图的当前顺序更新DataFrame中的Order列，同时更新圈选分类的ordered_indices"""
        if 'Order' not in self.df.columns:
            self.df['Order'] = range(len(self.df))
            return

        order_counter = 0

        # 遍历表格中的当前行顺序，同时收集每个分类的新顺序
        cat_new_order = {}  # category_name -> [df_idx, ...]
        for data_item in self.tree.get_children(""):
            values = self.tree.item(data_item, 'values')
            if values and len(values) > 3:
                cat_name = self.get_tree_item_category_key(data_item)
                cat_new_order.setdefault(cat_name, [])
                df_idx = int(values[3])
                if df_idx in self.df.index:
                    self.df.loc[df_idx, 'Order'] = order_counter
                    order_counter += 1
                    cat_new_order[cat_name].append(df_idx)

        # 同步更新圈选分类的 ordered_indices
        for cat in self.category_list:
            name = cat['name']
            if name in cat_new_order:
                cat['ordered_indices'] = cat_new_order[name]

    def open_add_data_dialog(self):
        """打开新增条目对话框"""
        dialog = self.create_popup_window(self.root, "新增条目", "add_data_dialog", 400, 280)
        dialog.configure(bg="#F8FAFC")
        dialog.resizable(False, False)

        # 准备默认数据
        default_y, default_x, insert_pos = 0.0, 0.0, len(self.df)
        insert_after_label = "末尾"
        selected = self.tree.selection()
        if selected and self.is_tree_data_item(selected[0]):
            vals = self.tree.item(selected[0], 'values')
            if len(vals) > 3:
                row_idx = int(vals[3])
                if row_idx in self.df.index:
                    default_y = self.df.loc[row_idx, 'Y'] + 1
                    default_x = self.df.loc[row_idx, 'X']
                    insert_pos = self.df.index.get_loc(row_idx) + 1
                    insert_after_label = str(vals[0])[:12] + ("…" if len(str(vals[0])) > 12 else "")

        # 默认组：跟选中条目一致
        default_group = 'B'
        if selected and self.is_tree_data_item(selected[0]):
            vals = self.tree.item(selected[0], 'values')
            if len(vals) > 2:
                default_group = self._get_group_from_values(vals)

        # ── 顶部标题栏 ──
        header = tk.Frame(dialog, bg="#22C55E", height=52)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text="＋  新增条目", bg="#22C55E", fg="white",
                 font=("Microsoft YaHei", 13, "bold")).pack(side=tk.LEFT, padx=18, pady=12)

        # ── 插入位置提示 ──
        hint_frame = tk.Frame(dialog, bg="#F0FDF4", bd=0)
        hint_frame.pack(fill=tk.X, padx=16, pady=(12, 0))
        tk.Label(hint_frame, text=f"📍 将插入到「{insert_after_label}」下方",
                 bg="#F0FDF4", fg="#16A34A",
                 font=("Microsoft YaHei", 9)).pack(anchor="w", padx=10, pady=6)

        # ── 表单 ──
        form = tk.Frame(dialog, bg="#F8FAFC")
        form.pack(fill=tk.X, padx=16, pady=(10, 0))

        tk.Label(form, text="名称", bg="#F8FAFC", fg="#374151",
                 font=("Microsoft YaHei", self.current_font_size, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 6))
        n_ent = tk.Entry(form, font=("Microsoft YaHei", 11), bg="white",
                         relief="flat", bd=0, highlightthickness=2,
                         highlightbackground="#D1D5DB", highlightcolor="#22C55E")
        n_ent.grid(row=0, column=1, sticky="ew", padx=(10, 0), pady=(0, 6), ipady=5)
        n_ent.focus_set()

        tk.Label(form, text="组", bg="#F8FAFC", fg="#374151",
                 font=("Microsoft YaHei", self.current_font_size, "bold")).grid(row=1, column=0, sticky="w", pady=(6, 0))

        # A/B/C 三个切换按钮
        grp_frame = tk.Frame(form, bg="#F8FAFC")
        grp_frame.grid(row=1, column=1, sticky="w", padx=(10, 0), pady=(6, 0))
        selected_group = tk.StringVar(value=default_group)
        grp_btns = {}

        def set_group(g):
            selected_group.set(g)
            colors = {
                'A': ("#EF4444", "#FEE2E2"),
                'B': ("#2563EB", "#DBEAFE"),
                'C': ("#16A34A", "#DCFCE7"),
                'D': ("#7C3AED", "#EDE9FE"),
            }
            for grp, btn in grp_btns.items():
                if grp == g:
                    btn.config(bg=colors[grp][0], fg="white", relief="flat")
                else:
                    btn.config(bg=colors[grp][1], fg=colors[grp][0], relief="flat")

        for g in ['A', 'B', 'C', 'D']:
            b = tk.Button(grp_frame, text=f"  {g}  ", font=("Microsoft YaHei", 10, "bold"),
                          relief="flat", bd=0, cursor="hand2", padx=6, pady=4,
                          command=lambda grp=g: set_group(grp))
            b.pack(side=tk.LEFT, padx=(0, 6))
            grp_btns[g] = b
        set_group(default_group)

        form.columnconfigure(1, weight=1)

        # 名称变化时自动推断组
        def on_name_change(*args):
            name = n_ent.get().strip()
            if name:
                g = self.get_group_by_text_color(name)
                set_group(g)
        n_ent.bind('<KeyRelease>', on_name_change)

        # ── 按钮区 ──
        btn_frame = tk.Frame(dialog, bg="#F8FAFC")
        btn_frame.pack(fill=tk.X, padx=16, pady=(16, 14))

        def do_save(keep_open=False):
            nonlocal insert_pos, selected, default_y, default_x
            name = n_ent.get().strip()
            if not name:
                n_ent.config(highlightbackground="#EF4444")
                n_ent.focus_set()
                return
            group_val = selected_group.get()
            try:
                self.push_undo_snapshot(f"新增条目 — {name}")

                # 计算 Order
                if insert_pos == 0:
                    new_order = -1
                elif insert_pos >= len(self.df):
                    new_order = float(len(self.df))
                else:
                    prev_order = self.df.iloc[insert_pos - 1]['Order'] if insert_pos > 0 else -1
                    next_order = self.df.iloc[insert_pos]['Order'] if insert_pos < len(self.df) else float(len(self.df))
                    new_order = (prev_order + next_order) / 2

                # 检测圈选分类
                lasso_tag = ''
                parent_cat = None
                if selected and self.is_tree_data_item(selected[0]):
                    vals = self.tree.item(selected[0], 'values')
                    if len(vals) > 3:
                        row_idx = int(vals[3])
                        if 'LassoTag' in self.df.columns and row_idx in self.df.index:
                            lasso_tag = self.df.loc[row_idx, 'LassoTag']
                            if lasso_tag:
                                for cat in self.category_list:
                                    if cat['name'] == lasso_tag:
                                        parent_cat = cat
                                        break

                row_data = {'Label': name, 'Y': default_y, 'X': default_x,
                            'Group': group_val, 'Order': new_order}
                if 'LassoTag' in self.df.columns:
                    row_data['LassoTag'] = lasso_tag
                row = pd.DataFrame([row_data])
                self.df = pd.concat([self.df.iloc[:insert_pos], row,
                                     self.df.iloc[insert_pos:]]).reset_index(drop=True)
                self.reorder_dataframe()
                self._shift_category_indices_after_insert(insert_pos)
                self._shift_tree_indices_after_insert(insert_pos)

                if parent_cat is not None:
                    new_idx = insert_pos
                    parent_cat['indices'].add(new_idx)
                    if parent_cat.get('ordered_indices') is not None:
                        ref_idx = int(self.tree.item(selected[0], 'values')[3])
                        try:
                            pos = parent_cat['ordered_indices'].index(ref_idx)
                            parent_cat['ordered_indices'].insert(pos + 1, new_idx)
                        except ValueError:
                            parent_cat['ordered_indices'].append(new_idx)

                # 直接插入树行
                new_df_idx = insert_pos
                new_status = "☑" if group_val == 'C' else "☐"
                item_tags = self.get_item_tags(name, group_val, False)
                display_category = self.get_tree_item_category(selected[0]) if selected and self.is_tree_data_item(selected[0]) else "5"
                category_key = lasso_tag or (self.get_tree_item_category_key(selected[0]) if selected and self.is_tree_data_item(selected[0]) else "数据区")
                if selected and self.is_tree_data_item(selected[0]):
                    ref_iid = selected[0]
                    ref_tree_pos = self.tree.index(ref_iid)
                    new_iid = self.tree.insert("", ref_tree_pos + 1,
                                               values=(name, new_status, group_val, new_df_idx, display_category, category_key),
                                               tags=tuple(item_tags))
                else:
                    new_iid = self.tree.insert("", "end",
                                               values=(name, new_status, group_val, new_df_idx, display_category, category_key),
                                               tags=tuple(item_tags))

                self.tree.selection_set(new_iid)
                self.tree.focus(new_iid)
                self.tree.see(new_iid)
                self.generate_report_from_tree()

                if keep_open:
                    # 下次插入紧接在刚新增的行后面
                    insert_pos = insert_pos + 1
                    selected = [new_iid]
                    default_y = default_y + 1
                    n_ent.delete(0, tk.END)
                    n_ent.config(highlightbackground="#D1D5DB")
                    n_ent.focus_set()
                else:
                    dialog.destroy()

            except Exception as e:
                messagebox.showerror("错误", f"添加失败: {e}", parent=dialog)

        tk.Button(btn_frame, text="保存", command=lambda: do_save(False),
                  bg="#22C55E", fg="white", font=("Microsoft YaHei", 10, "bold"),
                  relief="flat", bd=0, padx=18, pady=7, cursor="hand2").pack(side=tk.LEFT)
        tk.Button(btn_frame, text="保存并继续", command=lambda: do_save(True),
                  bg="#2563EB", fg="white", font=("Microsoft YaHei", 10),
                  relief="flat", bd=0, padx=18, pady=7, cursor="hand2").pack(side=tk.LEFT, padx=(8, 0))
        tk.Button(btn_frame, text="取消", command=dialog.destroy,
                  bg="#E5E7EB", fg="#374151", font=("Microsoft YaHei", 10),
                  relief="flat", bd=0, padx=18, pady=7, cursor="hand2").pack(side=tk.LEFT, padx=(8, 0))
        tk.Label(btn_frame, text="Enter 保存", bg="#F8FAFC", fg="#9CA3AF",
                 font=("Microsoft YaHei", 8)).pack(side=tk.RIGHT, padx=4)

        dialog.bind('<Return>', lambda e: do_save(False))
        dialog.bind('<Escape>', lambda e: dialog.destroy())

    def on_drag_start(self, event):
        """开始拖拽或处理特殊列点击"""
        self.tree.focus_set()
        self.drag_source_item = None
        self.drag_source_index = None
        item = self.tree.identify_row(event.y)
        column = self.tree.identify_column(event.x)

        # 单击复选框列 - 切换C组状态
        if item and self.is_tree_data_item(item) and column == '#3':
            self.toggle_c_group(item)
            return

        # 检查是否点击了组列
        if item and self.is_tree_data_item(item) and column == '#4':
            self.show_group_dropdown(item, event)
            return

        # 正常的拖拽逻辑
        if item and self.is_tree_data_item(item):
            self.drag_source_item = item
            values = self.tree.item(item, 'values')
            if values and len(values) > 3:
                try:
                    self.drag_source_index = int(values[3])
                except (TypeError, ValueError):
                    self.drag_source_index = None
            self.tree.configure(cursor="hand2")
    
    def show_group_dropdown(self, iid, event):
        """显示组选择下拉菜单（Excel内嵌Combobox风格）"""
        try:
            values = self.tree.item(iid, 'values')
            if not values or len(values) < 3:
                return

            current_group = self._get_group_from_values(values)

            # 获取单元格位置
            bbox = self.tree.bbox(iid, '#4')
            if not bbox:
                return
            x, y, width, height = bbox

            # 如果已有编辑器，先销毁
            if hasattr(self, '_group_combo') and self._group_combo.winfo_exists():
                self._group_combo.destroy()

            combo = ttk.Combobox(self.tree, values=['A', 'B', 'C', 'D'],
                                 state='readonly',
                                 font=("Microsoft YaHei", self.current_font_size))
            combo.set(current_group)
            combo.place(x=x, y=y, width=width + 2, height=height + 2)
            combo.focus_set()
            combo.event_generate('<Button-1>')  # 自动展开下拉

            self._group_combo = combo
            self._group_combo_iid = iid

            def on_select(e):
                new_group = combo.get()
                combo.destroy()
                self.set_group_value(iid, new_group)

            def on_focus_out(e):
                try:
                    combo.destroy()
                except:
                    pass

            combo.bind('<<ComboboxSelected>>', on_select)
            combo.bind('<FocusOut>', on_focus_out)
            combo.bind('<Escape>', lambda e: combo.destroy())

        except Exception as e:
            print(f"显示组下拉菜单失败: {e}")
    
    def set_group_value(self, iid, group_value):
        """设置组值"""
        try:
            values = self.tree.item(iid, 'values')
            if values and len(values) > 3:
                idx = int(values[3])
                label_text = values[0]
                old_group = self._get_group_from_values(values)
                if old_group == group_value:
                    self.show_temp_message(f"✓ 已是 {group_value}组")
                    return
                self.push_undo_snapshot(f"修改组值 — {values[0]} {old_group}→{group_value}")
                if idx in self.df.index:
                    self.df.loc[idx, 'Group'] = group_value
                self.update_tree_item_in_place(iid, label_text=label_text, group_value=group_value)
                self.generate_report_from_tree()
                self.show_temp_message(f"✓ 组已更新为：{group_value}")
        except Exception as e:
            print(f"设置组值失败: {e}")

    def _get_group_from_values(self, values):
        """从树视图values中读取组值（去掉显示用的▼箭头）"""
        if values and len(values) > 2:
            return str(values[2]).replace(' ▼', '').strip()
        return 'B'

    def toggle_c_group(self, iid):
        """切换复选框：勾选=C组，取消=恢复原组（B或A）"""
        try:
            values = self.tree.item(iid, 'values')
            if not values or len(values) < 4:
                return
            current_group = self._get_group_from_values(values)
            idx = int(values[3])
            if current_group == 'C':
                # 取消勾选：恢复为B（或根据字体样式规则判断）
                label_text = values[0]
                new_group = self.get_group_by_text_color(label_text)
                if new_group == 'C':
                    new_group = 'B'
            else:
                new_group = 'C'
            if current_group == new_group:
                self.show_temp_message(f"✓ 已是 {new_group}组")
                return
            self.push_undo_snapshot(f"切换C组 — {values[0]} {current_group}→{new_group}")
            self.df.loc[idx, 'Group'] = new_group
            # 直接更新树中该行的显示，不重建整棵树
            label_text = values[0]
            self.update_tree_item_in_place(iid, label_text=label_text, group_value=new_group)
            self.generate_report_from_tree()
        except Exception as e:
            print(f"切换复选框失败: {e}")

    def on_drag_motion(self, event):
        """拖拽中"""
        # 移动时取消长按
        if hasattr(self, '_long_press_job') and self._long_press_job:
            self.root.after_cancel(self._long_press_job)
            self._long_press_job = None

        if event.y < 24:
            self.tree.yview_scroll(-1, "units")
        elif event.y > self.tree.winfo_height() - 24:
            self.tree.yview_scroll(1, "units")

        target = self.tree.identify_row(event.y)
        if target:
            self.show_drag_indicator(target, event.y)

    def show_drag_indicator(self, target, pointer_y):
        """显示拖拽插入位置指示线。"""
        try:
            bbox = self.tree.bbox(target)
            if not bbox:
                self.hide_drag_indicator()
                return

            x, y, width, height = bbox
            line_y = y + height if pointer_y > y + height / 2 else y

            if self.drag_indicator is None or not self.drag_indicator.winfo_exists():
                self.drag_indicator = tk.Frame(self.tree, bg="#1976D2", height=2)

            self.drag_indicator.place(x=0, y=line_y, relwidth=1.0, height=2)
            self.drag_indicator.lift()
        except Exception as e:
            print(f"显示拖拽指示线失败: {e}")

    def hide_drag_indicator(self):
        """隐藏拖拽插入位置指示线。"""
        try:
            if self.drag_indicator is not None and self.drag_indicator.winfo_exists():
                self.drag_indicator.place_forget()
        except Exception:
            pass

    def find_tree_item_by_df_index(self, df_index):
        """Find the current Treeview item for a DataFrame row index."""
        if df_index is None:
            return None
        for data_item in self.tree.get_children(""):
            values = self.tree.item(data_item, 'values')
            if values and len(values) > 3:
                try:
                    if int(values[3]) == df_index:
                        return data_item
                except (TypeError, ValueError):
                    continue
        return None

    def on_drag_release(self, event):
        """结束拖拽"""
        if not self.drag_source_item: 
            self.hide_drag_indicator()
            self.tree.configure(cursor="")
            return
            
        target = self.tree.identify_row(event.y)
        source_item = self.drag_source_item
        if not self.tree.exists(source_item):
            source_item = self.find_tree_item_by_df_index(self.drag_source_index)

        if not source_item:
            self.drag_source_item = None
            self.drag_source_index = None
            self.hide_drag_indicator()
            self.tree.configure(cursor="")
            return

        if target and target != source_item:
            try:
                src_label = self.tree.item(source_item, 'values')[0] if self.tree.item(source_item, 'values') else ''
                self.push_undo_snapshot(f"拖拽排序 — {src_label}")
                if not self.is_tree_data_item(target):
                    return
                dest_p = ""
                bbox = self.tree.bbox(target)
                insert_index = self.tree.index(target)
                if bbox and event.y > bbox[1] + bbox[3] / 2:
                    insert_index += 1

                self.tree.move(source_item, dest_p, insert_index)
                self.tree.selection_set(source_item)
                self.tree.focus(source_item)
                self.tree.see(source_item)
                
                # 更新DataFrame中的Order
                self.update_order_from_tree()
                
                self.generate_report_from_tree()
            except Exception as e:
                print(f"拖拽排序失败: {e}")
                self.show_temp_message("拖拽排序失败，请重试")
        self.drag_source_item = None
        self.drag_source_index = None
        self.hide_drag_indicator()
        self.tree.configure(cursor="")

    def on_plot_click(self, event):
        """绘图点击事件"""
        if not self.plot_initialized:
            return
        if event.inaxes != self.ax: return
        if not self.enable_lasso_mode.get():
            if event.button == 1:
                val = round(event.ydata, 1)
                if val not in self.thresholds: self.thresholds.append(val); self.thresholds.sort(); self.refresh_all()
            elif event.button == 3 and self.thresholds:
                closest = min(self.thresholds, key=lambda x: abs(x - event.ydata))
                if abs(closest - event.ydata) < (self.ax.get_ylim()[1] - self.ax.get_ylim()[0]) * 0.05:
                    self.thresholds.remove(closest);
                    self.refresh_all()

    def on_lasso_select(self, verts):
        """圈选事件"""
        if not self.plot_initialized:
            return
        if self.df.empty: return
        path = MplPath(verts)
        inside = path.contains_points(self.df[['X', 'Y']].values)
        selected_indices = self.df.index[inside].tolist()
        new_idx = set(selected_indices)
        if new_idx:
            # 圈选结果：先按 X 从大到小，再按 Y 从小到大
            ordered_indices = sorted(
                selected_indices,
                key=lambda idx: (-self.df.loc[idx, 'X'], self.df.loc[idx, 'Y'])
            )

            cat_id = len(self.category_list) + 1
            cat_name = f"圈选提取 {cat_id}"

            # 从其他分类移走这些索引，并清除旧 LassoTag
            for cat in self.category_list:
                removed = cat['indices'] & new_idx
                cat['indices'] -= new_idx
                if 'ordered_indices' in cat:
                    cat['ordered_indices'] = [idx for idx in cat['ordered_indices'] if idx not in new_idx]
                if removed:
                    self.df.loc[list(removed), 'LassoTag'] = ''

            # 确保 LassoTag 列存在
            if 'LassoTag' not in self.df.columns:
                self.df['LassoTag'] = ''

            # 给圈选条目打标记
            self.df.loc[list(new_idx), 'LassoTag'] = cat_name

            self.category_list.insert(0, {'name': cat_name, 'indices': new_idx,
                                          'ordered_indices': ordered_indices,
                                          'color': self.color_cycle[(cat_id - 1) % len(self.color_cycle)]})
            self.refresh_all()

    def update_plot_view(self):
        """更新绘图视图"""
        if not self.plot_initialized:
            return
        self.ax.clear();
        self.ax.set_title("绘图交互区")
        if not self.df.empty:
            colors = ['#1f77b4'] * len(self.df);
            sizes = [60] * len(self.df)
            for i in self.df.index:
                if i in self.marked_indices:
                    colors[i], sizes[i] = 'red', 120
                else:
                    for cat in self.category_list:
                        if i in cat['indices']: colors[i], sizes[i] = cat['color'], 100; break
            self.ax.scatter(self.df['X'], self.df['Y'], c=colors, s=sizes, zorder=5)
            for idx, row in self.df.iterrows():
                m = idx in self.marked_indices
                self.ax.annotate(row['Label'], (row['X'], row['Y']), xytext=(0, 5), textcoords="offset points",
                                 ha='center', fontsize=9, color='red' if m else 'black',
                                 weight='bold' if m else 'normal')
        for y in self.thresholds: self.ax.axhline(y=y, color='blue', linestyle='--', alpha=0.5)
        if self.enable_lasso_mode.get():
            self.lasso = LassoSelector(self.ax, onselect=self.on_lasso_select, props={'color': 'red', 'linewidth': 1.5})
        else:
            if self.lasso: self.lasso.set_active(False); self.lasso = None
        self.canvas.draw()

    def classify_and_display(self):
        """分类并显示"""
        tree_state = self.capture_tree_state()
        for i in self.tree.get_children(): self.tree.delete(i)
        if self.df.empty: return
        
        # 配置字体样式标签
        self.configure_font_style_tags()
        
        def auto_category_labels(count):
            start = 6 - count
            return [str(start + i) for i in range(count)]

        sections = []
        cat_idx = set()
        for i, cat in enumerate(self.category_list):
            # 圈选分类优先按画圈轨迹顺序显示；旧数据或普通分类按 Order / 索引显示。
            if cat.get('ordered_indices'):
                sorted_indices = [
                    idx for idx in cat['ordered_indices']
                    if idx in cat['indices'] and idx in self.df.index
                ]
                missing_indices = [
                    idx for idx in cat['indices']
                    if idx in self.df.index and idx not in sorted_indices
                ]
                if 'Order' in self.df.columns:
                    missing_indices = sorted(missing_indices, key=lambda x: self.df.loc[x, 'Order'])
                else:
                    missing_indices = sorted(missing_indices)
                sorted_indices.extend(missing_indices)
            elif 'Order' in self.df.columns:
                sorted_indices = sorted(list(cat['indices']), key=lambda x: self.df.loc[x, 'Order'] if x in self.df.index else float('inf'))
            else:
                sorted_indices = sorted(list(cat['indices']))

            rows = [idx for idx in sorted_indices if idx in self.df.index]
            if rows:
                sections.append({'key': cat['name'], 'indices': rows})
                cat_idx.update(rows)

        rem_df = self.df.drop(list(cat_idx))
        if not rem_df.empty:
            t_sorted = sorted(self.thresholds)
            line_cats = []
            if not t_sorted:
                line_cats.append(("数据区", rem_df))
            else:
                line_cats.append((f"低于 {t_sorted[0]}", rem_df[rem_df['Y'] < t_sorted[0]]))
                for i in range(len(t_sorted) - 1):
                    line_cats.append((f"{t_sorted[i]} ~ {t_sorted[i + 1]}",
                                      rem_df[(rem_df['Y'] >= t_sorted[i]) & (rem_df['Y'] < t_sorted[i + 1])]))
                line_cats.append((f"高于 {t_sorted[-1]}", rem_df[rem_df['Y'] >= t_sorted[-1]]))
            for name, sub in line_cats:
                if sub.empty: continue
                display_name = self.custom_cat_names.get(name, name)
                if 'Order' in sub.columns:
                    sub_sorted = sub.sort_values('Order')
                else:
                    sub_sorted = sub

                rows = [r_idx for r_idx, _ in sub_sorted.iterrows()]
                if rows:
                    sections.append({'key': display_name, 'indices': rows})

        row_counter = 0  # 全局行计数，用于交替背景色
        category_labels = auto_category_labels(len(sections))
        for section, category_label in zip(sections, category_labels):
            category_key = section['key']
            for idx in section['indices']:
                if idx not in self.df.index:
                    continue
                m = idx in self.marked_indices
                label_text = self.df.loc[idx, 'Label']
                group = self.df.loc[idx, 'Group'] if 'Group' in self.df.columns else self.get_group_by_text_color(label_text)

                item_tags = self.get_item_tags(label_text, group, m)
                item_tags.append('row_even' if row_counter % 2 == 0 else 'row_odd')
                row_counter += 1

                self.tree.insert("", "end",
                                 values=(label_text, "☑" if group == 'C' else "☐", group, idx, category_label, category_key),
                                 tags=tuple(item_tags))
        self.restore_tree_state(tree_state)
        self.generate_report_from_tree()

    def capture_tree_state(self):
        """记录树的展开、选择和滚动位置，用于刷新后恢复操作上下文。"""
        state = {'open_categories': {}, 'selected_indices': [], 'focus_index': None, 'yview': None}
        try:
            state['yview'] = self.tree.yview()
            for iid in self.tree.selection():
                values = self.tree.item(iid, 'values')
                if values and len(values) > 3:
                    state['selected_indices'].append(int(values[3]))

            focus_iid = self.tree.focus()
            if focus_iid:
                values = self.tree.item(focus_iid, 'values')
                if values and len(values) > 3:
                    state['focus_index'] = int(values[3])
        except Exception as e:
            print(f"记录分类树状态失败: {e}")
        return state

    def restore_tree_state(self, state):
        """恢复树的展开、选择和滚动位置。"""
        if not state:
            return
        try:
            index_to_iid = {}
            for iid in self.tree.get_children(""):
                values = self.tree.item(iid, 'values')
                if values and len(values) > 3:
                    index_to_iid[int(values[3])] = iid

            selected_iids = [
                index_to_iid[idx]
                for idx in state.get('selected_indices', [])
                if idx in index_to_iid
            ]
            if selected_iids:
                self.tree.selection_set(selected_iids)
                self.tree.see(selected_iids[0])

            focus_index = state.get('focus_index')
            if focus_index in index_to_iid:
                self.tree.focus(index_to_iid[focus_index])

            yview = state.get('yview')
            if yview:
                self.tree.yview_moveto(yview[0])
        except Exception as e:
            print(f"恢复分类树状态失败: {e}")
    
    def configure_font_style_tags(self):
        """配置字体样式标签"""
        # 配置用户自定义的字体样式规则
        for prefix, style in self.font_style_rules.items():
            if not style.get('enabled', True):
                continue
            tag_name = f"font_style_{prefix}"
            
            # 构建字体配置
            font_config = []
            font_config.append(style.get('font_family', 'Microsoft YaHei'))
            font_config.append(style.get('font_size', self.current_font_size))
            
            font_weight = style.get('font_weight', 'normal')
            if font_weight == 'bold':
                font_config.append('bold')
            
            # 配置标签 - 字体样式标签优先级更高，会覆盖标记的字体和颜色设置
            self.tree.tag_configure(tag_name, 
                                   foreground=style.get('color', '#000000'),
                                   font=tuple(font_config))
            
            # 为标记状态的字体样式项目创建特殊标签（保持字体样式，但有标记背景）
            marked_tag_name = f"marked_{tag_name}"
            self.tree.tag_configure(marked_tag_name,
                                   foreground=style.get('color', '#000000'),
                                   font=tuple(font_config),
                                   background='#FFFACD')  # 标记背景色
        
        # 配置组值颜色标签
        self.configure_group_color_tags()
    
    def configure_group_color_tags(self):
        """配置组值颜色标签"""
        # A组：红色（通过字体样式规则已处理）
        # B组：默认黑色
        # C组：深绿色（更容易识别）
        
        # C组标签
        self.tree.tag_configure('group_c', 
                               foreground='#006600',  # 深绿色
                               font=("Microsoft YaHei", self.current_font_size))
        
        # C组标记状态标签
        self.tree.tag_configure('group_c_marked',
                               foreground='#006600',  # 深绿色
                               font=("Microsoft YaHei", self.current_font_size),
                               background='#FFFACD')  # 标记背景色
        
        # B组标签（默认样式）
        self.tree.tag_configure('group_b', 
                               foreground='#000000',  # 黑色
                               font=("Microsoft YaHei", self.current_font_size))
        
        # B组标记状态标签
        self.tree.tag_configure('group_b_marked',
                               foreground='#000000',  # 黑色
                               font=("Microsoft YaHei", self.current_font_size),
                               background='#FFFACD')  # 标记背景色
    
    def get_item_tags(self, label_text, group, is_marked):
        """获取数据项的标签列表"""
        item_tags = []
        
        # 检查字体样式标签（优先级最高）
        font_style_tag = self.get_font_style_tag(label_text)
        
        if font_style_tag:
            # 有字体样式规则，使用字体样式标签
            if is_marked:
                item_tags.append(f"marked_{font_style_tag}")
            else:
                item_tags.append(font_style_tag)
        else:
            # 没有字体样式规则，使用组值颜色标签
            if group == 'C':
                if is_marked:
                    item_tags.append('group_c_marked')
                else:
                    item_tags.append('group_c')
            elif group == 'B':
                if is_marked:
                    item_tags.append('group_b_marked')
                else:
                    item_tags.append('group_b')
            else:  # A组或其他
                if is_marked:
                    item_tags.append('marked')
                # A组通常通过字体样式规则处理，如果没有规则就用默认样式
        
        return item_tags

    def is_tree_data_item(self, iid):
        """Return True for table rows that represent data items."""
        if not iid or not self.tree.exists(iid):
            return False
        values = self.tree.item(iid, 'values')
        return bool(values and len(values) > 3)

    def get_tree_item_category(self, iid):
        """Read the displayed category text from the first table column."""
        values = self.tree.item(iid, 'values')
        if values and len(values) > 4:
            return str(values[4]).strip()
        return str(self.tree.item(iid, 'text')).replace("📂 ", "").strip()

    def get_tree_item_category_key(self, iid):
        """Read the hidden stable category key used by internal logic."""
        values = self.tree.item(iid, 'values')
        if values and len(values) > 5:
            return str(values[5]).strip()
        return self.get_tree_item_category(iid)

    def set_tree_row_values(self, iid, label_text, status, group_value, idx, category=None, category_key=None):
        """Write row values while keeping the existing category cell."""
        if category is None:
            category = self.get_tree_item_category(iid) if self.tree.exists(iid) else ""
        if category_key is None:
            category_key = self.get_tree_item_category_key(iid) if self.tree.exists(iid) else category
        self.tree.item(iid, values=(label_text, status, group_value, idx, category, category_key))

    def update_tree_item_in_place(self, iid, label_text=None, group_value=None):
        """Update one data row in the tree without rebuilding or reordering siblings."""
        values = self.tree.item(iid, 'values')
        if not values or len(values) < 4:
            return False

        idx = int(values[3])
        current_label = values[0]
        current_group = self._get_group_from_values(values)
        label_text = current_label if label_text is None else label_text
        group_value = current_group if group_value is None else group_value

        new_status = "☑" if group_value == 'C' else "☐"
        self.set_tree_row_values(iid, label_text, new_status, group_value, idx)

        item_tags = self.get_item_tags(label_text, group_value, idx in self.marked_indices)
        row_tags = [tag for tag in self.tree.item(iid, 'tags') if tag in ('row_even', 'row_odd')]
        item_tags.extend(row_tags)
        self.tree.item(iid, tags=tuple(item_tags))
        return True

    def rename_category_in_place(self, iid, old_name, new_name):
        """Rename a category in the table without rebuilding or reordering rows."""
        for row_iid in self.tree.get_children(""):
            if self.get_tree_item_category(row_iid) == old_name:
                values = self.tree.item(row_iid, 'values')
                if values and len(values) > 3:
                    self.set_tree_row_values(row_iid, values[0], values[1], values[2], values[3], new_name)

        renamed = False
        for cat in self.category_list:
            if cat.get('name') == old_name:
                cat['name'] = new_name
                renamed = True
                break

        if 'LassoTag' in self.df.columns:
            self.df.loc[self.df['LassoTag'] == old_name, 'LassoTag'] = new_name

        if not renamed:
            self.custom_cat_names[old_name] = new_name

    def get_font_style_tag(self, text):
        """获取文本对应的字体样式标签"""
        for prefix, style in self.font_style_rules.items():
            if not style.get('enabled', True):
                continue
            if text.lower().startswith(prefix.lower()):
                return f"font_style_{prefix}"
        return None
    
    def get_group_by_text_color(self, text):
        """根据字体样式规则获取组值"""
        for prefix, style in self.font_style_rules.items():
            if not style.get('enabled', True):
                continue
            if text.lower().startswith(prefix.lower()):
                # 优先使用规则中明确指定的 target_group
                if 'target_group' in style and style['target_group'] in ('A', 'B', 'C', 'D'):
                    return style['target_group']
                if style.get('target_group') == 'none':
                    return 'B'
                # 兼容旧逻辑：红色自动为 A 组
                if self._is_red_color(style.get('color', '#000000')):
                    return 'A'
        return 'B'

    def _is_red_color(self, color_str):
        """判断颜色是否为红色（精确匹配）"""
        c = str(color_str or '').strip().upper()
        # 精确匹配常见红色值
        red_colors = {'#FF0000', '#FF0000FF', 'RED', '#F00', '#CC0000', '#DC143C', '#B22222', '#8B0000'}
        return c in red_colors

    def is_text_red_color(self, text):
        """判断文字是否为红色"""
        text = str(text or '').strip()
        for prefix, style in self.font_style_rules.items():
            if not style.get('enabled', True):
                continue
            if text.lower().startswith(prefix.lower()):
                if self._is_red_color(style.get('color', '#000000')):
                    return True

        color_config = self.store.get('color_config', {}) if hasattr(self, 'store') else {}
        text_colors = color_config.get('text_colors', {}) if isinstance(color_config, dict) else {}
        if self._is_red_color(text_colors.get(text)):
            return True
        return False

    def is_tree_name_cell_red(self, iid, label_text):
        """判断表格名称列当前显示是否为红色。"""
        if self.is_text_red_color(label_text):
            return True

        try:
            for tag in self.tree.item(iid, 'tags'):
                foreground = self.tree.tag_configure(tag, 'foreground')
                if self._is_red_color(foreground):
                    return True
        except Exception:
            pass

        return False

    def find_red_name_non_a_rows(self):
        """查找名称列为红色但组值不是A的数据行。"""
        issues = []
        if not hasattr(self, 'tree'):
            return issues

        for iid in self.tree.get_children(""):
            if not self.is_tree_data_item(iid):
                continue
            values = self.tree.item(iid, 'values')
            if not values or len(values) < 4:
                continue

            label_text = str(values[0]).strip()
            group_value = self._get_group_from_values(values)
            if label_text and self.is_tree_name_cell_red(iid, label_text) and group_value != 'A':
                issues.append({
                    'category': self.get_tree_item_category(iid),
                    'name': label_text,
                    'group': group_value,
                })
        return issues

    def confirm_export_with_red_name_group_issues(self):
        """导出Excel前提示红色名称未归入A组的行。"""
        issues = self.find_red_name_non_a_rows()
        if not issues:
            return True

        preview_lines = []
        for item in issues[:12]:
            preview_lines.append(f"分类：{item['category']}  名称：{item['name']}  当前组：{item['group']}")
        if len(issues) > 12:
            preview_lines.append(f"... 还有 {len(issues) - 12} 行")

        message = (
            f"发现 {len(issues)} 行名称列为红色，但组不是 A：\n\n"
            + "\n".join(preview_lines)
            + "\n\n是否仍然继续导出 Excel？"
        )
        return messagebox.askyesno("导出前检查", message, icon='warning')

    def toggle_report_separator(self):
        """切换报告分隔方式"""
        if self.report_separator == 'line':
            self.report_separator = 'blank'
            self.separator_btn.config(text="分隔: 空行")
        else:
            self.report_separator = 'line'
            self.separator_btn.config(text="分隔: ----")
        self.save_report_config()
        self.generate_report_from_tree()

    def toggle_report_format(self):
        """切换文本报告格式。"""
        if self.report_format == 'columns':
            self.report_format = 'legacy'
            self.report_format_btn.config(text="格式: 仅名称")
        else:
            self.report_format = 'columns'
            self.report_format_btn.config(text="格式: 三列")
        self.save_report_config()
        self.generate_report_from_tree()

    def generate_report_from_tree(self):
        """从表格生成报告 - 根据分类、组值和红色文字添加分隔"""
        self.report_text.delete("1.0", tk.END)
        content = ""
        separator = "----\n" if self.report_separator == 'line' else "\n"

        sections = []
        current_title = None
        current_items = []
        for iid in self.tree.get_children(""):
            vals = self.tree.item(iid, "values")
            if len(vals) < 4:
                continue
            title = self.get_tree_item_category(iid)
            if title != current_title:
                if current_items:
                    sections.append((current_title, current_items))
                current_title = title
                current_items = []
            current_items.append({
                'category': title,
                'name': vals[0],
                'group': vals[2],
                'is_red': self.is_text_red_color(vals[0])
            })
        if current_items:
            sections.append((current_title, current_items))

        for title, items_data in sections:
            if self.report_format == 'columns':
                content += f"【{title}】:\n"

            prev_group = None
            prev_is_red = None
            for i, item in enumerate(items_data):
                category = item['category']
                name = item['name']
                group = item['group']
                is_red = item['is_red']

                if i > 0:
                    if (prev_group is not None and prev_group != group) or (prev_is_red and is_red):
                        content += separator

                leading_tildes = len(name) - len(name.lstrip('~'))
                if leading_tildes > 0:
                    content += "\n" * leading_tildes
                    name = name[leading_tildes:]

                if self.report_format == 'legacy':
                    # 仅名称模式：只输出名称
                    content += f"{name}\n"
                else:
                    # 三列模式：分类\t名称\t组，预览 Excel 导出效果
                    content += f"{category}\t{name}\t{group}\n"
                prev_group = group
                prev_is_red = is_red

            content += separator

        self.report_text.insert(tk.END, content)

    def on_font_combo_change(self, event):
        """字体大小改变"""
        self.current_font_size = int(self.combo_font.get())
        self.save_font_config()  # 保存字号设置
        self.apply_font_style()
        self.refresh_all()

    def apply_font_style(self):
        """应用字体样式"""
        s = self.current_font_size
        # 更新 Treeview 样式 — 只改字体和行高，不动内部布局
        style = ttk.Style()
        style.configure("Treeview",
                        font=("Microsoft YaHei", s),
                        rowheight=max(int(s * 2.2), s + 10),
                        background="white",
                        fieldbackground="white")
        style.configure("Treeview.Heading",
                        font=("Microsoft YaHei", max(s - 1, 8)),
                        foreground="#6B7280",
                        background="#F7F9FC",
                        relief="flat",
                        borderwidth=0)
        style.map("Treeview.Heading",
                  background=[("active", "#EFF6FF")],
                  foreground=[("active", "#1A6FD4")])

        # 更新特定标签样式 - 标记状态只改变背景色，不改变字体和颜色
        self.tree.tag_configure('marked', background='#FFFACD')  # 浅黄色背景表示标记状态
        # 交替行背景色
        self.tree.tag_configure('row_even', background='#FFFFFF')
        self.tree.tag_configure('row_odd', background='#F5F5F5')
        self.report_text.configure(font=("Microsoft YaHei", s))

    def on_right_click(self, event):
        """右键点击事件 - 统一弹菜单，不直接执行操作"""
        iid = self.tree.identify_row(event.y)
        if not iid:
            return

        # 多选支持：如果点击的项目已在选中列表中，不改变选中状态
        if iid not in self.tree.selection():
            self.tree.selection_set(iid)

        context_menu = tk.Menu(self.root, tearoff=0)

        if not self.is_tree_data_item(iid):
            return

        current_group = self._get_group_from_values(self.tree.item(iid, 'values'))
        selected = [i for i in self.tree.selection() if self.is_tree_data_item(i)]
        selected_count = len(selected)
        category_name = self.get_tree_item_category(iid)

        group_menu = tk.Menu(context_menu, tearoff=0)
        for g in ['A', 'B', 'C', 'D']:
            label = f"● {g}（当前）" if g == current_group else f"   {g}"
            group_menu.add_command(
                label=label,
                command=lambda grp=g, clicked=iid: self.set_selected_group_value(clicked, grp)
            )
        if selected_count > 1:
            context_menu.add_cascade(label=f"🏷 改组选中 {selected_count} 项", menu=group_menu)
        else:
            context_menu.add_cascade(label=f"🏷 改组（当前：{current_group}）", menu=group_menu)
        context_menu.add_separator()

        category_menu = tk.Menu(context_menu, tearoff=0)
        for g in ['A', 'B', 'C', 'D']:
            category_menu.add_command(
                label=f"改为 {g}",
                command=lambda grp=g, clicked=iid: self.set_selected_group_value(clicked, grp)
            )
        context_menu.add_command(label=f"✏️ 重命名分类「{category_name}」",
                                 command=lambda row=iid: self.rename_category(row))
        context_menu.add_cascade(label=f"批量修改选中条目组值（{selected_count}项）", menu=category_menu)
        context_menu.add_command(label=f"📊 查看「{category_name}」统计",
                                 command=lambda cat=category_name: self.show_category_stats(cat))
        context_menu.add_separator()

        context_menu.add_command(label="⬆️ 上移一行", command=self.move_item_up)
        context_menu.add_command(label="⬇️ 下移一行", command=self.move_item_down)
        context_menu.add_separator()
        context_menu.add_command(label="✂️ 拆分A组（全部）", command=self.split_group_a_items)
        context_menu.add_separator()
        context_menu.add_command(label="➕ 新增", command=self.open_add_data_dialog)
        context_menu.add_command(label="❌ 删除", command=self.delete_selected_data)

        if len(selected) == 2:
            context_menu.add_separator()
            context_menu.add_command(label="🔗 合并选中两行", command=self.merge_selected_items)

        try:
            context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            context_menu.grab_release()
    
    def batch_set_category_group(self, category_iid, target_group):
        """批量将分类下所有数据项的组值设为指定组"""
        try:
            category_name = self.get_tree_item_category(category_iid) if self.tree.exists(str(category_iid)) else str(category_iid)
            children = [
                iid for iid in self.tree.get_children("")
                if self.is_tree_data_item(iid) and self.get_tree_item_category(iid) == category_name
            ]
            if not children:
                messagebox.showinfo("提示", f"分类「{category_name}」下没有数据项！")
                return
            
            # 收集要修改的数据项信息
            items_to_change = []
            for child_iid in children:
                values = self.tree.item(child_iid, 'values')
                if values and len(values) > 3:
                    idx = int(values[3])
                    if idx in self.df.index:
                        current_group = self._get_group_from_values(values)
                        item_name = values[0]
                        items_to_change.append({
                            'idx': idx,
                            'name': item_name,
                            'current_group': current_group
                        })
            
            if not items_to_change:
                messagebox.showinfo("提示", f"分类「{category_name}」下没有有效的数据项！")
                return
            
            # 统计当前组值分布
            group_stats = {}
            for item in items_to_change:
                group = item['current_group']
                group_stats[group] = group_stats.get(group, 0) + 1
            
            # 构建统计信息
            stats_text = "、".join([f"{group}组{count}个" for group, count in group_stats.items()])
            
            # 确认对话框
            total_count = len(items_to_change)
            if not messagebox.askyesno("确认批量修改", 
                                     f"分类「{category_name}」包含 {total_count} 个数据项：\n" +
                                     f"当前分布：{stats_text}\n\n" +
                                     f"确定要将所有项目的组值都改为 {target_group} 吗？"):
                return
            
            # 执行批量修改
            undo_snapshot = self._create_classifier_snapshot()
            changed_count = 0
            skipped_count = 0
            for item in items_to_change:
                idx = item['idx']
                if idx in self.df.index:
                    if item['current_group'] == target_group:
                        skipped_count += 1
                        continue
                    self.df.loc[idx, 'Group'] = target_group
                    changed_count += 1

            if changed_count:
                undo_snapshot['action_name'] = f"批量改组为{target_group}"
                self.undo_stack.append(undo_snapshot)
                if len(self.undo_stack) > self.undo_limit:
                    self.undo_stack.pop(0)
                self.update_undo_button_state()
                for child_iid in children:
                    values = self.tree.item(child_iid, 'values')
                    if values and len(values) > 3:
                        self.update_tree_item_in_place(child_iid, label_text=values[0], group_value=target_group)
                self.generate_report_from_tree()
                msg = f"✓ 「{category_name}」{changed_count} 个项目 → {target_group}组"
                if skipped_count:
                    msg += f"（跳过 {skipped_count} 个）"
                self.show_temp_message(msg)
            else:
                self.show_temp_message(f"✓ 「{category_name}」已全部是 {target_group}组")
            
        except Exception as e:
            messagebox.showerror("错误", f"批量修改组值失败：{str(e)}")

    def set_selected_group_value(self, clicked_iid, group_value):
        """将当前选中的数据项改为指定组；未多选时只改右键点击项。"""
        try:
            selected = [i for i in self.tree.selection() if self.is_tree_data_item(i)]
            target_items = selected if clicked_iid in selected else [clicked_iid]
            undo_snapshot = self._create_classifier_snapshot()
            changed_count = 0
            skipped_count = 0

            for item in target_items:
                values = self.tree.item(item, 'values')
                if not values or len(values) <= 3:
                    continue
                idx = int(values[3])
                if idx not in self.df.index:
                    continue
                old_group = self._get_group_from_values(values)
                if old_group == group_value:
                    skipped_count += 1
                    continue
                self.df.loc[idx, 'Group'] = group_value
                changed_count += 1

            if changed_count:
                undo_snapshot['action_name'] = f"改组为{group_value}"
                self.undo_stack.append(undo_snapshot)
                if len(self.undo_stack) > self.undo_limit:
                    self.undo_stack.pop(0)
                self.update_undo_button_state()
                for item in target_items:
                    if not self.tree.exists(item):
                        continue
                    values = self.tree.item(item, 'values')
                    if values and len(values) > 3:
                        self.update_tree_item_in_place(item, label_text=values[0], group_value=group_value)
                self.generate_report_from_tree()
                if len(target_items) > 1:
                    msg = f"✓ 已改组 {changed_count} 项 → {group_value}组"
                    if skipped_count:
                        msg += f"（跳过 {skipped_count} 项）"
                    self.show_temp_message(msg)
                else:
                    self.show_temp_message(f"✓ 组已更新为：{group_value}")
            else:
                self.show_temp_message(f"✓ 选中项已是 {group_value}组")

        except Exception as e:
            print(f"批量快速设置组值失败: {e}")
            messagebox.showerror("错误", f"设置组值失败：{str(e)}")

    def install_group_shortcut_bindings(self):
        """安装高优先级改组快捷键，避免 +/- 被其他控件先处理。"""
        tag = 'GroupShortcut'
        self.root.bind_class(tag, '<KeyPress>', self.handle_group_shortcut_key, add='+')
        self.root.bind_all('<KeyPress>', self.handle_group_shortcut_key, add='+')
        self.prepend_bindtag_recursive(self.root, tag)

    def prepend_bindtag_recursive(self, widget, tag):
        """把快捷键标签放到控件事件链最前面。"""
        try:
            tags = widget.bindtags()
            if tag not in tags:
                widget.bindtags((tag,) + tags)
        except Exception:
            return
        for child in widget.winfo_children():
            self.prepend_bindtag_recursive(child, tag)

    def handle_group_shortcut(self, group_value):
        """在分类表格页处理 +/- 改组快捷键。"""
        if not self.is_group_shortcut_context():
            return

        selected = [i for i in self.tree.selection() if self.is_tree_data_item(i)]

        focus_widget = self.root.focus_get()
        if focus_widget is not None:
            focus_class = focus_widget.winfo_class()
            if not selected and focus_class in ('Entry', 'TEntry', 'Text', 'TCombobox', 'Combobox', 'Spinbox', 'TSpinbox'):
                return
            if hasattr(self, 'inline_editor') and focus_widget == self.inline_editor:
                return

        return self.set_selected_group_by_shortcut(group_value)

    def handle_group_shortcut_key(self, event):
        """识别 +/- 键并分派到对应改组动作。"""
        key_char = getattr(event, 'char', '')
        key_sym = getattr(event, 'keysym', '')
        if key_char == '+' or key_sym in ('plus', 'KP_Add'):
            return self.handle_group_shortcut("D")
        if key_char == '-' or key_sym in ('minus', 'KP_Subtract'):
            return self.handle_group_shortcut("C")

    def is_group_shortcut_context(self):
        """只在分类表格页启用改组快捷键。"""
        try:
            if self.main_notebook.select() != str(self.classifier_tab):
                return False
            # 新版：判断当前步骤是否为分类表格
            current_page = getattr(self, '_current_step', '分类表格')
            return current_page == '分类表格'
        except Exception:
            return False

    def set_selected_group_by_shortcut(self, group_value):
        """通过快捷键将选中的数据项批量改组；无选择时使用当前焦点行。"""
        selected = [i for i in self.tree.selection() if self.is_tree_data_item(i)]
        clicked_iid = selected[0] if selected else self.tree.focus()

        if not clicked_iid or not self.is_tree_data_item(clicked_iid):
            self.show_temp_message("请选择要改组的数据项")
            return "break"

        self.set_selected_group_value(clicked_iid, group_value)
        return "break"

    def batch_set_category_group_to_c(self, category_iid):
        """批量将分类下所有数据项的组值设为C（兼容性方法）"""
        self.batch_set_category_group(category_iid, 'C')

    def quick_set_group_to_c(self, iid):
        """右键快速将组值设为C"""
        try:
            values = self.tree.item(iid, 'values')
            if values and len(values) > 3:
                idx = int(values[3])
                old_group = self._get_group_from_values(values)
                item_name = values[0]
                
                # 直接设置为C
                new_group = 'C'
                
                # 更新DataFrame中的组值
                if old_group != new_group:
                    self.push_undo_snapshot("改组为C")
                self.df.loc[idx, 'Group'] = new_group
                
                self.update_tree_item_in_place(iid, label_text=item_name, group_value=new_group)
                self.generate_report_from_tree()
                
                # 显示提示消息
                if old_group != new_group:
                    self.show_temp_message(f"✓ {item_name}: {old_group} → {new_group}")
                else:
                    self.show_temp_message(f"✓ {item_name}: 已是 {new_group}")
                    
        except Exception as e:
            print(f"快速设置组值为C失败: {e}")
            messagebox.showerror("错误", f"设置组值失败：{str(e)}")
    
    
    def show_group_context_menu(self, iid, event):
        """显示组值快速修改右键菜单"""
        try:
            values = self.tree.item(iid, 'values')
            if not values or len(values) < 3:
                return
            
            current_group = self._get_group_from_values(values)
            item_name = values[0]
            context_menu = tk.Menu(self.root, tearoff=0)
            
            # 添加标题
            context_menu.add_command(label=f"📝 修改组值: {item_name}", state=tk.DISABLED)
            context_menu.add_separator()
            
            # 添加快速修改选项
            for group in ['A', 'B', 'C', 'D']:
                if group == current_group:
                    # 当前组值用特殊标记，但仍可点击（用于确认）
                    label = f"● {group} (当前)"
                    context_menu.add_command(
                        label=label,
                        command=lambda g=group: self.quick_set_group_value(iid, g),
                        foreground="#666"
                    )
                else:
                    # 其他组值
                    label = f"  {group}"
                    context_menu.add_command(
                        label=label,
                        command=lambda g=group: self.quick_set_group_value(iid, g)
                    )
            
            # 添加分隔符和批量操作
            context_menu.add_separator()
            
            # 如果有多个选中项，添加批量修改选项
            selected_items = self.tree.selection()
            data_items = [item for item in selected_items if self.is_tree_data_item(item)]
            
            if len(data_items) > 1:
                context_menu.add_command(
                    label=f"📝 批量修改 ({len(data_items)} 项)",
                    command=self.batch_change_group
                )
            
            # 显示菜单
            context_menu.tk_popup(event.x_root, event.y_root)
            
        except Exception as e:
            print(f"显示组右键菜单失败: {e}")
        finally:
            try:
                context_menu.grab_release()
            except:
                pass
    
    def quick_set_group_value(self, iid, group_value):
        """快速设置单个项目的组值"""
        try:
            values = self.tree.item(iid, 'values')
            if values and len(values) > 3:
                idx = int(values[3])
                old_group = self._get_group_from_values(values)
                item_name = values[0]
                
                # 更新DataFrame中的组值
                self.df.loc[idx, 'Group'] = group_value
                
                self.update_tree_item_in_place(iid, label_text=item_name, group_value=group_value)
                self.generate_report_from_tree()
                
                # 显示提示消息
                if old_group != group_value:
                    self.show_temp_message(f"✓ {item_name}: {old_group} → {group_value}")
                else:
                    self.show_temp_message(f"✓ {item_name}: 保持 {group_value}")
                    
        except Exception as e:
            print(f"快速设置组值失败: {e}")
            messagebox.showerror("错误", f"设置组值失败：{str(e)}")
    
    def on_double_click(self, event):
        """双击事件 - 直接在单元格中编辑"""
        iid = self.tree.identify_row(event.y)
        column = self.tree.identify_column(event.x)

        if iid:
            self.tree.selection_set(iid)

            if self.is_tree_data_item(iid):
                if column == '#1':
                    self.start_inline_edit(iid, column)
                    return "break"
                if column == '#2':
                    self.start_inline_edit(iid, column)
                    return "break"
                elif column == '#3':
                    self.toggle_c_group(iid)
                    return "break"

    def on_long_press_start(self, event):
        """记录按下时间，用于长按检测"""
        self._long_press_iid = self.tree.identify_row(event.y)
        self._long_press_col = self.tree.identify_column(event.x)
        self._long_press_job = self.root.after(
            600, lambda: self._trigger_long_press(event)
        )

    def on_long_press_cancel(self, event):
        """鼠标释放或移动时取消长按"""
        if hasattr(self, '_long_press_job') and self._long_press_job:
            self.root.after_cancel(self._long_press_job)
            self._long_press_job = None

    def _trigger_long_press(self, event):
        """长按 600ms 后触发编辑"""
        self._long_press_job = None
        iid = self._long_press_iid
        column = self._long_press_col
        if not iid or not self.tree.exists(iid):
            return
        if self.is_tree_data_item(iid) and column in ('#1', '#2'):
            self.tree.selection_set(iid)
            self.start_inline_edit(iid, column)
    
    def start_inline_edit(self, iid, column):
        """开始内联编辑"""
        try:
            # 如果已经有编辑器在运行，先结束它
            if hasattr(self, 'inline_editor'):
                self.finish_inline_edit()
            
            # 获取单元格的位置和大小
            bbox = self.tree.bbox(iid, column)
            if not bbox:
                return
            
            x, y, width, height = bbox
            
            # 获取当前值
            if column == '#1':
                # 分类列
                current_value = self.get_tree_item_category(iid)
                edit_type = 'category'
                editor_widget = 'entry'
            elif column == '#2':
                # 名称列
                values = self.tree.item(iid, 'values')
                if not values:
                    return
                current_value = values[0]
                edit_type = 'item_name'
                editor_widget = 'entry'
            elif column == '#4':
                # 组列
                values = self.tree.item(iid, 'values')
                if not values or len(values) < 3:
                    return
                current_value = self._get_group_from_values(values)
                edit_type = 'item_group'
                editor_widget = 'combobox'
            else:
                return
            
            # 创建编辑器控件
            if editor_widget == 'combobox':
                # 创建下拉框编辑器
                self.inline_editor = ttk.Combobox(self.tree, values=['A', 'B', 'C', 'D'], state="readonly",
                                                font=("Microsoft YaHei", self.current_font_size))
                self.inline_editor.place(x=x, y=y, width=width, height=height)
                self.inline_editor.set(current_value)
            else:
                # 创建文本框编辑器
                self.inline_editor = tk.Entry(self.tree,
                                              font=("Microsoft YaHei", self.current_font_size),
                                              bg="#EFF6FF",
                                              highlightthickness=2,
                                              highlightbackground="#2563EB",
                                              highlightcolor="#2563EB",
                                              relief="flat", bd=0)
                self.inline_editor.place(x=x, y=y, width=width, height=height)
                # 设置初始值并全选
                self.inline_editor.insert(0, current_value)
                self.inline_editor.select_range(0, tk.END)
            
            self.inline_editor.focus_set()
            
            # 保存编辑信息
            self.edit_info = {
                'iid': iid,
                'column': column,
                'original_value': current_value,
                'edit_type': edit_type
            }

            if edit_type == 'category':
                self.tree.selection_remove(iid)
                self.tree.focus('')
            
            # 绑定事件
            self.inline_editor.bind('<Return>', self.finish_inline_edit)
            self.inline_editor.bind('<Escape>', self.cancel_inline_edit)
            self.inline_editor.bind('<FocusOut>', self.finish_inline_edit)
            
            # 绑定树视图事件，当用户点击其他地方时结束编辑
            self.tree.bind('<Button-1>', self.on_tree_click_during_edit, add='+')

            # 编辑状态视觉提示
            self.tree.config(cursor="xterm")
            self.show_temp_message("✏️ 编辑中 — Enter 确认  Esc 取消", duration=0)
        except Exception as e:
            print(f"开始内联编辑失败: {e}")
    
    def on_tree_click_during_edit(self, event):
        """编辑期间点击树视图的其他地方"""
        if hasattr(self, 'inline_editor'):
            # 检查点击位置是否在编辑器上
            editor_x = self.inline_editor.winfo_x()
            editor_y = self.inline_editor.winfo_y()
            editor_width = self.inline_editor.winfo_width()
            editor_height = self.inline_editor.winfo_height()
            
            if not (editor_x <= event.x <= editor_x + editor_width and 
                    editor_y <= event.y <= editor_y + editor_height):
                # 点击在编辑器外部，结束编辑
                self.finish_inline_edit()
    
    def finish_inline_edit(self, event=None):
        """完成内联编辑"""
        try:
            if not hasattr(self, 'inline_editor') or not hasattr(self, 'edit_info'):
                return
            
            new_value = self.inline_editor.get().strip()
            edit_info = self.edit_info
            
            # 清理编辑器
            self.cleanup_inline_editor()
            
            # 如果值没有改变，直接返回
            if new_value == edit_info['original_value'] or not new_value:
                return
            
            # 根据编辑类型更新数据
            if edit_info['edit_type'] == 'category':
                # 更新分类名称
                self.push_undo_snapshot(f"重命名分类 — {edit_info['original_value']}→{new_value}")
                iid = edit_info['iid']
                old_name = edit_info['original_value']
                self.rename_category_in_place(iid, old_name, new_value)
                self.generate_report_from_tree()
                self.show_temp_message(f"✓ 分类已重命名：{new_value}")
                
            elif edit_info['edit_type'] == 'item_name':
                # 更新数据项名称
                self.push_undo_snapshot(f"编辑名称 — {edit_info['original_value']}→{new_value}")
                values = self.tree.item(edit_info['iid'], 'values')
                if values and len(values) > 3:
                    idx = int(values[3])
                    self.df.loc[idx, 'Label'] = new_value
                    group = self.get_group_by_text_color(new_value)
                    self.df.loc[idx, 'Group'] = group
                    self.update_tree_item_in_place(edit_info['iid'], label_text=new_value, group_value=group)
                    self.generate_report_from_tree()
                    self.show_temp_message(f"✓ 已更新：{new_value}")
                    
            elif edit_info['edit_type'] == 'item_group':
                # 更新数据项组
                values = self.tree.item(edit_info['iid'], 'values')
                old_grp = self._get_group_from_values(values) if values else ''
                self.push_undo_snapshot(f"修改组值 — {values[0] if values else ''} {old_grp}→{new_value}")
                if values and len(values) > 3:
                    idx = int(values[3])
                    self.df.loc[idx, 'Group'] = new_value
                    label_text = values[0]
                    self.update_tree_item_in_place(edit_info['iid'], label_text=label_text, group_value=new_value)
                    self.generate_report_from_tree()
                    self.show_temp_message(f"✓ 组已更新：{new_value}")
            
        except Exception as e:
            print(f"完成内联编辑失败: {e}")
            self.cleanup_inline_editor()
    
    def cancel_inline_edit(self, event=None):
        """取消内联编辑"""
        self.cleanup_inline_editor()
    
    def cleanup_inline_editor(self):
        """清理内联编辑器"""
        try:
            if hasattr(self, 'inline_editor'):
                self.inline_editor.destroy()
                delattr(self, 'inline_editor')

            if hasattr(self, 'edit_info'):
                delattr(self, 'edit_info')

            # 解绑树视图的临时事件
            self.tree.unbind('<Button-1>')
            # 重新绑定原有的事件
            self.tree.bind("<ButtonPress-1>", self.on_drag_start)

            # 恢复光标和状态栏
            self.tree.config(cursor="")
            self.show_temp_message("")

        except Exception as e:
            print(f"清理内联编辑器失败: {e}")
    
    def edit_item_name_inline(self, iid):
        """内联编辑数据项名称（保留作为备用方法）"""
        # 这个方法现在被 start_inline_edit 替代，但保留以防需要
        self.start_inline_edit(iid, '#1')
    
    def rename_category_inline(self, iid):
        """内联重命名分类目录（保留作为备用方法）"""
        # 这个方法现在被 start_inline_edit 替代，但保留以防需要
        self.start_inline_edit(iid, '#0')
    
    def _set_status(self, state):
        """更新左下角状态栏：idle=蓝色就绪，running=黄色识别中，done=绿色识别成功"""
        if not hasattr(self, '_status_dot') or not hasattr(self, '_status_text'):
            return
        if state == 'running':
            self._status_dot.config(fg='#F59E0B')
            self._status_text.config(text='识别中')
        elif state == 'done':
            self._status_dot.config(fg='#22C55E')
            self._status_text.config(text='识别成功')
            self.root.after(3000, lambda: self._set_status('idle'))
        else:
            self._status_dot.config(fg='#3B82F6')
            self._status_text.config(text='就绪')

    def show_toast(self, message, duration=3000):
        """右下角弹出自动消失的 Toast 通知"""
        try:
            toast = tk.Toplevel(self.root)
            toast.overrideredirect(True)
            toast.attributes('-topmost', True)
            toast.attributes('-alpha', 0.92)

            lbl = tk.Label(toast, text=message, bg='#323232', fg='white',
                           font=('Microsoft YaHei', 12), padx=24, pady=16,
                           wraplength=420, justify=tk.LEFT)
            lbl.pack()

            toast.update_idletasks()
            tw = toast.winfo_reqwidth()
            th = toast.winfo_reqheight()
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()
            x = sw - tw - 24
            y = sh - th - 60
            toast.geometry(f'+{x}+{y}')

            # 点击也可以关闭
            lbl.bind('<Button-1>', lambda e: toast.destroy())

            # 淡出关闭
            def _fade_out(alpha=0.92):
                if not toast.winfo_exists():
                    return
                alpha -= 0.06
                if alpha <= 0:
                    toast.destroy()
                else:
                    toast.attributes('-alpha', alpha)
                    toast.after(40, lambda: _fade_out(alpha))

            toast.after(duration, _fade_out)
        except Exception:
            pass

    def show_temp_message(self, message, duration=2000):
        """显示临时消息提示"""
        try:
            # 在工具栏右侧的消息区域显示临时消息
            if hasattr(self, 'temp_message_label'):
                self.temp_message_label.destroy()
            
            self.temp_message_label = tk.Label(self.message_area, text=message, 
                                             bg="#E8F5E8", fg="#2E7D32", 
                                             font=("Microsoft YaHei", 9), 
                                             padx=10, pady=3,
                                             relief=tk.RAISED, bd=1)
            self.temp_message_label.pack(side=tk.RIGHT)
            
            # 设置定时器自动隐藏消息（duration=0 表示永久显示）
            if duration > 0:
                self.root.after(duration, lambda: self.hide_temp_message())
        except:
            pass  # 如果显示临时消息失败，不影响主要功能
    
    def hide_temp_message(self):
        """隐藏临时消息"""
        try:
            if hasattr(self, 'temp_message_label'):
                self.temp_message_label.destroy()
                delattr(self, 'temp_message_label')
        except:
            pass
    
    def toggle_mark(self, idx, refresh=True):
        """切换标记状态"""
        if idx in self.marked_indices:
            self.marked_indices.remove(idx)
        else:
            self.marked_indices.add(idx)
        if refresh:
            self.refresh_all()
    
    def split_group_a_items(self, event=None):
        """拆分分类目录树中所有组值为A且文字数大于2的单元格"""
        if self.df.empty:
            messagebox.showinfo("提示", "没有数据可以处理！")
            return
        
        # 收集所有需要拆分的项目（不依赖选择）
        items_to_split = []
        for idx, row in self.df.iterrows():
            # 检查是否为A组且文字数大于2
            if row['Group'] == 'A' and len(row['Label']) > 2:
                items_to_split.append({
                    'idx': idx,
                    'label': row['Label'],
                    'y': row['Y'],
                    'x': row['X'],
                    'order': row.get('Order', idx)
                })
        
        if not items_to_split:
            messagebox.showinfo("提示", "没有找到符合条件的项目！\n条件：组值为A且文字数大于2个字符")
            return
        
        # 确认对话框
        count = len(items_to_split)
        preview_text = "\n".join([f"• {item['label']}" for item in items_to_split[:10]])
        if count > 10:
            preview_text += f"\n... 还有 {count-10} 个项目"
        
        if not messagebox.askyesno("确认拆分", 
                                 f"找到 {count} 个符合条件的项目：\n\n{preview_text}\n\n" +
                                 "将自动拆分所有这些项目：\n" +
                                 "• 前两个字 → A组\n" +
                                 "• 其余文字 → C组\n" +
                                 "• 其他条目的组值保持不变\n\n" +
                                 "确定要继续吗？"):
            return
        
        try:
            # 按索引倒序处理，避免索引变化影响
            self.push_undo_snapshot("Split A group")
            total_count = len(items_to_split)

            # Show progress
            self.progress_label.config(text=f"Splitting items... 0/{total_count}")
            self.root.update()

            def update_split_progress(current, total, label):
                self.progress_label.config(text=f"Splitting items... {current}/{total} - {label}")
                self.root.update()

            split_count = self._split_group_a_preserve_tree_order(update_split_progress)

            # Clear progress
            self.progress_label.config(text="")

            self.refresh_all()
            
            # 显示结果
            self.show_temp_message(f"✓ 已拆分 {split_count} 个项目！")
            
            # 统计拆分后的数据
            a_count = len(self.df[self.df['Group'] == 'A'])
            c_count = len(self.df[self.df['Group'] == 'C'])
            total_items = len(self.df)

            self.show_toast(
                f"✅ 拆分完成：{split_count} 个项目\n"
                f"A组 {a_count} 个 · C组 {c_count} 个 · 共 {total_items} 个"
            )
            
        except Exception as e:
            # 清除进度显示
            self.progress_label.config(text="")
            messagebox.showerror("错误", f"拆分失败：{str(e)}")
        
        # 如果是按键触发的，防止默认行为
        if event:
            return "break"

    def toggle_mark_selected(self, event=None):
        """切换选中项的标记状态"""
        selected_items = self.tree.selection()
        if not selected_items:
            return
            
        modified = False
        for iid in selected_items:
            # Check if item exists before accessing
            if self.is_tree_data_item(iid):
                values = self.tree.item(iid, 'values')
                if values and len(values) > 3:
                    idx = int(values[3])
                    self.toggle_mark(idx, refresh=False)
                    modified = True
        
        if modified:
            self.refresh_all()
        
        # 如果是按键触发的，防止默认行为（如滚动）
        if event:
            return "break"
    
    def batch_change_group(self):
        """批量修改选中项的组值"""
        selected_items = self.tree.selection()
        if not selected_items:
            messagebox.showwarning("提示", "请先选择要修改的数据项！")
            return
        
        # 过滤出数据项（排除分类目录）
        data_items = []
        for iid in selected_items:
            if self.is_tree_data_item(iid):
                values = self.tree.item(iid, 'values')
                if values and len(values) > 3:
                    data_items.append({
                        'iid': iid,
                        'name': values[0],
                        'current_group': self._get_group_from_values(values),
                        'index': int(values[3])
                    })
        
        if not data_items:
            messagebox.showwarning("提示", "请选择数据项（不是分类目录）！")
            return
        
        # 创建批量修改对话框
        self.show_batch_group_dialog(data_items)
    
    def show_batch_group_dialog(self, data_items):
        """显示批量修改组值对话框"""
        dialog = self.create_popup_window(self.root, "批量修改组值", "batch_group_dialog", 500, 400)
        
        # 标题
        tk.Label(dialog, text="📝 批量修改组值", 
                font=("Microsoft YaHei", 14, "bold"), fg="#333").pack(pady=(20, 15))
        
        # 信息显示
        info_text = f"已选择 {len(data_items)} 个数据项"
        tk.Label(dialog, text=info_text, 
                font=("Microsoft YaHei", 10), fg="#666").pack(pady=(0, 10))
        
        # 预览框架
        preview_frame = tk.LabelFrame(dialog, text="预览选中的项目", padx=10, pady=10)
        preview_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # 创建预览列表
        preview_listbox = tk.Listbox(preview_frame, height=8, font=("Microsoft YaHei", 9))
        preview_scrollbar = ttk.Scrollbar(preview_frame, orient=tk.VERTICAL, command=preview_listbox.yview)
        preview_listbox.configure(yscrollcommand=preview_scrollbar.set)
        
        # 添加数据项到预览列表
        for item in data_items:
            preview_listbox.insert(tk.END, f"{item['name']} (当前组: {item['current_group']})")
        
        preview_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        preview_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 选择新组值
        group_frame = tk.Frame(dialog)
        group_frame.pack(fill=tk.X, padx=20, pady=10)
        
        tk.Label(group_frame, text="选择新的组值:", 
                font=("Microsoft YaHei", 11, "bold")).pack(side=tk.LEFT)
        
        group_var = tk.StringVar(value="A")
        group_combo = ttk.Combobox(group_frame, textvariable=group_var, 
                                  values=['A', 'B', 'C', 'D'], state="readonly", 
                                  font=("Microsoft YaHei", 10), width=10)
        group_combo.pack(side=tk.LEFT, padx=10)
        
        # 按钮框架
        btn_frame = tk.Frame(dialog)
        btn_frame.pack(fill=tk.X, padx=20, pady=20)
        
        def apply_batch_change():
            new_group = group_var.get()
            if not new_group:
                messagebox.showwarning("提示", "请选择新的组值！", parent=dialog)
                return
            
            # 确认对话框
            if not messagebox.askyesno("确认修改", 
                                     f"确定要将选中的 {len(data_items)} 个项目的组值都改为 '{new_group}' 吗？", 
                                     parent=dialog):
                return
            
            # 执行批量修改
            modified_count = 0
            undo_snapshot = self._create_classifier_snapshot()
            for item in data_items:
                try:
                    idx = item['index']
                    if idx in self.df.index:
                        self.df.loc[idx, 'Group'] = new_group
                        if self.tree.exists(item['iid']):
                            self.update_tree_item_in_place(item['iid'], label_text=item['name'], group_value=new_group)
                        modified_count += 1
                except Exception as e:
                    print(f"修改项目 {item['name']} 失败: {e}")
            
            # 刷新显示
            if modified_count:
                undo_snapshot['action_name'] = f"批量改组为{new_group}"
                self.undo_stack.append(undo_snapshot)
                if len(self.undo_stack) > self.undo_limit:
                    self.undo_stack.pop(0)
                self.update_undo_button_state()
            self.generate_report_from_tree()
            
            # 显示结果
            messagebox.showinfo("修改完成", 
                              f"成功修改了 {modified_count} 个项目的组值为 '{new_group}'", 
                              parent=dialog)
            dialog.destroy()
        
        # 按钮
        tk.Button(btn_frame, text="应用修改", command=apply_batch_change,
                 bg="#4CAF50", fg="white", font=("Microsoft YaHei", 10, "bold"),
                 padx=20, pady=8).pack(side=tk.RIGHT, padx=5)
        
        tk.Button(btn_frame, text="取消", command=dialog.destroy,
                 bg="#757575", fg="white", font=("Microsoft YaHei", 10),
                 padx=20, pady=8).pack(side=tk.RIGHT)
    
    def edit_item_name(self, iid):
        """编辑数据项名称"""
        try:
            values = self.tree.item(iid, 'values')
            if values:
                old_name = values[0]
                idx = int(values[3])
                
                new_name = simpledialog.askstring(
                    "编辑名称", 
                    f"请输入新的名称：\n\n原名称：{old_name}", 
                    initialvalue=old_name
                )
                
                if new_name and new_name != old_name:
                    # 更新DataFrame中的数据
                    self.push_undo_snapshot("编辑名称")
                    self.df.loc[idx, 'Label'] = new_name
                    group = self.get_group_by_text_color(new_name)
                    self.df.loc[idx, 'Group'] = group
                    self.update_tree_item_in_place(iid, label_text=new_name, group_value=group)
                    self.generate_report_from_tree()
                    messagebox.showinfo("成功", f"名称已更新：\n{old_name} → {new_name}")
        except Exception as e:
            messagebox.showerror("错误", f"编辑名称失败：{str(e)}")
    
    def rename_category(self, iid):
        """重命名分类目录"""
        try:
            old_name = self.get_tree_item_category(iid)
            
            new_name = simpledialog.askstring(
                "重命名分类", 
                f"请输入新的分类名称：\n\n原名称：{old_name}", 
                initialvalue=old_name
            )
            
            if new_name and new_name != old_name:
                # 查找并更新分类名称
                self.push_undo_snapshot("重命名分类")
                self.rename_category_in_place(iid, old_name, new_name)
                self.generate_report_from_tree()
                messagebox.showinfo("成功", f"分类名称已更新：\n{old_name} → {new_name}")
        except Exception as e:
            messagebox.showerror("错误", f"重命名分类失败：{str(e)}")
    
    def delete_single_item(self, iid):
        """删除单个数据项"""
        try:
            values = self.tree.item(iid, 'values')
            if values:
                name = values[0]
                idx = int(values[3])
                
                if messagebox.askyesno("确认删除", f"确定要删除以下数据项吗？\n\n名称：{name}"):
                    # 从DataFrame中删除
                    self.push_undo_snapshot("删除数据")
                    self.df = self.df.drop(idx).reset_index(drop=True)
                    self.reorder_dataframe()
                    self._shift_category_indices_after_delete([idx])
                    
                    self.refresh_all()
                    messagebox.showinfo("成功", f"已删除数据项：{name}")
        except Exception as e:
            messagebox.showerror("错误", f"删除失败：{str(e)}")
    
    def show_category_stats(self, iid):
        """显示分类统计信息"""
        try:
            category_name = self.get_tree_item_category(iid) if self.tree.exists(str(iid)) else str(iid)
            children = [
                row_iid for row_iid in self.tree.get_children("")
                if self.is_tree_data_item(row_iid) and self.get_tree_item_category(row_iid) == category_name
            ]
            
            if not children:
                messagebox.showinfo("统计信息", f"分类「{category_name}」\n\n暂无数据项")
                return
            
            total_count = len(children)
            marked_count = 0
            
            for child in children:
                values = self.tree.item(child, 'values')
                if values and len(values) > 3:
                    idx = int(values[3])
                    if idx in self.marked_indices:
                        marked_count += 1
            
            unmarked_count = total_count - marked_count
            
            stats_info = f"分类「{category_name}」统计信息：\n\n"
            stats_info += f"📊 总数据项：{total_count} 个\n"
            stats_info += f"✅ 已标记：{marked_count} 个\n"
            stats_info += f"⭕ 未标记：{unmarked_count} 个\n"
            
            if total_count > 0:
                marked_percent = (marked_count / total_count) * 100
                stats_info += f"📈 标记率：{marked_percent:.1f}%"
            
            messagebox.showinfo("分类统计", stats_info)
        except Exception as e:
            messagebox.showerror("错误", f"获取统计信息失败：{str(e)}")
    
    def change_category_color(self, iid):
        """更改分类颜色"""
        try:
            category_name = self.get_tree_item_category(iid) if self.tree.exists(str(iid)) else str(iid)
            idx = next((i for i, cat in enumerate(self.category_list) if cat.get('name') == category_name), -1)
            
            if idx < len(self.category_list):
                current_color = self.category_list[idx]['color']
                
                # 创建颜色选择对话框
                color_window = tk.Toplevel(self.root)
                color_window.title("选择颜色")
                color_window.geometry("400x300")
                color_window.transient(self.root)
                color_window.grab_set()
                
                # 居中显示
                color_window.update_idletasks()
                x = (color_window.winfo_screenwidth() // 2) - (400 // 2)
                y = (color_window.winfo_screenheight() // 2) - (300 // 2)
                color_window.geometry(f"400x300+{x}+{y}")
                
                tk.Label(color_window, text=f"为分类「{category_name}」选择颜色", 
                        font=("Arial", 12, "bold")).pack(pady=15)
                
                selected_color = [current_color]  # 用列表存储选择的颜色
                
                # 颜色按钮框架
                color_frame = tk.Frame(color_window)
                color_frame.pack(pady=20)
                
                colors = ['#FF0000', '#00AA00', '#FF8C00', '#9400D3', '#0000FF', '#00CED1', 
                         '#FF1493', '#32CD32', '#FFD700', '#8A2BE2', '#00BFFF', '#FF6347']
                
                for i, color in enumerate(colors):
                    row = i // 4
                    col = i % 4
                    
                    def make_color_callback(c):
                        return lambda: [selected_color.__setitem__(0, c), color_window.destroy()]
                    
                    btn = tk.Button(color_frame, bg=color, width=8, height=3,
                                   command=make_color_callback(color),
                                   relief=tk.RAISED if color != current_color else tk.SUNKEN,
                                   bd=3 if color == current_color else 1)
                    btn.grid(row=row, column=col, padx=5, pady=5)
                
                # 取消按钮
                tk.Button(color_window, text="取消", command=color_window.destroy,
                         bg="#757575", fg="white", padx=20, pady=8).pack(pady=15)
                
                # 等待用户选择
                self.root.wait_window(color_window)
                
                # 应用新颜色
                if selected_color[0] != current_color:
                    self.push_undo_snapshot("更改分类颜色")
                    self.category_list[idx]['color'] = selected_color[0]
                    self.refresh_all()
                    messagebox.showinfo("成功", f"分类「{category_name}」的颜色已更新")
            else:
                messagebox.showinfo("提示", "该分类不支持更改颜色")
        except Exception as e:
            messagebox.showerror("错误", f"更改颜色失败：{str(e)}")

    def refresh_tree_only(self):
        """只刷新分类目录树和报告，不重绘 matplotlib 图表（适合小操作）"""
        try:
            self.classify_and_display()
        except Exception as e:
            print(f"刷新树时出错: {e}")

    def refresh_all(self):
        """刷新所有（含 matplotlib 图表重绘，适合数据结构变化时调用）"""
        try:
            if self.plot_initialized:
                self.update_plot_view()
            self.classify_and_display()
        except Exception as e:
            print(f"刷新显示时出错: {e}")

    def merge_selected_items(self):
        """合并选中的两行为一行，文字用空格连接，组值取第一行"""
        selected = [i for i in self.tree.selection() if self.is_tree_data_item(i)]
        if len(selected) != 2:
            messagebox.showwarning("提示", "请选中恰好两行再合并")
            return

        # 按树中显示顺序排序（谁在上面谁是第一个）
        all_items = list(self.tree.get_children(""))
        selected.sort(key=lambda x: all_items.index(x) if x in all_items else 0)

        v1 = self.tree.item(selected[0], 'values')
        v2 = self.tree.item(selected[1], 'values')
        if not v1 or not v2 or len(v1) < 4 or len(v2) < 4:
            return

        idx1, idx2 = int(v1[3]), int(v2[3])
        label1, label2 = v1[0], v2[0]
        group1 = self._get_group_from_values(v1)

        merged_label = f"{label1} {label2}"

        self.push_undo_snapshot(f"合并两行 — {label1} + {label2}")

        # 直接更新树：第一行改文字，第二行删除
        new_status = "☑" if group1 == 'C' else "☐"
        self.set_tree_row_values(selected[0], merged_label, new_status, group1, idx1)
        item_tags = self.get_item_tags(merged_label, group1, idx1 in self.marked_indices)
        self.tree.item(selected[0], tags=tuple(item_tags))
        self.tree.delete(selected[1])
        self._shift_tree_indices_after_delete([idx2])

        # 焦点落在第一行
        self.tree.selection_set(selected[0])
        self.tree.focus(selected[0])
        self.tree.see(selected[0])

        # 更新 df
        self.df.loc[idx1, 'Label'] = merged_label
        self.df.loc[idx1, 'Group'] = group1
        self._shift_category_indices_after_delete([idx2])
        self.df = self.df.drop(idx2).reset_index(drop=True)
        self.reorder_dataframe()

        # 用 LassoTag 同步 indices
        if self.category_list and not self.df.empty and 'LassoTag' in self.df.columns:
            for cat in self.category_list:
                tag = cat['name']
                matched_set = set(self.df.index[self.df['LassoTag'] == tag].tolist())
                if cat.get('ordered_indices') is not None:
                    cat['ordered_indices'] = [i for i in cat['ordered_indices'] if i in matched_set]
                cat['indices'] = matched_set

        self.generate_report_from_tree()
        self.show_temp_message(f"✓ 已合并：{merged_label}")

    def delete_selected_data(self):
        """删除选中数据"""
        items = self.tree.selection()
        # 只处理数据项（有父节点的），记录 iid 和 df 索引
        item_pairs = [(i, int(self.tree.item(i, 'values')[3]))
                      for i in items if self.is_tree_data_item(i)]
        if not item_pairs:
            return
        indices = [idx for _, idx in item_pairs]
        if not messagebox.askyesno("确认", "删除数据？"):
            return

        deleted_labels = [self.tree.item(i, 'values')[0] for i, _ in item_pairs if self.tree.exists(i)]
        label_str = '、'.join(deleted_labels[:3]) + ('…' if len(deleted_labels) > 3 else '')
        self.push_undo_snapshot(f"删除 — {label_str}")

        # 直接从树里移除这些行，其他条目位置不变
        for iid, _ in item_pairs:
            if self.tree.exists(iid):
                self.tree.delete(iid)
        self._shift_tree_indices_after_delete(indices)

        # 删除前先用偏移计算更新 ordered_indices（此时索引还未变）
        self._shift_category_indices_after_delete(indices)

        self.df = self.df.drop(indices).reset_index(drop=True)
        self.reorder_dataframe()

        # reset_index 后再用 LassoTag 更新 indices
        if self.category_list and not self.df.empty and 'LassoTag' in self.df.columns:
            for cat in self.category_list:
                tag = cat['name']
                matched_set = set(self.df.index[self.df['LassoTag'] == tag].tolist())
                if cat.get('ordered_indices') is not None:
                    cat['ordered_indices'] = [i for i in cat['ordered_indices'] if i in matched_set]
                cat['indices'] = matched_set

        # 只重新生成报告，不重建树
        self.generate_report_from_tree()

    def reset_all(self, silent=False):
        """内部用：重置分类视图（导入数据时调用，不清空数据）"""
        # 重置分类视图
        self.thresholds = []
        self.category_list = []
        self.marked_indices = set()
        self.custom_cat_names = {}

        # 恢复组值：按字体样式规则重新推断
        if not self.df.empty:
            self.df['Group'] = self.df['Label'].apply(self.get_group_by_text_color)

        self.refresh_all()

    def clear_all_data(self):
        """将分类表格和报告重置为最近一次粘贴解析后的状态。"""
        if not self.parsed_snapshot:
            messagebox.showwarning("提示", "还没有可重置的粘贴解析数据。\n请先使用「粘贴并解析数据」。")
            return

        if not messagebox.askyesno(
            "确认重置",
            "确定要将分类表格和报告重置为最近一次粘贴解析后的状态吗？\n"
            "条目顺序、分类和文字内容都会恢复；可以使用「撤销」返回当前状态。"
        ):
            return

        self.push_undo_snapshot("重置为粘贴解析后的状态")
        self._restore_snapshot(self.parsed_snapshot)
        self.show_temp_message("✓ 已重置为粘贴解析后的状态")
    
    def add_spaces_to_tree_items(self, silent=False):
        """为分类目录树中的项目名称添加空格。
        silent=True 时静默执行，不弹窗，返回修改数量。
        """
        try:
            if self.df.empty:
                if not silent:
                    messagebox.showwarning("提示", "没有数据可以处理！")
                return 0

            all_custom_chars = []
            if self.space_presets:
                for preset in self.space_presets.values():
                    chars = preset.get('custom_chars', '')
                    if chars:
                        all_custom_chars.append(chars)

            if not all_custom_chars:
                if not silent:
                    if messagebox.askyesno("提示", "未找到空格规则预设。\n是否前往【空格设置】进行配置？"):
                        self.show_space_settings()
                return 0

            combined_chars = "|".join(all_custom_chars)
            return self.apply_space_rules([], combined_chars, silent=silent)

        except Exception as e:
            if not silent:
                messagebox.showerror("错误", f"处理失败：{str(e)}")
            return 0

    def apply_corrections(self):
        """执行拆分A组。"""
        if self.df.empty:
            messagebox.showwarning("提示", "没有数据可以处理！")
            return

        undo_snapshot = self._create_classifier_snapshot()

        split_count = self._split_group_a_silent()
        self.refresh_all()

        if split_count:
            undo_snapshot['action_name'] = f"拆分A组：{split_count} 个项目"
            self.undo_stack.append(undo_snapshot)
            if len(self.undo_stack) > self.undo_limit:
                self.undo_stack.pop(0)
            self.update_undo_button_state()
            self.show_temp_message(f"✓ 已拆分A组：{split_count} 个项目")
            self.show_toast(f"✅ 拆分完成：{split_count} 个项目")
        else:
            self.show_temp_message("✓ 没有需要拆分的A组项目")
    
    def show_space_rules_dialog(self):
        """显示空格规则选择对话框"""
        rules_window = tk.Toplevel(self.root)
        rules_window.title("添加空格规则")
        rules_window.geometry("600x700")
        rules_window.transient(self.root)
        rules_window.grab_set()
        rules_window.resizable(False, False)
        
        # 居中显示
        rules_window.update_idletasks()
        x = (rules_window.winfo_screenwidth() // 2) - (300)
        y = (rules_window.winfo_screenheight() // 2) - (350)
        rules_window.geometry(f"600x700+{x}+{y}")
        
        # 标题
        tk.Label(rules_window, text="🔤 选择空格插入规则", 
                font=("Arial", 14, "bold")).pack(pady=15)
        
        # 预设选择框架
        preset_frame = tk.LabelFrame(rules_window, text="快速选择预设", padx=10, pady=10)
        preset_frame.pack(fill=tk.X, padx=20, pady=10)
        
        preset_var = tk.StringVar()
        preset_combo = ttk.Combobox(preset_frame, textvariable=preset_var, 
                                   values=list(self.space_presets.keys()), 
                                   state="readonly", width=40)
        preset_combo.pack(side=tk.LEFT, padx=5)
        
        def load_preset():
            preset_name = preset_var.get()
            if preset_name and preset_name in self.space_presets:
                preset = self.space_presets[preset_name]
                # 只加载自定义字符
                self.custom_chars_var.set(preset.get('custom_chars', ''))
        
        tk.Button(preset_frame, text="加载预设", command=load_preset,
                 bg="#4CAF50", fg="white", padx=15, pady=5).pack(side=tk.LEFT, padx=5)
        
        tk.Button(preset_frame, text="管理预设", command=lambda: self.show_preset_manager(rules_window),
                 bg="#FF9800", fg="white", padx=15, pady=5).pack(side=tk.LEFT, padx=5)
        
        tk.Label(rules_window, text="选择要在哪些字符之间插入空格：", 
                fg="gray", font=("Arial", 10)).pack(pady=5)
        
        # 规则选择框架
        rules_frame = tk.Frame(rules_window, padx=20, pady=10)
        rules_frame.pack(fill=tk.BOTH, expand=True)
        
        # 规则变量
        self.space_rules = {}
        
        # 直接显示自定义规则，不显示预设规则选项
        # 自定义规则
        custom_frame = tk.LabelFrame(rules_frame, text="自定义规则", padx=10, pady=8)
        custom_frame.pack(fill=tk.X, pady=10)
        
        tk.Label(custom_frame, text="在以下字符之间插入空格（用逗号分隔，成对出现）：", 
                font=("Arial", 10)).pack(anchor=tk.W)
        
        self.custom_chars_var = tk.StringVar()
        custom_entry = tk.Entry(custom_frame, textvariable=self.custom_chars_var, 
                               font=("Arial", 10), width=60)
        custom_entry.pack(fill=tk.X, pady=5)
        
        # 添加更详细的说明
        examples_text = ("支持格式：\n"
                        "• 直接输入需要插入空格的两个字，用分隔符分开\n"
                        "• 例：一时|二时|三时 （会自动变为：一 时、二 时、三 时）\n"
                        "• 支持分隔符：竖线(|)、逗号(,)、空格")
        
        tk.Label(custom_frame, text=examples_text, 
                font=("Arial", 9), fg="gray", justify=tk.LEFT).pack(anchor=tk.W, pady=(5, 0))
        
        # 按钮框架
        btn_frame = tk.Frame(rules_window, pady=15)
        btn_frame.pack(fill=tk.X)
        
        def apply_rules():
            # 只检查自定义字符
            custom_chars = self.custom_chars_var.get().strip()
            
            if not custom_chars:
                messagebox.showwarning("提示", "请输入自定义字符！")
                return
            
            rules_window.destroy()
            self.apply_space_rules([], custom_chars)
        
        def preview_changes():
            # 预览功能
            custom_chars = self.custom_chars_var.get().strip()
            
            if not custom_chars:
                messagebox.showwarning("提示", "请输入自定义字符！")
                return
            
            self.preview_space_changes([], custom_chars)
        
        def save_as_preset():
            # 保存当前设置为预设
            custom_chars = self.custom_chars_var.get().strip()
            
            if not custom_chars:
                messagebox.showwarning("提示", "请输入自定义字符！")
                return
            
            preset_name = simpledialog.askstring("保存预设", "请输入预设名称：")
            if preset_name:
                description = simpledialog.askstring("预设描述", "请输入预设描述（可选）：") or ""
                
                self.space_presets[preset_name] = {
                    "rules": [],
                    "custom_chars": custom_chars,
                    "description": description
                }
                self.save_space_config()
                
                # 更新下拉框
                preset_combo['values'] = list(self.space_presets.keys())
                messagebox.showinfo("成功", f"预设「{preset_name}」已保存！")
        
        tk.Button(btn_frame, text="💾 保存预设", command=save_as_preset,
                 bg="#9C27B0", fg="white", padx=15, pady=8).pack(side=tk.LEFT, padx=5)
        
        tk.Button(btn_frame, text="预览效果", command=preview_changes,
                 bg="#2196F3", fg="white", padx=15, pady=8).pack(side=tk.LEFT, padx=5)
        
        tk.Button(btn_frame, text="应用规则", command=apply_rules,
                 bg="#4CAF50", fg="white", padx=15, pady=8).pack(side=tk.RIGHT, padx=5)
        
        tk.Button(btn_frame, text="取消", command=rules_window.destroy,
                 bg="#757575", fg="white", padx=15, pady=8).pack(side=tk.RIGHT)
    
    def apply_space_rules(self, selected_rules, custom_chars, silent=False):
        """应用空格规则到数据。silent=True 时不弹窗，返回修改数量。"""
        try:
            modified_count = 0
            total_count = len(self.df)
            
            for idx in self.df.index:
                if 'LassoTag' in self.df.columns and self.df.loc[idx, 'LassoTag'] not in ('', None) and pd.notna(self.df.loc[idx, 'LassoTag']):
                    continue
                original_text = self.df.loc[idx, 'Label']
                modified_text = self.process_text_with_space_rules(original_text, selected_rules, custom_chars)
                
                if modified_text != original_text:
                    self.df.loc[idx, 'Label'] = modified_text
                    modified_count += 1
            
            if not silent:
                # 刷新显示
                self.refresh_all()
                # 显示结果
                if modified_count > 0:
                    self.show_temp_message(f"✓ 已处理 {modified_count}/{total_count} 个项目")
                    messagebox.showinfo("处理完成", 
                        f"空格插入完成！\n\n"
                        f"总项目数：{total_count}\n"
                        f"已修改：{modified_count}\n"
                        f"未修改：{total_count - modified_count}")
                else:
                    messagebox.showinfo("处理完成", "没有项目需要修改。")

            return modified_count
                
        except Exception as e:
            if not silent:
                messagebox.showerror("错误", f"应用规则失败：{str(e)}")
            return 0
    
    def preview_space_changes(self, selected_rules, custom_chars):
        """预览空格规则的效果"""
        try:
            preview_window = tk.Toplevel(self.root)
            preview_window.title("预览效果")
            preview_window.geometry("700x500")
            preview_window.transient(self.root)
            
            # 居中显示
            preview_window.update_idletasks()
            x = (preview_window.winfo_screenwidth() // 2) - (350)
            y = (preview_window.winfo_screenheight() // 2) - (250)
            preview_window.geometry(f"700x500+{x}+{y}")
            
            tk.Label(preview_window, text="🔍 预览效果", 
                    font=("Arial", 14, "bold")).pack(pady=10)
            
            # 创建文本显示区域
            text_frame = tk.Frame(preview_window)
            text_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
            
            preview_text = scrolledtext.ScrolledText(text_frame, width=80, height=25, 
                                                   font=("Microsoft YaHei", 10))
            preview_text.pack(fill=tk.BOTH, expand=True)
            
            # 生成预览内容
            preview_content = "预览结果（显示前10个会发生变化的项目）：\n"
            preview_content += "="*60 + "\n\n"
            
            changed_count = 0
            for idx in self.df.index:
                if changed_count >= 10:
                    break
                    
                original_text = self.df.loc[idx, 'Label']
                modified_text = self.process_text_with_space_rules(original_text, selected_rules, custom_chars)
                
                if modified_text != original_text:
                    changed_count += 1
                    preview_content += f"{changed_count}. 原文：{original_text}\n"
                    preview_content += f"   修改：{modified_text}\n\n"
            
            if changed_count == 0:
                preview_content += "没有项目会发生变化。\n"
            elif changed_count == 10:
                total_changes = sum(1 for idx in self.df.index 
                                  if self.process_text_with_space_rules(self.df.loc[idx, 'Label'], selected_rules, custom_chars) != self.df.loc[idx, 'Label'])
                preview_content += f"... 还有 {total_changes - 10} 个项目会发生变化\n"
            
            preview_text.insert(tk.END, preview_content)
            preview_text.config(state=tk.DISABLED)
            
            # 关闭按钮
            tk.Button(preview_window, text="关闭", command=preview_window.destroy,
                     bg="#757575", fg="white", padx=30, pady=8).pack(pady=10)
            
        except Exception as e:
            messagebox.showerror("错误", f"预览失败：{str(e)}")
    
    def process_text_with_space_rules(self, text, selected_rules, custom_chars):
        """根据规则处理文本，插入空格（只处理自定义字符）"""
        import re
        
        result = text
        
        # 只应用自定义字符规则
        if custom_chars:
            # 新逻辑：用户输入要分割的词（如“一时”），程序将其变为“一 时”
            # 支持分隔符：| , ， 空格
            tokens = re.split(r'[|,\s，]+', custom_chars)
            tokens = [t.strip() for t in tokens if t.strip()]
            
            for token in tokens:
                # 只处理2个字的词
                if len(token) == 2:
                    char1 = token[0]
                    char2 = token[1]
                    
                    escaped_char1 = re.escape(char1)
                    escaped_char2 = re.escape(char2)
                    
                    # 创建正则表达式模式
                    pattern = fr'({escaped_char1})({escaped_char2})'
                    result = re.sub(pattern, r'\1 \2', result)
        
        # 清理多余的空格
        result = re.sub(r'\s+', ' ', result).strip()
        
        return result
    
    def show_space_settings(self):
        """显示空格规则和清理规则的合并设置窗口"""
        # 清除保存的窗口尺寸，始终用默认尺寸打开
        try:
            all_configs = self.store.get('popup_windows', {})
            if 'space_filter_settings' in all_configs:
                del all_configs['space_filter_settings']
                self.store.set('popup_windows', all_configs)
        except Exception:
            pass
        settings_window = self.create_popup_window(self.root, "空格和清理规则设置", "space_filter_settings", 860, 670, auto_fit=False)
        settings_window.configure(bg="#F8FAFC")

        colors = {
            "bg": "#F8FAFC",
            "card": "#FFFFFF",
            "border": "#DDE7F3",
            "text": "#0F172A",
            "muted": "#64748B",
            "blue": "#2563EB",
            "blue_soft": "#EAF2FF",
            "green": "#16A34A",
            "green_soft": "#DCFCE7",
            "green_border": "#B7E4C7",
            "danger": "#EF4444",
        }

        def make_button(parent, text, command, bg="#FFFFFF", fg="#334155", padx=12, pady=5, bold=False):
            btn = tk.Button(parent, text=text, command=command, bg=bg, fg=fg,
                            activebackground=bg, activeforeground=fg,
                            relief=tk.FLAT, bd=0, cursor="hand2",
                            font=("Microsoft YaHei", 9, "bold" if bold else "normal"),
                            padx=padx, pady=pady)
            return btn

        def make_card(parent):
            outer = tk.Frame(parent, bg=colors["border"], padx=1, pady=1)
            inner = tk.Frame(outer, bg=colors["card"], padx=16, pady=14)
            inner.pack(fill=tk.BOTH, expand=True)
            return outer, inner

        def draw_line_numbers(event=None):
            line_numbers.config(state=tk.NORMAL)
            line_numbers.delete("1.0", tk.END)
            line_count = int(chars_text.index("end-1c").split(".")[0])
            line_numbers.insert("1.0", "\n".join(str(i) for i in range(1, max(line_count, 1) + 1)))
            line_numbers.config(state=tk.DISABLED)

        def sync_text_scroll(*args):
            chars_text.yview(*args)
            line_numbers.yview(*args)

        def sync_from_text(*args):
            scrollbar.set(*args)
            line_numbers.yview_moveto(args[0])

        footer = tk.Frame(settings_window, bg="#FFFFFF", padx=24, pady=12,
                          highlightthickness=1, highlightbackground="#E5E7EB")
        footer.pack(fill=tk.X, side=tk.BOTTOM)

        main = tk.Frame(settings_window, bg=colors["bg"])
        main.pack(fill=tk.BOTH, expand=True)

        header = tk.Frame(main, bg=colors["bg"])
        header.pack(fill=tk.X, padx=28, pady=(18, 10))
        tk.Label(header, text="⚙", bg=colors["bg"], fg=colors["blue"],
                 font=("Microsoft YaHei", 24, "bold")).pack()
        tk.Label(header, text="空格和清理规则设置", bg=colors["bg"], fg=colors["text"],
                 font=("Microsoft YaHei", 17, "bold")).pack(pady=(0, 6))
        tk.Label(header, text="在这里统一管理加空格规则，以及需要从名称中去掉的文字或符号",
                 bg=colors["bg"], fg=colors["muted"], font=("Microsoft YaHei", 9)).pack()

        content = tk.Frame(main, bg=colors["bg"])
        content.pack(fill=tk.BOTH, expand=True, padx=26, pady=(6, 12))
        content.grid_columnconfigure(0, weight=1, uniform="rules")
        content.grid_columnconfigure(1, weight=1, uniform="rules")
        content.grid_rowconfigure(0, weight=1)

        space_outer, space_card = make_card(content)
        space_outer.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        filter_outer, filter_card = make_card(content)
        filter_outer.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        space_card.grid_columnconfigure(0, weight=1)
        space_card.grid_rowconfigure(3, weight=1)
        filter_card.grid_columnconfigure(0, weight=1)
        filter_card.grid_rowconfigure(3, weight=1)

        space_title = tk.Frame(space_card, bg=colors["card"])
        space_title.grid(row=0, column=0, sticky="ew")
        tk.Label(space_title, text="▣  空格规则", bg=colors["card"], fg=colors["blue"],
                 font=("Microsoft YaHei", self.current_font_size, "bold")).pack(side=tk.LEFT)
        help_btn = make_button(space_title, "? 帮助", lambda: messagebox.showinfo(
            "空格规则帮助",
            "每行输入一个两个字的词，保存后会在两个字之间自动加空格。\n例如：一时 会处理成 一 时",
            parent=settings_window), bg=colors["blue_soft"], fg=colors["blue"], padx=9, pady=2)
        help_btn.pack(side=tk.RIGHT)

        tk.Label(space_card, text="将以下文字按“每组两个字”加空格（每行一个，回车换行或粘贴多行）",
                 bg=colors["card"], fg=colors["muted"], font=("Microsoft YaHei", 8)).grid(row=1, column=0, sticky="w", pady=(12, 8))

        example = tk.Frame(space_card, bg=colors["blue_soft"], highlightthickness=1, highlightbackground="#BFDBFE")
        example.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        tk.Label(example, text="ⓘ  示例： 一时、二时、三时   →   一 时、二 时、三 时",
                 bg=colors["blue_soft"], fg=colors["blue"], font=("Microsoft YaHei", 9)).pack(anchor=tk.W, padx=10, pady=6)

        editor = tk.Frame(space_card, bg="#D7E3F5", highlightthickness=1, highlightbackground="#BFDBFE")
        editor.grid(row=3, column=0, sticky="nsew")
        editor.grid_columnconfigure(1, weight=1)
        editor.grid_rowconfigure(0, weight=1)
        line_numbers = tk.Text(editor, width=4, bg="#F8FAFC", fg="#64748B", relief=tk.FLAT,
                               bd=0, padx=8, pady=8, font=("Consolas", 10), state=tk.DISABLED)
        line_numbers.grid(row=0, column=0, sticky="ns")
        chars_text = tk.Text(editor, wrap=tk.NONE, bg="#FFFFFF", fg=colors["text"],
                             insertbackground=colors["blue"], relief=tk.FLAT, bd=0,
                             padx=8, pady=8, font=("Microsoft YaHei", 10),
                             yscrollcommand=sync_from_text)
        chars_text.grid(row=0, column=1, sticky="nsew")
        scrollbar = ttk.Scrollbar(editor, orient=tk.VERTICAL, command=sync_text_scroll)
        scrollbar.grid(row=0, column=2, sticky="ns")

        current_chars = []
        if self.space_presets:
            for preset in self.space_presets.values():
                chars = preset.get('custom_chars', '')
                if chars:
                    current_chars.append(chars)
        tokens = re.split(r'[|,\s，]+', "|".join(current_chars))
        tokens = [t.strip() for t in tokens if t.strip()]
        chars_text.insert("1.0", "\n".join(tokens))
        draw_line_numbers()
        chars_text.bind("<KeyRelease>", draw_line_numbers)
        chars_text.bind("<MouseWheel>", lambda e: settings_window.after_idle(draw_line_numbers))

        tk.Label(space_card, text="💡 提示：每个词为2个字，按回车换行或粘贴多行",
                 bg=colors["card"], fg=colors["blue"], font=("Microsoft YaHei", 8)).grid(row=4, column=0, sticky="w", pady=(9, 0))

        filter_title = tk.Frame(filter_card, bg=colors["card"])
        filter_title.grid(row=0, column=0, sticky="ew")
        tk.Label(filter_title, text="🗑  清理规则", bg=colors["card"], fg=colors["green"],
                 font=("Microsoft YaHei", self.current_font_size, "bold")).pack(side=tk.LEFT)
        filter_help_btn = make_button(filter_title, "? 帮助", lambda: messagebox.showinfo(
            "清理规则帮助",
            "匹配到列表里的文字或符号时，会从名称中删除。\n支持普通文字或正则表达式。",
            parent=settings_window), bg="#F0FDF4", fg="#166534", padx=9, pady=2)
        filter_help_btn.pack(side=tk.RIGHT)

        tk.Label(filter_card, text="匹配到以下内容时，将自动删除（支持普通文字或正则表达式）",
                 bg=colors["card"], fg=colors["muted"], font=("Microsoft YaHei", 8)).grid(row=1, column=0, sticky="w", pady=(12, 8))

        input_row = tk.Frame(filter_card, bg=colors["card"])
        input_row.grid(row=2, column=0, sticky="ew", pady=(0, 12))
        input_row.grid_columnconfigure(0, weight=1)
        entry_var = tk.StringVar()
        placeholder = "输入要清理的文字或符号，按 Enter 添加"
        entry = tk.Entry(input_row, textvariable=entry_var, bg="#FFFFFF", fg="#94A3B8",
                         insertbackground=colors["blue"], relief=tk.FLAT,
                         highlightthickness=1, highlightbackground=colors["border"],
                         highlightcolor="#93C5FD", font=("Microsoft YaHei", 9))
        entry.insert(0, placeholder)
        entry.grid(row=0, column=0, sticky="ew", ipady=7)

        local_filter_rules = list(self.filter_rules)
        chips_canvas = tk.Canvas(filter_card, bg=colors["card"], highlightthickness=0)
        chips_scroll = ttk.Scrollbar(filter_card, orient=tk.VERTICAL, command=chips_canvas.yview)
        chips_frame = tk.Frame(chips_canvas, bg=colors["card"])
        chips_window = chips_canvas.create_window((0, 0), window=chips_frame, anchor="nw")
        chips_canvas.configure(yscrollcommand=chips_scroll.set)
        chips_canvas.grid(row=3, column=0, sticky="nsew")
        chips_scroll.grid(row=3, column=1, sticky="ns", padx=(6, 0))

        def clear_placeholder(event=None):
            if entry_var.get() == placeholder:
                entry.delete(0, tk.END)
                entry.config(fg=colors["text"])

        def restore_placeholder(event=None):
            if not entry_var.get().strip():
                entry.config(fg="#94A3B8")
                entry_var.set(placeholder)

        entry.bind("<FocusIn>", clear_placeholder)
        entry.bind("<FocusOut>", restore_placeholder)

        def resize_chips(event=None):
            chips_canvas.itemconfigure(chips_window, width=chips_canvas.winfo_width())

        def refresh_chips():
            for child in chips_frame.winfo_children():
                child.destroy()

            header_row = tk.Frame(chips_frame, bg=colors["card"])
            header_row.grid(row=0, column=0, columnspan=4, sticky="ew", pady=(0, 10))
            tk.Label(header_row, text=f"当前规则（{len(local_filter_rules)}）", bg=colors["card"],
                     fg=colors["text"], font=("Microsoft YaHei", 9, "bold")).pack(side=tk.LEFT)
            if local_filter_rules:
                clear_btn = make_button(header_row, "🗑 清空全部", clear_filter_rules,
                                        bg=colors["card"], fg=colors["blue"], padx=4, pady=0)
                clear_btn.pack(side=tk.RIGHT)

            if not local_filter_rules:
                tk.Label(chips_frame, text="暂无清理规则", bg=colors["card"], fg="#94A3B8",
                         font=("Microsoft YaHei", 10)).grid(row=1, column=0, sticky="w", pady=10)
            else:
                max_cols = 4
                for idx, rule in enumerate(local_filter_rules):
                    chip = tk.Frame(chips_frame, bg=colors["green_soft"], padx=9, pady=5,
                                    highlightthickness=1, highlightbackground=colors["green_border"])
                    chip.grid(row=1 + idx // max_cols, column=idx % max_cols, sticky="w", padx=(0, 8), pady=(0, 8))
                    tk.Label(chip, text=rule, bg=colors["green_soft"], fg="#14532D",
                             font=("Microsoft YaHei", 9)).pack(side=tk.LEFT)
                    close = tk.Label(chip, text="  ×", bg=colors["green_soft"], fg="#5B8F72",
                                     font=("Microsoft YaHei", 10, "bold"), cursor="hand2")
                    close.pack(side=tk.LEFT)
                    close.bind("<Button-1>", lambda e, i=idx: delete_filter_rule(i))

            chips_frame.update_idletasks()
            chips_canvas.configure(scrollregion=chips_canvas.bbox("all"))

        def add_filter_rule():
            text = entry_var.get().strip()
            if not text or text == placeholder:
                return
            for item in re.split(r'[|\n]+', text):
                item = item.strip()
                if item and item not in local_filter_rules:
                    local_filter_rules.append(item)
            entry_var.set("")
            restore_placeholder()
            refresh_chips()
            entry.focus_set()

        def delete_filter_rule(index):
            if 0 <= index < len(local_filter_rules):
                local_filter_rules.pop(index)
                refresh_chips()

        def clear_filter_rules():
            local_filter_rules.clear()
            refresh_chips()

        add_btn = make_button(input_row, "+ 添加", add_filter_rule,
                              bg="#22C55E", fg="#FFFFFF", padx=14, pady=7, bold=True)
        add_btn.grid(row=0, column=1, padx=(8, 0))
        entry.bind('<Return>', lambda e: add_filter_rule())
        chips_canvas.bind("<Configure>", resize_chips)
        refresh_chips()

        usage = tk.Frame(main, bg="#EAF2FF", padx=18, pady=12,
                         highlightthickness=1, highlightbackground="#C7DBF7")
        usage.pack(fill=tk.X, padx=26, pady=(0, 12))
        tk.Label(usage, text="💡", bg="#EAF2FF", fg=colors["blue"],
                 font=("Microsoft YaHei", 16)).pack(side=tk.LEFT, padx=(0, 12))
        usage_text = tk.Frame(usage, bg="#EAF2FF")
        usage_text.pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Label(usage_text, text="使用说明", bg="#EAF2FF", fg=colors["text"],
                 font=("Microsoft YaHei", self.current_font_size, "bold")).pack(anchor=tk.W)
        tk.Label(usage_text, text="• 空格规则：将每组两个字之间自动插入空格（如“一时” → “一 时”）",
                 bg="#EAF2FF", fg="#334155", font=("Microsoft YaHei", 8)).pack(anchor=tk.W, pady=(4, 0))
        tk.Label(usage_text, text="• 清理规则：匹配到列表中的内容时，将从名称中删除",
                 bg="#EAF2FF", fg="#334155", font=("Microsoft YaHei", 8)).pack(anchor=tk.W)

        def close_window():
            settings_window.destroy()

        def save_settings():
            raw_content = chars_text.get("1.0", tk.END).strip()
            tokens = re.split(r'[|,\s，]+', raw_content)
            tokens = [t.strip() for t in tokens if t.strip()]
            formatted_content = "|".join(tokens)

            self.space_presets = {
                "Default": {
                    "custom_chars": formatted_content,
                    "rules": [],
                    "description": "默认规则"
                }
            }
            self.filter_rules = list(local_filter_rules)
            self.save_space_config()
            self.save_filter_config()
            self.show_temp_message("✓ 空格和清理规则已保存")
            settings_window.destroy()

        make_button(footer, "取消", close_window, bg="#FFFFFF", fg="#334155",
                    padx=26, pady=8).pack(side=tk.RIGHT, padx=(10, 0))
        make_button(footer, "💾 保存", save_settings, bg=colors["blue"], fg="#FFFFFF",
                    padx=28, pady=8, bold=True).pack(side=tk.RIGHT)
    
    def show_preset_manager(self, parent_window):
        """显示预设管理器（简化版）"""
        parent_window.withdraw()  # 隐藏父窗口
        
        try:
            self.show_space_settings()
        finally:
            parent_window.deiconify()  # 恢复父窗口
    
    def edit_preset_dialog(self, preset_name, refresh_callback):
        """编辑预设对话框"""
        if preset_name not in self.space_presets:
            return
        
        preset = self.space_presets[preset_name]
        
        edit_window = tk.Toplevel(self.root)
        edit_window.title(f"编辑预设 - {preset_name}")
        edit_window.geometry("500x400")
        edit_window.transient(self.root)
        edit_window.grab_set()
        
        # 居中显示
        edit_window.update_idletasks()
        x = (edit_window.winfo_screenwidth() // 2) - (250)
        y = (edit_window.winfo_screenheight() // 2) - (200)
        edit_window.geometry(f"500x400+{x}+{y}")
        
        tk.Label(edit_window, text=f"编辑预设：{preset_name}", 
                font=("Arial", 12, "bold")).pack(pady=15)
        
        # 预设名称
        name_frame = tk.Frame(edit_window, padx=20)
        name_frame.pack(fill=tk.X, pady=5)
        
        tk.Label(name_frame, text="预设名称：").pack(anchor=tk.W)
        name_var = tk.StringVar(value=preset_name)
        name_entry = tk.Entry(name_frame, textvariable=name_var, font=("Arial", 11), width=40)
        name_entry.pack(fill=tk.X, pady=5)
        
        # 描述
        desc_frame = tk.Frame(edit_window, padx=20)
        desc_frame.pack(fill=tk.X, pady=5)
        
        tk.Label(desc_frame, text="描述：").pack(anchor=tk.W)
        desc_var = tk.StringVar(value=preset.get('description', ''))
        desc_entry = tk.Entry(desc_frame, textvariable=desc_var, font=("Arial", 11), width=40)
        desc_entry.pack(fill=tk.X, pady=5)
        
        # 自定义字符
        custom_frame = tk.Frame(edit_window, padx=20)
        custom_frame.pack(fill=tk.X, pady=5)
        
        tk.Label(custom_frame, text="自定义字符（每组两个字，用|或,分隔）：").pack(anchor=tk.W)
        custom_var = tk.StringVar(value=preset.get('custom_chars', ''))
        custom_entry = tk.Entry(custom_frame, textvariable=custom_var, font=("Arial", 11), width=40)
        custom_entry.pack(fill=tk.X, pady=5)
        
        tk.Label(custom_frame, text="例：一时|二时|三时 表示在“一时”变成“一 时”", 
                font=("Arial", 9), fg="gray").pack(anchor=tk.W)
        
        # 按钮
        btn_frame = tk.Frame(edit_window, pady=15)
        btn_frame.pack(fill=tk.X)
        
        def save_changes():
            new_name = name_var.get().strip()
            if not new_name:
                messagebox.showwarning("提示", "预设名称不能为空！")
                return
            
            # 如果名称改变了，删除旧的
            if new_name != preset_name and new_name in self.space_presets:
                if not messagebox.askyesno("预设已存在", f"预设「{new_name}」已存在，是否覆盖？"):
                    return
            
            if new_name != preset_name:
                del self.space_presets[preset_name]
            
            # 保存新的预设（只保存自定义字符）
            self.space_presets[new_name] = {
                "rules": [],
                "custom_chars": custom_var.get().strip(),
                "description": desc_var.get().strip()
            }
            
            self.save_space_config()
            refresh_callback()
            edit_window.destroy()
            messagebox.showinfo("成功", f"预设「{new_name}」已保存！")
        
        tk.Button(btn_frame, text="保存", command=save_changes,
                 bg="#4CAF50", fg="white", padx=20, pady=8).pack(side=tk.RIGHT, padx=5)
        
        tk.Button(btn_frame, text="取消", command=edit_window.destroy,
                 bg="#757575", fg="white", padx=20, pady=8).pack(side=tk.RIGHT)

    def load_from_text(self):
        """从文本加载数据"""
        try:
            txt = self.root.clipboard_get()
            if txt: self.text_input.delete("1.0", tk.END); self.text_input.insert(tk.END, txt)
        except:
            pass
        raw = self.text_input.get("1.0", tk.END).strip();
        data = []
        for line in raw.split('\n'):
            parts = re.split(r'[|\t,，]+', line.strip())
            if len(parts) >= 3:
                try:
                    # 如果有第4列，作为组，否则根据文字颜色自动判断
                    if len(parts) > 3 and parts[3].strip() in ['A', 'B', 'C', 'D']:
                        group = parts[3].strip()
                    else:
                        # 根据文字颜色自动设置组值
                        group = self.get_group_by_text_color(parts[0].strip())
                    data.append([parts[0].strip(), float(parts[1]), float(parts[2]), group])
                except:
                    continue
        if data:
            self.df = pd.DataFrame(data, columns=['Label', 'Y', 'X', 'Group'])
            self.df['Order'] = range(len(self.df))
            self.df['LassoTag'] = ''
            self.reset_all(silent=True)

            # 自动执行空格规则和清理规则
            self.add_spaces_to_tree_items(silent=True)
            self._apply_filter_rules_silent()
            self.refresh_all()
            self.parsed_snapshot = self._create_classifier_snapshot()
            self.parsed_snapshot['action_name'] = "粘贴解析后的状态"

            self._step_switch('交互绘图', 0)

    def convert_text(self, mode):
        """转换文本"""
        try:
            import opencc
            txt = self.report_text.get("1.0", tk.END).strip()
            if txt:
                converter = opencc.OpenCC(mode)
                yview = self.report_text.yview()
                self.report_text.delete("1.0", tk.END)
                self.report_text.insert(tk.END, converter.convert(txt))
                self.report_text.yview_moveto(yview[0])
        except ImportError:
            messagebox.showwarning("提示", "需要安装 opencc-python-reimplemented 库才能使用繁简转换功能")

    def convert_to_simplified(self):
        """转换为简体"""
        self.convert_text('t2s')

    def convert_to_traditional(self):
        """转换为繁体"""
        self.convert_text('s2t')

    def export_txt_file(self):
        """导出文本文件"""
        raw = self.report_text.get("1.0", tk.END)
        if not raw.strip():
            messagebox.showwarning("提示", "没有内容可以导出！")
            return
            
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")],
            title="导出文本报告"
        )
        
        if path:
            try:
                # 过滤掉分类标题行
                filtered = [l for l in raw.splitlines() if not (l.strip().startswith("【") and "】" in l)]
                content = "\n".join(filtered).strip()
                
                # 写入文件
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
                
                # 保存导出记录
                self.save_export_record(path, content)
                
                # 显示成功消息
                file_size = len(content.encode('utf-8'))
                line_count = len(filtered)
                self.show_toast(f"✅ 导出成功\n📁 {os.path.basename(path)}\n{line_count} 行 · {file_size} 字节")
                
            except Exception as e:
                messagebox.showerror("导出失败", f"导出文件时出错：{str(e)}")

    def export_excel_file(self):
        """导出 Excel：从文本报告读取内容，支持三列和仅名称模式。"""
        try:
            if not self.confirm_export_with_red_name_group_issues():
                return

            path = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Excel 文件", "*.xlsx"), ("所有文件", "*.*")],
                title="导出 Excel"
            )
            if not path:
                return

            # 获取报告文本内容
            report_content = self.report_text.get("1.0", tk.END).strip()
            if not report_content:
                messagebox.showwarning("提示", "报告内容为空！")
                return

            lines = report_content.split("\n")
            separator = "----" if self.report_separator == 'line' else ""
            
            rows = []
            current_category = ""
            
            for line in lines:
                line_stripped = line.strip()
                
                # 跳过空行和分隔线
                if not line_stripped:
                    continue
                if separator and line_stripped == separator:
                    continue
                
                # 检查是否是分类标题（格式：【分类名】:）
                if line_stripped.startswith("【") and line_stripped.endswith("】:"):
                    current_category = line_stripped[1:-2]
                    continue
                
                # 根据报告格式解析行内容
                if self.report_format == 'columns':
                    # 三列模式：分类\t名称\t组
                    parts = line.split("\t")
                    if len(parts) >= 3:
                        category = parts[0].strip()
                        name = parts[1].strip()
                        group = parts[2].strip()
                        if category:
                            current_category = category
                        rows.append({"辈分": current_category, "内容": name, "组": group})
                else:
                    # 仅名称模式：只有内容
                    rows.append({"辈分": current_category, "内容": line_stripped, "组": ""})

            if not rows:
                messagebox.showwarning("提示", "没有可导出的数据！")
                return

            # 相邻辈分和组相同的合并内容
            merged_rows = []
            current_row = None
            for row in rows:
                if (current_row
                        and current_row["辈分"] == row["辈分"]
                        and current_row["组"] == row["组"]):
                    current_row["内容"] += f"\n{row['内容']}"
                else:
                    if current_row:
                        merged_rows.append(current_row)
                    current_row = row.copy()
            if current_row:
                merged_rows.append(current_row)

            df_export = pd.DataFrame(merged_rows, columns=["辈分", "内容", "组"])
            with pd.ExcelWriter(path, engine="openpyxl") as writer:
                df_export.to_excel(writer, index=False)
                ws = writer.sheets["Sheet1"]
                from openpyxl.styles import Alignment, Font
                for cell in ws[1]:
                    cell.font = Font(bold=True)
                for row_cells in ws.iter_rows():
                    for cell in row_cells:
                        cell.alignment = Alignment(wrap_text=True, vertical="top")
                widths = {"A": 12, "B": 60, "C": 10}
                for col, width in widths.items():
                    ws.column_dimensions[col].width = width

            self.save_export_record(path, report_content)
            self.show_toast(f"✅ Excel 导出成功\n📁 {os.path.basename(path)}")

        except ImportError:
            messagebox.showerror("导出失败", "缺少 Excel 写入组件，请安装 openpyxl 后重试。")
        except Exception as e:
            messagebox.showerror("导出失败", f"导出 Excel 时出错：{str(e)}")
    
    def save_export_record(self, file_path, content):
        """保存导出记录"""
        try:
            # 获取现有的导出历史记录
            export_history = self.store.get('export_history', [])
            
            # 获取历史记录限制数量（默认500）
            max_records = self.store.get('export_history_limit', 500)
            
            # 创建新的导出记录
            export_record = {
                'timestamp': datetime.now().isoformat(),
                'file_path': file_path,
                'file_name': os.path.basename(file_path),
                'content': content,
                'line_count': len([l for l in content.splitlines() if l.strip()]),
                'char_count': len(content),
                'size_bytes': len(content.encode('utf-8'))
            }
            
            # 检查是否达到记录限制
            if len(export_history) >= max_records:
                # 提示用户记录已满
                self.show_export_limit_warning(len(export_history), max_records)
                
                # 删除最旧的记录为新记录腾出空间
                export_history = export_history[:max_records-1]
            
            # 添加到历史记录开头
            export_history.insert(0, export_record)
            
            # 保存到数据存储
            self.store.set('export_history', export_history)
            
        except Exception as e:
            print(f"保存导出记录失败: {e}")
    
    def check_data_file_size(self):
        """检查数据文件大小并提供管理建议"""
        try:
            data_file_path = self.data_file
            if not data_file_path.exists():
                return
            
            file_size = data_file_path.stat().st_size
            file_size_mb = file_size / (1024 * 1024)
            
            # 获取导出历史记录信息
            export_history = self.store.get('export_history', [])
            export_count = len(export_history)
            
            # 计算导出历史记录占用的大小（估算）
            export_size = 0
            for record in export_history:
                export_size += len(record.get('content', '').encode('utf-8'))
                export_size += 500  # 估算元数据大小
            
            export_size_mb = export_size / (1024 * 1024)
            
            # 设置警告阈值
            warning_size_mb = 50  # 50MB警告
            critical_size_mb = 100  # 100MB严重警告
            
            if file_size_mb > critical_size_mb:
                self.show_file_size_warning(file_size_mb, export_count, export_size_mb, "critical")
            elif file_size_mb > warning_size_mb:
                self.show_file_size_warning(file_size_mb, export_count, export_size_mb, "warning")
            
            return {
                'total_size_mb': file_size_mb,
                'export_count': export_count,
                'export_size_mb': export_size_mb,
                'other_size_mb': file_size_mb - export_size_mb
            }
            
        except Exception as e:
            print(f"检查数据文件大小失败: {e}")
            return None
    
    def show_file_size_warning(self, file_size_mb, export_count, export_size_mb, level):
        """显示文件大小警告"""
        try:
            if level == "critical":
                title = "⚠️ 数据文件过大警告"
                icon = "warning"
                bg_color = "#ffebee"
            else:
                title = "💡 数据文件大小提醒"
                icon = "info"
                bg_color = "#fff3e0"
            
            message = (f"📊 数据文件大小统计：\n\n"
                      f"• 总文件大小：{file_size_mb:.1f} MB\n"
                      f"• 导出历史记录：{export_count} 个\n"
                      f"• 导出记录占用：{export_size_mb:.1f} MB\n"
                      f"• 其他数据占用：{file_size_mb - export_size_mb:.1f} MB\n\n")
            
            if level == "critical":
                message += ("⚠️ 数据文件已超过 100MB，可能影响软件性能！\n\n"
                           "建议操作：\n"
                           "• 清理部分导出历史记录\n"
                           "• 导出重要记录后清空历史\n"
                           "• 调整历史记录数量限制")
            else:
                message += ("💡 数据文件已超过 50MB，建议适当清理\n\n"
                           "可选操作：\n"
                           "• 查看导出历史记录管理\n"
                           "• 考虑清理旧的导出记录")
            
            result = messagebox.askyesnocancel(title, message + "\n\n是否现在打开导出历史管理？", icon=icon)
            
            if result is True:
                # 用户选择打开导出历史管理
                self.show_export_history()
            elif result is False:
                # 用户选择查看详细信息
                self.show_data_file_details()
                
        except Exception as e:
            print(f"显示文件大小警告失败: {e}")
    
    def show_data_file_details(self):
        """显示数据文件详细信息"""
        try:
            # 创建详细信息窗口
            details_window = self.create_popup_window(self.root, "数据文件详细信息", "data_file_details", 600, 500)
            
            # 标题
            tk.Label(details_window, text="📊 数据文件详细信息", 
                    font=("Microsoft YaHei", 14, "bold"), fg="#333").pack(pady=(20, 15))
            
            # 获取详细信息
            file_info = self.check_data_file_size()
            if not file_info:
                tk.Label(details_window, text="无法获取文件信息", fg="red").pack(pady=20)
                return
            
            # 信息显示区域
            info_frame = tk.LabelFrame(details_window, text="文件大小分析", padx=20, pady=15)
            info_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
            
            # 创建信息文本
            info_text = scrolledtext.ScrolledText(info_frame, height=15, width=60, 
                                                font=("Microsoft YaHei", 10), wrap=tk.WORD)
            info_text.pack(fill=tk.BOTH, expand=True)
            
            # 构建详细信息
            details = f"数据文件路径：{self.data_file}\n\n"
            details += f"📊 大小统计：\n"
            details += f"• 总文件大小：{file_info['total_size_mb']:.2f} MB\n"
            details += f"• 导出历史记录：{file_info['export_count']} 个\n"
            details += f"• 导出记录占用：{file_info['export_size_mb']:.2f} MB ({file_info['export_size_mb']/file_info['total_size_mb']*100:.1f}%)\n"
            details += f"• 其他数据占用：{file_info['other_size_mb']:.2f} MB ({file_info['other_size_mb']/file_info['total_size_mb']*100:.1f}%)\n\n"
            
            details += f"💡 优化建议：\n"
            if file_info['export_size_mb'] > 20:
                details += f"• 导出历史记录占用较大，建议清理旧记录\n"
            if file_info['total_size_mb'] > 50:
                details += f"• 文件总大小较大，可能影响启动速度\n"
            if file_info['export_count'] > 200:
                details += f"• 导出记录数量较多，建议调整数量限制\n"
            
            details += f"\n🔧 管理操作：\n"
            details += f"• 点击下方按钮可以进行相应的管理操作\n"
            details += f"• 建议定期清理不需要的历史记录\n"
            details += f"• 可以导出重要记录后清空历史"
            
            info_text.insert("1.0", details)
            info_text.config(state=tk.DISABLED)
            
            # 操作按钮
            btn_frame = tk.Frame(details_window)
            btn_frame.pack(fill=tk.X, padx=20, pady=20)
            
            tk.Button(btn_frame, text="📜 管理导出历史", command=self.show_export_history,
                     bg="#4CAF50", fg="white", font=("Microsoft YaHei", 10),
                     padx=15, pady=8).pack(side=tk.LEFT, padx=5)
            
            tk.Button(btn_frame, text="⚙️ 数量设置", command=self.show_export_limit_settings,
                     bg="#FF9800", fg="white", font=("Microsoft YaHei", 10),
                     padx=15, pady=8).pack(side=tk.LEFT, padx=5)
            
            tk.Button(btn_frame, text="🔄 刷新信息", 
                     command=lambda: [details_window.destroy(), self.show_data_file_details()],
                     bg="#2196F3", fg="white", font=("Microsoft YaHei", 10),
                     padx=15, pady=8).pack(side=tk.LEFT, padx=5)
            
            tk.Button(btn_frame, text="❌ 关闭", command=details_window.destroy,
                     bg="#757575", fg="white", font=("Microsoft YaHei", 10),
                     padx=15, pady=8).pack(side=tk.RIGHT, padx=5)
            
        except Exception as e:
            messagebox.showerror("错误", f"显示文件详细信息失败：{str(e)}")
    
    def show_export_limit_warning(self, current_count, max_count):
        """显示导出记录数量限制警告"""
        try:
            result = messagebox.askyesnocancel(
                "导出历史记录已满",
                f"📊 当前导出历史记录：{current_count}/{max_count}\n\n" +
                f"历史记录已达到上限！新的导出记录将会覆盖最旧的记录。\n\n" +
                f"🔧 您可以选择：\n" +
                f"• 是：继续导出并覆盖最旧记录\n" +
                f"• 否：调整历史记录数量限制\n" +
                f"• 取消：取消本次导出操作",
                icon='warning'
            )
            
            if result is True:
                # 用户选择继续
                return True
            elif result is False:
                # 用户选择调整限制
                self.show_export_limit_settings()
                return False
            else:
                # 用户取消
                return False
                
        except Exception as e:
            print(f"显示导出限制警告失败: {e}")
            return True
    
    def show_export_limit_settings(self):
        """显示导出历史记录数量设置"""
        try:
            # 创建设置窗口
            settings_window = self.create_popup_window(self.root, "导出历史记录设置", "export_limit_settings", 500, 400)
            
            # 标题
            tk.Label(settings_window, text="📊 导出历史记录数量设置", 
                    font=("Microsoft YaHei", 14, "bold"), fg="#333").pack(pady=(20, 15))
            
            # 当前状态
            current_count = len(self.store.get('export_history', []))
            current_limit = self.store.get('export_history_limit', 500)
            
            status_frame = tk.Frame(settings_window, bg="#f0f0f0", relief=tk.RAISED, bd=1)
            status_frame.pack(fill=tk.X, padx=20, pady=10)
            
            status_text = f"📈 当前状态：已保存 {current_count} 个记录，限制 {current_limit} 个"
            tk.Label(status_frame, text=status_text, bg="#f0f0f0", 
                    font=("Microsoft YaHei", 11)).pack(pady=10)
            
            # 设置区域
            settings_frame = tk.LabelFrame(settings_window, text="设置选项", padx=20, pady=15)
            settings_frame.pack(fill=tk.X, padx=20, pady=10)
            
            # 数量限制设置
            limit_frame = tk.Frame(settings_frame)
            limit_frame.pack(fill=tk.X, pady=5)
            
            tk.Label(limit_frame, text="历史记录数量限制：", 
                    font=("Microsoft YaHei", 10)).pack(side=tk.LEFT)
            
            limit_var = tk.StringVar(value=str(current_limit))
            limit_entry = tk.Entry(limit_frame, textvariable=limit_var, 
                                  font=("Arial", 11), width=10, justify=tk.CENTER)
            limit_entry.pack(side=tk.LEFT, padx=10)
            
            tk.Label(limit_frame, text="个", font=("Microsoft YaHei", 10)).pack(side=tk.LEFT)
            
            # 预设按钮
            preset_frame = tk.Frame(settings_frame)
            preset_frame.pack(fill=tk.X, pady=10)
            
            tk.Label(preset_frame, text="快速设置：", font=("Microsoft YaHei", 10)).pack(anchor=tk.W)
            
            preset_btn_frame = tk.Frame(preset_frame)
            preset_btn_frame.pack(fill=tk.X, pady=5)
            
            presets = [100, 200, 500, 1000, 2000]
            for preset in presets:
                tk.Button(preset_btn_frame, text=str(preset), 
                         command=lambda p=preset: limit_var.set(str(p)),
                         width=8, font=("Arial", 9)).pack(side=tk.LEFT, padx=2)
            
            # 提示信息
            hint_text = ("💡 提示：\n"
                        "• 建议设置 100-2000 个记录\n"
                        "• 记录过多可能影响软件启动速度\n"
                        "• 设置为 0 表示不限制数量（不推荐）")
            
            tk.Label(settings_frame, text=hint_text, font=("Arial", 9), 
                    fg="gray", justify=tk.LEFT).pack(anchor=tk.W, pady=10)
            
            # 按钮区域
            btn_frame = tk.Frame(settings_window)
            btn_frame.pack(fill=tk.X, padx=20, pady=20)
            
            def save_settings():
                """保存设置"""
                try:
                    new_limit = int(limit_var.get())
                    if new_limit < 0:
                        messagebox.showerror("输入错误", "记录数量不能为负数！", parent=settings_window)
                        return
                    
                    if new_limit > 10000:
                        if not messagebox.askyesno("确认设置", 
                                                 f"设置 {new_limit} 个记录可能会影响软件性能，确定要设置吗？", 
                                                 parent=settings_window):
                            return
                    
                    # 保存新的限制
                    self.store.set('export_history_limit', new_limit)
                    
                    # 如果当前记录数超过新限制，询问是否删除多余记录
                    if current_count > new_limit > 0:
                        if messagebox.askyesno("记录超限", 
                                             f"当前有 {current_count} 个记录，超过新限制 {new_limit} 个。\n" +
                                             f"是否删除最旧的 {current_count - new_limit} 个记录？", 
                                             parent=settings_window):
                            export_history = self.store.get('export_history', [])
                            export_history = export_history[:new_limit]
                            self.store.set('export_history', export_history)
                    
                    messagebox.showinfo("设置成功", 
                                      f"✅ 导出历史记录限制已设置为 {new_limit} 个", 
                                      parent=settings_window)
                    settings_window.destroy()
                    
                except ValueError:
                    messagebox.showerror("输入错误", "请输入有效的数字！", parent=settings_window)
                except Exception as e:
                    messagebox.showerror("设置失败", f"保存设置时出错：{str(e)}", parent=settings_window)
            
            def clear_history():
                """清空历史记录"""
                # 使用统一的密码验证清空功能
                self.clear_all_with_password()
                settings_window.destroy()
            
            tk.Button(btn_frame, text="保存设置", command=save_settings,
                     bg="#4CAF50", fg="white", font=("Microsoft YaHei", 10, "bold"),
                     padx=20, pady=8).pack(side=tk.RIGHT, padx=5)
            
            tk.Button(btn_frame, text="清空历史", command=clear_history,
                     bg="#f44336", fg="white", font=("Microsoft YaHei", 10),
                     padx=20, pady=8).pack(side=tk.RIGHT, padx=5)
            
            tk.Button(btn_frame, text="取消", command=settings_window.destroy,
                     bg="#757575", fg="white", font=("Microsoft YaHei", 10),
                     padx=20, pady=8).pack(side=tk.RIGHT, padx=5)
            
            # 焦点设置
            limit_entry.focus_set()
            limit_entry.select_range(0, tk.END)
            
        except Exception as e:
            messagebox.showerror("错误", f"显示设置窗口失败：{str(e)}")
    
    def verify_admin_password(self, parent_window=None, title="密码验证", message="请输入管理员密码："):
        """验证管理员密码"""
        try:
            # 创建密码输入对话框
            password_dialog = tk.Toplevel(parent_window or self.root)
            password_dialog.title(title)
            password_dialog.geometry("400x250")
            password_dialog.transient(parent_window or self.root)
            password_dialog.grab_set()
            
            # 居中显示
            password_dialog.update_idletasks()
            x = (password_dialog.winfo_screenwidth() // 2) - (400 // 2)
            y = (password_dialog.winfo_screenheight() // 2) - (250 // 2)
            password_dialog.geometry(f"400x250+{x}+{y}")
            
            # 结果变量
            result = {'verified': False}
            
            # 标题
            tk.Label(password_dialog, text="🔐 " + title, 
                    font=("Microsoft YaHei", 14, "bold"), fg="#333").pack(pady=(20, 15))
            
            # 消息
            tk.Label(password_dialog, text=message, 
                    font=("Microsoft YaHei", 11)).pack(pady=10)
            
            # 密码输入框
            password_frame = tk.Frame(password_dialog)
            password_frame.pack(pady=15)
            
            tk.Label(password_frame, text="密码：", font=("Microsoft YaHei", 10)).pack(side=tk.LEFT)
            password_var = tk.StringVar()
            password_entry = tk.Entry(password_frame, textvariable=password_var, 
                                    show="*", font=("Arial", 12), width=15)
            password_entry.pack(side=tk.LEFT, padx=10)
            
            # 错误提示
            error_label = tk.Label(password_dialog, text="", fg="red", font=("Arial", 9))
            error_label.pack(pady=5)
            
            # 按钮框架
            btn_frame = tk.Frame(password_dialog)
            btn_frame.pack(pady=20)
            
            def verify_password():
                """验证密码"""
                entered_password = password_var.get()
                if entered_password == "000":
                    result['verified'] = True
                    password_dialog.destroy()
                else:
                    error_label.config(text="❌ 密码错误，请重试")
                    password_entry.delete(0, tk.END)
                    password_entry.focus_set()
            
            def cancel():
                """取消"""
                result['verified'] = False
                password_dialog.destroy()
            
            tk.Button(btn_frame, text="确定", command=verify_password,
                     bg="#4CAF50", fg="white", font=("Microsoft YaHei", 10, "bold"),
                     padx=20, pady=8).pack(side=tk.LEFT, padx=10)
            
            tk.Button(btn_frame, text="取消", command=cancel,
                     bg="#757575", fg="white", font=("Microsoft YaHei", 10),
                     padx=20, pady=8).pack(side=tk.LEFT, padx=10)
            
            # 绑定回车键
            password_entry.bind("<Return>", lambda e: verify_password())
            password_entry.focus_set()
            
            # 等待对话框关闭
            password_dialog.wait_window()
            
            return result['verified']
            
        except Exception as e:
            print(f"密码验证失败: {e}")
            return False
    
    def export_all_history(self):
        """一键导出所有历史记录（需要密码验证）"""
        try:
            # 密码验证
            if not self.verify_admin_password(title="导出所有历史记录", 
                                            message="此操作将导出所有历史记录到一个文件\n请输入管理员密码："):
                return
            
            export_history = self.store.get('export_history', [])
            if not export_history:
                messagebox.showinfo("提示", "没有历史记录可以导出")
                return
            
            # 选择保存位置
            from datetime import datetime
            default_filename = f"导出历史记录_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            
            path = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")],
                title="导出所有历史记录",
                initialvalue=default_filename
            )
            
            if not path:
                return
            
            # 生成导出内容
            export_content = self.generate_all_history_content(export_history)
            
            # 写入文件
            with open(path, "w", encoding="utf-8") as f:
                f.write(export_content)
            
            # 显示成功消息
            file_size = len(export_content.encode('utf-8'))
            self.show_toast(f"✅ 历史记录导出成功\n📁 {os.path.basename(path)}\n共 {len(export_history)} 条记录")
            
        except Exception as e:
            messagebox.showerror("导出失败", f"导出所有历史记录时出错：{str(e)}")
    
    def generate_all_history_content(self, export_history):
        """生成所有历史记录的导出内容"""
        content = "=" * 60 + "\n"
        content += "OCR 导出历史记录汇总\n"
        content += f"导出时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        content += f"记录数量：{len(export_history)} 个\n"
        content += "=" * 60 + "\n\n"
        
        for i, record in enumerate(export_history, 1):
            timestamp = datetime.fromisoformat(record['timestamp']).strftime("%Y-%m-%d %H:%M:%S")
            
            content += f"【记录 {i}】\n"
            content += f"导出时间：{timestamp}\n"
            content += f"文件名：{record['file_name']}\n"
            content += f"文件路径：{record['file_path']}\n"
            content += f"行数：{record['line_count']} 行\n"
            content += f"字符数：{record['char_count']} 个\n"
            content += f"文件大小：{record['size_bytes']} 字节\n"
            content += "-" * 40 + "\n"
            content += "内容：\n"
            content += record['content']
            content += "\n" + "=" * 60 + "\n\n"
        
        return content
    
    def clear_all_with_password(self):
        """清空所有历史记录（需要密码验证）"""
        try:
            export_history = self.store.get('export_history', [])
            if not export_history:
                messagebox.showinfo("提示", "没有历史记录需要清空")
                return
            
            # 密码验证
            if not self.verify_admin_password(title="清空所有历史记录", 
                                            message=f"此操作将永久删除所有 {len(export_history)} 个历史记录\n请输入管理员密码："):
                return
            
            # 二次确认
            if not messagebox.askyesno("最终确认", 
                                     f"⚠️ 警告：即将永久删除所有 {len(export_history)} 个导出历史记录！\n\n" +
                                     f"此操作不可撤销，确定要继续吗？\n\n" +
                                     f"建议：删除前可以先使用'一键导出'功能备份所有记录。"):
                return
            
            # 清空历史记录
            self.store.set('export_history', [])
            
            messagebox.showinfo("清空成功", 
                              f"✅ 已成功清空所有 {len(export_history)} 个导出历史记录")
            
            # 如果当前有历史记录窗口打开，关闭它
            # 这里可以添加刷新逻辑，但为了简单起见，提示用户重新打开
            
        except Exception as e:
            messagebox.showerror("清空失败", f"清空历史记录时出错：{str(e)}")

    def show_export_history(self):
        """显示导出历史记录"""
        try:
            export_history = self.store.get('export_history', [])
            
            if not export_history:
                messagebox.showinfo("导出历史", "暂无导出历史记录")
                return
            
            # 创建历史记录窗口
            history_window = self.create_popup_window(self.root, "导出历史记录", "export_history", 800, 600)
            
            # 标题
            current_limit = self.store.get('export_history_limit', 500)
            file_info = self.check_data_file_size()
            
            if file_info:
                title_text = f"📜 导出历史记录 ({len(export_history)}/{current_limit}) - 文件大小: {file_info['total_size_mb']:.1f}MB"
            else:
                title_text = f"📜 导出历史记录 ({len(export_history)}/{current_limit})"
                
            tk.Label(history_window, text=title_text, 
                    font=("Microsoft YaHei", 14, "bold"), fg="#333").pack(pady=(20, 10))
            
            # 创建框架
            main_frame = tk.Frame(history_window)
            main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
            
            # 左侧：历史记录列表
            left_frame = tk.Frame(main_frame)
            left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            
            tk.Label(left_frame, text="历史记录列表：", font=("Microsoft YaHei", 11, "bold")).pack(anchor=tk.W)
            
            # 创建列表框
            list_frame = tk.Frame(left_frame)
            list_frame.pack(fill=tk.BOTH, expand=True, pady=5)
            
            history_listbox = tk.Listbox(list_frame, font=("Microsoft YaHei", 9))
            history_scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=history_listbox.yview)
            history_listbox.configure(yscrollcommand=history_scrollbar.set)
            
            history_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            history_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            
            # 右侧：详细信息和操作
            right_frame = tk.Frame(main_frame, width=300)
            right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(20, 0))
            right_frame.pack_propagate(False)
            
            tk.Label(right_frame, text="详细信息：", font=("Microsoft YaHei", 11, "bold")).pack(anchor=tk.W)
            
            # 详细信息显示区域
            info_text = scrolledtext.ScrolledText(right_frame, height=15, width=35, 
                                                font=("Microsoft YaHei", 9), wrap=tk.WORD)
            info_text.pack(fill=tk.BOTH, expand=True, pady=5)
            
            # 操作按钮
            btn_frame = tk.Frame(right_frame)
            btn_frame.pack(fill=tk.X, pady=10)
            
            def view_content():
                """查看内容"""
                selection = history_listbox.curselection()
                if not selection:
                    messagebox.showwarning("提示", "请先选择一个记录", parent=history_window)
                    return
                
                record = export_history[selection[0]]
                self.show_export_content(record, history_window)
            
            def delete_record():
                """删除记录"""
                selection = history_listbox.curselection()
                if not selection:
                    messagebox.showwarning("提示", "请先选择一个记录", parent=history_window)
                    return
                
                if messagebox.askyesno("确认删除", "确定要删除这个导出记录吗？", parent=history_window):
                    del export_history[selection[0]]
                    self.store.set('export_history', export_history)
                    refresh_list()
            
            def clear_all():
                """清空所有记录"""
                if messagebox.askyesno("确认清空", "确定要清空所有导出记录吗？", parent=history_window):
                    self.store.set('export_history', [])
                    history_window.destroy()
                    messagebox.showinfo("成功", "已清空所有导出记录")
            
            tk.Button(btn_frame, text="查看内容", command=view_content, 
                     bg="#4CAF50", fg="white", font=("Microsoft YaHei", 9)).pack(fill=tk.X, pady=2)
            tk.Button(btn_frame, text="删除记录", command=delete_record, 
                     bg="#f44336", fg="white", font=("Microsoft YaHei", 9)).pack(fill=tk.X, pady=2)
            tk.Button(btn_frame, text="一键导出", command=self.export_all_history, 
                     bg="#2196F3", fg="white", font=("Microsoft YaHei", 9)).pack(fill=tk.X, pady=2)
            tk.Button(btn_frame, text="数量设置", command=self.show_export_limit_settings, 
                     bg="#FF9800", fg="white", font=("Microsoft YaHei", 9)).pack(fill=tk.X, pady=2)
            tk.Button(btn_frame, text="文件信息", command=self.show_data_file_details, 
                     bg="#9C27B0", fg="white", font=("Microsoft YaHei", 9)).pack(fill=tk.X, pady=2)
            tk.Button(btn_frame, text="清空所有", command=self.clear_all_with_password, 
                     bg="#757575", fg="white", font=("Microsoft YaHei", 9)).pack(fill=tk.X, pady=2)
            
            def refresh_list():
                """刷新列表"""
                history_listbox.delete(0, tk.END)
                for i, record in enumerate(export_history):
                    timestamp = datetime.fromisoformat(record['timestamp']).strftime("%Y-%m-%d %H:%M:%S")
                    display_text = f"{timestamp} - {record['file_name']}"
                    history_listbox.insert(tk.END, display_text)
            
            def on_select(event):
                """选择记录时显示详细信息"""
                selection = history_listbox.curselection()
                if selection:
                    record = export_history[selection[0]]
                    timestamp = datetime.fromisoformat(record['timestamp']).strftime("%Y-%m-%d %H:%M:%S")
                    
                    info = f"导出时间：{timestamp}\n"
                    info += f"文件名：{record['file_name']}\n"
                    info += f"文件路径：{record['file_path']}\n"
                    info += f"行数：{record['line_count']} 行\n"
                    info += f"字符数：{record['char_count']} 个\n"
                    info += f"文件大小：{record['size_bytes']} 字节\n\n"
                    info += "内容预览：\n"
                    info += "=" * 30 + "\n"
                    
                    # 显示前10行内容作为预览
                    content_lines = record['content'].splitlines()
                    preview_lines = content_lines[:10]
                    info += "\n".join(preview_lines)
                    
                    if len(content_lines) > 10:
                        info += f"\n... 还有 {len(content_lines) - 10} 行"
                    
                    info_text.delete("1.0", tk.END)
                    info_text.insert("1.0", info)
            
            history_listbox.bind('<<ListboxSelect>>', on_select)
            
            # 初始化列表
            refresh_list()
            
        except Exception as e:
            messagebox.showerror("错误", f"显示导出历史失败：{str(e)}")
    
    def show_export_content(self, record, parent_window):
        """显示导出内容的完整窗口"""
        try:
            # 创建内容查看窗口
            content_window = tk.Toplevel(parent_window)
            content_window.title(f"查看导出内容 - {record['file_name']}")
            content_window.geometry("800x600")
            content_window.transient(parent_window)
            
            # 居中显示
            content_window.update_idletasks()
            x = (content_window.winfo_screenwidth() // 2) - (800 // 2)
            y = (content_window.winfo_screenheight() // 2) - (600 // 2)
            content_window.geometry(f"800x600+{x}+{y}")
            
            # 标题信息
            info_frame = tk.Frame(content_window, bg="#f0f0f0")
            info_frame.pack(fill=tk.X, padx=10, pady=10)
            
            timestamp = datetime.fromisoformat(record['timestamp']).strftime("%Y-%m-%d %H:%M:%S")
            info_text = f"📄 {record['file_name']} | 🕒 {timestamp} | 📊 {record['line_count']}行 {record['char_count']}字符"
            tk.Label(info_frame, text=info_text, bg="#f0f0f0", 
                    font=("Microsoft YaHei", 10)).pack(pady=5)
            
            # 工具栏
            toolbar = tk.Frame(content_window, bg="#e0e0e0")
            toolbar.pack(fill=tk.X)
            
            def copy_content():
                """复制内容到剪贴板"""
                try:
                    content_window.clipboard_clear()
                    content_window.clipboard_append(record['content'])
                    messagebox.showinfo("成功", "内容已复制到剪贴板", parent=content_window)
                except Exception as e:
                    messagebox.showerror("错误", f"复制失败：{str(e)}", parent=content_window)
            
            def save_as():
                """另存为"""
                try:
                    path = filedialog.asksaveasfilename(
                        parent=content_window,
                        defaultextension=".txt",
                        filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")],
                        title="另存为",
                        initialvalue=record['file_name']
                    )
                    
                    if path:
                        with open(path, "w", encoding="utf-8") as f:
                            f.write(record['content'])
                        messagebox.showinfo("成功", f"文件已保存到：{path}", parent=content_window)
                        
                except Exception as e:
                    messagebox.showerror("错误", f"保存失败：{str(e)}", parent=content_window)
            
            tk.Button(toolbar, text="📋 复制内容", command=copy_content, 
                     bg="#4CAF50", fg="white", padx=10, pady=5).pack(side=tk.LEFT, padx=5, pady=5)
            tk.Button(toolbar, text="💾 另存为", command=save_as, 
                     bg="#2196F3", fg="white", padx=10, pady=5).pack(side=tk.LEFT, padx=5, pady=5)
            tk.Button(toolbar, text="❌ 关闭", command=content_window.destroy, 
                     bg="#757575", fg="white", padx=10, pady=5).pack(side=tk.RIGHT, padx=5, pady=5)
            
            # 内容显示区域
            content_text = scrolledtext.ScrolledText(content_window, wrap=tk.WORD, 
                                                   font=("Microsoft YaHei", 11))
            content_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            # 插入内容
            content_text.insert("1.0", record['content'])
            content_text.config(state=tk.DISABLED)  # 设为只读
            
        except Exception as e:
            messagebox.showerror("错误", f"显示内容失败：{str(e)}", parent=parent_window)

    def _setup_drag_drop(self):
        """设置拖放功能"""
        try:
            from tkinterdnd2 import DND_FILES, TkinterDnD
            
            # 如果root不是TkinterDnD.Tk实例，则无法使用拖放
            # 这种情况下我们使用Windows原生的拖放API
            pass
        except ImportError:
            # 如果没有安装tkinterdnd2，使用Windows原生方法
            pass
        
        # 绑定拖放事件到主窗口、拖拽区和文件标签
        try:
            drop_targets = [self.root]
            if hasattr(self, 'drop_zone'):
                drop_targets.append(self.drop_zone)
            if hasattr(self, 'file_label'):
                drop_targets.append(self.file_label)

            for target in drop_targets:
                target.drop_target_register(DND_FILES)
                target.dnd_bind('<<Drop>>', self._on_drop)
                target.dnd_bind('<<DragEnter>>', self._on_drag_enter)
                target.dnd_bind('<<DragLeave>>', self._on_drag_leave)
        except:
            # 如果拖放功能不可用，忽略错误
            pass

    def _set_drop_zone_style(self, active=False):
        """更新拖拽区视觉状态。"""
        if not hasattr(self, 'drop_zone') or not hasattr(self, 'file_label'):
            return

        if active:
            bg = "#D6ECFF"
            relief = tk.SOLID
        else:
            bg = "#EAF4FF"
            relief = tk.GROOVE

        self.drop_zone.config(bg=bg, relief=relief)
        self.file_label.config(bg=bg)

    def _on_drag_enter(self, event):
        """拖入窗口时高亮拖拽区。"""
        self._set_drop_zone_style(active=True)
        return getattr(event, 'action', None)

    def _on_drag_leave(self, event):
        """拖离窗口时恢复拖拽区。"""
        self._set_drop_zone_style(active=False)
        return getattr(event, 'action', None)
    
    def _on_drop(self, event):
        """处理拖放事件"""
        try:
            # 获取拖放的文件路径
            files = event.data
            print(f"拖放原始数据: {files}")  # 调试信息
            print(f"数据类型: {type(files)}")  # 调试信息
            
            self._set_drop_zone_style(active=False)

            # Tk 原生 splitlist 能正确处理空格、中文和多文件路径。
            if isinstance(files, (tuple, list)):
                file_list = [str(f) for f in files]
            else:
                try:
                    file_list = list(self.root.tk.splitlist(str(files)))
                except tk.TclError:
                    file_list = [str(files)]
            
            print(f"解析后的文件列表: {file_list}")  # 调试信息
            
            # 清理路径
            cleaned_files = []
            for f in file_list:
                # 移除各种引号和空格
                f = f.strip().strip('{}').strip('"').strip("'").strip()
                
                # 尝试不同的路径格式
                # 1. 原始路径
                if os.path.exists(f):
                    cleaned_files.append(f)
                    print(f"✓ 找到文件: {f}")
                    continue
                
                # 2. 转换斜杠
                f_backslash = f.replace('/', '\\')
                if os.path.exists(f_backslash):
                    cleaned_files.append(f_backslash)
                    print(f"✓ 找到文件(转换后): {f_backslash}")
                    continue
                
                # 3. 转换为正斜杠
                f_slash = f.replace('\\', '/')
                if os.path.exists(f_slash):
                    cleaned_files.append(f_slash)
                    print(f"✓ 找到文件(转换后): {f_slash}")
                    continue
                
                print(f"✗ 文件不存在: {f}")
            
            if not cleaned_files:
                error_msg = f"未找到有效的文件！\n\n原始数据: {files}\n解析结果: {file_list}\n\n请确保拖放的是图片文件。"
                messagebox.showwarning("提示", error_msg)
                return
            
            # 过滤出图片文件
            image_extensions = ('.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.webp')
            image_files = [f for f in cleaned_files if f.lower().endswith(image_extensions)]
            
            if not image_files:
                messagebox.showwarning("提示", f"请拖放图片文件！\n\n找到 {len(cleaned_files)} 个文件，但都不是图片格式\n支持格式：JPG, PNG, BMP等")
                return
            
            self._handle_dropped_images(image_files)
        
        except Exception as e:
            print(f"拖放处理错误: {e}")
            import traceback
            traceback.print_exc()
            messagebox.showerror("错误", f"拖放文件失败：{str(e)}")

    def _start_high_accuracy_recognition(self, image_files):
        """选择图片后启动高精度识别。"""
        if len(image_files) == 1:
            self.select_file_internal(image_files[0])
            self.progress_label.config(text="✓ 已通过拖放选择 1 个文件，准备高精度识别")
        else:
            self.batch_select_files_internal(image_files)
            self.progress_label.config(text=f"✓ 已通过拖放选择 {len(image_files)} 个文件，准备高精度批量识别")

        self.root.after(300, self.perform_ocr)

    def _start_quick_recognition(self, image_files):
        """选择图片后启动快速识别。"""
        if len(image_files) == 1:
            self.select_file_internal(image_files[0])
            self.progress_label.config(text="✓ 已通过拖放选择 1 个文件，准备快速识别")
        else:
            self.batch_select_files_internal(image_files)
            self.progress_label.config(text=f"✓ 已通过拖放选择 {len(image_files)} 个文件，准备快速批量识别")

        self.root.after(300, self.perform_quick_ocr)

    def _start_general_recognition(self, image_files):
        """选择图片后启动通用识别。"""
        if len(image_files) == 1:
            self.select_file_internal(image_files[0])
            self.progress_label.config(text="✓ 已通过拖放选择 1 个文件，准备通用识别")
        else:
            self.batch_select_files_internal(image_files)
            self.progress_label.config(text=f"✓ 已通过拖放选择 {len(image_files)} 个文件，准备通用批量识别")

        self.root.after(300, self.perform_general_ocr)

    def _get_image_drop_info(self, image_file):
        """读取拖入图片信息，并判断各识别模式是否可用。"""
        info = {
            'path': image_file,
            'name': os.path.basename(image_file),
            'width': 0,
            'height': 0,
            'size_text': '',
            'accurate': False,
            'basic': False,
            'general': False,
            'error': None
        }

        try:
            with Image.open(image_file) as img:
                info['width'], info['height'] = img.size

            file_size = os.path.getsize(image_file)
            if file_size < 1024 * 1024:
                info['size_text'] = f"{file_size / 1024:.1f}KB"
            else:
                info['size_text'] = f"{file_size / (1024 * 1024):.1f}MB"

            width = info['width']
            height = info['height']
            info['accurate'] = (
                self.size_limit_unlocked or (
                    self.size_limits["accurate_min_width"] <= width <= self.size_limits["accurate_max_width"] and
                    self.size_limits["accurate_min_height"] <= height <= self.size_limits["accurate_max_height"]
                )
            )
            info['basic'] = (
                self.size_limits["basic_min_width"] <= width <= self.size_limits["basic_max_width"] and
                self.size_limits["basic_min_height"] <= height <= self.size_limits["basic_max_height"]
            )
            info['general'] = (
                self.size_limits["general_min_width"] <= width <= self.size_limits["general_max_width"] and
                self.size_limits["general_min_height"] <= height <= self.size_limits["general_max_height"]
            )
        except Exception as e:
            info['error'] = str(e)

        return info

    def _get_drop_recommendation(self, image_infos):
        """根据拖入图片数量和尺寸给出推荐操作。"""
        count = len(image_infos)
        valid_infos = [info for info in image_infos if not info.get('error')]

        if not valid_infos:
            return "裁剪识别", "crop", "无法读取图片尺寸，建议先进入裁剪窗口确认图片。"

        if count == 2:
            return "推荐：拼接图片", "merge", "检测到 2 张图片，适合先预览拼接方向再识别。"

        all_accurate = all(info['accurate'] for info in valid_infos)
        all_general = all(info['general'] for info in valid_infos)
        all_basic = all(info['basic'] for info in valid_infos)

        if all_accurate:
            return "推荐：高精度识别", "accurate", "所有图片都符合高精度识别尺寸要求。"
        if all_general:
            return "推荐：通用识别", "general", "图片尺寸更适合通用识别。"
        if all_basic:
            return "推荐：快速识别", "basic", "图片尺寸更适合快速识别。"

        return "推荐：裁剪识别", "crop", "部分图片尺寸不符合识别范围，建议先裁剪或调整。"

    def _handle_dropped_images(self, image_files):
        """处理拖入的图片：单张直接识别，两张询问是否拼接，多张直接批量识别"""
        self._increment_book_page_for_import()

        count = len(image_files)

        if count == 1:
            # 单张：直接按当前选中模式识别
            self.select_file_internal(image_files[0])
            mode = getattr(self, '_selected_ocr_mode', tk.StringVar()).get()
            self.root.after(200, lambda: self._start_ocr_and_parse())

        elif count == 2:
            # 两张：询问是否拼接
            win = tk.Toplevel(self.root)
            win.title('两张图片')
            win.transient(self.root)
            win.grab_set()
            win.resizable(False, False)
            win.configure(bg='white')

            sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
            w, h = 360, 160
            win.geometry(f'{w}x{h}+{(sw-w)//2}+{(sh-h)//2}')

            tk.Label(win, text='检测到 2 张图片', bg='white', fg='#111827',
                     font=('Microsoft YaHei', 12, 'bold')).pack(pady=(20, 6))
            tk.Label(win, text='是否先拼接再识别？', bg='white', fg='#6B7280',
                     font=('Microsoft YaHei', 9)).pack(pady=(0, 16))

            btn_row = tk.Frame(win, bg='white')
            btn_row.pack()

            def do_merge():
                win.destroy()
                self._merge_images_from_drag(image_files)

            def do_batch():
                win.destroy()
                self.batch_select_files_internal(image_files)
                self.root.after(200, lambda: self._start_ocr_and_parse())

            tk.Button(btn_row, text='拼接识别', command=do_merge,
                      bg='#1A6FD4', fg='white', relief='flat',
                      font=('Microsoft YaHei', 10, 'bold'),
                      padx=20, pady=7, cursor='hand2').pack(side=tk.LEFT, padx=(0, 8))
            tk.Button(btn_row, text='分别识别', command=do_batch,
                      bg='#F3F4F6', fg='#374151', relief='flat',
                      font=('Microsoft YaHei', 10),
                      padx=20, pady=7, cursor='hand2').pack(side=tk.LEFT)

            win.bind('<Return>', lambda e: do_merge())
            win.bind('<Escape>', lambda e: win.destroy())

        else:
            # 多张：直接批量识别
            self.batch_select_files_internal(image_files)
            self.root.after(200, lambda: self._start_ocr_and_parse())

    def _show_drop_preview_options(self, image_files):
        """显示拖入图片预览和推荐操作。"""
        from PIL import ImageTk

        image_infos = [self._get_image_drop_info(path) for path in image_files]
        recommend_text, recommend_action, recommend_reason = self._get_drop_recommendation(image_infos)
        count = len(image_files)

        win_h = 560 if count <= 2 else 620
        option_window = self.create_popup_window(self.root, "拖入图片预览", "drop_preview_options", 680, win_h)
        option_window.preview_photos = []

        tk.Label(option_window, text=f"检测到 {count} 张图片",
                 font=("Microsoft YaHei", 14, "bold")).pack(pady=(16, 6))
        tk.Label(option_window, text=recommend_reason,
                 fg="#555555", font=("Microsoft YaHei", 10), wraplength=610).pack(pady=(0, 10))

        preview_frame = tk.Frame(option_window, bg="#F7FAFC")
        preview_frame.pack(fill=tk.X, padx=20, pady=4)

        preview_count = min(count, 6)
        for i, info in enumerate(image_infos[:preview_count]):
            card = tk.Frame(preview_frame, bg="white", relief=tk.GROOVE, bd=1)
            card.grid(row=i // 3, column=i % 3, padx=8, pady=8, sticky="nsew")
            preview_frame.grid_columnconfigure(i % 3, weight=1)

            try:
                with Image.open(info['path']) as img:
                    img.thumbnail((150, 95), Image.Resampling.LANCZOS)
                    photo = ImageTk.PhotoImage(img.copy())
                option_window.preview_photos.append(photo)
                tk.Label(card, image=photo, bg="white").pack(padx=6, pady=(6, 4))
            except Exception:
                tk.Label(card, text="无法预览", bg="white", fg="#B00020",
                         width=18, height=5).pack(padx=6, pady=(6, 4))

            detail = info['name']
            if info.get('error'):
                detail += "\n读取失败"
            else:
                modes = []
                if info['accurate']:
                    modes.append("高精度")
                if info['basic']:
                    modes.append("快速")
                if info['general']:
                    modes.append("通用")
                modes_text = "、".join(modes) if modes else "无可用模式"
                detail += f"\n{info['width']}x{info['height']}  {info['size_text']}\n可用：{modes_text}"

            tk.Label(card, text=detail, bg="white", fg="#1F2937",
                     justify=tk.LEFT, wraplength=175, font=("Microsoft YaHei", 8)).pack(
                         padx=6, pady=(0, 8), anchor=tk.W)

        if count > preview_count:
            tk.Label(option_window, text=f"还有 {count - preview_count} 张图片未显示预览，将按拖入顺序处理。",
                     fg="#666666", font=("Microsoft YaHei", 9)).pack(pady=(2, 6))

        def close_and_run(action):
            option_window.destroy()
            # 拖入图片后当前页 +1（取消则不递增）
            if action != "cancel":
                self._capture_history_book_page()
                self._increment_book_page_for_import()
            if action == "accurate":
                self._start_high_accuracy_recognition(image_files)
            elif action == "basic":
                self._start_quick_recognition(image_files)
            elif action == "general":
                self._start_general_recognition(image_files)
            elif action == "merge":
                self._merge_images_from_drag(image_files)
            elif action == "crop":
                self._open_crop_window(image_files)

        button_frame = tk.Frame(option_window)
        button_frame.pack(pady=(14, 6))

        tk.Button(button_frame, text=recommend_text, command=lambda: close_and_run(recommend_action),
                  bg="#1976D2", fg="white", padx=24, pady=9,
                  font=("Microsoft YaHei", self.current_font_size, "bold")).pack(side=tk.LEFT, padx=6)

        if count == 2 and recommend_action != "merge":
            tk.Button(button_frame, text="拼接图片", command=lambda: close_and_run("merge"),
                      bg="#FF9800", fg="white", padx=18, pady=8,
                      font=("Microsoft YaHei", 10)).pack(side=tk.LEFT, padx=6)

        tk.Button(button_frame, text="高精度识别", command=lambda: close_and_run("accurate"),
                  bg="#2196F3", fg="white", padx=18, pady=8,
                  font=("Microsoft YaHei", 10)).pack(side=tk.LEFT, padx=6)
        tk.Button(button_frame, text="通用识别", command=lambda: close_and_run("general"),
                  bg="#9C27B0", fg="white", padx=18, pady=8,
                  font=("Microsoft YaHei", 10)).pack(side=tk.LEFT, padx=6)
        tk.Button(button_frame, text="快速识别", command=lambda: close_and_run("basic"),
                  bg="#00BCD4", fg="white", padx=18, pady=8,
                  font=("Microsoft YaHei", 10)).pack(side=tk.LEFT, padx=6)

        bottom_frame = tk.Frame(option_window)
        bottom_frame.pack(pady=(4, 12))
        tk.Button(bottom_frame, text="裁剪识别", command=lambda: close_and_run("crop"),
                  bg="#4CAF50", fg="white", padx=18, pady=8,
                  font=("Microsoft YaHei", 10)).pack(side=tk.LEFT, padx=6)
        tk.Button(bottom_frame, text="取消", command=option_window.destroy,
                  bg="#757575", fg="white", padx=22, pady=8,
                  font=("Microsoft YaHei", 10)).pack(side=tk.LEFT, padx=6)

    def _show_single_image_drop_options(self, image_file):
        """显示单张图片拖入操作选项。"""
        self._show_drop_preview_options([image_file])
    
    def _show_multi_image_options(self, image_files):
        """显示两张图片拖入操作选项。"""
        option_window = self.create_popup_window(self.root, "选择操作", "multi_image_options", 500, 480)
        
        tk.Label(option_window, text="🖼️ 检测到 2 张图片", 
                font=("Arial", 14, "bold")).pack(pady=18)
        
        file_preview = "\n".join([f"{i + 1}. {os.path.basename(path)}" for i, path in enumerate(image_files)])
        tk.Label(option_window, text=file_preview, 
                fg="blue", font=("Arial", 10), justify=tk.LEFT, wraplength=420).pack(pady=5)
        
        tk.Label(option_window, text="请选择操作方式：", 
                font=("Arial", 10)).pack(pady=12)
        
        # 选项1：拼接图片
        option1_frame = tk.Frame(option_window, relief=tk.RIDGE, borderwidth=2, bg="#FFF3E0")
        option1_frame.pack(pady=8, padx=30, fill=tk.X)
        
        tk.Label(option1_frame, text="1️⃣ 拼接图片", 
                font=("Arial", 12, "bold"), bg="#FFF3E0").pack(pady=8)
        
        tk.Label(option1_frame, text="将两张图片横向拼接成一张，可在预览中切换方向", 
                fg="gray", font=("Arial", 9), bg="#FFF3E0").pack(pady=5)
        
        def merge_images_action():
            option_window.destroy()
            self._merge_images_from_drag(image_files)
        
        tk.Button(option1_frame, text="拼接图片", command=merge_images_action,
                 bg="#FF9800", fg="white", padx=20, pady=6, font=("Arial", 10)).pack(pady=8)
        
        # 选项2：批量识别
        option1_frame = tk.Frame(option_window, relief=tk.RIDGE, borderwidth=2, bg="#E3F2FD")
        option1_frame.pack(pady=8, padx=30, fill=tk.X)
        
        tk.Label(option1_frame, text="2️⃣ 批量识别", 
                font=("Arial", 12, "bold"), bg="#E3F2FD").pack(pady=8)
        
        tk.Label(option1_frame, text="按拖入顺序分别识别两张图片", 
                fg="gray", font=("Arial", 9), bg="#E3F2FD").pack(pady=5)
        
        def batch_recognize():
            option_window.destroy()
            self._start_high_accuracy_recognition(image_files)
        
        tk.Button(option1_frame, text="批量识别", command=batch_recognize,
                 bg="#2196F3", fg="white", padx=20, pady=6, font=("Arial", 10)).pack(pady=8)

        # 选项3：裁剪识别
        option3_frame = tk.Frame(option_window, relief=tk.RIDGE, borderwidth=2, bg="#E8F5E9")
        option3_frame.pack(pady=8, padx=30, fill=tk.X)

        tk.Label(option3_frame, text="3️⃣ 裁剪识别",
                font=("Arial", 12, "bold"), bg="#E8F5E9").pack(pady=8)

        tk.Label(option3_frame, text="在裁剪窗口中框选区域后进行识别",
                fg="gray", font=("Arial", 9), bg="#E8F5E9").pack(pady=5)

        def crop_recognize():
            option_window.destroy()
            self._open_crop_window(image_files)

        tk.Button(option3_frame, text="裁剪识别", command=crop_recognize,
                 bg="#4CAF50", fg="white", padx=20, pady=6, font=("Arial", 10)).pack(pady=8)

        # 取消按钮
        tk.Button(option_window, text="取消", command=option_window.destroy,
                 bg="#757575", fg="white", padx=30, pady=8).pack(pady=15)
    
    def _merge_images_horizontally(self, images, reverse_order=True):
        """横向拼接图片，reverse_order=True 时后面的图片排在左边。"""
        total_width = sum(img.width for img in images)
        max_height = max(img.height for img in images)
        merged_image = Image.new('RGB', (total_width, max_height), 'white')

        x_offset = 0
        ordered_images = reversed(images) if reverse_order else images
        for img in ordered_images:
            y_offset = (max_height - img.height) // 2
            merged_image.paste(img, (x_offset, y_offset))
            x_offset += img.width

        return merged_image, total_width, max_height

    def _show_merged_image_preview(self, images, item_label="图片数量", item_action="选择"):
        """显示拼接结果预览，可切换方向，并返回 choice, merged_image, width, height。"""
        from PIL import ImageTk

        item_count = len(images)
        reverse_order = [True]
        merged_image, total_width, max_height = self._merge_images_horizontally(
            images, reverse_order[0]
        )

        preview_dialog = tk.Toplevel(self.root)
        preview_dialog.title("拼接预览")
        preview_dialog.transient(self.root)
        preview_dialog.grab_set()

        screen_w = preview_dialog.winfo_screenwidth()
        screen_h = preview_dialog.winfo_screenheight()
        max_preview_w = int(screen_w * 0.8)
        max_preview_h = int(screen_h * 0.6)

        scale = min(max_preview_w / total_width, max_preview_h / max_height, 1.0)
        preview_w = max(1, int(total_width * scale))
        preview_h = max(1, int(max_height * scale))

        win_w = max(preview_w + 40, 720)
        win_h = preview_h + 190
        x = (screen_w - win_w) // 2
        y = (screen_h - win_h) // 2
        preview_dialog.geometry(f"{win_w}x{win_h}+{x}+{y}")
        preview_dialog.minsize(720, 320)

        tk.Label(preview_dialog, text="拼接预览",
                 font=("Microsoft YaHei", 13, "bold")).pack(pady=(12, 4))

        info_label = tk.Label(preview_dialog,
                              text=f"{item_label}: {item_count}  |  尺寸: {total_width}x{max_height}",
                              fg="gray", font=("Microsoft YaHei", 9))
        info_label.pack()

        order_label = tk.Label(preview_dialog, fg="#E65100", font=("Microsoft YaHei", 9))
        order_label.pack(pady=(4, 0))

        img_label = tk.Label(preview_dialog, relief=tk.SUNKEN, bd=1)
        img_label.pack(pady=10, padx=20)

        user_choice = [None]
        selected_merged_image = [merged_image]

        def update_preview():
            merged, _, _ = self._merge_images_horizontally(images, reverse_order[0])
            selected_merged_image[0] = merged
            preview_img = merged.resize((preview_w, preview_h), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(preview_img)
            img_label.config(image=photo)
            img_label.image = photo

            if reverse_order[0]:
                order_text = f"当前：反向拼接，后{item_action}的内容显示在左边，先{item_action}的内容显示在右边。"
                switch_text = "切换为正向拼接"
            else:
                order_text = f"当前：正向拼接，先{item_action}的内容显示在左边，后{item_action}的内容显示在右边。"
                switch_text = "切换为反向拼接"
            order_label.config(text=order_text)
            switch_btn.config(text=switch_text)

        def switch_direction():
            reverse_order[0] = not reverse_order[0]
            update_preview()

        def choose(choice):
            user_choice[0] = choice
            preview_dialog.destroy()

        btn_frame = tk.Frame(preview_dialog)
        btn_frame.pack(pady=10)

        switch_btn = tk.Button(btn_frame, text="切换为正向拼接", command=switch_direction,
                               bg="#FF9800", fg="white", font=("Microsoft YaHei", 10),
                               padx=18, pady=8)
        switch_btn.pack(side=tk.LEFT, padx=6)
        tk.Button(btn_frame, text="💾 保存并识别", command=lambda: choose('save'),
                  bg="#4CAF50", fg="white", font=("Microsoft YaHei", 10),
                  padx=18, pady=8).pack(side=tk.LEFT, padx=6)
        tk.Button(btn_frame, text="🔍 直接识别", command=lambda: choose('no_save'),
                  bg="#2196F3", fg="white", font=("Microsoft YaHei", 10),
                  padx=18, pady=8).pack(side=tk.LEFT, padx=6)
        tk.Button(btn_frame, text="取消", command=lambda: choose('cancel'),
                  bg="#757575", fg="white", font=("Microsoft YaHei", 10),
                  padx=18, pady=8).pack(side=tk.LEFT, padx=6)

        preview_dialog.protocol("WM_DELETE_WINDOW", lambda: choose('cancel'))
        update_preview()
        self.root.wait_window(preview_dialog)
        return user_choice[0] or 'cancel', selected_merged_image[0], total_width, max_height

    def _merge_images_from_drag(self, file_paths):
        """从拖放触发的拼接图片功能"""
        try:
            # 加载所有图片
            images = []
            for path in file_paths:
                img = Image.open(path)
                images.append(img)
            
            preview_choice, merged_image, total_width, max_height = self._show_merged_image_preview(
                images, item_label="图片数量", item_action="选择"
            )

            if preview_choice == 'cancel':
                return
            
            # 保存到临时文件
            import tempfile
            temp_dir = tempfile.gettempdir()
            temp_path = os.path.join(temp_dir, "merged_temp.jpg")
            merged_image.save(temp_path, format='JPEG', quality=90)
            
            # 如果选择保存
            if preview_choice == 'save':
                save_path = filedialog.asksaveasfilename(
                    defaultextension=".jpg",
                    filetypes=[("JPEG图片", "*.jpg"), ("PNG图片", "*.png"), ("所有文件", "*.*")],
                    initialfile=f"merged_{len(images)}images_{total_width}x{max_height}.jpg"
                )
                
                if save_path:
                    if save_path.lower().endswith('.png'):
                        merged_image.save(save_path, format='PNG')
                    else:
                        merged_image.save(save_path, format='JPEG', quality=95)
                    
                    self.progress_label.config(
                        text=f"✓ 拼接图片已保存到：{os.path.basename(save_path)}")
                    temp_path = save_path
            
            # 继续识别流程
            if preview_choice in ('save', 'no_save'):
                self.image_paths = [temp_path]
                self.file_label.config(
                    text=f"已选择: 拼接图片 ({len(images)}张) - {total_width}x{max_height}", 
                    fg="blue")
                
                # 直接使用高精度识别
                self.root.after(500, self.perform_ocr)
        
        except Exception as e:
            messagebox.showerror("错误", f"拼接失败：{str(e)}")
    
    def _create_ribbon_group(self, parent, title):
        """创建Ribbon功能组"""
        group_frame = tk.Frame(parent, bg="#f0f0f0", relief=tk.FLAT, bd=0)
        group_frame.pack(side=tk.LEFT, padx=5, pady=5)
        
        # 按钮容器
        btn_container = tk.Frame(group_frame, bg="#f0f0f0")
        btn_container.pack(side=tk.TOP, fill=tk.BOTH, expand=True, pady=(0, 3))
        
        # 组标题
        title_label = tk.Label(group_frame, text=title, bg="#f0f0f0", fg="#333", 
                              font=("Arial", 8), anchor=tk.CENTER)
        title_label.pack(side=tk.BOTTOM, fill=tk.X)
        
        # 右侧分隔线
        separator = tk.Frame(parent, width=1, bg="#d0d0d0")
        separator.pack(side=tk.LEFT, fill=tk.Y, padx=3, pady=8)
        
        return btn_container
    
    def _create_ribbon_button(self, parent, text, command, color, large=False, state=tk.NORMAL):
        """创建Ribbon按钮"""
        if large:
            # 大按钮（单个）
            btn = tk.Button(parent, text=text, command=command, bg=color, fg="white",
                          font=("Arial", 9), width=10, height=3, relief=tk.RAISED, bd=1,
                          cursor="hand2", state=state)
            btn.pack(side=tk.LEFT, padx=3, pady=2)
        else:
            # 小按钮（多个）
            btn = tk.Button(parent, text=text, command=command, bg=color, fg="white",
                          font=("Arial", 8), width=8, height=3, relief=tk.RAISED, bd=1,
                          cursor="hand2", state=state)
            btn.pack(side=tk.LEFT, padx=2, pady=2)
        
        # 鼠标悬停效果
        def on_enter(e):
            if btn['state'] != tk.DISABLED:
                btn['relief'] = tk.RAISED
                btn['bd'] = 2
        
        def on_leave(e):
            btn['relief'] = tk.RAISED
            btn['bd'] = 1
        
        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)
        
        return btn
    
    def unlock_size_limit(self):
        """解锁尺寸限制功能（提供两个选项）"""
        if self.size_limit_unlocked:
            # 已解锁，显示选项菜单
            self.show_unlock_menu()
            return
        
        # 创建密码输入窗口
        password_window = self.create_popup_window(self.root, "解锁尺寸限制", "unlock_password", 500, 350)
        
        tk.Label(password_window, text="🔓 解锁尺寸限制", 
                font=("Arial", 14, "bold")).pack(pady=20)
        
        tk.Label(password_window, text="解锁后可以：", 
                fg="gray", font=("Arial", 10)).pack(pady=5)
        
        tk.Label(password_window, text="1️⃣ 解除所有限制（任意尺寸使用高精度）", 
                fg="blue", font=("Arial", 9)).pack(pady=2)
        
        tk.Label(password_window, text="2️⃣ 修改尺寸范围（自定义限制）", 
                fg="blue", font=("Arial", 9)).pack(pady=2)
        
        tk.Label(password_window, text="请输入密码：", font=("Arial", 10)).pack(pady=15)
        password_entry = tk.Entry(password_window, show="*", font=("Arial", 12), width=20)
        password_entry.pack(pady=5)
        password_entry.focus_set()
        
        result_label = tk.Label(password_window, text="", fg="red")
        result_label.pack(pady=5)
        
        def check_password():
            entered_password = password_entry.get()
            if entered_password == self.unlock_password:
                self.size_limit_unlocked = True
                self.unlock_btn.config(text="🔓 已解锁", bg="#4CAF50")
                
                password_window.destroy()
                
                # 显示选项菜单
                self.show_unlock_menu()
                
                if self.image_paths:
                    if len(self.image_paths) == 1:
                        self.select_file_internal(self.image_paths[0])
                    else:
                        self.batch_select_files_internal(self.image_paths)
            else:
                result_label.config(text="❌ 密码错误，请重试")
                password_entry.delete(0, tk.END)
        
        btn_frame = tk.Frame(password_window)
        btn_frame.pack(pady=15)
        
        tk.Button(btn_frame, text="确定", command=check_password,
                 bg="#4CAF50", fg="white", padx=30, pady=8).pack(side=tk.LEFT, padx=5)
        
        tk.Button(btn_frame, text="取消", command=password_window.destroy,
                 bg="#757575", fg="white", padx=30, pady=8).pack(side=tk.LEFT, padx=5)
        
        password_entry.bind("<Return>", lambda e: check_password())
    
    def show_unlock_menu(self):
        """显示解锁后的选项菜单"""
        menu_window = self.create_popup_window(self.root, "尺寸限制管理", "size_limit_menu", 550, 500)
        
        tk.Label(menu_window, text="🔓 尺寸限制管理", 
                font=("Arial", 14, "bold")).pack(pady=20)
        
        tk.Label(menu_window, text="请选择操作：", 
                fg="gray", font=("Arial", 10)).pack(pady=10)
        
        # 选项1：解除所有限制
        option1_frame = tk.Frame(menu_window, relief=tk.RIDGE, borderwidth=2, bg="#E3F2FD")
        option1_frame.pack(pady=10, padx=30, fill=tk.X)
        
        tk.Label(option1_frame, text="1️⃣ 解除所有限制", 
                font=("Arial", 12, "bold"), bg="#E3F2FD").pack(pady=10)
        
        tk.Label(option1_frame, text="允许对任意尺寸的图片使用高精度识别\n不受尺寸范围限制", 
                fg="gray", font=("Arial", 9), bg="#E3F2FD").pack(pady=5)
        
        def remove_all_limits():
            # 设置为无限制模式
            if hasattr(self, 'size_hint_label'):
                bas_range = f"{self.size_limits['basic_min_width']}~{self.size_limits['basic_max_width']}x{self.size_limits['basic_min_height']}~{self.size_limits['basic_max_height']}"
                self.size_hint_label.config(text=f"💡 高精度(已解除限制) | 快速({bas_range})")
            else:
                # 兼容旧版本的更新方式
                for widget in self.progress_frame.winfo_children():
                    if isinstance(widget, tk.Label) and ("高精度" in widget.cget("text") or "已解锁" in widget.cget("text")):
                        bas_range = f"{self.size_limits['basic_min_width']}~{self.size_limits['basic_max_width']}x{self.size_limits['basic_min_height']}~{self.size_limits['basic_max_height']}"
                        widget.config(text=f"💡 高精度(已解除限制) | 快速({bas_range})")
            
            menu_window.destroy()
            messagebox.showinfo("成功", 
                "已解除所有尺寸限制！\n\n"
                "现在可以对任意尺寸的图片使用高精度识别")
            
            if self.image_paths:
                if len(self.image_paths) == 1:
                    self.select_file_internal(self.image_paths[0])
                else:
                    self.batch_select_files_internal(self.image_paths)
        
        tk.Button(option1_frame, text="解除所有限制", command=remove_all_limits,
                 bg="#2196F3", fg="white", padx=20, pady=8, font=("Arial", 10)).pack(pady=10)
        
        # 选项2：修改尺寸范围
        option2_frame = tk.Frame(menu_window, relief=tk.RIDGE, borderwidth=2, bg="#FFF3E0")
        option2_frame.pack(pady=10, padx=30, fill=tk.X)
        
        tk.Label(option2_frame, text="2️⃣ 修改尺寸范围", 
                font=("Arial", 12, "bold"), bg="#FFF3E0").pack(pady=10)
        
        tk.Label(option2_frame, text="自定义高精度和快速识别的尺寸范围\n更灵活地控制识别条件", 
                fg="gray", font=("Arial", 9), bg="#FFF3E0").pack(pady=5)
        
        def open_size_settings():
            menu_window.destroy()
            self.show_size_settings()
        
        tk.Button(option2_frame, text="修改尺寸范围", command=open_size_settings,
                 bg="#FF9800", fg="white", padx=20, pady=8, font=("Arial", 10)).pack(pady=10)
        
        # 关闭按钮
        tk.Button(menu_window, text="关闭", command=menu_window.destroy,
                 bg="#757575", fg="white", padx=30, pady=8).pack(pady=15)
    
    def select_file_internal(self, file_path):
        """内部方法：处理文件选择逻辑"""
        self.image_paths = [file_path]
        
        try:
            img = Image.open(file_path)
            width, height = img.size
            file_size = os.path.getsize(file_path)
            
            if file_size < 1024 * 1024:
                size_str = f"{file_size/1024:.1f}KB"
            else:
                size_str = f"{file_size/(1024*1024):.1f}MB"
            
            if self.size_limit_unlocked:
                meets_accurate_requirement = True
            else:
                # 高精度：宽度和高度都在范围内（两个都要满足）
                width_in_accurate_range = self.size_limits["accurate_min_width"] <= width <= self.size_limits["accurate_max_width"]
                height_in_accurate_range = self.size_limits["accurate_min_height"] <= height <= self.size_limits["accurate_max_height"]
                meets_accurate_requirement = width_in_accurate_range and height_in_accurate_range
            
            # 快速识别：宽度和高度都在范围内（两个都要满足）
            width_in_basic_range = self.size_limits["basic_min_width"] <= width <= self.size_limits["basic_max_width"]
            height_in_basic_range = self.size_limits["basic_min_height"] <= height <= self.size_limits["basic_max_height"]
            meets_basic_requirement = width_in_basic_range and height_in_basic_range
            
            # 通用识别：宽度和高度都在范围内（两个都要满足）
            width_in_general_range = self.size_limits["general_min_width"] <= width <= self.size_limits["general_max_width"]
            height_in_general_range = self.size_limits["general_min_height"] <= height <= self.size_limits["general_max_height"]
            meets_general_requirement = width_in_general_range and height_in_general_range
            has_accurate_key = self._has_ocr_key('accurate')
            has_basic_key = self._has_ocr_key('basic')
            has_general_key = self._has_ocr_key('general')
            
            # 统计符合的模式数量
            available_modes = []
            if meets_accurate_requirement and has_accurate_key:
                available_modes.append("高精度")
            if meets_basic_requirement and has_basic_key:
                available_modes.append("快速")
            if meets_general_requirement and has_general_key:
                available_modes.append("通用")
            
            # 根据可用模式设置按钮状态和提示信息
            self.ocr_btn.config(state=tk.NORMAL if meets_accurate_requirement and has_accurate_key else tk.DISABLED)
            self.quick_ocr_btn.config(state=tk.NORMAL if meets_basic_requirement and has_basic_key else tk.DISABLED)
            self.general_ocr_btn.config(state=tk.NORMAL if meets_general_requirement and has_general_key else tk.DISABLED)
            
            unlock_hint = " [已解锁]" if self.size_limit_unlocked and (width < self.size_limits["accurate_min_width"] or height < self.size_limits["accurate_min_height"]) else ""
            
            if len(available_modes) == 3:
                # 三种模式都可用
                info_text = f"已选择: {os.path.basename(file_path)} ({width}x{height}, {size_str}){unlock_hint}"
                self.file_label.config(text=info_text, fg="black")
                self.progress_label.config(text="")
            elif len(available_modes) == 2:
                # 两种模式可用
                modes_str = "、".join(available_modes)
                info_text = f"已选择: {os.path.basename(file_path)} ({width}x{height}, {size_str}){unlock_hint} ✓ 可用: {modes_str}"
                self.file_label.config(text=info_text, fg="blue")
                unavailable = [m for m in ["高精度", "快速", "通用"] if m not in available_modes]
                self.progress_label.config(text=f"💡 提示：{unavailable[0]}识别不可用，建议使用{modes_str}识别")
            elif len(available_modes) == 1:
                # 只有一种模式可用
                mode_str = available_modes[0]
                info_text = f"已选择: {os.path.basename(file_path)} ({width}x{height}, {size_str}){unlock_hint} ⚠️ 仅可用: {mode_str}"
                self.file_label.config(text=info_text, fg="orange")
                self.progress_label.config(text=f"💡 提示：该图片尺寸仅符合{mode_str}识别要求")
            else:
                # 没有可用模式
                info_text = f"已选择: {os.path.basename(file_path)} ({width}x{height}, {size_str}) ❌ 尺寸不符合任何识别要求"
                self.file_label.config(text=info_text, fg="red")
                self.progress_label.config(text="❌ 错误：图片尺寸不符合任何识别要求，请检查图片尺寸或点击「解锁限制」")
        except:
            self.file_label.config(text=f"已选择: {os.path.basename(file_path)}", fg="black")
            self._update_ocr_btn_by_keys()
            self.progress_label.config(text="")
    
    def select_file(self):
        """选择图片文件（支持多选）"""
        file_paths = filedialog.askopenfilenames(
            title="选择图片（可多选）",
            filetypes=[("图片文件", "*.jpg *.jpeg *.png *.bmp"), ("所有文件", "*.*")]
        )
        if file_paths:
            if len(file_paths) == 1:
                self.select_file_internal(file_paths[0])
            else:
                self.batch_select_files_internal(list(file_paths))
            # 导入新图片后，当前页 +1
            self._capture_history_book_page()
            self._increment_book_page_for_import()
    
    def batch_select_files_internal(self, file_paths):
        """内部方法：处理批量文件选择逻辑"""
        self.image_paths = file_paths
        count = len(self.image_paths)
        
        meets_accurate_count = 0
        meets_basic_count = 0
        meets_general_count = 0
        meets_all_count = 0
        meets_none_count = 0
        
        try:
            total_size = 0
            for path in self.image_paths:
                total_size += os.path.getsize(path)
                try:
                    img = Image.open(path)
                    width, height = img.size
                    
                    if self.size_limit_unlocked:
                        meets_accurate = True
                    else:
                        # 高精度：宽度和高度都在范围内
                        width_in_accurate = self.size_limits["accurate_min_width"] <= width <= self.size_limits["accurate_max_width"]
                        height_in_accurate = self.size_limits["accurate_min_height"] <= height <= self.size_limits["accurate_max_height"]
                        meets_accurate = width_in_accurate and height_in_accurate
                    
                    # 快速识别：宽度和高度都在范围内
                    width_in_basic = self.size_limits["basic_min_width"] <= width <= self.size_limits["basic_max_width"]
                    height_in_basic = self.size_limits["basic_min_height"] <= height <= self.size_limits["basic_max_height"]
                    meets_basic = width_in_basic and height_in_basic
                    
                    # 通用识别：宽度和高度都在范围内
                    width_in_general = self.size_limits["general_min_width"] <= width <= self.size_limits["general_max_width"]
                    height_in_general = self.size_limits["general_min_height"] <= height <= self.size_limits["general_max_height"]
                    meets_general = width_in_general and height_in_general
                    
                    # 统计各种组合
                    available_modes = 0
                    if meets_accurate:
                        meets_accurate_count += 1
                        available_modes += 1
                    if meets_basic:
                        meets_basic_count += 1
                        available_modes += 1
                    if meets_general:
                        meets_general_count += 1
                        available_modes += 1
                    
                    if available_modes == 3:
                        meets_all_count += 1
                    elif available_modes == 0:
                        meets_none_count += 1
                        
                except:
                    meets_none_count += 1
            
            if total_size < 1024 * 1024:
                size_str = f"{total_size/1024:.1f}KB"
            else:
                size_str = f"{total_size/(1024*1024):.1f}MB"
            
            info_parts = [f"已选择 {count} 个文件 (总大小: {size_str})"]
            if meets_all_count > 0:
                info_parts.append(f"全部可用: {meets_all_count}张")
            if meets_accurate_count > meets_all_count:
                info_parts.append(f"高精度: {meets_accurate_count}张")
            if meets_basic_count > meets_all_count:
                info_parts.append(f"快速: {meets_basic_count}张")
            if meets_general_count > meets_all_count:
                info_parts.append(f"通用: {meets_general_count}张")
            if meets_none_count > 0:
                info_parts.append(f"都不符合: {meets_none_count}张")
            
            info_text = " | ".join(info_parts)
            
            # 设置按钮状态
            has_accurate_key = self._has_ocr_key('accurate')
            has_basic_key = self._has_ocr_key('basic')
            has_general_key = self._has_ocr_key('general')
            usable_accurate_count = meets_accurate_count if has_accurate_key else 0
            usable_basic_count = meets_basic_count if has_basic_key else 0
            usable_general_count = meets_general_count if has_general_key else 0
            self.ocr_btn.config(state=tk.NORMAL if usable_accurate_count > 0 else tk.DISABLED)
            self.quick_ocr_btn.config(state=tk.NORMAL if usable_basic_count > 0 else tk.DISABLED)
            self.general_ocr_btn.config(state=tk.NORMAL if usable_general_count > 0 else tk.DISABLED)
            
            # 根据可用模式数量设置提示信息
            available_mode_count = sum([1 for count in [usable_accurate_count, usable_basic_count, usable_general_count] if count > 0])
            
            if available_mode_count == 3:
                self.file_label.config(text=info_text, fg="black")
                if meets_none_count > 0:
                    self.progress_label.config(text=f"💡 提示：{meets_none_count}张图片不符合任何识别要求，将被跳过")
                else:
                    self.progress_label.config(text="")
            elif available_mode_count == 2:
                available_modes = []
                if usable_accurate_count > 0:
                    available_modes.append("高精度")
                if usable_basic_count > 0:
                    available_modes.append("快速")
                if usable_general_count > 0:
                    available_modes.append("通用")
                modes_str = "、".join(available_modes)
                self.file_label.config(text=info_text + f" ✓ 可用: {modes_str}", fg="blue")
                self.progress_label.config(text=f"💡 提示：部分图片可用{modes_str}识别")
            elif available_mode_count == 1:
                if usable_accurate_count > 0:
                    mode_str = "高精度"
                elif usable_basic_count > 0:
                    mode_str = "快速"
                else:
                    mode_str = "通用"
                self.file_label.config(text=info_text + f" ⚠️ 仅可用: {mode_str}", fg="orange")
                self.progress_label.config(text=f"💡 提示：所有图片仅符合{mode_str}识别要求")
            else:
                self.file_label.config(text=info_text + " ❌ 所有图片都不符合任何识别要求", fg="red")
                if self.size_limit_unlocked:
                    self.progress_label.config(text="❌ 错误：所有图片尺寸都不符合任何识别要求")
                else:
                    self.progress_label.config(text="❌ 错误：所有图片尺寸都不符合任何识别要求，可点击「解锁限制」")
        except:
            self.file_label.config(text=f"已选择 {count} 个文件", fg="black")
            self._update_ocr_btn_by_keys()
            self.progress_label.config(text="")

    def calculate_image_hash(self, image_path):
        """Return a SHA-256 fingerprint for the original image bytes."""
        sha256 = hashlib.sha256()
        with open(image_path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def _ocr_cache_key(self, image_hash, ocr_type):
        return f"{ocr_type}:{image_hash}"

    def get_cached_ocr_result(self, image_path, ocr_type):
        try:
            image_hash = self.calculate_image_hash(image_path)
            cache = self.store.get('ocr_cache', {}) or {}
            record = cache.get(self._ocr_cache_key(image_hash, ocr_type))
            if not record:
                return image_hash, None
            return image_hash, {
                'file': os.path.basename(image_path),
                'path': image_path,
                'lines': record.get('lines', []),
                'count': len(record.get('lines', [])),
                'cached': True,
                'image_hash': image_hash,
                'cached_from': record.get('file', '')
            }
        except Exception as e:
            print(f"读取OCR缓存失败: {e}")
            return None, None

    def save_ocr_cache(self, image_hash, ocr_type, image_path, lines):
        if not image_hash or not lines:
            return
        try:
            cache = self.store.get('ocr_cache', {}) or {}
            cache[self._ocr_cache_key(image_hash, ocr_type)] = {
                'hash': image_hash,
                'type': ocr_type,
                'file': os.path.basename(image_path),
                'path': image_path,
                'lines': lines,
                'line_count': len(lines),
                'updated_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            self.store.set('ocr_cache', cache)
        except Exception as e:
            print(f"保存OCR缓存失败: {e}")

    def append_cached_ocr_result(self, image_path, cached_result):
        cached_from = cached_result.get('cached_from') or cached_result.get('file', '')
        if cached_from and cached_from != os.path.basename(image_path):
            note = f"命中已识别图片缓存，复用结果（来源: {cached_from}）\n"
        else:
            note = "命中已识别图片缓存，复用结果\n"
        self.root.after(0, lambda n=note: self.result_text.insert(tk.END, n))
        recognized_text = "\n".join(cached_result.get('lines', []))
        if recognized_text:
            self.root.after(0, lambda t=recognized_text: self.result_text.insert(tk.END, t + "\n"))
        self.all_results.append(cached_result)
        self.root.after(0, lambda c=cached_result.get('count', 0):
            self.result_text.insert(tk.END, f"\n缓存复用成功：{c} 行文字\n"))
        self.root.after(0, lambda: self.result_text.see(tk.END))

    def perform_ocr(self):
        """执行 OCR 识别（支持批量）- 使用多线程避免卡顿"""
        if not self.image_paths:
            messagebox.showwarning("警告", "请先选择图片文件！")
            return
        
        if not API_KEY or not SECRET_KEY:
            messagebox.showerror("错误", "请先在 .env 文件中配置 API_KEY 和 SECRET_KEY！")
            return
        
        self.ocr_btn.config(state=tk.DISABLED)
        self.select_btn.config(state=tk.DISABLED)
        
        thread = threading.Thread(target=self._perform_ocr_thread, daemon=True)
        thread.start()
    
    def _perform_ocr_thread(self):
        """OCR识别线程（后台执行）"""
        try:
            self.root.after(0, lambda: self.result_text.delete(1.0, tk.END))
            self.all_results = []
            
            total = len(self.image_paths)
            
            for idx, image_path in enumerate(self.image_paths, 1):
                self.root.after(0, lambda i=idx, p=image_path: 
                    self.progress_label.config(text=f"正在处理: {i}/{total} - {os.path.basename(p)}"))
                
                self.root.after(0, lambda: self.result_text.insert(tk.END, f"\n{'='*80}\n"))
                self.root.after(0, lambda i=idx, p=image_path: 
                    self.result_text.insert(tk.END, f"文件 {i}/{total}: {os.path.basename(p)}\n"))
                self.root.after(0, lambda: self.result_text.insert(tk.END, f"{'='*80}\n"))
                
                try:
                    img = Image.open(image_path)
                    width, height = img.size
                    
                    unlock_status = " [已解锁]" if self.size_limit_unlocked else ""
                    self.root.after(0, lambda w=width, h=height, u=unlock_status: 
                        self.result_text.insert(tk.END, f"图片尺寸: {w}x{h}{u}\n"))
                    
                    # 检查是否符合高精度识别要求
                    if not self.size_limit_unlocked:
                        width_in_accurate = self.size_limits["accurate_min_width"] <= width <= self.size_limits["accurate_max_width"]
                        height_in_accurate = self.size_limits["accurate_min_height"] <= height <= self.size_limits["accurate_max_height"]
                        meets_accurate = width_in_accurate and height_in_accurate
                        
                        if not meets_accurate:
                            acc_w_range = f"{self.size_limits['accurate_min_width']}~{self.size_limits['accurate_max_width']}"
                            acc_h_range = f"{self.size_limits['accurate_min_height']}~{self.size_limits['accurate_max_height']}"
                            self.root.after(0, lambda w=width, h=height, wr=acc_w_range, hr=acc_h_range: 
                                self.result_text.insert(tk.END, 
                                    f"⚠️ 跳过：图片尺寸不符合要求\n"
                                    f"   当前尺寸: {w}x{h}\n"
                                    f"   要求：宽度({wr})且高度({hr})都要在范围内\n"
                                    f"   建议使用「快速识别」按钮或点击「解锁限制」\n"))
                            
                            self.all_results.append({
                                'file': os.path.basename(image_path),
                                'path': image_path,
                                'lines': [],
                                'count': 0,
                                'skipped': True,
                                'reason': f'图片尺寸不符合要求（{width}x{height}）'
                            })
                            
                            self.root.after(0, lambda: self.result_text.see(tk.END))
                            continue
                    
                except Exception as e:
                    self.root.after(0, lambda err=str(e): 
                        self.result_text.insert(tk.END, f"⚠️ 无法读取图片尺寸: {err}\n"))
                
                image_hash, cached_result = self.get_cached_ocr_result(image_path, 'accurate')
                if cached_result:
                    self.append_cached_ocr_result(image_path, cached_result)
                    continue

                result = ocr_image(image_path)
                
                if "words_result" in result:
                    formatted_lines = []
                    for item in result["words_result"]:
                        words = item["words"]
                        location = item.get("location", {})
                        top = location.get("top", 0)
                        left = location.get("left", 0)
                        height = location.get("height", 0)
                        formatted_lines.append(f"{words}|{top}|{left}|{height}")
                    
                    recognized_text = "\n".join(formatted_lines)
                    self.root.after(0, lambda t=recognized_text: 
                        self.result_text.insert(tk.END, t + "\n"))
                    
                    self.all_results.append({
                        'file': os.path.basename(image_path),
                        'path': image_path,
                        'lines': formatted_lines,
                        'count': len(formatted_lines),
                        'image_hash': image_hash
                    })
                    self.save_ocr_cache(image_hash, 'accurate', image_path, formatted_lines)
                    
                    self.root.after(0, lambda c=len(formatted_lines): 
                        self.result_text.insert(tk.END, f"\n✓ 识别成功：{c} 行文字\n"))
                else:
                    self.root.after(0, lambda r=result: 
                        self.result_text.insert(tk.END, f"✗ 识别失败：{r}\n"))
                    self.all_results.append({
                        'file': os.path.basename(image_path),
                        'path': image_path,
                        'lines': [],
                        'count': 0,
                        'error': str(result)
                    })
                
                self.root.after(0, lambda: self.result_text.see(tk.END))
                
                if idx < total:
                    import time
                    time.sleep(0.5)
            
            cached_count = sum(1 for r in self.all_results if r.get('cached') and r.get('count', 0) > 0)
            cached_lines = sum(r['count'] for r in self.all_results if r.get('cached'))
            success_count = sum(1 for r in self.all_results if r['count'] > 0)
            api_success_count = success_count - cached_count
            skipped_count = sum(1 for r in self.all_results if r.get('skipped', False))
            failed_count = sum(1 for r in self.all_results if r.get('error') and not r.get('skipped', False))
            total_lines = sum(r['count'] for r in self.all_results)
            api_lines = total_lines - cached_lines
            stats_success_count = success_count if self.stats_count_cache_as_success else api_success_count
            
            if total > 0:
                self.record_ocr('accurate', stats_success_count, failed_count, total_lines,
                                cached_count=cached_count, cached_lines=cached_lines,
                                api_lines=api_lines, processed_count=total - skipped_count)
                if skipped_count > 0:
                    today = datetime.now().strftime("%Y-%m-%d")
                    if today in self.stats and 'accurate' in self.stats[today]:
                        self.stats[today]['accurate']['skipped'] += skipped_count
                        self.save_stats()
                
                # 添加到历史记录（在主线程中执行）
                results_copy = [r.copy() for r in self.all_results]
                self.root.after(0, lambda: self.add_to_history('高精度识别', results_copy))
            
            self.root.after(0, lambda: self.progress_label.config(text=f"✓ 完成！共处理 {total} 个文件"))
            self.root.after(0, lambda: self.export_btn.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.copy_btn.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.add_zeros_btn.config(state=tk.NORMAL))
            self.root.after(0, self._update_ocr_btn_by_keys)
            self.root.after(0, lambda: self.select_btn.config(state=tk.NORMAL))
            
            status_msg = f"✓ 高精度识别完成！总:{total} 成功:{success_count}"
            if cached_count > 0:
                status_msg += f" 缓存:{cached_count}"
            if skipped_count > 0:
                status_msg += f" 跳过:{skipped_count}"
            if failed_count > 0:
                status_msg += f" 失败:{failed_count}"
            status_msg += f" | 文字行数:{total_lines}"
            if skipped_count > 0:
                status_msg += " | 💡跳过的图片可用快速识别"
            
            self.root.after(0, lambda m=status_msg: self.progress_label.config(text=m))
        
        except Exception as e:
            self.root.after(0, lambda: self.result_text.insert(tk.END, f"\n发生错误：{str(e)}\n"))
            self.root.after(0, lambda: messagebox.showerror("错误", f"发生错误：{str(e)}"))
            self.root.after(0, lambda: self.progress_label.config(text="✗ 处理失败"))
            self.root.after(0, self._update_ocr_btn_by_keys)
            self.root.after(0, lambda: self.select_btn.config(state=tk.NORMAL))

    

    

    def _perform_screenshot_ocr(self):
        """截图专用OCR识别，跳过尺寸限制直接调用通用识别接口"""
        if not self.image_paths:
            messagebox.showwarning("警告", "请先选择图片文件！")
            return

        if not API_KEY_GENERAL or not SECRET_KEY_GENERAL:
            messagebox.showerror("错误", "请先在 .env 文件中配置 API_KEY_GENERAL 和 SECRET_KEY_GENERAL！")
            return

        self.ocr_btn.config(state=tk.DISABLED)
        self.quick_ocr_btn.config(state=tk.DISABLED)
        self.general_ocr_btn.config(state=tk.DISABLED)
        self.select_btn.config(state=tk.DISABLED)

        def _thread():
            try:
                image_path = self.image_paths[0]
                self.root.after(0, lambda: self.result_text.delete(1.0, tk.END))
                self.root.after(0, lambda: self.progress_label.config(text="通用识别中（截图）..."))
                self.all_results = []

                image_hash, cached_result = self.get_cached_ocr_result(image_path, 'general')
                if cached_result:
                    self.append_cached_ocr_result(image_path, cached_result)
                else:
                    result = ocr_image_general(image_path)
                    if "words_result" in result:
                        formatted_lines = []
                        for item in result["words_result"]:
                            words = item["words"]
                            location = item.get("location", {})
                            top = location.get("top", 0)
                            left = location.get("left", 0)
                            height_val = location.get("height", 0)
                            formatted_lines.append(f"{words}|{top}|{left}|{height_val}")
                        recognized_text = "\n".join(formatted_lines)
                        self.root.after(0, lambda t=recognized_text: self.result_text.insert(tk.END, t + "\n"))
                        self.all_results.append({
                            'file': os.path.basename(image_path),
                            'path': image_path,
                            'lines': formatted_lines,
                            'count': len(formatted_lines),
                            'image_hash': image_hash
                        })
                        self.save_ocr_cache(image_hash, 'general', image_path, formatted_lines)
                        self.root.after(0, lambda c=len(formatted_lines):
                            self.result_text.insert(tk.END, f"\n✓ 识别成功：{c} 行文字\n"))
                    else:
                        self.root.after(0, lambda r=result:
                            self.result_text.insert(tk.END, f"✗ 识别失败：{r}\n"))
                        self.all_results.append({
                            'file': os.path.basename(image_path),
                            'path': image_path,
                            'lines': [],
                            'count': 0,
                            'error': str(result)
                        })

                self.root.after(0, lambda: self.result_text.see(tk.END))
                self.root.after(0, lambda: self.export_btn.config(state=tk.NORMAL))
                self.root.after(0, lambda: self.copy_btn.config(state=tk.NORMAL))
                self.root.after(0, lambda: self.add_zeros_btn.config(state=tk.NORMAL))
                self.root.after(0, self._update_ocr_btn_by_keys)
                self.root.after(0, lambda: self.select_btn.config(state=tk.NORMAL))
                total_lines = sum(r['count'] for r in self.all_results)
                self.root.after(0, lambda: self.progress_label.config(
                    text=f"✓ 截图识别完成！文字行数：{total_lines}"))
            except Exception as e:
                self.root.after(0, lambda: self.result_text.insert(tk.END, f"\n发生错误：{str(e)}\n"))
                self.root.after(0, lambda: messagebox.showerror("错误", f"发生错误：{str(e)}"))
                self.root.after(0, lambda: self.progress_label.config(text="✗ 处理失败"))
                self.root.after(0, self._update_ocr_btn_by_keys)
                self.root.after(0, lambda: self.select_btn.config(state=tk.NORMAL))

        import threading
        threading.Thread(target=_thread, daemon=True).start()

    def perform_general_ocr(self):
        """执行通用 OCR 识别"""
        if not self.image_paths:
            messagebox.showwarning("警告", "请先选择图片文件！")
            return
        
        if not API_KEY_GENERAL or not SECRET_KEY_GENERAL:
            messagebox.showerror("错误", "请先在 .env 文件中配置 API_KEY_GENERAL 和 SECRET_KEY_GENERAL！")
            return
        
        self.ocr_btn.config(state=tk.DISABLED)
        self.quick_ocr_btn.config(state=tk.DISABLED)
        self.general_ocr_btn.config(state=tk.DISABLED)
        self.select_btn.config(state=tk.DISABLED)
        
        thread = threading.Thread(target=self._perform_general_ocr_thread, daemon=True)
        thread.start()
    
    def _perform_general_ocr_thread(self):
        """通用OCR识别线程"""
        try:
            self.root.after(0, lambda: self.result_text.delete(1.0, tk.END))
            self.all_results = []
            
            total = len(self.image_paths)
            
            for idx, image_path in enumerate(self.image_paths, 1):
                self.root.after(0, lambda i=idx, p=image_path: 
                    self.progress_label.config(text=f"通用识别中: {i}/{total} - {os.path.basename(p)}"))
                
                self.root.after(0, lambda: self.result_text.insert(tk.END, f"\n{'='*80}\n"))
                self.root.after(0, lambda i=idx, p=image_path: 
                    self.result_text.insert(tk.END, f"文件 {i}/{total}: {os.path.basename(p)}\n"))
                self.root.after(0, lambda: self.result_text.insert(tk.END, f"{'='*80}\n"))
                
                try:
                    img = Image.open(image_path)
                    width, height = img.size
                    
                    self.root.after(0, lambda w=width, h=height: 
                        self.result_text.insert(tk.END, f"图片尺寸: 宽{w} x 高{h}\n"))
                    
                    # 检查是否符合通用识别要求
                    width_in_general = self.size_limits["general_min_width"] <= width <= self.size_limits["general_max_width"]
                    height_in_general = self.size_limits["general_min_height"] <= height <= self.size_limits["general_max_height"]
                    meets_general = width_in_general and height_in_general
                    
                    if not meets_general:
                        gen_w_range = f"{self.size_limits['general_min_width']}~{self.size_limits['general_max_width']}"
                        gen_h_range = f"{self.size_limits['general_min_height']}~{self.size_limits['general_max_height']}"
                        self.root.after(0, lambda w=width, h=height, wr=gen_w_range, hr=gen_h_range: 
                            self.result_text.insert(tk.END, 
                                f"⚠️ 跳过：图片尺寸不符合要求\n"
                                f"   当前尺寸: 宽{w} x 高{h}\n"
                                f"   要求：宽度({wr})且高度({hr})都要在范围内\n"
                                f"   建议使用其他识别模式\n"))
                        
                        self.all_results.append({
                            'file': os.path.basename(image_path),
                            'path': image_path,
                            'lines': [],
                            'count': 0,
                            'skipped': True,
                            'reason': f'图片尺寸不符合要求（宽{width} x 高{height}）'
                        })
                        
                        self.root.after(0, lambda: self.result_text.see(tk.END))
                        continue
                    
                except Exception as e:
                    self.root.after(0, lambda err=str(e): 
                        self.result_text.insert(tk.END, f"⚠️ 无法读取图片尺寸: {err}\n"))
                
                image_hash, cached_result = self.get_cached_ocr_result(image_path, 'general')
                if cached_result:
                    self.append_cached_ocr_result(image_path, cached_result)
                    continue

                result = ocr_image_general(image_path)
                
                if "words_result" in result:
                    formatted_lines = []
                    for item in result["words_result"]:
                        words = item["words"]
                        location = item.get("location", {})
                        top = location.get("top", 0)
                        left = location.get("left", 0)
                        height = location.get("height", 0)
                        formatted_lines.append(f"{words}|{top}|{left}|{height}")
                    
                    recognized_text = "\n".join(formatted_lines)
                    self.root.after(0, lambda t=recognized_text: 
                        self.result_text.insert(tk.END, t + "\n"))
                    
                    self.all_results.append({
                        'file': os.path.basename(image_path),
                        'path': image_path,
                        'lines': formatted_lines,
                        'count': len(formatted_lines),
                        'image_hash': image_hash
                    })
                    self.save_ocr_cache(image_hash, 'general', image_path, formatted_lines)
                    
                    self.root.after(0, lambda c=len(formatted_lines): 
                        self.result_text.insert(tk.END, f"\n✓ 识别成功：{c} 行文字\n"))
                else:
                    self.root.after(0, lambda r=result: 
                        self.result_text.insert(tk.END, f"✗ 识别失败：{r}\n"))
                    self.all_results.append({
                        'file': os.path.basename(image_path),
                        'path': image_path,
                        'lines': [],
                        'count': 0,
                        'error': str(result)
                    })
                
                self.root.after(0, lambda: self.result_text.see(tk.END))
                
                if idx < total:
                    import time
                    time.sleep(0.5)
            
            cached_count = sum(1 for r in self.all_results if r.get('cached') and r.get('count', 0) > 0)
            cached_lines = sum(r['count'] for r in self.all_results if r.get('cached'))
            success_count = sum(1 for r in self.all_results if r['count'] > 0)
            api_success_count = success_count - cached_count
            skipped_count = sum(1 for r in self.all_results if r.get('skipped', False))
            failed_count = sum(1 for r in self.all_results if r.get('error') and not r.get('skipped', False))
            total_lines = sum(r['count'] for r in self.all_results)
            api_lines = total_lines - cached_lines
            stats_success_count = success_count if self.stats_count_cache_as_success else api_success_count
            
            actual_processed = total - skipped_count
            if actual_processed > 0:
                self.record_ocr('general', stats_success_count, failed_count, total_lines,
                                cached_count=cached_count, cached_lines=cached_lines,
                                api_lines=api_lines, processed_count=actual_processed)
                # 添加到历史记录（在主线程中执行）
                results_copy = [r.copy() for r in self.all_results]
                self.root.after(0, lambda: self.add_to_history('通用识别', results_copy))
            
            self.root.after(0, lambda: self.progress_label.config(text=f"✓ 完成！共处理 {total} 个文件"))
            self.root.after(0, lambda: self.export_btn.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.copy_btn.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.add_zeros_btn.config(state=tk.NORMAL))
            self.root.after(0, self._update_ocr_btn_by_keys)
            self.root.after(0, lambda: self.select_btn.config(state=tk.NORMAL))
            
            status_msg = f"✓ 通用识别完成！总:{total} 成功:{success_count}"
            if cached_count > 0:
                status_msg += f" 缓存:{cached_count}"
            if skipped_count > 0:
                status_msg += f" 跳过:{skipped_count}"
            if failed_count > 0:
                status_msg += f" 失败:{failed_count}"
            status_msg += f" | 文字行数:{total_lines}"
            if skipped_count > 0:
                status_msg += " | 💡跳过的图片可用其他识别模式"
            
            self.root.after(0, lambda m=status_msg: self.progress_label.config(text=m))
        
        except Exception as e:
            self.root.after(0, lambda: self.result_text.insert(tk.END, f"\n发生错误：{str(e)}\n"))
            self.root.after(0, lambda: messagebox.showerror("错误", f"发生错误：{str(e)}"))
            self.root.after(0, lambda: self.progress_label.config(text="✗ 处理失败"))
            self.root.after(0, self._update_ocr_btn_by_keys)
            self.root.after(0, lambda: self.select_btn.config(state=tk.NORMAL))

    def perform_quick_ocr(self):
        """执行快速 OCR 识别"""
        if not self.image_paths:
            messagebox.showwarning("警告", "请先选择图片文件！")
            return
        
        if not API_KEY_BASIC or not SECRET_KEY_BASIC:
            messagebox.showerror("错误", "请先在 .env 文件中配置 API_KEY_BASIC 和 SECRET_KEY_BASIC！")
            return
        
        self.ocr_btn.config(state=tk.DISABLED)
        self.quick_ocr_btn.config(state=tk.DISABLED)
        self.general_ocr_btn.config(state=tk.DISABLED)
        self.select_btn.config(state=tk.DISABLED)
        
        thread = threading.Thread(target=self._perform_quick_ocr_thread, daemon=True)
        thread.start()
    
    def _perform_quick_ocr_thread(self):
        """快速OCR识别线程"""
        try:
            self.root.after(0, lambda: self.result_text.delete(1.0, tk.END))
            self.all_results = []
            
            total = len(self.image_paths)
            
            for idx, image_path in enumerate(self.image_paths, 1):
                self.root.after(0, lambda i=idx, p=image_path: 
                    self.progress_label.config(text=f"快速识别中: {i}/{total} - {os.path.basename(p)}"))
                
                self.root.after(0, lambda: self.result_text.insert(tk.END, f"\n{'='*80}\n"))
                self.root.after(0, lambda i=idx, p=image_path: 
                    self.result_text.insert(tk.END, f"文件 {i}/{total}: {os.path.basename(p)}\n"))
                self.root.after(0, lambda: self.result_text.insert(tk.END, f"{'='*80}\n"))
                
                try:
                    img = Image.open(image_path)
                    width, height = img.size
                    
                    self.root.after(0, lambda w=width, h=height: 
                        self.result_text.insert(tk.END, f"图片尺寸: 宽{w} x 高{h}\n"))
                    
                    # 检查是否符合快速识别要求
                    width_in_basic = self.size_limits["basic_min_width"] <= width <= self.size_limits["basic_max_width"]
                    height_in_basic = self.size_limits["basic_min_height"] <= height <= self.size_limits["basic_max_height"]
                    meets_basic = width_in_basic and height_in_basic
                    
                    if not meets_basic:
                        bas_w_range = f"{self.size_limits['basic_min_width']}~{self.size_limits['basic_max_width']}"
                        bas_h_range = f"{self.size_limits['basic_min_height']}~{self.size_limits['basic_max_height']}"
                        self.root.after(0, lambda w=width, h=height, wr=bas_w_range, hr=bas_h_range: 
                            self.result_text.insert(tk.END, 
                                f"⚠️ 跳过：图片尺寸不符合要求\n"
                                f"   当前尺寸: 宽{w} x 高{h}\n"
                                f"   要求：宽度({wr})且高度({hr})都要在范围内\n"
                                f"   建议使用「高精度识别」按钮\n"))
                        
                        self.all_results.append({
                            'file': os.path.basename(image_path),
                            'path': image_path,
                            'lines': [],
                            'count': 0,
                            'skipped': True,
                            'reason': f'图片尺寸不符合要求（宽{width} x 高{height}）'
                        })
                        
                        self.root.after(0, lambda: self.result_text.see(tk.END))
                        continue
                    
                except Exception as e:
                    self.root.after(0, lambda err=str(e): 
                        self.result_text.insert(tk.END, f"⚠️ 无法读取图片尺寸: {err}\n"))
                
                image_hash, cached_result = self.get_cached_ocr_result(image_path, 'basic')
                if cached_result:
                    self.append_cached_ocr_result(image_path, cached_result)
                    continue

                result = ocr_image_basic(image_path)
                
                if "words_result" in result:
                    text_only_lines = []
                    for item in result["words_result"]:
                        words = item["words"]
                        location = item.get("location", {})
                        top = location.get("top", 0)
                        left = location.get("left", 0)
                        height = location.get("height", 0)
                        text_only_lines.append(f"{words}|{top}|{left}|{height}")
                    
                    recognized_text = "\n".join(text_only_lines)
                    self.root.after(0, lambda t=recognized_text: 
                        self.result_text.insert(tk.END, t + "\n"))
                    
                    self.all_results.append({
                        'file': os.path.basename(image_path),
                        'path': image_path,
                        'lines': text_only_lines,
                        'count': len(text_only_lines),
                        'image_hash': image_hash
                    })
                    self.save_ocr_cache(image_hash, 'basic', image_path, text_only_lines)
                    
                    self.root.after(0, lambda c=len(text_only_lines): 
                        self.result_text.insert(tk.END, f"\n✓ 识别成功：{c} 行文字\n"))
                else:
                    self.root.after(0, lambda r=result: 
                        self.result_text.insert(tk.END, f"✗ 识别失败：{r}\n"))
                    self.all_results.append({
                        'file': os.path.basename(image_path),
                        'path': image_path,
                        'lines': [],
                        'count': 0,
                        'error': str(result)
                    })
                
                self.root.after(0, lambda: self.result_text.see(tk.END))
                
                if idx < total:
                    import time
                    time.sleep(0.5)
            
            cached_count = sum(1 for r in self.all_results if r.get('cached') and r.get('count', 0) > 0)
            cached_lines = sum(r['count'] for r in self.all_results if r.get('cached'))
            success_count = sum(1 for r in self.all_results if r['count'] > 0)
            api_success_count = success_count - cached_count
            skipped_count = sum(1 for r in self.all_results if r.get('skipped', False))
            failed_count = sum(1 for r in self.all_results if r.get('error') and not r.get('skipped', False))
            total_lines = sum(r['count'] for r in self.all_results)
            api_lines = total_lines - cached_lines
            stats_success_count = success_count if self.stats_count_cache_as_success else api_success_count
            
            actual_processed = total - skipped_count
            if actual_processed > 0:
                self.record_ocr('basic', stats_success_count, failed_count, total_lines,
                                cached_count=cached_count, cached_lines=cached_lines,
                                api_lines=api_lines, processed_count=actual_processed)
                # 添加到历史记录（在主线程中执行）
                results_copy = [r.copy() for r in self.all_results]
                self.root.after(0, lambda: self.add_to_history('快速识别', results_copy))
            
            self.root.after(0, lambda: self.progress_label.config(text=f"✓ 完成！共处理 {total} 个文件"))
            self.root.after(0, lambda: self.export_btn.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.copy_btn.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.add_zeros_btn.config(state=tk.NORMAL))
            self.root.after(0, self._update_ocr_btn_by_keys)
            self.root.after(0, lambda: self.select_btn.config(state=tk.NORMAL))
            
            status_msg = f"✓ 快速识别完成！总:{total} 成功:{success_count}"
            if cached_count > 0:
                status_msg += f" 缓存:{cached_count}"
            if skipped_count > 0:
                status_msg += f" 跳过:{skipped_count}"
            if failed_count > 0:
                status_msg += f" 失败:{failed_count}"
            status_msg += f" | 文字行数:{total_lines}"
            if skipped_count > 0:
                status_msg += " | 💡跳过的图片可用高精度识别"
            
            self.root.after(0, lambda m=status_msg: self.progress_label.config(text=m))
        
        except Exception as e:
            self.root.after(0, lambda: self.result_text.insert(tk.END, f"\n发生错误：{str(e)}\n"))
            self.root.after(0, lambda: messagebox.showerror("错误", f"发生错误：{str(e)}"))
            self.root.after(0, lambda: self.progress_label.config(text="✗ 处理失败"))
            self.root.after(0, self._update_ocr_btn_by_keys)
            self.root.after(0, lambda: self.select_btn.config(state=tk.NORMAL))
    
    def clear_result(self):
        """清空结果"""
        self.result_text.delete(1.0, tk.END)
        self.all_results = []
        self.progress_label.config(text="")
        self.export_btn.config(state=tk.DISABLED)
        self.copy_btn.config(state=tk.DISABLED)
        self.add_zeros_btn.config(state=tk.DISABLED)
    
    def copy_text(self):
        """复制识别的文字到剪贴板"""
        if not self.all_results:
            messagebox.showwarning("警告", "没有可复制的文字！")
            return
        
        try:
            all_lines = []
            for result in self.all_results:
                all_lines.extend(result['lines'])
            
            text_to_copy = "\n".join(all_lines)
            
            self.root.clipboard_clear()
            self.root.clipboard_append(text_to_copy)

            line_count = len(all_lines)
            char_count = len(text_to_copy)
            
            has_position = any('|' in line for line in all_lines)
            
            if has_position:
                format_info = "格式: 文字|top|left|height"
            else:
                format_info = "格式: 纯文字"
            
            self.progress_label.config(
                text=f"✓ 已复制到剪贴板！{format_info} | {line_count}行 {char_count}字符")
        
        except Exception as e:
            messagebox.showerror("错误", f"复制失败：{str(e)}")

    def copy_and_parse_text(self):
        """复制识别结果并直接解析到分类数据。"""
        if not self.all_results:
            messagebox.showwarning("警告", "没有可复制和解析的文字！")
            return

        try:
            all_lines = []
            for result in self.all_results:
                all_lines.extend(result['lines'])

            text_to_copy = "\n".join(all_lines)
            self.root.clipboard_clear()
            self.root.clipboard_append(text_to_copy)

            self.text_input.delete("1.0", tk.END)
            self.text_input.insert(tk.END, text_to_copy)
            self.load_from_text()

            self.progress_label.config(
                text=f"✓ 已复制并解析！{len(all_lines)}行 {len(text_to_copy)}字符")

        except Exception as e:
            messagebox.showerror("错误", f"复制并解析失败：{str(e)}")
    
    def add_zeros_to_lines(self):
        """在纯文字行后面添加|0|0（带位置信息的不改变）"""
        if not self.all_results:
            messagebox.showwarning("警告", "没有可处理的文字！")
            return
        
        try:
            # 统计处理的行数
            total_lines = 0
            modified_lines = 0
            skipped_lines = 0
            
            # 遍历所有结果
            for result in self.all_results:
                if result['lines']:
                    new_lines = []
                    for line in result['lines']:
                        total_lines += 1
                        # 如果行中已经有|符号，说明是带位置信息的格式，不改变
                        if '|' in line:
                            new_lines.append(line)
                            skipped_lines += 1
                        else:
                            # 纯文字，直接添加|0|0
                            new_line = f"{line}|0|0"
                            new_lines.append(new_line)
                            modified_lines += 1
                    
                    # 更新结果
                    result['lines'] = new_lines
            
            # 更新显示
            self.result_text.delete(1.0, tk.END)
            for result in self.all_results:
                self.result_text.insert(tk.END, f"\n{'='*80}\n")
                self.result_text.insert(tk.END, f"文件: {result['file']}\n")
                self.result_text.insert(tk.END, f"{'='*80}\n")
                
                if result['lines']:
                    for line in result['lines']:
                        self.result_text.insert(tk.END, line + "\n")
                    self.result_text.insert(tk.END, f"\n✓ 已处理：{len(result['lines'])} 行\n")
                else:
                    self.result_text.insert(tk.END, "无内容\n")
            
            # 显示处理结果
            if modified_lines > 0:
                self.progress_label.config(
                    text=f"✓ 已添加|0|0！处理 {modified_lines} 行，跳过 {skipped_lines} 行（已有位置信息）")
                
                messagebox.showinfo("处理完成", 
                    f"已在纯文字行后面添加|0|0\n\n"
                    f"总行数: {total_lines} 行\n"
                    f"已处理: {modified_lines} 行（纯文字）\n"
                    f"已跳过: {skipped_lines} 行（带位置信息）")
            else:
                self.progress_label.config(
                    text=f"✓ 无需处理！所有 {total_lines} 行都已有位置信息")
                
                messagebox.showinfo("无需处理", 
                    f"所有行都已包含位置信息，无需添加|0|0\n\n"
                    f"总行数: {total_lines} 行")
        
        except Exception as e:
            messagebox.showerror("错误", f"处理失败：{str(e)}")
    
    def show_context_menu(self, event):
        """显示右键菜单"""
        try:
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()
    
    def copy_selected(self):
        """复制选中的文字"""
        try:
            selected_text = self.result_text.get(tk.SEL_FIRST, tk.SEL_LAST)
            if selected_text:
                self.root.clipboard_clear()
                self.root.clipboard_append(selected_text)
                self.root.update()
                self.progress_label.config(text=f"✓ 已复制 {len(selected_text)} 个字符")
        except tk.TclError:
            messagebox.showwarning("提示", "请先选中要复制的文字！")
    
    def copy_all_text(self):
        """复制全部文字和位置信息"""
        try:
            all_lines = []
            for result in self.all_results:
                all_lines.extend(result['lines'])
            
            if all_lines:
                text_to_copy = "\n".join(all_lines)
                self.root.clipboard_clear()
                self.root.clipboard_append(text_to_copy)
                self.root.update()
                
                line_count = len(all_lines)
                self.progress_label.config(text=f"✓ 已复制 {line_count} 行文字和位置信息")
            else:
                messagebox.showwarning("提示", "没有可复制的文字！")
        except Exception as e:
            messagebox.showerror("错误", f"复制失败：{str(e)}")
    
    def select_all(self):
        """全选文字"""
        self.result_text.tag_add(tk.SEL, "1.0", tk.END)
        self.result_text.mark_set(tk.INSERT, "1.0")
        self.result_text.see(tk.INSERT)
    
    def load_window_config(self):
        """加载主窗口配置"""
        try:
            config = self.store.get('window_config', {})
            if config:
                width = config.get('width', 1300)
                height = config.get('height', 900)
                x = config.get('x', None)
                y = config.get('y', None)
                
                # 应用窗口尺寸和位置
                if x is not None and y is not None:
                    self.root.geometry(f"{width}x{height}+{x}+{y}")
                else:
                    self.root.geometry(f"{width}x{height}")
                
                print(f"✓ 已加载窗口配置：{width}x{height}")
            else:
                # 默认尺寸
                self.root.geometry("1300x900")
                print("✓ 使用默认窗口尺寸")
        except Exception as e:
            print(f"⚠️ 加载窗口配置失败: {e}")
            self.root.geometry("1300x900")
    
    def save_window_config(self):
        """保存主窗口配置"""
        try:
            # 获取当前窗口尺寸和位置
            geometry = self.root.geometry()
            # 格式：widthxheight+x+y
            parts = geometry.replace('+', 'x').replace('-', 'x').split('x')
            
            if len(parts) >= 2:
                config = {
                    'width': int(parts[0]),
                    'height': int(parts[1])
                }
                
                # 保存位置（如果有）
                if len(parts) >= 4:
                    config['x'] = int(parts[2])
                    config['y'] = int(parts[3])
                
                self.store.set('window_config', config)
                print(f"✓ 已保存窗口配置：{config['width']}x{config['height']}")
        except Exception as e:
            print(f"⚠️ 保存窗口配置失败: {e}")
    
    def load_popup_config(self, window_name):
        """加载弹出窗口配置"""
        try:
            all_configs = self.store.get('popup_windows', {})
            return all_configs.get(window_name, None)
        except Exception as e:
            print(f"⚠️ 加载弹出窗口配置失败: {e}")
            return None

    def center_window(self, window, width=None, height=None):
        """Center a Tk window on the current screen."""
        try:
            window.update_idletasks()
            if width is None or height is None:
                geometry_size = window.geometry().split("+", 1)[0]
                current_width, current_height = [int(v) for v in geometry_size.split("x")[:2]]
                width = width or current_width
                height = height or current_height

            screen_width = window.winfo_screenwidth()
            screen_height = window.winfo_screenheight()
            x = max(0, (screen_width - width) // 2)
            y = max(0, (screen_height - height) // 2)
            window.geometry(f"{width}x{height}+{x}+{y}")
        except Exception as e:
            print(f"Center window failed: {e}")
    
    def save_popup_config(self, window_name, window):
        """保存弹出窗口配置"""
        try:
            all_configs = self.store.get('popup_windows', {})
            
            # 获取窗口尺寸和位置
            geometry = window.geometry()
            parts = geometry.replace('+', 'x').replace('-', 'x').split('x')
            
            if len(parts) >= 2:
                config = {
                    'width': int(parts[0]),
                    'height': int(parts[1])
                }
                
                if len(parts) >= 4:
                    config['x'] = int(parts[2])
                    config['y'] = int(parts[3])
                
                # 更新配置
                all_configs[window_name] = config
                self.store.set('popup_windows', all_configs)
                
                print(f"✓ 已保存 {window_name} 窗口配置：{config['width']}x{config['height']}")
        except Exception as e:
            print(f"⚠️ 保存弹出窗口配置失败: {e}")
    
    def create_popup_window(self, parent, title, window_name, default_width=500, default_height=400, auto_fit=True):
        """创建带配置保存功能的弹出窗口"""
        popup = tk.Toplevel(parent)
        popup.withdraw()
        popup.title(title)
        popup.transient(parent)
        
        # 加载保存的配置
        config = self.load_popup_config(window_name)

        if config:
            width = config.get('width', default_width)
            height = config.get('height', default_height)
        else:
            width = default_width
            height = default_height

        # 始终居中显示，不使用保存的位置
        self.center_window(popup, width, height)
        
        # 设置最小尺寸
        popup.minsize(default_width, default_height)

        def fit_popup_to_content():
            """内容创建完成后自动放大窗口，避免默认尺寸裁掉按钮或底部内容。"""
            try:
                popup.update_idletasks()
                current = popup.geometry().split("+", 1)[0]
                current_width, current_height = [int(v) for v in current.split("x")[:2]]
                required_width = max(default_width, popup.winfo_reqwidth() + 24)
                required_height = max(default_height, popup.winfo_reqheight() + 24)

                screen_width = popup.winfo_screenwidth()
                screen_height = popup.winfo_screenheight()
                max_width = max(default_width, screen_width - 80)
                max_height = max(default_height, screen_height - 120)
                new_width = min(max(current_width, required_width), max_width)
                new_height = min(max(current_height, required_height), max_height)

                if new_width <= current_width and new_height <= current_height:
                    return

                self.center_window(popup, new_width, new_height)
            except Exception as e:
                print(f"⚠️ 自动调整弹窗尺寸失败: {e}")
        
        # 绑定关闭事件，保存配置
        def on_popup_close():
            self.save_popup_config(window_name, popup)
            popup.destroy()
        
        popup.protocol("WM_DELETE_WINDOW", on_popup_close)
        
        # 绑定窗口配置改变事件，实时保存配置
        def on_configure(event):
            # 只处理窗口本身的配置改变事件，忽略子控件的事件
            if event.widget == popup:
                # 延迟保存，避免频繁保存
                if hasattr(popup, '_save_timer'):
                    popup.after_cancel(popup._save_timer)
                popup._save_timer = popup.after(500, lambda: self.save_popup_config(window_name, popup))
        
        popup.bind('<Configure>', on_configure)

        def show_popup():
            if auto_fit:
                fit_popup_to_content()
            popup.deiconify()
            popup.lift()
            popup.grab_set()

        popup.after_idle(show_popup)

        return popup
    
    def on_closing(self):
        """窗口关闭时的处理"""
        try:
            self.save_window_config()
        except Exception as e:
            print(f"保存窗口配置失败: {e}")

        try:
            for after_id in self.root.tk.call('after', 'info'):
                self.root.after_cancel(after_id)
        except Exception:
            pass

        try:
            if _matplotlib_loaded and plt is not None:
                plt.close('all')
        except Exception:
            pass

        try:
            self.root.quit()
        except Exception:
            pass

        try:
            self.root.destroy()
        except Exception:
            pass
    
    def load_history_limit(self):
        """加载历史记录数量限制"""
        try:
            self.history_limit = self.store.get('history_limit', 100)
            print(f"✓ 历史记录限制：{self.history_limit} 条")
        except Exception as e:
            print(f"⚠️ 加载历史记录限制失败: {e}")
            self.history_limit = 100
    
    def save_history_limit(self):
        """保存历史记录数量限制"""
        try:
            self.store.set('history_limit', self.history_limit)
            print(f"✓ 已保存历史记录限制：{self.history_limit} 条")
        except Exception as e:
            print(f"⚠️ 保存历史记录限制失败: {e}")
    
    def load_history(self):
        """加载历史记录"""
        try:
            self.history_data = self.store.get('history', [])
            print(f"✓ 已加载历史记录：{len(self.history_data)} 条")
        except Exception as e:
            print(f"⚠️ 加载历史记录失败: {e}")
            self.history_data = []
    
    def save_history(self):
        """保存历史记录"""
        try:
            self.store.set('history', self.history_data)
            print(f"✓ 已保存历史记录：{len(self.history_data)} 条")
        except Exception as e:
            print(f"⚠️ 保存历史记录失败: {e}")
    
    def _increment_book_page_for_import(self):
        """导入图片时把"当前页"+1。"""
        if not hasattr(self, '_book_page_var'):
            return
        try:
            page_no = int(self._book_page_var.get())
        except (ValueError, TypeError):
            return
        next_page = page_no + 1
        self._suppress_book_page_trace = True
        try:
            self._book_page_var.set(str(next_page))
            self.store.set('book_page', next_page)
        finally:
            self._suppress_book_page_trace = False

    def _capture_history_book_page(self):
        """Remember the page number that belongs to the current import/recognition."""
        if not hasattr(self, '_book_page_var'):
            self._pending_history_book_page = None
            return
        try:
            self._pending_history_book_page = int(self._book_page_var.get())
        except (ValueError, TypeError):
            self._pending_history_book_page = None

    def add_to_history(self, ocr_type, results):
        """添加识别结果到历史记录"""
        try:
            print(f"📝 开始添加历史记录：{ocr_type}, 结果数量：{len(results)}")
            
            # 过滤掉跳过的结果
            valid_results = [r for r in results if r.get('count', 0) > 0 and not r.get('skipped', False)]
            
            if not valid_results:
                print("⚠️ 没有有效的识别结果，跳过保存历史记录")
                return

            # 读取当前书名和页码（以书籍信息面板的当前页为准）
            book_name = self._book_name_var.get().strip() if hasattr(self, '_book_name_var') else ''
            try:
                page_no = int(self._book_page_var.get()) if hasattr(self, '_book_page_var') else ''
            except (ValueError, TypeError):
                page_no = ''

            history_item = {
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'type': ocr_type,
                'book_name': book_name,
                'page_no': str(page_no) if page_no != '' else '',
                'file_count': len(valid_results),
                'total_lines': sum(r['count'] for r in valid_results),
                'files': []
            }
            
            # 添加文件信息（保存所有内容）
            for result in valid_results:
                file_info = {
                    'name': result['file'],
                    'lines': result['count'],
                    'content': result['lines']  # 保存所有行
                }
                history_item['files'].append(file_info)
                print(f"  - {result['file']}: {result['count']} 行")

            # 添加到历史记录列表开头
            self.history_data.insert(0, history_item)

            # 限制历史记录数量
            if len(self.history_data) > self.history_limit:
                self.history_data = self.history_data[:self.history_limit]

            # 保存到文件
            self.save_history()
            print(f"✓ 历史记录添加成功：{history_item['file_count']} 个文件，{history_item['total_lines']} 行")
        except Exception as e:
            print(f"⚠️ 添加历史记录失败: {e}")
            import traceback
            traceback.print_exc()
    
    def load_stats(self):
        """加载统计数据"""
        try:
            self.stats = self.store.get('stats', {})
            print(f"✓ 已加载统计数据：{len(self.stats)} 天的记录")
        except Exception as e:
            print(f"⚠️ 加载统计数据失败: {e}")
            self.stats = {}
    
    def load_size_limits(self):
        """加载尺寸限制配置"""
        try:
            saved_limits = self.store.get('size_limits', {})
            if saved_limits:
                self.size_limits.update(saved_limits)
                print(f"✓ 已加载尺寸限制配置: {saved_limits}")
            # 如果界已经创建，立即更新显示
            if hasattr(self, 'size_hint_label'):
                self.update_size_hint_display()
        except Exception as e:
            print(f"⚠️ 加载尺寸限制配置失败: {e}")
    
    def save_size_limits(self):
        """保存尺寸限制配置"""
        try:
            self.store.set('size_limits', self.size_limits)
            print(f"✓ 尺寸限制配置已保存")
            # 保存后立即更新界面显示
            self.update_size_hint_display()
        except Exception as e:
            print(f"⚠️ 保存尺寸限制配置失败: {e}")
    
    def load_font_config(self):
        """加载字号配置"""
        try:
            config = self.store.get('font_config', {})
            if config:
                self.current_font_size = config.get('font_size', 11)
            else:
                self.current_font_size = 11
            print(f"✓ 已加载字号配置: {self.current_font_size}")
        except Exception as e:
            print(f"⚠️ 加载字号配置失败: {e}")
            self.current_font_size = 11
    
    def save_font_config(self):
        """保存字号配置"""
        try:
            config = {'font_size': self.current_font_size}
            self.store.set('font_config', config)
            print(f"✓ 字号配置已保存: {self.current_font_size}")
        except Exception as e:
            print(f"⚠️ 保存字号配置失败: {e}")
    
    def load_space_config(self):
        """加载空格规则配置"""
        try:
            config = self.store.get('space_presets', {})
            if config:
                self.space_presets = config
                
                # 自动修复旧格式预设
                if "数字编号" in self.space_presets:
                    chars = self.space_presets["数字编号"].get("custom_chars", "")
                    if "一,号" in chars:
                        self.space_presets["数字编号"]["custom_chars"] = "一号|二号|三号|四号|五号|六号|七号|八号|九号|十号"
                        self.space_presets["数字编号"]["description"] = "数字编号中间加空格（一号→一 号）"
                        self.save_space_config()
                        print("✓ 已自动修复旧格式预设：数字编号")

                print(f"✓ 已加载空格规则配置: {len(self.space_presets)} 个预设")
            else:
                # 创建默认预设（只包含自定义字符预设）
                self.space_presets = {
                    "数字编号": {
                        "rules": [],
                        "custom_chars": "一号|二号|三号|四号|五号|六号|七号|八号|九号|十号",
                        "description": "数字编号中间加空格（一号→一 号）"
                    }
                }
                self.save_space_config()
                print("✓ 创建默认空格规则配置")
        except Exception as e:
            print(f"⚠️ 加载空格规则配置失败: {e}")
            self.space_presets = {}
    
    def save_space_config(self):
        """保存空格规则配置"""
        try:
            self.store.set('space_presets', self.space_presets)
            print(f"✓ 空格规则配置已保存: {len(self.space_presets)} 个预设")
        except Exception as e:
            print(f"⚠️ 保存空格规则配置失败: {e}")
    
    def load_font_style_config(self):
        """加载字体样式配置"""
        try:
            config = self.store.get('font_style_rules', {})
            if config:
                self.font_style_rules = config
                print(f"✓ 已加载字体样式配置: {len(self.font_style_rules)} 个规则")
            else:
                # 创建默认字体样式规则
                self.font_style_rules = {
                    "a": {
                        "font_family": "Arial",
                        "font_size": 12,
                        "font_weight": "bold",
                        "color": "#FF0000",
                        "description": "以'a'开头的项目使用红色粗体"
                    }
                }
                self.save_font_style_config()
                print("✓ 创建默认字体样式配置")
        except Exception as e:
            print(f"⚠️ 加载字体样式配置失败: {e}")
            self.font_style_rules = {}
    
    def save_font_style_config(self):
        """保存字体样式配置"""
        try:
            self.store.set('font_style_rules', self.font_style_rules)
            print(f"✓ 字体样式配置已保存: {len(self.font_style_rules)} 个规则")
        except Exception as e:
            print(f"⚠️ 保存字体样式配置失败: {e}")

    def load_filter_config(self):
        """加载过滤清理规则"""
        try:
            self.filter_rules = self.store.get('filter_rules', [])
            print(f"✓ 已加载过滤规则: {len(self.filter_rules)} 条")
        except Exception as e:
            print(f"⚠️ 加载过滤规则失败: {e}")
            self.filter_rules = []

    def save_filter_config(self):
        """保存过滤清理规则"""
        try:
            self.store.set('filter_rules', self.filter_rules)
            print(f"✓ 过滤规则已保存: {len(self.filter_rules)} 条")
        except Exception as e:
            print(f"⚠️ 保存过滤规则失败: {e}")

    def load_replace_config(self):
        """加载替换规则"""
        try:
            self.replace_rules = self.store.get('replace_rules', [])
            self.replace_rules = self._sort_replace_rules(self.replace_rules)
        except Exception as e:
            print(f"⚠️ 加载替换规则失败: {e}")
            self.replace_rules = []

    def _sort_replace_rules(self, rules):
        """按查找内容长度降序排列替换规则，避免短规则先替换长规则的一部分。"""
        return sorted(rules, key=lambda rule: len(str(rule.get('find', ''))), reverse=True)
    
    def load_report_config(self):
        """加载报告格式和分隔方式设置"""
        try:
            self.report_format = self.store.get('report_format', 'legacy')
            self.report_separator = self.store.get('report_separator', 'line')
            # 更新按钮显示
            if hasattr(self, 'report_format_btn'):
                if self.report_format == 'columns':
                    self.report_format_btn.config(text="格式: 三列")
                else:
                    self.report_format_btn.config(text="格式: 仅名称")
            if hasattr(self, 'separator_btn'):
                if self.report_separator == 'blank':
                    self.separator_btn.config(text="分隔: 空行")
                else:
                    self.separator_btn.config(text="分隔: ----")
        except Exception as e:
            print(f"⚠️ 加载报告设置失败: {e}")
            self.report_format = 'legacy'
            self.report_separator = 'line'
    
    def save_report_config(self):
        """保存报告格式和分隔方式设置"""
        try:
            self.store.set('report_format', self.report_format)
            self.store.set('report_separator', self.report_separator)
        except Exception as e:
            print(f"⚠️ 保存报告设置失败: {e}")

    def _run_replace_rules(self):
        """直接执行替换规则（作用于分类表格的 df）"""
        if self.df.empty:
            messagebox.showwarning("提示", "没有数据可以处理！")
            return
        if not self.replace_rules:
            messagebox.showinfo("提示", "还没有配置替换规则，请先点「⚙️ 替换设置」添加规则。")
            return
        self.push_undo_snapshot("替换")
        changed = self.apply_replace_rules()
        
        # 更新树视图中的条目，而不是完全刷新
        for iid in self.tree.get_children(""):
            if not self.is_tree_data_item(iid):
                continue
            vals = self.tree.item(iid, "values")
            if len(vals) > 3:
                idx = int(vals[3])
                if idx in self.df.index:
                    new_label = self.df.loc[idx, 'Label']
                    group = self._get_group_from_values(vals)
                    self.update_tree_item_in_place(iid, label_text=new_label, group_value=group)
        
        # 重新生成报告
        self.generate_report_from_tree()
        
        if changed:
            self.show_temp_message(f"✓ 替换完成：修改 {changed} 行")
        else:
            self.show_temp_message("✓ 没有匹配的内容")

    def _run_replace_rules_report(self):
        """对报告文本区域直接进行替换，在三列模式下只替换名称列"""
        if not self.replace_rules:
            messagebox.showinfo("提示", "还没有配置替换规则，请先点「⚙️ 替换设置」添加规则。")
            return
        
        # 保存当前状态到撤销栈
        self.push_undo_snapshot("报告替换")
        
        # 获取当前报告文本
        content = self.report_text.get("1.0", tk.END).rstrip("\n")
        lines = content.splitlines(keepends=True)
        separator = "----" if self.report_separator == 'line' else ""
        replace_rules = self._sort_replace_rules(self.replace_rules)

        changed_count = 0
        new_lines = []
        
        for line in lines:
            line_stripped = line.strip()
            
            # 检查是否是标题、分隔线等不需要替换的内容
            if not line_stripped:
                new_lines.append(line)
                continue
            if line_stripped.startswith("【") and line_stripped.endswith("】:"):
                new_lines.append(line)
                continue
            if separator and line_stripped == separator:
                new_lines.append(line)
                continue
            
            # 根据格式进行替换
            if self.report_format == 'columns':
                # 三列模式：报告由“分类\t名称\t组”生成，只替换名称列。
                parts = line.split("\t")
                if len(parts) < 3:
                    new_lines.append(line)
                    continue

                original_name = parts[1]
                name = original_name
                # 对名称列进行替换
                for rule in replace_rules:
                    find = rule.get('find', '')
                    replace = rule.get('replace', '')
                    if find:
                        name = name.replace(find, replace)
                
                if name != original_name:
                    changed_count += 1

                parts[1] = name
                new_lines.append("\t".join(parts))
            else:
                # 仅名称模式：直接替换整行
                original_line = line
                for rule in replace_rules:
                    find = rule.get('find', '')
                    replace = rule.get('replace', '')
                    if find:
                        line = line.replace(find, replace)
                if line != original_line:
                    changed_count += 1
                new_lines.append(line)
        
        # 更新报告文本
        yview = self.report_text.yview()
        self.report_text.delete("1.0", tk.END)
        self.report_text.insert("1.0", ''.join(new_lines))
        self.report_text.yview_moveto(yview[0])
        
        if changed_count > 0:
            self.show_temp_message(f"✓ 报告替换完成：修改 {changed_count} 处")
        else:
            self.show_temp_message("✓ 没有匹配的内容")

    def sync_report_to_data(self):
        """将文本报告区域的内容同步回数据源（df）和树视图"""
        if self.df.empty:
            messagebox.showinfo("提示", "没有数据可以同步")
            return
        
        # 保存当前状态到撤销栈
        self.push_undo_snapshot("同步报告到数据")
        
        content = self.report_text.get("1.0", tk.END)
        if not content.strip():
            self.show_temp_message("✓ 报告内容为空，没有同步")
            return
        
        # 从树视图获取所有数据项的顺序和信息
        tree_items = []
        for iid in self.tree.get_children(""):
            if not self.is_tree_data_item(iid):
                continue
            vals = self.tree.item(iid, "values")
            if len(vals) > 3:
                idx = int(vals[3])
                tree_items.append({
                    "iid": iid,
                    "idx": idx,
                    "label": vals[0],
                    "group": self._get_group_from_values(vals),
                    "category": vals[4] if len(vals) > 4 else None
                })
        
        # 解析报告内容
        lines = content.splitlines(keepends=True)
        separator = "----" if self.report_separator == 'line' else ""

        # 收集所有实际的名称行（排除标题、分隔线等）
        name_lines = []
        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                continue
            if line_stripped.startswith("【") and line_stripped.endswith("】:"):
                continue  # 跳过分类标题
            if separator and line_stripped == separator:
                continue  # 跳过分隔线
            
            if self.report_format == 'columns':
                # 三列模式：报告由“分类\t名称\t组”生成，只同步名称列。
                parts = line.split("\t")
                if len(parts) >= 3:
                    name_lines.append(parts[1].strip())
            else:
                # 仅名称模式：直接使用整行作为名称
                name_lines.append(line_stripped)
        
        # 将解析出的名称与树视图中的项目进行匹配更新
        updated = 0
        for i, tree_item in enumerate(tree_items):
            if i < len(name_lines):
                new_label = name_lines[i]
                # 更新数据源
                if tree_item["idx"] in self.df.index:
                    self.df.loc[tree_item["idx"], 'Label'] = new_label
                # 更新树视图
                self.update_tree_item_in_place(tree_item["iid"], label_text=new_label, group_value=tree_item["group"])
                updated += 1
        
        if updated > 0:
            self.show_temp_message(f"✓ 已同步 {updated} 个项目")
        else:
            self.show_temp_message("✓ 没有需要同步的更改")

    def save_replace_config(self):
        """保存替换规则"""
        try:
            self.replace_rules = self._sort_replace_rules(self.replace_rules)
            self.store.set('replace_rules', self.replace_rules)
        except Exception as e:
            print(f"⚠️ 保存替换规则失败: {e}")

    def apply_replace_rules(self, rules=None, silent=False):
        """执行替换规则，对所有条目生效，返回修改数量"""
        if self.df.empty:
            return 0
        rules = rules if rules is not None else self.replace_rules
        if not rules:
            return 0
        rules = self._sort_replace_rules(rules)

        # 确保 Label 列是字符串类型并保存 before 副本
        self.df['Label'] = self.df['Label'].astype(str)
        before = self.df['Label'].copy()
        for rule in rules:
            find = rule.get('find', '')
            replace = rule.get('replace', '')
            if not find:
                continue
            self.df['Label'] = self.df['Label'].str.replace(find, replace, regex=False)

        changed = int((self.df['Label'] != before).sum())
        return changed

    def show_replace_settings(self):
        """显示替换规则设置窗口"""
        win = self.create_popup_window(self.root, "替换规则", "replace_settings", 560, 500)
        win.configure(bg="#F8FAFC")

        # 标题栏
        header = tk.Frame(win, bg="#F97316", height=48)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text="🔄  替换规则", bg="#F97316", fg="white",
                 font=("Microsoft YaHei", 12, "bold")).pack(side=tk.LEFT, padx=16, pady=10)

        local_rules = [dict(r) for r in self._sort_replace_rules(self.replace_rules)]

        # 规则列表区
        list_frame = tk.Frame(win, bg="#F8FAFC")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=(12, 0))

        # 列标题
        hdr = tk.Frame(list_frame, bg="#E2E8F0")
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text="查找内容", bg="#E2E8F0", fg="#374151",
                 font=("Microsoft YaHei", 9, "bold"), width=20, anchor="w").pack(side=tk.LEFT, padx=8, pady=4)
        tk.Label(hdr, text="替换为（空=删除）", bg="#E2E8F0", fg="#374151",
                 font=("Microsoft YaHei", 9, "bold"), width=20, anchor="w").pack(side=tk.LEFT, padx=8, pady=4)

        # 滚动区
        scroll_frame = tk.Frame(list_frame, bg="#F8FAFC")
        scroll_frame.pack(fill=tk.BOTH, expand=True)
        sb = ttk.Scrollbar(scroll_frame, orient=tk.VERTICAL)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        canvas = tk.Canvas(scroll_frame, bg="#F8FAFC", highlightthickness=0,
                           yscrollcommand=sb.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.config(command=canvas.yview)
        rows_frame = tk.Frame(canvas, bg="#F8FAFC")
        canvas_win = canvas.create_window((0, 0), window=rows_frame, anchor="nw")

        def on_configure(e):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfig(canvas_win, width=canvas.winfo_width())
        rows_frame.bind("<Configure>", on_configure)
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_win, width=e.width))

        row_widgets = []

        def add_row(find_val='', replace_val=''):
            row = tk.Frame(rows_frame, bg="#F8FAFC")
            row.pack(fill=tk.X, pady=2)
            find_ent = tk.Entry(row, font=("Microsoft YaHei", 10), width=18,
                                relief="flat", highlightthickness=1,
                                highlightbackground="#D1D5DB", highlightcolor="#F97316")
            find_ent.insert(0, find_val)
            find_ent.pack(side=tk.LEFT, padx=(0, 6), ipady=4)
            tk.Label(row, text="→", bg="#F8FAFC", fg="#9CA3AF",
                     font=("Microsoft YaHei", 11)).pack(side=tk.LEFT, padx=4)
            rep_ent = tk.Entry(row, font=("Microsoft YaHei", 10), width=18,
                               relief="flat", highlightthickness=1,
                               highlightbackground="#D1D5DB", highlightcolor="#F97316")
            rep_ent.insert(0, replace_val)
            rep_ent.pack(side=tk.LEFT, padx=(6, 8), ipady=4)
            del_btn = tk.Button(row, text="✕", bg="#FEE2E2", fg="#EF4444",
                                relief="flat", font=("Microsoft YaHei", 9),
                                padx=6, pady=2, cursor="hand2",
                                command=lambda r=row, w=(find_ent, rep_ent): _del_row(r, w))
            del_btn.pack(side=tk.LEFT)
            row_widgets.append((find_ent, rep_ent, row))

        def _del_row(row, widgets):
            row_widgets[:] = [(f, r, rw) for f, r, rw in row_widgets if rw is not row]
            row.destroy()

        for rule in local_rules:
            add_row(rule.get('find', ''), rule.get('replace', ''))

        # 底부 버튼
        btn_bar = tk.Frame(win, bg="#F1F5F9")
        btn_bar.pack(fill=tk.X, padx=16, pady=10)

        tk.Button(btn_bar, text="＋ 添加规则", command=lambda: add_row(),
                  bg="#F97316", fg="white", relief="flat",
                  font=("Microsoft YaHei", 9), padx=10, pady=5,
                  cursor="hand2").pack(side=tk.LEFT)

        def collect_rules():
            rules = []
            for find_ent, rep_ent, _ in row_widgets:
                f = find_ent.get()
                r = rep_ent.get()
                if f:
                    rules.append({'find': f, 'replace': r})
            return self._sort_replace_rules(rules)

        def save_and_apply():
            rules = collect_rules()
            self.replace_rules = rules
            self.save_replace_config()
            self.show_temp_message("✓ 替换规则已保存")
            win.destroy()
            self._run_replace_rules()

        def save_only():
            rules = collect_rules()
            self.replace_rules = rules
            self.save_replace_config()
            self.show_temp_message("✓ 替换规则已保存")

        tk.Button(btn_bar, text="应用", command=save_and_apply,
                  bg="#22C55E", fg="white", relief="flat",
                  font=("Microsoft YaHei", 9, "bold"), padx=10, pady=5,
                  cursor="hand2").pack(side=tk.RIGHT, padx=(6, 0))
        tk.Button(btn_bar, text="保存", command=save_only,
                  bg="#2563EB", fg="white", relief="flat",
                  font=("Microsoft YaHei", 9), padx=10, pady=5,
                  cursor="hand2").pack(side=tk.RIGHT, padx=(6, 0))
        tk.Button(btn_bar, text="取消", command=win.destroy,
                  bg="#E5E7EB", fg="#374151", relief="flat",
                  font=("Microsoft YaHei", 9), padx=10, pady=5,
                  cursor="hand2").pack(side=tk.RIGHT)

    def show_filter_settings(self):
        """显示过滤清理规则设置窗口"""
        self.show_space_settings()

    def apply_filter_rules(self):
        """应用过滤规则，从名称列中删除指定内容，清理后为空的行直接删除"""
        if self.df.empty or not self.filter_rules:
            messagebox.showinfo("提示", "没有数据或没有过滤规则")
            return

        before_labels = self.df['Label'].copy()
        for rule in self.filter_rules:
            self.df['Label'] = self.df['Label'].str.replace(re.escape(rule), '', regex=True)

        # 去掉首尾空格
        self.df['Label'] = self.df['Label'].str.strip()

        changed = (self.df['Label'] != before_labels).sum()

        if changed == 0:
            messagebox.showinfo("清理完成", "没有匹配的内容，无需修改")
            return

        # 清理后为空的行删掉
        empty_mask = self.df['Label'] == ''
        removed = empty_mask.sum()
        if removed > 0:
            self.df = self.df[~empty_mask].reset_index(drop=True)
            self.reorder_dataframe()

        self.category_list, self.marked_indices = [], set()
        self.refresh_all()
        self.show_temp_message(f"✓ 已修改 {changed} 行")
        msg = f"已从 {changed} 行中删除匹配内容"
        if removed > 0:
            msg += f"\n其中 {removed} 行内容清空后已自动删除"
        messagebox.showinfo("清理完成", msg)

    def _apply_filter_rules_silent(self):
        """静默执行过滤规则，返回 (changed, removed) 数量，不弹窗不刷新。"""
        if self.df.empty or not self.filter_rules:
            return 0, 0

        # 跳过已圈选的条目（LassoTag 非空且非NaN）
        if 'LassoTag' not in self.df.columns:
            self.df['LassoTag'] = ''
        self.df['LassoTag'] = self.df['LassoTag'].fillna('')
        mask_editable = self.df['LassoTag'] == ''

        before_labels = self.df['Label'].copy()

        for rule in self.filter_rules:
            self.df.loc[mask_editable, 'Label'] = self.df.loc[mask_editable, 'Label'].str.replace(re.escape(rule), '', regex=True)
        self.df.loc[mask_editable, 'Label'] = self.df.loc[mask_editable, 'Label'].str.strip()

        changed = int((self.df['Label'] != before_labels).sum())

        empty_mask = (self.df['Label'] == '') & mask_editable
        removed = int(empty_mask.sum())
        if removed > 0:
            self._shift_category_indices_after_delete(self.df.index[empty_mask].tolist())
            self.df = self.df[~empty_mask].reset_index(drop=True)
            self.reorder_dataframe()

        return changed, removed

    def _split_group_a_silent(self):
        """静默拆分所有 A 组且文字数 > 2 的项目，返回拆分数量，不弹窗不刷新。"""
        return self._split_group_a_preserve_tree_order()
    
    def get_system_fonts(self):
        """获取系统可用字体列表"""
        try:
            import tkinter.font as tkFont
            
            # 获取所有字体族
            font_families = list(tkFont.families())
            
            # 过滤和排序字体
            filtered_fonts = []
            
            # 优先显示常用中文字体
            priority_fonts = [
                "Microsoft YaHei", "微软雅黑",
                "SimHei", "黑体", 
                "SimSun", "宋体",
                "KaiTi", "楷体",
                "FangSong", "仿宋",
                "Arial", "Times New Roman", "Courier New",
                "Calibri", "Verdana", "Tahoma"
            ]
            
            # 先添加优先字体（如果系统中存在）
            for font in priority_fonts:
                if font in font_families:
                    filtered_fonts.append(font)
                    font_families.remove(font)
            
            # 添加分隔符
            if filtered_fonts and font_families:
                filtered_fonts.append("--- 其他字体 ---")
            
            # 添加剩余字体，按字母顺序排序
            remaining_fonts = sorted([f for f in font_families if not f.startswith('@')])  # 过滤掉@开头的字体
            filtered_fonts.extend(remaining_fonts)
            
            print(f"✓ 已加载 {len(filtered_fonts)} 个系统字体")
            return filtered_fonts
            
        except Exception as e:
            print(f"⚠️ 获取系统字体失败: {e}")
            # 如果获取失败，返回默认字体列表
            return ["Microsoft YaHei", "Arial", "SimHei", "Times New Roman", "Courier New"]
    
    def update_size_hint_display(self):
        """更新界面上的尺寸提示信息"""
        try:
            if hasattr(self, 'size_hint_label'):
                if self.size_limit_unlocked:
                    bas_range = f"{self.size_limits['basic_min_width']}~{self.size_limits['basic_max_width']}x{self.size_limits['basic_min_height']}~{self.size_limits['basic_max_height']}"
                    self.size_hint_label.config(text=f"💡 高精度(已解锁限制) | 快速({bas_range})")
                else:
                    acc_range = f"{self.size_limits['accurate_min_width']}~{self.size_limits['accurate_max_width']}x{self.size_limits['accurate_min_height']}~{self.size_limits['accurate_max_height']}"
                    bas_range = f"{self.size_limits['basic_min_width']}~{self.size_limits['basic_max_width']}x{self.size_limits['basic_min_height']}~{self.size_limits['basic_max_height']}"
                    self.size_hint_label.config(text=f"💡 高精度({acc_range}) | 快速({bas_range})")
        except Exception as e:
            print(f"⚠️ 更新界面提示信息失败: {e}")
    
    def show_size_settings(self):
        """显示尺寸设置窗口（需要解锁）"""
        # 检查是否已解锁
        if not self.size_limit_unlocked:
            messagebox.showwarning("需要解锁", 
                "尺寸设置需要先解锁！\n\n"
                "请点击「🔒 解锁限制」按钮并输入密码")
            return
        
        settings_window = self.create_popup_window(self.root, "图片尺寸限制设置", "size_limit_settings", 600, 700)
        
        tk.Label(settings_window, text="⚙️ 图片尺寸限制设置", 
                font=("Arial", 14, "bold")).pack(pady=15)
        
        tk.Label(settings_window, text="设置OCR识别的图片尺寸范围要求", 
                fg="gray").pack(pady=5)
        
        # 设置框架
        settings_frame = tk.Frame(settings_window)
        settings_frame.pack(pady=20, padx=30, fill=tk.BOTH, expand=True)
        
        # 高精度识别设置
        tk.Label(settings_frame, text="高精度识别范围（适合大图）：", 
                font=("Arial", 11, "bold")).grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=10)
        
        tk.Label(settings_frame, text="最小宽度 (px):").grid(row=1, column=0, sticky=tk.W, pady=5)
        acc_min_width_var = tk.StringVar(value=str(self.size_limits['accurate_min_width']))
        acc_min_width_entry = tk.Entry(settings_frame, textvariable=acc_min_width_var, width=15)
        acc_min_width_entry.grid(row=1, column=1, sticky=tk.W, pady=5, padx=10)
        
        tk.Label(settings_frame, text="最大宽度 (px):").grid(row=2, column=0, sticky=tk.W, pady=5)
        acc_max_width_var = tk.StringVar(value=str(self.size_limits['accurate_max_width']))
        acc_max_width_entry = tk.Entry(settings_frame, textvariable=acc_max_width_var, width=15)
        acc_max_width_entry.grid(row=2, column=1, sticky=tk.W, pady=5, padx=10)
        
        tk.Label(settings_frame, text="最小高度 (px):").grid(row=3, column=0, sticky=tk.W, pady=5)
        acc_min_height_var = tk.StringVar(value=str(self.size_limits['accurate_min_height']))
        acc_min_height_entry = tk.Entry(settings_frame, textvariable=acc_min_height_var, width=15)
        acc_min_height_entry.grid(row=3, column=1, sticky=tk.W, pady=5, padx=10)
        
        tk.Label(settings_frame, text="最大高度 (px):").grid(row=4, column=0, sticky=tk.W, pady=5)
        acc_max_height_var = tk.StringVar(value=str(self.size_limits['accurate_max_height']))
        acc_max_height_entry = tk.Entry(settings_frame, textvariable=acc_max_height_var, width=15)
        acc_max_height_entry.grid(row=4, column=1, sticky=tk.W, pady=5, padx=10)
        
        # 快速识别设置
        tk.Label(settings_frame, text="快速识别范围（适合小图）：", 
                font=("Arial", 11, "bold")).grid(row=5, column=0, columnspan=2, sticky=tk.W, pady=10)
        
        tk.Label(settings_frame, text="最小宽度 (px):").grid(row=6, column=0, sticky=tk.W, pady=5)
        bas_min_width_var = tk.StringVar(value=str(self.size_limits['basic_min_width']))
        bas_min_width_entry = tk.Entry(settings_frame, textvariable=bas_min_width_var, width=15)
        bas_min_width_entry.grid(row=6, column=1, sticky=tk.W, pady=5, padx=10)
        
        tk.Label(settings_frame, text="最大宽度 (px):").grid(row=7, column=0, sticky=tk.W, pady=5)
        bas_max_width_var = tk.StringVar(value=str(self.size_limits['basic_max_width']))
        bas_max_width_entry = tk.Entry(settings_frame, textvariable=bas_max_width_var, width=15)
        bas_max_width_entry.grid(row=7, column=1, sticky=tk.W, pady=5, padx=10)
        
        tk.Label(settings_frame, text="最小高度 (px):").grid(row=8, column=0, sticky=tk.W, pady=5)
        bas_min_height_var = tk.StringVar(value=str(self.size_limits['basic_min_height']))
        bas_min_height_entry = tk.Entry(settings_frame, textvariable=bas_min_height_var, width=15)
        bas_min_height_entry.grid(row=8, column=1, sticky=tk.W, pady=5, padx=10)
        
        tk.Label(settings_frame, text="最大高度 (px):").grid(row=9, column=0, sticky=tk.W, pady=5)
        bas_max_height_var = tk.StringVar(value=str(self.size_limits['basic_max_height']))
        bas_max_height_entry = tk.Entry(settings_frame, textvariable=bas_max_height_var, width=15)
        bas_max_height_entry.grid(row=9, column=1, sticky=tk.W, pady=5, padx=10)
        
        # 提示信息
        hint_text = "💡 提示：修改后将立即生效，并保存到配置文件\n范围格式：最小值 ≤ 图片尺寸 ≤ 最大值"
        tk.Label(settings_frame, text=hint_text, fg="blue", justify=tk.LEFT,
                font=("Arial", 9)).grid(row=10, column=0, columnspan=2, pady=15)
        
        def save_settings():
            try:
                # 验证输入
                acc_min_w = int(acc_min_width_var.get())
                acc_max_w = int(acc_max_width_var.get())
                acc_min_h = int(acc_min_height_var.get())
                acc_max_h = int(acc_max_height_var.get())
                bas_min_w = int(bas_min_width_var.get())
                bas_max_w = int(bas_max_width_var.get())
                bas_min_h = int(bas_min_height_var.get())
                bas_max_h = int(bas_max_height_var.get())
                
                # 验证范围合理性
                if acc_min_w < 0 or acc_max_w < 0 or acc_min_h < 0 or acc_max_h < 0:
                    messagebox.showerror("错误", "高精度识别尺寸不能为负数！")
                    return
                
                if bas_min_w < 0 or bas_max_w < 0 or bas_min_h < 0 or bas_max_h < 0:
                    messagebox.showerror("错误", "快速识别尺寸不能为负数！")
                    return
                
                if acc_min_w > acc_max_w or acc_min_h > acc_max_h:
                    messagebox.showerror("错误", "高精度识别：最小值不能大于最大值！")
                    return
                
                if bas_min_w > bas_max_w or bas_min_h > bas_max_h:
                    messagebox.showerror("错误", "快速识别：最小值不能大于最大值！")
                    return
                
                # 保存设置
                self.size_limits['accurate_min_width'] = acc_min_w
                self.size_limits['accurate_max_width'] = acc_max_w
                self.size_limits['accurate_min_height'] = acc_min_h
                self.size_limits['accurate_max_height'] = acc_max_h
                self.size_limits['basic_min_width'] = bas_min_w
                self.size_limits['basic_max_width'] = bas_max_w
                self.size_limits['basic_min_height'] = bas_min_h
                self.size_limits['basic_max_height'] = bas_max_h
                
                self.save_size_limits()
                # 同时保存统计口径设置
                self.stats_count_cache_as_success = bool(include_cache_var.get())
                self.save_stats_settings()
                
                # 更新提示信息
                if hasattr(self, 'size_hint_label'):
                    if self.size_limit_unlocked:
                        self.size_hint_label.config(text=f"💡 高精度(已解锁限制) | 快速({bas_min_w}~{bas_max_w}x{bas_min_h}~{bas_max_h})")
                    else:
                        self.size_hint_label.config(text=f"💡 高精度({acc_min_w}~{acc_max_w}x{acc_min_h}~{acc_max_h}) | 快速({bas_min_w}~{bas_max_w}x{bas_min_h}~{bas_max_h})")
                else:
                    # 兼容旧版本的更新方式
                    for widget in self.progress_frame.winfo_children():
                        if isinstance(widget, tk.Label) and "高精度" in widget.cget("text"):
                            if self.size_limit_unlocked:
                                widget.config(text=f"💡 高精度(已解锁限制) | 快速({bas_min_w}~{bas_max_w}x{bas_min_h}~{bas_max_h})")
                            else:
                                widget.config(text=f"💡 高精度({acc_min_w}~{acc_max_w}x{acc_min_h}~{acc_max_h}) | 快速({bas_min_w}~{bas_max_w}x{bas_min_h}~{bas_max_h})")
                
                # 保存窗口尺寸配置
                self.save_popup_config("size_limit_settings", settings_window)
                
                settings_window.destroy()
                messagebox.showinfo("成功", "尺寸限制设置已保存！")
                
                # 如果已选择文件，重新检查
                if self.image_paths:
                    if len(self.image_paths) == 1:
                        self.select_file_internal(self.image_paths[0])
                    else:
                        self.batch_select_files_internal(self.image_paths)
            
            except ValueError:
                messagebox.showerror("错误", "请输入有效的数字！")
        
        def reset_defaults():
            acc_min_width_var.set("3500")
            acc_max_width_var.set("15000")
            acc_min_height_var.set("4000")
            acc_max_height_var.set("15000")
            bas_min_width_var.set("0")
            bas_max_width_var.set("8100")
            bas_min_height_var.set("0")
            bas_max_height_var.set("3000")
        
        # 统计口径设置（整合）
        stats_frame = tk.LabelFrame(settings_window, text="统计口径设置", padx=15, pady=10)
        stats_frame.pack(fill=tk.X, padx=30, pady=(0, 10))
        include_cache_var = tk.BooleanVar(value=bool(self.stats_count_cache_as_success))
        tk.Checkbutton(stats_frame, text="缓存复用也计入成功统计",
                       variable=include_cache_var,
                       font=("Microsoft YaHei", 10)).pack(anchor=tk.W)
        tk.Label(stats_frame,
                 text='关闭：缓存只进入"缓存复用"列；开启：缓存同时计入成功列',
                 fg="gray", font=("Arial", 9), justify=tk.LEFT).pack(anchor=tk.W)

        # 按钮区
        btn_frame = tk.Frame(settings_window)
        btn_frame.pack(pady=15)
        
        tk.Button(btn_frame, text="保存", command=save_settings,
                 bg="#4CAF50", fg="white", padx=30, pady=8).pack(side=tk.LEFT, padx=5)
        
        tk.Button(btn_frame, text="恢复默认", command=reset_defaults,
                 bg="#FF9800", fg="white", padx=30, pady=8).pack(side=tk.LEFT, padx=5)
        
        tk.Button(btn_frame, text="取消", command=settings_window.destroy,
                 bg="#757575", fg="white", padx=30, pady=8).pack(side=tk.LEFT, padx=5)
    
    def save_stats(self):
        """保存统计数据"""
        try:
            self.store.set('stats', self.stats)
        except Exception as e:
            print(f"⚠️ 保存统计数据失败: {e}")
            messagebox.showerror("错误", f"统计数据保存失败：{e}")

    def save_stats_settings(self):
        """保存统计口径设置"""
        try:
            self.store.set('stats_count_cache_as_success', self.stats_count_cache_as_success)
        except Exception as e:
            print(f"⚠️ 保存统计设置失败: {e}")
            messagebox.showerror("错误", f"统计设置保存失败：{e}")

    def show_stats_settings(self):
        """显示统计口径设置"""
        win = self.create_popup_window(self.root, "统计设置", "stats_settings", 520, 300)

        tk.Label(win, text="📊 统计口径设置",
                 font=("Arial", 15, "bold")).pack(pady=(20, 10))

        include_cache_var = tk.BooleanVar(value=bool(self.stats_count_cache_as_success))

        option_frame = tk.LabelFrame(win, text="缓存复用", padx=18, pady=14)
        option_frame.pack(fill=tk.X, padx=28, pady=10)

        tk.Checkbutton(
            option_frame,
            text="缓存复用也计入成功统计",
            variable=include_cache_var,
            font=("Microsoft YaHei", 11)
        ).pack(anchor=tk.W)

        hint = (
            "关闭：缓存只进入“缓存复用”列，成功列表示实际接口识别成功。\n"
            "开启：缓存会同时计入成功列，适合按处理结果统计。\n"
            "此设置只影响之后新增的统计记录，不会重算已有统计。"
        )
        tk.Label(win, text=hint, fg="gray", justify=tk.LEFT,
                 font=("Microsoft YaHei", 9)).pack(fill=tk.X, padx=32, pady=(6, 12))

        btn_frame = tk.Frame(win)
        btn_frame.pack(pady=8)

        def save_settings():
            self.stats_count_cache_as_success = bool(include_cache_var.get())
            self.save_stats_settings()
            win.destroy()
            messagebox.showinfo("成功", "统计设置已保存！")

        tk.Button(btn_frame, text="保存", command=save_settings,
                  bg="#4CAF50", fg="white", padx=24, pady=7).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="取消", command=win.destroy,
                  bg="#757575", fg="white", padx=24, pady=7).pack(side=tk.LEFT, padx=5)
    
    def _empty_ocr_stats(self):
        return {
            'count': 0,
            'processed': 0,
            'success': 0,
            'failed': 0,
            'cached': 0,
            'lines': 0,
            'api_lines': 0,
            'cached_lines': 0
        }

    def _ensure_ocr_stats_fields(self, stats, include_skipped=False):
        defaults = self._empty_ocr_stats()
        if include_skipped:
            defaults['skipped'] = 0
        if 'cached' not in stats:
            stats['cached'] = 0
        if 'cached_lines' not in stats:
            stats['cached_lines'] = 0
        if 'processed' not in stats:
            stats['processed'] = stats.get('success', 0) + stats.get('failed', 0) + stats.get('cached', 0)
        if 'api_lines' not in stats:
            stats['api_lines'] = max(0, stats.get('lines', 0) - stats.get('cached_lines', 0))
        for key, value in defaults.items():
            stats.setdefault(key, value)
        return stats

    def _normalize_stats_for_display(self):
        for day_data in self.stats.values():
            self._ensure_ocr_stats_fields(day_data.setdefault('accurate', {}), include_skipped=True)
            self._ensure_ocr_stats_fields(day_data.setdefault('basic', {}))
            self._ensure_ocr_stats_fields(day_data.setdefault('general', {}))

    def record_ocr(self, ocr_type, success_count, failed_count, lines,
                   cached_count=0, cached_lines=0, api_lines=None, processed_count=None):
        """记录识别统计"""
        today = datetime.now().strftime("%Y-%m-%d")
        
        if today not in self.stats:
            self.stats[today] = {
                'accurate': {**self._empty_ocr_stats(), 'skipped': 0},
                'basic': self._empty_ocr_stats(),
                'general': self._empty_ocr_stats()
            }
        
        # 确保所有模式都存在
        if 'general' not in self.stats[today]:
            self.stats[today]['general'] = self._empty_ocr_stats()
        
        if 'accurate' not in self.stats[today]:
            self.stats[today]['accurate'] = {**self._empty_ocr_stats(), 'skipped': 0}
        
        if 'basic' not in self.stats[today]:
            self.stats[today]['basic'] = self._empty_ocr_stats()

        self._ensure_ocr_stats_fields(self.stats[today]['accurate'], include_skipped=True)
        self._ensure_ocr_stats_fields(self.stats[today]['basic'])
        self._ensure_ocr_stats_fields(self.stats[today]['general'])

        if api_lines is None:
            api_lines = lines - cached_lines
        if processed_count is None:
            processed_count = success_count + failed_count + cached_count
        
        self.stats[today][ocr_type]['count'] += 1
        self.stats[today][ocr_type]['processed'] += processed_count
        self.stats[today][ocr_type]['success'] += success_count
        self.stats[today][ocr_type]['failed'] += failed_count
        self.stats[today][ocr_type]['cached'] += cached_count
        self.stats[today][ocr_type]['lines'] += lines
        self.stats[today][ocr_type]['api_lines'] += api_lines
        self.stats[today][ocr_type]['cached_lines'] += cached_lines
        
        self.save_stats()

    
    def show_stats(self):
        """显示统计信息"""
        self._normalize_stats_for_display()
        stats_window = self.create_popup_window(self.root, "识别统计", "stats_window", 1100, 850)
        
        tk.Label(stats_window, text="📊 OCR 识别统计", 
                font=("Arial", 16, "bold")).pack(pady=15)
        
        # 创建选项卡
        from tkinter import ttk
        notebook = ttk.Notebook(stats_window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # 总计选项卡
        total_tab = tk.Frame(notebook)
        notebook.add(total_tab, text="📈 总计统计")
        
        # 按日统计选项卡
        daily_tab = tk.Frame(notebook)
        notebook.add(daily_tab, text="📅 按日统计")
        
        # 按月统计选项卡
        monthly_tab = tk.Frame(notebook)
        notebook.add(monthly_tab, text="📊 按月统计")
        
        # === 总计统计 ===
        self._show_total_stats(total_tab)
        
        # === 按日统计 ===
        self._show_daily_stats(daily_tab)
        
        # === 按月统计 ===
        self._show_monthly_stats(monthly_tab)
        
        # 按钮
        btn_frame = tk.Frame(stats_window)
        btn_frame.pack(pady=10)
        
        tk.Button(btn_frame, text="关闭", command=stats_window.destroy,
                 bg="#757575", fg="white", padx=20, pady=8).pack()
    
    def show_history(self):
        """显示历史记录"""
        history_window = self.create_popup_window(self.root, "识别历史记录", "history_window", 1200, 800)
        
        tk.Label(history_window, text="📜 OCR 识别历史记录", 
                font=("Arial", 16, "bold")).pack(pady=15)
        
        # 创建表格框架
        from tkinter import ttk

        search_frame = tk.Frame(history_window)
        search_frame.pack(fill=tk.X, padx=20, pady=(0, 8))
        search_inner = tk.Frame(search_frame)
        search_inner.pack(side=tk.RIGHT)
        tk.Label(search_inner, text="搜索：", font=("Microsoft YaHei", 10)).pack(side=tk.LEFT)
        search_var = tk.StringVar()
        search_entry = tk.Entry(search_inner, textvariable=search_var, font=("Microsoft YaHei", 10), width=28)
        search_entry.pack(side=tk.LEFT, padx=(6, 8), ipady=3)
        search_status_var = tk.StringVar()
        tk.Label(search_inner, textvariable=search_status_var, fg="gray", width=16, anchor="w",
                 font=("Microsoft YaHei", 9)).pack(side=tk.RIGHT, padx=(8, 0))
        tk.Button(search_inner, text="清空", command=lambda: search_var.set(""),
                 bg="#E5E7EB", fg="#374151", padx=12, pady=3).pack(side=tk.RIGHT)
        
        table_frame = tk.Frame(history_window)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # 创建滚动条
        scrollbar = tk.Scrollbar(table_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 创建表格
        columns = ("时间", "类型", "文件数", "总行数", "操作")
        # 使用自定义样式 History.Treeview，避免影响全局 Treeview 样式
        tree = ttk.Treeview(table_frame, columns=columns, show="headings", 
                            yscrollcommand=scrollbar.set, height=25, style="History.Treeview")
        
        # 设置列标题
        tree.heading("时间", text="识别时间")
        tree.heading("类型", text="识别类型")
        tree.heading("文件数", text="文件数")
        tree.heading("总行数", text="总行数")
        tree.heading("操作", text="操作")
        
        # 设置列宽度
        tree.column("时间", width=180, anchor=tk.CENTER)
        tree.column("类型", width=120, anchor=tk.CENTER)
        tree.column("文件数", width=100, anchor=tk.CENTER)
        tree.column("总行数", width=100, anchor=tk.CENTER)
        tree.column("操作", width=150, anchor=tk.CENTER)
        
        scrollbar.config(command=tree.yview)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 配置样式 (使用自定义样式名)
        style = ttk.Style()
        style.configure("History.Treeview", font=("Microsoft YaHei", 10), rowheight=30)
        style.configure("History.Treeview.Heading", font=("Microsoft YaHei", 11, "bold"))
        
        def history_item_matches(item, keyword):
            """按时间、类型、文件名和识别内容搜索历史记录。"""
            if not keyword:
                return True
            keyword = keyword.lower()
            searchable_parts = [
                str(item.get('timestamp', '')),
                str(item.get('type', '')),
                str(item.get('file_count', '')),
                str(item.get('total_lines', '')),
            ]
            for file_info in item.get('files', []):
                searchable_parts.append(str(file_info.get('name', '')))
                for line in file_info.get('content', []):
                    searchable_parts.append(str(line))
            return keyword in "\n".join(searchable_parts).lower()

        def refresh_history_tree(*args):
            keyword = search_var.get().strip()
            tree.delete(*tree.get_children())
            matched_count = 0
            for idx, item in enumerate(self.history_data):
                if not history_item_matches(item, keyword):
                    continue
                tag = f"item_{matched_count}"
                tree.insert("", tk.END,
                           iid=f"history_{idx}",
                           values=(item.get('timestamp', ''),
                                  item.get('type', ''),
                                  item.get('file_count', 0),
                                  item.get('total_lines', 0),
                                  "查看详情"),
                           tags=(tag,))
                if matched_count % 2 == 0:
                    tree.tag_configure(tag, background="#F5F5F5")
                matched_count += 1
            if keyword:
                search_status_var.set(f"找到 {matched_count}/{len(self.history_data)} 条")
            else:
                search_status_var.set("")
        
        # 双击查看详情
        def on_double_click(event):
            selection = tree.selection()
            if selection:
                try:
                    history_index = int(selection[0].replace("history_", ""))
                    self.show_history_detail(self.history_data[history_index])
                except (ValueError, IndexError):
                    pass
        
        tree.bind("<Double-1>", on_double_click)
        search_var.trace_add("write", refresh_history_tree)
        search_entry.bind("<Return>", lambda e: on_double_click(e))
        refresh_history_tree()
        
        # 按钮框架
        btn_frame = tk.Frame(history_window)
        btn_frame.pack(pady=10)
        
        def clear_history():
            if messagebox.askyesno("确认", "确定要清空所有历史记录吗？\n此操作不可恢复！"):
                self.history_data = []
                self.save_history()
                history_window.destroy()
                messagebox.showinfo("成功", "历史记录已清空")
        
        def copy_selected_text():
            """复制选定记录并解析到分类数据"""
            selection = tree.selection()
            if not selection:
                messagebox.showwarning("提示", "请先选择一条历史记录")
                return
            
            try:
                history_index = int(selection[0].replace("history_", ""))
                history_item = self.history_data[history_index]

                pure_content = []
                for file_info in history_item['files']:
                    for line in file_info['content']:
                        if line.strip():
                            pure_content.append(line.strip())
                
                final_text = "\n".join(pure_content)
                
                if final_text:
                    self.root.clipboard_clear()
                    self.root.clipboard_append(final_text)
                    # 解析到分类数据
                    self.text_input.delete("1.0", tk.END)
                    self.text_input.insert(tk.END, final_text)
                    self.load_from_text()
                    history_window.destroy()
                else:
                    messagebox.showwarning("提示", "该记录没有可复制的文字内容")
                    
            except Exception as e:
                messagebox.showerror("错误", f"复制失败：{str(e)}")
        
        def set_history_limit():
            """设置历史记录数量限制"""
            limit_window = self.create_popup_window(history_window, "历史记录数量设置", "history_limit_settings", 450, 300)
            
            tk.Label(limit_window, text="📝 历史记录数量设置", 
                    font=("Arial", 14, "bold")).pack(pady=20)
            
            tk.Label(limit_window, text=f"当前限制：{self.history_limit} 条", 
                    fg="blue", font=("Arial", 11)).pack(pady=10)
            
            tk.Label(limit_window, text="设置新的历史记录数量限制：", 
                    font=("Arial", 10)).pack(pady=10)
            
            # 输入框
            limit_var = tk.StringVar(value=str(self.history_limit))
            limit_entry = tk.Entry(limit_window, textvariable=limit_var, 
                                  font=("Arial", 12), width=15, justify=tk.CENTER)
            limit_entry.pack(pady=10)
            limit_entry.focus_set()
            
            # 快捷按钮
            quick_frame = tk.Frame(limit_window)
            quick_frame.pack(pady=10)
            
            tk.Label(quick_frame, text="快捷设置：", font=("Arial", 9)).pack(side=tk.LEFT, padx=5)
            
            for value in [50, 100, 200, 500, 1000]:
                tk.Button(quick_frame, text=str(value), 
                         command=lambda v=value: limit_var.set(str(v)),
                         bg="#2196F3", fg="white", padx=10, pady=3, 
                         font=("Arial", 9)).pack(side=tk.LEFT, padx=2)
            
            hint_text = "💡 提示：\n• 设置为0表示不限制\n• 超出限制的旧记录会被自动删除"
            tk.Label(limit_window, text=hint_text, fg="gray", 
                    font=("Arial", 9), justify=tk.LEFT).pack(pady=10)
            
            def save_limit():
                try:
                    new_limit = int(limit_var.get())
                    if new_limit < 0:
                        messagebox.showerror("错误", "数量不能为负数！")
                        return
                    
                    old_limit = self.history_limit
                    self.history_limit = new_limit
                    self.save_history_limit()
                    
                    # 如果新限制小于当前记录数，裁剪历史记录
                    if new_limit > 0 and len(self.history_data) > new_limit:
                        removed_count = len(self.history_data) - new_limit
                        self.history_data = self.history_data[:new_limit]
                        self.save_history()
                        messagebox.showinfo("成功", 
                            f"历史记录限制已更新！\n\n"
                            f"旧限制：{old_limit} 条\n"
                            f"新限制：{new_limit} 条\n"
                            f"已删除：{removed_count} 条旧记录")
                    else:
                        limit_text = "不限制" if new_limit == 0 else f"{new_limit} 条"
                        messagebox.showinfo("成功", 
                            f"历史记录限制已更新！\n\n"
                            f"旧限制：{old_limit} 条\n"
                            f"新限制：{limit_text}")
                    
                    limit_window.destroy()
                    history_window.destroy()
                    self.show_history()
                
                except ValueError:
                    messagebox.showerror("错误", "请输入有效的数字！")
            
            btn_frame2 = tk.Frame(limit_window)
            btn_frame2.pack(pady=15)
            
            tk.Button(btn_frame2, text="保存", command=save_limit,
                     bg="#4CAF50", fg="white", padx=25, pady=8).pack(side=tk.LEFT, padx=5)
            
            tk.Button(btn_frame2, text="取消", command=limit_window.destroy,
                     bg="#757575", fg="white", padx=25, pady=8).pack(side=tk.LEFT, padx=5)
            
            limit_entry.bind("<Return>", lambda e: save_limit())
        
        tk.Button(btn_frame, text="📋 复制解析", command=copy_selected_text,
                 bg="#4CAF50", fg="white", padx=20, pady=8).pack(side=tk.LEFT, padx=5)
        
        tk.Button(btn_frame, text="数量设置", command=set_history_limit,
                 bg="#2196F3", fg="white", padx=20, pady=8).pack(side=tk.LEFT, padx=5)
        
        tk.Button(btn_frame, text="清空历史", command=clear_history,
                 bg="#F44336", fg="white", padx=20, pady=8).pack(side=tk.LEFT, padx=5)
        
        tk.Button(btn_frame, text="关闭", command=history_window.destroy,
                 bg="#757575", fg="white", padx=20, pady=8).pack(side=tk.LEFT, padx=5)
        
        # 显示统计信息
        limit_text = "不限制" if self.history_limit == 0 else f"{self.history_limit} 条"
        info_text = f"共 {len(self.history_data)} 条历史记录 | 限制: {limit_text}"
        if self.history_data:
            total_files = sum(item['file_count'] for item in self.history_data)
            total_lines = sum(item['total_lines'] for item in self.history_data)
            info_text += f" | 总文件数: {total_files} | 总行数: {total_lines}"
        
        tk.Label(history_window, text=info_text, fg="gray", font=("Arial", 10)).pack(pady=5)
    
    def show_api_key_settings(self):
        """显示API密钥设置窗口"""
        settings_window = self.create_popup_window(self.root, "API密钥设置", "api_key_settings", 700, 700)
        
        tk.Label(settings_window, text="🔑 OCR 密钥设置", 
                font=("Arial", 14, "bold")).pack(pady=15)
        
        tk.Label(settings_window, text="修改后将自动保存到 .env 文件", 
                fg="gray", font=("Arial", 10)).pack(pady=5)
        
        # 设置框架
        settings_frame = tk.Frame(settings_window)
        settings_frame.pack(pady=20, padx=30, fill=tk.BOTH, expand=True)
        
        # 高精度识别密钥
        tk.Label(settings_frame, text="高精度识别密钥：", 
                font=("Arial", 11, "bold"), fg="#2196F3").grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=10)
        
        tk.Label(settings_frame, text="API Key:").grid(row=1, column=0, sticky=tk.W, pady=5)
        api_key_var = tk.StringVar(value=API_KEY)
        api_key_entry = tk.Entry(settings_frame, textvariable=api_key_var, width=50, font=("Arial", 10))
        api_key_entry.grid(row=1, column=1, sticky=tk.W, pady=5, padx=10)
        
        tk.Label(settings_frame, text="Secret Key:").grid(row=2, column=0, sticky=tk.W, pady=5)
        secret_key_var = tk.StringVar(value=SECRET_KEY)
        secret_key_entry = tk.Entry(settings_frame, textvariable=secret_key_var, width=50, font=("Arial", 10))
        secret_key_entry.grid(row=2, column=1, sticky=tk.W, pady=5, padx=10)
        
        # 分隔线
        tk.Frame(settings_frame, height=2, bg="gray").grid(row=3, column=0, columnspan=2, sticky=tk.EW, pady=15)
        
        # 快速识别密钥
        tk.Label(settings_frame, text="快速识别密钥", 
                font=("Arial", 11, "bold"), fg="#00BCD4").grid(row=4, column=0, columnspan=2, sticky=tk.W, pady=10)
        
        tk.Label(settings_frame, text="API Key:").grid(row=5, column=0, sticky=tk.W, pady=5)
        api_key_basic_var = tk.StringVar(value=API_KEY_BASIC)
        api_key_basic_entry = tk.Entry(settings_frame, textvariable=api_key_basic_var, width=50, font=("Arial", 10))
        api_key_basic_entry.grid(row=5, column=1, sticky=tk.W, pady=5, padx=10)
        
        tk.Label(settings_frame, text="Secret Key:").grid(row=6, column=0, sticky=tk.W, pady=5)
        secret_key_basic_var = tk.StringVar(value=SECRET_KEY_BASIC)
        secret_key_basic_entry = tk.Entry(settings_frame, textvariable=secret_key_basic_var, width=50, font=("Arial", 10))
        secret_key_basic_entry.grid(row=6, column=1, sticky=tk.W, pady=5, padx=10)
        
        # 分隔线
        tk.Frame(settings_frame, height=2, bg="gray").grid(row=7, column=0, columnspan=2, sticky=tk.EW, pady=15)
        
        # 通用识别密钥
        tk.Label(settings_frame, text="通用识别密钥", 
                font=("Arial", 11, "bold"), fg="#9C27B0").grid(row=8, column=0, columnspan=2, sticky=tk.W, pady=10)
        
        tk.Label(settings_frame, text="API Key:").grid(row=9, column=0, sticky=tk.W, pady=5)
        api_key_general_var = tk.StringVar(value=API_KEY_GENERAL)
        api_key_general_entry = tk.Entry(settings_frame, textvariable=api_key_general_var, width=50, font=("Arial", 10))
        api_key_general_entry.grid(row=9, column=1, sticky=tk.W, pady=5, padx=10)
        
        tk.Label(settings_frame, text="Secret Key:").grid(row=10, column=0, sticky=tk.W, pady=5)
        secret_key_general_var = tk.StringVar(value=SECRET_KEY_GENERAL)
        secret_key_general_entry = tk.Entry(settings_frame, textvariable=secret_key_general_var, width=50, font=("Arial", 10))
        secret_key_general_entry.grid(row=10, column=1, sticky=tk.W, pady=5, padx=10)
        
        # 提示信息
        hint_text = "💡 提示：\n• 高精度识别密钥为必填项\n• 快速/通用密钥为空时，对应按钮不可用\n• Key 和 Secret Key 必须成对填写\n 修改后立即生效，无需重启程序"
        tk.Label(settings_frame, text=hint_text, fg="blue", justify=tk.LEFT,
                font=("Arial", 9)).grid(row=11, column=0, columnspan=2, pady=15, sticky=tk.W)
        
        def save_api_keys():
            try:
                new_api_key = api_key_var.get().strip()
                new_secret_key = secret_key_var.get().strip()
                new_api_key_basic = api_key_basic_var.get().strip()
                new_secret_key_basic = secret_key_basic_var.get().strip()
                new_api_key_general = api_key_general_var.get().strip()
                new_secret_key_general = secret_key_general_var.get().strip()
                
                # 验证必填项
                if not new_api_key or not new_secret_key:
                    messagebox.showerror("错误", "高精度识别的API Key和Secret Key不能为空！")
                    return
                if bool(new_api_key_basic) != bool(new_secret_key_basic):
                    messagebox.showerror("错误", "快速识别的API Key和Secret Key必须同时填写，或同时留空！")
                    return
                if bool(new_api_key_general) != bool(new_secret_key_general):
                    messagebox.showerror("错误", "通用识别的API Key和Secret Key必须同时填写，或同时留空！")
                    return
                
                # 更新全局变量
                global API_KEY, SECRET_KEY, API_KEY_BASIC, SECRET_KEY_BASIC, API_KEY_GENERAL, SECRET_KEY_GENERAL
                API_KEY = new_api_key
                SECRET_KEY = new_secret_key
                API_KEY_BASIC = new_api_key_basic
                SECRET_KEY_BASIC = new_secret_key_basic
                API_KEY_GENERAL = new_api_key_general
                SECRET_KEY_GENERAL = new_secret_key_general
                
                # 保存到.env文件
                env_path = Path(__file__).parent / '.env'
                env_lines = []
                
                # 读取现有的.env文件（如果存在）
                existing_keys = set()
                if env_path.exists():
                    with open(env_path, 'r', encoding='utf-8') as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith('#') and '=' in line:
                                key = line.split('=', 1)[0].strip()
                                if key not in ['BAIDU_API_KEY', 'BAIDU_SECRET_KEY', 
                                             'BAIDU_API_KEY_BASIC', 'BAIDU_SECRET_KEY_BASIC',
                                             'BAIDU_API_KEY_GENERAL', 'BAIDU_SECRET_KEY_GENERAL']:
                                    env_lines.append(line)
                
                # 添加新的密钥
                env_lines.append(f"BAIDU_API_KEY={new_api_key}")
                env_lines.append(f"BAIDU_SECRET_KEY={new_secret_key}")
                
                if new_api_key_basic:
                    env_lines.append(f"BAIDU_API_KEY_BASIC={new_api_key_basic}")
                if new_secret_key_basic:
                    env_lines.append(f"BAIDU_SECRET_KEY_BASIC={new_secret_key_basic}")
                
                if new_api_key_general:
                    env_lines.append(f"BAIDU_API_KEY_GENERAL={new_api_key_general}")
                if new_secret_key_general:
                    env_lines.append(f"BAIDU_SECRET_KEY_GENERAL={new_secret_key_general}")
                
                # 写入文件
                with open(env_path, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(env_lines))
                
                settings_window.destroy()
                messagebox.showinfo("成功", 
                    "API密钥已保存！\n\n"
                    "密钥已更新并保存到 .env 文件\n"
                    "立即生效，无需重启程序")
                self._update_ocr_btn_by_keys()
            
            except Exception as e:
                messagebox.showerror("错误", f"保存失败：{str(e)}")
        
        # 按钮
        btn_frame = tk.Frame(settings_window)
        btn_frame.pack(pady=15)
        
        tk.Button(btn_frame, text="保存", command=save_api_keys,
                 bg="#4CAF50", fg="white", padx=30, pady=8, font=("Arial", 11)).pack(side=tk.LEFT, padx=5)
        
        tk.Button(btn_frame, text="取消", command=settings_window.destroy,
                 bg="#757575", fg="white", padx=30, pady=8, font=("Arial", 11)).pack(side=tk.LEFT, padx=5)
    
    def show_history_detail(self, history_item):
        """显示历史记录详情"""
        detail_window = self.create_popup_window(self.root, "历史记录详情", "history_detail", 900, 700)
        
        # 标题
        title_text = f"📄 {history_item['type']} - {history_item['timestamp']}"
        tk.Label(detail_window, text=title_text, 
                font=("Arial", 14, "bold")).pack(pady=15)
        
        # 信息
        info_text = f"文件数: {history_item['file_count']} | 总行数: {history_item['total_lines']}"
        tk.Label(detail_window, text=info_text, fg="gray").pack(pady=5)
        
        # 创建文本框显示内容（ScrolledText自带滚动条）
        text_widget = scrolledtext.ScrolledText(detail_window, width=100, height=30,
                                                font=("Microsoft YaHei", 10))
        text_widget.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # 显示内容
        for file_info in history_item['files']:
            text_widget.insert(tk.END, f"\n{'='*80}\n")
            text_widget.insert(tk.END, f"文件: {file_info['name']}\n")
            text_widget.insert(tk.END, f"行数: {file_info['lines']}\n")
            text_widget.insert(tk.END, f"{'='*80}\n\n")
            
            for line in file_info['content']:
                text_widget.insert(tk.END, line + "\n")
            
            if file_info['lines'] > len(file_info['content']):
                text_widget.insert(tk.END, f"\n... (还有 {file_info['lines'] - len(file_info['content'])} 行未显示)\n")
        
        text_widget.config(state=tk.DISABLED)
        
        # 按钮
        btn_frame = tk.Frame(detail_window)
        btn_frame.pack(pady=10)
        

        
        def copy_all_content():
            """复制完整内容（包括文件信息和分隔线）"""
            try:
                all_text = text_widget.get(1.0, tk.END)
                self.root.clipboard_clear()
                self.root.clipboard_append(all_text)
                messagebox.showinfo("成功", "完整内容已复制到剪贴板")
            except Exception as e:
                messagebox.showerror("错误", f"复制失败：{str(e)}")
        
        def export_history_item():
            """导出历史记录到文件"""
            filepath = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")],
                initialfile=f"历史记录_{history_item['timestamp'].replace(':', '-').replace(' ', '_')}.txt"
            )
            
            if filepath:
                try:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(f"识别时间: {history_item['timestamp']}\n")
                        f.write(f"识别类型: {history_item['type']}\n")
                        f.write(f"文件数量: {history_item['file_count']}\n")
                        f.write(f"总行数: {history_item['total_lines']}\n")
                        f.write("="*80 + "\n\n")
                        
                        for file_info in history_item['files']:
                            f.write("="*80 + "\n")
                            f.write(f"文件: {file_info['name']}\n")
                            f.write(f"行数: {file_info['lines']}\n")
                            f.write("="*80 + "\n\n")
                            
                            for line in file_info['content']:
                                f.write(line + "\n")
                            f.write("\n")
                    
                    messagebox.showinfo("成功", f"已导出到：{os.path.basename(filepath)}")
                except Exception as e:
                    messagebox.showerror("错误", f"导出失败：{str(e)}")
        

        tk.Button(btn_frame, text="📄 复制全部", command=copy_all_content,
                 bg="#607D8B", fg="white", padx=15, pady=8,
                 font=("Arial", 10)).pack(side=tk.LEFT, padx=3)
        
        tk.Button(btn_frame, text="导出文件", command=export_history_item,
                 bg="#4CAF50", fg="white", padx=20, pady=8).pack(side=tk.LEFT, padx=5)
        
        tk.Button(btn_frame, text="关闭", command=detail_window.destroy,
                 bg="#757575", fg="white", padx=20, pady=8).pack(side=tk.LEFT, padx=5)
    
    def _show_total_stats(self, parent):
        """显示总计统计"""
        # 计算总计
        totals = {
            'accurate': self._empty_ocr_stats(),
            'basic': self._empty_ocr_stats(),
            'general': self._empty_ocr_stats()
        }
        
        for day_data in self.stats.values():
            for mode in totals:
                mode_stats = day_data.get(mode, {})
                for key in totals[mode]:
                    totals[mode][key] += mode_stats.get(key, 0)
        
        total_days = len(self.stats)
        
        info_frame = tk.Frame(parent)
        info_frame.pack(fill=tk.BOTH, expand=True, padx=30, pady=20)
        
        # 计算日平均
        acc = totals['accurate']
        bas = totals['basic']
        gen = totals['general']
        total_all_count = sum(totals[mode]['count'] for mode in totals)
        total_all_processed = sum(totals[mode]['processed'] for mode in totals)
        total_all_success = sum(totals[mode]['success'] for mode in totals)
        total_all_cached = sum(totals[mode]['cached'] for mode in totals)
        total_all_lines = sum(totals[mode]['lines'] for mode in totals)
        success_label = "成功(含缓存)" if self.stats_count_cache_as_success else "接口成功"
        
        total_info = f"""
使用天数: {total_days} 天
当前口径: 缓存复用{'计入' if self.stats_count_cache_as_success else '不计入'}成功统计

【高精度识别】
  处理批次: {acc['count']} 次
  处理图片: {acc['processed']} 张
  {success_label}: {acc['success']} 张
  缓存复用: {acc['cached']} 张
  输出行数: {acc['lines']} 行
  日平均处理: {acc['processed'] / total_days if total_days > 0 else 0:.1f} 张/天

【快速识别】
  处理批次: {bas['count']} 次
  处理图片: {bas['processed']} 张
  {success_label}: {bas['success']} 张
  缓存复用: {bas['cached']} 张
  输出行数: {bas['lines']} 行
  日平均处理: {bas['processed'] / total_days if total_days > 0 else 0:.1f} 张/天

【通用识别】
  处理批次: {gen['count']} 次
  处理图片: {gen['processed']} 张
  {success_label}: {gen['success']} 张
  缓存复用: {gen['cached']} 张
  输出行数: {gen['lines']} 行
  日平均处理: {gen['processed'] / total_days if total_days > 0 else 0:.1f} 张/天

【总计】
  总处理批次: {total_all_count} 次
  总处理图片: {total_all_processed} 张
  总{success_label}: {total_all_success} 张
  总缓存复用: {total_all_cached} 张
  总输出行数: {total_all_lines} 行
  日平均处理: {total_all_processed / total_days if total_days > 0 else 0:.1f} 张/天
        """
        tk.Label(info_frame, text=total_info, font=("Arial", 11), 
                justify=tk.LEFT, anchor=tk.W).pack(fill=tk.BOTH, expand=True)
    
    def _show_daily_stats(self, parent):
        """显示按日统计（表格形式）"""
        from tkinter import ttk
        
        # 创建表格框架
        table_frame = tk.Frame(parent)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # 创建滚动条
        scrollbar = tk.Scrollbar(table_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 创建表格
        success_col = "成功(含缓存)" if self.stats_count_cache_as_success else "接口成功"
        columns = ("日期", "类型", "批次", "处理", success_col, "缓存复用", "失败", "行数")
        tree = ttk.Treeview(table_frame, columns=columns, show="headings", 
                           yscrollcommand=scrollbar.set, height=25, selectmode="extended")
        
        # 设置列标题
        tree.heading("日期", text="日期")
        tree.heading("类型", text="类型")
        tree.heading("批次", text="批次")
        tree.heading("处理", text="处理")
        tree.heading(success_col, text=success_col)
        tree.heading("缓存复用", text="缓存复用")
        tree.heading("失败", text="失败")
        tree.heading("行数", text="行数")
        
        # 设置列宽度和对齐方式
        tree.column("日期", width=150, anchor=tk.CENTER)
        tree.column("类型", width=100, anchor=tk.CENTER)
        tree.column("批次", width=70, anchor=tk.CENTER)
        tree.column("处理", width=70, anchor=tk.CENTER)
        tree.column(success_col, width=110 if self.stats_count_cache_as_success else 90, anchor=tk.CENTER)
        tree.column("缓存复用", width=90, anchor=tk.CENTER)
        tree.column("失败", width=70, anchor=tk.CENTER)
        tree.column("行数", width=80, anchor=tk.CENTER)
        
        # 配置滚动条
        scrollbar.config(command=tree.yview)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 配置表格样式
        style = ttk.Style()
        style.configure("Treeview", font=("Microsoft YaHei", self.current_font_size), rowheight=max(int(self.current_font_size * 2.2), self.current_font_size + 10))
        style.configure("Treeview.Heading", font=("Microsoft YaHei", 11, "bold"))

        control_frame = tk.Frame(parent)
        control_frame.pack(fill=tk.X, padx=20, pady=(0, 10))
        tk.Label(control_frame, text="指定日期：", font=("Microsoft YaHei", 10)).pack(side=tk.LEFT)
        delete_date_var = tk.StringVar()
        delete_date_entry = tk.Entry(control_frame, textvariable=delete_date_var,
                                     font=("Microsoft YaHei", 10), width=14)
        delete_date_entry.pack(side=tk.LEFT, padx=(4, 8), ipady=2)
        tk.Label(control_frame, text="多个日期可用逗号、空格或换行分隔", fg="gray",
                 font=("Microsoft YaHei", 9)).pack(side=tk.LEFT, padx=(0, 12))

        def parse_stats_dates(text):
            return [part for part in re.split(r"[\s,，;；]+", text.strip()) if part]

        def get_selected_stats_dates():
            selection = tree.selection()
            if not selection:
                return []
            selected_dates = []
            item_id = selection[0]
            for item_id in selection:
                selected_date = ""
                if item_id.startswith("daily|"):
                    selected_date = item_id.split("|", 2)[1]
                else:
                    values = tree.item(item_id).get('values', [])
                    selected_date = str(values[0]) if values and values[0] else ""
                if selected_date and selected_date not in selected_dates:
                    selected_dates.append(selected_date)
            return selected_dates

        def on_daily_select(event=None):
            selected_dates = get_selected_stats_dates()
            if selected_dates:
                delete_date_var.set(", ".join(selected_dates))

        def delete_stats_date():
            target_dates = parse_stats_dates(delete_date_var.get())
            if not target_dates:
                messagebox.showwarning("提示", "请先输入日期，或在表格中选中要删除的日期")
                return
            existing_dates = [date for date in target_dates if date in self.stats]
            missing_dates = [date for date in target_dates if date not in self.stats]
            if not existing_dates:
                messagebox.showwarning("提示", f"没有找到这些日期的统计记录：{', '.join(target_dates)}")
                return
            date_text = ", ".join(existing_dates)
            missing_text = f"\n\n未找到并跳过：{', '.join(missing_dates)}" if missing_dates else ""
            stats_window = parent.winfo_toplevel()
            if not self.verify_admin_password(
                parent_window=stats_window,
                title="删除统计记录",
                message=f"此操作将删除这些日期的识别统计：\n{date_text}\n请输入管理员密码："
            ):
                return
            if not messagebox.askyesno("确认删除",
                                       f"确定要删除这些日期的识别统计吗？\n{date_text}\n此操作不会删除识别历史记录。{missing_text}"):
                return
            for date in existing_dates:
                del self.stats[date]
            self.save_stats()
            stats_window.destroy()
            self.show_stats()
            messagebox.showinfo("成功", f"已删除 {len(existing_dates)} 个日期的识别统计")

        tk.Button(control_frame, text="删除指定日期统计", command=delete_stats_date,
                  bg="#F44336", fg="white", padx=14, pady=5).pack(side=tk.LEFT)
        tree.bind("<<TreeviewSelect>>", on_daily_select)
        
        # 插入数据
        sorted_dates = sorted(self.stats.keys(), reverse=True)
        
        for date in sorted_dates:
            day_data = self.stats[date]
            
            if 'accurate' in day_data:
                acc = day_data['accurate']
                bas = day_data.get('basic', {})
                gen = day_data.get('general', {})
                
                # 插入高精度数据
                tree.insert("", tk.END, iid=f"daily|{date}|accurate", values=(date, "高精度",
                                               acc.get('count', 0), 
                                               acc.get('processed', 0),
                                               acc.get('success', 0),
                                               acc.get('cached', 0),
                                               acc.get('failed', 0),
                                               acc.get('lines', 0)),
                           tags=("accurate",))
                
                # 插入快速识别数据
                tree.insert("", tk.END, iid=f"daily|{date}|basic", values=("", "快速",
                                               bas.get('count', 0), 
                                               bas.get('processed', 0),
                                               bas.get('success', 0),
                                               bas.get('cached', 0),
                                               bas.get('failed', 0),
                                               bas.get('lines', 0)),
                           tags=("basic",))
                
                # 插入通用识别数据
                tree.insert("", tk.END, iid=f"daily|{date}|general", values=("", "通用",
                                               gen.get('count', 0), 
                                               gen.get('processed', 0),
                                               gen.get('success', 0),
                                               gen.get('cached', 0),
                                               gen.get('failed', 0),
                                               gen.get('lines', 0)),
                           tags=("general",))
                
                # 插入日合计
                day_total_count = acc.get('count', 0) + bas.get('count', 0) + gen.get('count', 0)
                day_total_processed = acc.get('processed', 0) + bas.get('processed', 0) + gen.get('processed', 0)
                day_total_success = acc.get('success', 0) + bas.get('success', 0) + gen.get('success', 0)
                day_total_cached = acc.get('cached', 0) + bas.get('cached', 0) + gen.get('cached', 0)
                day_total_failed = acc.get('failed', 0) + bas.get('failed', 0) + gen.get('failed', 0)
                day_total_lines = acc.get('lines', 0) + bas.get('lines', 0) + gen.get('lines', 0)
                tree.insert("", tk.END, iid=f"daily|{date}|total", values=("", "日合计",
                                               day_total_count, 
                                               day_total_processed,
                                               day_total_success,
                                               day_total_cached,
                                               day_total_failed,
                                               day_total_lines),
                           tags=("total",))
        
        # 设置行颜色
        tree.tag_configure("accurate", background="#E3F2FD")
        tree.tag_configure("basic", background="#FFF3E0")
        tree.tag_configure("general", background="#F3E5F5")
        tree.tag_configure("total", background="#E8F5E9", font=("Microsoft YaHei", self.current_font_size, "bold"))
    
    def _show_monthly_stats(self, parent):
        """显示按月统计"""
        # 按月汇总数据
        monthly_data = {}
        
        for date, day_data in self.stats.items():
            if 'accurate' in day_data:
                month = date[:7]  # YYYY-MM
                
                if month not in monthly_data:
                    monthly_data[month] = {
                        'accurate': self._empty_ocr_stats(),
                        'basic': self._empty_ocr_stats(),
                        'general': self._empty_ocr_stats(),
                        'days': set()
                    }
                
                monthly_data[month]['days'].add(date)
                
                acc = day_data['accurate']
                bas = day_data.get('basic', {})
                gen = day_data.get('general', {})
                
                for key in self._empty_ocr_stats():
                    monthly_data[month]['accurate'][key] += acc.get(key, 0)
                    monthly_data[month]['basic'][key] += bas.get(key, 0)
                    monthly_data[month]['general'][key] += gen.get(key, 0)
        
        # 创建表格框架
        from tkinter import ttk
        
        table_frame = tk.Frame(parent)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # 创建滚动条
        scrollbar = tk.Scrollbar(table_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 创建表格
        success_col = "成功(含缓存)" if self.stats_count_cache_as_success else "接口成功"
        columns = ("月份", "天数", "类型", "批次", "处理", success_col, "缓存复用", "行数", "日均")
        tree = ttk.Treeview(table_frame, columns=columns, show="headings", 
                           yscrollcommand=scrollbar.set, height=25)
        
        # 设置列标题
        tree.heading("月份", text="月份")
        tree.heading("天数", text="天数")
        tree.heading("类型", text="类型")
        tree.heading("批次", text="批次")
        tree.heading("处理", text="处理")
        tree.heading(success_col, text=success_col)
        tree.heading("缓存复用", text="缓存复用")
        tree.heading("行数", text="行数")
        tree.heading("日均", text="日均")
        
        # 设置列宽度和对齐方式
        tree.column("月份", width=120, anchor=tk.CENTER)
        tree.column("天数", width=80, anchor=tk.CENTER)
        tree.column("类型", width=100, anchor=tk.CENTER)
        tree.column("批次", width=70, anchor=tk.CENTER)
        tree.column("处理", width=70, anchor=tk.CENTER)
        tree.column(success_col, width=110 if self.stats_count_cache_as_success else 90, anchor=tk.CENTER)
        tree.column("缓存复用", width=90, anchor=tk.CENTER)
        tree.column("行数", width=80, anchor=tk.CENTER)
        tree.column("日均", width=100, anchor=tk.CENTER)
        
        # 配置滚动条
        scrollbar.config(command=tree.yview)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 配置表格样式
        style = ttk.Style()
        style.configure("Treeview", font=("Microsoft YaHei", self.current_font_size), rowheight=max(int(self.current_font_size * 2.2), self.current_font_size + 10))
        style.configure("Treeview.Heading", font=("Microsoft YaHei", 11, "bold"))
        
        # 插入数据
        sorted_months = sorted(monthly_data.keys(), reverse=True)
        
        for month in sorted_months:
            data = monthly_data[month]
            acc = data['accurate']
            bas = data['basic']
            gen = data['general']
            days = len(data['days'])
            
            # 计算日平均
            avg_acc = acc['processed'] / days if days > 0 else 0
            avg_bas = bas['processed'] / days if days > 0 else 0
            avg_gen = gen['processed'] / days if days > 0 else 0
            
            # 插入高精度数据
            tree.insert("", tk.END, values=(month, days, "高精度", 
                                           acc['count'], acc['processed'], acc['success'],
                                           acc['cached'], acc['lines'],
                                           f"{avg_acc:.1f}"),
                       tags=("accurate",))
            
            # 插入快速识别数据
            tree.insert("", tk.END, values=("", "", "快速", 
                                           bas['count'], bas['processed'], bas['success'],
                                           bas['cached'], bas['lines'],
                                           f"{avg_bas:.1f}"),
                       tags=("basic",))

            # 插入通用识别数据
            tree.insert("", tk.END, values=("", "", "通用",
                                           gen['count'], gen['processed'], gen['success'],
                                           gen['cached'], gen['lines'],
                                           f"{avg_gen:.1f}"),
                       tags=("general",))
            
            # 插入月合计
            month_total_count = acc['count'] + bas['count'] + gen['count']
            month_total_processed = acc['processed'] + bas['processed'] + gen['processed']
            month_total_success = acc['success'] + bas['success'] + gen['success']
            month_total_cached = acc['cached'] + bas['cached'] + gen['cached']
            month_total_lines = acc['lines'] + bas['lines'] + gen['lines']
            avg_total = month_total_processed / days if days > 0 else 0
            tree.insert("", tk.END, values=("", "", "月合计", 
                                           month_total_count, month_total_processed,
                                           month_total_success, month_total_cached,
                                           month_total_lines,
                                           f"{avg_total:.1f}"),
                       tags=("total",))
        
        # 设置行颜色
        tree.tag_configure("accurate", background="#E3F2FD")
        tree.tag_configure("basic", background="#FFF3E0")
        tree.tag_configure("general", background="#F3E5F5")
        tree.tag_configure("total", background="#E8F5E9", font=("Microsoft YaHei", self.current_font_size, "bold"))
    
    def export_results(self):
        """导出识别结果"""
        if not self.all_results:
            messagebox.showwarning("警告", "没有可导出的结果！")
            return
        
        filepath = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("文本文件", "*.txt"), ("CSV文件", "*.csv"), ("所有文件", "*.*")]
        )
        
        if not filepath:
            return
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                for result in self.all_results:
                    f.write("="*80 + "\n")
                    f.write(f"文件: {result['file']}\n")
                    f.write(f"识别行数: {result['count']}\n")
                    f.write("="*80 + "\n\n")
                    
                    if result['count'] > 0:
                        for line in result['lines']:
                            f.write(line + "\n")
                    else:
                        f.write("识别失败\n")
                    
                    f.write("\n\n")
            
            self.progress_label.config(text=f"✓ 已导出到：{os.path.basename(filepath)}")
        
        except Exception as e:
            messagebox.showerror("错误", f"导出失败：{str(e)}")
    
    def merge_images(self):
        """拼接图片功能"""
        file_paths = filedialog.askopenfilenames(
            title="选择要拼接的图片（按住Ctrl多选）",
            filetypes=[("图片文件", "*.jpg *.jpeg *.png *.bmp"), ("所有文件", "*.*")]
        )
        
        if not file_paths:
            return  # 用户取消选择
        
        if len(file_paths) < 2:
            messagebox.showwarning("警告", "请至少选择2张图片！\n\n提示：按住Ctrl键可以多选图片")
            return
        
        try:
            # 加载所有图片
            images = []
            for path in file_paths:
                img = Image.open(path)
                images.append(img)
            
            preview_choice, merged_image, total_width, max_height = self._show_merged_image_preview(
                images, item_label="图片数量", item_action="选择"
            )

            if preview_choice == 'cancel':
                return
            
            # 保存到临时文件（用于识别）
            import tempfile
            temp_dir = tempfile.gettempdir()
            temp_path = os.path.join(temp_dir, "merged_temp.jpg")
            merged_image.save(temp_path, format='JPEG', quality=90)
            
            # 如果选择保存
            if preview_choice == 'save':
                save_path = filedialog.asksaveasfilename(
                    defaultextension=".jpg",
                    filetypes=[("JPEG图片", "*.jpg"), ("PNG图片", "*.png"), ("所有文件", "*.*")],
                    initialfile=f"merged_{len(images)}images_{total_width}x{max_height}.jpg"
                )
                
                if save_path:
                    # 保存到用户指定位置
                    if save_path.lower().endswith('.png'):
                        merged_image.save(save_path, format='PNG')
                    else:
                        merged_image.save(save_path, format='JPEG', quality=95)
                    
                    self.progress_label.config(
                        text=f"✓ 拼接图片已保存到：{os.path.basename(save_path)}")
                    
                    # 使用保存的文件进行识别
                    temp_path = save_path
            
            # 继续识别流程
            if preview_choice in ('save', 'no_save'):
                self.image_paths = [temp_path]
                self.file_label.config(
                    text=f"已选择: 拼接图片 ({len(images)}张) - {total_width}x{max_height}", 
                    fg="blue")
                
                # 检查尺寸并启用相应按钮（宽度和高度都在范围内）
                width_in_accurate = self.size_limits["accurate_min_width"] <= total_width <= self.size_limits["accurate_max_width"]
                height_in_accurate = self.size_limits["accurate_min_height"] <= max_height <= self.size_limits["accurate_max_height"]
                meets_accurate = width_in_accurate and height_in_accurate
                
                width_in_basic = self.size_limits["basic_min_width"] <= total_width <= self.size_limits["basic_max_width"]
                height_in_basic = self.size_limits["basic_min_height"] <= max_height <= self.size_limits["basic_max_height"]
                meets_basic = width_in_basic and height_in_basic
                
                if meets_accurate and self._has_ocr_key('accurate'):
                    self.ocr_btn.config(state=tk.NORMAL)
                else:
                    self.ocr_btn.config(state=tk.DISABLED)
                
                if meets_basic and self._has_ocr_key('basic'):
                    self.quick_ocr_btn.config(state=tk.NORMAL)
                else:
                    self.quick_ocr_btn.config(state=tk.DISABLED)
                
                self.progress_label.config(text="")
                
                # 选择识别方式
                if meets_accurate and meets_basic:
                    ocr_choice = messagebox.askyesno("选择识别方式",
                        f"是否使用高精度识别？\n\n"
                        f"「是」= 高精度识别\n"
                        f"「否」= 快速识别")
                    if ocr_choice:
                        self.root.after(500, self.perform_ocr)
                    else:
                        self.root.after(500, self.perform_quick_ocr)
                elif meets_accurate:
                    self.root.after(500, self.perform_ocr)
                elif meets_basic:
                    self.root.after(500, self.perform_quick_ocr)
                else:
                    messagebox.showwarning("警告", 
                        f"拼接后的图片尺寸不符合任何识别要求\n\n"
                        f"当前尺寸: {total_width}x{max_height}\n"
                        f"高精度要求: 宽≥{self.size_limits['accurate_min_width']} 且 高≥{self.size_limits['accurate_min_height']}\n"
                        f"快速识别要求: 宽<{self.size_limits['basic_max_width']} 且 高<{self.size_limits['basic_max_height']}")
        
        except Exception as e:
            messagebox.showerror("错误", f"拼接失败：{str(e)}")
    
    def start_screenshot_capture(self):
        """启动屏幕截图拼接功能：多次框选截图，从右到左拼接，Enter确认，预览后识别"""
        try:
            from PIL import ImageGrab
        except ImportError:
            messagebox.showerror("缺少依赖", "需要安装 Pillow 库\n请运行：pip install Pillow")
            return

        captured_shots = []  # 按截图顺序存储，拼接时从右到左

        def do_capture():
            """最小化主窗口，显示全屏透明截图界面"""
            self.root.iconify()
            self.root.update()
            import time
            time.sleep(0.3)  # 等待窗口最小化完成

            overlay = tk.Toplevel()
            overlay.attributes('-fullscreen', True)
            overlay.attributes('-alpha', 0.25)
            overlay.attributes('-topmost', True)
            overlay.configure(bg='black')
            overlay.title('截图模式')

            canvas = tk.Canvas(overlay, cursor='cross', bg='black',
                               highlightthickness=0)
            canvas.pack(fill=tk.BOTH, expand=True)

            # 状态提示：独立置顶窗口，不受 overlay 透明度影响
            hint_win = tk.Toplevel()
            hint_win.overrideredirect(True)
            hint_win.attributes('-topmost', True)
            hint_win.geometry('+10+10')
            count_label = tk.Label(hint_win,
                text=f'框选第 {len(captured_shots)+1} 张 | 空格=暂停移动 | Enter=完成 | Esc=取消',
                bg='#1976D2', fg='white',
                font=('Microsoft YaHei', 13, 'bold'),
                padx=12, pady=6)
            count_label.pack()

            start_x = start_y = 0
            rect_id = None
            _mid_drag = {'active': False, 'last_y': 0, 'last_x': 0}
            _paused = [False]

            def on_pause_toggle(e=None):
                """空格键：暂停/恢复截图覆盖层"""
                if not _paused[0]:
                    # 暂停：隐藏覆盖层，释放鼠标焦点
                    _paused[0] = True
                    overlay.attributes('-alpha', 0.0)
                    overlay.attributes('-topmost', False)
                    overlay.withdraw()
                    count_label.config(
                        text='⏸ 已暂停，自由操作中 | 再按空格继续截图',
                        bg='#E65100')
                else:
                    # 恢复：重新显示覆盖层
                    _paused[0] = False
                    overlay.deiconify()
                    overlay.attributes('-topmost', True)
                    overlay.attributes('-alpha', 0.25)
                    overlay.focus_force()
                    canvas.focus_set()
                    size_hint = ''
                    if captured_shots:
                        total_w = sum(s.width for s in captured_shots)
                        max_h = max(s.height for s in captured_shots)
                        size_hint = f'已截 {len(captured_shots)} 张 | 累计：{total_w}×{max_h} px | '
                    count_label.config(
                        text=f'{size_hint}空格=暂停 | Enter=完成 | Esc=取消',
                        bg='#1976D2')

            # 用全局键盘钩子监听空格，覆盖层隐藏时也能响应
            import keyboard as _kb
            _kb.add_hotkey('space', lambda: overlay.after(0, on_pause_toggle), suppress=False)

            def on_press(e):
                nonlocal start_x, start_y, rect_id
                start_x, start_y = e.x, e.y
                if rect_id:
                    canvas.delete(rect_id)
                rect_id = canvas.create_rectangle(start_x, start_y, start_x, start_y,
                                                  outline='#FF4444', width=2)

            def on_drag(e):
                if rect_id:
                    canvas.coords(rect_id, start_x, start_y, e.x, e.y)

            def on_release(e):
                nonlocal rect_id
                x1, y1 = min(start_x, e.x), min(start_y, e.y)
                x2, y2 = max(start_x, e.x), max(start_y, e.y)
                if x2 - x1 < 5 or y2 - y1 < 5:
                    return
                overlay.attributes('-alpha', 0.0)
                overlay.update()
                import time
                time.sleep(0.05)
                shot = ImageGrab.grab(bbox=(x1, y1, x2, y2))
                overlay.attributes('-alpha', 0.25)
                captured_shots.append(shot)
                # 计算累计拼接尺寸
                total_w = sum(s.width for s in captured_shots)
                max_h = max(s.height for s in captured_shots)
                acc_max_w = self.size_limits.get('accurate_max_width', 15000)
                acc_max_h = self.size_limits.get('accurate_max_height', 15000)
                size_hint = f'累计：{total_w}×{max_h} px'
                if total_w > acc_max_w or max_h > acc_max_h:
                    size_hint += ' ⚠️超出限制'
                # 更新提示
                count_label.config(
                    text=f'已截 {len(captured_shots)} 张 | {size_hint} | Enter=完成 | Esc=取消')
                if rect_id:
                    canvas.delete(rect_id)
                    rect_id = None

            def on_middle_press(e):
                """中键按下：记录起始位置，准备拖动滚动"""
                _mid_drag['active'] = True
                _mid_drag['last_y'] = e.y
                _mid_drag['last_x'] = e.x
                canvas.config(cursor='fleur')

            def on_middle_drag(e):
                """中键拖动：根据垂直位移滚动底层窗口"""
                if not _mid_drag['active']:
                    return
                import pyautogui
                dy = e.y - _mid_drag['last_y']
                dx = e.x - _mid_drag['last_x']
                # 每移动20px触发一次滚动
                if abs(dy) >= 20:
                    clicks = -int(dy / 20)  # 向下拖 → 向下滚（负数）
                    overlay.attributes('-alpha', 0.0)
                    overlay.update()
                    pyautogui.scroll(clicks, x=e.x_root, y=e.y_root)
                    overlay.attributes('-alpha', 0.25)
                    _mid_drag['last_y'] = e.y
                if abs(dx) >= 20:
                    overlay.attributes('-alpha', 0.0)
                    overlay.update()
                    pyautogui.hscroll(-int(dx / 20), x=e.x_root, y=e.y_root)
                    overlay.attributes('-alpha', 0.25)
                    _mid_drag['last_x'] = e.x

            def on_middle_release(e):
                """中键松开"""
                _mid_drag['active'] = False
                canvas.config(cursor='cross')
                overlay.focus_force()

            def on_enter(e):
                _kb.remove_hotkey('space')
                overlay.destroy()
                hint_win.destroy()
                self.root.deiconify()
                if captured_shots:
                    self.root.after(200, _preview_and_confirm)

            def on_escape(e):
                _kb.remove_hotkey('space')
                overlay.destroy()
                hint_win.destroy()
                self.root.deiconify()

            canvas.bind('<ButtonPress-1>', on_press)
            canvas.bind('<B1-Motion>', on_drag)
            canvas.bind('<ButtonRelease-1>', on_release)
            canvas.bind('<ButtonPress-2>', on_middle_press)
            canvas.bind('<B2-Motion>', on_middle_drag)
            canvas.bind('<ButtonRelease-2>', on_middle_release)
            canvas.bind('<space>', on_pause_toggle)
            overlay.bind('<Return>', on_enter)
            overlay.bind('<Escape>', on_escape)
            overlay.bind('<space>', on_pause_toggle)
            hint_win.bind('<space>', on_pause_toggle)
            canvas.focus_set()
            overlay.focus_force()

        def _preview_and_confirm():
            if not captured_shots:
                return

            # 从右到左拼接：反转顺序后横向拼接
            shots_rtl = list(reversed(captured_shots))
            total_w = sum(s.width for s in shots_rtl)
            max_h = max(s.height for s in shots_rtl)
            merged = Image.new('RGB', (total_w, max_h), (255, 255, 255))
            x_offset = 0
            for shot in shots_rtl:
                merged.paste(shot, (x_offset, 0))
                x_offset += shot.width

            # 尺寸检查提示
            w, h = merged.size
            warnings = []
            acc_max_w = self.size_limits.get('accurate_max_width', 15000)
            acc_max_h = self.size_limits.get('accurate_max_height', 15000)
            bas_max_w = self.size_limits.get('basic_max_width', 8100)
            bas_max_h = self.size_limits.get('basic_max_height', 3000)
            if w > acc_max_w or h > acc_max_h:
                warnings.append(f'⚠️ 超出高精度最大尺寸 ({acc_max_w}x{acc_max_h})')
            if w > bas_max_w or h > bas_max_h:
                warnings.append(f'⚠️ 超出快速识别最大尺寸 ({bas_max_w}x{bas_max_h})')

            # 预览窗口
            preview_win = tk.Toplevel(self.root)
            preview_win.title('预览拼接结果')
            preview_win.transient(self.root)
            preview_win.grab_set()

            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()
            pw, ph = min(900, sw - 80), min(600, sh - 120)
            preview_win.geometry(f'{pw}x{ph}+{(sw-pw)//2}+{(sh-ph)//2}')

            info_frame = tk.Frame(preview_win, bg='#F5F5F5')
            info_frame.pack(fill=tk.X, padx=10, pady=8)
            tk.Label(info_frame, text=f'拼接结果：{w}×{h} px，共 {len(captured_shots)} 张截图（从右到左）',
                     bg='#F5F5F5', font=('Microsoft YaHei', 10)).pack(side=tk.LEFT)

            if warnings:
                warn_frame = tk.Frame(preview_win, bg='#FFF3E0')
                warn_frame.pack(fill=tk.X, padx=10, pady=(0, 6))
                for msg in warnings:
                    tk.Label(warn_frame, text=msg, bg='#FFF3E0', fg='#E65100',
                             font=('Microsoft YaHei', 9)).pack(anchor=tk.W, padx=8, pady=2)

            # 图片预览
            img_frame = tk.Frame(preview_win)
            img_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
            canvas_p = tk.Canvas(img_frame, bg='#EEEEEE')
            sb_h = ttk.Scrollbar(img_frame, orient=tk.HORIZONTAL, command=canvas_p.xview)
            sb_v = ttk.Scrollbar(img_frame, orient=tk.VERTICAL, command=canvas_p.yview)
            canvas_p.configure(xscrollcommand=sb_h.set, yscrollcommand=sb_v.set)
            sb_h.pack(side=tk.BOTTOM, fill=tk.X)
            sb_v.pack(side=tk.RIGHT, fill=tk.Y)
            canvas_p.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

            # 缩放预览图
            scale = min(1.0, (pw - 40) / w, (ph - 160) / h)
            disp_w, disp_h = int(w * scale), int(h * scale)
            disp_img = merged.resize((disp_w, disp_h), Image.Resampling.LANCZOS)
            from PIL import ImageTk
            tk_img = ImageTk.PhotoImage(disp_img)
            canvas_p.create_image(0, 0, anchor=tk.NW, image=tk_img)
            canvas_p.image = tk_img
            canvas_p.configure(scrollregion=(0, 0, disp_w, disp_h))

            # 滚轮缩放
            _zoom = [scale]

            def _rescale(new_scale):
                new_scale = max(0.05, min(new_scale, 5.0))
                _zoom[0] = new_scale
                nw = int(w * new_scale)
                nh = int(h * new_scale)
                resized = merged.resize((nw, nh), Image.Resampling.LANCZOS)
                new_photo = ImageTk.PhotoImage(resized)
                canvas_p.itemconfig(canvas_p.find_all()[0], image=new_photo)
                canvas_p.image = new_photo
                canvas_p.configure(scrollregion=(0, 0, nw, nh))

            def _on_wheel(e):
                factor = 1.15 if e.delta > 0 else (1 / 1.15)
                _rescale(_zoom[0] * factor)

            canvas_p.bind('<MouseWheel>', _on_wheel)

            tk.Label(info_frame, text='  滚轮缩放',
                     bg='#F5F5F5', fg='#888', font=('Microsoft YaHei', 9)).pack(side=tk.RIGHT)

            # 按钮
            btn_frame = tk.Frame(preview_win)
            btn_frame.pack(fill=tk.X, padx=10, pady=8)

            def confirm_ocr():
                preview_win.destroy()
                # 保存到临时文件
                import tempfile
                tmp = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
                tmp.close()
                merged.save(tmp.name)
                self.image_paths = [tmp.name]
                self.all_results = []
                self.file_label.config(
                    text=f'截图拼接：{w}×{h} px，{len(captured_shots)} 张',
                    fg='#1E5A8A')
                # 截图直接识别，不受尺寸限制
                self.root.after(100, self._perform_screenshot_ocr)

            def retake():
                preview_win.destroy()
                captured_shots.clear()
                self.root.after(100, do_capture)

            tk.Button(btn_frame, text='✅ 确认识别', command=confirm_ocr,
                      bg='#4CAF50', fg='white', font=('Microsoft YaHei', 10, 'bold'),
                      padx=20, pady=6).pack(side=tk.LEFT, padx=5)
            tk.Button(btn_frame, text='� 保存截图片', command=lambda: save_merged(),
                      bg='#1976D2', fg='white', font=('Microsoft YaHei', 10),
                      padx=20, pady=6).pack(side=tk.LEFT, padx=5)
            tk.Button(btn_frame, text='🔄 重新截图', command=retake,
                      bg='#FF9800', fg='white', font=('Microsoft YaHei', 10),
                      padx=20, pady=6).pack(side=tk.LEFT, padx=5)
            tk.Button(btn_frame, text='取消', command=preview_win.destroy,
                      bg='#757575', fg='white', font=('Microsoft YaHei', 10),
                      padx=20, pady=6).pack(side=tk.LEFT, padx=5)

            def save_merged():
                path = filedialog.asksaveasfilename(
                    parent=preview_win,
                    defaultextension='.png',
                    filetypes=[('PNG 图片', '*.png'), ('JPEG 图片', '*.jpg'), ('所有文件', '*.*')],
                    title='保存拼接图片'
                )
                if path:
                    merged.save(path)
                    messagebox.showinfo('保存成功', f'图片已保存：\n{path}', parent=preview_win)

        do_capture()

    def crop_and_merge_direct(self):
        """直接从主界面调用裁剪并拼接功能"""
        file_paths = filedialog.askopenfilenames(
            title="选择要裁剪的图片（可多选）",
            filetypes=[("图片文件", "*.jpg *.jpeg *.png *.bmp"), ("所有文件", "*.*")]
        )
        
        if not file_paths:
            return
        
        self._open_crop_window(file_paths)
    
    def _open_crop_window(self, file_paths):
        """打开裁剪窗口"""
        crop_window = tk.Toplevel(self.root)
        crop_window.title("裁剪并拼接 - 框选区域")
        
        screen_width = crop_window.winfo_screenwidth()
        screen_height = crop_window.winfo_screenheight()
        
        window_width = int(screen_width * 0.9)
        window_height = int(screen_height * 0.9)
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        
        crop_window.geometry(f"{window_width}x{window_height}+{x}+{y}")
        crop_window.state('zoomed')
        
        try:
            images_data = []
            for path in file_paths:
                img = Image.open(path)
                images_data.append({
                    'path': path,
                    'name': os.path.basename(path),
                    'original': img,
                    'crop_areas': []
                })
            
            display_mode = ['dual' if len(images_data) >= 2 else 'single']
            current_image_index = [0]
            
            max_display_size = min(window_width - 100, window_height - 300)
            
            def get_display_image(img, is_dual_mode=False):
                max_width = (max_display_size // 2 - 20) if is_dual_mode else max_display_size
                max_height = max_display_size
                
                if img.width > max_width or img.height > max_height:
                    scale = min(max_width / img.width, max_height / img.height)
                    new_width = int(img.width * scale)
                    new_height = int(img.height * scale)
                    display_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                    return display_img, scale
                return img.copy(), 1.0
            
            current_rect = None
            start_x = start_y = 0
            zoom_level = [1.0]
            is_panning = [False]
            
            title_frame = tk.Frame(crop_window, bg="#FF9800")
            title_frame.pack(fill=tk.X)
            
            tk.Label(title_frame, text="✂️ 裁剪并拼接", font=("Arial", 14, "bold"),
                    bg="#FF9800", fg="white", pady=8).pack(side=tk.LEFT, padx=20)
            
            tk.Label(title_frame, text="💡 左键框选 | 右键删除 | 滚轮缩放 | 中键拖动 | Ctrl+0适合屏幕", 
                    font=("Arial", 10), bg="#FF9800", fg="white", pady=8).pack(side=tk.RIGHT, padx=20)
            
            nav_frame = tk.Frame(crop_window)
            nav_frame.pack(fill=tk.X, padx=20, pady=8)
            
            image_label = tk.Label(nav_frame, text="", font=("Arial", 11, "bold"), fg="blue")
            image_label.pack(side=tk.LEFT)
            
            canvas_frame = tk.Frame(crop_window)
            canvas_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
            
            h_scrollbar = tk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL)
            h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
            
            v_scrollbar = tk.Scrollbar(canvas_frame, orient=tk.VERTICAL)
            v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            
            canvas = tk.Canvas(canvas_frame, bg="gray", cursor="cross",
                             xscrollcommand=h_scrollbar.set,
                             yscrollcommand=v_scrollbar.set)
            canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            
            h_scrollbar.config(command=canvas.xview)
            v_scrollbar.config(command=canvas.yview)
            
            status_label = tk.Label(crop_window, text="", fg="blue", font=("Arial", 10))
            status_label.pack(pady=5)
            
            merge_info_frame = tk.Frame(crop_window, bg="#f0f0f0", relief=tk.RIDGE, bd=2)
            merge_info_frame.pack(fill=tk.X, padx=20, pady=5)
            
            merge_info_label = tk.Label(merge_info_frame, text="", bg="#f0f0f0", 
                                       font=("Arial", 10, "bold"), fg="#333")
            merge_info_label.pack(pady=8)
            
            def update_status():
                current_img = images_data[current_image_index[0]]
                total_areas = sum(len(img['crop_areas']) for img in images_data)
                
                total_width = 0
                max_height = 0
                
                for img_data in images_data:
                    for area in img_data['crop_areas']:
                        x1, y1, x2, y2 = area['coords']
                        width = x2 - x1
                        height = y2 - y1
                        total_width += width
                        max_height = max(max_height, height)
                
                status_text = f"当前图片已框选 {len(current_img['crop_areas'])} 个区域 | 总共 {total_areas} 个区域"
                status_label.config(text=status_text, fg="blue")
                
                if total_areas > 0:
                    remaining_width = 8100 - total_width
                    usage_percent = (total_width / 8100) * 100
                    
                    merge_text = f"📏 拼接尺寸: 宽 {total_width}px × 高 {max_height}px"
                    merge_text += f"  |  已用: {usage_percent:.1f}%"
                    
                    if total_width > self.size_limits["basic_max_width"]:
                        merge_text += f"  |  ❌ 超限 {total_width - 8100}px"
                        merge_info_label.config(text=merge_text, fg="red")
                        merge_info_frame.config(bg="#ffe0e0")
                        merge_info_label.config(bg="#ffe0e0")
                    elif total_width > 7000:
                        merge_text += f"  |  ⚠️ 剩余 {remaining_width}px"
                        merge_info_label.config(text=merge_text, fg="#ff6600")
                        merge_info_frame.config(bg="#fff3e0")
                        merge_info_label.config(bg="#fff3e0")
                    else:
                        merge_text += f"  |  ✓ 剩余 {remaining_width}px"
                        merge_info_label.config(text=merge_text, fg="green")
                        merge_info_frame.config(bg="#e8f5e9")
                        merge_info_label.config(bg="#e8f5e9")
                else:
                    merge_info_label.config(text="💡 请框选要拼接的区域（左键拖动框选，右键删除）", 
                                          fg="#666")
                    merge_info_frame.config(bg="#f0f0f0")
                    merge_info_label.config(bg="#f0f0f0")
            
            def display_current_image():
                """显示当前图片"""
                canvas.delete("all")
                from PIL import ImageTk
                
                if display_mode[0] == 'dual' and len(images_data) >= 2:
                    img1_data = images_data[0]
                    img2_data = images_data[1]
                    
                    base_img1, base_scale1 = get_display_image(img1_data['original'], is_dual_mode=True)
                    base_img2, base_scale2 = get_display_image(img2_data['original'], is_dual_mode=True)
                    
                    final_scale1 = base_scale1 * zoom_level[0]
                    final_scale2 = base_scale2 * zoom_level[0]
                    
                    final_width1 = int(img1_data['original'].width * final_scale1)
                    final_height1 = int(img1_data['original'].height * final_scale1)
                    final_width2 = int(img2_data['original'].width * final_scale2)
                    final_height2 = int(img2_data['original'].height * final_scale2)
                    
                    display_img1 = img1_data['original'].resize((final_width1, final_height1), Image.Resampling.LANCZOS)
                    display_img2 = img2_data['original'].resize((final_width2, final_height2), Image.Resampling.LANCZOS)
                    
                    gap = 20
                    total_width = final_width1 + gap + final_width2
                    total_height = max(final_height1, final_height2)
                    
                    canvas.config(scrollregion=(0, 0, total_width, total_height))
                    
                    photo1 = ImageTk.PhotoImage(display_img1)
                    canvas.photo1 = photo1
                    canvas.create_image(0, 0, anchor=tk.NW, image=photo1, tags="image1")
                    canvas.create_text(final_width1 // 2, 20, text=f"图1: {img1_data['name']}", 
                                     font=("Arial", 12, "bold"), fill="yellow", tags="label1")
                    
                    x_offset = final_width1 + gap
                    photo2 = ImageTk.PhotoImage(display_img2)
                    canvas.photo2 = photo2
                    canvas.create_image(x_offset, 0, anchor=tk.NW, image=photo2, tags="image2")
                    canvas.create_text(x_offset + final_width2 // 2, 20, text=f"图2: {img2_data['name']}", 
                                     font=("Arial", 12, "bold"), fill="yellow", tags="label2")
                    
                    canvas.image_info = [
                        {'x_offset': 0, 'scale': final_scale1, 'data': img1_data},
                        {'x_offset': x_offset, 'scale': final_scale2, 'data': img2_data}
                    ]
                    
                    area_counter = 1
                    for img_idx, img_info in enumerate(canvas.image_info):
                        img_data = img_info['data']
                        scale = img_info['scale']
                        x_off = img_info['x_offset']
                        
                        for area in img_data['crop_areas']:
                            orig_x1, orig_y1, orig_x2, orig_y2 = area['coords']
                            x1 = x_off + orig_x1 * scale
                            y1 = orig_y1 * scale
                            x2 = x_off + orig_x2 * scale
                            y2 = orig_y2 * scale
                            
                            rect_id = canvas.create_rectangle(x1, y1, x2, y2, outline="red", width=2, tags="rect")
                            text_id = canvas.create_text((x1+x2)/2, (y1+y2)/2, text=str(area_counter),
                                                        font=("Arial", 20, "bold"), fill="red", tags="text")
                            area['rect_id'] = rect_id
                            area['text_id'] = text_id
                            area['display_coords'] = (x1, y1, x2, y2)
                            area['image_index'] = img_idx
                            area_counter += 1
                    
                    zoom_percent = int(zoom_level[0] * 100)
                    image_label.config(text=f"双图模式: {img1_data['name']} + {img2_data['name']} | 缩放: {zoom_percent}%")
                
                else:
                    current_img = images_data[current_image_index[0]]
                    base_display_img, base_scale = get_display_image(current_img['original'], is_dual_mode=False)
                    
                    final_scale = base_scale * zoom_level[0]
                    final_width = int(current_img['original'].width * final_scale)
                    final_height = int(current_img['original'].height * final_scale)
                    
                    display_img = current_img['original'].resize((final_width, final_height), Image.Resampling.LANCZOS)
                    
                    photo = ImageTk.PhotoImage(display_img)
                    canvas.photo = photo
                    canvas.image_info = [{'x_offset': 0, 'scale': final_scale, 'data': current_img}]
                    
                    canvas.config(scrollregion=(0, 0, final_width, final_height))
                    canvas.create_image(0, 0, anchor=tk.NW, image=photo, tags="image")
                    
                    for i, area in enumerate(current_img['crop_areas']):
                        orig_x1, orig_y1, orig_x2, orig_y2 = area['coords']
                        x1 = orig_x1 * final_scale
                        y1 = orig_y1 * final_scale
                        x2 = orig_x2 * final_scale
                        y2 = orig_y2 * final_scale
                        
                        rect_id = canvas.create_rectangle(x1, y1, x2, y2, outline="red", width=2, tags="rect")
                        text_id = canvas.create_text((x1+x2)/2, (y1+y2)/2, text=str(i+1),
                                                    font=("Arial", 20, "bold"), fill="red", tags="text")
                        area['rect_id'] = rect_id
                        area['text_id'] = text_id
                        area['display_coords'] = (x1, y1, x2, y2)
                        area['image_index'] = 0
                    
                    zoom_percent = int(zoom_level[0] * 100)
                    image_label.config(text=f"图片 {current_image_index[0]+1}/{len(images_data)}: {current_img['name']} | 缩放: {zoom_percent}%")
                
                update_status()


            
            def on_mouse_down(event):
                nonlocal start_x, start_y, current_rect
                start_x = canvas.canvasx(event.x)
                start_y = canvas.canvasy(event.y)
                current_rect = canvas.create_rectangle(start_x, start_y, start_x, start_y,
                                                       outline="red", width=2)
            
            def on_mouse_move(event):
                if current_rect:
                    current_x = canvas.canvasx(event.x)
                    current_y = canvas.canvasy(event.y)
                    canvas.coords(current_rect, start_x, start_y, current_x, current_y)
            
            def on_mouse_up(event):
                nonlocal current_rect
                if current_rect:
                    x1, y1, x2, y2 = canvas.coords(current_rect)
                    
                    if abs(x2 - x1) > 10 and abs(y2 - y1) > 10:
                        center_x = (x1 + x2) / 2
                        target_img = None
                        target_img_info = None
                        
                        for img_info in canvas.image_info:
                            img_data = img_info['data']
                            x_off = img_info['x_offset']
                            scale = img_info['scale']
                            img_width = img_data['original'].width * scale
                            
                            if x_off <= center_x <= x_off + img_width:
                                target_img = img_data
                                target_img_info = img_info
                                break
                        
                        if target_img and target_img_info:
                            scale = target_img_info['scale']
                            x_off = target_img_info['x_offset']
                            
                            orig_x1 = int((min(x1, x2) - x_off) / scale)
                            orig_y1 = int(min(y1, y2) / scale)
                            orig_x2 = int((max(x1, x2) - x_off) / scale)
                            orig_y2 = int(max(y1, y2) / scale)
                            
                            orig_x1 = max(0, min(orig_x1, target_img['original'].width))
                            orig_y1 = max(0, min(orig_y1, target_img['original'].height))
                            orig_x2 = max(0, min(orig_x2, target_img['original'].width))
                            orig_y2 = max(0, min(orig_y2, target_img['original'].height))
                            
                            total_areas = sum(len(img['crop_areas']) for img in images_data)
                            
                            area = {
                                'rect_id': current_rect,
                                'coords': (orig_x1, orig_y1, orig_x2, orig_y2),
                                'display_coords': (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
                            }
                            target_img['crop_areas'].append(area)
                            
                            label_x = (x1 + x2) / 2
                            label_y = (y1 + y2) / 2
                            text_id = canvas.create_text(label_x, label_y, 
                                                         text=str(total_areas + 1),
                                                         font=("Arial", 20, "bold"), fill="red")
                            area['text_id'] = text_id
                            
                            update_status()
                        else:
                            canvas.delete(current_rect)
                    else:
                        canvas.delete(current_rect)
                    
                    current_rect = None
            
            def on_canvas_click(event):
                click_x = canvas.canvasx(event.x)
                click_y = canvas.canvasy(event.y)
                
                deleted = False
                
                if display_mode[0] == 'dual' and len(images_data) >= 2:
                    for img_data in images_data:
                        for i, area in enumerate(img_data['crop_areas']):
                            x1, y1, x2, y2 = area['display_coords']
                            if x1 <= click_x <= x2 and y1 <= click_y <= y2:
                                canvas.delete(area['rect_id'])
                                canvas.delete(area['text_id'])
                                img_data['crop_areas'].pop(i)
                                deleted = True
                                break
                        if deleted:
                            break
                else:
                    current_img = images_data[current_image_index[0]]
                    for i, area in enumerate(current_img['crop_areas']):
                        x1, y1, x2, y2 = area['display_coords']
                        if x1 <= click_x <= x2 and y1 <= click_y <= y2:
                            canvas.delete(area['rect_id'])
                            canvas.delete(area['text_id'])
                            current_img['crop_areas'].pop(i)
                            deleted = True
                            break
                
                if deleted:
                    display_current_image()
            
            def on_mouse_wheel(event):
                """鼠标滚轮缩放"""
                old_zoom = zoom_level[0]
                
                if event.delta > 0:
                    zoom_level[0] *= 1.15
                else:
                    zoom_level[0] /= 1.15
                
                zoom_level[0] = max(0.1, min(zoom_level[0], 10.0))
                
                display_current_image()
            
            def on_pan_start(event):
                """开始平移（中键拖动）"""
                canvas.config(cursor="fleur")
                canvas.scan_mark(event.x, event.y)
                is_panning[0] = True
            
            def on_pan_move(event):
                """平移中（中键拖动）"""
                if is_panning[0]:
                    canvas.scan_dragto(event.x, event.y, gain=1)
            
            def on_pan_end(event):
                """结束平移"""
                canvas.config(cursor="cross")
                is_panning[0] = False
            
            def prev_image():
                """上一张图片"""
                if current_image_index[0] > 0:
                    current_image_index[0] -= 1
                    zoom_level[0] = 1.0
                    display_current_image()
            
            def next_image():
                """下一张图片"""
                if current_image_index[0] < len(images_data) - 1:
                    current_image_index[0] += 1
                    zoom_level[0] = 1.0
                    display_current_image()
            
            def on_key_press(event):
                """键盘快捷键处理"""
                if event.keysym == 'r' or event.keysym == 'R':
                    zoom_level[0] = 1.0
                    display_current_image()
                elif event.keysym == 'Left':
                    prev_image()
                elif event.keysym == 'Right':
                    next_image()
                elif event.keysym == 'plus' or event.keysym == 'equal':
                    zoom_level[0] *= 1.2
                    zoom_level[0] = min(zoom_level[0], 10.0)
                    display_current_image()
                elif event.keysym == 'minus':
                    zoom_level[0] /= 1.2
                    zoom_level[0] = max(zoom_level[0], 0.1)
                    display_current_image()
                elif event.keysym == '0' and (event.state & 0x4):  # Ctrl+0
                    fit_screen()
            
            crop_window.bind("<Key>", on_key_press)
            canvas.focus_set()
            
            canvas.bind("<ButtonPress-1>", on_mouse_down)
            canvas.bind("<B1-Motion>", on_mouse_move)
            canvas.bind("<ButtonRelease-1>", on_mouse_up)
            canvas.bind("<Button-3>", on_canvas_click)
            canvas.bind("<MouseWheel>", on_mouse_wheel)
            canvas.bind("<ButtonPress-2>", on_pan_start)
            canvas.bind("<B2-Motion>", on_pan_move)
            canvas.bind("<ButtonRelease-2>", on_pan_end)
            
            display_current_image()
            
            def do_crop_and_merge():
                all_crop_areas = []
                for img_data in images_data:
                    if img_data['crop_areas']:
                        all_crop_areas.extend([
                            (img_data['original'], area['coords'], img_data['name']) 
                            for area in img_data['crop_areas']
                        ])
                
                if not all_crop_areas:
                    messagebox.showwarning("警告", "请至少框选一个区域！")
                    return
                
                try:
                    cropped_images = []
                    for i, (original_img, coords, img_name) in enumerate(all_crop_areas):
                        x1, y1, x2, y2 = coords
                        cropped = original_img.crop((x1, y1, x2, y2))
                        cropped_images.append(cropped)
                    
                    total_width = sum(img.width for img in cropped_images)
                    max_height = max(img.height for img in cropped_images)
                    
                    if total_width > self.size_limits["basic_max_width"]:
                        messagebox.showerror("图片尺寸超限",
                            f"拼接后的图片宽度超过限制！\n\n"
                            f"当前宽度: {total_width}px\n"
                            f"最大宽度: 8100px\n"
                            f"超出: {total_width - 8100}px")
                        return
                    
                    crop_window.destroy()

                    user_choice, merged, total_width, max_height = self._show_merged_image_preview(
                        cropped_images, item_label="区域数量", item_action="框选"
                    )
                    
                    if user_choice == 'cancel':
                        # 用户取消操作
                        return

                    import tempfile
                    temp_dir = tempfile.gettempdir()
                    temp_path = os.path.join(temp_dir, "cropped_merged_ocr.jpg")
                    merged.save(temp_path, format='JPEG', quality=90)
                    
                    # 如果选择保存
                    if user_choice == 'save':
                        save_path = filedialog.asksaveasfilename(
                            defaultextension=".jpg",
                            filetypes=[
                                ("JPEG图片", "*.jpg"),
                                ("PNG图片", "*.png"),
                                ("所有文件", "*.*")
                            ],
                            initialfile=f"merged_{len(cropped_images)}regions_w{total_width}xh{max_height}.jpg"
                        )
                        
                        if save_path:
                            # 保存图片
                            if save_path.lower().endswith('.png'):
                                merged.save(save_path, format='PNG')
                            else:
                                merged.save(save_path, format='JPEG', quality=95)
                            
                            self.progress_label.config(
                                text=f"✓ 拼接图片已保存到：{os.path.basename(save_path)}"
                            )
                        else:
                            # 用户取消了保存对话框，但仍然继续识别
                            pass
                    
                    # 继续识别流程
                    self.result_text.delete(1.0, tk.END)
                    self.result_text.insert(tk.END, f"✓ 已裁剪 {len(cropped_images)} 个区域并拼接\n")
                    self.result_text.insert(tk.END, f"✓ 拼接尺寸: 宽{total_width} x 高{max_height}\n")
                    if user_choice == 'save':
                        self.result_text.insert(tk.END, "="*80 + "\n")
                        self.result_text.insert(tk.END, f"✓ 图片已保存\n")
                    self.result_text.insert(tk.END, "正在识别拼接后的图片，请稍候...\n\n")
                    
                    self.image_paths = [temp_path]
                    self.file_label.config(
                        text=f"裁剪拼接图片 ({len(cropped_images)}个区域) - 宽{total_width} x 高{max_height}",
                        fg="blue"
                    )
                    
                    # 直接使用截图专用识别（不受尺寸限制）
                    self.root.after(100, self._perform_screenshot_ocr)
                
                except Exception as e:
                    messagebox.showerror("错误", f"裁剪拼接失败：{str(e)}")
            
            btn_frame = tk.Frame(crop_window)
            btn_frame.pack(pady=15)
            
            def zoom_in():
                zoom_level[0] *= 1.2
                zoom_level[0] = min(zoom_level[0], 10.0)
                display_current_image()
            
            def zoom_out():
                zoom_level[0] /= 1.2
                zoom_level[0] = max(zoom_level[0], 0.1)
                display_current_image()
            
            def zoom_reset():
                zoom_level[0] = 1.0
                display_current_image()
            
            def fit_screen():
                """适合屏幕 - 自动调整缩放以填充可视区域"""
                try:
                    # 获取canvas的可视区域大小
                    canvas_width = canvas.winfo_width()
                    canvas_height = canvas.winfo_height()
                    
                    if canvas_width <= 1 or canvas_height <= 1:
                        # 如果canvas还没有渲染，使用默认值
                        canvas_width = max_display_size
                        canvas_height = max_display_size
                    
                    if display_mode[0] == 'dual' and len(images_data) >= 2:
                        # 双图模式：计算两张图片的总宽度
                        img1 = images_data[0]['original']
                        img2 = images_data[1]['original']
                        
                        # 获取基础缩放
                        _, base_scale1 = get_display_image(img1, is_dual_mode=True)
                        _, base_scale2 = get_display_image(img2, is_dual_mode=True)
                        
                        # 计算总宽度（包括间隔）
                        total_width = img1.width * base_scale1 + 20 + img2.width * base_scale2
                        max_height = max(img1.height * base_scale1, img2.height * base_scale2)
                        
                        # 计算适合屏幕的缩放比例
                        scale_x = canvas_width / total_width
                        scale_y = canvas_height / max_height
                        fit_scale = min(scale_x, scale_y) * 0.95  # 留5%边距
                        
                        zoom_level[0] = fit_scale
                    else:
                        # 单图模式
                        current_img = images_data[current_image_index[0]]['original']
                        _, base_scale = get_display_image(current_img, is_dual_mode=False)
                        
                        # 计算适合屏幕的缩放比例
                        img_width = current_img.width * base_scale
                        img_height = current_img.height * base_scale
                        
                        scale_x = canvas_width / img_width
                        scale_y = canvas_height / img_height
                        fit_scale = min(scale_x, scale_y) * 0.95  # 留5%边距
                        
                        zoom_level[0] = fit_scale
                    
                    # 限制缩放范围
                    zoom_level[0] = max(0.1, min(zoom_level[0], 10.0))
                    
                    display_current_image()
                    
                    # 居中显示
                    canvas.update_idletasks()
                    canvas.xview_moveto(0)
                    canvas.yview_moveto(0)
                
                except Exception as e:
                    print(f"适合屏幕失败: {e}")
                    zoom_level[0] = 1.0
                    display_current_image()
            
            tk.Button(btn_frame, text="🔍+", command=zoom_in,
                     bg="#009688", fg="white", font=("Arial", 11),
                     padx=15, pady=10).pack(side=tk.LEFT, padx=3)
            
            tk.Button(btn_frame, text="🔍-", command=zoom_out,
                     bg="#009688", fg="white", font=("Arial", 11),
                     padx=15, pady=10).pack(side=tk.LEFT, padx=3)
            
            tk.Button(btn_frame, text="重置", command=zoom_reset,
                     bg="#009688", fg="white", font=("Arial", 11),
                     padx=15, pady=10).pack(side=tk.LEFT, padx=3)
            
            tk.Button(btn_frame, text="📐 适合屏幕", command=fit_screen,
                     bg="#009688", fg="white", font=("Arial", 11),
                     padx=15, pady=10).pack(side=tk.LEFT, padx=3)
            
            tk.Frame(btn_frame, width=2, bg="gray").pack(side=tk.LEFT, padx=10, fill=tk.Y)
            
            if len(images_data) > 1:
                tk.Button(btn_frame, text="◀ 上一张", command=prev_image,
                         bg="#2196F3", fg="white", font=("Arial", 11),
                         padx=20, pady=10).pack(side=tk.LEFT, padx=5)
                
                tk.Button(btn_frame, text="下一张 ▶", command=next_image,
                         bg="#2196F3", fg="white", font=("Arial", 11),
                         padx=20, pady=10).pack(side=tk.LEFT, padx=5)
                
                tk.Frame(btn_frame, width=2, bg="gray").pack(side=tk.LEFT, padx=10, fill=tk.Y)
            
            tk.Button(btn_frame, text="✓ 确认拼接", command=do_crop_and_merge,
                     bg="#4CAF50", fg="white", font=("Arial", 12, "bold"),
                     padx=40, pady=12).pack(side=tk.LEFT, padx=10)
            
            tk.Button(btn_frame, text="✗ 取消", command=crop_window.destroy,
                     bg="#757575", fg="white", font=("Arial", 12),
                     padx=40, pady=12).pack(side=tk.LEFT, padx=10)
        
        except Exception as e:
            messagebox.showerror("错误", f"加载图片失败：{str(e)}")
    
    def show_font_style_settings(self):
        """显示字体样式设置窗口"""
        win = self.create_popup_window(self.root, "字体样式设置", "font_style_settings", 1000, 840)
        win.configure(bg="#F8FAFC")
        win.minsize(980, 820)

        ui_font = ("Microsoft YaHei", 9)
        title_font = ("Microsoft YaHei", 15, "bold")
        label_font = ("Microsoft YaHei", 9, "bold")
        muted = "#64748B"
        border = "#DDE3EA"
        primary = "#2563EB"
        current_prefix = tk.StringVar(value="")

        style = ttk.Style(win)
        style.configure("FontRule.Treeview", font=("Microsoft YaHei", 9), rowheight=34, borderwidth=0)
        style.configure("FontRule.Treeview.Heading", font=("Microsoft YaHei", 9, "bold"))

        def button(parent, text, command, bg="#FFFFFF", fg="#111827", width=None):
            return tk.Button(parent, text=text, command=command, bg=bg, fg=fg,
                             activebackground=bg, activeforeground=fg,
                             relief=tk.FLAT, bd=0, padx=12, pady=7, width=width,
                             font=("Microsoft YaHei", 9), cursor="hand2")

        header = tk.Frame(win, bg="#F8FAFC")
        header.pack(fill=tk.X, padx=16, pady=(12, 8))
        icon = tk.Label(header, text="A", bg="#635BFF", fg="white",
                        font=("Microsoft YaHei", 15, "bold"), width=2)
        icon.pack(side=tk.LEFT, padx=(0, 12))
        title_box = tk.Frame(header, bg="#F8FAFC")
        title_box.pack(side=tk.LEFT)
        tk.Label(title_box, text="字体样式设置", bg="#F8FAFC", fg="#111827",
                 font=title_font).pack(anchor=tk.W)
        tk.Label(title_box, text="为以指定字符开头的项目设置特殊字体样式",
                 bg="#F8FAFC", fg=muted, font=ui_font).pack(anchor=tk.W, pady=(2, 0))
        button(header, "重置", lambda: load_rule(current_prefix.get(), force=True),
               bg="#FFFFFF", fg="#374151").pack(side=tk.RIGHT)

        main = tk.Frame(win, bg="#F8FAFC")
        main.pack(fill=tk.BOTH, expand=True, padx=16)
        main.grid_columnconfigure(0, weight=1, minsize=430)
        main.grid_columnconfigure(1, weight=1, minsize=420)
        main.grid_rowconfigure(0, weight=1)

        left = tk.Frame(main, bg="#F8FAFC")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        right = tk.Frame(main, bg="#F8FAFC")
        right.grid(row=0, column=1, sticky="nsew")

        left_bar = tk.Frame(left, bg="#F8FAFC")
        left_bar.pack(fill=tk.X, pady=(0, 8))
        tk.Label(left_bar, text="样式规则列表", bg="#F8FAFC", fg="#111827",
                 font=label_font).pack(side=tk.LEFT)
        up_down = tk.Frame(left_bar, bg="#F8FAFC")
        up_down.pack(side=tk.RIGHT)

        columns = ("prefix", "font", "size", "weight", "color", "enabled", "priority")
        rules_tree = ttk.Treeview(left, columns=columns, show="headings", style="FontRule.Treeview",
                                  selectmode="browse")
        headings = {
            "prefix": ("匹配前缀", 80),
            "font": ("字体", 130),
            "size": ("大小", 55),
            "weight": ("粗细", 65),
            "color": ("颜色", 85),
            "enabled": ("启用", 55),
            "priority": ("优先级", 55),
        }
        for col, (text, width) in headings.items():
            rules_tree.heading(col, text=text)
            rules_tree.column(col, width=width, anchor=tk.CENTER if col in ("size", "enabled", "priority") else tk.W)
        rules_tree.pack(fill=tk.BOTH, expand=True)
        rules_tree.tag_configure("disabled", foreground="#94A3B8")

        tk.Label(left, text="优先级数字越小，优先级越高", bg="#F8FAFC", fg=muted,
                 font=("Microsoft YaHei", 8)).pack(anchor=tk.W, pady=(8, 0))

        form_title = tk.Label(right, text="编辑当前规则", bg="#F8FAFC", fg="#111827",
                              font=label_font)
        form_title.pack(anchor=tk.W, pady=(0, 8))

        prefix_var = tk.StringVar()
        font_family_var = tk.StringVar()
        font_size_var = tk.StringVar()
        font_weight_var = tk.StringVar()
        color_var = tk.StringVar()
        group_mode_var = tk.StringVar(value="color")
        target_group_var = tk.StringVar(value="A")
        desc_var = tk.StringVar()
        enabled_var = tk.BooleanVar(value=True)
        test_text_var = tk.StringVar(value="德魔样振子瑞")

        available_fonts = self.get_system_fonts()
        usable_fonts = [f for f in available_fonts if not f.startswith("---")]

        def section(parent, title):
            frame = tk.LabelFrame(parent, text=title, bg="#F8FAFC", fg="#111827",
                                  font=label_font, bd=1, relief=tk.SOLID, padx=10, pady=7)
            frame.pack(fill=tk.X, pady=(0, 8))
            return frame

        prefix_frame = tk.Frame(right, bg="#F8FAFC")
        prefix_frame.pack(fill=tk.X, pady=(0, 8))
        tk.Label(prefix_frame, text="匹配前缀", bg="#F8FAFC", fg="#111827", font=label_font).pack(anchor=tk.W)
        prefix_entry = tk.Entry(prefix_frame, textvariable=prefix_var, font=ui_font, relief=tk.SOLID, bd=1)
        prefix_entry.pack(fill=tk.X, pady=(4, 3), ipady=4)
        tk.Label(prefix_frame, text="例：输入“德”表示以“德”开头的项目",
                 bg="#F8FAFC", fg=muted, font=("Microsoft YaHei", 8)).pack(anchor=tk.W)

        preview_frame = tk.LabelFrame(right, text="实时预览", bg="#F8FAFC", fg="#111827",
                                      font=label_font, bd=1, relief=tk.SOLID, padx=12, pady=10)
        preview_frame.pack(fill=tk.X, pady=(0, 8))
        preview_label = tk.Label(preview_frame, text="", bg="#FFFFFF", fg="#FF0000",
                                 font=("Microsoft YaHei", 22), anchor=tk.CENTER, height=1)
        preview_label.pack(fill=tk.X)
        tk.Label(preview_frame, text="当前设置的效果预览", bg="#F8FAFC", fg=muted,
                 font=("Microsoft YaHei", 8)).pack(anchor=tk.W, pady=(6, 0))

        font_frame = section(right, "字体设置")
        tk.Label(font_frame, text="字体", bg="#F8FAFC", font=ui_font).grid(row=0, column=0, sticky=tk.W, pady=3)
        font_combo = ttk.Combobox(font_frame, textvariable=font_family_var, values=available_fonts,
                                  state="readonly", width=24)
        font_combo.grid(row=0, column=1, sticky=tk.W, padx=12, pady=3)
        tk.Label(font_frame, text="大小", bg="#F8FAFC", font=ui_font).grid(row=1, column=0, sticky=tk.W, pady=3)
        ttk.Combobox(font_frame, textvariable=font_size_var, values=[str(i) for i in range(8, 31)],
                     state="readonly", width=10).grid(row=1, column=1, sticky=tk.W, padx=12, pady=3)
        tk.Label(font_frame, text="粗细", bg="#F8FAFC", font=ui_font).grid(row=2, column=0, sticky=tk.W, pady=3)
        ttk.Combobox(font_frame, textvariable=font_weight_var, values=["Light", "normal", "bold"],
                     state="readonly", width=10).grid(row=2, column=1, sticky=tk.W, padx=12, pady=3)

        color_frame = section(right, "颜色设置")
        color_row = tk.Frame(color_frame, bg="#F8FAFC")
        color_row.pack(fill=tk.X)
        swatch = tk.Label(color_row, width=5, bg="#FF0000", relief=tk.SOLID, bd=1)
        swatch.pack(side=tk.LEFT, ipady=5)
        color_entry = tk.Entry(color_row, textvariable=color_var, font=ui_font, width=12, relief=tk.SOLID, bd=1)
        color_entry.pack(side=tk.LEFT, padx=10, ipady=4)

        preset_colors = ["#FF0000", "#CC0000", "#FF8C00", "#00AA00", "#006600",
                         "#0000FF", "#003399", "#9400D3", "#000000"]
        preset_row = tk.Frame(color_frame, bg="#F8FAFC")
        preset_row.pack(fill=tk.X, pady=(7, 0))
        for c in preset_colors:
            tk.Button(preset_row, bg=c, width=3, relief=tk.FLAT,
                      command=lambda v=c: color_var.set(v)).pack(side=tk.LEFT, padx=(0, 4), ipady=5)

        def choose_color():
            from tkinter import colorchooser
            color = colorchooser.askcolor(title="选择颜色", color=color_var.get())
            if color[1]:
                color_var.set(color[1])

        button(color_row, "取色", choose_color, bg="#FFFFFF").pack(side=tk.LEFT)

        group_frame = section(right, "分组方式")
        tk.Radiobutton(group_frame, text="不分组", variable=group_mode_var, value="none",
                       bg="#F8FAFC", font=ui_font).pack(anchor=tk.W)
        color_radio = tk.Radiobutton(group_frame, text="按颜色自动分组（红色 → A，其他 → B）",
                                     variable=group_mode_var, value="color",
                                     bg="#F8FAFC", font=ui_font)
        color_radio.pack(anchor=tk.W)
        manual_row = tk.Frame(group_frame, bg="#F8FAFC")
        manual_row.pack(fill=tk.X)
        tk.Radiobutton(manual_row, text="手动指定分组", variable=group_mode_var, value="manual",
                       bg="#F8FAFC", font=ui_font).pack(side=tk.LEFT)
        group_combo = ttk.Combobox(manual_row, textvariable=target_group_var, values=["A", "B", "C", "D"],
                                   state="readonly", width=8)
        group_combo.pack(side=tk.LEFT, padx=8)

        desc_frame = tk.Frame(right, bg="#F8FAFC")
        desc_frame.pack(fill=tk.X)
        tk.Label(desc_frame, text="描述（可选）", bg="#F8FAFC", fg="#111827", font=label_font).pack(anchor=tk.W)
        tk.Entry(desc_frame, textvariable=desc_var, font=ui_font, relief=tk.SOLID, bd=1).pack(fill=tk.X, pady=(4, 6), ipady=4)
        tk.Checkbutton(right, text="启用此规则", variable=enabled_var, bg="#F8FAFC",
                       font=ui_font).pack(anchor=tk.W)

        test = tk.Frame(win, bg="#FFFFFF", highlightbackground=border, highlightthickness=1)
        test.pack(fill=tk.X, padx=0, pady=(8, 0))
        test_inner = tk.Frame(test, bg="#FFFFFF")
        test_inner.pack(fill=tk.X, padx=16, pady=8)
        tk.Label(test_inner, text="效果测试", bg="#FFFFFF", fg="#111827",
                 font=label_font).grid(row=0, column=0, sticky=tk.W, pady=(0, 8))
        tk.Label(test_inner, text="测试文本：", bg="#FFFFFF", font=ui_font).grid(row=1, column=0, sticky=tk.W)
        tk.Entry(test_inner, textvariable=test_text_var, font=ui_font, relief=tk.SOLID, bd=1,
                 width=28).grid(row=1, column=1, sticky=tk.W, padx=8, ipady=4)
        tk.Label(test_inner, text="预览效果：", bg="#FFFFFF", font=ui_font).grid(row=1, column=2, sticky=tk.W, padx=(60, 8))
        bottom_preview = tk.Label(test_inner, text="", bg="#FFFFFF", fg="#FF0000", font=("Microsoft YaHei", 18))
        bottom_preview.grid(row=1, column=3, sticky=tk.W)

        footer = tk.Frame(win, bg="#F8FAFC")
        footer.pack(fill=tk.X, padx=16, pady=8)

        def sorted_prefixes():
            return list(self.font_style_rules.keys())

        def normalize_weight(weight):
            return "bold" if weight == "bold" else weight

        def update_preview(*args):
            try:
                size = int(font_size_var.get() or 12)
            except ValueError:
                size = 12
            family = font_family_var.get() or "Microsoft YaHei"
            if family.startswith("---"):
                family = "Microsoft YaHei"
            weight = normalize_weight(font_weight_var.get())
            font_parts = [family, size]
            if weight == "bold":
                font_parts.append("bold")
            try:
                color = color_var.get() or "#000000"
                swatch.config(bg=color)
                sample = test_text_var.get() or "德魔样振子瑞"
                prefix_text = prefix_var.get().strip()
                if prefix_text and not sample.startswith(prefix_text):
                    sample = prefix_text + sample
                preview_label.config(text=sample, fg=color, font=tuple(font_parts))
                bottom_preview.config(text=sample, fg=color, font=tuple(font_parts))
            except tk.TclError:
                pass

        def set_form_defaults():
            current_prefix.set("")
            prefix_var.set("")
            font_family_var.set("Microsoft YaHei")
            font_size_var.set("18")
            font_weight_var.set("normal")
            color_var.set("#FF0000")
            group_mode_var.set("color")
            target_group_var.set("A")
            desc_var.set("")
            enabled_var.set(True)
            form_title.config(text="编辑当前规则")
            update_preview()

        def load_rule(prefix, force=False):
            if not prefix or prefix not in self.font_style_rules:
                set_form_defaults()
                return
            style_data = self.font_style_rules[prefix]
            current_prefix.set(prefix)
            prefix_var.set(prefix)
            font_family_var.set(style_data.get("font_family", "Microsoft YaHei"))
            font_size_var.set(str(style_data.get("font_size", 18)))
            font_weight_var.set(style_data.get("font_weight", "normal"))
            color_var.set(style_data.get("color", "#FF0000"))
            target = style_data.get("target_group", "auto")
            if target == "none":
                group_mode_var.set("none")
            elif target in ("A", "B", "C", "D"):
                group_mode_var.set("manual")
                target_group_var.set(target)
            else:
                group_mode_var.set("color")
            desc_var.set(style_data.get("description", ""))
            enabled_var.set(style_data.get("enabled", True))
            form_title.config(text=f"编辑当前规则 - {prefix}")
            if force:
                self.show_temp_message("✓ 已重置为已保存的规则")
            update_preview()

        def refresh_rules_list(select_prefix=None):
            rules_tree.delete(*rules_tree.get_children())
            for index, (rule_prefix, style_data) in enumerate(self.font_style_rules.items(), start=1):
                enabled = style_data.get("enabled", True)
                weight = style_data.get("font_weight", "normal")
                rules_tree.insert("", tk.END, iid=rule_prefix,
                                  values=(rule_prefix,
                                          style_data.get("font_family", "Microsoft YaHei"),
                                          style_data.get("font_size", 18),
                                          weight,
                                          style_data.get("color", "#000000"),
                                          "是" if enabled else "否",
                                          index),
                                  tags=() if enabled else ("disabled",))
            target = select_prefix if select_prefix in self.font_style_rules else None
            if not target and self.font_style_rules:
                target = next(iter(self.font_style_rules.keys()))
            if target:
                rules_tree.selection_set(target)
                rules_tree.focus(target)
                load_rule(target)
            else:
                set_form_defaults()

        def save_current(close_after=False):
            old_prefix = current_prefix.get()
            new_prefix = prefix_var.get().strip()
            if not new_prefix:
                messagebox.showwarning("提示", "匹配前缀不能为空！")
                return False
            if old_prefix != new_prefix and new_prefix in self.font_style_rules:
                if not messagebox.askyesno("规则已存在", f"规则「{new_prefix}」已存在，是否覆盖？"):
                    return False
            if old_prefix and old_prefix != new_prefix and old_prefix in self.font_style_rules:
                del self.font_style_rules[old_prefix]

            if group_mode_var.get() == "none":
                target_group = "none"
            elif group_mode_var.get() == "manual":
                target_group = target_group_var.get()
            else:
                target_group = "auto"

            self.font_style_rules[new_prefix] = {
                "font_family": font_family_var.get(),
                "font_size": int(font_size_var.get()),
                "font_weight": font_weight_var.get(),
                "color": color_var.get(),
                "target_group": target_group,
                "description": desc_var.get().strip(),
                "enabled": enabled_var.get(),
            }
            self.save_font_style_config()

            if enabled_var.get() and not self.df.empty:
                effective_group = target_group
                if effective_group == "auto":
                    effective_group = "A" if self._is_red_color(color_var.get()) else "B"
                if effective_group in ("A", "B", "C", "D"):
                    mask = self.df['Label'].str.lower().str.startswith(new_prefix.lower())
                    changed = mask.sum()
                    self.df.loc[mask, 'Group'] = effective_group
                    if changed > 0:
                        self.show_temp_message(f"✓ 已将 {changed} 个匹配项自动设为 {effective_group} 组")

            current_prefix.set(new_prefix)
            refresh_rules_list(new_prefix)
            self.refresh_all()
            if close_after:
                win.destroy()
            return True

        def add_rule():
            rules_tree.selection_remove(rules_tree.selection())
            set_form_defaults()
            prefix_entry.focus_set()

        def delete_rule():
            prefix = current_prefix.get()
            if not prefix:
                messagebox.showwarning("提示", "请先选择一个规则！")
                return
            if messagebox.askyesno("确认删除", f"确定要删除规则「{prefix}」吗？"):
                del self.font_style_rules[prefix]
                self.save_font_style_config()
                refresh_rules_list()
                self.refresh_all()

        def move_rule(direction):
            prefix = current_prefix.get()
            prefixes = sorted_prefixes()
            if prefix not in prefixes:
                return
            index = prefixes.index(prefix)
            new_index = index + direction
            if new_index < 0 or new_index >= len(prefixes):
                return
            prefixes[index], prefixes[new_index] = prefixes[new_index], prefixes[index]
            self.font_style_rules = {p: self.font_style_rules[p] for p in prefixes}
            self.save_font_style_config()
            refresh_rules_list(prefix)
            self.refresh_all()

        def on_select(event=None):
            selection = rules_tree.selection()
            if selection:
                load_rule(selection[0])

        rules_tree.bind("<<TreeviewSelect>>", on_select)
        button(left_bar, "+ 添加规则", add_rule, bg="#FFFFFF").pack(side=tk.RIGHT, padx=(0, 6))
        button(left_bar, "删除规则", delete_rule, bg="#FFFFFF").pack(side=tk.RIGHT, padx=(0, 6))
        button(up_down, "↑", lambda: move_rule(-1), bg="#FFFFFF", width=2).pack(side=tk.LEFT, padx=2)
        button(up_down, "↓", lambda: move_rule(1), bg="#FFFFFF", width=2).pack(side=tk.LEFT, padx=2)

        for var in (prefix_var, font_family_var, font_size_var, font_weight_var, color_var, test_text_var):
            var.trace_add("write", update_preview)

        # 备份规则，供取消时还原
        import copy
        _rules_backup = copy.deepcopy(self.font_style_rules)

        def on_cancel():
            self.font_style_rules = copy.deepcopy(_rules_backup)
            self.save_font_style_config()
            self.refresh_all()
            win.destroy()

        button(footer, "取消", on_cancel, bg="#FFFFFF", fg="#374151").pack(side=tk.RIGHT, padx=(8, 0))
        button(footer, "应用", lambda: save_current(close_after=True),
               bg=primary, fg="white").pack(side=tk.RIGHT, padx=(8, 0))
        button(footer, "保存", lambda: save_current(close_after=False),
               bg="#4CAF50", fg="white").pack(side=tk.RIGHT)

        refresh_rules_list()
    
    def show_font_style_editor(self, prefix, refresh_callback):
        """显示字体样式编辑器"""
        is_edit = prefix is not None
        title = f"编辑字体样式 - {prefix}" if is_edit else "添加字体样式规则"
        window_name = f"font_style_editor_{prefix}" if is_edit else "font_style_editor_new"
        
        editor_window = self.create_popup_window(self.root, title, window_name, 500, 450)
        
        tk.Label(editor_window, text=title, 
                font=("Arial", 12, "bold")).pack(pady=15)
        
        # 前缀设置
        prefix_frame = tk.Frame(editor_window, padx=20)
        prefix_frame.pack(fill=tk.X, pady=5)
        
        tk.Label(prefix_frame, text="前缀字符：").pack(anchor=tk.W)
        prefix_var = tk.StringVar(value=prefix if is_edit else "")
        prefix_entry = tk.Entry(prefix_frame, textvariable=prefix_var, font=("Arial", 11), width=40)
        prefix_entry.pack(fill=tk.X, pady=5)
        tk.Label(prefix_frame, text="例：输入'a'表示以'a'开头的项目", 
                font=("Arial", 9), fg="gray").pack(anchor=tk.W)
        
        # 字体设置
        font_frame = tk.LabelFrame(editor_window, text="字体设置", padx=10, pady=10)
        font_frame.pack(fill=tk.X, padx=20, pady=10)
        
        # 字体族 - 获取系统所有可用字体
        tk.Label(font_frame, text="字体：").grid(row=0, column=0, sticky=tk.W, pady=5)
        font_family_var = tk.StringVar()
        
        # 获取系统字体列表
        available_fonts = self.get_system_fonts()
        
        font_family_combo = ttk.Combobox(font_frame, textvariable=font_family_var,
                                        values=available_fonts,
                                        state="readonly", width=25)
        font_family_combo.grid(row=0, column=1, sticky=tk.W, padx=10, pady=5)
        
        # 绑定选择事件，防止选择分隔符
        def on_font_select(event):
            selected = font_family_var.get()
            if selected.startswith("---"):
                # 如果选择了分隔符，恢复到之前的选择
                font_family_combo.set(font_family_var.get() if font_family_var.get() not in available_fonts[:10] else "Microsoft YaHei")
        
        font_family_combo.bind("<<ComboboxSelected>>", on_font_select)
        
        # 字体大小
        tk.Label(font_frame, text="大小：").grid(row=1, column=0, sticky=tk.W, pady=5)
        font_size_var = tk.StringVar()
        font_size_combo = ttk.Combobox(font_frame, textvariable=font_size_var,
                                      values=[str(i) for i in range(8, 25)],
                                      state="readonly", width=10)
        font_size_combo.grid(row=1, column=1, sticky=tk.W, padx=10, pady=5)
        
        # 字体粗细
        tk.Label(font_frame, text="粗细：").grid(row=2, column=0, sticky=tk.W, pady=5)
        font_weight_var = tk.StringVar()
        font_weight_combo = ttk.Combobox(font_frame, textvariable=font_weight_var,
                                        values=["normal", "bold"],
                                        state="readonly", width=15)
        font_weight_combo.grid(row=2, column=1, sticky=tk.W, padx=10, pady=5)
        
        # 颜色设置
        color_frame = tk.LabelFrame(editor_window, text="颜色设置", padx=10, pady=10)
        color_frame.pack(fill=tk.X, padx=20, pady=10)

        tk.Label(color_frame, text="文字颜色：").pack(anchor=tk.W)

        color_var = tk.StringVar()

        # 预设颜色按钮行
        preset_colors = [
            ("红色", "#FF0000"), ("深红", "#CC0000"), ("橙色", "#FF8C00"),
            ("绿色", "#00AA00"), ("深绿", "#006600"), ("蓝色", "#0000FF"),
            ("深蓝", "#003399"), ("紫色", "#9400D3"), ("黑色", "#000000"),
        ]

        btn_row = tk.Frame(color_frame)
        btn_row.pack(anchor=tk.W, pady=(0, 5))

        def make_color_btn(name, hex_color):
            def on_click():
                color_var.set(hex_color)
                preview_label.config(bg=hex_color)
            btn = tk.Button(btn_row, text=name, bg=hex_color,
                           fg="white" if hex_color not in ("#FF8C00", "#00AA00") else "black",
                           font=("Arial", 9), padx=6, pady=3,
                           relief=tk.RAISED, bd=1, command=on_click)
            btn.pack(side=tk.LEFT, padx=2)

        for name, hex_color in preset_colors:
            make_color_btn(name, hex_color)

        # 输入框 + 取色器 + 预览
        input_row = tk.Frame(color_frame)
        input_row.pack(anchor=tk.W, pady=3)

        color_entry = tk.Entry(input_row, textvariable=color_var, font=("Arial", 11), width=12)
        color_entry.pack(side=tk.LEFT)

        preview_label = tk.Label(input_row, text="  预览  ", font=("Arial", 10),
                                 relief=tk.SUNKEN, bd=1, padx=8, pady=3)
        preview_label.pack(side=tk.LEFT, padx=8)

        def update_preview(*args):
            try:
                c = color_var.get()
                preview_label.config(bg=c)
            except:
                pass

        color_var.trace_add('write', update_preview)

        def choose_color():
            from tkinter import colorchooser
            color = colorchooser.askcolor(title="选择颜色", color=color_var.get())
            if color[1]:
                color_var.set(color[1])

        tk.Button(input_row, text="更多颜色...", command=choose_color,
                 bg="#9C27B0", fg="white", padx=8, pady=3).pack(side=tk.LEFT, padx=5)
        
        # 自动分组设置
        group_frame = tk.LabelFrame(editor_window, text="自动分组", padx=10, pady=10)
        group_frame.pack(fill=tk.X, padx=20, pady=5)
        
        tk.Label(group_frame, text="匹配此前缀的条目自动归入：").grid(row=0, column=0, sticky=tk.W)
        target_group_var = tk.StringVar(value='auto')
        group_combo = ttk.Combobox(group_frame, textvariable=target_group_var,
                                   values=['auto（根据颜色自动判断）', 'A', 'B', 'C', 'D'],
                                   state="readonly", width=25)
        group_combo.grid(row=0, column=1, sticky=tk.W, padx=10)
        tk.Label(group_frame, text="auto = 红色→A，其他→B", 
                font=("Arial", 9), fg="gray").grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=3)
        
        # 描述
        desc_frame = tk.Frame(editor_window, padx=20)
        desc_frame.pack(fill=tk.X, pady=5)
        
        tk.Label(desc_frame, text="描述（可选）：").pack(anchor=tk.W)
        desc_var = tk.StringVar()
        desc_entry = tk.Entry(desc_frame, textvariable=desc_var, font=("Arial", 11), width=40)
        desc_entry.pack(fill=tk.X, pady=5)
        
        # 如果是编辑模式，加载现有值
        if is_edit and prefix in self.font_style_rules:
            style = self.font_style_rules[prefix]
            font_family_var.set(style.get('font_family', 'Microsoft YaHei'))
            font_size_var.set(str(style.get('font_size', 12)))
            font_weight_var.set(style.get('font_weight', 'normal'))
            color_var.set(style.get('color', '#000000'))
            desc_var.set(style.get('description', ''))
            tg = style.get('target_group', 'auto')
            target_group_var.set(tg if tg in ('A', 'B', 'C', 'D') else 'auto（根据颜色自动判断）')
        else:
            # 设置默认值
            font_family_var.set('Microsoft YaHei')
            font_size_var.set('12')
            font_weight_var.set('normal')
            color_var.set('#FF0000')
            target_group_var.set('auto（根据颜色自动判断）')
        
        # 按钮
        btn_frame = tk.Frame(editor_window, pady=15)
        btn_frame.pack(fill=tk.X)
        
        def save_style():
            new_prefix = prefix_var.get().strip()
            if not new_prefix:
                messagebox.showwarning("提示", "前缀字符不能为空！")
                return
            
            # 如果是编辑模式且前缀改变了，删除旧的
            if is_edit and new_prefix != prefix and new_prefix in self.font_style_rules:
                if not messagebox.askyesno("规则已存在", f"规则「{new_prefix}」已存在，是否覆盖？"):
                    return
            
            if is_edit and new_prefix != prefix:
                del self.font_style_rules[prefix]
            
            # 保存新的规则
            tg_raw = target_group_var.get()
            target_group = tg_raw if tg_raw in ('A', 'B', 'C', 'D') else 'auto'
            self.font_style_rules[new_prefix] = {
                "font_family": font_family_var.get(),
                "font_size": int(font_size_var.get()),
                "font_weight": font_weight_var.get(),
                "color": color_var.get(),
                "target_group": target_group,
                "description": desc_var.get().strip()
            }
            
            self.save_font_style_config()
            
            # 自动将匹配前缀的数据改为对应组
            if not self.df.empty:
                effective_group = target_group
                if effective_group == 'auto':
                    effective_group = 'A' if self._is_red_color(color_var.get()) else None
                if effective_group:
                    mask = self.df['Label'].str.lower().str.startswith(new_prefix.lower())
                    changed = mask.sum()
                    self.df.loc[mask, 'Group'] = effective_group
                    if changed > 0:
                        self.show_temp_message(f"✓ 已将 {changed} 个匹配项自动设为 {effective_group} 组")
            
            refresh_callback()
            editor_window.destroy()
            
            # 刷新显示
            self.refresh_all()
            messagebox.showinfo("成功", f"字体样式规则「{new_prefix}」已保存！")
        
        tk.Button(btn_frame, text="保存", command=save_style,
                 bg="#4CAF50", fg="white", padx=20, pady=8).pack(side=tk.RIGHT, padx=5)
        
        tk.Button(btn_frame, text="取消", command=editor_window.destroy,
                 bg="#757575", fg="white", padx=20, pady=8).pack(side=tk.RIGHT)

    def create_tooltip(self, widget, text):
        """创建简单的工具提示"""
        def on_enter(event):
            tooltip = tk.Toplevel()
            tooltip.wm_overrideredirect(True)
            tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")
            label = tk.Label(tooltip, text=text, background="lightyellow", 
                           relief="solid", borderwidth=1, font=("Arial", 9))
            label.pack()
            widget.tooltip = tooltip
        
        def on_leave(event):
            if hasattr(widget, 'tooltip'):
                widget.tooltip.destroy()
                del widget.tooltip
        
        widget.bind("<Enter>", on_enter)
        widget.bind("<Leave>", on_leave)


if __name__ == '__main__':
    try:
        # 尝试使用TkinterDnD支持拖放
        from tkinterdnd2 import TkinterDnD
        root = TkinterDnD.Tk()
    except ImportError:
        # 如果没有安装tkinterdnd2，使用普通Tk
        print("提示：安装 tkinterdnd2 可以启用拖放功能")
        print("安装命令：pip install tkinterdnd2")
        root = tk.Tk()
    
    try:
        app = OCRApp(root)
        root.mainloop()
    except KeyboardInterrupt:
        print("\n程序被用户中断")
    except Exception as e:
        print(f"程序运行出错: {e}")
        import traceback
        traceback.print_exc()
    finally:
        try:
            root.destroy()
        except:
            pass
