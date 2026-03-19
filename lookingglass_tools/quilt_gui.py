from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

from .quilt_builder import (
    QuiltBuildResult,
    build_quilts,
    describe_validation_issues,
    scan_render_sequences,
    validate_render_sequence,
)


class QuiltMakerApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Looking Glass Portrait Quilt Maker")
        self.geometry("820x600")
        self.minsize(780, 540)

        self.input_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.sequence_var = tk.StringVar()
        self.output_name_var = tk.StringVar()
        self.output_format_var = tk.StringVar(value="jpg")
        self.skip_incomplete_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(
            value="Choose a rendered-images folder, then scan for camera sequences."
        )

        self._message_queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self._worker_thread: threading.Thread | None = None
        self._available_sequences: dict[str, object] = {}

        self._build_widgets()
        self.after(100, self._poll_queue)

    def _build_widgets(self) -> None:
        container = ttk.Frame(self, padding=16)
        container.pack(fill="both", expand=True)
        container.columnconfigure(1, weight=1)
        container.rowconfigure(6, weight=1)

        ttk.Label(
            container,
            text="Build Portrait quilts from files named like arbitrary_name_00_000.jpeg.",
        ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 14))

        ttk.Label(container, text="Rendered Images").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Entry(container, textvariable=self.input_var).grid(
            row=1,
            column=1,
            sticky="ew",
            padx=8,
            pady=4,
        )
        ttk.Button(container, text="Browse...", command=self._browse_input).grid(
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

        ttk.Label(container, text="Sequence").grid(row=3, column=0, sticky="w", pady=4)
        self.sequence_box = ttk.Combobox(
            container,
            textvariable=self.sequence_var,
            state="readonly",
        )
        self.sequence_box.grid(row=3, column=1, sticky="ew", padx=8, pady=4)
        self.sequence_box.bind("<<ComboboxSelected>>", self._on_sequence_selected)
        ttk.Button(container, text="Scan Folder", command=self._scan_sequences).grid(
            row=3,
            column=2,
            sticky="ew",
            pady=4,
        )

        options_frame = ttk.Frame(container)
        options_frame.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(8, 10))
        options_frame.columnconfigure(1, weight=1)
        options_frame.columnconfigure(3, weight=1)

        ttk.Label(options_frame, text="Output Name").grid(row=0, column=0, sticky="w")
        ttk.Entry(options_frame, textvariable=self.output_name_var).grid(
            row=0,
            column=1,
            sticky="ew",
            padx=(8, 20),
        )
        ttk.Label(options_frame, text="Format").grid(row=0, column=2, sticky="w")
        ttk.Combobox(
            options_frame,
            textvariable=self.output_format_var,
            values=("jpg", "png"),
            state="readonly",
            width=10,
        ).grid(row=0, column=3, sticky="w", padx=8)

        ttk.Checkbutton(
            options_frame,
            text="Skip incomplete frame sets",
            variable=self.skip_incomplete_var,
        ).grid(row=1, column=0, columnspan=4, sticky="w", pady=(10, 0))

        self.build_button = ttk.Button(
            container,
            text="Create Quilts",
            command=self._start_build,
        )
        self.build_button.grid(row=5, column=0, columnspan=3, sticky="ew", pady=(0, 10))

        ttk.Label(container, textvariable=self.status_var).grid(
            row=6,
            column=0,
            columnspan=3,
            sticky="w",
            pady=(0, 8),
        )

        self.log_box = scrolledtext.ScrolledText(container, wrap="word", height=18, state="disabled")
        self.log_box.grid(row=7, column=0, columnspan=3, sticky="nsew")
        container.rowconfigure(7, weight=1)

        self._append_log("Ready.")

    def _append_log(self, message: str) -> None:
        self.log_box.configure(state="normal")
        self.log_box.insert("end", message + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _set_running(self, is_running: bool) -> None:
        state = "disabled" if is_running else "normal"
        self.build_button.configure(state=state)

    def _browse_input(self) -> None:
        path = filedialog.askdirectory(title="Select Rendered Images Folder")
        if path:
            self.input_var.set(path)
            self._scan_sequences()

    def _browse_output(self) -> None:
        path = filedialog.askdirectory(title="Select Output Folder")
        if path:
            self.output_var.set(path)

    def _scan_sequences(self) -> None:
        input_folder = self.input_var.get().strip()
        if not input_folder:
            messagebox.showerror("Missing Folder", "Select a rendered-images folder first.")
            return

        try:
            self._available_sequences = scan_render_sequences(input_folder)
        except Exception as exc:
            self._available_sequences = {}
            self.sequence_box["values"] = ()
            self.sequence_var.set("")
            self.status_var.set("Scan failed.")
            self._append_log(f"Error: {exc}")
            messagebox.showerror("Scan Failed", str(exc))
            return

        sequence_names = list(self._available_sequences)
        self.sequence_box["values"] = sequence_names
        if sequence_names:
            self.sequence_var.set(sequence_names[0])
            self._on_sequence_selected()

        frame_counts = [
            len(sequence.images_by_frame)
            for sequence in self._available_sequences.values()
        ]
        self.status_var.set(
            f"Found {len(sequence_names)} sequence(s) and {sum(frame_counts)} frame groups."
        )
        self._append_log("Scan completed.")

    def _on_sequence_selected(self, _event: object | None = None) -> None:
        sequence_name = self.sequence_var.get().strip()
        if not sequence_name:
            return

        sequence = self._available_sequences.get(sequence_name)
        if sequence is None:
            return

        self.output_name_var.set(sequence_name)
        validation = validate_render_sequence(sequence, expected_views=48)
        complete_frames = [
            frame
            for frame in validation.expected_frames
            if frame not in validation.missing_frames
            and frame not in validation.missing_scenes_by_frame
            and frame not in validation.extra_scenes_by_frame
        ]
        self._append_log(
            f"Selected sequence '{sequence_name}' with {len(sequence.images_by_frame)} detected frame groups."
        )
        if validation.has_issues:
            self.status_var.set("Sequence scanned. Missing scenes or frames were found.")
            self._append_log(describe_validation_issues(sequence, validation))
        else:
            self.status_var.set(
                f"Sequence scanned. {len(complete_frames)} complete frame set(s) ready."
            )

    def _start_build(self) -> None:
        if self._worker_thread is not None and self._worker_thread.is_alive():
            return

        input_folder = self.input_var.get().strip()
        output_folder = self.output_var.get().strip()
        sequence_name = self.sequence_var.get().strip()
        if not input_folder:
            messagebox.showerror("Missing Folder", "Select a rendered-images folder.")
            return
        if not output_folder:
            messagebox.showerror("Missing Output Folder", "Select an output folder.")
            return
        if not sequence_name:
            messagebox.showerror("Missing Sequence", "Scan the folder and choose a sequence.")
            return

        self._set_running(True)
        self.status_var.set("Creating quilts...")
        self._append_log("Starting quilt creation.")

        def worker() -> None:
            try:
                result = build_quilts(
                    images_dir=input_folder,
                    output_dir=output_folder,
                    sequence_prefix=sequence_name,
                    output_name=self.output_name_var.get().strip() or None,
                    output_format=self.output_format_var.get().strip() or "jpg",
                    skip_incomplete=self.skip_incomplete_var.get(),
                    progress_callback=lambda text: self._message_queue.put(("log", text)),
                )
                self._message_queue.put(("done", result))
            except Exception as exc:
                self._message_queue.put(("error", str(exc)))

        self._worker_thread = threading.Thread(target=worker, daemon=True)
        self._worker_thread.start()

    def _handle_done(self, result: QuiltBuildResult) -> None:
        self._set_running(False)
        summary = f"Created {len(result.output_paths)} quilt file(s)."
        if result.skipped_frames:
            summary += f" Skipped {len(result.skipped_frames)} incomplete frame(s)."
        self.status_var.set(summary)
        self._append_log("Quilt creation finished.")
        messagebox.showinfo("Done", summary)

    def _poll_queue(self) -> None:
        while True:
            try:
                event_type, payload = self._message_queue.get_nowait()
            except queue.Empty:
                break

            if event_type == "log":
                self._append_log(str(payload))
            elif event_type == "done":
                self._handle_done(payload)
            elif event_type == "error":
                self._set_running(False)
                self.status_var.set("Quilt creation failed.")
                self._append_log(f"Error: {payload}")
                messagebox.showerror("Build Failed", str(payload))

        self.after(100, self._poll_queue)


def main() -> None:
    app = QuiltMakerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
