# -*- coding: utf-8 -*-
"""
@Author  : Adapted for tkinter
@Time    : 2024
@FileName: gui_tkinter.py
@desc: Графический интерфейс извлечения субтитров с использованием tkinter
"""
import backend.main
import os
import configparser
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import cv2
from threading import Thread
import multiprocessing
from PIL import Image, ImageTk
import queue
import numpy as np


class SubtitleExtractorGUI:
    def _load_config(self):
        self.config_file = os.path.join(os.path.dirname(__file__), 'settings.ini')
        self.subtitle_config_file = os.path.join(os.path.dirname(__file__), 'subtitle.ini')
        
        # Если файла настроек нет, создаем его с настройками по умолчанию
        if not os.path.exists(self.config_file):
            self._create_default_config()
        
        self.config = configparser.ConfigParser()
        self.interface_config = configparser.ConfigParser()
        
        self.config.read(self.config_file, encoding='utf-8')
        self.INTERFACE_KEY_NAME_MAP = {
            'Русский': 'ru',
            '简体中文': 'ch',
            '繁體中文': 'chinese_cht',
            'English': 'en',
            '한국어': 'ko',
            '日本語': 'japan',
            'Tiếng Việt': 'vi',
            'Español': 'es'
        }
        
        interface = self.config['DEFAULT']['Interface']
        interface_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend', 'interface',
                                      f"{self.INTERFACE_KEY_NAME_MAP.get(interface, 'ru')}.ini")
        self.interface_config.read(interface_file, encoding='utf-8')

    def _create_default_config(self):
        """Создание конфигурационного файла по умолчанию"""
        with open(self.config_file, mode='w', encoding='utf-8') as f:
            f.write('[DEFAULT]\n')
            f.write('Interface = Русский\n')
            f.write('Language = ru\n')
            f.write('Mode = fast\n')

    def __init__(self):
        # Проверка среды выполнения при первом запуске
        from paddle import utils
        utils.run_check()
        
        self.root = tk.Tk()
        
        # Сначала загружаем конфиг для получения заголовка
        self._load_config()
        self.root.title(self.interface_config['SubtitleExtractorGUI']['Title'] + " v" + backend.main.config.VERSION)
        
        # Иконка
        self.icon_path = os.path.join(os.path.dirname(__file__), 'design', 'vse.ico')
        if os.path.exists(self.icon_path):
            try:
                self.root.iconbitmap(self.icon_path)
            except:
                pass
        
        # Размер экрана
        self.screen_width = self.root.winfo_screenwidth()
        self.screen_height = self.root.winfo_screenheight()
        
        # Размер области предпросмотра видео
        self.video_preview_width = 960
        self.video_preview_height = self.video_preview_width * 9 // 16
        
        # Разрешение ниже 1080
        if self.screen_width // 2 < 960:
            self.video_preview_width = 640
            self.video_preview_height = self.video_preview_width * 9 // 16
        
        # Путь к видео
        self.video_path = None
        # Видео cap
        self.video_cap = None
        # Частота кадров видео
        self.fps = None
        # Количество кадров видео
        self.frame_count = None
        # Ширина видео
        self.frame_width = None
        # Высота видео
        self.frame_height = None
        
        # Область субтитров
        self.xmin = None
        self.xmax = None
        self.ymin = None
        self.ymax = None
        
        # Извлекатель субтитров
        self.se = None
        
        # Очередь для обновления UI
        self.update_queue = queue.Queue()
        
        # Создание интерфейса
        self._create_widgets()
        
        # Запуск обработки очереди обновлений
        self.root.after(100, self._process_update_queue)
        
        # Центрируем окно
        self._center_window()

    def _center_window(self):
        """Центрирование окна на экране"""
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')

    def _create_widgets(self):
        # Основной фрейм
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Область предпросмотра видео
        self.video_label = ttk.Label(main_frame, background='black')
        self.video_label.grid(row=0, column=0, columnspan=4, pady=(0, 10), sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Черный фон для области предпросмотра
        self.blank_image = Image.new('RGB', (self.video_preview_width, self.video_preview_height), 'black')
        self.blank_photo = ImageTk.PhotoImage(self.blank_image)
        self.video_label.config(image=self.blank_photo)
        
        # Панель управления (первая строка)
        control_frame = ttk.Frame(main_frame)
        control_frame.grid(row=1, column=0, columnspan=4, pady=(0, 10), sticky=(tk.W, tk.E))
        
        # Кнопка открытия файла
        self.open_button = ttk.Button(control_frame, text=self.interface_config['SubtitleExtractorGUI']['Open'],
                                     command=self._open_file)
        self.open_button.grid(row=0, column=0, padx=(0, 10), sticky=tk.W)
        
        # Панель для ползунка (вторая строка)
        slider_frame = ttk.Frame(main_frame)
        slider_frame.grid(row=2, column=0, columnspan=4, pady=(0, 10), sticky=(tk.W, tk.E))
        
        # Ползунок прогресса видео (занимает всю ширину)
        self.video_slider = ttk.Scale(slider_frame, from_=1, to=1, orient=tk.HORIZONTAL,
                                     command=self._on_video_slide)
        self.video_slider.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        # Настройка веса для растягивания ползунка
        slider_frame.columnconfigure(0, weight=1)
        
        # Нижняя панель (текстовая область и ползунки субтитров)
        bottom_frame = ttk.Frame(main_frame)
        bottom_frame.grid(row=3, column=0, columnspan=4, pady=(0, 10), sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Левая часть: текстовая область вывода
        left_panel = ttk.Frame(bottom_frame)
        left_panel.grid(row=0, column=0, padx=(0, 10), sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Текстовое поле вывода
        self.output_text = tk.Text(left_panel, width=60, height=10)
        self.output_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Скроллбар для текстового поля
        scrollbar = ttk.Scrollbar(left_panel, orient=tk.VERTICAL, command=self.output_text.yview)
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.output_text.config(yscrollcommand=scrollbar.set)
        
        # Правая часть: ползунки для области субтитров
        right_panel = ttk.Frame(bottom_frame)
        right_panel.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Панель настройки области субтитров - вертикальные ползунки
        subtitle_frame_vertical = ttk.LabelFrame(right_panel, text=self.interface_config['SubtitleExtractorGUI']['Vertical'])
        subtitle_frame_vertical.grid(row=0, column=0, padx=(0, 10), pady=(0, 5), sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Вертикальные ползунки (Y и Height)
        self.y_slider = ttk.Scale(subtitle_frame_vertical, from_=0, to=0, orient=tk.VERTICAL,
                                 command=self._on_subtitle_slide, length=150)
        self.y_slider.grid(row=0, column=0, padx=5, pady=5)
        self.y_slider.config(state=tk.DISABLED)
        
        self.yh_slider = ttk.Scale(subtitle_frame_vertical, from_=0, to=0, orient=tk.VERTICAL,
                                  command=self._on_subtitle_slide, length=150)
        self.yh_slider.grid(row=0, column=1, padx=5, pady=5)
        self.yh_slider.config(state=tk.DISABLED)
        
        # Панель настройки области субтитров - горизонтальные ползунки
        subtitle_frame_horizontal = ttk.LabelFrame(right_panel, text=self.interface_config['SubtitleExtractorGUI']['Horizontal'])
        subtitle_frame_horizontal.grid(row=1, column=0, padx=(0, 10), pady=(5, 0), sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Горизонтальные ползунки (X и Width)
        self.x_slider = ttk.Scale(subtitle_frame_horizontal, from_=0, to=0, orient=tk.VERTICAL,
                                 command=self._on_subtitle_slide, length=150)
        self.x_slider.grid(row=0, column=0, padx=5, pady=5)
        self.x_slider.config(state=tk.DISABLED)
        
        self.xw_slider = ttk.Scale(subtitle_frame_horizontal, from_=0, to=0, orient=tk.VERTICAL,
                                  command=self._on_subtitle_slide, length=150)
        self.xw_slider.grid(row=0, column=1, padx=5, pady=5)
        self.xw_slider.config(state=tk.DISABLED)
        
        # Панель кнопок и прогресс-бар
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=4, column=0, columnspan=4, pady=(0, 10), sticky=(tk.W, tk.E))
        
        # Кнопка запуска
        self.run_button = ttk.Button(button_frame, text=self.interface_config['SubtitleExtractorGUI']['Run'],
                                    command=self._run_extraction, state=tk.DISABLED)
        self.run_button.grid(row=0, column=0, padx=(0, 10))
        
        # Кнопка настроек
        self.settings_button = ttk.Button(button_frame, text=self.interface_config['SubtitleExtractorGUI']['Setting'],
                                         command=self._open_settings)
        self.settings_button.grid(row=0, column=1, padx=(0, 10))
        
        # Прогресс-бар (растягивается)
        self.progress_bar = ttk.Progressbar(button_frame, length=300, mode='determinate')
        self.progress_bar.grid(row=0, column=2, padx=(10, 0), sticky=(tk.W, tk.E))
        
        # Настройка весов для растягивания элементов
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=0)
        main_frame.columnconfigure(2, weight=0)
        main_frame.columnconfigure(3, weight=0)
        main_frame.rowconfigure(0, weight=1)  # Видео растягивается
        main_frame.rowconfigure(3, weight=1)  # Нижняя панель растягивается
        
        bottom_frame.columnconfigure(0, weight=3)  # Текстовая область занимает 3/4
        bottom_frame.columnconfigure(1, weight=1)  # Ползунки занимают 1/4
        bottom_frame.rowconfigure(0, weight=1)
        
        left_panel.columnconfigure(0, weight=1)
        left_panel.rowconfigure(0, weight=1)
        
        right_panel.columnconfigure(0, weight=1)
        right_panel.rowconfigure(0, weight=1)
        right_panel.rowconfigure(1, weight=1)
        
        button_frame.columnconfigure(2, weight=1)  # Прогресс-бар растягивается
        
        # Очередь видеофайлов
        self.video_queue = []

    def _open_file(self):
        filetypes = [
            (self.interface_config['SubtitleExtractorGUI']['AllFile'], '*.*'),
            ('MP4 files', '*.mp4'),
            ('FLV files', '*.flv'),
            ('WMV files', '*.wmv'),
            ('AVI files', '*.avi')
        ]
        
        filenames = filedialog.askopenfilenames(filetypes=filetypes)
        if filenames:
            self.video_queue = list(filenames)
            self.video_path = self.video_queue[0]
            self._load_video()

    def _load_video(self):
        if self.video_path:
            self.video_cap = cv2.VideoCapture(self.video_path)
            if self.video_cap.isOpened():
                ret, frame = self.video_cap.read()
                if ret:
                    for video in self.video_queue:
                        self._print_output(f"{self.interface_config['SubtitleExtractorGUI']['OpenVideoSuccess']}: {video}")
                    
                    # Получение информации о видео
                    self.frame_count = int(self.video_cap.get(cv2.CAP_PROP_FRAME_COUNT))
                    self.frame_height = int(self.video_cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    self.frame_width = int(self.video_cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    self.fps = self.video_cap.get(cv2.CAP_PROP_FPS)
                    
                    # Обновление ползунков
                    self.video_slider.config(from_=1, to=self.frame_count)
                    self.video_slider.set(1)
                    
                    # Предустановка области субтитров
                    y_p, h_p, x_p, w_p = self._parse_subtitle_config()
                    y = self.frame_height * y_p
                    h = self.frame_height * h_p
                    x = self.frame_width * x_p
                    w = self.frame_width * w_p
                    
                    self.y_slider.config(from_=0, to=self.frame_height)
                    self.y_slider.set(y)
                    self.y_slider.config(state=tk.NORMAL)
                    
                    self.x_slider.config(from_=0, to=self.frame_width)
                    self.x_slider.set(x)
                    self.x_slider.config(state=tk.NORMAL)
                    
                    self.yh_slider.config(from_=0, to=self.frame_height - y)
                    self.yh_slider.set(h)
                    self.yh_slider.config(state=tk.NORMAL)
                    
                    self.xw_slider.config(from_=0, to=self.frame_width - x)
                    self.xw_slider.set(w)
                    self.xw_slider.config(state=tk.NORMAL)
                    
                    # Активация кнопки запуска
                    self.run_button.config(state=tk.NORMAL)
                    
                    # Обновление предпросмотра
                    self._update_preview(frame, (y, h, x, w))

    def _on_video_slide(self, value):
        if self.video_cap is not None and self.video_cap.isOpened():
            frame_no = int(float(value))
            self.video_cap.set(cv2.CAP_PROP_POS_FRAMES, frame_no)
            ret, frame = self.video_cap.read()
            if ret:
                y = self.y_slider.get()
                h = self.yh_slider.get()
                x = self.x_slider.get()
                w = self.xw_slider.get()
                
                # Обновление диапазонов ползунков высоты и ширины
                self.yh_slider.config(to=self.frame_height - y)
                self.xw_slider.config(to=self.frame_width - x)
                
                self._update_preview(frame, (y, h, x, w))

    def _on_subtitle_slide(self, value):
        if self.video_cap is not None and self.video_cap.isOpened():
            frame_no = self.video_slider.get()
            self.video_cap.set(cv2.CAP_PROP_POS_FRAMES, frame_no)
            ret, frame = self.video_cap.read()
            if ret:
                y = self.y_slider.get()
                h = self.yh_slider.get()
                x = self.x_slider.get()
                w = self.xw_slider.get()
                
                # Обновление диапазонов ползунков высоты и ширины
                self.yh_slider.config(to=self.frame_height - y)
                self.xw_slider.config(to=self.frame_width - x)
                
                self._update_preview(frame, (y, h, x, w))

    def _update_preview(self, frame, y_h_x_w):
        y, h, x, w = y_h_x_w
        # Рисование прямоугольника области субтитров
        draw = cv2.rectangle(img=frame.copy(), 
                           pt1=(int(x), int(y)), 
                           pt2=(int(x) + int(w), int(y) + int(h)),
                           color=(0, 255, 0), 
                           thickness=3)
        
        # Масштабирование видео для отображения (letterbox)
        resized_frame = self._img_resize_with_letterbox(draw)
        
        # Конвертация для tkinter
        rgb_image = cv2.cvtColor(resized_frame, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(rgb_image)
        photo = ImageTk.PhotoImage(pil_image)
        
        self.video_label.config(image=photo)
        self.video_label.image = photo

    def _img_resize_with_letterbox(self, image):
        """
        Масштабирование изображения с сохранением пропорций (letterbox)
        """
        height, width = image.shape[0], image.shape[1]
        
        # Рассчет соотношения сторон
        target_width = self.video_preview_width
        target_height = self.video_preview_height
        
        # Рассчет масштаба
        scale = min(target_width / width, target_height / height)
        
        # Новые размеры с сохранением пропорций
        new_width = int(width * scale)
        new_height = int(height * scale)
        
        # Масштабирование
        resized = cv2.resize(image, (new_width, new_height))
        
        # Создание черного фона
        result = np.zeros((target_height, target_width, 3), dtype=np.uint8)
        
        # Размещение изображения по центру
        x_offset = (target_width - new_width) // 2
        y_offset = (target_height - new_height) // 2
        
        result[y_offset:y_offset+new_height, x_offset:x_offset+new_width] = resized
        
        return result

    def _run_extraction(self):
        if self.video_cap is None:
            self._print_output(self.interface_config['SubtitleExtractorGUI']['OpenVideoFirst'])
            return
        
        # Блокировка элементов управления
        self._set_controls_state(tk.DISABLED)
        
        # Установка области субтитров
        self.xmin = int(self.x_slider.get())
        self.xmax = int(self.x_slider.get() + self.xw_slider.get())
        self.ymin = int(self.y_slider.get())
        self.ymax = int(self.y_slider.get() + self.yh_slider.get())
        
        if self.ymax > self.frame_height:
            self.ymax = self.frame_height
        if self.xmax > self.frame_width:
            self.xmax = self.frame_width
        
        self._print_output(f"{self.interface_config['SubtitleExtractorGUI']['SubtitleArea']}: ({self.ymin},{self.ymax},{self.xmin},{self.xmax})")
        
        subtitle_area = (self.ymin, self.ymax, self.xmin, self.xmax)
        
        # Сохранение настроек области
        y_p = self.ymin / self.frame_height
        h_p = (self.ymax - self.ymin) / self.frame_height
        x_p = self.xmin / self.frame_width
        w_p = (self.xmax - self.xmin) / self.frame_width
        self._set_subtitle_config(y_p, h_p, x_p, w_p)
        
        # Запуск извлечения в отдельном потоке
        def extraction_task():
            while self.video_queue:
                video_path = self.video_queue.pop(0)
                self.se = backend.main.SubtitleExtractor(video_path, subtitle_area, gui_mode=True)
                self.se.run()
                
                # Обновление прогресса через очередь
                self.update_queue.put(("progress", self.se.progress_total))
                self.update_queue.put(("finished", None))
            
            # Разблокировка элементов управления после завершения
            self.update_queue.put(("unlock", None))
        
        Thread(target=extraction_task, daemon=True).start()
        
        if self.video_cap:
            self.video_cap.release()
            self.video_cap = None

    def _set_controls_state(self, state):
        self.open_button.config(state=state)
        self.run_button.config(state=state)
        self.settings_button.config(state=state)
        self.video_slider.config(state=state)
        self.y_slider.config(state=state)
        self.yh_slider.config(state=state)
        self.x_slider.config(state=state)
        self.xw_slider.config(state=state)

    def _print_output(self, text):
        self.output_text.insert(tk.END, text + "\n")
        self.output_text.see(tk.END)
        self.root.update_idletasks()

    def _process_update_queue(self):
        try:
            while True:
                msg_type, data = self.update_queue.get_nowait()
                
                if msg_type == "progress":
                    self.progress_bar['value'] = data
                elif msg_type == "finished":
                    self._print_output("Извлечение завершено!")
                elif msg_type == "unlock":
                    self._set_controls_state(tk.NORMAL)
                    self.progress_bar['value'] = 0
                    
        except queue.Empty:
            pass
        
        self.root.after(100, self._process_update_queue)

    def _open_settings(self):
        # Открываем окно настроек как модальное
        settings_window = SettingsWindow(self)
        settings_window.show()

    def _set_subtitle_config(self, y, h, x, w):
        with open(self.subtitle_config_file, mode='w', encoding='utf-8') as f:
            f.write('[AREA]\n')
            f.write(f'Y = {y}\n')
            f.write(f'H = {h}\n')
            f.write(f'X = {x}\n')
            f.write(f'W = {w}\n')

    def _parse_subtitle_config(self):
        y_p, h_p, x_p, w_p = .78, .21, .05, .9
        
        if not os.path.exists(self.subtitle_config_file):
            self._set_subtitle_config(y_p, h_p, x_p, w_p)
            return y_p, h_p, x_p, w_p
        else:
            try:
                config = configparser.ConfigParser()
                config.read(self.subtitle_config_file, encoding='utf-8')
                conf_y_p = float(config['AREA']['Y'])
                conf_h_p = float(config['AREA']['H'])
                conf_x_p = float(config['AREA']['X'])
                conf_w_p = float(config['AREA']['W'])
                return conf_y_p, conf_h_p, conf_x_p, conf_w_p
            except Exception:
                self._set_subtitle_config(y_p, h_p, x_p, w_p)
                return y_p, h_p, x_p, w_p

    def update_interface_text(self):
        """Обновление текстов интерфейса после изменения настроек"""
        self._load_config()
        self.root.title(self.interface_config['SubtitleExtractorGUI']['Title'] + " v" + backend.main.config.VERSION)
        self.open_button.config(text=self.interface_config['SubtitleExtractorGUI']['Open'])
        self.run_button.config(text=self.interface_config['SubtitleExtractorGUI']['Run'])
        self.settings_button.config(text=self.interface_config['SubtitleExtractorGUI']['Setting'])

    def run(self):
        # Предупреждение о GPU
        self._print_output(self.interface_config['Main']['GPUWarning'])
        self.root.mainloop()


class SettingsWindow:
    def __init__(self, parent):
        self.parent = parent
        self.window = tk.Toplevel(parent.root)
        self.window.title("Настройки")
        
        # Блокируем главное окно
        self.window.transient(parent.root)
        self.window.grab_set()
        
        # Загрузка текстов интерфейса
        self._load_interface_text()
        
        self._create_widgets()
        self._center_window()

    def _center_window(self):
        """Центрирование окна настроек"""
        self.window.update_idletasks()
        width = 400
        height = 250
        x = (self.window.winfo_screenwidth() // 2) - (width // 2)
        y = (self.window.winfo_screenheight() // 2) - (height // 2)
        self.window.geometry(f'{width}x{height}+{x}+{y}')

    def _load_interface_text(self):
        # Используем конфиг из родительского окна
        self.interface_config = self.parent.interface_config
        
        # Загрузка маппингов языков
        config_language_mode_gui = self.interface_config["LanguageModeGUI"]
        
        self.INTERFACE_KEY_NAME_MAP = {
            'Русский': 'ru',
            '简体中文': 'ch',
            '繁體中文': 'chinese_cht',
            'English': 'en',
            '한국어': 'ko',
            '日本語': 'japan',
            'Tiếng Việt': 'vi',
            'Español': 'es'
        }
        
        self.LANGUAGE_NAME_KEY_MAP = {}
        for lang in backend.main.config.MULTI_LANG:
            lang_key = f"Language{lang.upper()}"
            if lang_key in config_language_mode_gui:
                self.LANGUAGE_NAME_KEY_MAP[config_language_mode_gui[lang_key]] = lang
        
        self.LANGUAGE_NAME_KEY_MAP = dict(sorted(self.LANGUAGE_NAME_KEY_MAP.items(), key=lambda item: item[1]))
        self.LANGUAGE_KEY_NAME_MAP = {v: k for k, v in self.LANGUAGE_NAME_KEY_MAP.items()}
        
        self.MODE_NAME_KEY_MAP = {
            config_language_mode_gui['ModeAuto']: 'auto',
            config_language_mode_gui['ModeFast']: 'fast',
            config_language_mode_gui['ModeAccurate']: 'accurate',
        }
        self.MODE_KEY_NAME_MAP = {v: k for k, v in self.MODE_NAME_KEY_MAP.items()}

    def _create_widgets(self):
        main_frame = ttk.Frame(self.window, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Загрузка текущих настроек
        interface_def, language_def, mode_def = self._parse_config()
        
        # Язык интерфейса
        ttk.Label(main_frame, text=self.interface_config["LanguageModeGUI"]["InterfaceLanguage"]).grid(
            row=0, column=0, sticky=tk.W, pady=(0, 10))
        
        self.interface_var = tk.StringVar(value=interface_def)
        interface_combo = ttk.Combobox(main_frame, textvariable=self.interface_var, 
                                      values=list(self.INTERFACE_KEY_NAME_MAP.keys()),
                                      state="readonly", width=30)
        interface_combo.grid(row=0, column=1, pady=(0, 10), padx=(10, 0))
        
        # Язык субтитров
        ttk.Label(main_frame, text=self.interface_config["LanguageModeGUI"]["SubtitleLanguage"]).grid(
            row=1, column=0, sticky=tk.W, pady=(0, 10))
        
        self.language_var = tk.StringVar(value=language_def)
        language_combo = ttk.Combobox(main_frame, textvariable=self.language_var,
                                     values=list(self.LANGUAGE_NAME_KEY_MAP.keys()),
                                     state="readonly", width=30)
        language_combo.grid(row=1, column=1, pady=(0, 10), padx=(10, 0))
        
        # Режим распознавания
        ttk.Label(main_frame, text=self.interface_config["LanguageModeGUI"]["Mode"]).grid(
            row=2, column=0, sticky=tk.W, pady=(0, 10))
        
        self.mode_var = tk.StringVar(value=mode_def)
        mode_combo = ttk.Combobox(main_frame, textvariable=self.mode_var,
                                 values=list(self.MODE_NAME_KEY_MAP.keys()),
                                 state="readonly", width=30)
        mode_combo.grid(row=2, column=1, pady=(0, 10), padx=(10, 0))
        
        # Кнопки
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, columnspan=2, pady=(20, 0))
        
        ttk.Button(button_frame, text="OK", command=self._save_settings).grid(row=0, column=0, padx=(0, 10))
        ttk.Button(button_frame, text="Отмена", command=self.window.destroy).grid(row=0, column=1)
        
        # Настройка весов
        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)

    def _save_settings(self):
        interface = self.interface_var.get()
        language_name = self.language_var.get()
        mode_name = self.mode_var.get()
        
        if (interface in self.INTERFACE_KEY_NAME_MAP and 
            language_name in self.LANGUAGE_NAME_KEY_MAP and
            mode_name in self.MODE_NAME_KEY_MAP):
            
            language = self.LANGUAGE_NAME_KEY_MAP[language_name]
            mode = self.MODE_NAME_KEY_MAP[mode_name]
            
            # Сохранение настроек
            config_file = os.path.join(os.path.dirname(__file__), 'settings.ini')
            with open(config_file, mode='w', encoding='utf-8') as f:
                f.write('[DEFAULT]\n')
                f.write(f'Interface = {interface}\n')
                f.write(f'Language = {language}\n')
                f.write(f'Mode = {mode}\n')
            
            # Обновление родительского GUI
            self.parent.update_interface_text()
            
            self.window.destroy()
        else:
            messagebox.showerror("Ошибка", "Пожалуйста, выберите корректные значения")

    def _parse_config(self):
        config_file = os.path.join(os.path.dirname(__file__), 'settings.ini')
        
        if not os.path.exists(config_file):
            interface_def = self.interface_config['LanguageModeGUI']['InterfaceDefault']
            language_def = self.interface_config['LanguageModeGUI']['LanguageRU']
            mode_def = self.interface_config['LanguageModeGUI']['ModeFast']
            return interface_def, language_def, mode_def
        
        config = configparser.ConfigParser()
        config.read(config_file, encoding='utf-8')
        
        interface = config['DEFAULT']['Interface']
        language = config['DEFAULT']['Language']
        mode = config['DEFAULT']['Mode']
        
        interface_def = interface if interface in self.INTERFACE_KEY_NAME_MAP else \
            self.interface_config['LanguageModeGUI']['InterfaceDefault']
        
        language_def = self.LANGUAGE_KEY_NAME_MAP.get(language, 
            self.interface_config['LanguageModeGUI']['LanguageRU'])
        
        mode_def = self.MODE_KEY_NAME_MAP.get(mode, 
            self.interface_config['LanguageModeGUI']['ModeFast'])
        
        return interface_def, language_def, mode_def

    def show(self):
        self.window.wait_window()


if __name__ == '__main__':
    try:
        multiprocessing.set_start_method("spawn")
        # Запуск графического интерфейса
        app = SubtitleExtractorGUI()
        app.run()
    except Exception as e:
        print(f'[{type(e)}] {e}')
        import traceback
        traceback.print_exc()
        msg = traceback.format_exc()
        err_log_path = os.path.join(os.path.expanduser('~'), 'VSE-Error-Message.log')
        with open(err_log_path, 'w', encoding='utf-8') as f:
            f.writelines(msg)
        import platform
        if platform.system() == 'Windows':
            os.system('pause')
        else:
            input()
