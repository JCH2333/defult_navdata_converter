from __future__ import annotations

import json
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .convert import convert, export_intermediate_model
from .deployment import deploy
from .model_io import load_model
from .official_index import build_official_navaid_index
from .paths import detect_paths
from .profile import DEFAULT_CYCLE
from .update_manager import check_prerelease
from .validation import validate_candidate
from .version import __version__


BG = "#0d151e"
PANEL = "#142230"
TEXT = "#e8f1f8"
MUTED = "#92a7b8"
ACCENT = "#65d4c7"
WARNING = "#f6c56f"


class App:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title(f"424 → 默认通用导航数据 · {__version__} 测试版")
        self.root.geometry("1120x760")
        self.root.minsize(900, 620)
        self.root.configure(bg=BG)
        self.raw = tk.StringVar()
        self.base = tk.StringVar()
        self.jepp = tk.StringVar()
        self.baseline = tk.StringVar()
        self.general_doc_cache = tk.StringVar()
        self.general_doc_keypoint_cache_directory = tk.StringVar(value="enr-4.4")
        self.iap_ocr_cache_roots = tk.StringVar()
        self.reference = tk.StringVar()
        self.model_path = tk.StringVar()
        self.output = tk.StringVar(value=str(Path.cwd() / "output" / "candidate-2608-default"))
        self.target = tk.StringVar()
        self.status = tk.StringVar(value="等待检测")
        self.events: queue.Queue[tuple[str, object, object | None]] = queue.Queue()
        self.busy = False
        self._build()
        self.root.after(100, self._drain)
        self.root.after(250, self._detect)
        self.root.after(900, self._check_update)

    def _build(self) -> None:
        header = tk.Frame(self.root, bg=BG, padx=26, pady=20)
        header.pack(fill=tk.X)
        tk.Label(header, text="424  →  DEFAULT NAVDATA", bg=BG, fg=TEXT, font=("Segoe UI", 20, "bold")).pack(anchor=tk.W)
        tk.Label(header, text="2608 来源解析 · 官方全球基线 · 中国覆盖层 · 可恢复部署", bg=BG, fg=MUTED, font=("Microsoft YaHei UI", 10)).pack(anchor=tk.W, pady=(4, 0))
        banner = tk.Frame(self.root, bg="#2c2416", highlightthickness=1, highlightbackground="#67512a", padx=14, pady=9)
        banner.pack(fill=tk.X, padx=26)
        tk.Label(banner, text="发布安全门：只有参考成品字节一致且已完成实机验证的正式候选才能覆盖 Community。", bg="#2c2416", fg=WARNING, font=("Microsoft YaHei UI", 9, "bold")).pack(anchor=tk.W)
        paths = tk.Frame(self.root, bg=PANEL, highlightthickness=1, highlightbackground="#263544", padx=16, pady=14)
        paths.pack(fill=tk.X, padx=26, pady=14)
        rows = [
            ("2608 原始目录", self.raw, "dir"),
            ("官方 nav-base", self.base, "dir"),
            ("官方 nav-jepp", self.jepp, "dir"),
            ("官方设施索引", self.baseline, "file"),
            ("航路 OCR 缓存", self.general_doc_cache, "dir"),
            ("重要点 OCR 子目录", self.general_doc_keypoint_cache_directory, "text"),
            ("IAP OCR 共识缓存", self.iap_ocr_cache_roots, "dirs"),
            ("参考成品（只读）", self.reference, "dir"),
            ("中间模型（可选）", self.model_path, "model"),
            ("隔离候选输出", self.output, "dir"),
            ("Community 目标", self.target, "dir"),
        ]
        for row, (label, variable, kind) in enumerate(rows):
            tk.Label(paths, text=label, bg=PANEL, fg=MUTED, width=18, anchor=tk.E, font=("Microsoft YaHei UI", 9)).grid(row=row, column=0, sticky=tk.E, pady=5)
            tk.Entry(paths, textvariable=variable, bg="#0b1118", fg=TEXT, insertbackground=TEXT, relief=tk.FLAT, highlightthickness=1, highlightbackground="#314657").grid(row=row, column=1, sticky=tk.EW, padx=10, pady=5)
            if kind == "text":
                tk.Label(paths, text="", bg=PANEL, width=7).grid(
                    row=row,
                    column=2,
                    pady=5,
                )
            elif kind == "dirs":
                tk.Button(
                    paths,
                    text="添加",
                    command=lambda v=variable: self._add_directory(v),
                    bg="#203447",
                    fg=TEXT,
                    relief=tk.FLAT,
                    padx=12,
                ).grid(row=row, column=2, pady=5)
            else:
                tk.Button(
                    paths,
                    text="浏览",
                    command=lambda v=variable, k=kind: self._browse(v, k),
                    bg="#203447",
                    fg=TEXT,
                    relief=tk.FLAT,
                    padx=12,
                ).grid(row=row, column=2, pady=5)
        paths.columnconfigure(1, weight=1)
        actions = tk.Frame(self.root, bg=BG, padx=26, pady=4)
        actions.pack(fill=tk.X)
        for text, command in (
            ("自动检测", self._detect),
            ("生成官方索引", self._build_official_index),
            ("导出中间模型", self._export_model),
            ("生成候选", self._build_candidate),
            ("验证候选", self._validate),
            ("检查测试更新", self._check_update),
            ("备份并覆盖", self._deploy),
        ):
            tk.Button(actions, text=text, command=command, bg="#203447", fg=TEXT, activebackground="#2a5060", activeforeground=ACCENT, relief=tk.FLAT, padx=14, pady=7).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Label(self.root, textvariable=self.status).pack(anchor=tk.W, padx=26, pady=(6, 4))
        log_frame = tk.Frame(self.root, bg=PANEL, highlightthickness=1, highlightbackground="#263544", padx=10, pady=8)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=26, pady=(0, 22))
        self.log = tk.Text(log_frame, bg="#0b1118", fg="#c7d6e5", relief=tk.FLAT, wrap=tk.WORD, state=tk.DISABLED, font=("Consolas", 10))
        self.log.pack(fill=tk.BOTH, expand=True)

    def _browse(self, variable: tk.StringVar, kind: str) -> None:
        if kind == "file":
            value = filedialog.askopenfilename(
                filetypes=[("SQLite 数据库", "*.sqlite *.db3"), ("所有文件", "*.*")]
            )
        elif kind == "model":
            value = filedialog.askopenfilename(
                filetypes=[
                    ("中间模型", "*.json *.json.gz *.gz"),
                    ("所有文件", "*.*"),
                ]
            )
        else:
            value = filedialog.askdirectory()
        if value:
            variable.set(value)

    def _add_directory(self, variable: tk.StringVar) -> None:
        value = filedialog.askdirectory()
        if not value:
            return
        values = [item.strip() for item in variable.get().split(";") if item.strip()]
        if value not in values:
            values.append(value)
        variable.set(";".join(values))

    def _detect(self) -> None:
        detected = detect_paths()
        for variable, value in (
            (self.raw, detected.raw_root),
            (self.base, detected.nav_base),
            (self.jepp, detected.nav_jepp),
            (self.reference, detected.reference_root),
            (self.target, detected.community_root),
        ):
            if value and not variable.get():
                variable.set(str(value))
        self.status.set("路径检测完成")
        self._write("已检测本机 2608 原始数据、官方基线、参考目录和 Community 路径")

    def _required_baseline(self) -> bool:
        directories = (
            (self.base, "nav-base"),
            (self.jepp, "nav-jepp"),
        )
        missing = [
            label for variable, label in directories
            if not Path(variable.get()).is_dir()
        ]
        if missing:
            messagebox.showerror("输入不完整", "缺少：" + "、".join(missing))
            return False
        return True

    def _required(self) -> bool:
        if not self._required_baseline():
            return False
        if Path(self.model_path.get()).is_file():
            return True
        if not Path(self.raw.get()).is_dir():
            messagebox.showerror("输入不完整", "缺少：2608 原始目录")
            return False
        return True

    def _run(self, action, on_success=None) -> None:
        if self.busy:
            return
        self.busy = True
        def worker() -> None:
            try:
                self.events.put(("done", action(), on_success))
            except Exception as error:
                self.events.put(("error", error, None))
        threading.Thread(target=worker, daemon=True).start()

    def _build_official_index(self) -> None:
        if not self._required_baseline():
            return
        self.status.set("正在生成并校验官方设施索引")
        output = Path(self.baseline.get()) if self.baseline.get().strip() else None
        self._run(
            lambda: build_official_navaid_index(
                nav_base=Path(self.base.get()),
                nav_jepp=Path(self.jepp.get()),
                output=output,
            ).to_report(),
            self._set_baseline_index,
        )

    def _set_baseline_index(self, report: object) -> None:
        if isinstance(report, dict) and isinstance(report.get("database"), str):
            self.baseline.set(report["database"])

    def _build_candidate(self) -> None:
        if not self._required():
            return
        output = Path(self.output.get())
        model_path = (
            Path(self.model_path.get())
            if Path(self.model_path.get()).is_file()
            else None
        )
        model = load_model(model_path) if model_path else None
        raw = Path(self.raw.get())
        if not raw.is_dir() and model is not None:
            raw = model.root
        self.status.set(
            "正在从中间模型生成候选" if model is not None else "正在解析来源并生成候选"
        )
        self._run(lambda: convert(
            raw,
            Path(self.base.get()),
            Path(self.jepp.get()),
            output,
            cycle=DEFAULT_CYCLE,
            reference=(
                Path(self.reference.get())
                if Path(self.reference.get()).is_dir()
                else None
            ),
            baseline_db=(
                Path(self.baseline.get())
                if Path(self.baseline.get()).is_file()
                else None
            ),
            general_doc_cache=(
                Path(self.general_doc_cache.get())
                if Path(self.general_doc_cache.get()).is_dir()
                else None
            ),
            general_doc_key_point_cache_directory=(
                self.general_doc_keypoint_cache_directory.get().strip()
                or "enr-4.4"
            ),
            iap_ocr_cache_roots=(
                ()
                if model is not None
                else tuple(
                    Path(value.strip())
                    for value in self.iap_ocr_cache_roots.get().split(";")
                    if value.strip()
                )
            ),
            model=model,
            model_path=model_path,
        ))

    def _export_model(self) -> None:
        if not Path(self.raw.get()).is_dir():
            messagebox.showerror("输入不完整", "缺少：2608 原始目录")
            return
        value = filedialog.asksaveasfilename(
            defaultextension=".json.gz",
            filetypes=[
                ("压缩中间模型", "*.json.gz"),
                ("中间模型 JSON", "*.json"),
                ("所有文件", "*.*"),
            ],
        )
        if not value:
            return
        output = Path(value)
        self.status.set("正在导出中间模型")
        self._run(
            lambda: export_intermediate_model(
                Path(self.raw.get()),
                output,
                general_doc_cache=(
                    Path(self.general_doc_cache.get())
                    if Path(self.general_doc_cache.get()).is_dir()
                    else None
                ),
                general_doc_key_point_cache_directory=(
                    self.general_doc_keypoint_cache_directory.get().strip()
                    or "enr-4.4"
                ),
                iap_ocr_cache_roots=tuple(
                    Path(item.strip())
                    for item in self.iap_ocr_cache_roots.get().split(";")
                    if item.strip()
                ),
            ),
            self._set_model_path,
        )

    def _set_model_path(self, report: object) -> None:
        if isinstance(report, dict) and isinstance(report.get("output"), str):
            self.model_path.set(report["output"])

    def _validate(self) -> None:
        candidate = Path(self.output.get())
        self.status.set("正在验证候选")
        self._run(lambda: validate_candidate(candidate, Path(self.reference.get()) if Path(self.reference.get()).is_dir() else None))

    def _deploy(self) -> None:
        candidate = Path(self.output.get())
        target = Path(self.target.get())
        if messagebox.askyesno("安全确认", "仅正式候选可以覆盖 Community。现在执行完整发布门禁检查吗？") is False:
            return
        self.status.set("正在备份并覆盖")
        self._run(lambda: deploy(candidate, target))

    def _check_update(self) -> None:
        def work():
            release = check_prerelease()
            return {"update": release.__dict__ if release else None}
        self._run(work)

    def _write(self, value: object) -> None:
        self.log.configure(state=tk.NORMAL)
        self.log.insert(tk.END, str(value) + "\n")
        self.log.see(tk.END)
        self.log.configure(state=tk.DISABLED)

    def _drain(self) -> None:
        try:
            while True:
                kind, value, on_success = self.events.get_nowait()
                self.busy = False
                if kind == "error":
                    self.status.set("操作失败")
                    self._write("[失败] " + str(value))
                    messagebox.showerror("操作失败", str(value))
                else:
                    if callable(on_success):
                        on_success(value)
                    self.status.set("操作完成")
                    self._write(json.dumps(value, ensure_ascii=False, indent=2, default=str))
        except queue.Empty:
            pass
        self.root.after(100, self._drain)


def main() -> None:
    App().root.mainloop()
