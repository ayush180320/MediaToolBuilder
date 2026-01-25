# Media Workflow Studio Pro

**Automated Asset Generation Tool for Deluxe Media** *Developed by Ayush Singhal*

## Overview
Media Workflow Studio Pro is a secure, offline desktop application designed to streamline the production of digital media assets. It eliminates dependencies on external VDI environments (NICE DCV) and automates repetitive tasks such as PSD conversion, resizing, and banner template application.

## Features

### 1. PSD Bulk Converter
- Instantly converts batches of `.psd` files to high-quality `.jpg`.
- Handles layer compositing and CMYK to RGB conversion automatically.

### 2. Smart Resizer
- Batch resizes images to standard dimensions (e.g., 960x1440, 380x560).
- Uses **Lanczos Resampling** for high-quality downscaling without artifacts.
- Preserves original DPI.

### 3. HD Banner Automation
- Generates 2-Day and 3-Day campaign banners (286x410) from source artwork.
- Applies **Smart Sharpening (Unsharp Mask)** to ensure text legibility on small assets.
- Automatically renames files to campaign standards (e.g., `SummerSale_01_2Day.jpg`).

## Security & Compliance
- **Offline:** The tool has no internet capabilities and does not make network requests.
- **Local:** All processing happens on the local CPU; no data leaves the machine.
- **Portable:** Can be compiled to a standalone EXE.

## Installation / Usage

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
