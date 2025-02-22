import asyncio
import sqlite3
import pandas as pd
import sys
import os  # Thêm import os để đọc biến môi trường
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext

# Lấy TOKEN từ biến môi trường, nếu không có thì dùng giá trị mặc định (dành cho test cục bộ)
TOKEN = os.environ.get("TOKEN", "7809066941:AAHXcMWaYTKro2yXKjYvE9aPIn9I_cm8b_Q")

# Kết nối database SQLite
conn = sqlite3.connect("truyen.db", check_same_thread=False)
cursor = conn.cursor()

# Tạo bảng dữ liệu nếu chưa có
cursor.execute("""
CREATE TABLE IF NOT EXISTS truyen (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ten_truyen TEXT UNIQUE,
    so_chuong INTEGER DEFAULT 0,
    ngay_doc TEXT
)
""")
conn.commit()

# Hàm start bot
async def start(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text("Xin chào! Hãy nhập tên truyện và số chương đã đọc theo format:\n\n/t tên_truyện số_chương")

# Hàm thêm hoặc cập nhật truyện và tự động xuất Excel
async def them_truyen(update: Update, context: CallbackContext) -> None:
    try:
        args = context.args
        if len(args) < 2:
            await update.message.reply_text("Sai cú pháp! Hãy nhập: /t tên_truyện số_chương")
            return

        ten_truyen = " ".join(args[:-1])
        so_chuong = int(args[-1])

        cursor.execute("SELECT so_chuong FROM truyen WHERE ten_truyen=?", (ten_truyen,))
        row = cursor.fetchone()

        if row:
            so_chuong_moi = max(so_chuong, row[0])  # Lấy số chương lớn nhất đã đọc
            cursor.execute("UPDATE truyen SET so_chuong=?, ngay_doc=date('now') WHERE ten_truyen=?", (so_chuong_moi, ten_truyen))
            await update.message.reply_text(f"📖 Cập nhật: {ten_truyen} - {so_chuong_moi} chương")
        else:
            cursor.execute("INSERT INTO truyen (ten_truyen, so_chuong, ngay_doc) VALUES (?, ?, date('now'))", (ten_truyen, so_chuong))
            await update.message.reply_text(f"✅ Đã thêm truyện: {ten_truyen} - {so_chuong} chương")

        conn.commit()

        # Tự động xuất dữ liệu ra file Excel
        cursor.execute("SELECT * FROM truyen")
        rows = cursor.fetchall()
        
        if rows:
            df = pd.DataFrame(rows, columns=["ID", "Tên Truyện", "Số Chương", "Ngày Đọc"])
            df.to_excel("TruyenDaDoc.xlsx", index=False)
            await update.message.reply_text("📋 Dữ liệu đã được tự động cập nhật vào file Excel 'TruyenDaDoc.xlsx'.")

    except ValueError:
        await update.message.reply_text("Vui lòng nhập số chương hợp lệ!")

# Hàm liệt kê các truyện đã đọc
async def danh_sach_truyen(update: Update, context: CallbackContext) -> None:
    cursor.execute("SELECT ten_truyen, so_chuong, ngay_doc FROM truyen")
    data = cursor.fetchall()
    
    if not data:
        await update.message.reply_text("Bạn chưa đọc truyện nào!")
        return

    reply_text = "\n".join([f"{row[0]} - {row[1]} chương (Cập nhật: {row[2]})" for row in data])
    await update.message.reply_text(reply_text)

# Hàm xuất danh sách ra Excel (giữ lại cho trường hợp cần xuất thủ công)
async def xuat_excel(update: Update, context: CallbackContext) -> None:
    cursor.execute("SELECT * FROM truyen")
    rows = cursor.fetchall()

    if not rows:
        await update.message.reply_text("Không có dữ liệu để xuất!")
        return

    df = pd.DataFrame(rows, columns=["ID", "Tên Truyện", "Số Chương", "Ngày Đọc"])
    df.to_excel("TruyenDaDoc.xlsx", index=False)

    await update.message.reply_document(document=open("TruyenDaDoc.xlsx", "rb"))
    await update.message.reply_text("📄 File Excel 'TruyenDaDoc.xlsx' đã được xuất và gửi cho bạn.")

# Hàm chạy bot
async def main():
    # Tạo ứng dụng
    app = Application.builder().token(TOKEN).build()

    # Thêm các handler
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("t", them_truyen))  # Ghi truyện
    app.add_handler(CommandHandler("list", danh_sach_truyen))  # Danh sách truyện
    app.add_handler(CommandHandler("export", xuat_excel))  # Xuất file Excel

    print("Bot đang chạy...")
    
    # Khởi tạo ứng dụng
    await app.initialize()
    # Bắt đầu polling
    await app.start()
    await app.updater.start_polling()  # Chạy bot với polling
    
    # Giữ bot chạy cho đến khi bị dừng thủ công (Ctrl+C)
    try:
        await asyncio.Event().wait()  # Chờ vô thời hạn
    except KeyboardInterrupt:
        print("Bot đang dừng...")
    
    # Dừng bot một cách sạch sẽ
    await app.updater.stop()
    await app.stop()
    await app.shutdown()

if __name__ == "__main__":
    # Cấu hình chính sách vòng lặp cho Windows nếu cần
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    # Chạy ứng dụng
    asyncio.run(main())