import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import fitz  # PyMuPDF
from PIL import Image, ImageTk
import os
import sys
import threading


class PDFViewer(tk.Tk):
    def __init__(self, pdf_path=None):
        super().__init__()
        self.pdf_path = pdf_path
        self.doc = None
        self.current_page = 0
        self.zoom_level = 0.85  # Default 85%
        self.thumbs_images = []  # Cached thumbnails
        self.thumbnails_visible = False
        self.document_images = []  # Cached full document images for continuous scroll
        self.page_heights = []  # Heights for page calculation

        self.title("Simple PDF Reader v2.0")
        self.geometry("1200x850")
        self.minsize(800, 600)

        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.setup_ui()

        if pdf_path and os.path.isfile(pdf_path):
            self.open_pdf_document(pdf_path)
            self.load_document_continuous()
        else:
            self.after(200, self.show_welcome_screen)  # Delay for full render

    def setup_ui(self):
        # Toolbar
        toolbar = ttk.Frame(self, relief=tk.RAISED, padding=12)
        toolbar.pack(side=tk.TOP, fill=tk.X)

        button_width = 12

        ttk.Button(toolbar, text="Open PDF", width=button_width, command=self.open_new_pdf).grid(row=0, column=0, padx=6, pady=6)
        ttk.Button(toolbar, text="Previous", width=button_width, command=self.prev_page).grid(row=0, column=1, padx=6)
        self.page_label = ttk.Label(toolbar, text="No document", font=("Segoe UI", 11, "bold"), width=20, anchor="center")
        self.page_label.grid(row=0, column=2, padx=20)
        ttk.Button(toolbar, text="Next", width=button_width, command=self.next_page).grid(row=0, column=3, padx=6)

        ttk.Separator(toolbar, orient=tk.VERTICAL).grid(row=0, column=4, padx=25, sticky="ns")

        ttk.Button(toolbar, text="Zoom In", width=button_width, command=self.zoom_in).grid(row=0, column=5, padx=6)
        ttk.Button(toolbar, text="Zoom Out", width=button_width, command=self.zoom_out).grid(row=0, column=6, padx=6)
        ttk.Button(toolbar, text="Fit Width", width=button_width, command=self.fit_to_width).grid(row=0, column=7, padx=6)

        ttk.Label(toolbar, text="Zoom:", font=("Arial", 10)).grid(row=0, column=8, padx=(40, 8))
        self.zoom_display = ttk.Label(toolbar, text="85%", width=8, relief="sunken", anchor="center", font=("Arial", 10))
        self.zoom_display.grid(row=0, column=9, padx=6)

        ttk.Separator(toolbar, orient=tk.VERTICAL).grid(row=0, column=10, padx=25, sticky="ns")

        ttk.Button(toolbar, text="Thumbs", width=button_width, command=self.toggle_thumbnails).grid(row=0, column=11, padx=12)
        ttk.Button(toolbar, text="About", width=button_width, command=self.show_about).grid(row=0, column=12, padx=12)

        # Main frame for canvas and thumbnails
        self.main_frame = ttk.Frame(self)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=15)

        # Thumbnails sidebar (hidden by default)
        self.thumbs_frame = ttk.Frame(self.main_frame, width=150)
        self.thumbs_canvas = tk.Canvas(self.thumbs_frame, bg="lightgray", width=150, height=400)
        self.thumbs_scroll = ttk.Scrollbar(self.thumbs_frame, orient=tk.VERTICAL, command=self.thumbs_canvas.yview)
        self.thumbs_canvas.configure(yscrollcommand=self.thumbs_scroll.set)
        self.thumbs_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.thumbs_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.thumbs_frame.pack(side=tk.LEFT, fill=tk.Y)
        self.thumbs_frame.pack_forget()

        # Bind mouse wheel to thumbnails
        self.thumbs_canvas.bind("<MouseWheel>", self.on_thumbs_scroll)
        self.thumbs_canvas.bind("<Button-4>", self.on_thumbs_scroll)
        self.thumbs_canvas.bind("<Button-5>", self.on_thumbs_scroll)

        # Main canvas for continuous scrolling
        canvas_frame = ttk.Frame(self.main_frame)
        canvas_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(canvas_frame, bg="#f8f8f8", highlightthickness=0)
        v_scroll = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        h_scroll = ttk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL, command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        h_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Mouse bindings for main canvas
        self.canvas.bind("<MouseWheel>", self.handle_scroll)
        self.canvas.bind("<Button-4>", self.handle_scroll)
        self.canvas.bind("<Button-5>", self.handle_scroll)
        self.canvas.bind("<Control-MouseWheel>", self.on_ctrl_mousewheel)
        self.canvas.bind("<Configure>", self.on_canvas_resize)
        self.canvas.bind("<Enter>", lambda e: self.canvas.focus_set())  # Focus on hover

    def handle_scroll(self, event):
        """Combined handler for scroll + page label update"""
        if not self.doc:
            return

        # Scroll direction
        delta = getattr(event, "delta", 0)
        num = getattr(event, "num", 0)
        if delta > 0 or num == 4:
            self.canvas.yview_scroll(-2, "units")  # Up
        elif delta < 0 or num == 5:
            self.canvas.yview_scroll(2, "units")  # Down

        # Update page label
        self.update_current_page_from_scroll()

    def update_current_page_from_scroll(self):
        """Calculate current page from scroll position"""
        if not self.doc or not self.page_heights:
            return

        scroll_pos = self.canvas.yview()[0]
        total_height = self.canvas.bbox("all")[3] if self.canvas.bbox("all") else 0
        current_y = scroll_pos * total_height

        cumulative = 0
        for i, height in enumerate(self.page_heights):
            if current_y < cumulative + height:
                self.current_page = i
                self.update_page_info()
                break
            cumulative += height

    def on_thumbs_scroll(self, event):
        """Mouse wheel scroll for thumbnails"""
        if event.num == 4 or getattr(event, "delta", 0) > 0:
            self.thumbs_canvas.yview_scroll(-1, "units")
        else:
            self.thumbs_canvas.yview_scroll(1, "units")

    def on_ctrl_mousewheel(self, event):
        if not self.doc:
            return
        if event.delta > 0:
            self.zoom_in()
        else:
            self.zoom_out()

    def open_pdf_document(self, path):
        try:
            if self.doc:
                self.doc.close()
            self.doc = fitz.open(path)
            self.pdf_path = path
            self.current_page = 0
            self.zoom_level = 0.85
            self.thumbs_images = []
            self.document_images = []
            self.page_heights = []
            self.title(f"Simple PDF Reader v2.0 - {os.path.basename(path)}")
            self.update_page_info()
            self.load_document_continuous()
            self.generate_thumbnails()
        except Exception as e:
            messagebox.showerror("Error", f"Cannot open PDF:\n{e}")
            self.doc = None
            self.show_welcome_screen()

    def load_document_continuous(self):
        """Load all pages stacked for continuous scrolling"""
        if not self.doc:
            return

        self.document_images = []
        self.page_heights = []
        total_height = 0

        for page_num in range(len(self.doc)):
            page = self.doc[page_num]
            mat = fitz.Matrix(self.zoom_level, self.zoom_level)
            pix = page.get_pixmap(matrix=mat, alpha=False)

            img_width = pix.width
            img_height = pix.height
            canvas_width = self.canvas.winfo_width()
            x_offset = max(0, (canvas_width - img_width) // 2)

            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            page_photo = ImageTk.PhotoImage(img)
            self.document_images.append((page_photo, x_offset, total_height))
            self.page_heights.append(img_height + 20)  # Include gap

            # Stack vertically with 20px gap
            total_height += img_height + 20

        # Render all on canvas
        self.canvas.delete("all")
        for photo, x, y in self.document_images:
            self.canvas.create_image(x, y, image=photo, anchor="nw")

        self.canvas.config(scrollregion=(0, 0, self.canvas.winfo_width(), total_height))

        self.zoom_display.config(text=f"{int(self.zoom_level * 100)}%")

        # Focus canvas for scroll
        self.canvas.focus_set()

    def on_canvas_resize(self, event=None):
        if self.doc:
            self.load_document_continuous()

    def update_page_info(self):
        if self.doc:
            total = len(self.doc)
            self.page_label.config(text=f"Page {self.current_page + 1} of {total}")
        else:
            self.page_label.config(text="No document")

    def prev_page(self):
        if self.doc and self.current_page > 0:
            self.current_page -= 1
            self.update_page_info()
            self.refresh_thumbnails()
            # Scroll to page top
            page_y = sum(self.page_heights[:self.current_page])
            self.canvas.yview_moveto(page_y / self.canvas.bbox("all")[3])

    def next_page(self):
        if self.doc and self.current_page < len(self.doc) - 1:
            self.current_page += 1
            self.update_page_info()
            self.refresh_thumbnails()
            # Scroll to page top
            page_y = sum(self.page_heights[:self.current_page])
            self.canvas.yview_moveto(page_y / self.canvas.bbox("all")[3])

    def zoom_in(self):
        if not self.doc:
            return
        self.zoom_level = min(5.0, self.zoom_level * 1.25)
        self.load_document_continuous()

    def zoom_out(self):
        if not self.doc:
            return
        self.zoom_level = max(0.2, self.zoom_level * 0.8)
        self.load_document_continuous()

    def fit_to_width(self):
        if not self.doc:
            return
        canvas_width = self.canvas.winfo_width()
        if canvas_width <= 1:
            self.after(100, self.fit_to_width)
            return
        page = self.doc[0]  # Use first page for ratio
        self.zoom_level = max(0.3, (canvas_width - 100) / page.rect.width)
        self.load_document_continuous()

    def toggle_thumbnails(self):
        self.thumbnails_visible = not self.thumbnails_visible
        if self.thumbnails_visible:
            self.thumbs_frame.pack(side=tk.LEFT, fill=tk.Y)
            self.update_thumbnails()
        else:
            self.thumbs_frame.pack_forget()

    def generate_thumbnails(self):
        """Generate cached thumbnails in background thread for speed"""
        self.thumbs_images = []
        if not self.doc:
            return

        def generate():
            for page_num in range(len(self.doc)):
                page = self.doc[page_num]
                mat = fitz.Matrix(0.11, 0.11)
                pix = page.get_pixmap(matrix=mat)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                img = img.resize((120, int(120 * pix.height / pix.width)), Image.Resampling.LANCZOS)
                thumb = ImageTk.PhotoImage(img)
                self.thumbs_images.append(thumb)
            self.after(0, self._thumbnails_ready)

        threading.Thread(target=generate, daemon=True).start()

    def _thumbnails_ready(self):
        if self.thumbnails_visible:
            self.update_thumbnails()

    def refresh_thumbnails(self):
        if self.thumbnails_visible:
            self.update_thumbnails()

    def update_thumbnails(self):
        self.thumbs_canvas.delete("all")
        if not self.thumbs_images or not self.doc:
            return

        y_pos = 10
        thumb_width = 110

        for index, thumb in enumerate(self.thumbs_images):
            is_current = (index == self.current_page)
            border_color = "#4A90E2" if is_current else "#B0B0B0"
            border_width = 3 if is_current else 1

            img_height = thumb.height()

            rect_top = y_pos - 8
            rect_bot = y_pos + img_height + 22

            self.thumbs_canvas.create_rectangle(
                5, rect_top, thumb_width + 5, rect_bot,
                outline=border_color, width=border_width, tags=(f"thumb_rect_{index}")
            )

            self.thumbs_canvas.create_image(
                (thumb_width // 2) + 5, y_pos,
                image=thumb, anchor="n",
                tags=(f"thumb_img_{index}")
            )

            self.thumbs_canvas.create_text(
                (thumb_width // 2) + 5, y_pos + img_height + 10,
                text=f"Page {index + 1}",
                font=("Arial", 8, "bold" if is_current else "normal"),
                tags=(f"thumb_text_{index}")
            )

            def bind_all(tag):
                self.thumbs_canvas.tag_bind(
                    tag, "<Button-1>", lambda e, p=index: self.goto_thumb_page(p)
                )

            bind_all(f"thumb_rect_{index}")
            bind_all(f"thumb_img_{index}")
            bind_all(f"thumb_text_{index}")

            y_pos += img_height + 40

        self.thumbs_canvas.config(scrollregion=(0, 0, thumb_width + 10, y_pos + 20))

    def goto_thumb_page(self, page_num):
        if 0 <= page_num < len(self.doc):
            self.current_page = page_num
            self.update_page_info()
            self.refresh_thumbnails()
            # Scroll to page top
            page_y = sum(self.page_heights[:page_num])
            self.canvas.yview_moveto(page_y / self.canvas.bbox("all")[3])

    def show_about(self):
        messagebox.showinfo(
            "About Simple PDF Reader",
            "Simple PDF Reader v2.0\n\n"
            "Project Owner / Contributor: H Vikram Kondapalli\n"
            "Code Generator: Grok, created by xAI\n\n"
            "Built using:\n"
            "- Python\n"
            "- PyMuPDF (for PDF rendering)\n"
            "- Pillow (for image processing)\n"
            "- Tkinter (for the graphical user interface)\n\n"
            "A lightweight PDF reader with navigation, zoom and thumbnail features.\n\n"
            "Thank you for using this reader!"
        )

    def open_new_pdf(self):
        path = filedialog.askopenfilename(title="Open PDF File", filetypes=[("PDF Files", "*.pdf")])
        if path:
            self.open_pdf_document(path)

    def show_welcome_screen(self):
        self.canvas.delete("all")
        # Wait for canvas to be fully sized
        if self.canvas.winfo_width() > 1 and self.canvas.winfo_height() > 1:
            self.canvas.create_text(
                self.canvas.winfo_width() // 2,
                self.canvas.winfo_height() // 2,
                text="Simple PDF Reader v2.0\n\nClick 'Open PDF' to begin",
                font=("Helvetica", 22, "italic"),
                fill="gray60",
                anchor="center"
            )
        else:
            self.after(100, self.show_welcome_screen)  # Retry

    def on_closing(self):
        if self.doc:
            self.doc.close()
        self.destroy()


if __name__ == "__main__":
    path = None
    if len(sys.argv) > 1:
        path = sys.argv[1]
        if not os.path.isfile(path):
            path = None

    app = PDFViewer(path)
    app.mainloop()