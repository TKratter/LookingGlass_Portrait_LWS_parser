from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

from .lws_generator import DEFAULT_NUM_CAMERA_CHANNELS, DEFAULT_NUM_VIEWS, generate_lws_files


class LwsGeneratorApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Looking Glass Portrait LWS Generator")
        self.geometry("760x520")
        self.minsize(720, 480)

        self.source_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.views_var = tk.StringVar(value=str(DEFAULT_NUM_VIEWS))
        self.channels_var = tk.StringVar(value=str(DEFAULT_NUM_CAMERA_CHANNELS))
        self.status_var = tk.StringVar(value="Choose a LightWave scene and an output folder.")

        self._message_queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self._worker_thread: threading.Thread | None = None

        self._build_widgets()
        self.after(100, self._poll_queue)

    def _build_widgets(self) -> None:
        container = ttk.Frame(self, padding=16)
        container.pack(fill="both", expand=True)
        container.columnconfigure(1, weight=1)
        container.rowconfigure(5, weight=1)

        ttk.Label(
            container,
            text="Generate the 48 LightWave camera scenes for the Looking Glass Portrait.",
        ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 14))

        ttk.Label(container, text="Source .lws").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Entry(container, textvariable=self.source_var).grid(
            row=1,
            column=1,
            sticky="ew",
            padx=8,
            pady=4,
        )
        ttk.Button(container, text="Browse...", command=self._browse_source).grid(
            row=1,
            column=2,
            sticky="ew",
            pady=4,
        )

        ttk.Label(container, text="Output Folder").grid(row=2, column=0, sticky="w", pady=4)
        ttk.Entry(container, textvariable=self.output_var).grid(
            row=2,
            column=1,
            sticky="ew",
            padx=8,
            pady=4,
        )
        ttk.Button(container, text="Browse...", command=self._browse_output).grid(
            row=2,
            column=2,
            sticky="ew",
            pady=4,
        )

        options_frame = ttk.Frame(container)
        options_frame.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(8, 10))
        options_frame.columnconfigure(1, weight=1)
        options_frame.columnconfigure(3, weight=1)

        ttk.Label(options_frame, text="Views").grid(row=0, column=0, sticky="w")
        ttk.Entry(options_frame, textvariable=self.views_var, width=8).grid(
            row=0,
            column=1,
            sticky="w",
            padx=(8, 20),
        )
        ttk.Label(options_frame, text="Camera Channels").grid(row=0, column=2, sticky="w")
        ttk.Entry(options_frame, textvariable=self.channels_var, width=8).grid(
            row=0,
            column=3,
            sticky="w",
            padx=8,
        )

        self.generate_button = ttk.Button(
            container,
            text="Generate LWS Files",
            command=self._start_generation,
        )
        self.generate_button.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(0, 10))

        ttk.Label(container, textvariable=self.status_var).grid(
            row=5,
            column=0,
            columnspan=3,
            sticky="w",
            pady=(0, 8),
        )

        self.log_box = scrolledtext.ScrolledText(container, wrap="word", height=16, state="disabled")
        self.log_box.grid(row=6, column=0, columnspan=3, sticky="nsew")
        container.rowconfigure(6, weight=1)

        self._append_log("Ready.")

    def _browse_source(self) -> None:
        path = filedialog.askopenfilename(
            title="Select LightWave Scene",
            filetypes=[("LightWave Scene", "*.lws"), ("All Files", "*.*")],
        )
        if path:
            self.source_var.set(path)

    def _browse_output(self) -> None:
        path = filedialog.askdirectory(title="Select Output Folder")
        if path:
            self.output_var.set(path)

    def _append_log(self, message: str) -> None:
        self.log_box.configure(state="normal")
        self.log_box.insert("end", message + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _set_running(self, is_running: bool) -> None:
        state = "disabled" if is_running else "normal"
        self.generate_button.configure(state=state)

    def _start_generation(self) -> None:
        if self._worker_thread is not None and self._worker_thread.is_alive():
            return

        try:
            num_views = int(self.views_var.get().strip())
            num_channels = int(self.channels_var.get().strip())
        except ValueError:
            messagebox.showerror("Invalid Settings", "Views and camera channels must be whole numbers.")
            return

        source = self.source_var.get().strip()
        output = self.output_var.get().strip()
        if not source:
            messagebox.showerror("Missing Scene", "Select a LightWave scene file.")
            return
        if not output:
            messagebox.showerror("Missing Output Folder", "Select an output folder.")
            return

        self._set_running(True)
        self.status_var.set("Generating scene files...")
        self._append_log("Starting scene generation.")

        def worker() -> None:
            try:
                result = generate_lws_files(
                    source_path=source,
                    output_dir=output,
                    num_channels=num_channels,
                    num_views=num_views,
                    progress_callback=lambda text: self._message_queue.put(("log", text)),
                )
                self._message_queue.put(("done", result))
            except Exception as exc:
                self._message_queue.put(("error", str(exc)))

        self._worker_thread = threading.Thread(target=worker, daemon=True)
        self._worker_thread.start()

    def _poll_queue(self) -> None:
        while True:
            try:
                event_type, payload = self._message_queue.get_nowait()
            except queue.Empty:
                break

            if event_type == "log":
                self._append_log(str(payload))
            elif event_type == "done":
                result = payload
                self._set_running(False)
                self.status_var.set(
                    f"Created {len(result.output_paths)} files in {result.output_dir}."
                )
                self._append_log("Scene generation finished.")
                messagebox.showinfo(
                    "Done",
                    f"Created {len(result.output_paths)} scene files.",
                )
            elif event_type == "error":
                self._set_running(False)
                self.status_var.set("Scene generation failed.")
                self._append_log(f"Error: {payload}")
                messagebox.showerror("Generation Failed", str(payload))

        self.after(100, self._poll_queue)


def main() -> None:
    app = LwsGeneratorApp()
    app.mainloop()


if __name__ == "__main__":
    main()
