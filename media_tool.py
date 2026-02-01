import sys
import os
import time
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QPushButton, QTabWidget, QTextEdit, QListWidget, 
                             QLineEdit, QComboBox, QMessageBox, QFileDialog, QRadioButton, 
                             QProgressBar, QFrame, QSizePolicy)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize, QMimeData
from PyQt6.QtGui import QPixmap, QImage, QDragEnterEvent, QDropEvent, QIcon, QAction, QPalette, QColor
from PIL import Image, ImageQt, ImageFilter
from psd_tools import PSDImage

# --- WORKER THREAD (Non-Freezing UI) ---
class BatchProcessor(QThread):
    """
    Runs heavy image processing in the background so the UI never freezes.
    """
    progress_signal = pyqtSignal(int)
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(str)

    def __init__(self, mode, file_list, settings, custom_names):
        super().__init__()
        self.mode = mode
        self.file_list = file_list
        self.settings = settings
        self.custom_names = custom_names
        self._is_running = True

    def run(self):
        count = 0
        total = len(self.file_list)
        
        for index, f_path in enumerate(self.file_list):
            if not self._is_running: break
            
            try:
                base_name = os.path.basename(f_path)
                self.log_signal.emit(f"Processing: {base_name}...")
                
                # 1. Open Image & Capture Metadata
                if f_path.lower().endswith(".psd"):
                    psd = PSDImage.open(f_path)
                    img = psd.composite()
                    # PSDs often don't store DPI in standard PIL info, try to default to 72
                    original_dpi = (72, 72) 
                else:
                    img = Image.open(f_path)
                    original_dpi = img.info.get('dpi', (72, 72)) # CAPTURE ORIGINAL DPI

                # 2. Determine Output Path
                out_dir = os.path.join(os.path.dirname(f_path), "Processed_Output")
                os.makedirs(out_dir, exist_ok=True)
                
                # 3. Apply Operations
                final_name = self.custom_names.get(f_path, os.path.splitext(base_name)[0])
                
                if self.mode == "resize":
                    w, h = map(int, self.settings['res'].split('x'))
                    img = img.resize((w, h), Image.Resampling.LANCZOS)
                    final_name += f"_{w}x{h}"

                elif self.mode == "banner":
                    # HD Banner Logic
                    img = img.resize((286, 371), Image.Resampling.LANCZOS)
                    img = img.filter(ImageFilter.UnsharpMask(radius=0.8, percent=110, threshold=3))
                    
                    canvas = Image.new("RGB", (286, 410), (255, 255, 255))
                    canvas.paste(img, (0,0))
                    
                    # Overlay
                    tpl_name = "banner_2day.png" if self.settings['ban_type'] == "2day" else "banner_3day.png"
                    # Look for assets in the same directory as the script
                    tpl_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), tpl_name)
                    
                    if os.path.exists(tpl_path):
                        ovl = Image.open(tpl_path).convert("RGBA").resize((286, 410), Image.Resampling.LANCZOS)
                        canvas.paste(ovl, (0,0), mask=ovl)
                        img = canvas
                    else:
                        self.log_signal.emit(f"Warning: Overlay {tpl_name} not found.")

                    suf = "_2DayBanner" if self.settings['ban_type'] == "2day" else "_3DayBanner"
                    final_name += suf

                # 4. Save with ORIGINAL DPI
                save_path = os.path.join(out_dir, final_name + ".jpg")
                if img.mode in ("RGBA", "P"): img = img.convert("RGB")
                
                # --- THE INDUSTRY STANDARD SAVE ---
                img.save(save_path, "JPEG", quality=100, subsampling=0, dpi=original_dpi)
                
                count += 1
                progress_pct = int((index + 1) / total * 100)
                self.progress_signal.emit(progress_pct)

            except Exception as e:
                self.log_signal.emit(f"Error on {base_name}: {str(e)}")

        self.finished_signal.emit(f"Batch Complete. Processed {count}/{total} files.")

# --- CUSTOM DRAG-DROP WIDGET ---
class DropZone(QLabel):
    def __init__(self, parent_app):
        super().__init__()
        self.parent_app = parent_app
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setText("\n\nDRAG & DROP FILES HERE\n\n(Supported: JPG, PNG, PSD)\n\n")
        self.setStyleSheet("""
            QLabel {
                border: 2px dashed #444;
                border-radius: 10px;
                color: #666;
                font-size: 14px;
                background-color: #1e1e1e;
            }
            QLabel:hover {
                border-color: #00E5FF;
                color: #00E5FF;
                background-color: #252525;
            }
        """)
        self.setAcceptDrops(True)
        self.setMinimumSize(300, 400)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls(): event.accept()
        else: event.ignore()

    def dropEvent(self, event: QDropEvent):
        files = [u.toLocalFile() for u in event.mimeData().urls()]
        self.parent_app.load_files(files)

# --- MAIN APPLICATION ---
class MediaStudioPro(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Media Workflow Studio Pro v10 (Industrial Edition)")
        self.resize(1200, 800)
        self.setup_ui_theme()

        # Data
        self.files = []
        self.custom_names = {}
        self.current_preview = None
        
        # --- UI LAYOUT ---
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        self.main_layout = QHBoxLayout(main_widget)
        self.main_layout.setContentsMargins(20, 20, 20, 20)
        self.main_layout.setSpacing(20)

        # === LEFT COLUMN (CONTROLS) ===
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_panel.setFixedWidth(400)
        self.main_layout.addWidget(left_panel)

        # Tabs
        self.tabs = QTabWidget()
        self.setup_tabs()
        left_layout.addWidget(self.tabs)

        # Rename Section
        rename_box = QFrame()
        rename_box.setStyleSheet("background-color: #2b2b2b; border-radius: 8px; padding: 10px;")
        r_layout = QVBoxLayout(rename_box)
        
        r_layout.addWidget(QLabel("<b>RENAME FILE</b>"))
        self.lbl_target = QLabel("No file selected")
        self.lbl_target.setStyleSheet("color: #888;")
        r_layout.addWidget(self.lbl_target)
        
        self.entry_name = QLineEdit()
        self.entry_name.setPlaceholderText("Enter new filename...")
        self.entry_name.textChanged.connect(self.update_output_preview)
        r_layout.addWidget(self.entry_name)
        
        self.lbl_output_preview = QLabel("Output: ...")
        self.lbl_output_preview.setStyleSheet("color: #00E5FF; font-family: Consolas; margin-top: 5px;")
        r_layout.addWidget(self.lbl_output_preview)
        
        left_layout.addWidget(rename_box)
        
        # Progress Bar
        self.progress = QProgressBar()
        self.progress.setStyleSheet("QProgressBar { border: 0px; border-radius: 4px; background: #333; text-align: center; } QProgressBar::chunk { background: #00E5FF; }")
        left_layout.addWidget(self.progress)

        # === RIGHT COLUMN (PREVIEW) ===
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        self.main_layout.addWidget(right_panel)

        right_layout.addWidget(QLabel("<h2>Live Preview</h2>"))

        # File Selector
        self.combo_files = QComboBox()
        self.combo_files.currentIndexChanged.connect(self.change_preview_image)
        right_layout.addWidget(self.combo_files)

        # Drop Zone / Image Preview
        self.drop_zone = DropZone(self)
        right_layout.addWidget(self.drop_zone, alignment=Qt.AlignmentFlag.AlignCenter)

        # Info Console
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setMaximumHeight(120)
        self.console.setStyleSheet("background: #111; color: #00FF00; font-family: Consolas; border: 1px solid #333;")
        self.console.setText("System Ready. Waiting for files...")
        right_layout.addWidget(self.console)
        
        # Reset Button (Floating bottom right)
        btn_reset = QPushButton("Reset Workspace", self)
        btn_reset.clicked.connect(self.reset_workspace)
        btn_reset.setStyleSheet("background: #444; color: white; padding: 5px;")
        right_layout.addWidget(btn_reset, alignment=Qt.AlignmentFlag.AlignRight)

    def setup_ui_theme(self):
        # Fusion Dark Theme
        self.setStyleSheet("""
            QMainWindow { background-color: #121212; }
            QWidget { color: #e0e0e0; font-family: 'Segoe UI', sans-serif; font-size: 13px; }
            QTabWidget::pane { border: 1px solid #444; background: #1e1e1e; }
            QTabBar::tab { background: #2b2b2b; padding: 8px 20px; color: #aaa; }
            QTabBar::tab:selected { background: #0078d7; color: white; }
            QPushButton { background-color: #333; border: 1px solid #555; padding: 8px; border-radius: 4px; }
            QPushButton:hover { background-color: #444; border-color: #00E5FF; }
            QLineEdit, QComboBox { background: #222; border: 1px solid #444; padding: 5px; color: white; border-radius: 4px; }
            QListWidget { background: #1e1e1e; border: 1px solid #333; }
        """)

    def setup_tabs(self):
        # PSD Tab
        tab_psd = QWidget()
        l_psd = QVBoxLayout(tab_psd)
        btn_psd_run = QPushButton("Convert All PSDs to JPG")
        btn_psd_run.setStyleSheet("background-color: #0078d7; font-weight: bold;")
        btn_psd_run.clicked.connect(lambda: self.start_batch("psd"))
        l_psd.addWidget(QLabel("Batch convert PSD files to high-quality JPGs."))
        l_psd.addStretch()
        l_psd.addWidget(btn_psd_run)
        self.tabs.addTab(tab_psd, "PSD Converter")

        # Resize Tab
        tab_res = QWidget()
        l_res = QVBoxLayout(tab_res)
        l_res.addWidget(QLabel("Target Resolution:"))
        self.combo_res = QComboBox()
        self.combo_res.addItems(["286x410", "960x1440", "1920x1080", "380x560"])
        l_res.addWidget(self.combo_res)
        btn_res_run = QPushButton("Resize All")
        btn_res_run.setStyleSheet("background-color: #0078d7; font-weight: bold;")
        btn_res_run.clicked.connect(lambda: self.start_batch("resize"))
        l_res.addStretch()
        l_res.addWidget(btn_res_run)
        self.tabs.addTab(tab_res, "Smart Resize")

        # Banner Tab
        tab_ban = QWidget()
        l_ban = QVBoxLayout(tab_ban)
        self.group_ban = QRadioButton("2-Day Banner")
        self.rad_3day = QRadioButton("3-Day Banner")
        self.group_ban.setChecked(True)
        self.group_ban.toggled.connect(lambda: self.refresh_preview_image(self.current_preview))
        l_ban.addWidget(self.group_ban)
        l_ban.addWidget(self.rad_3day)
        btn_ban_run = QPushButton("Generate Banners")
        btn_ban_run.setStyleSheet("background-color: #0078d7; font-weight: bold;")
        btn_ban_run.clicked.connect(lambda: self.start_batch("banner"))
        l_ban.addStretch()
        l_ban.addWidget(btn_ban_run)
        self.tabs.addTab(tab_ban, "HD Banner")

    # ================= LOGIC =================

    def load_files(self, file_paths):
        valid = [f for f in file_paths if os.path.isfile(f) and f.lower().endswith(('.jpg', '.jpeg', '.png', '.psd'))]
        if not valid: return

        self.files = valid
        self.combo_files.clear()
        self.combo_files.addItems([os.path.basename(f) for f in valid])
        self.console.append(f"> Loaded {len(valid)} files.")
        
        if valid:
            self.combo_files.setCurrentIndex(0)

    def change_preview_image(self, index):
        if index < 0 or index >= len(self.files): return
        self.current_preview = self.files[index]
        self.refresh_preview_image(self.current_preview)
        
        # Update Rename UI
        base = os.path.basename(self.current_preview)
        self.lbl_target.setText(base)
        stored_name = self.custom_names.get(self.current_preview, "")
        self.entry_name.setText(stored_name)
        self.update_output_preview(stored_name)

    def refresh_preview_image(self, path):
        if not path: return
        
        # Show "Loading..."
        self.drop_zone.setText("Loading Preview...")
        QApplication.processEvents()

        try:
            # Load Image using Pillow (for PSD support)
            if path.lower().endswith(".psd"):
                img = PSDImage.open(path).composite()
            else:
                img = Image.open(path)

            # Apply Banner Preview if on Banner Tab
            if self.tabs.currentIndex() == 2:
                img = img.resize((286, 371), Image.Resampling.LANCZOS)
                canvas = Image.new("RGB", (286, 410), (255, 255, 255))
                canvas.paste(img, (0,0))
                
                tpl = "banner_2day.png" if self.group_ban.isChecked() else "banner_3day.png"
                
                # Check absolute path relative to script
                tpl_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), tpl)

                if os.path.exists(tpl_path):
                    ovl = Image.open(tpl_path).convert("RGBA").resize((286, 410), Image.Resampling.LANCZOS)
                    canvas.paste(ovl, (0,0), mask=ovl)
                    img = canvas

            # Convert to Qt
            img.thumbnail((400, 500), Image.Resampling.LANCZOS)
            if img.mode == "RGB": 
                img = img.convert("RGBA")
            
            data = img.tobytes("raw", "RGBA")
            qim = QImage(data, img.size[0], img.size[1], QImage.Format.Format_RGBA8888)
            pix = QPixmap.fromImage(qim)
            
            self.drop_zone.setPixmap(pix)
            self.drop_zone.setText("") # Clear text
            
            # Update Info
            dpi = img.info.get('dpi', (72,72))
            self.console.append(f"> Previewing: {os.path.basename(path)} | DPI: {int(dpi[0])}")

        except Exception as e:
            self.drop_zone.setText("Preview Error")
            self.console.append(f"Err: {str(e)}")

    def update_output_preview(self, text):
        if not self.current_preview: return
        self.custom_names[self.current_preview] = text
        suf = ""
        if self.tabs.currentIndex() == 2:
            suf = "_2DayBanner" if self.group_ban.isChecked() else "_3DayBanner"
        elif self.tabs.currentIndex() == 1:
            suf = f"_{self.combo_res.currentText()}"
        
        display_name = text if text else os.path.splitext(os.path.basename(self.current_preview))[0]
        self.lbl_output_preview.setText(f"Output: {display_name}{suf}.jpg")

    def start_batch(self, mode):
        if not self.files:
            QMessageBox.warning(self, "No Files", "Please drop files first.")
            return

        settings = {
            "res": self.combo_res.currentText(),
            "ban_type": "2day" if self.group_ban.isChecked() else "3day"
        }

        # Disable UI
        self.setEnabled(False)
        self.progress.setValue(0)
        
        # Start Thread
        self.worker = BatchProcessor(mode, self.files, settings, self.custom_names)
        self.worker.progress_signal.connect(self.progress.setValue)
        self.worker.log_signal.connect(self.console.append)
        self.worker.finished_signal.connect(self.batch_finished)
        self.worker.start()

    def batch_finished(self, msg):
        self.setEnabled(True)
        self.progress.setValue(100)
        QMessageBox.information(self, "Complete", msg)
        self.console.append(f"> {msg}")

    def reset_workspace(self):
        self.files = []
        self.custom_names = {}
        self.current_preview = None
        self.combo_files.clear()
        self.entry_name.clear()
        self.drop_zone.setPixmap(QPixmap())
        self.drop_zone.setText("\n\nDRAG & DROP FILES HERE\n\n(Supported: JPG, PNG, PSD)\n\n")
        self.console.setText("Workspace Reset.")
        self.progress.setValue(0)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MediaStudioPro()
    window.show()
    sys.exit(app.exec())
