"""
APPLICATION SECURITY MANIFEST & AUDIT LOG
-----------------------------------------
App Name:       Media Workflow Studio Pro
Version:        5.7 (State Lock Fix & Direct Trigger)
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

        self.title("Media Workflow Studio Pro v5.7")
        self.geometry("1100x750")
        self.minsize(1100, 750)
        
        self.bind("<Control-Alt-a>", self._reveal_author)
        
        # --- Layout Grid ---
        self.grid_columnconfigure(0, weight=4) # Left Panel
        self.grid_columnconfigure(1, weight=5) # Right Panel
        self.grid_rowconfigure(0, weight=1)

        # ============================================================
        # === LEFT PANEL: CONTROLS & RENAME ==========================
        # ============================================================
        self.left_frame = ctk.CTkFrame(self, corner_radius=0)
        self.left_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        # 1. Main Operation Tabs
        self.tab_view = ctk.CTkTabview(self.left_frame, command=self.on_tab_switch)
        self.tab_view.pack(fill="both", expand=True, padx=10, pady=10)

        self.tab_psd = self.tab_view.add("PSD Bulk Converter")
        self.tab_resize = self.tab_view.add("Smart Resizer")
        self.tab_banner = self.tab_view.add("HD Banner & Rename")

        # 2. Rename Section (Left Side)
        self.rename_frame = ctk.CTkFrame(self.left_frame, fg_color="#2b2b2b", border_color="gray", border_width=1)
        self.rename_frame.pack(fill="x", padx=10, pady=20, side="bottom")

        ctk.CTkLabel(self.rename_frame, text="RENAME SELECTED FILE", font=("Roboto", 12, "bold")).pack(pady=(10,5))
        
        self.lbl_rename_target = ctk.CTkLabel(self.rename_frame, text="No file selected", text_color="gray")
        self.lbl_rename_target.pack(pady=2)

        self.entry_manual_name = ctk.CTkEntry(self.rename_frame, placeholder_text="Enter new filename here...")
        self.entry_manual_name.pack(fill="x", padx=15, pady=5)
        self.entry_manual_name.bind("<KeyRelease>", self.on_manual_rename_type) 
        
        self.lbl_final_name = ctk.CTkLabel(self.rename_frame, text="Output: ...", text_color="#00E5FF", font=("Consolas", 11))
        self.lbl_final_name.pack(anchor="w", padx=15, pady=(0,10))

        # ============================================================
        # === RIGHT PANEL: PREVIEW & INFO ============================
        # ============================================================
        self.right_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="#1a1a1a")
        self.right_frame.grid(row=0, column=1, sticky="nsew", padx=(0,10), pady=10)
        
        # 1. Preview Header & Selector
        self.lbl_preview_title = ctk.CTkLabel(self.right_frame, text="Live Preview", font=("Roboto", 18, "bold"))
        self.lbl_preview_title.pack(pady=(15, 5))

        self.selector_var = ctk.StringVar(value="No Files Selected")
        self.preview_selector = ctk.CTkOptionMenu(
            self.right_frame, 
            dynamic_resizing=False, 
            width=300, 
            variable=self.selector_var,
            command=self.on_selector_change
        )
        self.preview_selector.pack(pady=5)
        
        # 2. The Image
        self.lbl_preview_img = ctk.CTkLabel(self.right_frame, text="[Drag Files Here]", width=286, height=410, fg_color="#222222", corner_radius=10)
        self.lbl_preview_img.pack(pady=10, padx=20)

        # 3. File Info Section (Under Preview)
        self.info_container = ctk.CTkFrame(self.right_frame, fg_color="transparent")
        self.info_container.pack(fill="both", expand=True, padx=20, pady=10)

        ctk.CTkLabel(self.info_container, text="FILE INFORMATION", font=("Roboto", 11, "bold"), text_color="gray").pack(anchor="w")

        self.info_box = ctk.CTkTextbox(self.info_container, height=100, fg_color="#222222", text_color="#00E5FF", font=("Consolas", 12))
        self.info_box.pack(fill="x", pady=5)
        self.info_box.insert("0.0", "Waiting for input...")
        self.info_box.configure(state="disabled")

        # ============================================================
        # Internal State
        self.file_list = []
        self.file_names = []
        self.custom_names_map = {} 
        self.current_preview_path = None
        self.current_ctk_image = None 
        
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

    # ============================================================
    # === CRITICAL FIX: RESET LOGIC ==============================
    # ============================================================
    def reset_ui(self):
        """
        FIXED RESET:
        We do NOT disable the selector anymore. We just clear the list.
        Disabling it caused the 'zombie' state when trying to reload.
        """
        try:
            # 1. Reset Internal State
            self.file_list = []
            self.file_names = []
            self.custom_names_map = {}
            self.current_preview_path = None
            self.current_ctk_image = None
            
            # 2. Reset Selector (KEEP ACTIVE)
            self.selector_var.set("No Files Selected")
            self.preview_selector.configure(values=["No Files Selected"])
            # DO NOT DISABLE HERE - This was the bug source

            # 3. Reset Visuals
            self.lbl_preview_img.configure(image=None, text="[Drag Files Here]")
            self.lbl_rename_target.configure(text="No file selected")
            
            self.entry_manual_name.delete(0, "end")
            self.lbl_final_name.configure(text="Output: ...")
            
            # 4. Clear Text Boxes (Unlock -> Clear -> Lock)
            self.info_box.configure(state="normal")
            self.info_box.delete("0.0", "end")
            self.info_box.insert("0.0", "Waiting for input...")
            self.info_box.configure(state="disabled")
            
            for txt in [self.txt_psd, self.txt_res, self.txt_ban]:
                txt.configure(state="normal")
                txt.delete("0.0", "end")
                txt.configure(state="disabled")
                
            self.update_idletasks()
            
        except Exception as e:
            print(f"Reset Exception: {e}")

    def on_tab_switch(self):
        # Optional: auto-reset on tab switch. 
        # Comment this line out if you want to keep files when switching tabs.
        self.reset_ui()

    # ============================================================
    # === LOADING NEW FILES ======================================
    # ============================================================
    def handle_files_input(self, files):
        if not files: return
        
        # 1. Clean old data first
        self.reset_ui()
        
        # 2. Load New Data
        self.file_list = list(files)
        self.file_names = [os.path.basename(f) for f in files]
        
        self.custom_names_map = {}
        for f in files:
            base = os.path.splitext(os.path.basename(f))[0]
            self.custom_names_map[f] = base

        # 3. Update Selector (Safe Mode)
        # We update the values list and set the variable explicitly
        self.preview_selector.configure(values=self.file_names)
        self.selector_var.set(self.file_names[0])
        
        # 4. Update Text Box List
        active = self.tab_view.get()
        target_box = self.txt_psd if active == "PSD Bulk Converter" else (self.txt_res if active == "Smart Resizer" else self.txt_ban)
        
        target_box.configure(state="normal")
        target_box.delete("0.0", "end")
        for f in self.file_names: target_box.insert("end", f"{f}\n")
        target_box.configure(state="disabled")

        # 5. DIRECT PREVIEW TRIGGER (Bypassing dropdown callback for reliability)
        self.current_preview_path = self.file_list[0]
        
        # Call update functions directly
        self.update_rename_fields() 
        self.update_preview_logic()
        self.update_file_info(self.current_preview_path)

    def on_selector_change(self, selected_filename):
        if selected_filename == "No Files Selected" or not self.file_list: return
        try:
            index = self.file_names.index(selected_filename)
            self.current_preview_path = self.file_list[index]
            
            self.update_rename_fields() 
            self.update_preview_logic()
            self.update_file_info(self.current_preview_path)
        except ValueError: pass

    # ============================================================
    # === INFO & PREVIEW LOGIC ===================================
    # ============================================================
    def update_file_info(self, filepath):
        if not filepath: return
        
        txt = "Reading..."
        try:
            size_bytes = os.path.getsize(filepath)
            size_str = f"{size_bytes / 1024:.1f} KB" if size_bytes < 1024*1024 else f"{size_bytes / (1024*1024):.2f} MB"
            
            if filepath.lower().endswith(".psd"):
                psd = PSDImage.open(filepath)
                w, h = psd.width, psd.height
                fmt = "PSD (Adobe)"
                mode = psd.color_mode
            else:
                img = Image.open(filepath)
                w, h = img.size
                fmt = img.format if img.format else "Image"
                mode = img.mode

            txt = (f"File: {os.path.basename(filepath)}\n"
                   f"Dimensions: {w} x {h}\n"
                   f"Format: {fmt}  |  Mode: {mode}\n"
                   f"File Size: {size_str}")

        except Exception as e:
            txt = f"Could not read file info.\n{e}"

        self.info_box.configure(state="normal")
        self.info_box.delete("0.0", "end")
        self.info_box.insert("0.0", txt)
        self.info_box.configure(state="disabled")

    def update_rename_fields(self):
        if not self.current_preview_path: return
        try:
            self.lbl_rename_target.configure(text=f"Editing: {os.path.basename(self.current_preview_path)}")
            
            stored_name = self.custom_names_map.get(self.current_preview_path, "")
            self.entry_manual_name.delete(0, "end")
            self.entry_manual_name.insert(0, stored_name)
            self._update_suffix_label(stored_name)
        except: pass

    def on_manual_rename_type(self, event):
        if not self.current_preview_path: return
        new_name = self.entry_manual_name.get()
        self.custom_names_map[self.current_preview_path] = new_name
        self._update_suffix_label(new_name)

    def _update_suffix_label(self, name):
        if self.tab_view.get() == "HD Banner & Rename":
            suffix = "2DayBanner_286x410" if self.ban_type.get() == "2day" else "3DayBanner_286x410"
            self.lbl_final_name.configure(text=f"Output: {name}_{suffix}.jpg")
        else:
            self.lbl_final_name.configure(text=f"Output: {name}.jpg")

    def update_preview_logic(self):
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
                
                stored = self.custom_names_map.get(self.current_preview_path, "")
                self._update_suffix_label(stored)

            img.thumbnail((286, 410), Image.Resampling.LANCZOS)
            self.current_ctk_image = ctk.CTkImage(img, size=img.size) 
            self.lbl_preview_img.configure(image=self.current_ctk_image, text="")
            
        except Exception as e:
            self.lbl_preview_img.configure(image=None, text=f"Preview Failed\n{str(e)}")

    def refresh_preview(self):
        self.update_preview_logic()

    def save_image_pro(self, img, path, dpi=(72,72)):
        if img.mode in ("RGBA", "P", "CMYK"): img = img.convert("RGB")
        img.save(path, "JPEG", quality=100, subsampling=0, dpi=dpi)

    # --- DRAG & DROP / FILE SELECT ---
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
        if files: self.handle_files_input(files)

    # --- TABS ---
    def _setup_psd_tab(self):
        ctk.CTkLabel(self.tab_psd, text="PSD Bulk Converter", font=("Arial", 14, "bold")).pack(pady=5)
        btn_frame = ctk.CTkFrame(self.tab_psd, fg_color="transparent")
        btn_frame.pack(pady=5)
        ctk.CTkButton(btn_frame, text="Select Files", command=lambda: self.select_files("psd")).pack(side="left", padx=5)
        
        # RESET
        ctk.CTkButton(btn_frame, text="Reset", fg_color="#C62828", hover_color="#B71C1C", width=80, command=self.reset_ui).pack(side="left", padx=5)
        
        self.txt_psd = ctk.CTkTextbox(self.tab_psd, height=150, state="disabled")
        self.txt_psd.pack(pady=5, fill="x")
        ctk.CTkButton(self.tab_psd, text="Convert All", fg_color="green", command=lambda: threading.Thread(target=self._process_psd, daemon=True).start()).pack(pady=10)

    def _process_psd(self):
        if not self.file_list: return messagebox.showwarning("Error", "No files selected")
        count = 0
        for f in self.file_list:
            try:
                out_dir = os.path.join(os.path.dirname(f), "Converted_PSD")
                os.makedirs(out_dir, exist_ok=True)
                psd = PSDImage.open(f)
                out_path = os.path.join(out_dir, os.path.basename(os.path.splitext(f)[0] + ".jpg"))
                self.save_image_pro(psd.composite(), out_path)
                count += 1
            except Exception as e: print(e)
        messagebox.showinfo("Report", f"Converted {count} files.")

    def _setup_resize_tab(self):
        ctk.CTkLabel(self.tab_resize, text="Smart Resizer", font=("Arial", 14, "bold")).pack(pady=5)
        btn_frame = ctk.CTkFrame(self.tab_resize, fg_color="transparent")
        btn_frame.pack(pady=5)
        ctk.CTkButton(btn_frame, text="Select Files", command=lambda: self.select_files("img")).pack(side="left", padx=5)
        
        # RESET
        ctk.CTkButton(btn_frame, text="Reset", fg_color="#C62828", hover_color="#B71C1C", width=80, command=self.reset_ui).pack(side="left", padx=5)
        
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
        ctk.CTkLabel(self.tab_banner, text="HD Banner & Batch Rename", font=("Arial", 14, "bold")).pack(pady=5)
        
        btn_frame = ctk.CTkFrame(self.tab_banner, fg_color="transparent")
        btn_frame.pack(pady=5)
        ctk.CTkButton(btn_frame, text="Select Files", command=lambda: self.select_files("img")).pack(side="left", padx=5)
        
        # RESET
        ctk.CTkButton(btn_frame, text="Reset", fg_color="#C62828", hover_color="#B71C1C", width=80, command=self.reset_ui).pack(side="left", padx=5)
        
        self.txt_ban = ctk.CTkTextbox(self.tab_banner, height=60, state="disabled")
        self.txt_ban.pack(pady=5, fill="x")
        
        self.ban_type = ctk.StringVar(value="2day")
        r = ctk.CTkFrame(self.tab_banner); r.pack(pady=5)
        ctk.CTkRadioButton(r, text="2-Day Banner", variable=self.ban_type, value="2day", command=self.refresh_preview).pack(side="left", padx=10)
        ctk.CTkRadioButton(r, text="3-Day Banner", variable=self.ban_type, value="3day", command=self.refresh_preview).pack(side="left", padx=10)
        
        ctk.CTkButton(self.tab_banner, text="Process Batch", fg_color="green", command=lambda: threading.Thread(target=self._process_ban, daemon=True).start()).pack(pady=10)

    def _process_ban(self):
        if not self.file_list: return messagebox.showwarning("Error", "No files selected")
        tpl = "banner_2day.png" if self.ban_type.get() == "2day" else "banner_3day.png"
        tpl_path = self.resource_path(tpl)
        if not os.path.exists(tpl_path): return messagebox.showerror("Error", f"Missing {tpl}")
        
        count = 0
        for fpath in self.file_list:
            try:
                out_dir = os.path.join(os.path.dirname(fpath), "Banner_Output")
                os.makedirs(out_dir, exist_ok=True)
                
                # PROCESSING
                img = Image.open(fpath)
                dpi = img.info.get('dpi', (72, 72))
                img_res = img.resize((286, 371), Image.Resampling.LANCZOS)
                img_res = img_res.filter(ImageFilter.UnsharpMask(radius=0.8, percent=110, threshold=3))
                
                canvas = Image.new("RGB", (286, 410), (255, 255, 255))
                canvas.paste(img_res, (0, 0))
                banner = Image.open(tpl_path).convert("RGBA").resize((286, 410), Image.Resampling.LANCZOS)
                canvas.paste(banner, (0, 0), mask=banner)
                
                # RETRIEVE CUSTOM NAME
                base_name = self.custom_names_map.get(fpath, os.path.splitext(os.path.basename(fpath))[0])
                
                # Define Suffix
                suffix = "2DayBanner_286x410" if self.ban_type.get() == "2day" else "3DayBanner_286x410"
                fname = f"{base_name}_{suffix}.jpg"
                    
                self.save_image_pro(canvas, os.path.join(out_dir, fname), dpi)
                count += 1
            except Exception as e: print(e)
        messagebox.showinfo("Success", f"Processed {count} files.")

    def _reveal_author(self, event=None):
        messagebox.showinfo("Credits", "Code by Ayush Singhal | Deluxe Media")

if __name__ == "__main__":
    app = ProMediaTool()
    app.mainloop()
