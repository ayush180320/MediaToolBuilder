"""
APPLICATION SECURITY MANIFEST & AUDIT LOG
-----------------------------------------
App Name:       Media Workflow Studio Pro
Version:        3.4 (PSD Engine Fix + Banner Info Fix)
Author:         Ayush Singhal
Company:        Deluxe Media
Purpose:        Local image manipulation.

COPYRIGHT NOTICE:
The logic and architecture of this script were authored by Ayush Singhal.
"""

import customtkinter as ctk
from tkinter import filedialog, messagebox
import os
import threading
import sys
import re
from PIL import Image, ImageTk, ImageFilter
from psd_tools import PSDImage

# --- SAFE IMPORT: DRAG & DROP ---
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    DRAG_DROP_AVAILABLE = True
except ImportError:
    DRAG_DROP_AVAILABLE = False
    class TkinterDnD:
        class DnDWrapper:
            pass

# --- Configuration ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

BaseClass = TkinterDnD.DnDWrapper if DRAG_DROP_AVAILABLE else object

class ProMediaTool(ctk.CTk, BaseClass):
    def __init__(self):
        super().__init__()

        self.title("Media Workflow Studio Pro v3.4")
        self.geometry("1100x750")

        self.bind("<Control-Alt-a>", self._reveal_author)
        
        # --- Layout ---
        self.grid_columnconfigure(0, weight=3) 
        self.grid_columnconfigure(1, weight=4) 
        self.grid_rowconfigure(0, weight=1)

        # --- LEFT PANEL ---
        self.left_frame = ctk.CTkFrame(self, corner_radius=0)
        self.left_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        self.tab_view = ctk.CTkTabview(self.left_frame)
        self.tab_view.pack(fill="both", expand=True, padx=10, pady=10)

        self.tab_psd = self.tab_view.add("PSD Bulk Converter")
        self.tab_resize = self.tab_view.add("Smart Resizer")
        self.tab_banner = self.tab_view.add("HD Banner & Rename")

        # --- RIGHT PANEL ---
        self.right_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="#1a1a1a")
        self.right_frame.grid(row=0, column=1, sticky="nsew", padx=(0,10), pady=10)
        
        self.lbl_preview_title = ctk.CTkLabel(self.right_frame, text="Live Preview", font=("Roboto", 16, "bold"))
        self.lbl_preview_title.pack(pady=(20, 5))

        self.preview_selector = ctk.CTkOptionMenu(self.right_frame, dynamic_resizing=False, width=280, command=self.on_selector_change)
        self.preview_selector.set("No Files Selected")
        self.preview_selector.configure(state="disabled")
        self.preview_selector.pack(pady=5)
        
        self.lbl_preview_img = ctk.CTkLabel(self.right_frame, text="[Drag Files Here]", width=286, height=410, fg_color="#2b2b2b", corner_radius=10)
        self.lbl_preview_img.pack(pady=10, padx=20)

        self.lbl_info_title = ctk.CTkLabel(self.right_frame, text="File Information", font=("Roboto", 12, "bold"), text_color="gray70")
        self.lbl_info_title.pack(pady=(10, 0), anchor="w", padx=20)
        
        self.info_box = ctk.CTkTextbox(self.right_frame, height=100, fg_color="#222222", text_color="#00E5FF")
        self.info_box.pack(fill="x", padx=20, pady=5, side="top")
        self.info_box.insert("0.0", "Waiting for selection...")
        self.info_box.configure(state="disabled")

        # Internal State
        self.file_list = []
        self.file_names = []
        self.current_preview_path = None
        
        self._setup_psd_tab()
        self._setup_resize_tab()
        self._setup_banner_tab()
        
        if DRAG_DROP_AVAILABLE:
            self.TkdndVersion = TkinterDnD._require(self)
            self.drop_target_register(DND_FILES)
            self.dnd_bind('<<Drop>>', self.drop_files_handler)

    def resource_path(self, relative_path):
        try: base_path = sys._MEIPASS
        except: base_path = os.path.abspath(".")
        return os.path.join(base_path, relative_path)

    # --- INPUT HANDLING ---
    def handle_files_input(self, files):
        if not files: return
        self.file_list = files
        self.file_names = [os.path.basename(f) for f in files]
        
        self.preview_selector.configure(state="normal", values=self.file_names)
        self.preview_selector.set(self.file_names[0])
        
        active = self.tab_view.get()
        target_box = self.txt_psd if active == "PSD Bulk Converter" else (self.txt_res if active == "Smart Resizer" else self.txt_ban)
        
        target_box.configure(state="normal")
        target_box.delete("0.0", "end")
        for f in self.file_names: target_box.insert("end", f"{f}\n")
        target_box.configure(state="disabled")

        self.current_preview_path = self.file_list[0]
        # Important: Refresh preview FIRST, then update info (info might depend on successful read)
        self.refresh_preview()
        self.update_file_info(self.current_preview_path)

    def on_selector_change(self, selected_filename):
        try:
            index = self.file_names.index(selected_filename)
            self.current_preview_path = self.file_list[index]
            self.refresh_preview()
            self.update_file_info(self.current_preview_path)
        except ValueError: pass

    def drop_files_handler(self, event):
        raw_files = event.data
        if "{" in raw_files:
            files = re.findall(r'\{.*?\}|\S+', raw_files)
            files = [f.replace("{", "").replace("}", "") for f in files]
        else:
            files = raw_files.split()
        self.handle_files_input(files)

    def select_files(self, mode):
        ft = [("Photoshop", "*.psd")] if mode == "psd" else [("Images", "*.jpg;*.png;*.jpeg")]
        files = filedialog.askopenfilenames(filetypes=ft)
        self.handle_files_input(files)

    # --- FILE INFO ENGINE ---
    def update_file_info(self, filepath):
        txt = "Reading..."
        try:
            size_mb = os.path.getsize(filepath) / (1024 * 1024)
            
            if filepath.lower().endswith(".psd"):
                # Wrap PSD read in specific try/catch to debug preview errors
                try:
                    psd = PSDImage.open(filepath)
                    w, h, fmt, mode = psd.width, psd.height, "PSD (Adobe)", psd.color_mode
                except Exception as e:
                    txt = f"PSD Error: {str(e)}\n(Try restarting app)"
                    raise e # Re-raise to skip to final block
            else:
                img = Image.open(filepath)
                w, h, fmt, mode = img.size, img.format, img.mode
            
            txt = f"File: {os.path.basename(filepath)}\nDim: {w}x{h}\nType: {fmt} | {mode}\nSize: {size_mb:.2f} MB"
            
        except Exception:
            # If txt wasn't set by the specific PSD error above, use generic
            if "PSD Error" not in txt:
                txt = f"Could not read metadata.\nFile: {os.path.basename(filepath)}"

        self.info_box.configure(state="normal")
        self.info_box.delete("0.0", "end")
        self.info_box.insert("0.0", txt)
        self.info_box.configure(state="disabled")

    # --- PREVIEW ENGINE ---
    def refresh_preview(self):
        if not self.current_preview_path: return
        try:
            if self.current_preview_path.lower().endswith(".psd"):
                psd = PSDImage.open(self.current_preview_path)
                img = psd.composite()
            else:
                img = Image.open(self.current_preview_path)

            if self.tab_view.get() == "HD Banner & Rename":
                img = img.resize((286, 371), Image.Resampling.LANCZOS)
                canvas = Image.new("RGB", (286, 410), (255, 255, 255))
                canvas.paste(img, (0, 0))
                
                tpl = "banner_2day.png" if self.ban_type.get() == "2day" else "banner_3day.png"
                tpl_path = self.resource_path(tpl)
                if os.path.exists(tpl_path):
                    banner = Image.open(tpl_path).convert("RGBA").resize((286, 410), Image.Resampling.LANCZOS)
                    canvas.paste(banner, (0, 0), mask=banner)
                    img = canvas

            img.thumbnail((286, 410))
            ctk_img = ctk.CTkImage(img, size=img.size)
            self.lbl_preview_img.configure(image=ctk_img, text="")
        except Exception as e:
            self.lbl_preview_img.configure(image="", text=f"Preview Failed\n{str(e)}")

    def save_image_pro(self, img, path, dpi=(72,72)):
        if img.mode in ("RGBA", "P", "CMYK"): img = img.convert("RGB")
        img.save(path, "JPEG", quality=100, subsampling=0, dpi=dpi)

    # --- TABS ---
    def _setup_psd_tab(self):
        ctk.CTkLabel(self.tab_psd, text="PSD Bulk Converter", font=("Arial", 14, "bold")).pack(pady=5)
        ctk.CTkButton(self.tab_psd, text="Select Files", command=lambda: self.select_files("psd")).pack()
        self.txt_psd = ctk.CTkTextbox(self.tab_psd, height=150, state="disabled")
        self.txt_psd.pack(pady=5, fill="x")
        ctk.CTkButton(self.tab_psd, text="Convert All", fg_color="green", command=lambda: threading.Thread(target=self._process_psd, daemon=True).start()).pack(pady=10)

    def _process_psd(self):
        if not self.file_list: return messagebox.showwarning("Error", "No files selected")
        count = 0
        errors = 0
        for f in self.file_list:
            try:
                out_dir = os.path.join(os.path.dirname(f), "Converted_PSD")
                os.makedirs(out_dir, exist_ok=True)
                
                psd = PSDImage.open(f)
                out_path = os.path.join(out_dir, os.path.basename(os.path.splitext(f)[0] + ".jpg"))
                self.save_image_pro(psd.composite(), out_path)
                count += 1
            except Exception as e:
                print(f"PSD Fail: {e}")
                errors += 1
        
        msg = f"Converted {count} files."
        if errors > 0: msg += f"\nFailed: {errors} (See console or info box)"
        messagebox.showinfo("Report", msg)

    def _setup_resize_tab(self):
        ctk.CTkLabel(self.tab_resize, text="Smart Resizer", font=("Arial", 14, "bold")).pack(pady=5)
        ctk.CTkButton(self.tab_resize, text="Select Files", command=lambda: self.select_files("img")).pack()
        self.txt_res = ctk.CTkTextbox(self.tab_resize, height=100, state="disabled")
        self.txt_res.pack(pady=5, fill="x")
        self.res_var = ctk.StringVar(value="286x410")
        ctk.CTkOptionMenu(self.tab_resize, values=["286x410", "960x1440", "380x560", "630x945"], variable=self.res_var).pack()
        ctk.CTkButton(self.tab_resize, text="Resize All", fg_color="green", command=lambda: threading.Thread(target=self._process_res, daemon=True).start()).pack(pady=10)

    def _process_res(self):
        if not self.file_list: return messagebox.showwarning("Error", "No files selected")
        w, h = map(int, self.res_var.get().split('x'))
        count = 0
        for f in self.file_list:
            try:
                out_dir = os.path.join(os.path.dirname(f), "Resized_Output")
                os.makedirs(out_dir, exist_ok=True)

                img = Image.open(f)
                img = img.resize((w, h), Image.Resampling.LANCZOS)
                out_path = os.path.join(out_dir, os.path.basename(os.path.splitext(f)[0] + f"_{self.res_var.get()}.jpg"))
                self.save_image_pro(img, out_path, img.info.get('dpi', (72,72)))
                count += 1
            except: pass
        messagebox.showinfo("Success", f"Resized {count} files.")

    def _setup_banner_tab(self):
        ctk.CTkLabel(self.tab_banner, text="HD Banner", font=("Arial", 14, "bold")).pack(pady=5)
        ctk.CTkButton(self.tab_banner, text="Select Files", command=lambda: self.select_files("img")).pack()
        self.txt_ban = ctk.CTkTextbox(self.tab_banner, height=60, state="disabled")
        self.txt_ban.pack(pady=5, fill="x")
        self.entry_title = ctk.CTkEntry(self.tab_banner, placeholder_text="Title Name (Optional)")
        self.entry_title.pack(fill="x", pady=5)
        
        self.ban_type = ctk.StringVar(value="2day")
        r = ctk.CTkFrame(self.tab_banner); r.pack()
        ctk.CTkRadioButton(r, text="2-Day", variable=self.ban_type, value="2day", command=self.refresh_preview).pack(side="left", padx=5)
        ctk.CTkRadioButton(r, text="3-Day", variable=self.ban_type, value="3day", command=self.refresh_preview).pack(side="left", padx=5)
        
        ctk.CTkButton(self.tab_banner, text="Process All", fg_color="green", command=lambda: threading.Thread(target=self._process_ban, daemon=True).start()).pack(pady=10)

    def _process_ban(self):
        if not self.file_list: return messagebox.showwarning("Error", "No files selected")
        tpl = "banner_2day.png" if self.ban_type.get() == "2day" else "banner_3day.png"
        tpl_path = self.resource_path(tpl)
        if not os.path.exists(tpl_path): return messagebox.showerror("Error", f"Missing {tpl}")

        count = 0
        user_title = self.entry_title.get().strip()
        
        for i, fpath in enumerate(self.file_list):
            try:
                out_dir = os.path.join(os.path.dirname(fpath), "Banner_Output")
                os.makedirs(out_dir, exist_ok=True)

                img = Image.open(fpath)
                dpi = img.info.get('dpi', (72, 72))
                img_res = img.resize((286, 371), Image.Resampling.LANCZOS)
                img_res = img_res.filter(ImageFilter.UnsharpMask(radius=0.8, percent=110, threshold=3))
                
                canvas = Image.new("RGB", (286, 410), (255, 255, 255))
                canvas.paste(img_res, (0, 0))
                banner = Image.open(tpl_path).convert("RGBA").resize((286, 410), Image.Resampling.LANCZOS)
                canvas.paste(banner, (0, 0), mask=banner)

                suffix = "2DayBanner_286x410" if self.ban_type.get() == "2day" else "3DayBanner_286x410"
                if user_title:
                    fname = f"{user_title}_{i+1:02d}_{suffix}.jpg" if len(self.file_list) > 1 else f"{user_title}_{suffix}.jpg"
                else:
                    fname = os.path.splitext(os.path.basename(fpath))[0] + f"_{suffix}.jpg"

                self.save_image_pro(canvas, os.path.join(out_dir, fname), dpi)
                count += 1
            except Exception as e: print(e)

        messagebox.showinfo("Success", f"Processed {count} Banners.")

    def _reveal_author(self, event=None):
        messagebox.showinfo("Credits", "Code by Ayush Singhal | Deluxe Media")

if __name__ == "__main__":
    app = ProMediaTool()
    app.mainloop()
