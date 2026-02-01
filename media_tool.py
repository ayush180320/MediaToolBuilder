"""
APPLICATION SECURITY MANIFEST & AUDIT LOG
-----------------------------------------
App Name:       Media Workflow Studio Pro
Version:        8.5 (Anti-Ghosting Image Patch)
Author:         Ayush Singhal
Company:        Deluxe Media
Purpose:        Local image manipulation.

COPYRIGHT NOTICE:
The logic and architecture of this script were authored by Ayush Singhal.
"""

import customtkinter as ctk
from tkinter import filedialog, messagebox, Menu
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

# --- THEME CONFIGURATION ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

BaseClass = TkinterDnD.DnDWrapper if DRAG_DROP_AVAILABLE else object

class ProMediaTool(ctk.CTk, BaseClass):
    def __init__(self):
        super().__init__()

        self.title("Media Workflow Studio Pro v8.5")
        self.geometry("1100x750")
        self.minsize(1100, 750)
        
        # --- BINDINGS ---
        self.bind("<Control-Alt-a>", self._reveal_author)
        self.bind("<Button-3>", self.show_context_menu)
        
        # --- LAYOUT ---
        self.grid_columnconfigure(0, weight=4)
        self.grid_columnconfigure(1, weight=5)
        self.grid_rowconfigure(0, weight=1)

        # ============================================================
        # === LEFT PANEL =============================================
        # ============================================================
        self.left_frame = ctk.CTkFrame(self, corner_radius=0)
        self.left_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        # Tabs
        self.tab_view = ctk.CTkTabview(self.left_frame)
        self.tab_view.pack(fill="both", expand=True, padx=10, pady=10)

        self.tab_psd = self.tab_view.add("PSD Bulk Converter")
        self.tab_resize = self.tab_view.add("Smart Resizer")
        self.tab_banner = self.tab_view.add("HD Banner & Rename")

        # Rename Section
        self.rename_frame = ctk.CTkFrame(self.left_frame, fg_color="#2b2b2b", border_color="gray", border_width=1)
        self.rename_frame.pack(fill="x", padx=10, pady=20, side="bottom")

        ctk.CTkLabel(self.rename_frame, text="RENAME SELECTED FILE", font=("Roboto", 12, "bold")).pack(pady=(10,5))
        self.lbl_rename_target = ctk.CTkLabel(self.rename_frame, text="No file selected", text_color="gray")
        self.lbl_rename_target.pack(pady=2)

        self.entry_manual_name = ctk.CTkEntry(self.rename_frame, placeholder_text="Enter new filename...")
        self.entry_manual_name.pack(fill="x", padx=15, pady=5)
        self.entry_manual_name.bind("<KeyRelease>", self.on_manual_rename_type) 
        
        self.lbl_final_name = ctk.CTkLabel(self.rename_frame, text="Output: ...", text_color="#00E5FF", font=("Consolas", 11))
        self.lbl_final_name.pack(anchor="w", padx=15, pady=(0,10))

        # ============================================================
        # === RIGHT PANEL ============================================
        # ============================================================
        self.right_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="#1a1a1a")
        self.right_frame.grid(row=0, column=1, sticky="nsew", padx=(0,10), pady=10)
        
        self.lbl_preview_title = ctk.CTkLabel(self.right_frame, text="Live Preview", font=("Roboto", 18, "bold"))
        self.lbl_preview_title.pack(pady=(15, 5))

        # Dropdown
        self.selector_var = ctk.StringVar(value="No Files Selected")
        self.preview_selector = ctk.CTkOptionMenu(
            self.right_frame, 
            dynamic_resizing=False, 
            width=300, 
            variable=self.selector_var,
            command=self.on_selector_click
        )
        self.preview_selector.pack(pady=5)
        
        # Image Area
        self.lbl_preview_img = ctk.CTkLabel(self.right_frame, text="[Drag Files Here]\n\n(Right-Click to Clear)", width=286, height=410, fg_color="#222222", corner_radius=10)
        self.lbl_preview_img.pack(pady=10, padx=20)

        # File Info Area
        self.info_container = ctk.CTkFrame(self.right_frame, fg_color="transparent")
        self.info_container.pack(fill="both", expand=True, padx=20, pady=10)

        ctk.CTkLabel(self.info_container, text="FILE INFORMATION", font=("Roboto", 11, "bold"), text_color="gray").pack(anchor="w")

        self.info_box = ctk.CTkTextbox(self.info_container, height=100, fg_color="#222222", text_color="#00E5FF", font=("Consolas", 12))
        self.info_box.pack(fill="x", pady=5)
        self.info_box.insert("0.0", "Waiting for input...")
        self.info_box.configure(state="disabled")

        # ============================================================
        # === INTERNAL STATE =========================================
        # ============================================================
        self.file_list = []      
        self.file_names = []     
        self.custom_names_map = {} 
        self.current_preview_path = None
        self.persistent_image_ref = None 
        
        # Context Menu
        self.context_menu = Menu(self, tearoff=0)
        self.context_menu.add_command(label="Reset Workspace", command=self.reset_workspace)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="About", command=self._reveal_author)

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
    # === 1. STATE MANAGEMENT ====================================
    # ============================================================
    def show_context_menu(self, event):
        try: self.context_menu.tk_popup(event.x_root, event.y_root)
        finally: self.context_menu.grab_release()

    def reset_workspace(self):
        """Clears memory with safety flush."""
        # 1. Unbind Image from UI first
        self.lbl_preview_img.configure(image=None)
        self.update_idletasks() # Force UI update to release reference
        
        # 2. Clear Internal Data
        self.file_list = []
        self.file_names = []
        self.custom_names_map = {}
        self.current_preview_path = None
        self.persistent_image_ref = None

        # 3. Reset UI Elements
        self.selector_var.set("No Files Selected")
        self.preview_selector.configure(values=["No Files Selected"])
        self.lbl_preview_img.configure(text="[Drag Files Here]\n\n(Right-Click to Clear)")
        self.lbl_rename_target.configure(text="No file selected")
        self.entry_manual_name.delete(0, "end")
        self.lbl_final_name.configure(text="Output: ...")
        
        self.info_box.configure(state="normal")
        self.info_box.delete("0.0", "end")
        self.info_box.insert("0.0", "Waiting for input...")
        self.info_box.configure(state="disabled")

        for txt in [self.txt_psd, self.txt_res, self.txt_ban]:
            txt.configure(state="normal")
            txt.delete("0.0", "end")
            txt.configure(state="disabled")

    # ============================================================
    # === 2. FILE LOADING (PATCHED) ==============================
    # ============================================================
    def handle_files_input(self, files):
        if not files: return
        
        try:
            # 1. FILTER
            valid_files = [f for f in files if os.path.isfile(f)]
            if not valid_files:
                messagebox.showerror("Error", "No valid files detected.")
                return

            # --- CRITICAL FIX: SAFETY FLUSH ---
            # Remove the old image from the label BEFORE loading the new one.
            # This prevents "pyimageX doesn't exist" errors.
            self.lbl_preview_img.configure(image=None) 
            self.persistent_image_ref = None
            self.update_idletasks() 
            # ----------------------------------

            # 2. LOAD DATA
            self.file_list = list(valid_files)
            self.file_names = [os.path.basename(f) for f in valid_files]
            self.custom_names_map = {f: os.path.splitext(os.path.basename(f))[0] for f in valid_files}

            # 3. UPDATE UI
            self.preview_selector.configure(values=self.file_names)
            self.selector_var.set(self.file_names[0])
            
            active_box = self.txt_psd
            if self.tab_view.get() == "Smart Resizer": active_box = self.txt_res
            elif self.tab_view.get() == "HD Banner & Rename": active_box = self.txt_ban
            
            active_box.configure(state="normal")
            active_box.delete("0.0", "end")
            for f in self.file_names: active_box.insert("end", f"{f}\n")
            active_box.configure(state="disabled")

            # 4. START PREVIEW
            if self.file_list:
                self.current_preview_path = self.file_list[0]
                self.refresh_engine()
            
        except Exception as e:
            print(f"Error details: {e}")
            messagebox.showerror("Load Error", f"An error occurred while loading files:\n\n{str(e)}")

    def on_selector_click(self, selected_filename):
        if selected_filename == "No Files Selected" or not self.file_list: return
        try:
            # SAFETY FLUSH for Selector Click too
            self.lbl_preview_img.configure(image=None)
            self.update_idletasks()
            
            index = self.file_names.index(selected_filename)
            self.current_preview_path = self.file_list[index]
            self.refresh_engine()
        except: pass

    # ============================================================
    # === 3. PREVIEW ENGINE ======================================
    # ============================================================
    def refresh_engine(self):
        if not self.current_preview_path: return
        
        try:
            # Rename Logic
            self.lbl_rename_target.configure(text=f"Editing: {os.path.basename(self.current_preview_path)}")
            stored_name = self.custom_names_map.get(self.current_preview_path, "")
            self.entry_manual_name.delete(0, "end")
            self.entry_manual_name.insert(0, stored_name)
            self._update_suffix_label(stored_name)

            # Info Logic
            self.update_file_info(self.current_preview_path)

            # Image Logic
            self.generate_preview_image(self.current_preview_path)
        except Exception as e:
            print(f"Engine Error: {e}")

    def update_file_info(self, filepath):
        txt = "Reading..."
        try:
            size = os.path.getsize(filepath)
            size_str = f"{size/1024:.1f} KB" if size < 1024*1024 else f"{size/(1024*1024):.2f} MB"
            
            if filepath.lower().endswith(".psd"):
                p = PSDImage.open(filepath)
                dim = f"{p.width} x {p.height}"
                fmt = "PSD"
            else:
                i = Image.open(filepath)
                dim = f"{i.size[0]} x {i.size[1]}"
                fmt = i.format
            
            txt = f"File: {os.path.basename(filepath)}\nDimensions: {dim}\nFormat: {fmt}\nSize: {size_str}"
        except Exception as e:
            txt = f"Error reading info:\n{e}"

        self.info_box.configure(state="normal")
        self.info_box.delete("0.0", "end")
        self.info_box.insert("0.0", txt)
        self.info_box.configure(state="disabled")

    def generate_preview_image(self, filepath):
        try:
            # Generate Image Object
            if filepath.lower().endswith(".psd"):
                img = PSDImage.open(filepath).composite()
            else:
                img = Image.open(filepath)

            if self.tab_view.get() == "HD Banner & Rename":
                img = img.resize((286, 371), Image.Resampling.LANCZOS)
                canvas = Image.new("RGB", (286, 410), (255, 255, 255))
                canvas.paste(img, (0,0))
                
                tpl = "banner_2day.png" if self.ban_type.get() == "2day" else "banner_3day.png"
                tpl_path = self.resource_path(tpl)
                if os.path.exists(tpl_path):
                    ovl = Image.open(tpl_path).convert("RGBA").resize((286,410), Image.Resampling.LANCZOS)
                    canvas.paste(ovl, (0,0), mask=ovl)
                    img = canvas

            img.thumbnail((286, 410), Image.Resampling.LANCZOS)
            
            # Create CTkImage
            new_image = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
            
            # ASSIGN TO SELF BEFORE CONFIGURING UI
            self.persistent_image_ref = new_image
            
            # Configure UI
            self.lbl_preview_img.configure(image=self.persistent_image_ref, text="")
            
        except Exception as e:
            print(f"Preview Gen Error: {e}")
            self.lbl_preview_img.configure(image=None, text="Preview Error")

    def on_manual_rename_type(self, event):
        if not self.current_preview_path: return
        name = self.entry_manual_name.get()
        self.custom_names_map[self.current_preview_path] = name
        self._update_suffix_label(name)

    def _update_suffix_label(self, name):
        if self.tab_view.get() == "HD Banner & Rename":
            suf = "2DayBanner_286x410" if self.ban_type.get() == "2day" else "3DayBanner_286x410"
            self.lbl_final_name.configure(text=f"Output: {name}_{suf}.jpg")
        else:
            self.lbl_final_name.configure(text=f"Output: {name}.jpg")

    def refresh_preview(self):
        self.refresh_engine()

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
        f = ctk.CTkFrame(self.tab_psd, fg_color="transparent"); f.pack(pady=5)
        ctk.CTkButton(f, text="Select Files", command=lambda: self.select_files("psd")).pack(side="left", padx=5)
        
        self.txt_psd = ctk.CTkTextbox(self.tab_psd, height=150, state="disabled")
        self.txt_psd.pack(pady=5, fill="x")
        ctk.CTkButton(self.tab_psd, text="Convert All", fg_color="green", command=lambda: threading.Thread(target=self._process_psd, daemon=True).start()).pack(pady=10)

    def _process_psd(self):
        if not self.file_list: return messagebox.showwarning("Error", "No files selected")
        count = 0
        for f in self.file_list:
            try:
                out = os.path.join(os.path.dirname(f), "Converted_PSD")
                os.makedirs(out, exist_ok=True)
                psd = PSDImage.open(f)
                save_p = os.path.join(out, os.path.basename(os.path.splitext(f)[0] + ".jpg"))
                self.save_image_pro(psd.composite(), save_p)
                count += 1
            except: pass
        messagebox.showinfo("Report", f"Converted {count} files.")

    def _setup_resize_tab(self):
        ctk.CTkLabel(self.tab_resize, text="Smart Resizer", font=("Arial", 14, "bold")).pack(pady=5)
        f = ctk.CTkFrame(self.tab_resize, fg_color="transparent"); f.pack(pady=5)
        ctk.CTkButton(f, text="Select Files", command=lambda: self.select_files("img")).pack(side="left", padx=5)
        
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
                out = os.path.join(os.path.dirname(f), "Resized_Output")
                os.makedirs(out, exist_ok=True)
                img = Image.open(f)
                img = img.resize((w, h), Image.Resampling.LANCZOS)
                save_p = os.path.join(out, os.path.basename(os.path.splitext(f)[0] + f"_{self.res_var.get()}.jpg"))
                self.save_image_pro(img, save_p, img.info.get('dpi', (72,72)))
                count += 1
            except: pass
        messagebox.showinfo("Success", f"Resized {count} files.")

    def _setup_banner_tab(self):
        ctk.CTkLabel(self.tab_banner, text="HD Banner & Batch Rename", font=("Arial", 14, "bold")).pack(pady=5)
        f = ctk.CTkFrame(self.tab_banner, fg_color="transparent"); f.pack(pady=5)
        ctk.CTkButton(f, text="Select Files", command=lambda: self.select_files("img")).pack(side="left", padx=5)
        
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
        if not os.path.exists(self.resource_path(tpl)): return messagebox.showerror("Error", f"Missing {tpl}")
        
        count = 0
        for f in self.file_list:
            try:
                out = os.path.join(os.path.dirname(f), "Banner_Output")
                os.makedirs(out, exist_ok=True)
                img = Image.open(f)
                dpi = img.info.get('dpi', (72, 72))
                img = img.resize((286, 371), Image.Resampling.LANCZOS)
                img = img.filter(ImageFilter.UnsharpMask(radius=0.8, percent=110, threshold=3))
                
                can = Image.new("RGB", (286, 410), (255, 255, 255))
                can.paste(img, (0,0))
                ovl = Image.open(self.resource_path(tpl)).convert("RGBA").resize((286, 410), Image.Resampling.LANCZOS)
                can.paste(ovl, (0,0), mask=ovl)
                
                base = self.custom_names_map.get(f, os.path.splitext(os.path.basename(f))[0])
                suf = "2DayBanner_286x410" if self.ban_type.get() == "2day" else "3DayBanner_286x410"
                self.save_image_pro(can, os.path.join(out, f"{base}_{suf}.jpg"), dpi)
                count += 1
            except: pass
        messagebox.showinfo("Success", f"Processed {count} files.")

    def _reveal_author(self, event=None):
        messagebox.showinfo("Credits", "Code by Ayush Singhal | Deluxe Media")

if __name__ == "__main__":
    app = ProMediaTool()
    app.mainloop()
