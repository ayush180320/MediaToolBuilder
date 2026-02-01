import sys
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QPushButton, QTabWidget, QTextEdit, QLineEdit, 
                             QComboBox, QMessageBox, QFileDialog, QRadioButton, 
                             QProgressBar, QFrame, QSizePolicy, QGroupBox)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QPixmap, QImage, QDragEnterEvent, QDropEvent, QColor, QPalette, QFont
from PIL import Image, ImageFilter
from psd_tools import PSDImage

#Path to assets (Banner overlays)
ASSET_DIR = os.path.dirname(os.path.abspath(__file__))

# --- WORKER THREAD (Background Processing) ---
class BatchProcessor(QThread):
    progress_signal = pyqtSignal(int)
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(str)

    def __init__(self, mode, file_list, settings):
        super().__init__()
        self.mode = mode
        self.file_list = file_list
        self.settings = settings
        self._is_running = True

    def run(self):
        count = 0
        total = len(self.file_list)
        
        for index, f_path in enumerate(self.file_list):
            if not self._is_running: break
            
            try:
                base_name = os.path.basename(f_path)
                name_only = os.path.splitext(base_name)[0]
                self.log_signal.emit(f"Processing: {base_name}...")
                
                # 1. Open & Capture Metadata
                if f_path.lower().endswith(".psd"):
                    psd = PSDImage.open(f_path)
                    img = psd.composite()
                    original_dpi = (72, 72)
                else:
                    img = Image.open(f_path)
                    original_dpi = img.info.get('dpi', (72, 72))

                # 2. Operations & Naming
                out_dir = os.path.join(os.path.dirname(f_path), "Processed_Output")
                os.makedirs(out_dir, exist_ok=True)
                final_name = name_only 

                # --- MODE: RESIZE ---
                if self.mode == "resize":
                    w, h = map(int, self.settings['res'].split('x'))
                    img = img.resize((w, h), Image.Resampling.LANCZOS)
                    final_name = f"{name_only}_{w}x{h}"

                # --- MODE: BANNER ---
                elif self.mode == "banner":
                    # Use Custom Name if provided, else original
                    custom_name = self.settings.get('custom_name', '').strip()
                    base_for_banner = custom_name if custom_name else name_only
                    
                    img = img.resize((286, 371), Image.Resampling.LANCZOS)
                    img = img.filter(ImageFilter.UnsharpMask(radius=0.8, percent=110, threshold=3))
                    
                    canvas = Image.new("RGB", (286, 410), (255, 255, 255))
                    canvas.paste(img, (0,0))
                    
                    tpl_name = "banner_2day.png" if self.settings['ban_type'] == "2day" else "banner_3day.png"
                    tpl_path = os.path.join(ASSET_DIR, tpl_name)
                    
                    if os.path.exists(tpl_path):
                        ovl = Image.open(tpl_path).convert("RGBA").resize((286, 410), Image.Resampling.LANCZOS)
                        canvas.paste(ovl, (0,0), mask=ovl)
                        img = canvas
                    
                    suf = "_2DayBanner" if self.settings['ban_type'] == "2day" else "_3DayBanner"
                    final_name = f"{base_for_banner}{suf}"

                # 3. Save
                save_path = os.path.join(out_dir, final_name + ".jpg")
                if img.mode in ("RGBA", "P"): img = img.convert("RGB")
                img.save(save_path, "JPEG", quality=100, subsampling=0, dpi=original_dpi)
                
                count += 1
                self.progress_signal.emit(int((index + 1) / total * 100))

            except Exception as e:
                self.log_signal.emit(f"Error: {str(e)}")

        self.finished_signal.emit(f"Batch Complete. {count}/{total} files processed.")

# --- CUSTOM PREVIEW WIDGET ---
class DropZone(QLabel):
    def __init__(self, parent_app):
        super().__init__()
        self.parent_app = parent_app
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setText("\n\nDRAG FILES HERE\n\n")
        self.setStyleSheet("""
            QLabel {
                border: 2px dashed #444;
                border-radius: 8px;
                color: #555;
                font-size: 14px;
                background-color: #1a1a1a;
            }
            QLabel:hover { border-color: #0078d7; color: #0078d7; background-color: #202020; }
        """)
        self.setAcceptDrops(True)
        self.setMinimumSize(350, 450)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls(): event.accept()
        else: event.ignore()

    def dropEvent(self, event: QDropEvent):
        files = [u.toLocalFile() for u in event.mimeData().urls()]
        self.parent_app.load_files(files)

# --- MAIN WINDOW ---
class MediaStudioPro(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Media Workflow Studio Pro v11")
        self.resize(1150, 780)
        self.setup_theme()

        self.files = []
        self.current_preview_path = None

        # --- MAIN LAYOUT ---
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(25)

        # ================= LEFT PANEL (CONTROLS) =================
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_panel.setFixedWidth(380)
        main_layout.addWidget(left_panel)

        # 1. Add Files Button
        btn_add = QPushButton("  + Add Files  ")
        btn_add.setFixedHeight(45)
        btn_add.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        btn_add.setStyleSheet("""
            QPushButton { background-color: #0078d7; color: white; border-radius: 6px; }
            QPushButton:hover { background-color: #0063b1; }
        """)
        btn_add.clicked.connect(self.open_file_dialog)
        left_layout.addWidget(btn_add)
        
        left_layout.addSpacing(10)

        # 2. Tabs
        self.tabs = QTabWidget()
        self.setup_tabs()
        left_layout.addWidget(self.tabs)
        
        # 3. Progress & Reset
        left_layout.addStretch()
        self.progress = QProgressBar()
        self.progress.setStyleSheet("QProgressBar { border: 0px; height: 6px; background: #333; } QProgressBar::chunk { background: #0078d7; }")
        left_layout.addWidget(self.progress)
        
        btn_reset = QPushButton("Reset Workspace")
        btn_reset.setStyleSheet("background: transparent; color: #666; text-align: left;")
        btn_reset.clicked.connect(self.reset_workspace)
        left_layout.addWidget(btn_reset)

        # ================= RIGHT PANEL (PREVIEW) =================
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        main_layout.addWidget(right_panel)

        # Navigator
        self.combo_files = QComboBox()
        self.combo_files.setStyleSheet("padding: 8px; bg: #222;")
        self.combo_files.currentIndexChanged.connect(self.on_file_select)
        right_layout.addWidget(self.combo_files)

        # Preview Image
        self.drop_zone = DropZone(self)
        right_layout.addWidget(self.drop_zone, 1) # Expandable

        # File Info Panel (Strictly Info)
        info_group = QGroupBox("FILE INFORMATION")
        info_group.setStyleSheet("QGroupBox { color: #888; border: 1px solid #333; margin-top: 10px; font-weight: bold; }")
        ig_layout = QVBoxLayout(info_group)
        
        self.info_box = QLabel("No file loaded.")
        self.info_box.setFont(QFont("Consolas", 10))
        self.info_box.setStyleSheet("color: #00E5FF; padding: 5px;")
        ig_layout.addWidget(self.info_box)
        
        right_layout.addWidget(info_group)

    def setup_theme(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #121212; }
            QWidget { color: #e0e0e0; font-family: 'Segoe UI', sans-serif; }
            QTabWidget::pane { border: 1px solid #333; background: #1e1e1e; border-radius: 6px; top: -1px; }
            QTabBar::tab { background: #2b2b2b; padding: 10px 20px; color: #888; border-top-left-radius: 6px; border-top-right-radius: 6px; margin-right: 2px; }
            QTabBar::tab:selected { background: #1e1e1e; color: white; border-bottom: 2px solid #0078d7; }
            QLineEdit { background: #252525; border: 1px solid #444; padding: 8px; color: white; border-radius: 4px; }
            QComboBox { background: #252525; border: 1px solid #444; padding: 5px; color: white; }
        """)

    def setup_tabs(self):
        # --- TAB 1: PSD ---
        t_psd = QWidget()
        l_psd = QVBoxLayout(t_psd)
        l_psd.setContentsMargins(20, 20, 20, 20)
        l_psd.addWidget(QLabel("<b>PSD Bulk Converter</b>\n\nConverts PSDs to High-Res JPGs.\nOriginal filename is preserved."))
        l_psd.addStretch()
        btn_psd = QPushButton("Start Conversion")
        btn_psd.setFixedHeight(40)
        btn_psd.setStyleSheet("background-color: #28a745; color: white; border-radius: 4px; font-weight: bold;")
        btn_psd.clicked.connect(lambda: self.start_batch("psd"))
        l_psd.addWidget(btn_psd)
        self.tabs.addTab(t_psd, "PSD")

        # --- TAB 2: RESIZE ---
        t_res = QWidget()
        l_res = QVBoxLayout(t_res)
        l_res.setContentsMargins(20, 20, 20, 20)
        l_res.addWidget(QLabel("<b>Smart Resizer</b>"))
        
        l_res.addWidget(QLabel("Target Dimension:"))
        self.combo_res = QComboBox()
        self.combo_res.addItems(["286x410", "960x1440", "1920x1080", "380x560"])
        l_res.addWidget(self.combo_res)
        
        l_res.addStretch()
        btn_res = QPushButton("Resize All")
        btn_res.setFixedHeight(40)
        btn_res.setStyleSheet("background-color: #28a745; color: white; border-radius: 4px; font-weight: bold;")
        btn_res.clicked.connect(lambda: self.start_batch("resize"))
        l_res.addWidget(btn_res)
        self.tabs.addTab(t_res, "Resize")

        # --- TAB 3: BANNER (With Rename) ---
        t_ban = QWidget()
        l_ban = QVBoxLayout(t_ban)
        l_ban.setContentsMargins(20, 20, 20, 20)
        l_ban.addWidget(QLabel("<b>HD Banner & Rename</b>"))
        
        # Banner Type
        self.rad_2day = QRadioButton("2-Day Banner")
        self.rad_3day = QRadioButton("3-Day Banner")
        self.rad_2day.setChecked(True)
        self.rad_2day.toggled.connect(self.refresh_preview)
        l_ban.addWidget(self.rad_2day)
        l_ban.addWidget(self.rad_3day)
        
        l_ban.addSpacing(15)
        
        # RENAME SECTION (Only here)
        rename_frame = QFrame()
        rename_frame.setStyleSheet("background: #252525; border-radius: 5px; border: 1px solid #333;")
        rf_layout = QVBoxLayout(rename_frame)
        rf_layout.addWidget(QLabel("RENAME FILE (Optional)"))
        self.entry_rename = QLineEdit()
        self.entry_rename.setPlaceholderText("Enter new name...")
        self.entry_rename.textChanged.connect(self.refresh_preview) # Live update preview if needed
        rf_layout.addWidget(self.entry_rename)
        l_ban.addWidget(rename_frame)

        l_ban.addStretch()
        btn_ban = QPushButton("Generate Banners")
        btn_ban.setFixedHeight(40)
        btn_ban.setStyleSheet("background-color: #28a745; color: white; border-radius: 4px; font-weight: bold;")
        btn_ban.clicked.connect(lambda: self.start_batch("banner"))
        l_ban.addWidget(btn_ban)
        self.tabs.addTab(t_ban, "HD Banner")

    # ================= LOGIC =================
    def open_file_dialog(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Images", "", "Files (*.jpg *.png *.jpeg *.psd)")
        if files: self.load_files(files)

    def load_files(self, paths):
        valid = [f for f in paths if os.path.isfile(f)]
        if not valid: return
        self.files = valid
        self.combo_files.clear()
        self.combo_files.addItems([os.path.basename(f) for f in valid])
        self.combo_files.setCurrentIndex(0)

    def on_file_select(self, index):
        if index >= 0:
            self.current_preview_path = self.files[index]
            # Clear rename box when switching files (optional, keeps it clean)
            self.entry_rename.clear() 
            self.refresh_preview()

    def refresh_preview(self):
        if not self.current_preview_path: return
        
        path = self.current_preview_path
        
        # 1. Update Info Box
        try:
            size_mb = os.path.getsize(path) / (1024*1024)
            img_tmp = Image.open(path)
            dpi = img_tmp.info.get('dpi', (72,72))
            info_txt = (f"File: {os.path.basename(path)}\n"
                        f"Size: {size_mb:.2f} MB\n"
                        f"Dim:  {img_tmp.width} x {img_tmp.height} px\n"
                        f"DPI:  {int(dpi[0])}")
            self.info_box.setText(info_txt)
        except: 
            self.info_box.setText("Reading info...")

        # 2. Generate Image
        try:
            if path.lower().endswith(".psd"):
                img = PSDImage.open(path).composite()
            else:
                img = Image.open(path)

            # If Banner Tab active -> Apply Banner Overlay Preview
            if self.tabs.currentIndex() == 2:
                img = img.resize((286, 371), Image.Resampling.LANCZOS)
                canvas = Image.new("RGB", (286, 410), (255, 255, 255))
                canvas.paste(img, (0,0))
                
                tpl = "banner_2day.png" if self.rad_2day.isChecked() else "banner_3day.png"
                tpl_path = os.path.join(ASSET_DIR, tpl)
                if os.path.exists(tpl_path):
                    ovl = Image.open(tpl_path).convert("RGBA").resize((286, 410), Image.Resampling.LANCZOS)
                    canvas.paste(ovl, (0,0), mask=ovl)
                    img = canvas

            img.thumbnail((400, 500), Image.Resampling.LANCZOS)
            if img.mode == "RGB": img = img.convert("RGBA")
            
            data = img.tobytes("raw", "RGBA")
            qim = QImage(data, img.size[0], img.size[1], QImage.Format.Format_RGBA8888)
            self.drop_zone.setPixmap(QPixmap.fromImage(qim))
            self.drop_zone.setText("")
        except Exception as e:
            self.drop_zone.setText("Preview Error")

    def start_batch(self, mode):
        if not self.files: return QMessageBox.warning(self, "Info", "Please add files first.")
        
        settings = {
            "res": self.combo_res.currentText(),
            "ban_type": "2day" if self.rad_2day.isChecked() else "3day",
            "custom_name": self.entry_rename.text() # Only used in banner mode
        }

        self.worker = BatchProcessor(mode, self.files, settings)
        self.worker.progress_signal.connect(self.progress.setValue)
        self.worker.finished_signal.connect(lambda m: QMessageBox.information(self, "Done", m))
        self.worker.start()
        self.progress.setValue(0)

    def reset_workspace(self):
        self.files = []
        self.combo_files.clear()
        self.entry_rename.clear()
        self.drop_zone.setPixmap(QPixmap())
        self.drop_zone.setText("\n\nDRAG FILES HERE\n\n")
        self.info_box.setText("No file loaded.")
        self.progress.setValue(0)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MediaStudioPro()
    window.show()
    sys.exit(app.exec())
