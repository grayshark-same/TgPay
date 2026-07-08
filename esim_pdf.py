import io
import os

import fitz
import qrcode
from PIL import Image, ImageDraw, ImageFont

_DIR = os.path.dirname(__file__)
_DPI = 150
_SCALE = _DPI / 72.0
_FONT_PATH = os.path.join(_DIR, "OpenSans-Bold.ttf")

_UA_INSTR = """Інструкція з встановлення eSIM

1. Увімкніть інтернет на смартфоні (Wi-Fi або мобільний інтернет з іншої SIM-карти).

2. Залежно від операційної системи:
• iOS: натисніть кнопку «Встановити eSIM» вище, перейдіть за посиланням або відскануйте QR-код. Вручну: Параметри > Стільникові дані > Додати eSIM > Використати QR-код.
• Android: Налаштування > Підключення > Диспетчер SIM-карт > Додавання eSIM > Сканувати QR-код.

3. Після встановлення підключіть бажаний тарифний план.

4. Завантажте застосунок My lifecell, щоб керувати послугами."""

_RU_INSTR = """Инструкция по установке eSIM

1. Включите интернет на устройстве (Wi-Fi или мобильный интернет с другой SIM-карты).

2. В зависимости от устройства:
• iOS: нажмите кнопку «Установить eSIM» выше, перейдите по ссылке или отсканируйте QR-код. Вручную: Настройки > Сотовая связь > Добавить eSIM > Использовать QR-код.
• Android: Настройки > Подключение > Диспетчер SIM-карт > Добавление eSIM > Сканировать QR-код.

3. После установки подключите нужный тариф.

4. Скачайте приложение для управления услугами."""

_UA_FOOTER = "Потрібна допомога при активації eSIM?\nПишіть нашому спеціалісту в Telegram — @donate008 (https://t.me/donate008)"
_RU_FOOTER = "Нужна помощь при активации eSIM?\nПишите нашему специалисту в Telegram — @donate008 (https://t.me/donate008)"

TEMPLATES = {
    "Lifecell": {
        "files": {"ua": "tpl_lifecell_ua.pdf", "ru": "esim_template_lifecell.pdf"},
        "fields": {
            "ua": [("+380638722617", "number"), ("9734", "pin1"),
                   ("37593898", "puk1"), ("89380062300760061399", "iccid")],
            "ru": [("+380638734653", "number"), ("7553", "pin1"),
                   ("15094066", "puk1"), ("89380062300758519044", "iccid")],
        },
        "order": ["number", "pin1", "puk1", "iccid"],
        "labels": {"number": "Номер eSIM", "pin1": "PIN1", "puk1": "PUK1",
                   "iccid": "ICCID", "activation_url": "ссылку активации (LPA)"},
        "qr_disp": (696, 369, 810, 480),
        "fontsize": 13,
        "cut_y": 695,          # display pt — низ картинки-шапки
        "page_w": 1200,        # display ширина pt
        "instr": {"ua": _UA_INSTR, "ru": _RU_INSTR},
        "footer": {"ua": _UA_FOOTER, "ru": _RU_FOOTER},
    },
    "Kievstar": {
        "mode": "fields",  # реальная вставка данных в PDF-шаблон (не фото)
        "template": "tpl_kievstar.pdf",
        "qr_rect": (348.75, 318.56005859375, 479.25, 449.06005859375),
        "placeholders": {
            "number": "+380 (98) 764 15 08",
            "tariff": "ВСЕ РАЗОМ Легкий",
            "exp": "25 березня 2027",
            "pin1": "1111",
            "pin2": "8953",
            "puk1": "1187 8259",
            "puk2": "6918 3288",
            "iccid": "8938 0039 9309 4754 18",
        },
        "order": ["number", "tariff", "pin1", "pin2", "puk1", "puk2", "iccid"],
        "labels": {
            "number": "Номер eSIM", "tariff": "Название тарифа",
            "pin1": "PIN1", "pin2": "PIN2", "puk1": "PUK1", "puk2": "PUK2",
            "iccid": "ICCID", "activation_url": "ссылку активации (LPA)",
        },
    },
}


def operators():
    return list(TEMPLATES.keys())


def fields_for(operator):
    cfg = TEMPLATES[operator]
    res = [(k, cfg["labels"][k]) for k in cfg["order"]]
    res.append(("activation_url", cfg["labels"]["activation_url"]))
    return res


def apple_url(activation):
    act = (activation or "").strip()
    lpa = act.split("carddata=", 1)[1] if "carddata=" in act else act
    return "https://esimsetup.apple.com/esim_qrcode_provisioning?carddata=" + lpa if lpa else ""


def _disp_rect(page, mb_rect):
    return (fitz.Rect(mb_rect) * page.rotation_matrix).normalize()


def _top_image(operator, lang, values):
    """PIL картинка шапки (данные+QR), обрезанная по cut_y."""
    cfg = TEMPLATES[operator]
    doc = fitz.open(os.path.join(_DIR, cfg["files"][lang]))
    page = doc[0]
    field_disp = {}
    for placeholder, key in cfg["fields"][lang]:
        rs = page.search_for(placeholder)
        if rs:
            field_disp[key] = _disp_rect(page, rs[0])

    pix = page.get_pixmap(dpi=_DPI)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples).convert("RGB")
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(_FONT_PATH, int(cfg["fontsize"] * _SCALE))

    for key, dr in field_disp.items():
        val = str(values.get(key, ""))
        x0, y0, x1, y1 = dr.x0 * _SCALE, dr.y0 * _SCALE, dr.x1 * _SCALE, dr.y1 * _SCALE
        draw.rectangle([x0 - 220, y0 - 3, x1 + 6, y1 + 3], fill="white")
        tb = draw.textbbox((0, 0), val, font=font)
        draw.text((x1 - (tb[2] - tb[0]), y0 - 2), val, font=font, fill="black")

    act = values.get("activation_url", "").strip()
    lpa = act.split("carddata=", 1)[1] if "carddata=" in act else act
    if lpa:
        qr = qrcode.make(lpa).convert("RGB")
        qx0, qy0, qx1, qy1 = [v * _SCALE for v in cfg["qr_disp"]]
        size = int(min(qx1 - qx0, qy1 - qy0))
        qr = qr.resize((size, size))
        draw.rectangle([qx0, qy0, qx0 + size, qy0 + size], fill="white")
        img.paste(qr, (int(qx0), int(qy0)))

    cut_px = int(cfg["cut_y"] * _SCALE)
    return img.crop((0, 0, img.width, cut_px))


def _add_body_page(out, cfg, lang, top_img, activation_url):
    w = cfg["page_w"]
    img_h = cfg["cut_y"]
    text_h = 470
    margin = 295  # под ширину карточки
    buf = io.BytesIO()
    top_img.save(buf, format="PNG")
    page = out.new_page(width=w, height=img_h + text_h)
    page.insert_image(fitz.Rect(0, 0, w, img_h), stream=buf.getvalue())
    page.insert_textbox(fitz.Rect(margin, img_h + 20, w - margin, img_h + text_h - 70),
                        cfg["instr"][lang], fontsize=13, fontname="F0",
                        fontfile=_FONT_PATH, color=(0, 0, 0), align=1)
    # кликабельные ссылки в тексте (синий цвет фраз)
    au = apple_url(activation_url)
    bot_url = "https://t.me/Paytelekom_bot?start=eSIM"
    link_phrases = []
    if au:
        link_phrases += [("по ссылке", au), ("за посиланням", au)]
    link_phrases += [("тариф.", bot_url), ("тарифний план.", bot_url)]
    for phrase, url in link_phrases:
        for r in page.search_for(phrase):
            page.insert_link({"kind": fitz.LINK_URI, "from": r, "uri": url})
            page.draw_rect(r, color=(1, 1, 1), fill=(1, 1, 1))
            page.insert_text((r.x0, r.y1 - 4), phrase, fontsize=13,
                             fontname="F0", fontfile=_FONT_PATH, color=(0, 0, 1))
    page.insert_textbox(fitz.Rect(margin, img_h + text_h - 65, w - margin, img_h + text_h - 8),
                        cfg["footer"][lang], fontsize=11, fontname="F0",
                        fontfile=_FONT_PATH, color=(0, 0, 0), align=1)


def make_esim_pdf(operator, out_path, values, langs=("ru", "ua")):
    cfg = TEMPLATES[operator]
    out = fitz.open()
    for lang in langs:
        if lang not in cfg["files"]:
            continue
        top = _top_image(operator, lang, values)
        _add_body_page(out, cfg, lang, top, values.get("activation_url", ""))
    out.save(out_path)
    return out_path


def _top_image_from_photo(operator, photo_path, activation_url):
    """Шапка: текстовый заголовок + присланное админом фото eSIM-карты (со своим QR)."""
    cfg = TEMPLATES[operator]
    w = cfg["page_w"]
    cut_y = cfg["cut_y"]
    title_h = 70

    photo = Image.open(photo_path).convert("RGB")
    scale = w / photo.width
    new_h = int(photo.height * scale)
    photo = photo.resize((w, new_h))
    photo_area_h = cut_y - title_h
    if new_h >= photo_area_h:
        photo = photo.crop((0, 0, w, photo_area_h))
    else:
        canvas = Image.new("RGB", (w, photo_area_h), "white")
        canvas.paste(photo, (0, 0))
        photo = canvas

    img = Image.new("RGB", (w, cut_y), "white")
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(_FONT_PATH, 30)
    title = f"Ваш eSIM {operator}"
    tb = draw.textbbox((0, 0), title, font=font)
    draw.text(((w - (tb[2] - tb[0])) / 2, (title_h - (tb[3] - tb[1])) / 2), title, font=font, fill="black")
    img.paste(photo, (0, title_h))

    return img


def make_esim_pdf_photo(operator, out_path, photo_path, activation_url, langs=("ru", "ua")):
    cfg = TEMPLATES[operator]
    out = fitz.open()
    top = _top_image_from_photo(operator, photo_path, activation_url)
    for lang in langs:
        if lang not in cfg["files"]:
            continue
        _add_body_page(out, cfg, lang, top, activation_url)
    out.save(out_path)
    return out_path


def _parse_lpa(activation_url):
    """Возвращает (lpa_строка_для_QR, smdp, code) из ссылки активации/LPA."""
    act = (activation_url or "").strip()
    lpa = act.split("carddata=", 1)[1] if "carddata=" in act else act
    parts = lpa.split("$")
    if len(parts) >= 3:
        return lpa, parts[1], parts[2]
    return lpa, "", ""


def make_esim_pdf_kievstar(out_path, values):
    """Вставляет реальные данные клиента в чистый (неповёрнутый) шаблон Kievstar."""
    cfg = TEMPLATES["Kievstar"]
    doc = fitz.open(os.path.join(_DIR, cfg["template"]))
    page = doc[0]

    lpa, smdp, code = _parse_lpa(values.get("activation_url", ""))
    full_lpa = f"LPA:1${smdp}${code}" if smdp and code else lpa

    pending = []  # (rect, new_text)
    for key, placeholder in cfg["placeholders"].items():
        new = values.get(key, "")
        if not new:
            continue
        for r in page.search_for(placeholder):
            page.add_redact_annot(r, fill=(1, 1, 1))
            pending.append((r, new))
    extra = [("consumer.rsp.world", smdp), ("Z1XMHD4WJ9IZTVVUEOPE3NMY", code)]
    if full_lpa:
        extra.append(("LPA:1$consumer.rsp.world$Z1XMHD4WJ9IZTVVUEOPE3NMY", full_lpa))
    for placeholder, new in extra:
        if not new:
            continue
        for r in page.search_for(placeholder):
            page.add_redact_annot(r, fill=(1, 1, 1))
            pending.append((r, new))

    if pending:
        page.apply_redactions()
        for r, new in pending:
            page.insert_text((r.x0, r.y1 - 2), new, fontsize=11, fontname="F0",
                             fontfile=_FONT_PATH, color=(0, 0, 0))

    if lpa:
        qr = qrcode.make(lpa).convert("RGB")
        buf = io.BytesIO()
        qr.save(buf, format="PNG")
        qr_rect = fitz.Rect(*cfg["qr_rect"])
        page.add_redact_annot(qr_rect, fill=(1, 1, 1))
        page.apply_redactions()
        page.insert_image(qr_rect, stream=buf.getvalue())

    doc.save(out_path)
    return out_path
