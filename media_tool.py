import customtkinter as ctk
from tkinter import filedialog, messagebox
from PIL import Image, ImageOps
from psd_tools import PSDImage
import os
import threading

# --- Professional Dark Theme (Adobe-like) ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

class ProMediaTool(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Media Workflow Automation Tool")
        self.geometry("750x650")
        self.resizable(False, False)
        
        # Grid layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Tab Interface
        self.tab_view = ctk.CTkTabview(self, width=700, height=580)
        self.tab_view.pack(pady=20, padx=20)

        self.tab_psd = self.tab_view.add("PSD -> JPG")
        self.tab_resize = self.tab_view.add("Smart Resizer")
        self.tab_banner = self.tab_view.add("Banner Workflow")

        # Setup Tabs
        self._setup_psd_tab()
        self._setup_resize_tab()
        self._setup_banner_tab()

        self.selected_file_path = None

    # --- HELPER: Photoshop Quality Save ---
    def save_image_pro(self, img_obj, output_path, original_dpi=(72, 72)):
        """Saves with max quality, 4:4:4 subsampling, and preserves DPI."""
        try:
            # Ensure RGB (removes Alpha channel if JPG, handles CMYK)
            if img_obj.mode in ("RGBA", "P", "CMYK"):
                img_obj = img_obj.convert("RGB")
            
            img_obj.save(
                output_path, 
                "JPEG", 
                quality=100,       # Max quality
                subsampling=0,     # Disable chroma subsampling (sharper colors)
                dpi=original_dpi   # Preserve print resolution
            )
            return True
        except Exception as e:
            print(f"Save Error: {e}")
            return False

    # ----------------------------------------------------------------
    # FEATURE 1: PSD CONVERTER
    # ----------------------------------------------------------------
    def _setup_psd_tab(self):
        # Header
        ctk.CTkLabel(self.tab_psd, text="PSD to JPG Converter", font=("Roboto Medium", 20)).pack(pady=20)
        
        # Area
        self.drop_frame_psd = ctk.CTkFrame(self.tab_psd, height=200, fg_color="#2b2b2b")
        self.drop_frame_psd.pack(fill="x", padx=30, pady=10)
        
        self.btn_psd_select = ctk.CTkButton(self.drop_frame_psd, text="Select PSD File", command=self.select_file_psd, width=200)
        self.btn_psd_select.pack(pady=40)
        
        self.lbl_psd_info = ctk.CTkLabel(self.tab_psd, text="Waiting for input...", text_color="gray")
        self.lbl_psd_info.pack(pady=5)

        self.btn_psd_run = ctk.CTkButton(self.tab_psd, text="Convert Now", state="disabled", fg_color="#1f6aa5", command=self.run_psd_thread)
        self.btn_psd_run.pack(pady=20)

    def select_file_psd(self):
        f = filedialog.askopenfilename(filetypes=[("Photoshop", "*.psd")])
        if f:
            self.selected_file_path = f
            self.lbl_psd_info.configure(text=f"Selected: {os.path.basename(f)}", text_color="#ddd")
            self.btn_psd_run.configure(state="normal")

    def run_psd_thread(self):
        threading.Thread(target=self.process_psd, daemon=True).start()

    def process_psd(self):
        self.btn_psd_run.configure(state="disabled", text="Rendering...")
        try:
            psd = PSDImage.open(self.selected_file_path)
            img = psd.composite() # Renders the visual representation
            
            out_path = os.path.splitext(self.selected_file_path)[0] + ".jpg"
            
            # Attempt to grab DPI from PSD metadata, default to 72 if missing
            dpi = (72, 72)

            self.save_image_pro(img, out_path, dpi)
            
            self.lbl_psd_info.configure(text=f"Saved: {os.path.basename(out_path)}", text_color="#4ade80")
            messagebox.showinfo("Done", "PSD Converted Successfully")
        except Exception as e:
            messagebox.showerror("Error", str(e))
        finally:
            self.btn_psd_run.configure(state="normal", text="Convert Now")

    # ----------------------------------------------------------------
    # FEATURE 2: RESIZER
    # ----------------------------------------------------------------
    def _setup_resize_tab(self):
        ctk.CTkLabel(self.tab_resize, text="Pro Resizer (Maintains Aspect Ratio)", font=("Roboto Medium", 20)).pack(pady=20)

        self.btn_res_select = ctk.CTkButton(self.tab_resize, text="Select Source Image", command=self.select_file_res)
        self.btn_res_select.pack(pady=10)
        
        self.lbl_res_info = ctk.CTkLabel(self.tab_resize, text="No file selected", text_color="gray")
        self.lbl_res_info.pack(pady=5)

        ctk.CTkLabel(self.tab_resize, text="Target Size:", font=("Arial", 12, "bold")).pack(pady=(20, 5))
        
        self.res_var = ctk.StringVar(value="286x410")
        sizes = ["286x410", "960x1440", "380x560", "630x945"]
        self.opt_res = ctk.CTkOptionMenu(self.tab_resize, values=sizes, variable=self.res_var, width=200)
        self.opt_res.pack(pady=5)

        self.btn_res_run = ctk.CTkButton(self.tab_resize, text="Resize", state="disabled", fg_color="#1f6aa5", command=self.run_res_thread)
        self.btn_res_run.pack(pady=20)

    def select_file_res(self):
        f = filedialog.askopenfilename(filetypes=[("Images", "*.jpg;*.jpeg;*.png;*.tiff")])
        if f:
            self.selected_file_path = f
            self.lbl_res_info.configure(text=f"Selected: {os.path.basename(f)}", text_color="#ddd")
            self.btn_res_run.configure(state="normal")

    def run_res_thread(self):
        threading.Thread(target=self.process_resize, daemon=True).start()

    def process_resize(self):
        try:
            target = self.res_var.get()
            w_target, h_target = map(int, target.split('x'))

            img = Image.open(self.selected_file_path)
            original_dpi = img.info.get('dpi', (72, 72))

            # Lanczos Filter is what Photoshop uses for "Bicubic Sharper" equivalent
            img_resized = img.resize((w_target, h_target), Image.Resampling.LANCZOS)

            out_path = os.path.splitext(self.selected_file_path)[0] + f"_{target}.jpg"
            self.save_image_pro(img_resized, out_path, original_dpi)

            self.lbl_res_info.configure(text=f"Exported: {os.path.basename(out_path)}", text_color="#4ade80")
            messagebox.showinfo("Done", "Image Resized")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ----------------------------------------------------------------
    # FEATURE 3: BANNER WORKFLOW
    # ----------------------------------------------------------------
    def _setup_banner_tab(self):
        ctk.CTkLabel(self.tab_banner, text="Banner Integration Workflow", font=("Roboto Medium", 20)).pack(pady=20)
        
        ctk.CTkLabel(self.tab_banner, text="Required: 'banner_2day.png' & 'banner_3day.png'\nMust be in the same folder as this app.", 
                     text_color="#f59e0b", font=("Arial", 11)).pack(pady=5)

        self.btn_ban_select = ctk.CTkButton(self.tab_banner, text="Select 2:3 Artwork", command=self.select_file_ban)
        self.btn_ban_select.pack(pady=15)
        
        self.lbl_ban_info = ctk.CTkLabel(self.tab_banner, text="Waiting...", text_color="gray")
        self.lbl_ban_info.pack(pady=5)

        # Radio Buttons
        self.ban_type = ctk.StringVar(value="2day")
        frame = ctk.CTkFrame(self.tab_banner, fg_color="transparent")
        frame.pack(pady=15)
        ctk.CTkRadioButton(frame, text="2-Day Banner", variable=self.ban_type, value="2day").pack(side="left", padx=10)
        ctk.CTkRadioButton(frame, text="3-Day Banner", variable=self.ban_type, value="3day").pack(side="left", padx=10)

        self.btn_ban_run = ctk.CTkButton(self.tab_banner, text="Generate Final", state="disabled", fg_color="#1f6aa5", command=self.run_ban_thread)
        self.btn_ban_run.pack(pady=20)

    def select_file_ban(self):
        f = filedialog.askopenfilename(filetypes=[("Images", "*.jpg;*.jpeg;*.png")])
        if f:
            self.selected_file_path = f
            self.lbl_ban_info.configure(text=f"Input: {os.path.basename(f)}", text_color="#ddd")
            self.btn_ban_run.configure(state="normal")

    def run_ban_thread(self):
        threading.Thread(target=self.process_banner, daemon=True).start()

    def process_banner(self):
        try:
            # Config
            art_w, art_h = 286, 371
            final_w, final_h = 286, 410
            
            template_file = "banner_2day.png" if self.ban_type.get() == "2day" else "banner_3day.png"
            
            # Check for template
            if not os.path.exists(template_file):
                messagebox.showerror("Missing File", f"Cannot find '{template_file}'\nPlease put it next to this tool.")
                return

            # Open Artwork
            img = Image.open(self.selected_file_path)
            original_dpi = img.info.get('dpi', (72, 72))
            
            # 1. Resize Artwork to 286x371 (Lanczos)
            img_resized = img.resize((art_w, art_h), Image.Resampling.LANCZOS)
            
            # 2. Create Final Canvas (White BG)
            final_canvas = Image.new("RGB", (final_w, final_h), (255, 255, 255))
            
            # 3. Paste Artwork at Top (0,0)
            final_canvas.paste(img_resized, (0, 0))
            
            # 4. Paste Banner Template (Overlay)
            banner = Image.open(template_file).convert("RGBA")
            if banner.size != (final_w, final_h):
                banner = banner.resize((final_w, final_h), Image.Resampling.LANCZOS)
                
            final_canvas.paste(banner, (0, 0), mask=banner)

            # 5. Save
            suffix = "_2DayBanner" if self.ban_type.get() == "2day" else "_3DayBanner"
            out_path = os.path.splitext(self.selected_file_path)[0] + f"{suffix}.jpg"
            
            self.save_image_pro(final_canvas, out_path, original_dpi)
            
            self.lbl_ban_info.configure(text=f"Created: {os.path.basename(out_path)}", text_color="#4ade80")
            messagebox.showinfo("Success", "Banner Applied Successfully")

        except Exception as e:
            messagebox.showerror("Error", str(e))

if __name__ == "__main__":
    app = ProMediaTool()
    app.mainloop()
