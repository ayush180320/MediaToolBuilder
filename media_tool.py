import sys
import os
import time
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QPushButton, QTabWidget, QLineEdit, QComboBox, 
                             QMessageBox, QFileDialog, QRadioButton, QProgressBar, 
                             QGroupBox, QStatusBar, QSplashScreen)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import (QPixmap, QImage, QDragEnterEvent, QDropEvent, QFont, 
                         QPainter, QPen, QColor, QKeySequence, QShortcut)
from PIL import Image, ImageFilter
from psd_tools import PSDImage

# --- CONFIGURATION ---
ASSET_DIR = os.path.dirname(os.path.abspath(__file__))
VERSION = "v15.0"
# NOTE: This name still appears in the 'About' popup (Ctrl+Alt+A), 
# but I have removed it from the Splash Screen as requested.
COPYRIGHT_OWNER = "Ayush Singhal" 
YEAR = "2026"

# --- WORKER THREAD ---
class BatchProcessor(QThread):
    progress_signal = pyqtSignal(int)
    status_signal = pyqtSignal(str) 
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
        
        folder_map = {
            "psd": "_Output_Converted",
            "resize": "_Output_Resized",
            "banner": "_Output_Banners"
        }
        folder_name = folder_map.get(self.mode, "_Output_General")

        for index, f_path in enumerate(self.file_list):
            if not self._is_running: break
            try:
                base_name = os.path.basename(f_path)
                name_only = os.path.splitext(base_name)[0]
                self.status_signal.emit(f"Processing ({index+1}/{total}): {base_name}...")
                
                # Load Image
                if f_path.lower().endswith(".psd"):
                    psd = PSDImage.open(f_path)
                    img = psd.composite()
                    original_dpi = (72, 72)
                else:
                    img = Image.open(f_path)
                    original_dpi = img.info.get('dpi', (72, 72))

                out_dir = os.path.join(os.path.dirname(f_path), folder_name)
                os.makedirs(out_dir, exist_ok=True)
                final_name = name_only 

                # --- PROCESSORS ---
                if self.mode == "resize":
                    if self.settings['res'] == "Custom":
                        try:
                            w = int(self.settings['custom_w'])
                            h = int(self.settings['custom_h'])
                        except ValueError:
                            w, h = 1000, 1000 
                    else:
                        w, h = map(int, self.settings['res'].split('x'))
                    img = img.resize((w, h), Image.Resampling.LANCZOS)
                    final_name = f"{name_only}_{w}x{h}"

                elif self.mode == "banner":
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
                    
                    suf = "_2Day" if self.settings['ban_type'] == "2day" else "_3Day"
                    final_name = f"{base_for_banner}{suf}"

                save_path = os.path.join(out_dir, final_name + ".jpg")
                if img.mode in ("RGBA", "P"): img = img.convert("RGB")
                img.save(save_path, "JPEG", quality=100, subsampling=0, dpi=original_dpi)
                count += 1
                self.progress_signal.emit(int((index + 1) / total * 100))
            except Exception as e:
                print(f"Error processing {f_path}: {e}")

        self.status_signal.emit("Ready")
        self.finished_signal.emit(f"Batch Complete. {count} files saved to '{folder_name}'.")

# --- UI COMPONENTS ---
class DropZone(QLabel):
    def __init__(self, parent_app):
        super().__init__()
        self.parent_app = parent_app
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setText("\n\nDROP IMAGES HERE\n\n")
        self.setStyleSheet("""
            QLabel { border: 2px dashed #444; border-radius: 12px; color: #555; font-size: 14px; background-color: #161616; }
            QLabel:hover { border-color: #0078d7; color: #0078d7; background-color: #1a1a1a; }
        """)
        self.setAcceptDrops(True)
        self.setMinimumSize(350, 450)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls(): event.accept()
        else: event.ignore()

    def dropEvent(self, event: QDropEvent):
        files = [u.toLocalFile() for u in event.mimeData().urls()]
        self.parent_app.load_files(files)

# --- MAIN APP ---
class MediaStudioPro(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Media Workflow Studio Pro {VERSION}")
        self.resize(1200, 700) 
        self.setup_styles()

        # Secret Copyright (Ctrl+Alt+A)
        self.ghost_copy = QShortcut(QKeySequence("Ctrl+Alt+A"), self)
        self.ghost_copy.activated.connect(self.show_ghost_copyright)

        self.files = []
        self.current_preview_path = None

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(25, 25, 25, 25)
        main_layout.setSpacing(30)

        # LEFT PANEL
        left_panel = QWidget(); left_layout = QVBoxLayout(left_panel)
        left_panel.setFixedWidth(400)
        main_layout.addWidget(left_panel)

        lbl_head = QLabel("WORKFLOW TOOLS")
        lbl_head.setStyleSheet("color: #666; font-weight: bold; letter-spacing: 1px;")
        left_layout.addWidget(lbl_head)

        btn_add = QPushButton("Select Files from Disk")
        btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_add.setFixedHeight(50)
        btn_add.clicked.connect(self.open_file_dialog)
        left_layout.addWidget(btn_add)
        left_layout.addSpacing(15)

        self.tabs = QTabWidget()
        self.setup_tabs()
        self.tabs.currentChanged.connect(self.on_tab_changed)
        left_layout.addWidget(self.tabs)
        left_layout.addStretch()

        self.lbl_status = QLabel("Ready")
        self.lbl_status.setStyleSheet("color: #888;")
        left_layout.addWidget(self.lbl_status)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        left_layout.addWidget(self.progress)
        
        btn_reset = QPushButton("Clear Workspace")
        btn_reset.setObjectName("GhostBtn")
        btn_reset.clicked.connect(self.reset_workspace)
        left_layout.addWidget(btn_reset)

        # RIGHT PANEL
        right_panel = QWidget(); right_layout = QVBoxLayout(right_panel)
        main_layout.addWidget(right_panel)
        nav_layout = QHBoxLayout()
        nav_layout.addWidget(QLabel("PREVIEW:"))
        self.combo_files = QComboBox()
        self.combo_files.currentIndexChanged.connect(self.on_file_select)
        nav_layout.addWidget(self.combo_files, 1)
        right_layout.addLayout(nav_layout)
        
        self.drop_zone = DropZone(self)
        right_layout.addWidget(self.drop_zone, 1)
        
        self.info_group = QGroupBox()
        self.info_group.setStyleSheet("QGroupBox { border: 1px solid #333; border-radius: 8px; background: #1a1a1a; margin-top: 10px; }")
        ig_layout = QVBoxLayout(self.info_group)
        self.lbl_info = QLabel("No file selected.")
        self.lbl_info.setStyleSheet("color: #00aaff; font-family: Consolas; font-size: 12px;")
        ig_layout.addWidget(self.lbl_info)
        right_layout.addWidget(self.info_group)

        self.setStatusBar(QStatusBar(self))
        self.statusBar().showMessage("System Ready")

    def show_ghost_copyright(self):
        msg = QMessageBox(self)
        msg.setWindowTitle("Credits")
        msg.setText(f"<h3>Media Studio Pro {VERSION}</h3>"
                    f"<p>Copyright &copy; {YEAR} <b>{COPYRIGHT_OWNER}</b></p>"
                    "<p>All rights reserved.<br>Licensed to Ayush Singhal.</p>")
        msg.setStyleSheet("QMessageBox { background-color: #1a1a1a; } QLabel { color: #e0e0e0; } QPushButton { background: #0078d7; color: white; }")
        msg.exec()

    def setup_styles(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #0f0f0f; }
            QWidget { color: #e0e0e0; font-family: 'Segoe UI', sans-serif; font-size: 13px; }
            QPushButton { background-color: #2d2d2d; border: 1px solid #3d3d3d; border-radius: 6px; color: white; font-weight: 600; }
            QPushButton:hover { background-color: #3d3d3d; border-color: #555; }
            QPushButton:pressed { background-color: #0078d7; border-color: #0078d7; }
            QPushButton#GhostBtn { background: transparent; border: none; color: #666; text-align: left; }
            QPushButton#ActionBtn { background-color: #0078d7; border: none; }
            QTabWidget::pane { border: 1px solid #333; background: #1a1a1a; border-radius: 8px; }
            QTabBar::tab { background: #0f0f0f; padding: 12px 20px; color: #666; }
            QTabBar::tab:selected { background: #1a1a1a; color: white; border-bottom: 2px solid #0078d7; }
            QLineEdit, QComboBox { background: #222; border: 1px solid #333; padding: 8px; border-radius: 4px; color: white; }
            QProgressBar { border: none; background: #222; height: 4px; }
            QProgressBar::chunk { background: #0078d7; }
        """)

    def setup_tabs(self):
        def create_tab(title, desc):
            w = QWidget(); l = QVBoxLayout(w)
            l.setContentsMargins(20, 25, 20, 25)
            l.addWidget(QLabel(f"<span style='font-size:14px; font-weight:bold;'>{title}</span>"))
            l.addWidget(QLabel(f"<span style='color:#777;'>{desc}</span>"))
            l.addSpacing(15)
            return w, l

        # PSD
        t1, l1 = create_tab("PSD Converter", "Convert Photoshop files to JPG.")
        l1.addStretch()
        btn1 = QPushButton("Convert All PSDs"); btn1.setObjectName("ActionBtn"); btn1.setFixedHeight(40)
        btn1.clicked.connect(lambda: self.start_batch("psd"))
        l1.addWidget(btn1)
        self.tabs.addTab(t1, "PSD")

        # RESIZE
        t2, l2 = create_tab("Smart Resizer", "Resize images to standard dimensions.")
        l2.addWidget(QLabel("Select Output Size:"))
        
        self.combo_res = QComboBox()
        # --- ADDED NEW PRESETS HERE ---
        self.combo_res.addItems(["286x410", "380x560", "800x1200", "960x1440", "1920x1080", "Custom"])
        
        self.combo_res.currentTextChanged.connect(self.toggle_custom)
        l2.addWidget(self.combo_res)
        
        self.custom_box = QWidget(); hla = QHBoxLayout(self.custom_box); hla.setContentsMargins(0,0,0,0)
        self.ecw = QLineEdit(); self.ecw.setPlaceholderText("W")
        self.ech = QLineEdit(); self.ech.setPlaceholderText("H")
        hla.addWidget(QLabel("W:")); hla.addWidget(self.ecw); hla.addWidget(QLabel("H:")); hla.addWidget(self.ech)
        l2.addWidget(self.custom_box); self.custom_box.hide()
        
        l2.addStretch()
        btn2 = QPushButton("Process Resizing"); btn2.setObjectName("ActionBtn"); btn2.setFixedHeight(40)
        btn2.clicked.connect(lambda: self.start_batch("resize"))
        l2.addWidget(btn2)
        self.tabs.addTab(t2, "Resize")

        # BANNER
        t3, l3 = create_tab("HD Banner Generator", "Add overlays and rename.")
        self.rad_2day = QRadioButton("2-Day Banner"); self.rad_3day = QRadioButton("3-Day Banner")
        self.rad_2day.setChecked(True); self.rad_2day.toggled.connect(self.refresh_preview)
        l3.addWidget(self.rad_2day); l3.addWidget(self.rad_3day)
        
        rn_grp = QGroupBox("Custom Rename"); rn_grp.setStyleSheet("color:#888; font-weight:bold; padding-top:15px;")
        rnl = QVBoxLayout(rn_grp)
        self.entry_rename = QLineEdit(); self.entry_rename.setPlaceholderText("e.g., Summer_Sale")
        self.entry_rename.textChanged.connect(self.refresh_preview)
        rnl.addWidget(self.entry_rename)
        l3.addWidget(rn_grp); l3.addStretch()
        
        btn3 = QPushButton("Generate Banners"); btn3.setObjectName("ActionBtn"); btn3.setFixedHeight(40)
        btn3.clicked.connect(lambda: self.start_batch("banner"))
        l3.addWidget(btn3)
        self.tabs.addTab(t3, "Banner")

    def toggle_custom(self, txt):
        if txt == "Custom": self.custom_box.show()
        else: self.custom_box.hide()

    def on_tab_changed(self):
        self.reset_workspace()

    def open_file_dialog(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Images", "", "Images (*.jpg *.png *.psd)")
        if files: self.load_files(files)

    def load_files(self, paths):
        valid = [f for f in paths if os.path.isfile(f)]
        if not valid: return
        self.files = valid
        self.combo_files.blockSignals(True)
        self.combo_files.clear()
        self.combo_files.addItems([os.path.basename(f) for f in valid])
        self.combo_files.blockSignals(False)
        self.combo_files.setCurrentIndex(0)
        self.on_file_select(0)
        self.statusBar().showMessage(f"Loaded {len(valid)} files.")

    def on_file_select(self, index):
        if self.files and index >= 0:
            self.current_preview_path = self.files[index]
            self.entry_rename.clear()
            self.refresh_preview()

    def refresh_preview(self):
        if not self.current_preview_path: return
        path = self.current_preview_path
        try:
            size_mb = os.path.getsize(path) / (1024*1024)
            img_tmp = Image.open(path)
            self.lbl_info.setText(f"NAME: {os.path.basename(path)}\nSIZE: {size_mb:.2f} MB\nDIM : {img_tmp.width} x {img_tmp.height}")
        except: self.lbl_info.setText("Reading...")

        try:
            if path.lower().endswith(".psd"): img = PSDImage.open(path).composite()
            else: img = Image.open(path)
            
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
            
            img.thumbnail((450, 550), Image.Resampling.LANCZOS)
            if img.mode == "RGB": img = img.convert("RGBA")
            qim = QImage(img.tobytes("raw", "RGBA"), img.size[0], img.size[1], QImage.Format.Format_RGBA8888)
            self.drop_zone.setPixmap(QPixmap.fromImage(qim))
            self.drop_zone.setText("")
        except: self.drop_zone.setText("Preview unavailable.")

    def start_batch(self, mode):
        if not self.files: return QMessageBox.warning(self, "No Files", "Select files first.")
        settings = {"res": self.combo_res.currentText(), "ban_type": "2day" if self.rad_2day.isChecked() else "3day", 
                    "custom_name": self.entry_rename.text(), "custom_w": self.ecw.text(), "custom_h": self.ech.text()}
        self.worker = BatchProcessor(mode, self.files, settings)
        self.worker.progress_signal.connect(self.progress.setValue)
        self.worker.status_signal.connect(self.lbl_status.setText)
        self.worker.finished_signal.connect(lambda m: QMessageBox.information(self, "Success", m))
        self.worker.start()

    def reset_workspace(self):
        self.files = []; self.combo_files.clear(); self.entry_rename.clear()
        self.drop_zone.setPixmap(QPixmap()); self.drop_zone.setText("\n\nDROP IMAGES HERE\n\n")
        self.lbl_info.setText("No file selected."); self.progress.setValue(0); self.lbl_status.setText("Cleared")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    splash_pix = QPixmap(os.path.join(ASSET_DIR, "splash_logo.png"))
    if splash_pix.isNull():
        splash_pix = QPixmap(600, 350); splash_pix.fill(QColor("#0f0f0f"))
        p = QPainter(splash_pix); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor("#333"), 6)); p.drawRect(0, 0, 600, 350)
        p.setPen(QColor("#0078d7")); p.setFont(QFont("Segoe UI", 36, QFont.Weight.Bold)); p.drawText(splash_pix.rect(), Qt.AlignmentFlag.AlignCenter, "MEDIA STUDIO")
        
        # --- SPLASH SCREEN CHANGED HERE ---
        # Removed "COPYRIGHT_OWNER" from the visual splash display. 
        # It now reads "Industry Edition".
        p.setPen(QColor("#666")); p.setFont(QFont("Consolas", 10)); p.drawText(0, 200, 600, 50, Qt.AlignmentFlag.AlignCenter, f"{VERSION} | Industry Edition")
        p.end()

    splash = QSplashScreen(splash_pix, Qt.WindowType.WindowStaysOnTopHint); splash.show()
    for msg in ["Loading Core...", "Initializing...", "Starting..."]:
        splash.showMessage(f"\n\n\n{msg}", Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter, Qt.GlobalColor.white)
        time.sleep(0.5); app.processEvents()

    window = MediaStudioPro()
    window.showMaximized() 
    splash.finish(window)
    sys.exit(app.exec())
