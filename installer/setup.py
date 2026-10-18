"""One-window registration; portable verification never blocks the Tk loop."""
import json
from pathlib import Path
import queue
import sys
import threading
import tkinter as tk
from tkinter import messagebox,ttk
from install_native import install
from portable_bundle import verify_bundle


def self_test():
    """Verify frozen Tcl/Tk without registering a host or reading reader data."""
    root=tk.Tk()
    try:
        root.withdraw()
        root.update_idletasks()
    finally:root.destroy()


def main():
    root=tk.Tk();root.title("Live translation · companion");root.resizable(False,False)
    frame=ttk.Frame(root,padding=20);frame.grid()
    ttk.Label(frame,text="Kết nối companion",font=("Segoe UI",15,"bold")).grid(row=0,column=0,columnspan=2,sticky="w")
    ttk.Label(frame,text="Đăng ký cho tài khoản Windows hiện tại; thường không cần admin.").grid(row=1,column=0,columnspan=2,sticky="w",pady=(6,16))
    ttk.Label(frame,text="Trình duyệt").grid(row=2,column=0,sticky="w")
    browser=tk.StringVar(value="Edge")
    selection=ttk.Combobox(frame,textvariable=browser,values=("Edge","Chrome"),state="readonly",width=14)
    selection.grid(row=2,column=1,sticky="w")
    ttk.Label(frame,text="ID extension · có thể sửa").grid(row=3,column=0,columnspan=2,sticky="w",pady=(12,4))
    identifier=tk.StringVar();entry=ttk.Entry(frame,textvariable=identifier,width=48)
    entry.grid(row=4,column=0,columnspan=2,sticky="ew");entry.focus_set()
    ttk.Label(frame,text="Lấy ID tại edge://extensions hoặc chrome://extensions.").grid(row=5,column=0,columnspan=2,sticky="w",pady=(4,12))
    status=tk.StringVar(value="Bản thử riêng tư; chưa phải bản phát hành có chữ ký.")
    ttk.Label(frame,textvariable=status,wraplength=400).grid(row=6,column=0,columnspan=2,sticky="w")
    messages=queue.Queue(maxsize=20);busy=False
    folder=Path(sys.executable).resolve().parent if getattr(sys,"frozen",False) else None
    if folder and (folder/"bundle.json").is_file():
        try:identifier.set(json.loads((folder/"bundle.json").read_text(encoding="utf-8")).get("extensionId",""))
        except (ValueError,OSError):pass
    def submit():
        nonlocal busy
        if busy:return
        value=identifier.get().strip();selected=browser.get().lower();busy=True
        action.configure(state="disabled");entry.configure(state="disabled");selection.configure(state="disabled")
        status.set("Đang kiểm tra runtime và model; cửa sổ vẫn hoạt động…")
        def run():
            try:
                if folder and (folder/"bundle.json").is_file():
                    verify_bundle(folder)
                install(value,bundle_dir=folder,browser=selected)
                messages.put((True,"Đã đăng ký. Mở popup extension và bấm Kết nối lại."))
            except Exception as error:messages.put((False,str(error)))
        threading.Thread(target=run,daemon=True).start()
    action=ttk.Button(frame,text="Kiểm tra & kết nối",command=submit)
    action.grid(row=7,column=0,columnspan=2,sticky="ew",pady=(16,0))
    def poll():
        nonlocal busy
        try:
            success,value=messages.get_nowait();busy=False;status.set(value)
            action.configure(state="normal");entry.configure(state="normal");selection.configure(state="readonly")
            if success:messagebox.showinfo("Live translation",value,parent=root)
            else:messagebox.showerror("Live translation",value,parent=root)
        except queue.Empty:pass
        root.after(150,poll)
    def close():
        if busy:status.set("Đang kiểm tra/đăng ký. Chờ xong trước khi đóng để không ngắt giữa chừng.");return
        root.destroy()
    root.protocol("WM_DELETE_WINDOW",close);root.after(150,poll);root.mainloop()


if __name__=="__main__":
    if sys.argv[1:]==["--self-test"]:
        try:self_test()
        except Exception:raise SystemExit(1)
    else:main()
