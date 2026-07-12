"""Genera assets/icono.ico (icono del .exe) dibujando el simbolo de marca con
Pillow — determinista, sin IA. Ejecutar: python generar_icono.py"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

VERDE = (47, 143, 91, 255)
VERDE_OSC = (30, 94, 58, 255)
CREMA = (251, 248, 242, 255)
HOJA = (191, 230, 204, 255)
TERRACOTA = (224, 96, 58, 255)

S = 256


def _fondo_degradado() -> Image.Image:
    """Fondo verde con degradado vertical suave y esquinas redondeadas."""
    grad = Image.new("RGBA", (S, S))
    gd = ImageDraw.Draw(grad)
    for y in range(S):
        t = y / (S - 1)
        col = tuple(round(VERDE[i] + (VERDE_OSC[i] - VERDE[i]) * t) for i in range(3)) + (255,)
        gd.line([(0, y), (S, y)], fill=col)
    mascara = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mascara).rounded_rectangle([0, 0, S - 1, S - 1], radius=56, fill=255)
    fondo = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    fondo.paste(grad, (0, 0), mascara)
    return fondo


def _icono() -> Image.Image:
    img = _fondo_degradado()
    d = ImageDraw.Draw(img)

    # Hoja: elipse en capa girada 40°.
    hoja = Image.new("RGBA", (110, 150), (0, 0, 0, 0))
    hd = ImageDraw.Draw(hoja)
    hd.ellipse([20, 10, 90, 140], fill=HOJA)
    hd.line([55, 25, 55, 125], fill=VERDE_OSC, width=4)
    hoja = hoja.rotate(38, expand=True, resample=Image.BICUBIC)
    img.alpha_composite(hoja, (int(S * 0.42), int(S * 0.06)))

    # Cuenco: borde + semicirculo inferior.
    cx, top = S // 2, int(S * 0.52)
    r = int(S * 0.30)
    d.rounded_rectangle([cx - r - 6, top - 8, cx + r + 6, top + 6], radius=7, fill=CREMA)
    d.pieslice([cx - r, top - r, cx + r, top + r], start=0, end=180, fill=CREMA)
    d.ellipse([cx - 8, top + r - 22, cx + 8, top + r - 6], fill=TERRACOTA)  # detalle
    return img


def main() -> None:
    img = _icono()
    salida = Path("assets") / "icono.ico"
    salida.parent.mkdir(exist_ok=True)
    img.save(salida, sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
    img.save(Path("assets") / "icono.png")
    print(f"Icono escrito en {salida}")


if __name__ == "__main__":
    main()
