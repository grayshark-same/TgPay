import fitz, qrcode, io

TEMPLATE = "/root/test_bot/esim_template_lifecell.pdf"
OUT = "/root/test_bot/_out.pdf"

ACT = "https://esimsetup.apple.com/esim_qrcode_provisioning?carddata=LPA:1$rsp-eu.redteamobile.com$264EC3BC2E59A99D51FDE50AC990AEB8"
lpa = ACT.split("carddata=", 1)[1]  # QR кодирует LPA-строку

# QR png
qr = qrcode.make(lpa)
buf = io.BytesIO(); qr.save(buf, format="PNG"); qr_png = buf.getvalue()

doc = fitz.open(TEMPLATE)
page = doc[0]

# область старого QR (display coords) — калибровка
qr_rect = fitz.Rect(696, 369, 810, 480)
# закрыть старый QR белым и вставить новый
page.draw_rect(qr_rect, color=(1, 1, 1), fill=(1, 1, 1))
page.insert_image(qr_rect, stream=qr_png)

doc.save(OUT)
pix = fitz.open(OUT)[0].get_pixmap(dpi=120, clip=fitz.Rect(550, 300, 900, 560))
pix.save("/root/test_bot/_qr.png")
print("saved")
