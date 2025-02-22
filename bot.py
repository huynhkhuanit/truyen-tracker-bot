import asyncio
import psycopg2  # Sử dụng PostgreSQL để lưu dữ liệu lâu dài
import pandas as pd
import sys
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext

# Lấy TOKEN từ biến môi trường
TOKEN = os.environ.get("TOKEN", "7809066941:AAHXcMWaYTKro2yXKjYvE9aPIn9I_cm8b_Q")

# Kết nối đến PostgreSQL (sử dụng ElephantSQL miễn phí)
conn = psycopg2.connect(os.environ.get("DATABASE_URL"))
cursor = conn.cursor()

# Tạo bảng dữ liệu nếu chưa có
cursor.execute("""
CREATE TABLE IF NOT EXISTS truyen (
    id SERIAL PRIMARY KEY,
    user_id INTEGER,
    ten_truyen TEXT,
    so_chuong INTEGER DEFAULT 0,
    ngay_doc DATE DEFAULT CURRENT_DATE,
    UNIQUE(user_id, ten_truyen)
)
""")
conn.commit()

# Hàm start bot
async def start(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text("Xin chào! Hãy nhập tên truyện và số chương đã đọc theo format:\n\n/t tên_truyện số_chương")

# Hàm thêm hoặc cập nhật truyện
async def them_truyen(update: Update, context: CallbackContext) -> None:
    try:
        args = context.args
        if len(args) < 2:
            await update.message.reply_text("Sai cú pháp! Hãy nhập: /t tên_truyện số_chương")
            return

        ten_truyen = " ".join(args[:-1])
        so_chuong = int(args[-1])
        user_id = update.effective_user.id

        cursor.execute("SELECT so_chuong FROM truyen WHERE user_id=%s AND ten_truyen=%s", (user_id, ten_truyen))
        row = cursor.fetchone()

        if row:
            so_chuong_moi = max(so_chuong, row[0])
            cursor.execute("UPDATE truyen SET so_chuong=%s, ngay_doc=CURRENT_DATE WHERE user_id=%s AND ten_truyen=%s", 
                           (so_chuong_moi, user_id, ten_truyen))
            await update.message.reply_text(f"📖 Cập nhật: {ten_truyen} - {so_chuong_moi} chương")
        else:
            cursor.execute("INSERT INTO truyen (user_id, ten_truyen, so_chuong, ngay_doc) VALUES (%s, %s, %s, CURRENT_DATE)", 
                           (user_id, ten_truyen, so_chuong))
            await update.message.reply_text(f"✅ Đã thêm truyện: {ten_truyen} - {so_chuong} chương")

        conn.commit()

        # Tự động tạo file Excel tạm và gửi qua Telegram (không lưu trên Render)
        cursor.execute("SELECT * FROM truyen WHERE user_id=%s", (user_id,))
        rows = cursor.fetchall()
        
        if rows:
            df = pd.DataFrame(rows, columns=["ID", "User ID", "Tên Truyện", "Số Chương", "Ngày Đọc"])
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
                df.to_excel(tmp.name, index=False)
                with open(tmp.name, "rb") as excel_file:
                    await update.message.reply_document(document=excel_file, filename=f"TruyenDaDoc_{user_id}.xlsx")
            import os
            os.unlink(tmp.name)  # Xóa file tạm sau khi gửi
            await update.message.reply_text("📋 Dữ liệu đã được tự động cập nhật và gửi qua file Excel.")

    except ValueError:
        await update.message.reply_text("Vui lòng nhập số chương hợp lệ!")

# Hàm liệt kê các truyện đã đọc
async def danh_sach_truyen(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    cursor.execute("SELECT ten_truyen, so_chuong, ngay_doc FROM truyen WHERE user_id=%s", (user_id,))
    data = cursor.fetchall()
    
    if not data:
        await update.message.reply_text("Bạn chưa đọc truyện nào!")
        return

    reply_text = "\n".join([f"{row[0]} - {row[1]} chương (Cập nhật: {row[2]})" for row in data])
    await update.message.reply_text(reply_text)

# Hàm xuất danh sách ra Excel (gửi qua Telegram)
async def xuat_excel(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    cursor.execute("SELECT * FROM truyen WHERE user_id=%s", (user_id,))
    rows = cursor.fetchall()

    if not rows:
        await update.message.reply_text("Không có dữ liệu để xuất!")
        return

    df = pd.DataFrame(rows, columns=["ID", "User ID", "Tên Truyện", "Số Chương", "Ngày Đọc"])
    import tempfile
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        df.to_excel(tmp.name, index=False)
        with open(tmp.name, "rb") as excel_file:
            await update.message.reply_document(document=excel_file, filename=f"TruyenDaDoc_{user_id}.xlsx")
    import os
    os.unlink(tmp.name)  # Xóa file tạm sau khi gửi
    await update.message.reply_text("📄 File Excel đã được gửi cho bạn.")

# Hàm chạy bot với webhooks
async def main():
    app = Application.builder().token(TOKEN).build()
    
    # Thêm các handler
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("t", them_truyen))
    app.add_handler(CommandHandler("list", danh_sach_truyen))
    app.add_handler(CommandHandler("export", xuat_excel))

    # Cấu hình webhook
    await app.bot.set_webhook(url="https://<your-render-service>.onrender.com/")
    await app.run_webhook(listen="0.0.0.0", port=10000)  # Port mặc định trên Render

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())