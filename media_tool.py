import sys
import os
import shutil
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QPushButton, QTabWidget, QLineEdit, QComboBox, 
                             QMessageBox, QFileDialog, QRadioButton, QProgressBar, 
                             QFrame, QGroupBox, QStatusBar)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QPixmap, QImage, QDragEnterEvent, QDropEvent, QFont, QIcon, QAction
from PIL import Image, ImageFilter
from psd_tools import PSDImage

# --- CONFIGURATION ---
ASSET_DIR = os.path.dirname(os.path.abspath(__file__))
VERSION = "v12.0 Stable"

# --- WORKER THREAD ---
class BatchProcessor(QThread):
    progress_signal = pyqtSignal(int)
    status_signal = pyqtSignal(str) # For status bar updates
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
        
        # 1. Define Output Folder based on Mode
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
                
                # Input Handling
                if f_path.lower().endswith(".psd"):
                    psd = PSDImage.open(f_path)
                    img = psd.composite()
                    original_dpi = (72, 72)
                else:
                    img = Image.open(f_path)
                    original_dpi = img.info.get('dpi', (72, 72))

                # Create Output Directory (Relative to input file)
                out_dir = os.path.join(os.path.dirname(f_path), folder_name)
                os.makedirs(out_dir, exist_ok=True)
                
                final_name = name_only 

                # --- PROCESSORS ---
                if self.mode == "resize":
                    w, h = map(int, self.settings['res'].split('x'))
                    img = img.resize((w, h), Image.Resampling.LANCZOS)
                    final_name = f"{name_only}_{w}x{h}"

                elif self.mode == "banner":
                    custom_name = self.settings.get('custom_name', '').strip()
                    base_for_banner = custom_name if custom_name else name_only
                    
                    # 1. Resize & Sharpen
                    img = img.resize((286, 371), Image.Resampling.LANCZOS)
                    img = img.filter(ImageFilter.UnsharpMask(radius=0.8, percent=110, threshold=3))
                    
                    # 2. Canvas
                    canvas = Image.new("RGB", (286, 410), (255, 255, 255))
                    canvas.paste(img, (0,0))
                    
                    # 3. Overlay
                    tpl_name = "banner_2day.png" if self.settings['ban_type'] == "2day" else "banner_3day.png"
                    tpl_path = os.path.join(ASSET_DIR, tpl_name)
                    
                    if os.path.exists(tpl_path):
                        ovl = Image.open(tpl_path).convert("RGBA").resize((286, 410), Image.Resampling.LANCZOS)
                        canvas.paste(ovl, (0,0), mask=ovl)
                        img = canvas
                    
                    suf = "_2Day" if self.settings['ban_type'] == "2day" else "_3Day"
                    final_name = f"{base_for_banner}{suf}"

                # Save
                save_path = os.path.join(out_dir, final_name + ".jpg")
                if img.mode in ("RGBA", "P"): img = img.convert("RGB")
                img.save(save_path, "JPEG", quality=100, subsampling=0, dpi=original_dpi)
                
                count += 1
                self.progress_signal.emit(int((index + 1) / total * 100))

            except Exception as e:
                print(f"Error: {e}")

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
            QLabel {
                border: 2px dashed #444;
                border-radius: 12px;
                color: #555;
                font-size: 14px;
                background-color: #161616;
            }
            QLabel:hover {
                border-color: #0078d7;
                color: #0078d7;
                background-color: #1a1a1a;
            }
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
        self.resize(1180, 800)
        self.setup_styles()

        self.files = []
        self.current_preview_path = None

        # --- UI CONSTRUCTION ---
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(25, 25, 25, 25)
        main_layout.setSpacing(30)

        # === LEFT COLUMN (CONTROLS) ===
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_panel.setFixedWidth(400)
        main_layout.addWidget(left_panel)

        # Header
        lbl_head = QLabel("WORKFLOW TOOLS")
        lbl_head.setStyleSheet("color: #666; font-weight: bold; letter-spacing: 1px;")
        left_layout.addWidget(lbl_head)

        # Add Files Button
        btn_add = QPushButton("Select Files from Disk")
        btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_add.setFixedHeight(50)
        btn_add.clicked.connect(self.open_file_dialog)
        left_layout.addWidget(btn_add)
        
        left_layout.addSpacing(15)

        # Tabs
        self.tabs = QTabWidget()
        self.setup_tabs()
        left_layout.addWidget(self.tabs)
        
        left_layout.addStretch()

        # Progress Section
        self.lbl_status = QLabel("Ready")
        self.lbl_status.setStyleSheet("color: #888;")
        left_layout.addWidget(self.lbl_status)
        
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        left_layout.addWidget(self.progress)
        
        btn_reset = QPushButton("Clear Workspace")
        btn_reset.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_reset.setObjectName("GhostBtn")
        btn_reset.clicked.connect(self.reset_workspace)
        left_layout.addWidget(btn_reset)

        # === RIGHT COLUMN (PREVIEW) ===
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        main_layout.addWidget(right_panel)

        # Navigator
        nav_layout = QHBoxLayout()
        nav_layout.addWidget(QLabel("PREVIEW:"))
        self.combo_files = QComboBox()
        self.combo_files.currentIndexChanged.connect(self.on_file_select)
        nav_layout.addWidget(self.combo_files, 1)
        right_layout.addLayout(nav_layout)

        # Image Area
        self.drop_zone = DropZone(self)
        right_layout.addWidget(self.drop_zone, 1)

        # Info Box
        self.info_group = QGroupBox()
        self.info_group.setStyleSheet("""
            QGroupBox { border: 1px solid #333; border-radius: 8px; background: #1a1a1a; margin-top: 10px; }
        """)
        ig_layout = QVBoxLayout(self.info_group)
        self.lbl_info = QLabel("No file selected.")
        self.lbl_info.setStyleSheet("color: #00aaff; font-family: Consolas; font-size: 12px;")
        ig_layout.addWidget(self.lbl_info)
        right_layout.addWidget(self.info_group)

        # Status Bar
        self.setStatusBar(QStatusBar(self))
        self.statusBar().showMessage("System Ready")

    def setup_styles(self):
        # Professional Dark Theme (CSS)
        self.setStyleSheet("""
            QMainWindow { background-color: #0f0f0f; }
            QWidget { color: #e0e0e0; font-family: 'Segoe UI', sans-serif; font-size: 13px; }
            
            /* Buttons */
            QPushButton { 
                background-color: #2d2d2d; 
                border: 1px solid #3d3d3d; 
                border-radius: 6px; 
                color: white; 
                font-weight: 600;
            }
            QPushButton:hover { background-color: #3d3d3d; border-color: #555; }
            QPushButton:pressed { background-color: #0078d7; border-color: #0078d7; }
            
            QPushButton#GhostBtn { background: transparent; border: none; color: #666; text-align: left; }
            QPushButton#GhostBtn:hover { color: #888; }
            
            QPushButton#ActionBtn { background-color: #0078d7; border: none; }
            QPushButton#ActionBtn:hover { background-color: #008ae6; }

            /* Tabs */
            QTabWidget::pane { border: 1px solid #333; background: #1a1a1a; border-radius: 8px; }
            QTabBar::tab { background: #0f0f0f; padding: 12px 20px; color: #666; border-top-left-radius: 6px; border-top-right-radius: 6px; }
            QTabBar::tab:selected { background: #1a1a1a; color: white; border-bottom: 2px solid #0078d7; }
            
            /* Inputs */
            QLineEdit, QComboBox { background: #222; border: 1px solid #333; padding: 8px; border-radius: 4px; color: white; }
            QComboBox::drop-down { border: none; }
            
            /* Progress */
            QProgressBar { border: none; background: #222; height: 4px; border-radius: 2px; }
            QProgressBar::chunk { background: #0078d7; border-radius: 2px; }
        """)

    def setup_tabs(self):
        # Helper to create consistent tab layouts
        def create_tab_layout(title, desc):
            w = QWidget()
            l = QVBoxLayout(w)
            l.setContentsMargins(20, 25, 20, 25)
            l.addWidget(QLabel(f"<span style='font-size:14px; font-weight:bold;'>{title}</span>"))
            l.addWidget(QLabel(f"<span style='color:#777;'>{desc}</span>"))
            l.addSpacing(15)
            return w, l

        # TAB 1: PSD
        t1, l1 = create_tab_layout("PSD Converter", "Convert Photoshop files to JPG.\nFolder: /_Output_Converted")
        l1.addStretch()
        btn1 = QPushButton("Convert All PSDs")
        btn1.setObjectName("ActionBtn"); btn1.setFixedHeight(40)
        btn1.clicked.connect(lambda: self.start_batch("psd"))
        l1.addWidget(btn1)
        self.tabs.addTab(t1, "PSD")

        # TAB 2: RESIZE
        t2, l2 = create_tab_layout("Smart Resizer", "Resize images to standard dimensions.\nFolder: /_Output_Resized")
        l2.addWidget(QLabel("Select Output Size:"))
        self.combo_res = QComboBox()
        self.combo_res.addItems(["286x410", "960x1440", "1920x1080", "380x560"])
        l2.addWidget(self.combo_res)
        l2.addStretch()
        btn2 = QPushButton("Process Resizing")
        btn2.setObjectName("ActionBtn"); btn2.setFixedHeight(40)
        btn2.clicked.connect(lambda: self.start_batch("resize"))
        l2.addWidget(btn2)
        self.tabs.addTab(t2, "Resize")

        # TAB 3: BANNER
        t3, l3 = create_tab_layout("HD Banner Generator", "Add overlays and rename.\nFolder: /_Output_Banners")
        self.rad_2day = QRadioButton("2-Day Banner Overlay")
        self.rad_3day = QRadioButton("3-Day Banner Overlay")
        self.rad_2day.setChecked(True)
        self.rad_2day.toggled.connect(self.refresh_preview)
        l3.addWidget(self.rad_2day)
        l3.addWidget(self.rad_3day)
        l3.addSpacing(15)
        
        # Rename Group
        rn_group = QGroupBox("Custom Rename (Optional)")
        rn_group.setStyleSheet("QGroupBox{border:1px solid #333; padding-top:15px; font-weight:bold; color:#888;}")
        rn_layout = QVBoxLayout(rn_group)
        self.entry_rename = QLineEdit()
        self.entry_rename.setPlaceholderText("e.g., Womens_Jacket_Red")
        self.entry_rename.textChanged.connect(self.refresh_preview)
        rn_layout.addWidget(self.entry_rename)
        l3.addWidget(rn_group)
        
        l3.addStretch()
        btn3 = QPushButton("Generate Banners")
        btn3.setObjectName("ActionBtn"); btn3.setFixedHeight(40)
        btn3.clicked.connect(lambda: self.start_batch("banner"))
        l3.addWidget(btn3)
        self.tabs.addTab(t3, "Banner")

    # ================= LOGIC =================
    def open_file_dialog(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Images", "", "Images (*.jpg *.png *.jpeg *.psd)")
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
        
        # 1. Info Update
        try:
            size_mb = os.path.getsize(path) / (1024*1024)
            img_tmp = Image.open(path)
            dpi = img_tmp.info.get('dpi', (72,72))
            
            self.lbl_info.setText(
                f"NAME: {os.path.basename(path)}\n"
                f"SIZE: {size_mb:.2f} MB\n"
                f"DIM : {img_tmp.width} x {img_tmp.height} px\n"
                f"DPI : {int(dpi[0])} DPI"
            )
        except: 
            self.lbl_info.setText("Reading file info...")

        # 2. Image Render
        try:
            if path.lower().endswith(".psd"):
                img = PSDImage.open(path).composite()
            else:
                img = Image.open(path)

            # Banner Preview Simulation
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
        except Exception as e:
            self.drop_zone.setText("Preview unavailable for this file.")

    def start_batch(self, mode):
        if not self.files: 
            return QMessageBox.warning(self, "No Files", "Please select files first.")
        
        settings = {
            "res": self.combo_res.currentText(),
            "ban_type": "2day" if self.rad_2day.isChecked() else "3day",
            "custom_name": self.entry_rename.text()
        }

        self.worker = BatchProcessor(mode, self.files, settings)
        self.worker.progress_signal.connect(self.progress.setValue)
        self.worker.status_signal.connect(self.lbl_status.setText)
        self.worker.finished_signal.connect(lambda m: QMessageBox.information(self, "Success", m))
        self.worker.start()

    def reset_workspace(self):
        self.files = []
        self.combo_files.clear()
        self.entry_rename.clear()
        self.drop_zone.setPixmap(QPixmap())
        self.drop_zone.setText("\n\nDROP IMAGES HERE\n\n")
        self.lbl_info.setText("No file selected.")
        self.progress.setValue(0)
        self.lbl_status.setText("Workspace Cleared")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MediaStudioPro()
    window.show()
    sys.exit(app.exec())
